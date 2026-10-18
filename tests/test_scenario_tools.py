import dataclasses
from datetime import date

import pytest

from rm_dashboard.agents import StubChatModel
from rm_dashboard.scenarios import SEED_SCENARIOS
from rm_dashboard.scenarios.agent import produce_shock_vector
from rm_dashboard.scenarios.store import ScenarioStore
from rm_dashboard.tools import ALLOWLISTS, EvidenceStore, ToolRefused, ToolRegistry

AS_OF = date(2026, 8, 26)
SID = "gulf-deterioration"


@pytest.fixture
def stored(registry, tmp_path):
    store = ScenarioStore(tmp_path)
    scenario = next(s for s in SEED_SCENARIOS if s.scenario_id == SID)
    v, ev = produce_shock_vector(registry, scenario=scenario, as_of=AS_OF, store=store, models=lambda r: StubChatModel(role=r), model_name="stub")
    store.save_vector(v, ev)
    return tmp_path, v


def call(registry, reports, shared=None, scenario_id=SID, as_of=AS_OF, role="scenario_impact"):
    reg = ToolRegistry(dataclasses.replace(registry.ctx, artifacts=reports), registry.specs.values())
    tb = reg.toolbox(role, ALLOWLISTS[role], store=shared or EvidenceStore())
    return tb.call("scenario.vector", {"scenario_id": scenario_id, "as_of": as_of})


def test_the_stored_vector_is_returned_as_conditional_evidence(registry, stored):
    reports, v = stored
    r = call(registry, reports)
    assert r.status == "ok" and r.data["scenario_id"] == SID and r.data["horizon_months"] == 3
    assert [c["channel"] for c in r.data["channels"]] == [c.channel for c in v.channels]
    c = r.data["channels"][0]
    assert {"best_pct", "likely_pct", "worst_pct", "rationale", "evidence_ids", "anchored_event"} <= set(c)
    assert any(f.code == "conditional_scenario" and "not a forecast" in f.message for f in r.flags)


def test_the_evidence_behind_each_move_becomes_resolvable_in_the_run(registry, stored):
    reports, v = stored
    shared = EvidenceStore()
    call(registry, reports, shared)
    assert {i for c in v.channels for i in c.evidence_ids} <= set(shared.results)


def test_no_vector_or_no_folder_is_no_data_with_the_command_to_run(registry, stored, tmp_path):
    reports, _ = stored
    assert call(registry, reports, scenario_id="no-such").status == "no_data"
    r = call(registry, reports, as_of=date(2026, 6, 30))
    assert r.status == "no_data" and "rm-dashboard-scenarios" in r.reason
    reg = ToolRegistry(dataclasses.replace(registry.ctx, artifacts=None), registry.specs.values())
    r = reg.toolbox("scenario_impact", ALLOWLISTS["scenario_impact"]).call("scenario.vector", {"scenario_id": SID, "as_of": AS_OF})
    assert r.status == "no_data" and "no artifact store" in r.reason


def test_only_the_impact_writer_may_read_the_vector(registry):
    assert "scenario.vector" in ALLOWLISTS["scenario_impact"] and "scenario.vector" not in ALLOWLISTS["scenario_analyst"]
    tb = registry.toolbox("scenario_analyst", ALLOWLISTS["scenario_analyst"])
    with pytest.raises(ToolRefused):
        tb.call("scenario.vector", {"scenario_id": SID, "as_of": AS_OF})


def test_the_analyst_cannot_reach_portfolio_or_credit_data():
    assert not {"positions.list", "portfolios.get", "credit.facilities", "analytics.credit_ltv"} & set(ALLOWLISTS["scenario_analyst"])
