"""The client-actions agent: one model call per client, then code validates, merges, floors, dates and orders."""

import json
from datetime import date

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from rm_dashboard.agents import prompts
from rm_dashboard.agents.outputs import parse_object_list
from rm_dashboard.agents.scope import register_people
from rm_dashboard.agents.stubplans import INPUT_MARKER
from rm_dashboard.domain import Gap
from rm_dashboard.llmlog import llm_config
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyDenied, PolicyEngine, PolicyEscalated, RunContext
from rm_dashboard.policy.engine import COMPLIANCE_CONTENT, EVIDENCE_PROVENANCE
from rm_dashboard.mandate_reconciliation import BreachResult, MandateReconciliation
from rm_dashboard.reconciliation import NoteResult, Reconciliation
from rm_dashboard.reportsource import StoreReportSource, flatten
from rm_dashboard.store import Kind, read_model
from rm_dashboard.tools import ToolRegistry

from .assemble import finalise, not_actioned
from .contracts import ClientActions
from .guard import guard_actions
from .rubric import RUBRIC_TEXT

ROLE = "client_actions"
SYSTEM_PROMPT = prompts.CLIENT_ACTIONS + "\n" + RUBRIC_TEXT


def load_reconciliation(source: StoreReportSource, as_of: date, client_id: str) -> Reconciliation | None:
    return read_model(source.store, as_of, Kind.RECONCILIATION, client_id, Reconciliation)


def load_mandate_reconciliation(source: StoreReportSource, as_of: date, client_id: str) -> MandateReconciliation | None:
    return read_model(source.store, as_of, Kind.MANDATE_RECONCILIATION, client_id, MandateReconciliation)


def build_input(client_id: str, as_of: date, findings, notes: list[NoteResult], quality_flags: list[str],
                mandate: list[BreachResult] | None = None) -> str:
    payload = {
        "client_id": client_id, "as_of": as_of.isoformat(),
        "findings": [{"ref": f.ref, "claim": f.claim, "confidence": f.confidence} for f in findings],
        "notes": [{"note_id": n.note_id, "note_date": n.note_date.isoformat(), "verdict": n.verdict,
                   "rationale": n.rationale, "quote": n.note_quote} for n in notes],
        "mandate": [{"ref": m.ref, "portfolio_id": m.portfolio_id, "kind": m.kind, "status": m.status, "breach": m.description,
                     "note_ids": m.note_ids, "waiver_claimed": m.waiver_claimed, "rationale": m.rationale,
                     "notes": [{"note_id": n.note_id, "quote": n.quote} for n in m.notes]} for m in (mandate or [])],
        "quality_flags": quality_flags,
    }
    return (f"Decide the next actions for client {client_id} as of {as_of.isoformat()}.\n"
            f"{INPUT_MARKER}{json.dumps(payload, sort_keys=True)}")


def derive_actions(registry: ToolRegistry, client_id: str, *, as_of: date, source: StoreReportSource, model: BaseChatModel,
                   engine: PolicyEngine | None = None, audit: AuditLog | None = None) -> ClientActions:
    """Actions for one client. Always returns a ``ClientActions``; failures become gaps."""
    run = RunContext(client_id, as_of, engine=engine or MockPolicyEngine(), audit=audit or AuditLog())
    base = dict(client_id=client_id, as_of=as_of)
    gaps: list[Gap] = []
    notes: dict[str, NoteResult] = {}
    mandate: dict[str, BreachResult] = {}
    started = False
    try:
        register_people(run, registry.ctx.repo, as_of)
        run.run_start(ROLE)
        started = True
        report, evidence = source.report(as_of, client_id), source.evidence(as_of, client_id)
        if report is None or evidence is None:
            what = "report" if report is None else "evidence"
            gap = Gap(kind="no_data", subject=client_id, description=f"no persisted {what} for {client_id} at {as_of} in {source.location(as_of)}")
            return _finish(run, ClientActions(status="insufficient_data", gaps=[gap], **base))
        rec = load_reconciliation(source, as_of, client_id)
        if rec is None:
            gaps.append(Gap(kind="other", subject=client_id, description="notes were not reconciled: no reconciliation exists for this client and date"))
        else:
            notes = {n.note_id: n for n in rec.results}
        mrec = load_mandate_reconciliation(source, as_of, client_id)
        if mrec is None:
            gaps.append(Gap(kind="other", subject=client_id, description="mandate breaches were not reconciled with notes: "
                            "no mandate reconciliation exists for this client and date; every mandate action is treated as no_note"))
        else:
            mandate = {m.ref: m for m in mrec.results}
        flat = flatten(report)
        findings = {f.ref: f for f in flat}
        if not flat and not notes:
            gaps.append(Gap(kind="no_data", subject=client_id, description="the report has no findings to derive actions from"))
            return _finish(run, ClientActions(status="partial", gaps=gaps, **base))
        raw, err = _ask(run, model, build_input(client_id, as_of, flat, list(notes.values()), [f.message for f in report.flags], list(mandate.values())))
        if err:
            gaps.append(Gap(kind="agent_error", description=err, subject=ROLE))
        out = guard_actions(raw, findings, notes, mandate)
        gaps += out.gaps
        actions = finalise(out.actions, findings, notes, evidence, as_of)
        pending = not_actioned(actions, notes, mandate)
        gaps = _checkpoints(run, gaps, len(actions))
        restore = run.pseudonymiser.restore
        actions = [a.model_copy(update={"title": restore(a.title), "what": restore(a.what), "why": restore(a.why)}) for a in actions]
        gaps = [g.model_copy(update={"description": restore(g.description)}) for g in gaps]
        return _finish(run, ClientActions(status="partial" if gaps else "complete", actions=actions, not_actioned=pending, gaps=gaps, **base))
    except (PolicyDenied, PolicyEscalated) as e:
        gaps.append(Gap(kind="policy_denied", description=e.reason, subject=ROLE))
        return _finish(run, ClientActions(status="partial" if started else "insufficient_data", gaps=gaps, **base))
    except Exception as e:  # noqa: BLE001 - always delivered: nothing escapes as an unhandled error
        gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
        return _finish(run, ClientActions(status="partial", gaps=gaps, **base))


def _ask(run: RunContext, model: BaseChatModel, text: str) -> tuple[list, str | None]:
    safe = run.model_call(ROLE, [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}])
    try:
        reply = model.invoke([SystemMessage(content=safe[0]["content"]), HumanMessage(content=safe[1]["content"])],
                           config=llm_config(run, ROLE))
    except Exception as e:  # noqa: BLE001
        return [], f"{type(e).__name__}: {e}"
    content = reply.content if isinstance(reply, AIMessage) and isinstance(reply.content, str) else ""
    return parse_object_list(content, "actions")


def _checkpoints(run: RunContext, gaps: list[Gap], n: int) -> list[Gap]:
    gaps = list(gaps)
    for name in (EVIDENCE_PROVENANCE, COMPLIANCE_CONTENT):
        try:
            run.guard(name, ROLE, "report_assembly", actions=n)
        except (PolicyDenied, PolicyEscalated) as e:
            gaps.append(Gap(kind="policy_denied", description=e.reason, subject=name))
    return gaps


def _finish(run: RunContext, result: ClientActions) -> ClientActions:
    return result.model_copy(update={"policy_decisions": run.report_decisions()})
