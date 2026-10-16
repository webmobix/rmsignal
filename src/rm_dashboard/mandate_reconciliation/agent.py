"""The mandate reconciler: one model call per client, only over breaches the system computed, checked in code."""

import json
from datetime import date

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from rm_dashboard.agents import prompts
from rm_dashboard.agents.outputs import parse_json_object
from rm_dashboard.agents.stubplans import INPUT_MARKER
from rm_dashboard.domain import Gap
from rm_dashboard.llmlog import llm_config
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyDenied, PolicyEscalated, PolicyEngine, RunContext
from rm_dashboard.policy.engine import COMPLIANCE_CONTENT, EVIDENCE_PROVENANCE
from rm_dashboard.reconciliation.guard import Note
from rm_dashboard.reportsource import FolderReportSource
from rm_dashboard.tools import ALLOWLISTS, ToolRegistry

from .contracts import BreachResult, MandateReconciliation
from .guard import _neutral, guard_results
from .subjects import Breach, build_subjects

ROLE = "mandate_reconciler"
NOTE_TOOLS = ALLOWLISTS["note_reconciler"]


def load_notes(registry: ToolRegistry, run: RunContext, client_id: str, as_of: date) -> list[Note]:
    """Notes of the client up to ``as_of`` through the notes tool (point-in-time, policy and audit apply)."""
    toolbox = registry.toolbox(ROLE, NOTE_TOOLS, observer=run.tool_observer(), run=run)
    result = toolbox.call("notes.list", {"client_id": client_id, "as_of": as_of.isoformat()})
    return [Note(r["note_id"], date.fromisoformat(str(r["note_date"])), r["quote"]) for r in (result.data or [])]


def build_input(client_id: str, as_of: date, breaches: list[Breach], notes: list[Note]) -> str:
    payload = {
        "client_id": client_id, "as_of": as_of.isoformat(),
        "breaches": [{"portfolio_id": b.portfolio_id, "portfolio_name": b.portfolio_name, "kind": b.kind, "key": b.key,
                      "evidence_id": b.evidence_id, "description": b.description, "names": list(b.names)} for b in breaches],
        "notes": [{"note_id": n.note_id, "note_date": n.note_date.isoformat(), "quote": n.quote} for n in notes],
    }
    return (f"Reconcile the notes of client {client_id} as of {as_of.isoformat()} with the computed mandate breaches.\n"
            f"{INPUT_MARKER}{json.dumps(payload, sort_keys=True)}")


def mandate_reconcile(registry: ToolRegistry, client_id: str, *, as_of: date, source: FolderReportSource, model: BaseChatModel,
                      engine: PolicyEngine | None = None, audit: AuditLog | None = None) -> MandateReconciliation:
    """Reconcile one client's breaches with its notes. Always returns a result; failures become gaps."""
    from rm_dashboard.agents.scope import register_people

    run = RunContext(client_id, as_of, engine=engine or MockPolicyEngine(), audit=audit or AuditLog())
    base = dict(client_id=client_id, as_of=as_of)
    gaps: list[Gap] = []
    breaches: list[Breach] = []
    try:
        register_people(run, registry.ctx.repo, as_of)
        run.run_start(ROLE)
        report, evidence = source.report(as_of, client_id), source.evidence(as_of, client_id)
        if report is None or evidence is None:
            what = "report" if report is None else "evidence"
            gap = Gap(kind="no_data", subject=client_id,
                      description=f"no persisted {what} for {client_id} at {as_of} in {source.run_dir(as_of)}")
            return _finish(run, MandateReconciliation(status="insufficient_data", gaps=[gap], **base))
        breaches, gaps, managed = build_subjects(evidence)
        notes = load_notes(registry, run, client_id, as_of) if breaches else []
        results: list[BreachResult] = [_neutral(b) for b in breaches]
        ambiguous = []
        if breaches and notes:
            raw, raw_amb, err = _ask(run, model, build_input(client_id, as_of, breaches, notes))
            if err:
                gaps.append(Gap(kind="agent_error", description=err, subject=ROLE))
            else:
                out = guard_results(raw, raw_amb, breaches, notes, evidence, as_of, multi_portfolio=managed > 1)
                results, ambiguous, gaps = out.results, out.ambiguous, gaps + out.gaps
    except (PolicyDenied, PolicyEscalated) as e:
        gaps.append(Gap(kind="policy_denied", description=e.reason, subject=ROLE))
        return _finish(run, MandateReconciliation(status="partial", results=[_neutral(b) for b in breaches], gaps=gaps, **base))
    except Exception as e:  # noqa: BLE001 - always delivered: nothing escapes as an unhandled error
        gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
        return _finish(run, MandateReconciliation(status="partial", results=[_neutral(b) for b in breaches], gaps=gaps, **base))
    gaps = _checkpoints(run, gaps, len(results))
    return _finish(run, MandateReconciliation(status="partial" if gaps else "complete", results=_restore(run, results),
                                              ambiguous_notes=ambiguous, gaps=[_restore_gap(run, g) for g in gaps], **base))


def _ask(run: RunContext, model: BaseChatModel, text: str) -> tuple[list, list, str | None]:
    safe = run.model_call(ROLE, [{"role": "system", "content": prompts.MANDATE_RECONCILER}, {"role": "user", "content": text}])
    try:
        reply = model.invoke([SystemMessage(content=safe[0]["content"]), HumanMessage(content=safe[1]["content"])],
                             config=llm_config(run, ROLE))
    except Exception as e:  # noqa: BLE001
        return [], [], f"{type(e).__name__}: {e}"
    content = reply.content if isinstance(reply, AIMessage) and isinstance(reply.content, str) else ""
    obj, err = parse_json_object(content)
    if err or obj is None or not isinstance(obj.get("results"), list):
        return [], [], err or "the model's answer had no results list"
    amb = obj.get("ambiguous_notes")
    return obj["results"], amb if isinstance(amb, list) else [], None


def _checkpoints(run: RunContext, gaps: list[Gap], results: int) -> list[Gap]:
    gaps = list(gaps)
    for name in (EVIDENCE_PROVENANCE, COMPLIANCE_CONTENT):
        try:
            run.guard(name, ROLE, "report_assembly", results=results)
        except (PolicyDenied, PolicyEscalated) as e:
            gaps.append(Gap(kind="policy_denied", description=e.reason, subject=name))
    return gaps


def _restore(run: RunContext, results: list[BreachResult]) -> list[BreachResult]:
    restore = run.pseudonymiser.restore
    return [r.model_copy(update={"rationale": restore(r.rationale)}) for r in results]


def _restore_gap(run: RunContext, g: Gap) -> Gap:
    return g.model_copy(update={"description": run.pseudonymiser.restore(g.description)})


def _finish(run: RunContext, rec: MandateReconciliation) -> MandateReconciliation:
    return rec.model_copy(update={"policy_decisions": run.report_decisions()})
