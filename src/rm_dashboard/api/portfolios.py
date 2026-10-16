"""Portfolio level views: rows on a client, mandate status and ``/api/portfolios/{id}``."""

from datetime import date
from typing import Literal

import polars as pl
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rm_dashboard.analytics import mandate as mandate_calc
from rm_dashboard.analytics import sector as sector_calc

from .context import ReadContext
from .deps import AsOf, Ctx
from .holdings import at, change, holdings_over_time, snapshots_at, total_usd
from .models import HasGaps, gap

router = APIRouter(prefix="/api", tags=["portfolios"])

MandateStatus = Literal["in_band", "out_of_band", "no_mandate"]
BreachStatus = Literal["no_note", "acknowledged", "client_directed", "contradicted"]
BreachKind = Literal["band", "position", "exclusion"]


class NoteQuote(BaseModel):
    note_id: str
    note_date: date
    quote: str


class BreachReconciliation(BaseModel):
    """What the RM's notes say about one computed breach. The portfolio list carries ids only; the detail adds the quotes."""

    portfolio_id: str
    kind: BreachKind
    key: str
    status: BreachStatus
    note_ids: list[str] = []
    description: str = ""
    rationale: str = ""
    waiver_claimed: bool = False
    notes: list[NoteQuote] = []


class ExclusionBreach(BaseModel):
    instrument_id: str
    instrument_name: str
    held: Literal["direct", "look_through"]
    via_instrument_id: str | None = None
    via_instrument_name: str | None = None
    value: float
    weight_pct: float
    key: str
    status: BreachStatus = "no_note"
    note_ids: list[str] = []


class PortfolioRow(BaseModel):
    portfolio_id: str
    portfolio_name: str
    mandate_code: str
    mandate_name: str
    service_model: str
    base_currency: str
    aum_usd: float
    aum_base: float
    previous_aum_usd: float | None = None
    change_usd: float | None = None
    change_pct: float | None = None
    mandate_status: MandateStatus
    breach_count: int = 0
    breach_reconciliation: list[BreachReconciliation] = []


class AumPoint(BaseModel):
    snapshot_date: date
    aum_usd: float
    aum_base: float


class Band(BaseModel):
    asset_class: str
    weight_pct: float
    min_pct: float
    target_pct: float
    max_pct: float
    gap_pp: float
    breach: Literal["above_max", "below_min"] | None = None
    out_of_band: bool


class PositionLimit(BaseModel):
    max_single_position_pct: float | None = None
    largest_instrument_id: str | None = None
    largest_instrument_name: str | None = None
    largest_weight_pct: float | None = None
    breaches: list[dict] = []
    note: str = ""


class HoldingRow(BaseModel):
    instrument_id: str
    instrument_name: str
    asset_class: str
    sub_asset_class: str
    sector: str | None = None
    instrument_ccy: str
    quantity: float
    market_value_usd: float
    market_value_base: float
    weight_pct: float
    unrealised_pnl_base: float | None = None
    unrealised_pnl_pct: float | None = None
    liquidity_tier: str
    valuation_date: date


class FacilityPoint(BaseModel):
    snapshot_date: date
    drawn: float
    collateral_market_value: float
    lending_value: float
    ltv_pct: float
    headroom: float


class Facility(BaseModel):
    facility_id: str
    portfolio_id: str
    facility_type: str
    currency: str
    credit_limit: float
    margin_call_ltv_pct: float
    current: FacilityPoint | None = None
    ltv_gap_pp: float | None = None
    history: list[FacilityPoint] = []


class SectorGroup(BaseModel):
    name: str
    value: float
    exposure_pct: float
    positions: int = 0
    contributors: list[str] = []


class SectorExposure(BaseModel):
    """Sector exposure of one portfolio. Informational: no sector limits exist in the mandates."""

    denominator: float = 0.0
    denominator_label: str = ""
    direct: list[SectorGroup] = []
    look_through: list[SectorGroup] = []
    basket_attribution_assumption: bool = False


class PortfolioDetail(HasGaps):
    as_of: date
    snapshot_date: date | None
    client_id: str
    client_name: str
    portfolio: PortfolioRow
    benchmark: str
    inception_date: date
    aum_history: list[AumPoint]
    bands: list[Band]
    position_limit: PositionLimit
    exclusion_breaches: list[ExclusionBreach] = []
    breach_reconciliation: list[BreachReconciliation] = []
    holdings: list[HoldingRow]
    sector_exposure: SectorExposure
    facilities: list[Facility]


def mandate_check(ctx: ReadContext, as_of: date, pf: dict, holdings: pl.DataFrame):
    """(status, calc data, gaps) for one portfolio at the effective snapshot."""
    if pf["service_model"] == "Custody":
        return "no_mandate", None, []
    bands = ctx.repo.mandates(as_of=as_of, mandate_code=pf["mandate_code"]).frame
    if bands.is_empty() or holdings.is_empty():
        return "no_mandate", None, [gap(f"no mandate bands or positions to measure {pf['portfolio_id']}", pf["portfolio_id"])]
    instruments = ctx.repo.instruments(as_of=as_of).frame
    calc = mandate_calc.mandate_drift(holdings, bands, service_model=pf["service_model"], instruments=instruments)
    if calc.status != "ok":
        return "no_mandate", None, [gap(calc.reason or "mandate check not available", pf["portfolio_id"])]
    d = calc.data
    out = bool(d["breaches"] or d["single_position_breaches"])
    return ("out_of_band" if out else "in_band"), d, []


def exclusion_check(ctx: ReadContext, as_of: date, pf: dict, holdings: pl.DataFrame) -> list[dict]:
    """Exclusion breaches of one managed portfolio (computed live, like the band check)."""
    if pf["service_model"] == "Custody" or holdings.is_empty():
        return []
    bands = ctx.repo.mandates(as_of=as_of, mandate_code=pf["mandate_code"]).frame
    notes = bands["mandate_notes"][0] if bands.height else None
    calc = mandate_calc.exclusion_breaches(holdings, ctx.repo.instruments(as_of=as_of).frame,
                                           service_model=pf["service_model"], mandate_notes=notes)
    return calc.data.get("breaches", []) if calc.status == "ok" else []


def breach_key(b: dict) -> str:
    return b["instrument_id"] + (f"@{b['via_instrument_id']}" if b["held"] == "look_through" else "")


def reconciliation_by_portfolio(ctx: ReadContext, as_of: date, client_id: str, *, detail: bool) -> dict[str, list[BreachReconciliation]] | None:
    """Persisted mandate reconciliation of the client grouped by portfolio; ``None`` when none was persisted."""
    rec = ctx.overviews.mandate_reconciliation(as_of, client_id)
    if rec is None:
        return None
    out: dict[str, list[BreachReconciliation]] = {}
    for r in rec.results:
        out.setdefault(r.portfolio_id, []).append(BreachReconciliation(
            portfolio_id=r.portfolio_id, kind=r.kind, key=r.key, status=r.status, note_ids=r.note_ids,
            waiver_claimed=r.waiver_claimed,
            **({"description": r.description, "rationale": r.rationale,
                "notes": [NoteQuote(note_id=n.note_id, note_date=n.note_date, quote=n.quote) for n in r.notes]} if detail else {})))
    return out


def portfolio_rows(ctx: ReadContext, as_of: date, client_id: str) -> tuple[list[PortfolioRow], list]:
    eff, prev, snaps = snapshots_at(ctx, as_of)
    pfs = ctx.repo.portfolios(as_of=as_of, client_id=client_id).frame
    gaps: list = []
    if pfs.is_empty() or eff is None:
        return [], gaps
    h_all = holdings_over_time(ctx, [s for s in (eff, prev) if s], client_id=client_id)
    now, before = at(h_all, eff), at(h_all, prev)
    recon = reconciliation_by_portfolio(ctx, as_of, client_id, detail=False)
    rows = []
    for pf in pfs.sort("portfolio_id").iter_rows(named=True):
        cur = now.filter(pl.col("portfolio_id") == pf["portfolio_id"]) if now.height else now
        prv = before.filter(pl.col("portfolio_id") == pf["portfolio_id"]) if before.height else before
        usd = total_usd(cur)
        before_usd = total_usd(prv) if prv.height else None
        d_usd, d_pct = change(usd, before_usd)
        status, data, g = mandate_check(ctx, as_of, pf, cur)
        gaps += g
        breaches = len(data["breaches"]) + len(data["single_position_breaches"]) if data else 0
        excluded = exclusion_check(ctx, as_of, pf, cur)
        breaches += len(excluded)
        if excluded and status == "in_band":
            status = "out_of_band"
        rows.append(PortfolioRow(
            portfolio_id=pf["portfolio_id"], portfolio_name=pf["portfolio_name"], mandate_code=pf["mandate_code"],
            mandate_name=pf["mandate_name"], service_model=pf["service_model"], base_currency=pf["base_currency"],
            aum_usd=usd, aum_base=float(cur["market_value_base"].sum()) if cur.height else 0.0,
            previous_aum_usd=before_usd, change_usd=d_usd, change_pct=d_pct,
            mandate_status=status, breach_count=breaches,
            breach_reconciliation=(recon or {}).get(pf["portfolio_id"], [])))
    if recon is None and any(r.breach_count for r in rows):
        gaps.append(gap(f"no mandate reconciliation persisted for {client_id}", client_id))
    return rows, gaps


def facilities_for(ctx: ReadContext, as_of: date, *, client_id: str | None = None,
                   portfolio_id: str | None = None) -> list[Facility]:
    terms = ctx.repo.facility_terms(as_of=as_of, client_id=client_id).frame
    snaps = ctx.repo.facility_snapshots(as_of=as_of, client_id=client_id).frame
    out = []
    for t in terms.iter_rows(named=True) if terms.height else []:
        if portfolio_id and t["collateral_portfolio_id"] != portfolio_id:
            continue
        hist = []
        for s in snaps.filter(pl.col("facility_id") == t["facility_id"]).sort("snapshot_date").iter_rows(named=True):
            hist.append(FacilityPoint(
                snapshot_date=s["snapshot_date"], drawn=s["drawn"], collateral_market_value=s["collateral_market_value"],
                lending_value=s["lending_value"], ltv_pct=s["ltv_pct"], headroom=s["headroom"]))
        cur = hist[-1] if hist else None
        out.append(Facility(
            facility_id=t["facility_id"], portfolio_id=t["collateral_portfolio_id"], facility_type=t["facility_type"],
            currency=t["facility_ccy"], credit_limit=t["credit_limit"], margin_call_ltv_pct=t["margin_call_ltv_pct"],
            current=cur, ltv_gap_pp=(t["margin_call_ltv_pct"] - cur.ltv_pct) if cur else None, history=hist))
    return sorted(out, key=lambda f: f.facility_id)


@router.get("/portfolios/{portfolio_id}")
def get_portfolio(ctx: Ctx, as_of: AsOf, portfolio_id: str) -> PortfolioDetail:
    pfs = ctx.repo.portfolios(as_of=as_of, portfolio_id=portfolio_id).frame
    if pfs.is_empty():
        raise HTTPException(404, f"no portfolio {portfolio_id!r} at {as_of}")
    pf = pfs.row(0, named=True)
    client_id = pf["client_id"]
    client = ctx.repo.clients(as_of=as_of, client_id=client_id).frame.row(0, named=True)
    eff, prev, snaps = snapshots_at(ctx, as_of)
    h_all = holdings_over_time(ctx, snaps, portfolio_id=portfolio_id)
    cur = at(h_all, eff)
    rows, _ = portfolio_rows(ctx, as_of, client_id)
    row = next(r for r in rows if r.portfolio_id == portfolio_id)
    gaps = []
    history = []
    if h_all.height:
        agg = h_all.group_by("snapshot_date").agg(
            pl.col("market_value_usd").sum().alias("usd"), pl.col("market_value_base").sum().alias("base")).sort("snapshot_date")
        history = [AumPoint(snapshot_date=r["snapshot_date"], aum_usd=r["usd"], aum_base=r["base"]) for r in agg.iter_rows(named=True)]
    status, data, g = mandate_check(ctx, as_of, pf, cur)
    gaps += g
    recon = reconciliation_by_portfolio(ctx, as_of, client_id, detail=True)
    mine = (recon or {}).get(portfolio_id, [])
    by_ref = {(r.kind, r.key): r for r in mine}
    exclusions = []
    for b in exclusion_check(ctx, as_of, pf, cur):
        r = by_ref.get(("exclusion", breach_key(b)))
        exclusions.append(ExclusionBreach(**{k: b[k] for k in ("instrument_id", "instrument_name", "held", "via_instrument_id",
                                                              "via_instrument_name", "value", "weight_pct")},
                                          key=breach_key(b), status=r.status if r else "no_note", note_ids=r.note_ids if r else []))
    if recon is None and (row.breach_count or exclusions):
        gaps.append(gap(f"no mandate reconciliation persisted for {client_id}", client_id))
    bands, limit = [], PositionLimit()
    if data:
        bands = [Band(**{k: b[k] for k in ("asset_class", "weight_pct", "min_pct", "target_pct", "max_pct", "gap_pp", "breach")},
                      out_of_band=b["breach"] is not None) for b in data["bands"]]
        limit.max_single_position_pct = data["max_single_position_pct"]
        limit.breaches = data["single_position_breaches"]
    elif pf["service_model"] == "Custody":
        limit.note = "custody account: not managed by the bank and not measured against a mandate"
    if cur.height:
        top = cur.sort("weight_pct", descending=True).row(0, named=True)
        limit.largest_instrument_id, limit.largest_instrument_name = top["instrument_id"], top["instrument_name"]
        limit.largest_weight_pct = top["weight_pct"]
    holdings = [HoldingRow(**{k: r[k] for k in HoldingRow.model_fields}) for r in
                cur.sort("market_value_usd", descending=True).iter_rows(named=True)] if cur.height else []
    if not holdings:
        gaps.append(gap(f"no positions for {portfolio_id} at {as_of}", portfolio_id))
    sectors = SectorExposure()
    if cur.height:
        sc = sector_calc.sector_look_through(cur, ctx.repo.instruments(as_of=as_of).frame)
        if sc.status == "ok":
            d = sc.data
            sectors = SectorExposure(
                denominator=d["denominator"], denominator_label=d["denominator_label"],
                direct=[SectorGroup(**g) for g in d["direct"]], look_through=[SectorGroup(**g) for g in d["look_through"]],
                basket_attribution_assumption=any(f.code == "basket_attribution_assumption" for f in sc.flags))
            gaps += [gap(f.message, f.subject or portfolio_id, kind="other") for f in sc.flags
                     if f.code != "basket_attribution_assumption"]
        else:
            gaps.append(gap(sc.reason or "sector exposure not available", portfolio_id))
    return PortfolioDetail(
        as_of=as_of, snapshot_date=eff, client_id=client_id, client_name=client["client_name"], portfolio=row,
        benchmark=pf["benchmark"], inception_date=pf["inception_date"], aum_history=history, bands=bands,
        position_limit=limit, exclusion_breaches=exclusions, breach_reconciliation=mine, holdings=holdings, sector_exposure=sectors, facilities=facilities_for(ctx, as_of, portfolio_id=portfolio_id), gaps=gaps)
