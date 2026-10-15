"""``/api/clients``: the book, one client with all of their portfolios, history and snapshot comparison."""

from datetime import date
from typing import Annotated, Any, Literal

import polars as pl
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from rm_dashboard.analytics import concentration, liquidity
from rm_dashboard.analytics.fx import FxTable, fx_table
from rm_dashboard.reportsource import flatten

from .clientdata import client_rows
from .context import ReadContext
from .deps import AsOf, Ctx
from .holdings import at, change, holdings_over_time, snapshots_at, total_usd
from .models import EventOut, HasGaps, Slice, gap
from .overview import ApiAction, build_overview
from .portfolios import AumPoint, Facility, PortfolioRow, facilities_for, portfolio_rows

router = APIRouter(prefix="/api", tags=["clients"])

TOP_N = 10
LIQUIDITY_HORIZON_DAYS = 365


class ClientRow(BaseModel):
    client_id: str
    client_name: str
    wealth_band: str
    booking_centre: str
    risk_profile: str
    aum_usd: float
    portfolio_count: int
    action_count: int
    top_importance: str | None = None
    max_urgency: float = 0.0
    report_status: str
    kyc_review_due: date
    kyc_overdue: bool


class ClientProfile(BaseModel):
    client_id: str
    client_name: str
    age: int | None = None
    nationality: str
    country_of_residence: str
    tax_domicile: str
    booking_centre: str
    base_currency: str
    wealth_band: str
    life_stage: str
    source_of_wealth: str
    risk_profile: str
    risk_tolerance_score: int
    investment_horizon_years: int
    liquidity_needs: str
    objectives: str
    client_since: date
    kyc_review_due: date
    kyc_overdue: bool
    pep_status: bool
    reporting_language: str


class Position(BaseModel):
    instrument_id: str
    instrument_name: str
    asset_class: str
    value_usd: float
    weight_pct: float
    portfolio_ids: list[str]


class Exposure(BaseModel):
    name: str
    value_usd: float
    share_pct: float
    single_name: bool
    via_look_through: bool
    instrument_ids: list[str]
    portfolio_ids: list[str]


class LiquidityItem(BaseModel):
    id: str
    kind: Literal["cash_need", "commitment"]
    description: str
    currency: str
    amount: float
    usd: float
    certainty: str
    due_from: date
    due_to: date


class LiquiditySummary(BaseModel):
    horizon_days: int
    horizon_end: date
    assets_by_tier: list[Slice]
    daily_liquid_usd: float
    needs_total_usd: float
    coverage_ratio: float | None = None
    shortfall_usd: float
    items: list[LiquidityItem]


class Consolidated(BaseModel):
    snapshot_date: date | None
    previous_snapshot_date: date | None
    total_aum_usd: float
    previous_aum_usd: float | None = None
    change_usd: float | None = None
    change_pct: float | None = None
    allocation: list[Slice]
    currency_exposure: list[Slice]
    top_positions: list[Position]
    look_through: list[Exposure]
    hhi: float | None = None
    liquidity: LiquiditySummary | None = None
    facilities: list[Facility]


class FindingOut(BaseModel):
    ref: str
    report_path: str
    client_id: str
    portfolio_id: str | None = None
    claim: str
    confidence: str
    evidence_ids: list[str]


class NoteOut(BaseModel):
    note_id: str
    note_date: date
    channel: str
    note: str
    verdict: Literal["consistent", "contradicted", "unverifiable"] | None = None
    rationale: str = ""
    finding_refs: list[str] = []
    evidence_ids: list[str] = []


class ClientDetail(HasGaps):
    as_of: date
    profile: ClientProfile
    consolidated: Consolidated
    portfolios: list[PortfolioRow]
    actions: list[ApiAction]
    findings: list[FindingOut]
    notes: list[NoteOut]
    report_status: str
    report_summary: str


class SeriesPoint(BaseModel):
    snapshot_date: date
    aum_usd: float


class PortfolioSeries(BaseModel):
    portfolio_id: str
    portfolio_name: str
    points: list[SeriesPoint]


class AumHistory(BaseModel):
    as_of: date
    client_id: str
    total: list[SeriesPoint]
    portfolios: list[PortfolioSeries]
    events: list[EventOut]


class PositionChange(BaseModel):
    portfolio_id: str
    instrument_id: str
    instrument_name: str
    change: Literal["added", "removed", "resized"]
    quantity_from: float | None = None
    quantity_to: float | None = None
    value_usd_from: float | None = None
    value_usd_to: float | None = None
    change_usd: float


class PortfolioChange(BaseModel):
    portfolio_id: str
    portfolio_name: str
    base_currency: str
    aum_usd_from: float
    aum_usd_to: float
    change_usd: float
    change_pct: float | None = None
    pnl_base_from: float | None = None
    pnl_base_to: float | None = None
    pnl_change_base: float | None = None
    positions: list[PositionChange]


class SnapshotChanges(HasGaps):
    as_of: date
    client_id: str
    from_date: date
    to_date: date
    total_from_usd: float
    total_to_usd: float
    change_usd: float
    change_pct: float | None = None
    portfolios: list[PortfolioChange]
    events: list[EventOut]


def _slices(frame: pl.DataFrame, key: str, total: float, label: str | None = None) -> list[Slice]:
    if frame.is_empty() or total <= 0:
        return []
    agg = frame.group_by(key).agg(pl.col("market_value_usd").sum().alias("v")).sort(["v", key], descending=[True, False])
    return [Slice(key=r[key], value_usd=r["v"], weight_pct=r["v"] / total * 100) for r in agg.iter_rows(named=True)]


def _events_between(ctx: ReadContext, as_of: date, start: date | None, end: date, *, inclusive: bool = False) -> list[EventOut]:
    f = ctx.repo.events(as_of=min(as_of, end)).frame
    if f.is_empty():
        return []
    if start is not None:
        f = f.filter(pl.col("event_date") >= start if inclusive else pl.col("event_date") > start)
    f = f.filter(pl.col("event_date") <= end).sort("event_date")
    return [EventOut(**{k: r[k] for k in EventOut.model_fields}) for r in f.iter_rows(named=True)]


def _look_through(ctx: ReadContext, as_of: date, cur: pl.DataFrame, client_id: str):
    pfs = ctx.repo.portfolios(as_of=as_of, client_id=client_id).frame.select("portfolio_id", "service_model")
    positions = cur.join(pfs, on="portfolio_id", how="left")
    calc = concentration.client_concentration(
        positions, ctx.repo.instruments(as_of=as_of).frame, value_col="market_value_usd", include_custody=True, top_n=TOP_N)
    if calc.status != "ok":
        return [], None, [gap(calc.reason or "concentration not available", client_id)]
    out = []
    for e in calc.data["top"]:
        c = e["contributions"]
        out.append(Exposure(
            name=e["name"], value_usd=e["value"], share_pct=e["share_pct"], single_name=e["single_name"],
            via_look_through=any(x["via"] == "look_through" for x in c),
            instrument_ids=sorted({x["instrument_id"] for x in c}), portfolio_ids=sorted({x["portfolio_id"] for x in c})))
    return out, calc.data["hhi"], []


def _liquidity(ctx: ReadContext, as_of: date, cur: pl.DataFrame, client_id: str):
    needs = ctx.repo.cash_needs(as_of=as_of, client_id=client_id).frame
    com = ctx.repo.commitments(as_of=as_of, client_id=client_id).frame
    m = ctx.repo.market_context(as_of=as_of).frame
    fx = fx_table(m.iter_rows(named=True)) if m.height else FxTable([])
    calc = liquidity.liquidity_coverage(cur, needs, com, fx, as_of=as_of, horizon_days=LIQUIDITY_HORIZON_DAYS)
    d = calc.data
    if calc.status != "ok" or "items" not in d:
        return None, [gap(calc.reason or "liquidity not available", client_id)]
    total = total_usd(cur)
    tiers = [Slice(key=k, value_usd=v, weight_pct=(v / total * 100 if total else 0.0))
             for k, v in sorted(d["assets_by_tier_usd"].items(), key=lambda kv: -kv[1])]
    items = [LiquidityItem(id=i["id"], kind=i["kind"], description=i["description"], currency=i["currency"],
                           amount=i["amount"], usd=i["usd"], certainty=i["certainty"],
                           due_from=date.fromisoformat(i["due_from"]), due_to=date.fromisoformat(i["due_to"]))
             for i in d["items"]]
    return LiquiditySummary(
        horizon_days=d["horizon_days"], horizon_end=date.fromisoformat(d["horizon_end"]), assets_by_tier=tiers,
        daily_liquid_usd=d["daily_liquid_usd"], needs_total_usd=d["needs_total_usd"], coverage_ratio=d["coverage_ratio"],
        shortfall_usd=d["shortfall_usd"], items=items), []


def consolidate(ctx: ReadContext, as_of: date, client_id: str) -> tuple[Consolidated, list]:
    eff, prev, _ = snapshots_at(ctx, as_of)
    gaps: list = []
    h = holdings_over_time(ctx, [s for s in (eff, prev) if s], client_id=client_id)
    cur, before = at(h, eff), at(h, prev)
    total = total_usd(cur)
    prev_total = total_usd(before) if before.height else None
    d_usd, d_pct = change(total, prev_total)
    if cur.is_empty():
        gaps.append(gap(f"no positions for {client_id} at {as_of}", client_id))
        return Consolidated(snapshot_date=eff, previous_snapshot_date=prev, total_aum_usd=0.0, allocation=[],
                            currency_exposure=[], top_positions=[], look_through=[], facilities=[]), gaps
    top = (cur.group_by("instrument_id").agg(
        pl.col("instrument_name").first(), pl.col("asset_class").first(), pl.col("market_value_usd").sum().alias("v"),
        pl.col("portfolio_id").unique().sort().alias("pfs")).sort(["v", "instrument_id"], descending=[True, False]).head(TOP_N))
    positions = [Position(instrument_id=r["instrument_id"], instrument_name=r["instrument_name"], asset_class=r["asset_class"],
                          value_usd=r["v"], weight_pct=r["v"] / total * 100, portfolio_ids=r["pfs"]) for r in top.iter_rows(named=True)]
    look, hhi, g1 = _look_through(ctx, as_of, cur, client_id)
    liq, g2 = _liquidity(ctx, as_of, cur, client_id)
    gaps += g1 + g2
    return Consolidated(
        snapshot_date=eff, previous_snapshot_date=prev, total_aum_usd=total, previous_aum_usd=prev_total,
        change_usd=d_usd, change_pct=d_pct, allocation=_slices(cur, "asset_class", total),
        currency_exposure=_slices(cur, "instrument_ccy", total), top_positions=positions, look_through=look, hhi=hhi,
        liquidity=liq, facilities=facilities_for(ctx, as_of, client_id=client_id)), gaps


@router.get("/clients")
def list_clients(ctx: Ctx, as_of: AsOf) -> list[ClientRow]:
    rows = client_rows(ctx, as_of)
    ov = {c.client_id: c for c in build_overview(ctx, as_of).client_rows}
    pf_count = {}
    pfs = ctx.repo.portfolios(as_of=as_of).frame
    if pfs.height:
        pf_count = dict(pfs.group_by("client_id").len().iter_rows())
    out = []
    for cid, c in sorted(rows.items()):
        o = ov.get(cid)
        report = ctx.reports.report(as_of, cid)
        out.append(ClientRow(
            client_id=cid, client_name=c["client_name"], wealth_band=c["wealth_band"], booking_centre=c["booking_centre"],
            risk_profile=c["risk_profile"], aum_usd=float(c["aum_usd"] or 0.0), portfolio_count=pf_count.get(cid, 0),
            action_count=o.action_count if o else 0, top_importance=o.top_importance if o else None,
            max_urgency=o.max_urgency if o else 0.0, report_status=report.status if report else "missing",
            kyc_review_due=c["kyc_review_due"], kyc_overdue=bool(c["kyc_overdue"])))
    return out


def _profile(c: dict) -> ClientProfile:
    d = {k: c[k] for k in ClientProfile.model_fields if k in c}
    return ClientProfile(**d)


def _findings(ctx: ReadContext, as_of: date, client_id: str) -> list[FindingOut]:
    report = ctx.reports.report(as_of, client_id)
    out = []
    if report is None:
        return out
    flat = {f.ref: f for f in flatten(report)}
    for f in flat.values():
        parts = f.report_path.split("/")
        out.append(FindingOut(ref=f.ref, report_path=f.report_path, client_id=parts[0],
                              portfolio_id=parts[1] if len(parts) > 1 else None, claim=f.claim,
                              confidence=f.confidence, evidence_ids=list(f.evidence_ids)))
    return out


def _notes(ctx: ReadContext, as_of: date, client_id: str) -> tuple[list[NoteOut], list]:
    f = ctx.repo.notes(as_of=as_of, client_id=client_id).frame
    recon = ctx.overviews.reconciliation(as_of, client_id)
    by_id = {r.note_id: r for r in recon.results} if recon else {}
    gaps = [] if recon or f.is_empty() else [gap(f"no note reconciliation persisted for {client_id}", client_id)]
    out = []
    for r in f.sort("note_date", descending=True).iter_rows(named=True) if f.height else []:
        x = by_id.get(r["note_id"])
        out.append(NoteOut(
            note_id=r["note_id"], note_date=r["note_date"], channel=r["channel"], note=r["note"],
            verdict=x.verdict if x else None, rationale=x.rationale if x else "",
            finding_refs=list(x.finding_refs) if x else [], evidence_ids=list(x.evidence_ids) if x else []))
    return out, gaps


@router.get("/clients/{client_id}")
def get_client(ctx: Ctx, as_of: AsOf, client_id: str) -> ClientDetail:
    rows = client_rows(ctx, as_of)
    if client_id not in rows:
        raise HTTPException(404, f"no client {client_id!r} at {as_of}")
    c = rows[client_id]
    consolidated, gaps = consolidate(ctx, as_of, client_id)
    portfolios, g_pf = portfolio_rows(ctx, as_of, client_id)
    ov = build_overview(ctx, as_of)
    actions = [a for a in ov.actions if a.client_id == client_id]
    report = ctx.reports.report(as_of, client_id)
    if ctx.overviews.client_actions(as_of, client_id) is None:
        gaps.append(gap(f"actions_missing: no client actions persisted for {client_id}", client_id))
    notes, g_notes = _notes(ctx, as_of, client_id)
    if report is None:
        gaps.append(gap(f"no analysis report persisted for {client_id}", client_id))
    else:
        gaps += [g for g in report.gaps]
    return ClientDetail(
        as_of=as_of, profile=_profile(c), consolidated=consolidated, portfolios=portfolios, actions=actions,
        findings=_findings(ctx, as_of, client_id), notes=notes,
        report_status=report.status if report else "missing", report_summary=report.summary if report else "",
        gaps=gaps + g_pf + g_notes)


@router.get("/clients/{client_id}/aum-history")
def aum_history(ctx: Ctx, as_of: AsOf, client_id: str) -> AumHistory:
    if client_id not in client_rows(ctx, as_of):
        raise HTTPException(404, f"no client {client_id!r} at {as_of}")
    eff, _, snaps = snapshots_at(ctx, as_of)
    h = holdings_over_time(ctx, snaps, client_id=client_id)
    names = dict(ctx.repo.portfolios(as_of=as_of, client_id=client_id).frame.select("portfolio_id", "portfolio_name").iter_rows())
    if h.is_empty():
        return AumHistory(as_of=as_of, client_id=client_id, total=[], portfolios=[], events=[])
    tot = h.group_by("snapshot_date").agg(pl.col("market_value_usd").sum().alias("v")).sort("snapshot_date")
    per = h.group_by("portfolio_id", "snapshot_date").agg(pl.col("market_value_usd").sum().alias("v")).sort("portfolio_id", "snapshot_date")
    series = []
    for pid in sorted(per["portfolio_id"].unique().to_list()):
        pts = per.filter(pl.col("portfolio_id") == pid)
        series.append(PortfolioSeries(portfolio_id=pid, portfolio_name=names.get(pid, pid),
                                      points=[SeriesPoint(snapshot_date=r["snapshot_date"], aum_usd=r["v"]) for r in pts.iter_rows(named=True)]))
    first = snaps[0]
    return AumHistory(
        as_of=as_of, client_id=client_id, total=[SeriesPoint(snapshot_date=r["snapshot_date"], aum_usd=r["v"]) for r in tot.iter_rows(named=True)],
        portfolios=series, events=_events_between(ctx, as_of, first, eff, inclusive=True))


@router.get("/clients/{client_id}/snapshot-changes")
def snapshot_changes(
    ctx: Ctx, as_of: AsOf, client_id: str,
    from_: Annotated[date | None, Query(alias="from")] = None, to: date | None = None,
) -> SnapshotChanges:
    if client_id not in client_rows(ctx, as_of):
        raise HTTPException(404, f"no client {client_id!r} at {as_of}")
    eff, prev, snaps = snapshots_at(ctx, as_of)
    to_d = to or eff
    from_d = from_ or (prev if to is None else None)
    if to_d not in snaps:
        raise HTTPException(422, f"'to' must be a snapshot date up to {eff}: {', '.join(map(str, snaps))}")
    if from_d is None:
        earlier = [s for s in snaps if s < to_d]
        from_d = earlier[-1] if earlier else None
    if from_d is None or from_d not in snaps:
        raise HTTPException(422, f"'from' must be a snapshot date: {', '.join(map(str, snaps))}")
    if from_d >= to_d:
        raise HTTPException(422, "'from' must be before 'to'")
    h = holdings_over_time(ctx, [from_d, to_d], client_id=client_id)
    a, b = at(h, from_d), at(h, to_d)
    pfs = ctx.repo.portfolios(as_of=as_of, client_id=client_id).frame
    portfolios = []
    for pf in pfs.sort("portfolio_id").iter_rows(named=True):
        pid = pf["portfolio_id"]
        pa = a.filter(pl.col("portfolio_id") == pid) if a.height else a
        pb = b.filter(pl.col("portfolio_id") == pid) if b.height else b
        ka = {r["instrument_id"]: r for r in pa.iter_rows(named=True)}
        kb = {r["instrument_id"]: r for r in pb.iter_rows(named=True)}
        pos = []
        for iid in sorted(set(ka) | set(kb)):
            x, y = ka.get(iid), kb.get(iid)
            va, vb = (x["market_value_usd"] if x else None), (y["market_value_usd"] if y else None)
            if x is None:
                kind = "added"
            elif y is None:
                kind = "removed"
            elif x["quantity"] != y["quantity"]:
                kind = "resized"
            else:
                continue
            pos.append(PositionChange(
                portfolio_id=pid, instrument_id=iid, instrument_name=(y or x)["instrument_name"], change=kind,
                quantity_from=x["quantity"] if x else None, quantity_to=y["quantity"] if y else None,
                value_usd_from=va, value_usd_to=vb, change_usd=(vb or 0.0) - (va or 0.0)))
        ta, tb = total_usd(pa), total_usd(pb)
        pnl_a = float(pa["unrealised_pnl_base"].drop_nulls().sum()) if pa.height else None
        pnl_b = float(pb["unrealised_pnl_base"].drop_nulls().sum()) if pb.height else None
        portfolios.append(PortfolioChange(
            portfolio_id=pid, portfolio_name=pf["portfolio_name"], base_currency=pf["base_currency"], aum_usd_from=ta,
            aum_usd_to=tb, change_usd=tb - ta, change_pct=((tb - ta) / ta * 100 if ta else None),
            pnl_base_from=pnl_a, pnl_base_to=pnl_b, pnl_change_base=(pnl_b - pnl_a) if pnl_a is not None and pnl_b is not None else None,
            positions=pos))
    ta, tb = total_usd(a), total_usd(b)
    gaps = [] if a.height and b.height else [gap(f"no positions at {from_d} or {to_d}", client_id)]
    return SnapshotChanges(
        as_of=as_of, client_id=client_id, from_date=from_d, to_date=to_d, total_from_usd=ta, total_to_usd=tb,
        change_usd=tb - ta, change_pct=((tb - ta) / ta * 100 if ta else None), portfolios=portfolios,
        events=_events_between(ctx, as_of, from_d, to_d), gaps=gaps)
