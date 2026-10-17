"""``/api/overview``: the persisted RM overview with what a dashboard needs to plot and link it."""

from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from rm_dashboard.actions.contracts import IMPORTANCE_ORDER
from rm_dashboard.overview.contracts import Overview, OverviewAction

from .clientdata import client_rows
from .context import ReadContext
from .deps import AsOf, Ctx
from .models import gap
from .urgency import urgency

router = APIRouter(prefix="/api", tags=["overview"])

MEETING_WINDOW_DAYS = 14


class ResolvedRef(BaseModel):
    """A source reference with the ids needed to link to it, so a UI never parses ``CL-0001/PF-0001#f8``."""

    kind: Literal["finding", "note", "mandate"]
    ref: str
    client_id: str
    portfolio_id: str | None = None
    claim: str | None = None
    evidence_ids: list[str] = []


class ApiAction(OverviewAction):
    client_aum_usd: float | None = None
    wealth_band: str | None = None
    urgency: float
    refs: list[ResolvedRef] = []


class OverviewClient(BaseModel):
    client_id: str
    client_name: str
    aum_usd: float
    wealth_band: str
    action_count: int
    top_importance: str | None = None
    max_urgency: float = 0.0


class LatestNote(BaseModel):
    note_id: str
    note_date: date
    channel: str
    note: str


class MeetingItem(BaseModel):
    kind: Literal["action", "kyc"]
    title: str
    due_date: date | None = None
    status: Literal["due", "overdue", "immediate"]
    action_id: str | None = None


class MeetingClient(BaseModel):
    client_id: str
    client_name: str
    items: list[MeetingItem]
    latest_note: LatestNote | None = None


class MeetingPrep(BaseModel):
    from_date: date
    to_date: date
    clients: list[MeetingClient]


class ApiOverview(Overview):
    actions: list[ApiAction] = []
    client_rows: list[OverviewClient] = []
    total_aum_usd: float = 0.0
    meeting_prep: MeetingPrep


def resolve_refs(ctx: ReadContext, as_of: date, action: OverviewAction) -> list[ResolvedRef]:
    findings = ctx.overviews.findings(as_of, action.client_id) or {}
    out = []
    for s in action.sources:
        f = findings.get(s.ref)
        path = s.report_path or action.client_id
        parts = path.split("/")
        out.append(ResolvedRef(
            kind=s.kind, ref=s.ref, client_id=parts[0] if parts[0].startswith("CL-") else action.client_id,
            portfolio_id=s.ref.split("/")[0] if s.kind == "mandate" else (parts[1] if len(parts) > 1 else None),
            claim=f.claim if f else None, evidence_ids=list(s.evidence_ids),
        ))
    return out


def meeting_prep(ctx: ReadContext, as_of: date, actions: list[ApiAction], names: dict[str, str]) -> MeetingPrep:
    end = as_of + timedelta(days=MEETING_WINDOW_DAYS)
    items: dict[str, list[MeetingItem]] = {}
    for a in actions:
        if a.horizon == "immediate" or (a.due_date is not None and a.due_date <= end):
            overdue = a.due_date is not None and a.due_date < as_of
            status = "overdue" if overdue else ("immediate" if a.horizon == "immediate" else "due")
            items.setdefault(a.client_id, []).append(
                MeetingItem(kind="action", title=a.title, due_date=a.due_date, status=status, action_id=a.action_id))
    for cid, row in client_rows(ctx, as_of).items():
        due = row["kyc_review_due"]
        if due <= end:
            items.setdefault(cid, []).append(MeetingItem(
                kind="kyc", title="KYC review", due_date=due, status="overdue" if due < as_of else "due"))
            names.setdefault(cid, row["client_name"])
    notes = ctx.repo.notes(as_of=as_of).frame
    latest: dict[str, LatestNote] = {}
    if notes.height:
        for r in notes.sort("note_date").iter_rows(named=True):
            latest[r["client_id"]] = LatestNote(
                note_id=r["note_id"], note_date=r["note_date"], channel=r["channel"], note=r["note"])
    clients = [
        MeetingClient(client_id=cid, client_name=names.get(cid, cid),
                      items=sorted(its, key=lambda i: (i.due_date or end, i.kind)), latest_note=latest.get(cid))
        for cid, its in sorted(items.items())
    ]
    return MeetingPrep(from_date=as_of, to_date=end, clients=clients)


def build_overview(ctx: ReadContext, as_of: date) -> ApiOverview:
    rows = client_rows(ctx, as_of)
    rm_id = next(iter(sorted({r["rm_id"] for r in rows.values()})), "")
    rm_name = next((r["rm_name"] for r in rows.values() if r["rm_id"] == rm_id), "")
    path = ctx.reports.run_dir(as_of) / "overview" / f"{rm_id}.json"
    if path.is_file():
        base = Overview.model_validate_json(path.read_text())
    else:
        base = Overview(
            rm_id=rm_id, rm_name=rm_name, as_of=as_of, status="insufficient_data",
            clients=sorted(rows),
            gaps=[gap(f"no overview persisted for {rm_id} at {as_of}; run `rm-dashboard-overview`", rm_id)],
        )
    actions = []
    seen: dict[str, int] = {}
    size: dict[str, int] = {}
    for a in base.actions:
        size[a.importance] = size.get(a.importance, 0) + 1
    for a in base.actions:
        pos = seen.get(a.importance, 0)
        seen[a.importance] = pos + 1
        c = rows.get(a.client_id, {})
        actions.append(ApiAction(
            **a.model_dump(), client_aum_usd=c.get("aum_usd"), wealth_band=c.get("wealth_band"),
            urgency=urgency(a.importance, a.horizon, a.due_date, as_of, 1.0 - pos / max(size[a.importance] - 1, 1)), refs=resolve_refs(ctx, as_of, a)))
    by_client: dict[str, list[ApiAction]] = {}
    for a in actions:
        if a.origin == "client_actions":  # coverage placeholders ("no actions persisted") are not the client's actions
            by_client.setdefault(a.client_id, []).append(a)
    client_list = []
    for cid, c in sorted(rows.items()):
        acts = by_client.get(cid, [])
        top = min((a.importance for a in acts), key=IMPORTANCE_ORDER.index, default=None)
        client_list.append(OverviewClient(
            client_id=cid, client_name=c["client_name"], aum_usd=float(c["aum_usd"] or 0.0),
            wealth_band=c["wealth_band"], action_count=len(acts), top_importance=top,
            max_urgency=max((a.urgency for a in acts), default=0.0)))
    names = {c["client_id"]: c["client_name"] for c in rows.values()}
    data = base.model_dump(exclude={"actions"})
    return ApiOverview(
        **data, actions=actions, client_rows=client_list,
        total_aum_usd=sum(c.aum_usd for c in client_list), meeting_prep=meeting_prep(ctx, as_of, actions, names))


@router.get("/overview")
def get_overview(ctx: Ctx, as_of: AsOf) -> ApiOverview:
    return build_overview(ctx, as_of)
