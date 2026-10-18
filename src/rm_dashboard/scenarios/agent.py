"""Layer A: the scenario analyst. One agent run per scenario and date turns the scenario text and point-in-time evidence into a
shock vector; code decides which moves survive."""

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

from .catalogue import scenario_hash
from .channels import Channel, vocabulary
from .contracts import NOT_A_PROBABILITY, ScenarioRecord, ShockVector
from .guard import VectorGuardInput, guard_vector
from .inputs import data_fingerprint, digest, vector_inputs_hash
from .store import ScenarioStore

ROLE = "scenario_analyst"
SPEC = AnalystSpec(ROLE, "scenario", r"[a-z0-9][a-z0-9-]*", prompts.SCENARIO_ANALYST, ALLOWLISTS[ROLE], (),
                   "Turns a scenario text and point-in-time market evidence into best, likely and worst moves per market channel.")


def request_text(scenario: ScenarioRecord, as_of: date, channels: list[Channel]) -> str:
    lines = [f"Produce the shock vector of scenario {scenario.scenario_id} ({scenario.name}) as of {as_of.isoformat()}.",
             f"Horizon: {scenario.horizon_months} months.", f"Premise: {scenario.premise}"]
    if scenario.mirrors:
        lines.append(f"It mirrors: {scenario.mirrors}")
    lines.append("Give a best, likely and worst move in percent for every channel:")
    lines += [f"- {c.channel} [{c.kind}]: {c.label}" for c in channels]
    return "\n".join(lines)


def current_hash(repo, scenario: ScenarioRecord, as_of: date, model: str) -> str:
    """The hash a vector made now would carry: stored vectors with this hash are current."""
    return vector_inputs_hash(scenario_hash=scenario_hash(scenario), data=data_fingerprint(repo, as_of), model=model)


def vector_hash(channels) -> str:
    """Of the content, not the inputs: a regenerated vector that says the same leaves its impacts current."""
    return digest([(c.channel, c.best, c.likely, c.worst) for c in sorted(channels, key=lambda c: c.channel)])


def produce_shock_vector(registry: ToolRegistry, *, scenario: ScenarioRecord, as_of: date, store: ScenarioStore, models: ModelFactory,
                         model_name: str = "", engine: PolicyEngine | None = None,
                         audit: AuditLog | None = None) -> tuple[ShockVector, list[ToolResult]]:
    """The vector of ``scenario`` at ``as_of`` and the evidence it rests on. Always returns a vector; failures become gaps."""
    registry = ToolRegistry(dataclasses.replace(registry.ctx, artifacts=store.store), registry.specs.values())
    run = RunContext(scenario.scenario_id, as_of, engine=engine or MockPolicyEngine(), audit=audit or AuditLog())
    repo = registry.ctx.repo
    inputs_hash = current_hash(repo, scenario, as_of, model_name)
    base = dict(scenario_id=scenario.scenario_id, as_of=as_of, horizon_months=scenario.horizon_months, inputs_hash=inputs_hash, model=model_name)
    market = repo.market_context(as_of=as_of)
    instruments = repo.instruments(as_of=as_of).frame.to_dicts()
    channels = vocabulary(instruments)
    gaps: list[Gap] = []
    scope = RunScope(run=run, registry=registry)
    started = False
    try:
        run.run_start(ROLE)
        started = True
        if market.status != "ok" or not channels:
            why = market.reason or "no market data at as_of" if market.status != "ok" else "no instrument in the data reaches a channel"
            return _finish(run, ShockVector(status="insufficient_data", gaps=[Gap(kind="no_data", description=why, subject="market_context")], **base)), []
        agent, _ = build_agent(SPEC, scope, models)
        raw: list = []
        summary = ""
        try:
            result = agent.invoke({"messages": [HumanMessage(content=request_text(scenario, as_of, channels))]},
                                  config={"recursion_limit": RECURSION_LIMIT, **llm_config(run, SPEC.name)})
            obj, err = parse_json_object(_final_text(result))
            if err:
                gaps.append(Gap(kind="agent_error", description=err, subject=ROLE))
            else:
                raw = obj.get("channels") if isinstance(obj.get("channels"), list) else []
                summary = obj.get("summary") if isinstance(obj.get("summary"), str) else ""
                if not raw:
                    gaps.append(Gap(kind="agent_error", description="the model's answer had no channels list", subject=ROLE))
        except (PolicyDenied, PolicyEscalated):
            raise
        except Exception as e:  # noqa: BLE001 - always delivered: nothing escapes as an unhandled error
            gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
        g = VectorGuardInput(store=scope.store, as_of=as_of, channels=[c.channel for c in channels], horizon_months=scenario.horizon_months,
                             instrument_names={str(i["instrument_name"]).lower() for i in instruments})
        out = guard_vector(raw, summary, g)
        gaps = [*scope.gaps, *gaps, *out.gaps]
        evidence = list(scope.store.results.values())
        keep = {i for c in out.channels for i in c.evidence_ids}
        evidence = [e for e in evidence if e.evidence_id in keep]
        status = "insufficient_data" if not out.channels else "partial" if gaps else "complete"
        vector = ShockVector(status=status, summary=out.summary or _built_summary(scenario, out.channels), channels=out.channels, gaps=gaps,
                             evidence_ids=sorted(e.evidence_id for e in evidence), vector_hash=vector_hash(out.channels), **base)
        return _finish(run, vector), evidence
    except (PolicyDenied, PolicyEscalated) as e:
        gaps.append(Gap(kind="policy_denied", description=e.reason, subject=ROLE))
    except Exception as e:  # noqa: BLE001
        gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
    return _finish(run, ShockVector(status="insufficient_data", gaps=gaps, **base)), []


def _built_summary(scenario: ScenarioRecord, channels) -> str:
    if not channels:
        return ""
    return (f"Under {scenario.name}, {len(channels)} market channel(s) are given a best, likely and worst move over "
            f"{scenario.horizon_months} months. {NOT_A_PROBABILITY}")


def _finish(run: RunContext, vector: ShockVector) -> ShockVector:
    gaps = list(vector.gaps)
    for name in (EVIDENCE_PROVENANCE, COMPLIANCE_CONTENT):
        try:
            run.guard(name, ROLE, "report_assembly", channels=len(vector.channels))
        except (PolicyDenied, PolicyEscalated) as e:
            gaps.append(Gap(kind="policy_denied", description=e.reason, subject=name))
    status = vector.status
    if len(gaps) > len(vector.gaps) and status == "complete":
        status = "partial"
    return vector.model_copy(update={"gaps": gaps, "status": status, "policy_decisions": run.report_decisions()})
