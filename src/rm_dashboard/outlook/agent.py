"""The outlook analyst: one agent run for the market, then code decides what the views may rest on."""

import dataclasses
from datetime import date

from langchain_core.messages import HumanMessage

from rm_dashboard.agents import prompts
from rm_dashboard.agents.analyst import RECURSION_LIMIT, AnalystSpec, ModelFactory, _final_text, build_agent
from rm_dashboard.agents.outputs import parse_json_object
from rm_dashboard.agents.scope import RunScope
from rm_dashboard.domain import Gap, ToolResult
from rm_dashboard.llmlog import llm_config
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyDenied, PolicyEngine, PolicyEscalated, RunContext
from rm_dashboard.policy.engine import COMPLIANCE_CONTENT, EVIDENCE_PROVENANCE
from rm_dashboard.tools import ALLOWLISTS, ToolRegistry

from .contracts import (
    SUBJECT, Change, EventRef, InstrumentInputs, InstrumentOutlook, InstrumentRef, MarketOutlook, OutlookInputs, PricePoint,
)
from .guard import GuardInput, InstrumentGuardInput, guard_instrument_outlook, guard_market_outlook
from .inputs import (
    all_events, compute_inputs, instrument_inputs, instrument_prices, market_context_for, required_segments, severe_events_in_window,
    unavailable_statistics,
)
from .relevance import relevant_events
from .store import OutlookStore

ROLE = "outlook_analyst"
SPEC = AnalystSpec(ROLE, "market", SUBJECT, prompts.OUTLOOK_ANALYST, ALLOWLISTS[ROLE], (),
                   "Writes the house view of the market from its history and the events.")
INSTRUMENT_SPEC = AnalystSpec(ROLE, "instrument", r"SYN-[A-Z]{2}-\d{4}", prompts.OUTLOOK_INSTRUMENT, ALLOWLISTS["outlook_instrument"], (),
                              "Writes the house view of one instrument in the context of its peers, events and the market outlook.")
"""Same agent, narrower tools: an instrument run cannot call the market-only tools and the market run cannot call the instrument ones."""


def request_text(as_of: date, segments: list[str]) -> str:
    return f"Produce the market outlook as of {as_of.isoformat()}. Segments: {', '.join(segments)}."


def carry_forward(prev: MarketOutlook, *, as_of: date, inputs: OutlookInputs, status: str | None = None,
                  gaps: list[Gap] | None = None, why: str | None = None) -> MarketOutlook:
    """The previous views again, every one ``unchanged``, with the date they come from."""
    why = why or f"no new data since {prev.as_of}"
    views = [v.model_copy(update={"change": Change(kind="unchanged", previous_direction=v.direction, why=why)}) for v in prev.views]
    return prev.model_copy(update={
        "as_of": as_of, "inputs": inputs, "views": views, "previous_as_of": prev.as_of, "is_first": False,
        "carried_forward_from": prev.as_of, "unaddressed_events": [], "policy_decisions": [],
        "changes_summary": f"Carried forward from {prev.as_of}: all {len(views)} views unchanged.",
        "status": status or prev.status, "gaps": [*prev.gaps, *(gaps or [])]})


def can_carry_forward(prev: MarketOutlook | None, inputs: OutlookInputs, force: bool) -> bool:
    return bool(prev and not force and prev.views and prev.inputs == inputs)


def produce_market_outlook(registry: ToolRegistry, *, as_of: date, store: OutlookStore, models: ModelFactory,
                           engine: PolicyEngine | None = None, audit: AuditLog | None = None,
                           force: bool = False) -> tuple[MarketOutlook, list[ToolResult]]:
    """The market outlook for ``as_of`` and the evidence it rests on. Always returns an outlook; failures become gaps."""
    registry = ToolRegistry(dataclasses.replace(registry.ctx, reports_dir=store.base_dir), registry.specs.values())
    run = RunContext(SUBJECT, as_of, engine=engine or MockPolicyEngine(), audit=audit or AuditLog())
    repo = registry.ctx.repo
    inputs, no_market = compute_inputs(repo, as_of)
    prev = store.previous_market(before=as_of)
    prev_evidence = store.load_market_evidence(prev.as_of) if prev else []
    gaps: list[Gap] = []
    scope = RunScope(run=run, registry=registry)
    started = False
    try:
        run.run_start(ROLE)
        started = True
        if no_market:
            out = MarketOutlook(as_of=as_of, status="insufficient_data", inputs=inputs, previous_as_of=prev.as_of if prev else None,
                                gaps=[Gap(kind="no_data", description=no_market, subject="market_context")])
            return _finish(run, out), []
        if can_carry_forward(prev, inputs, force):
            return _finish(run, carry_forward(prev, as_of=as_of, inputs=inputs)), prev_evidence
        required = required_segments(repo, as_of)
        agent, toolbox = build_agent(SPEC, scope, models)
        raw: list = []
        summary = ""
        try:
            result = agent.invoke({"messages": [HumanMessage(content=request_text(as_of, required))]},
                                  config={"recursion_limit": RECURSION_LIMIT, **llm_config(run, SPEC.name)})
            obj, err = parse_json_object(_final_text(result))
            if err:
                gaps.append(Gap(kind="agent_error", description=err, subject=ROLE))
            else:
                raw = obj.get("views") if isinstance(obj.get("views"), list) else []
                summary = obj.get("summary") if isinstance(obj.get("summary"), str) else ""
                if not raw:
                    gaps.append(Gap(kind="agent_error", description="the model's answer had no views list", subject=ROLE))
        except (PolicyDenied, PolicyEscalated):
            raise
        except Exception as e:  # noqa: BLE001 - always delivered: nothing escapes as an unhandled error
            gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
        events = all_events(repo, as_of)
        g = GuardInput(store=scope.store, as_of=as_of, required=required, prev=prev, all_events=events,
                       severe_in_window=severe_events_in_window(events, prev.as_of if prev else None, as_of))
        out = guard_market_outlook(raw, summary, g)
        evidence = list(scope.store.results.values())
        gaps = [*scope.gaps, *gaps, *out.gaps]
        if not out.fresh and prev is not None and prev.views:
            gaps.append(Gap(kind="agent_error", description="no valid new views: the previous views are carried forward", subject=ROLE))
            return _finish(run, carry_forward(prev, as_of=as_of, inputs=inputs, status="partial", gaps=gaps, why="the new run produced no valid views")), \
                [*prev_evidence, *evidence]
        outlook = MarketOutlook(
            as_of=as_of, status="partial" if gaps else "complete", summary=out.summary, views=out.views, inputs=inputs,
            previous_as_of=prev.as_of if prev else None, is_first=prev is None, changes_summary=out.changes_summary,
            unaddressed_events=out.unaddressed, gaps=gaps, evidence_ids=sorted(r.evidence_id for r in evidence))
        # views kept from the previous outlook cite its evidence: keep that evidence resolvable
        kept_prev = {i for v in out.views for r in (*v.drivers, *v.risks) for i in r.evidence_ids} - {r.evidence_id for r in evidence}
        extra = [e for e in prev_evidence if e.evidence_id in kept_prev]
        return _finish(run, outlook), [*extra, *evidence]
    except (PolicyDenied, PolicyEscalated) as e:
        gaps.append(Gap(kind="policy_denied", description=e.reason, subject=ROLE))
        return _fallback(run, prev, prev_evidence, inputs, as_of, gaps, started)
    except Exception as e:  # noqa: BLE001
        gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
        return _fallback(run, prev, prev_evidence, inputs, as_of, gaps, started)


def _fallback(run, prev, prev_evidence, inputs, as_of, gaps, started):
    if prev is not None and prev.views:
        return _finish(run, carry_forward(prev, as_of=as_of, inputs=inputs, status="partial", gaps=gaps,
                                          why="the new run failed")), prev_evidence
    out = MarketOutlook(as_of=as_of, status="partial" if started else "insufficient_data", inputs=inputs,
                        previous_as_of=prev.as_of if prev else None, is_first=prev is None, gaps=gaps)
    return _finish(run, out), []


def _finish(run: RunContext, outlook: MarketOutlook) -> MarketOutlook:
    gaps = list(outlook.gaps)
    for name in (EVIDENCE_PROVENANCE, COMPLIANCE_CONTENT):
        try:
            run.guard(name, ROLE, "report_assembly", views=len(outlook.views))
        except (PolicyDenied, PolicyEscalated) as e:
            gaps.append(Gap(kind="policy_denied", description=e.reason, subject=name))
    status = outlook.status
    if len(gaps) > len(outlook.gaps) and status == "complete":
        status = "partial"
    return outlook.model_copy(update={"gaps": gaps, "status": status, "policy_decisions": run.report_decisions()})


# ---- instruments ----------------------------------------------------------------------------------
def instrument_request_text(instrument_id: str, as_of: date) -> str:
    return f"Produce the outlook for instrument {instrument_id} as of {as_of.isoformat()}."


def can_carry_forward_instrument(prev: InstrumentOutlook | None, inputs: InstrumentInputs, force: bool) -> bool:
    return bool(prev and not force and prev.view is not None and prev.inputs.same_as(inputs))


def carry_forward_instrument(prev: InstrumentOutlook, *, as_of: date, inputs: InstrumentInputs, market_context: list, status: str | None = None,
                             gaps: list[Gap] | None = None, why: str | None = None) -> InstrumentOutlook:
    """The previous view again, ``unchanged``, with the date it comes from."""
    why = why or f"no new data since {prev.as_of}"
    view = prev.view.model_copy(update={"change": Change(kind="unchanged", previous_direction=prev.view.direction, why=why)})
    return prev.model_copy(update={
        "as_of": as_of, "inputs": inputs, "view": view, "previous_as_of": prev.as_of, "is_first": False, "carried_forward_from": prev.as_of,
        "market_context": market_context, "market_outlook_as_of": inputs.market_outlook_as_of, "unaddressed_events": [],
        "policy_decisions": [], "changes_summary": f"Carried forward from {prev.as_of}: the view is unchanged.",
        "status": status or prev.status, "gaps": [*prev.gaps, *(gaps or [])]})


def produce_instrument_outlook(registry: ToolRegistry, *, instrument_id: str, as_of: date, store: OutlookStore, models: ModelFactory,
                               engine: PolicyEngine | None = None, audit: AuditLog | None = None,
                               force: bool = False) -> tuple[InstrumentOutlook, list[ToolResult]]:
    """The outlook of one instrument and the evidence it rests on. Always returns an outlook; failures become gaps."""
    registry = ToolRegistry(dataclasses.replace(registry.ctx, reports_dir=store.base_dir), registry.specs.values())
    run = RunContext(instrument_id, as_of, engine=engine or MockPolicyEngine(), audit=audit or AuditLog())
    repo = registry.ctx.repo
    inputs, row, no_data = instrument_inputs(repo, store, instrument_id, as_of)
    prev = store.previous_instrument(instrument_id, before=as_of)
    prev_evidence = store.load_instrument_evidence(prev.as_of, instrument_id) if prev else []
    market = store.latest_market(as_of)
    market_context = market_context_for(row, market) if row else []
    ref = InstrumentRef(**{k: row.get(k) for k in InstrumentRef.model_fields}) if row else None
    prices = instrument_prices(repo, as_of, instrument_id)
    facts = dict(subject=instrument_id, as_of=as_of, instrument=ref, inputs=inputs, previous_as_of=prev.as_of if prev else None,
                 price_path=[PricePoint(snapshot_date=d, price=p) for d, p in prices],
                 unavailable_statistics=unavailable_statistics([p for _, p in prices]) if prices else [],
                 market_outlook_as_of=inputs.market_outlook_as_of, market_context=market_context)
    gaps: list[Gap] = []
    scope = RunScope(run=run, registry=registry)
    started = False
    try:
        run.run_start(ROLE)
        started = True
        if no_data:
            return _finish_instrument(run, InstrumentOutlook(status="insufficient_data", gaps=[Gap(kind="no_data", description=no_data, subject=instrument_id)],
                                                             **facts)), []
        if can_carry_forward_instrument(prev, inputs, force):
            return _finish_instrument(run, carry_forward_instrument(prev, as_of=as_of, inputs=inputs, market_context=market_context)), prev_evidence
        if market is None:
            gaps.append(Gap(kind="no_data", subject="outlook.market", description="no market outlook exists on or before as_of: the market context is unavailable"))
        agent, toolbox = build_agent(INSTRUMENT_SPEC, scope, models)
        raw: object = None
        summary = ""
        try:
            result = agent.invoke({"messages": [HumanMessage(content=instrument_request_text(instrument_id, as_of))]},
                                  config={"recursion_limit": RECURSION_LIMIT, **llm_config(run, INSTRUMENT_SPEC.name)})
            obj, err = parse_json_object(_final_text(result))
            if err:
                gaps.append(Gap(kind="agent_error", description=err, subject=ROLE))
            else:
                raw = obj.get("view")
                summary = obj.get("summary") if isinstance(obj.get("summary"), str) else ""
                if not isinstance(raw, dict):
                    gaps.append(Gap(kind="agent_error", description="the model's answer had no view", subject=ROLE))
        except (PolicyDenied, PolicyEscalated):
            raise
        except Exception as e:  # noqa: BLE001 - always delivered: nothing escapes as an unhandled error
            gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
        candidates = relevant_events(row, all_events(repo, as_of))
        g = InstrumentGuardInput(store=scope.store, as_of=as_of, prev=prev,
                                 severe_in_window=severe_events_in_window(candidates, prev.as_of if prev else None, as_of))
        out = guard_instrument_outlook(raw, summary, g)
        evidence = _own_evidence(scope, toolbox, out.view)
        gaps = [*scope.gaps, *gaps, *out.gaps]
        if not out.fresh and prev is not None and prev.view is not None:
            gaps.append(Gap(kind="agent_error", description="no valid new view: the previous view is carried forward", subject=ROLE))
            return _finish_instrument(run, carry_forward_instrument(prev, as_of=as_of, inputs=inputs, market_context=market_context, status="partial",
                                                                    gaps=gaps, why="the new run produced no valid view")), [*prev_evidence, *evidence]
        outlook = InstrumentOutlook(status="partial" if gaps else "complete", summary=out.summary, view=out.view, is_first=prev is None,
                                    relevant_events=out.cited_events, changes_summary=out.changes_summary, unaddressed_events=out.unaddressed,
                                    gaps=gaps, evidence_ids=sorted(r.evidence_id for r in evidence), **facts)
        return _finish_instrument(run, outlook), evidence
    except (PolicyDenied, PolicyEscalated) as e:
        gaps.append(Gap(kind="policy_denied", description=e.reason, subject=ROLE))
        return _instrument_fallback(run, prev, prev_evidence, inputs, as_of, market_context, gaps, started, facts)
    except Exception as e:  # noqa: BLE001
        gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
        return _instrument_fallback(run, prev, prev_evidence, inputs, as_of, market_context, gaps, started, facts)


def _own_evidence(scope: RunScope, toolbox, view) -> list[ToolResult]:
    """What the run's tools produced plus whatever the view cites. The market outlook's evidence that was only made resolvable
    stays in the market outlook's own file."""
    keep = {r.evidence_id for r in toolbox.produced} | {i for r in ((*view.drivers, *view.risks) if view else ()) for i in r.evidence_ids}
    return [r for r in scope.store.results.values() if r.evidence_id in keep]


def _instrument_fallback(run, prev, prev_evidence, inputs, as_of, market_context, gaps, started, facts):
    if prev is not None and prev.view is not None:
        return _finish_instrument(run, carry_forward_instrument(prev, as_of=as_of, inputs=inputs, market_context=market_context, status="partial",
                                                                gaps=gaps, why="the new run failed")), prev_evidence
    out = InstrumentOutlook(status="partial" if started else "insufficient_data", is_first=prev is None, gaps=gaps, **facts)
    return _finish_instrument(run, out), []


def _finish_instrument(run: RunContext, outlook: InstrumentOutlook) -> InstrumentOutlook:
    gaps = list(outlook.gaps)
    for name in (EVIDENCE_PROVENANCE, COMPLIANCE_CONTENT):
        try:
            run.guard(name, ROLE, "report_assembly", views=int(outlook.view is not None))
        except (PolicyDenied, PolicyEscalated) as e:
            gaps.append(Gap(kind="policy_denied", description=e.reason, subject=name))
    status = outlook.status
    if len(gaps) > len(outlook.gaps) and status == "complete":
        status = "partial"
    return outlook.model_copy(update={"gaps": gaps, "status": status, "policy_decisions": run.report_decisions()})
