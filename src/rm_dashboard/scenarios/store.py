"""Where scenario results live, per date and scenario. Other dates and scenarios are never touched.

    scenario-vector   <scenario_id>                 the shock vector        (evidence: scenario-vector/<scenario_id>)
    scenario-impact   <scenario_id>/<portfolio_id>  portfolio impacts       (evidence: scenario-impact/<scenario_id>/<portfolio_id>)
    scenario-client   <scenario_id>/<client_id>     client roll-ups
    scenario-rollup   <scenario_id>                 the RM book roll-up
"""

from datetime import date
from pathlib import Path

from rm_dashboard.domain import ToolResult
from rm_dashboard.store import ArtifactStore, Kind, as_store, read_model
from rm_dashboard.store import evidence as ev

from .contracts import ClientRollup, PortfolioImpact, RMRollup, ShockVector


class ScenarioStore:
    def __init__(self, store: ArtifactStore | str | Path):
        self.store = as_store(store)

    # ---- reading ------------------------------------------------------------------------
    def load_vector(self, as_of: date, scenario_id: str) -> ShockVector | None:
        return read_model(self.store, as_of, Kind.SCENARIO_VECTOR, scenario_id, ShockVector)

    def load_vector_evidence(self, as_of: date, scenario_id: str) -> list[ToolResult]:
        return ev.get_evidence(self.store, as_of, ev.SCENARIO_VECTOR, scenario_id) or []

    def load_impact(self, as_of: date, scenario_id: str, portfolio_id: str) -> PortfolioImpact | None:
        return read_model(self.store, as_of, Kind.SCENARIO_IMPACT, f"{scenario_id}/{portfolio_id}", PortfolioImpact)

    def load_impact_evidence(self, as_of: date, scenario_id: str, portfolio_id: str) -> list[ToolResult]:
        return ev.get_evidence(self.store, as_of, ev.SCENARIO_IMPACT, f"{scenario_id}/{portfolio_id}") or []

    def load_client(self, as_of: date, scenario_id: str, client_id: str) -> ClientRollup | None:
        return read_model(self.store, as_of, Kind.SCENARIO_CLIENT, f"{scenario_id}/{client_id}", ClientRollup)

    def load_rollup(self, as_of: date, scenario_id: str) -> RMRollup | None:
        return read_model(self.store, as_of, Kind.SCENARIO_ROLLUP, scenario_id, RMRollup)

    def scenario_ids(self, as_of: date) -> list[str]:
        ids = set(self.store.keys(as_of, Kind.SCENARIO_VECTOR)) | set(self.store.keys(as_of, Kind.SCENARIO_ROLLUP))
        for kind in (Kind.SCENARIO_IMPACT, Kind.SCENARIO_CLIENT):
            ids |= {k.split("/", 1)[0] for k in self.store.keys(as_of, kind)}
        return sorted(ids)

    # ---- writing: evidence first, the result last, so a reader never sees a result whose evidence is missing ---------------
    def save_vector(self, vector: ShockVector, evidence: list[ToolResult]) -> None:
        ev.put_evidence(self.store, vector.as_of, ev.SCENARIO_VECTOR, vector.scenario_id, evidence)
        self.store.put(vector.as_of, Kind.SCENARIO_VECTOR, vector.scenario_id, vector.model_dump_json(indent=2))

    def save_impact(self, impact: PortfolioImpact, evidence: list[ToolResult] | None = None) -> None:
        key = f"{impact.scenario_id}/{impact.portfolio_id}"
        if evidence:
            ev.put_evidence(self.store, impact.as_of, ev.SCENARIO_IMPACT, key, evidence)
        self.store.put(impact.as_of, Kind.SCENARIO_IMPACT, key, impact.model_dump_json(indent=2))

    def save_client(self, rollup: ClientRollup) -> None:
        self.store.put(rollup.as_of, Kind.SCENARIO_CLIENT, f"{rollup.scenario_id}/{rollup.client_id}", rollup.model_dump_json(indent=2))

    def save_rollup(self, rollup: RMRollup) -> None:
        self.store.put(rollup.as_of, Kind.SCENARIO_ROLLUP, rollup.scenario_id, rollup.model_dump_json(indent=2))
