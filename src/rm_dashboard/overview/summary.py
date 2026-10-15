"""The optional model summary of an overview: guarded, and never able to change actions or their order."""

import json
from datetime import date
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from rm_dashboard.agents import prompts
from rm_dashboard.agents.guard import evidence_numbers, unsupported_numbers
from rm_dashboard.agents.scope import register_people
from rm_dashboard.agents.stubplans import INPUT_MARKER
from rm_dashboard.domain import Gap
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyDenied, PolicyEngine, PolicyEscalated, RunContext
from rm_dashboard.policy.engine import COMPLIANCE_CONTENT, EVIDENCE_PROVENANCE
from rm_dashboard.tools import ToolRegistry

from .build import build_overview
from .contracts import Overview, OverviewAction, Theme
from .source import OverviewSource, RmInfo

ROLE = "rm_overview_summary"
TOP_N = 20
MAX_THEMES = 4


def build_input(overview: Overview, top: list[OverviewAction]) -> str:
    payload = {
        "rm_id": overview.rm_id, "as_of": overview.as_of.isoformat(),
        "actions": [{"action_id": a.action_id, "client": a.client_name, "category": a.category, "importance": a.importance,
                     "horizon": a.horizon, "title": a.title, "what": a.what, "why": a.why} for a in top],
    }
    return (f"Brief the RM {overview.rm_id} on the next actions as of {overview.as_of.isoformat()}.\n"
            f"{INPUT_MARKER}{json.dumps(payload, sort_keys=True)}")


def _text(a: OverviewAction) -> list[str]:
    return [a.title, a.what, a.why]


def guard_summary(raw: Any, top: list[OverviewAction]) -> tuple[str, list[Theme], list[Gap]]:
    """Summary and themes that survive: figures grounded in the actions, theme ids that exist. Nothing else is read."""
    gaps: list[Gap] = []
    if not isinstance(raw, dict):
        return "", [], [Gap(kind="agent_error", description="the model's answer was not an object", subject=ROLE)]
    by_id = {a.action_id: a for a in top}
    summary = raw.get("summary") if isinstance(raw.get("summary"), str) else ""
    bad = unsupported_numbers(summary, evidence_numbers([t for a in top for t in _text(a)]))
    if bad:
        gaps.append(Gap(kind="guard_removed", subject="summary",
                        description="summary removed: figure(s) " + ", ".join(f"{b:g}" for b in bad) + " not present in the actions"))
        summary = ""
    themes: list[Theme] = []
    for t in raw.get("themes") if isinstance(raw.get("themes"), list) else []:
        title = t.get("title") if isinstance(t, dict) else None
        ids = t.get("action_ids") if isinstance(t, dict) else None
        if not isinstance(title, str) or not title.strip() or not isinstance(ids, list):
            gaps.append(Gap(kind="guard_removed", subject="theme", description="theme removed: it needs a title and action ids"))
            continue
        unknown = [i for i in ids if i not in by_id]
        if unknown or len(set(ids)) < 2:
            gaps.append(Gap(kind="guard_removed", subject=title[:60],
                            description=f"theme removed: " + (f"unknown action id(s) {', '.join(map(str, unknown))}" if unknown else "it groups fewer than two actions")))
            continue
        bad = unsupported_numbers(title, evidence_numbers([x for i in ids for x in _text(by_id[i])]))
        if bad:
            gaps.append(Gap(kind="guard_removed", subject=title[:60], description="theme removed: figure(s) " + ", ".join(f"{b:g}" for b in bad) + " not present in its actions"))
            continue
        if len(themes) < MAX_THEMES:
            themes.append(Theme(title=title.strip(), action_ids=list(dict.fromkeys(ids))))
    return summary.strip(), themes, gaps


def create_overview(registry: ToolRegistry, rm: RmInfo, *, as_of: date, source: OverviewSource, model: BaseChatModel,
                    engine: PolicyEngine | None = None, audit: AuditLog | None = None) -> Overview:
    """The overview of one RM with an optional summary. Always returns an ``Overview``."""
    overview = build_overview(rm, as_of, source)
    run = RunContext(rm.rm_id, as_of, engine=engine or MockPolicyEngine(), audit=audit or AuditLog())
    if not overview.actions:
        return overview.model_copy(update={"policy_decisions": run.report_decisions()})
    top = overview.actions[:TOP_N]
    gaps = list(overview.gaps)
    summary, themes = "", []
    try:
        register_people(run, registry.ctx.repo, as_of)
        run.run_start(ROLE)
        raw, err = _ask(run, model, build_input(overview, top))
        if err:
            gaps.append(Gap(kind="agent_error", description=err, subject=ROLE))
        else:
            summary, themes, new = guard_summary(raw, top)
            gaps += new
        for name in (EVIDENCE_PROVENANCE, COMPLIANCE_CONTENT):
            try:
                run.guard(name, ROLE, "report_assembly", actions=len(top))
            except (PolicyDenied, PolicyEscalated) as e:
                gaps.append(Gap(kind="policy_denied", description=e.reason, subject=name))
    except (PolicyDenied, PolicyEscalated) as e:
        gaps.append(Gap(kind="policy_denied", description=e.reason, subject=ROLE))
    except Exception as e:  # noqa: BLE001 - always delivered: a failed summary never blocks the overview
        gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
    restore = run.pseudonymiser.restore
    return overview.model_copy(update={
        "summary": restore(summary), "themes": [Theme(title=restore(t.title), action_ids=t.action_ids) for t in themes],
        "gaps": gaps, "status": "partial" if gaps else overview.status, "policy_decisions": run.report_decisions()})


def _ask(run: RunContext, model: BaseChatModel, text: str) -> tuple[Any, str | None]:
    from rm_dashboard.agents.outputs import parse_json_object

    safe = run.model_call(ROLE, [{"role": "system", "content": prompts.RM_OVERVIEW_SUMMARY}, {"role": "user", "content": text}])
    try:
        reply = model.invoke([SystemMessage(content=safe[0]["content"]), HumanMessage(content=safe[1]["content"])])
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"
    content = reply.content if isinstance(reply, AIMessage) and isinstance(reply.content, str) else ""
    return parse_json_object(content)
