"""Scenario tools: read the stored shock vector of a scenario. They never start a scenario run."""

from rm_dashboard.domain import QualityFlag
from rm_dashboard.scenarios.store import ScenarioStore

from .envelope import build_result
from .spec import Params, ToolContext, ToolSpec

CONDITIONAL = "conditional_scenario"
NO_FOLDER = "no reports folder is configured: the shock vector cannot be read"
NO_VECTOR = "no shock vector exists for scenario {id} on {as_of}; run rm-dashboard-scenarios"


class ScenarioParams(Params):
    scenario_id: str


def scenario_vector(ctx: ToolContext, p: ScenarioParams):
    """The market shock vector of a scenario at the run's date, as the evidence for what a channel does under it."""
    store = ScenarioStore(ctx.reports_dir) if ctx.reports_dir else None
    v = store.load_vector(p.as_of, p.scenario_id) if store else None
    if v is None or not v.channels:
        return build_result(tool="scenario.vector", version="1", params=p, as_of=p.as_of, data=None, status="no_data",
                            reason=NO_FOLDER if store is None else NO_VECTOR.format(id=p.scenario_id, as_of=p.as_of))
    if ctx.store is not None:  # the evidence behind each channel move becomes resolvable in this run
        for e in store.load_vector_evidence(p.as_of, p.scenario_id):
            ctx.store.add(e)
    flag = QualityFlag(code=CONDITIONAL, message=f"shock vector of {p.scenario_id} over {v.horizon_months} months: conditional on the "
                                                  "scenario, a central case and its brackets, not a forecast or a probability")
    data = {"scenario_id": v.scenario_id, "horizon_months": v.horizon_months, "status": v.status, "summary": v.summary,
            "channels": [{"channel": c.channel, "best_pct": c.best, "likely_pct": c.likely, "worst_pct": c.worst, "rationale": c.rationale,
                          "evidence_ids": c.evidence_ids, "anchored_event": c.anchored_event.event_id if c.anchored_event else None}
                         for c in v.channels]}
    return build_result(tool="scenario.vector", version="1", params=p, as_of=p.as_of, data=data, extra_flags=[flag])


SCENARIO_TOOLS = [
    ToolSpec("scenario.vector", "The stored market shock vector of a scenario for the run's date: best, likely and worst move per channel.",
             ScenarioParams, scenario_vector, "scenario"),
]
