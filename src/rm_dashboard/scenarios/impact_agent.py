"""Layer B: the impact of one scenario on one portfolio. Code computes every figure; an agent places holdings the rules cannot
place and writes the summary."""

import dataclasses
from datetime import date

from rm_dashboard.agents.analyst import ModelFactory
from rm_dashboard.agents.scope import RunScope
from rm_dashboard.domain import Gap, ToolResult
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyDenied, PolicyEngine, PolicyEscalated, RunContext
from rm_dashboard.policy.engine import COMPLIANCE_CONTENT, EVIDENCE_PROVENANCE
from rm_dashboard.tools import ToolRegistry

from .channels import vocabulary
from .contracts import AgentMapping, PortfolioImpact, ScenarioRecord
from .impact import ambiguous_holdings, compute_impact, summary_figures
from .inputs import holdings_fingerprint, impact_inputs_hash, load_portfolio_inputs
from .store import ScenarioStore
from .writer import ROLE, Writer, header_for


def current_hash(inputs, vector, model: str) -> str:
    """The hash an impact made now would carry. It includes the vector's inputs (scenario text, data) and its content: an edited scenario or a
    regenerated vector that says something else regenerates the impact."""
    chain = f"{vector.inputs_hash}:{vector.vector_hash}" if vector else ""
    return impact_inputs_hash(vector_hash=chain, holdings=holdings_fingerprint(inputs), model=model)


def produce_portfolio_impact(registry: ToolRegistry, *, scenario: ScenarioRecord, portfolio_id: str, as_of: date, store: ScenarioStore,
                             models: ModelFactory, model_name: str = "", engine: PolicyEngine | None = None,
                             audit: AuditLog | None = None) -> tuple[PortfolioImpact, list[ToolResult]]:
    """The impact of ``scenario`` on ``portfolio_id`` and the evidence behind its prose. Always returns an impact: the figures come
    from code, so a model failure costs the prose and the placement of unmapped holdings, never the numbers."""
    registry = ToolRegistry(dataclasses.replace(registry.ctx, reports_dir=store.base_dir), registry.specs.values())
    run = RunContext(portfolio_id, as_of, engine=engine or MockPolicyEngine(), audit=audit or AuditLog())
    inputs = load_portfolio_inputs(registry.ctx.repo, as_of, portfolio_id)
    vector = store.load_vector(as_of, scenario.scenario_id)
    if inputs is None:
        return _finish(run, PortfolioImpact(scenario_id=scenario.scenario_id, portfolio_id=portfolio_id, client_id="", as_of=as_of,
                                            status="insufficient_data", horizon_months=scenario.horizon_months,
                                            gaps=[Gap(kind="no_data", subject=portfolio_id, description=f"portfolio {portfolio_id} not found at {as_of}")])), []
    ihash = current_hash(inputs, vector, model_name)
    kw = dict(inputs_hash=ihash, vector_hash=vector.vector_hash if vector else "")
    impact = compute_impact(inputs, vector, scenario, as_of, **kw)
    impact = impact.model_copy(update={"model": model_name})
    scope = RunScope(run=run, registry=registry)
    gaps: list[Gap] = []
    evidence: list[ToolResult] = []
    try:
        run.run_start(ROLE)
    except (PolicyDenied, PolicyEscalated) as e:  # not entitled: no figures are delivered
        return _finish(run, PortfolioImpact(scenario_id=scenario.scenario_id, portfolio_id=portfolio_id, client_id=inputs.portfolio["client_id"],
                                            as_of=as_of, status="insufficient_data", horizon_months=scenario.horizon_months, model=model_name,
                                            gaps=[Gap(kind="policy_denied", description=e.reason, subject=ROLE)], **kw)), []
    try:
        if impact.status == "insufficient_data":
            return _finish(run, impact), []
        writer = Writer(scope, models)
        subject = f"Portfolio {portfolio_id}."
        header = header_for(scenario.name, scenario.premise, scenario.horizon_months, as_of, subject)
        ambiguous = ambiguous_holdings(inputs)
        if ambiguous:
            channels = vocabulary(list(inputs.instruments.values()))
            accepted, verdicts, mgaps = writer.mappings(header, ambiguous, channels, [c.channel for c in vector.channels])
            gaps += mgaps
            if verdicts or accepted:
                impact = compute_impact(inputs, vector, scenario, as_of, agent_channels=accepted,
                                        agent_mappings=[AgentMapping(**v) for v in verdicts], **kw).model_copy(update={"model": model_name})
        likely = impact.cases["likely"].delta_usd
        summary, sgaps = writer.summary("summary", header, summary_figures(impact), impact.summary, direction=likely)
        gaps += sgaps
        impact = impact.model_copy(update={"summary": summary})
        evidence = list(scope.store.results.values())
    except (PolicyDenied, PolicyEscalated) as e:
        gaps.append(Gap(kind="policy_denied", description=e.reason, subject=ROLE))
    except Exception as e:  # noqa: BLE001 - always delivered: nothing escapes as an unhandled error
        gaps.append(Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE))
    gaps = [*scope.gaps, *gaps]
    status = "partial" if (gaps or impact.gaps) and impact.status == "complete" else impact.status
    impact = impact.model_copy(update={"gaps": [*impact.gaps, *gaps], "status": status,
                                       "evidence_ids": sorted(e.evidence_id for e in evidence)})
    return _finish(run, impact), evidence


def _finish(run: RunContext, impact: PortfolioImpact) -> PortfolioImpact:
    gaps = list(impact.gaps)
    for name in (EVIDENCE_PROVENANCE, COMPLIANCE_CONTENT):
        try:
            run.guard(name, ROLE, "report_assembly", positions=len(impact.positions))
        except (PolicyDenied, PolicyEscalated) as e:
            gaps.append(Gap(kind="policy_denied", description=e.reason, subject=name))
    status = impact.status
    if len(gaps) > len(impact.gaps) and status == "complete":
        status = "partial"
    return impact.model_copy(update={"gaps": gaps, "status": status, "policy_decisions": run.report_decisions()})
