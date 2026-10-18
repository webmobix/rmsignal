"""The analysts: Deep Agents graphs with narrow tools, delegation, an output guard and always-delivered reports."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from deepagents import CompiledSubAgent, create_deep_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from rm_dashboard.domain import Finding, Gap, Report
from rm_dashboard.llmlog import llm_config
from rm_dashboard.policy import PolicyDenied, PolicyEscalated
from rm_dashboard.tools import ALLOWLISTS, Toolbox

from . import prompts
from .guard import guard_output
from .middleware import AllowListMiddleware, NoSummarizationMiddleware, PrivacyMiddleware
from .scope import RunScope
from .tooladapter import lc_name, make_tools, to_json

RECURSION_LIMIT = 80
NO_DATA_STATUSES = ("no_data", "insufficient_data", "insufficient_history")


@dataclass(frozen=True)
class AnalystSpec:
    name: str
    subject_kind: str
    subject_pattern: str
    prompt: str
    allowlist: tuple[str, ...]
    delegates: tuple[str, ...]
    description: str


ANALYSTS: dict[str, AnalystSpec] = {
    "instrument_analyst": AnalystSpec(
        "instrument_analyst", "instrument", r"SYN-[A-Z]{2}-\d{4}", prompts.INSTRUMENT_ANALYST,
        ALLOWLISTS["instrument_analyst"], (), "Analyses one instrument: reference data, price path, events, market context."),
    "portfolio_analyst": AnalystSpec(
        "portfolio_analyst", "portfolio", r"PF-\d{4}", prompts.PORTFOLIO_ANALYST,
        ALLOWLISTS["portfolio_analyst"], (),
        "Analyses one portfolio: composition, mandate bands, P&L; reads the persisted outlooks of its largest positions."),
    "relationship_analyst": AnalystSpec(
        "relationship_analyst", "client", r"CL-\d{4}", prompts.RELATIONSHIP_ANALYST,
        ALLOWLISTS["relationship_analyst"], ("portfolio_analyst",),
        "Analyses one client relationship: profile, concentration, liquidity, credit; delegates portfolios."),
}

ModelFactory = Callable[[str], BaseChatModel]
"""role name -> chat model for that agent."""


# ---- building -----------------------------------------------------------------------------
def build_agent(spec: AnalystSpec, scope: RunScope, models: ModelFactory, *, requester: str = "user",
                checkpointer=None):
    """Compile one analyst. Returns (agent graph, toolbox)."""
    run = scope.run
    toolbox: Toolbox = scope.registry.toolbox(spec.name, spec.allowlist, store=scope.store, observer=run.tool_observer(), run=run)
    tools = make_tools(toolbox, scope)
    subagents = [
        CompiledSubAgent(name=d, description=ANALYSTS[d].description,
                         runnable=RunnableLambda(_child_runner(d, scope, models, spec.name)))
        for d in spec.delegates
    ]
    agent = create_deep_agent(
        model=models(spec.name), tools=tools, system_prompt=spec.prompt, subagents=subagents or None,
        middleware=[AllowListMiddleware({lc_name(n) for n in spec.allowlist}, set(spec.delegates)),
                    PrivacyMiddleware(scope, spec.name), NoSummarizationMiddleware()],
        checkpointer=checkpointer, name=spec.name,
    )
    return agent, toolbox


def _child_runner(role: str, parent: RunScope, models: ModelFactory, requester: str):
    spec = ANALYSTS[role]

    def run_child(state: dict, config=None) -> dict:
        text = _last_text(state)
        m = re.search(spec.subject_pattern, text or "")
        if not m:
            gap = Gap(kind="agent_error", description=f"{role} was asked without a {spec.subject_kind} id", subject=role)
            parent.gaps.append(gap)
            payload = {"agent": role, "subject": None, "status": "partial", "findings": [], "gaps": [gap.description]}
            return {"messages": [AIMessage(content=to_json(payload))]}
        child_scope = RunScope(run=parent.run.child(requester), registry=parent.registry, store=parent.store)
        report = analyse(role, m.group(0), child_scope, models, requester=requester, top_level=False)
        parent.children.append(report)
        payload = {"agent": role, "subject": report.subject, "status": report.status,
                   "findings": [f.model_dump() for f in report.findings],
                   "gaps": [g.description for g in report.gaps]}
        return {"messages": [AIMessage(content=to_json(payload))]}

    return run_child


def _last_text(state: dict) -> str:
    for m in reversed(state.get("messages", [])):
        if m.text:  # text of string or block content (Gemini returns blocks)
            return m.text
    return ""


# ---- running ------------------------------------------------------------------------------
def request_message(spec: AnalystSpec, subject: str, scope: RunScope) -> HumanMessage:
    return HumanMessage(content=f"Analyse {spec.subject_kind} {subject} as of {scope.as_of.isoformat()}.")


def analyse(role: str, subject: str, scope: RunScope, models: ModelFactory, *, requester: str = "user",
            top_level: bool = True, checkpointer=None) -> Report:
    """Run one analyst and always return a Report."""
    spec = ANALYSTS[role]
    run = scope.run
    base = dict(subject=subject, as_of=scope.as_of, agent=role)
    try:
        run.run_start(role, requester) if top_level else run.guard("request_entitlement", role, "delegation_start", requester=requester)
    except (PolicyDenied, PolicyEscalated) as e:
        return _finish(Report(status="insufficient_data", gaps=[Gap(kind="policy_denied", description=e.reason, subject=role)], **base),
                       scope, spec, top_level)
    res = scope.registry.ctx.repo.resolve(as_of=scope.as_of)
    if res.status != "ok":
        gap = Gap(kind="no_data", description=res.reason or "no data at as_of", subject="as_of")
        return _finish(Report(status="insufficient_data", gaps=[gap], **base), scope, spec, top_level)
    produced: list = []
    try:
        agent, toolbox = build_agent(spec, scope, models, requester=requester, checkpointer=checkpointer)
        produced = toolbox.produced
        out = agent.invoke({"messages": [request_message(spec, subject, scope)]},
                           config={"recursion_limit": RECURSION_LIMIT, **llm_config(run, role)})
        text = _final_text(out)
        return assemble_report(spec, subject, scope, produced, text, top_level)
    except Exception as e:  # noqa: BLE001 - always-deliver: nothing escapes as an unhandled error
        scope.gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=role))
        return assemble_report(spec, subject, scope, produced, None, top_level)


def _final_text(out: dict) -> str:
    for m in reversed(out.get("messages", [])):
        if isinstance(m, AIMessage) and m.text.strip() and not m.tool_calls:
            return m.text
    return ""


def parse_output(text: str | None) -> tuple[list, str, str | None]:
    """(raw findings, summary, error). Tolerates code fences and surrounding prose."""
    if not text:
        return [], "", "the agent produced no final answer"
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-z]*\n?|```$", "", s, flags=re.M).strip()
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end <= start:
        return [], "", "the agent's final answer was not JSON"
    try:
        obj = json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return [], "", "the agent's final answer was not valid JSON"
    findings = obj.get("findings")
    return (findings if isinstance(findings, list) else []), str(obj.get("summary") or ""), None


def assemble_report(spec: AnalystSpec, subject: str, scope: RunScope, produced: list, text: str | None,
                    top_level: bool) -> Report:
    raw, summary, err = parse_output(text)
    gaps = list(scope.gaps)
    if err:
        gaps.append(Gap(kind="agent_error", description=err, subject=spec.name))
    out = guard_output(raw, summary, scope.store, scope.as_of)
    gaps += out.gaps

    seen = set()
    for r in produced:
        if r.status in NO_DATA_STATUSES:
            key = (r.computation.tool, r.reason)
            if key not in seen:
                seen.add(key)
                gaps.append(Gap(kind="no_data", description=f"{r.computation.tool}: {r.reason}", subject=r.computation.tool))
    by_id = {r.evidence_id: r for r in produced}
    cited = [i for f in out.findings for i in f.evidence_ids]
    flags, fseen = [], set()
    for i in dict.fromkeys(cited):
        for f in (by_id[i].flags if i in by_id else scope.store.get(i).flags):
            k = (f.code, f.subject, f.message)
            if k not in fseen:
                fseen.add(k)
                flags.append(f)
    children = list(scope.children)
    evidence = sorted({r.evidence_id for r in produced} | set(cited) | {i for c in children for i in c.evidence_ids})
    status = "partial" if gaps or any(c.status != "complete" for c in children) else "complete"
    if produced and all(r.status == "insufficient_data" for r in produced):
        status = "insufficient_data"
    report = Report(subject=subject, as_of=scope.as_of, status=status, agent=spec.name, summary=out.summary,
                    findings=out.findings, gaps=gaps, flags=flags, evidence_ids=evidence, children=children)
    return _finish(report, scope, spec, top_level)


def _finish(report: Report, scope: RunScope, spec: AnalystSpec, top_level: bool) -> Report:
    report = scope.run.assemble(report, spec.name)
    return restore_names(report, scope) if top_level else report


def restore_names(report: Report, scope: RunScope) -> Report:
    """Pseudonyms go back to names only in the final report."""
    restore = scope.run.pseudonymiser.restore
    return report.model_copy(update={
        "summary": restore(report.summary),
        "findings": [Finding(claim=restore(f.claim), confidence=f.confidence, evidence_ids=f.evidence_ids) for f in report.findings],
        "gaps": [g.model_copy(update={"description": restore(g.description)}) for g in report.gaps],
        "children": [restore_names(c, scope) for c in report.children],
    })
