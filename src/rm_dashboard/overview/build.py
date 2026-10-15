"""Aggregation of client actions into an RM overview. Deterministic code: no model decides order, content or links."""

from datetime import date

from rm_dashboard.actions.contracts import HORIZON_ORDER, IMPORTANCE_ORDER, CATEGORIES, ClientActions
from rm_dashboard.domain import Gap

from .contracts import CategoryGroup, ClientWithoutActions, Overview, OverviewAction
from .source import ClientInfo, OverviewSource, RmInfo

FAILURE_GAPS = ("agent_error", "policy_denied", "no_data")


def sort_key(a: OverviewAction, aum: dict[str, float]):
    return (IMPORTANCE_ORDER.index(a.importance), HORIZON_ORDER.index(a.horizon), a.due_date or date.max,
            -aum.get(a.client_id, 0.0), a.client_id, a.title)


def rank_actions(actions: list[OverviewAction], aum: dict[str, float]) -> list[OverviewAction]:
    ordered = sorted(actions, key=lambda a: sort_key(a, aum))
    return [a.model_copy(update={"rank": i}) for i, a in enumerate(ordered, start=1)]


def group_by_category(actions: list[OverviewAction]) -> list[CategoryGroup]:
    out = []
    for c in CATEGORIES:
        ids = [a.action_id for a in actions if a.category == c]
        if ids:
            out.append(CategoryGroup(category=c, count=len(ids), action_ids=ids))
    return out


def coverage_action(client: ClientInfo, reason: str) -> OverviewAction:
    """A `data_quality` action produced without a model for a client the earlier stages did not deliver."""
    if reason == "report_missing":
        title, what = f"Analysis report missing for {client.client_name}", "Run the client analysis for this date and review the result."
        why = "No analysis report exists for this client at this date, so nothing about the client could be assessed."
    else:
        title, what = f"Actions missing for {client.client_name}", "Re-run the action derivation for this client and review the result."
        why = "The analysis report exists but its next actions were not delivered for this date."
    return OverviewAction(rank=0, action_id=f"{client.client_id}-COVER", origin="coverage", client_id=client.client_id,
                          client_name=client.client_name, title=title, what=what, why=why, category="data_quality",
                          importance="high", horizon="none", sources=[])


def _links_broken(a: ClientActions, source: OverviewSource, as_of: date) -> list[str]:
    findings = source.findings(as_of, a.client_id)
    rec = source.reconciliation(as_of, a.client_id)
    notes = {n.note_id for n in rec.results} if rec else set()
    broken = []
    for act in a.actions:
        for s in act.sources:
            if s.kind == "finding":
                f = (findings or {}).get(s.ref)
                if f is None:
                    broken.append(f"{s.ref}: finding not found in the report" if findings is not None else f"{s.ref}: report file missing")
                elif s.report_path is not None and f.report_path != s.report_path:
                    broken.append(f"{s.ref}: report path {s.report_path} does not match")
                elif not set(s.evidence_ids) <= set(f.evidence_ids):
                    broken.append(f"{s.ref}: evidence ids differ from the finding's")
            elif s.ref not in notes:
                broken.append(f"{s.ref}: note not found in the reconciliation")
    return broken


def build_overview(rm: RmInfo, as_of: date, source: OverviewSource) -> Overview:
    """Everything except the optional model summary."""
    base = dict(rm_id=rm.rm_id, rm_name=rm.rm_name, as_of=as_of, clients=[c.client_id for c in rm.clients])
    if not source.has_actions_folder(as_of) or all(source.client_actions(as_of, c.client_id) is None for c in rm.clients):
        gap = Gap(kind="no_data", subject=rm.rm_id, description=f"no client actions exist for {as_of} in {source.location(as_of)}")
        without = [ClientWithoutActions(client_id=c.client_id, client_name=c.client_name,
                                        reason="actions_missing" if source.findings(as_of, c.client_id) is not None else "report_missing")
                   for c in rm.clients]
        return Overview(status="insufficient_data", clients_without_actions=without, gaps=[gap], **base)

    actions: list[OverviewAction] = []
    without: list[ClientWithoutActions] = []
    gaps: list[Gap] = []
    for c in rm.clients:
        ca = source.client_actions(as_of, c.client_id)
        report_present = source.findings(as_of, c.client_id) is not None
        reason = None
        if ca is None:
            reason = "actions_missing" if report_present else "report_missing"
        else:
            gaps += [Gap(kind=g.kind, subject=c.client_id, description=f"{c.client_id}: {g.description}") for g in ca.gaps]
            for text in _links_broken(ca, source, as_of):
                gaps.append(Gap(kind="other", subject=c.client_id, description=f"link_broken: {c.client_id}: {text}"))
            if ca.status == "insufficient_data" or (not ca.actions and any(g.kind in FAILURE_GAPS for g in ca.gaps)):
                reason = "actions_missing" if report_present else "report_missing"
            elif not ca.actions:
                without.append(ClientWithoutActions(client_id=c.client_id, client_name=c.client_name, reason="no_action_needed"))
            for i, a in enumerate(ca.actions, start=1):
                actions.append(OverviewAction(
                    rank=0, action_id=f"{c.client_id}-A{i}", client_id=c.client_id, client_name=c.client_name, title=a.title,
                    what=a.what, why=a.why, category=a.category, importance=a.importance, horizon=a.horizon,
                    due_date=a.due_date, sources=list(a.sources)))
        if reason:
            without.append(ClientWithoutActions(client_id=c.client_id, client_name=c.client_name, reason=reason))
            actions.append(coverage_action(c, reason))
    ranked = rank_actions(actions, {c.client_id: c.aum_usd for c in rm.clients})
    return Overview(status="partial" if gaps else "complete", actions=ranked, by_category=group_by_category(ranked),
                    clients_without_actions=without, gaps=gaps, **base)
