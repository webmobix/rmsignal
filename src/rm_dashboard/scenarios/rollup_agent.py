"""The summaries of client and RM-book roll-ups: aggregates by code, then one short agent call checked against the aggregates."""

import dataclasses
from datetime import date

from rm_dashboard.agents.analyst import ModelFactory
from rm_dashboard.agents.scope import RunScope
from rm_dashboard.domain import Gap
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyDenied, PolicyEngine, PolicyEscalated, RunContext
from rm_dashboard.tools import ToolRegistry

from .contracts import ClientRollup, PortfolioImpact, RMRollup, ScenarioRecord
from .inputs import rollup_inputs_hash
from .rollups import build_client_rollup, build_rm_rollup, client_figures, rm_figures
from .store import ScenarioStore
from .writer import ROLE, Writer, header_for


def _summarise(registry: ToolRegistry, store: ScenarioStore, models: ModelFactory, *, subject: str, as_of: date, task: str, header: str,
               figures: dict, fallback: str, direction: float, engine: PolicyEngine | None, audit: AuditLog | None) -> tuple[str, list[Gap]]:
    registry = ToolRegistry(dataclasses.replace(registry.ctx, artifacts=store.store), registry.specs.values())
    run = RunContext(subject, as_of, engine=engine or MockPolicyEngine(), audit=audit or AuditLog())
    try:
        run.run_start(ROLE)
        writer = Writer(RunScope(run=run, registry=registry), models)
        return writer.summary(task, header, figures, fallback, direction=direction)
    except (PolicyDenied, PolicyEscalated) as e:
        return fallback, [Gap(kind="policy_denied", description=e.reason, subject=ROLE)]
    except Exception as e:  # noqa: BLE001 - always delivered
        return fallback, [Gap(kind="agent_error", description=f"{type(e).__name__}: {e}", subject=ROLE)]


def _with(rollup, summary: str, gaps: list[Gap]):
    status = "partial" if gaps and rollup.status == "complete" else rollup.status
    return rollup.model_copy(update={"summary": summary, "gaps": [*rollup.gaps, *gaps], "status": status})


def produce_client_rollup(registry: ToolRegistry, *, scenario: ScenarioRecord, as_of: date, client_id: str, impacts: dict[str, PortfolioImpact | None],
                          store: ScenarioStore, models: ModelFactory, names: dict[str, str] | None = None, model_name: str = "",
                          engine: PolicyEngine | None = None, audit: AuditLog | None = None) -> ClientRollup:
    ihash = rollup_inputs_hash(member_hashes=[i.inputs_hash for i in impacts.values() if i is not None], model=model_name)
    r = build_client_rollup(scenario, as_of, client_id, impacts, names, inputs_hash=ihash, model=model_name)
    if r.status == "insufficient_data":
        return r
    header = header_for(scenario.name, scenario.premise, scenario.horizon_months, as_of, f"Client {client_id}, {r.coverage.computed} portfolio(s).")
    summary, gaps = _summarise(registry, store, models, subject=client_id, as_of=as_of, task="client_summary", header=header,
                               figures=client_figures(r), fallback=r.summary, direction=r.cases["likely"].delta_usd, engine=engine, audit=audit)
    return _with(r, summary, gaps)


def produce_rm_rollup(registry: ToolRegistry, *, scenario: ScenarioRecord, as_of: date, rm_id: str | None, clients: dict[str, ClientRollup | None],
                      store: ScenarioStore, models: ModelFactory, model_name: str = "", engine: PolicyEngine | None = None,
                      audit: AuditLog | None = None) -> RMRollup:
    ihash = rollup_inputs_hash(member_hashes=[c.inputs_hash for c in clients.values() if c is not None], model=model_name)
    r = build_rm_rollup(scenario, as_of, rm_id, clients, inputs_hash=ihash, model=model_name)
    if r.status == "insufficient_data":
        return r
    header = header_for(scenario.name, scenario.premise, scenario.horizon_months, as_of, f"RM book {rm_id or ''}: {r.coverage.computed} of {r.coverage.total} clients.")
    summary, gaps = _summarise(registry, store, models, subject=rm_id or "RM", as_of=as_of, task="rm_summary", header=header,
                               figures=rm_figures(r), fallback=r.summary, direction=r.cases["likely"].delta_usd, engine=engine, audit=audit)
    return _with(r, summary, gaps)
