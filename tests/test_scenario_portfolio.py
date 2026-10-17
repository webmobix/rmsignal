"""The portfolio impact end to end on the seeded data with the stub model."""

from datetime import date

import pytest
from langchain_core.messages import AIMessage

from rm_dashboard.agents import StubChatModel
from rm_dashboard.policy import ScriptedEngine
from rm_dashboard.scenarios import SEED_SCENARIOS
from rm_dashboard.scenarios.agent import produce_shock_vector
from rm_dashboard.scenarios.impact_agent import produce_portfolio_impact
from rm_dashboard.scenarios.store import ScenarioStore

AS_OF = date(2026, 8, 26)
SCENARIO = next(s for s in SEED_SCENARIOS if s.scenario_id == "gulf-deterioration")


def models(vector_mode="normal", impact_mode="normal"):
    return lambda role: StubChatModel(role=role, mode=vector_mode if role == "scenario_analyst" else impact_mode)


@pytest.fixture
def store(registry, tmp_path):
    s = ScenarioStore(tmp_path)
    v, ev = produce_shock_vector(registry, scenario=SCENARIO, as_of=AS_OF, store=s, models=models(), model_name="stub")
    s.save_vector(v, ev)
    return s


def impact(registry, store, pid="PF-0003", mode="normal", **kw):
    return produce_portfolio_impact(registry, scenario=SCENARIO, portfolio_id=pid, as_of=AS_OF, store=store, models=models(impact_mode=mode),
                                    model_name="stub", **kw)


def test_a_portfolio_gets_three_computed_cases_with_agent_prose(registry, store):
    i, _ = impact(registry, store)
    assert set(i.cases) == {"best", "likely", "worst"} and i.before_usd > 0
    assert i.cases["worst"].after_usd <= i.cases["likely"].after_usd <= i.cases["best"].after_usd
    assert i.summary.startswith("Under the scenario the likely case is a") and "not probabilities" in i.summary
    assert i.positions and i.position_count == len(i.positions) and i.explainers["likely"] and i.client_id == "CL-0002"
    assert i.vector_hash and i.inputs_hash and i.model == "stub"


def test_every_figure_is_computed_not_modelled(registry, store):
    i, _ = impact(registry, store)
    assert i.cases["likely"].delta_usd == pytest.approx(sum(p.moves["likely"].delta_usd for p in i.positions), abs=0.05)
    assert i.cases["likely"].delta_pct == pytest.approx(i.cases["likely"].delta_usd / i.before_usd * 100, abs=1e-3)


def test_ambiguous_holdings_are_placed_by_the_agent_and_marked(registry, store):
    pid = next(p for p in (f"PF-{n:04d}" for n in range(1, 25)) if any(
        "agent" == x.mapping for x in impact(registry, store, p)[0].positions))
    i, _ = impact(registry, store, pid)
    placed = [p for p in i.positions if p.mapping == "agent"]
    assert placed and all(c.agent_assigned for p in placed for c in p.channels if not c.channel.startswith("fx_"))
    assert i.agent_mappings and all(m.accepted for m in i.agent_mappings)


def test_a_proposal_outside_the_vector_is_dropped_with_a_gap(registry, store):
    pid = next(p for p in (f"PF-{n:04d}" for n in range(1, 25)) if impact(registry, store, p)[0].agent_mappings)
    i, _ = impact(registry, store, pid, mode="bad_channel")
    assert not any(p.mapping == "agent" for p in i.positions) and i.agent_mappings and not any(m.accepted for m in i.agent_mappings)
    assert any("not market or overlay channels" in g.description for g in i.gaps) and i.status == "partial"


def test_a_summary_with_a_wrong_figure_is_replaced_by_the_code_built_one(registry, store):
    i, _ = impact(registry, store, mode="bad_figure")
    assert "77.7" not in i.summary and i.summary.startswith("Under Gulf deterioration")
    assert any(g.kind == "guard_removed" and g.subject == "summary" for g in i.gaps) and i.status == "partial"


def test_a_summary_that_calls_a_loss_a_gain_is_replaced(registry, store):
    i, _ = impact(registry, store, mode="wrong_sign")
    assert i.summary.startswith("Under Gulf deterioration") and any("describes a" in g.description for g in i.gaps)


def test_model_failure_costs_the_prose_not_the_figures(registry, store):
    good, _ = impact(registry, store)
    bad, _ = impact(registry, store, mode="raise")
    assert bad.cases["likely"].delta_usd == good.cases["likely"].delta_usd and bad.summary.startswith("Under Gulf deterioration")
    assert bad.status == "partial" and any(g.kind == "agent_error" for g in bad.gaps)


def test_without_a_vector_there_are_no_figures(registry, tmp_path):
    i, _ = impact(registry, ScenarioStore(tmp_path))
    assert i.status == "insufficient_data" and i.cases == {} and i.positions == [] and i.gaps


def test_an_unknown_portfolio_is_insufficient_data(registry, store):
    i, _ = impact(registry, store, "PF-9999")
    assert i.status == "insufficient_data" and "not found" in i.gaps[0].description


def test_a_policy_denial_delivers_no_figures(registry, store):
    i, _ = impact(registry, store, engine=ScriptedEngine({"request_entitlement": "deny"}))
    assert i.status == "insufficient_data" and i.cases == {} and i.gaps[0].kind == "policy_denied"


def test_a_changed_vector_changes_the_impact_hash(registry, store):
    a, _ = impact(registry, store)
    v = store.load_vector(AS_OF, SCENARIO.scenario_id)
    store.save_vector(v.model_copy(update={"vector_hash": "changed"}), [])
    b, _ = impact(registry, store)
    assert a.inputs_hash != b.inputs_hash
