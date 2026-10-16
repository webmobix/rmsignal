"""The note reconciler: one model call per client, judged against the persisted report, checked in code."""

import json
from datetime import date

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from rm_dashboard.agents import prompts
from rm_dashboard.agents.outputs import parse_object_list
from rm_dashboard.agents.stubplans import INPUT_MARKER
from rm_dashboard.domain import Gap
from rm_dashboard.llmlog import llm_config
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyDenied, PolicyEscalated, PolicyEngine, RunContext
from rm_dashboard.policy.engine import COMPLIANCE_CONTENT, EVIDENCE_PROVENANCE
from rm_dashboard.reportsource import FolderReportSource, flatten
from rm_dashboard.tools import ALLOWLISTS, ToolRegistry

from .contracts import NoteResult, Reconciliation
from .guard import Note, _unverifiable, guard_results

ROLE = "note_reconciler"
FAILED = "No assessment could be made because the reconciliation run failed; the note is treated as unverifiable."


def load_notes(registry: ToolRegistry, run: RunContext, client_id: str, as_of: date):
    """Notes of the client up to ``as_of`` through the notes tool (point-in-time, policy and audit apply)."""
    toolbox = registry.toolbox(ROLE, ALLOWLISTS[ROLE], observer=run.tool_observer(), run=run)
    result = toolbox.call("notes.list", {"client_id": client_id, "as_of": as_of.isoformat()})
    notes = [Note(r["note_id"], date.fromisoformat(str(r["note_date"])), r["quote"]) for r in (result.data or [])]
    return notes, result


def build_input(client_id: str, as_of: date, notes: list[Note], findings, quality_flags: list[str]) -> str:
    payload = {
        "client_id": client_id, "as_of": as_of.isoformat(),
        "notes": [{"note_id": n.note_id, "note_date": n.note_date.isoformat(), "quote": n.quote} for n in notes],
        "findings": [{"ref": f.ref, "claim": f.claim, "confidence": f.confidence} for f in findings],
        "quality_flags": quality_flags,
    }
    return (f"Reconcile the notes of client {client_id} as of {as_of.isoformat()} with the report findings.\n"
            f"{INPUT_MARKER}{json.dumps(payload, sort_keys=True)}")


def parse_results(text: str | None) -> tuple[list, str | None]:
    return parse_object_list(text, "results")


def reconcile(registry: ToolRegistry, client_id: str, *, as_of: date, source: FolderReportSource, model: BaseChatModel,
              engine: PolicyEngine | None = None, audit: AuditLog | None = None) -> Reconciliation:
    """Reconcile one client's notes. Always returns a ``Reconciliation``; failures become gaps."""
    from rm_dashboard.agents.scope import register_people

    run = RunContext(client_id, as_of, engine=engine or MockPolicyEngine(), audit=audit or AuditLog())
    base = dict(client_id=client_id, as_of=as_of)
    gaps: list[Gap] = []
    notes: list[Note] = []
    results: list[NoteResult] = []
    try:
        register_people(run, registry.ctx.repo, as_of)
        run.run_start(ROLE)
        report, evidence = source.report(as_of, client_id), source.evidence(as_of, client_id)
        if report is None or evidence is None:
            what = "report" if report is None else "evidence"
            gap = Gap(kind="no_data", subject=client_id,
                      description=f"no persisted {what} for {client_id} at {as_of} in {source.run_dir(as_of)}")
            return _finish(run, Reconciliation(status="insufficient_data", gaps=[gap], **base))
        notes, _ = load_notes(registry, run, client_id, as_of)
        if not notes:
            return _finish(run, Reconciliation(status="complete", **base))
        findings = flatten(report)
        raw, err = _ask(run, model, build_input(client_id, as_of, notes, findings, [f.message for f in report.flags]))
        if err:
            gaps.append(Gap(kind="agent_error", description=err, subject=ROLE))
        out = guard_results(raw, notes, {f.ref: f for f in findings}, evidence, as_of)
        results, gaps = out.results, gaps + out.gaps
        if err:
            results = [_unverifiable(n, FAILED) for n in sorted(notes, key=lambda n: (n.note_date, n.note_id))]
    except (PolicyDenied, PolicyEscalated) as e:
        gaps.append(Gap(kind="policy_denied", description=e.reason, subject=ROLE))
        status = "partial" if notes else "insufficient_data"
        return _finish(run, Reconciliation(status=status, results=_all_unverifiable(notes), gaps=gaps, **base))
    except Exception as e:  # noqa: BLE001 - always delivered: nothing escapes as an unhandled error
        gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
        return _finish(run, Reconciliation(status="partial", results=_all_unverifiable(notes), gaps=gaps, **base))
    gaps = _checkpoints(run, gaps, len(results))
    return _finish(run, Reconciliation(status="partial" if gaps else "complete", results=_restore(run, results),
                                       gaps=[_restore_gap(run, g) for g in gaps], **base))


def _all_unverifiable(notes: list[Note]) -> list[NoteResult]:
    return [_unverifiable(n, FAILED) for n in sorted(notes, key=lambda n: (n.note_date, n.note_id))]


def _ask(run: RunContext, model: BaseChatModel, text: str) -> tuple[list, str | None]:
    safe = run.model_call(ROLE, [{"role": "system", "content": prompts.NOTE_RECONCILER}, {"role": "user", "content": text}])
    try:
        reply = model.invoke([SystemMessage(content=safe[0]["content"]), HumanMessage(content=safe[1]["content"])],
                           config=llm_config(run, ROLE))
    except Exception as e:  # noqa: BLE001
        return [], f"{type(e).__name__}: {e}"
    content = reply.content if isinstance(reply, AIMessage) and isinstance(reply.content, str) else ""
    return parse_results(content)


def _checkpoints(run: RunContext, gaps: list[Gap], results: int) -> list[Gap]:
    gaps = list(gaps)
    for name in (EVIDENCE_PROVENANCE, COMPLIANCE_CONTENT):
        try:
            run.guard(name, ROLE, "report_assembly", results=results)
        except (PolicyDenied, PolicyEscalated) as e:
            gaps.append(Gap(kind="policy_denied", description=e.reason, subject=name))
    return gaps


def _restore(run: RunContext, results: list[NoteResult]) -> list[NoteResult]:
    restore = run.pseudonymiser.restore
    return [r.model_copy(update={"rationale": restore(r.rationale)}) for r in results]


def _restore_gap(run: RunContext, g: Gap) -> Gap:
    return g.model_copy(update={"description": run.pseudonymiser.restore(g.description)})


def _finish(run: RunContext, rec: Reconciliation) -> Reconciliation:
    return rec.model_copy(update={"policy_decisions": run.report_decisions()})
