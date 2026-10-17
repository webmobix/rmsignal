from datetime import date

import pytest

from rm_dashboard.agents import StubChatModel
from rm_dashboard.scenarios.contracts import CASES
from rm_dashboard.scenarios.impact import compute_impact
from rm_dashboard.scenarios.mapping import PortfolioInputs
from rm_dashboard.scenarios.rollup_agent import produce_client_rollup, produce_rm_rollup
from rm_dashboard.scenarios.rollups import build_client_rollup, build_rm_rollup
from rm_dashboard.scenarios.store import ScenarioStore
from scenario_fixtures import AS_OF, SCENARIO, US_EQ, holding, move, simple_portfolio, vector

V = vector(move("equity_us", 2, -5, -10), move("rates_duration", 1, 0, 1))


def impact(usd=100.0, client="CL-A", pid="PF-A", v=V, facilities=None):
    p = simple_portfolio(**({"facilities": facilities} if facilities is not None else {}))
    p.portfolio.update(portfolio_id=pid, client_id=client)
    k = usd / 100
    p.holdings = [{**h, "portfolio_id": pid, "client_id": client, "market_value_usd": h["market_value_usd"] * k,
                   "market_value_base": h["market_value_base"] * k, "lending_value_base": h["lending_value_base"] * k} for h in p.holdings]
    return compute_impact(p, v, SCENARIO, AS_OF)


def gain(client, pid):
    p = simple_portfolio()
    p.portfolio.update(portfolio_id=pid, client_id=client)
    p.holdings = [{**holding("SYN-EQ-0001", US_EQ, 100, pf=pid), "client_id": client}]
    return compute_impact(p, vector(move("equity_us", 9, 4, 1)), SCENARIO, AS_OF)


def test_client_totals_are_the_sum_of_the_portfolios():
    a, b = impact(100, pid="PF-A"), impact(300, pid="PF-B")
    r = build_client_rollup(SCENARIO, AS_OF, "CL-A", {"PF-A": a, "PF-B": b})
    for k in CASES:
        assert r.cases[k].delta_usd == pytest.approx(a.cases[k].delta_usd + b.cases[k].delta_usd)
        assert r.cases[k].before_usd == 400.0 and r.cases[k].after_usd == pytest.approx(400 + r.cases[k].delta_usd)
    assert r.cases["likely"].delta_pct == pytest.approx(-3.0) and r.status == "complete" and len(r.positions) == 6
    assert r.untouched_count == 2 and r.reached_pct == 90.0
    assert [p.portfolio_id for p in r.portfolios] == ["PF-A", "PF-B"] and r.coverage.computed == 2


def test_client_with_a_missing_portfolio_says_so_and_is_partial():
    r = build_client_rollup(SCENARIO, AS_OF, "CL-A", {"PF-A": impact(), "PF-B": None})
    assert r.status == "partial" and r.coverage.missing == ["PF-B"] and r.coverage.computed == 1 and r.coverage.total == 2
    assert "PF-B" in r.gaps[0].description


def test_client_without_any_result_has_no_figures():
    r = build_client_rollup(SCENARIO, AS_OF, "CL-A", {"PF-A": None})
    assert r.status == "insufficient_data" and r.cases == {}


def test_rm_roll_up_ranks_by_worst_case_loss_and_lists_beneficiaries():
    clients = {c: build_client_rollup(SCENARIO, AS_OF, c, {f"PF-{c}": i}) for c, i in
               {"CL-1": impact(100, "CL-1", "PF-CL-1"), "CL-2": impact(500, "CL-2", "PF-CL-2"), "CL-3": gain("CL-3", "PF-CL-3")}.items()}
    r = build_rm_rollup(SCENARIO, AS_OF, "RM-1", clients)
    assert [c.client_id for c in r.most_hit] == ["CL-2", "CL-1", "CL-3"]
    assert r.most_hit[0].cases["worst"].delta_usd == pytest.approx(-28.5) and r.most_hit[0].cases["worst"].delta_pct == pytest.approx(-5.7)
    assert [c.client_id for c in r.beneficiaries] == ["CL-3"]
    assert r.cases["likely"].delta_usd == pytest.approx(sum(c.cases["likely"].delta_usd for c in clients.values()))
    assert r.coverage.computed == 3 and r.status == "complete" and r.rm_id == "RM-1"


def test_rm_roll_up_lists_each_crossing_with_client_facility_and_case():
    clients = {"CL-1": build_client_rollup(SCENARIO, AS_OF, "CL-1", {"PF-1": impact(100, "CL-1", "PF-1")})}
    r = build_rm_rollup(SCENARIO, AS_OF, "RM-1", clients)
    ltv = [x for x in r.crossings if x.kind == "ltv"]
    assert [(x.client_id, x.label, x.case) for x in ltv] == [("CL-1", "CF-T", "worst")] and "trigger" in ltv[0].detail
    band = [x for x in r.crossings if x.kind == "band"]
    assert band and band[0].label == "Fixed Income" and band[0].case == "worst" and band[0].portfolio_id == "PF-1"


def test_rm_roll_up_is_honest_about_coverage():
    clients = {f"CL-{n}": build_client_rollup(SCENARIO, AS_OF, f"CL-{n}", {f"PF-{n}": impact(100, f"CL-{n}", f"PF-{n}")}) for n in range(1, 18)}
    clients.update({f"CL-{n}": None for n in range(18, 21)})
    r = build_rm_rollup(SCENARIO, AS_OF, "RM-1", clients)
    assert (r.coverage.computed, r.coverage.total) == (17, 20) and r.coverage.missing == ["CL-18", "CL-19", "CL-20"]
    assert r.status == "partial" and "17 of 20 clients covered" in r.gaps[0].description and "17 of 20" in r.summary


def test_rm_roll_up_without_any_client_has_no_figures():
    assert build_rm_rollup(SCENARIO, AS_OF, "RM-1", {"CL-1": None}).status == "insufficient_data"


# ---- summaries ------------------------------------------------------------------------------------
def models(mode="normal"):
    return lambda role: StubChatModel(role=role, mode=mode)


def test_client_summary_from_the_agent_when_its_figures_match(registry, tmp_path):
    members = {"PF-A": impact(100, pid="PF-A"), "PF-B": impact(300, pid="PF-B")}
    r = produce_client_rollup(registry, scenario=SCENARIO, as_of=AS_OF, client_id="CL-A", impacts=members, store=ScenarioStore(tmp_path),
                              models=models(), model_name="stub")
    assert r.summary.startswith("Under the scenario the likely case is a loss of 3.0%") and r.status == "complete" and r.inputs_hash


def test_client_summary_with_a_wrong_figure_falls_back_to_code(registry, tmp_path):
    r = produce_client_rollup(registry, scenario=SCENARIO, as_of=AS_OF, client_id="CL-A", impacts={"PF-A": impact()}, store=ScenarioStore(tmp_path),
                              models=models("bad_figure"), model_name="stub")
    assert r.summary.startswith("Under Test scenario") and "77.7" not in r.summary
    assert r.status == "partial" and any(g.kind == "guard_removed" for g in r.gaps)


def test_rm_summary_with_a_wrong_book_total_uses_the_code_built_summary(registry, tmp_path):
    clients = {"CL-1": build_client_rollup(SCENARIO, AS_OF, "CL-1", {"PF-1": impact(100, "CL-1", "PF-1")})}
    ok = produce_rm_rollup(registry, scenario=SCENARIO, as_of=AS_OF, rm_id="RM-1", clients=clients, store=ScenarioStore(tmp_path), models=models(),
                           model_name="stub")
    bad = produce_rm_rollup(registry, scenario=SCENARIO, as_of=AS_OF, rm_id="RM-1", clients=clients, store=ScenarioStore(tmp_path),
                            models=models("bad_figure"), model_name="stub")
    assert ok.summary.startswith("Under the scenario") and bad.summary.startswith("Under Test scenario") and bad.status == "partial"
    assert bad.cases == ok.cases


def test_a_failing_model_keeps_the_aggregates(registry, tmp_path):
    clients = {"CL-1": build_client_rollup(SCENARIO, AS_OF, "CL-1", {"PF-1": impact(100, "CL-1", "PF-1")})}
    r = produce_rm_rollup(registry, scenario=SCENARIO, as_of=AS_OF, rm_id="RM-1", clients=clients, store=ScenarioStore(tmp_path),
                          models=models("raise"), model_name="stub")
    assert r.cases["likely"].delta_usd == pytest.approx(-3.0) and r.summary and any(g.kind == "agent_error" for g in r.gaps)
