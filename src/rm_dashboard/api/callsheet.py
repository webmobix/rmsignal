"""``GET /api/portfolios/{id}/call-sheet``: everything the RM needs for a client call about one portfolio.

Read-only assembly of the seeded data and persisted output. No model is called and no batch stage is started.
Each section is built independently; a builder that fails becomes a gap of its own section.
"""

from collections.abc import Callable
from datetime import date
from typing import Literal, TypeVar

import polars as pl
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rm_dashboard.outlook.contracts import InstrumentView, MarketContext
from rm_dashboard.outlook.relevance import relevant_events
from rm_dashboard.reportsource import flatten
from rm_dashboard.tools.domain_tools import with_event_ids

from .clients import LiquiditySummary, _events_between, _liquidity
from .context import ReadContext
from .deps import AsOf, Ctx
from .holdings import at, holdings_over_time, snapshots_at, total_usd
from .models import EventOut, HasGaps, gap
from .overview import build_overview
from .portfolios import (
    Band, BreachReconciliation, ExclusionBreach, Facility, PortfolioDetail, PositionLimit, SectorExposure, assemble_detail,
)

router = APIRouter(prefix="/api", tags=["call-sheet"])

NOTE_LIMIT = 10
SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}
CLIENT_LEVEL = "Client level: spans all of the client's portfolios, not only this one."


# ---- response ----------------------------------------------------------------------------------------
class Contributor(BaseModel):
    instrument_id: str
    instrument_name: str
    value_usd_from: float | None = None
    value_usd_to: float | None = None
    change_usd: float


class SheetFinding(BaseModel):
    ref: str
    claim: str
    confidence: str
    evidence_ids: list[str]


class SheetEvent(EventOut):
    event_id: str


class PerformanceSection(HasGaps):
    snapshot_date: date | None = None
    previous_snapshot_date: date | None = None
    aum_usd: float = 0.0
    previous_aum_usd: float | None = None
    change_usd: float | None = None
    change_pct: float | None = None
    contributors: list[Contributor] = []
    findings: list[SheetFinding] = []
    events: list[SheetEvent] = []


class OpenAction(BaseModel):
    action_id: str
    title: str
    category: str
    importance: str
    horizon: str
    due_date: date | None = None


class MandateSection(HasGaps):
    applicable: bool = True
    statement: str = ""
    bands: list[Band] = []
    position_limit: PositionLimit = PositionLimit()
    exclusion_breaches: list[ExclusionBreach] = []
    breach_reconciliation: list[BreachReconciliation] = []
    open_actions: list[OpenAction] = []


class OwnershipSection(HasGaps):
    sector_exposure: SectorExposure = SectorExposure()
    unclassified_pct: dict[str, float] = {}


class OutlookEntry(BaseModel):
    """The bank's view of one instrument as of ``as_of`` (its own date), copied from the persisted outlook."""

    as_of: date
    older_than_as_of: bool
    view: InstrumentView
    market_outlook_as_of: date | None = None
    market_context: list[MarketContext] = []


class BankViewEntry(BaseModel):
    instrument_id: str
    instrument_name: str
    asset_class: str
    weight_pct: float
    value_usd: float
    outlook: OutlookEntry | None = None


class BankViewSection(HasGaps):
    entries: list[BankViewEntry] = []


class EventInstrument(BaseModel):
    instrument_id: str
    instrument_name: str
    matched_on: list[dict]


class MatchedEvent(SheetEvent):
    instruments: list[EventInstrument]


class EventsSection(HasGaps):
    events: list[MatchedEvent] = []


class CashCreditSection(HasGaps):
    facilities: list[Facility] = []
    client_liquidity: LiquiditySummary | None = None
    client_level_note: str = CLIENT_LEVEL


class SheetNote(BaseModel):
    note_id: str
    note_date: date
    channel: str
    note: str


class SheetCommitment(BaseModel):
    commitment_id: str
    portfolio_id: str | None = None
    fund_name: str
    currency: str
    committed: float
    called_to_date: float
    uncalled: float
    expected_call_window: str | None = None


class ConversationSection(HasGaps):
    notes: list[SheetNote] = []
    note_limit: int = NOTE_LIMIT
    note_total: int = 0
    commitments: list[SheetCommitment] = []
    scope: Literal["client"] = "client"
    client_level_note: str = CLIENT_LEVEL


class CallSheet(HasGaps):
    as_of: date
    snapshot_date: date | None
    portfolio_id: str
    portfolio_name: str
    client_id: str
    client_name: str
    mandate_name: str
    service_model: str
    performance: PerformanceSection
    mandate: MandateSection
    ownership: OwnershipSection
    bank_view: BankViewSection
    events: EventsSection
    cash_credit: CashCreditSection
    conversation: ConversationSection


# ---- builders ---------------------------------------------------------------------------------------------
S = TypeVar("S", bound=HasGaps)


def safe(name: str, empty: type[S], builder: Callable[[], S]) -> S:
    """A builder's failure never escapes: the section is empty and says what went wrong."""
    try:
        return builder()
    except Exception as e:  # noqa: BLE001
        return empty(gaps=[gap(f"{name} section could not be built: {type(e).__name__}: {e}", name, kind="other")])


def performance(ctx: ReadContext, as_of: date, d: PortfolioDetail, by: dict) -> PerformanceSection:
    eff, prev, _ = snapshots_at(ctx, as_of)
    h = holdings_over_time(ctx, [s for s in (eff, prev) if s], portfolio_id=d.portfolio.portfolio_id)
    now, before = at(h, eff), at(h, prev)
    a = {r["instrument_id"]: r for r in before.iter_rows(named=True)} if before.height else {}
    b = {r["instrument_id"]: r for r in now.iter_rows(named=True)} if now.height else {}
    rows = []
    for iid in set(a) | set(b):
        va = a[iid]["market_value_usd"] if iid in a else None
        vb = b[iid]["market_value_usd"] if iid in b else None
        delta = (vb or 0.0) - (va or 0.0)
        if delta:
            rows.append(Contributor(instrument_id=iid, instrument_name=(b.get(iid) or a[iid])["instrument_name"],
                                    value_usd_from=va, value_usd_to=vb, change_usd=delta))
    rows.sort(key=lambda c: (-abs(c.change_usd), c.instrument_id))
    gaps = list(by["holdings"])
    if prev is None:
        gaps.append(gap(f"no earlier snapshot than {eff} to compare {d.portfolio.portfolio_id} with", d.portfolio.portfolio_id))
    findings: list[SheetFinding] = []
    report = ctx.reports.report(as_of, d.client_id)
    if report is None:
        gaps.append(gap(f"no analysis report persisted for {d.client_id} at {as_of}", d.client_id))
    else:
        pid = d.portfolio.portfolio_id
        findings = [SheetFinding(ref=f.ref, claim=f.claim, confidence=f.confidence, evidence_ids=list(f.evidence_ids))
                    for f in flatten(report) if f.report_path.split("/")[-1] == pid]
    events = [SheetEvent(**e.model_dump(), event_id=eid) for e, eid in _events_with_ids(ctx, as_of, prev, eff)] if prev and eff else []
    return PerformanceSection(
        snapshot_date=eff, previous_snapshot_date=prev, aum_usd=d.portfolio.aum_usd, previous_aum_usd=d.portfolio.previous_aum_usd,
        change_usd=d.portfolio.change_usd, change_pct=d.portfolio.change_pct, contributors=rows[:5], findings=findings,
        events=events, gaps=gaps)


def _event_ids(ctx: ReadContext, as_of: date) -> list[dict]:
    f = ctx.repo.events(as_of=as_of).frame
    return with_event_ids(f.to_dicts()) if f.height else []


def _events_with_ids(ctx: ReadContext, as_of: date, start: date, end: date):
    keyed = {(e["event_date"], e["description"]): e["event_id"] for e in _event_ids(ctx, as_of)}
    return [(e, keyed.get((e.event_date, e.description), "")) for e in _events_between(ctx, as_of, start, end)]


def mandate(ctx: ReadContext, as_of: date, d: PortfolioDetail, by: dict) -> MandateSection:
    pid = d.portfolio.portfolio_id
    if d.portfolio.service_model == "Custody":
        return MandateSection(applicable=False, statement=d.position_limit.note or "Custody account: no mandate applies.")
    actions = [a for a in build_overview(ctx, as_of).actions
               if a.client_id == d.client_id and any(r.portfolio_id == pid for r in a.refs)]
    return MandateSection(
        statement=f"{d.portfolio.mandate_name} mandate", bands=d.bands, position_limit=d.position_limit,
        exclusion_breaches=d.exclusion_breaches, breach_reconciliation=d.breach_reconciliation, gaps=list(by["mandate"]),
        open_actions=[OpenAction(action_id=a.action_id, title=a.title, category=a.category, importance=a.importance,
                                 horizon=a.horizon, due_date=a.due_date) for a in actions])


def ownership(d: PortfolioDetail, by: dict) -> OwnershipSection:
    s = d.sector_exposure
    unclassified = {v: sum(g.exposure_pct for g in getattr(s, v) if g.name in ("unclassified", "Unclassified (look-through)"))
                    for v in ("direct", "look_through")}
    gaps = list(by["ownership"])
    if not s.direct:
        gaps.append(gap(f"sector exposure not available for {d.portfolio.portfolio_id}", d.portfolio.portfolio_id))
    return OwnershipSection(sector_exposure=s, unclassified_pct=unclassified, gaps=gaps)


def bank_view(ctx: ReadContext, as_of: date, d: PortfolioDetail) -> BankViewSection:
    entries, gaps = [], []
    for h in d.holdings:
        o = ctx.outlooks.latest_instrument(h.instrument_id, as_of)
        entry = BankViewEntry(instrument_id=h.instrument_id, instrument_name=h.instrument_name, asset_class=h.asset_class,
                              weight_pct=h.weight_pct, value_usd=h.market_value_usd)
        if o is None or o.view is None:
            gaps.append(gap(f"outlook_missing: no outlook persisted for {h.instrument_id} at or before {as_of}", h.instrument_id))
        else:
            entry.outlook = OutlookEntry(as_of=o.as_of, older_than_as_of=o.as_of < as_of, view=o.view,
                                         market_outlook_as_of=o.market_outlook_as_of, market_context=o.market_context)
        entries.append(entry)
    return BankViewSection(entries=entries, gaps=gaps)


def events(ctx: ReadContext, as_of: date, d: PortfolioDetail) -> EventsSection:
    evs = _event_ids(ctx, as_of)
    inst = ctx.repo.instruments(as_of=as_of).frame
    held = {h.instrument_id for h in d.holdings}
    by_id: dict[str, MatchedEvent] = {}
    for i in inst.filter(pl.col("instrument_id").is_in(sorted(held))).iter_rows(named=True) if held and inst.height else []:
        for e in relevant_events(i, evs):
            m = by_id.get(e["event_id"])
            if m is None:
                m = by_id[e["event_id"]] = MatchedEvent(
                    event_id=e["event_id"], instruments=[], **{k: e[k] for k in EventOut.model_fields})
            m.instruments.append(EventInstrument(instrument_id=i["instrument_id"], instrument_name=i["instrument_name"],
                                                 matched_on=e["matched_on"]))
    out = sorted(by_id.values(), key=lambda m: (SEVERITY_ORDER.get(m.severity, 3), -m.event_date.toordinal(), m.event_id))
    return EventsSection(events=out, gaps=[] if out else [gap(f"no event up to {as_of} matches the holdings", d.portfolio.portfolio_id)])


def cash_credit(ctx: ReadContext, as_of: date, d: PortfolioDetail) -> CashCreditSection:
    eff = snapshots_at(ctx, as_of)[0]
    cur = at(holdings_over_time(ctx, [eff] if eff else [], client_id=d.client_id), eff)
    liq, gaps = _liquidity(ctx, as_of, cur, d.client_id) if cur.height else (None, [gap(f"no positions for {d.client_id}", d.client_id)])
    return CashCreditSection(facilities=d.facilities, client_liquidity=liq, gaps=list(gaps))


def conversation(ctx: ReadContext, as_of: date, d: PortfolioDetail) -> ConversationSection:
    f = ctx.repo.notes(as_of=as_of, client_id=d.client_id).frame
    notes = [SheetNote(note_id=r["note_id"], note_date=r["note_date"], channel=r["channel"], note=r["note"])
             for r in f.sort(["note_date", "note_id"], descending=True).iter_rows(named=True)] if f.height else []
    c = ctx.repo.commitments(as_of=as_of, client_id=d.client_id).frame
    commitments = [SheetCommitment(**{k: r[k] for k in SheetCommitment.model_fields}) for r in c.iter_rows(named=True)
                   if (r["uncalled"] or 0) > 0] if c.height else []
    return ConversationSection(notes=notes[:NOTE_LIMIT], note_total=len(notes), commitments=commitments)


@router.get("/portfolios/{portfolio_id}/call-sheet")
def get_call_sheet(ctx: Ctx, as_of: AsOf, portfolio_id: str) -> CallSheet:
    detail, by = assemble_detail(ctx, as_of, portfolio_id)  # 404 for an unknown portfolio
    return CallSheet(
        as_of=as_of, snapshot_date=detail.snapshot_date, portfolio_id=portfolio_id,
        portfolio_name=detail.portfolio.portfolio_name, client_id=detail.client_id, client_name=detail.client_name,
        mandate_name=detail.portfolio.mandate_name, service_model=detail.portfolio.service_model,
        performance=safe("performance", PerformanceSection, lambda: performance(ctx, as_of, detail, by)),
        mandate=safe("mandate", MandateSection, lambda: mandate(ctx, as_of, detail, by)),
        ownership=safe("ownership", OwnershipSection, lambda: ownership(detail, by)),
        bank_view=safe("bank_view", BankViewSection, lambda: bank_view(ctx, as_of, detail)),
        events=safe("events", EventsSection, lambda: events(ctx, as_of, detail)),
        cash_credit=safe("cash_credit", CashCreditSection, lambda: cash_credit(ctx, as_of, detail)),
        conversation=safe("conversation", ConversationSection, lambda: conversation(ctx, as_of, detail)))
