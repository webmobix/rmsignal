import pytest

from rm_dashboard.scenarios.impact import ambiguous_holdings, compute_impact
from rm_dashboard.scenarios.mapping import PortfolioInputs, map_holdings
from scenario_fixtures import (
    ALL, AS_OF, BASKET, CASH, ENERGY, HEDGE, SCENARIO, US_EQ, holding, move, simple_portfolio, vector,
)

V = vector(move("equity_us", 2, -5, -10), move("rates_duration", 1, 0, 1))


def impact(inputs=None, v=V, **kw):
    return compute_impact(inputs or simple_portfolio(), v, SCENARIO, AS_OF, **kw)


def test_three_cases_bracket_the_central_case():
    i = impact()
    assert i.status == "complete" and not i.gaps
    assert i.before_usd == 100.0
    assert i.cases["likely"].after_usd == 97.0 and i.cases["likely"].delta_usd == -3.0 and i.cases["likely"].delta_pct == -3.0
    assert i.cases["worst"].delta_usd == -5.7 and i.cases["best"].delta_usd == 1.5
    assert i.cases["worst"].after_usd <= i.cases["likely"].after_usd <= i.cases["best"].after_usd
    for k in ("best", "likely", "worst"):
        assert i.cases[k].after_usd == pytest.approx(i.before_usd + i.cases[k].delta_usd)


def test_untouched_cash_is_counted_and_excluded_from_the_reached_share():
    i = impact()
    cash = next(p for p in i.positions if p.instrument_id == "SYN-CA-0001")
    assert cash.mapping == "untouched" and cash.moves["worst"].move_pct == 0 and cash.channels == []
    assert i.untouched_count == 1 and i.reached_pct == 90.0 and i.position_count == 3


def test_per_position_moves_list_their_channels_and_weights():
    i = impact()
    eq = next(p for p in i.positions if p.instrument_id == "SYN-EQ-0001")
    assert eq.weight_pct == 60.0 and eq.moves["likely"].move_pct == -5 and eq.moves["likely"].delta_usd == -3.0
    assert [(c.channel, c.likely_pct) for c in eq.channels] == [("equity_us", -5)]


def test_channels_are_additive_for_one_holding():
    inputs = PortfolioInputs(simple_portfolio().portfolio, [holding("SYN-EQ-0100", ENERGY, 100)], ALL)
    v = vector(move("equity_asia", 4, -2, -6), move("sector_energy", 6, 3, -1), move("fx_idr", 0, -1, -3))
    p = impact(inputs, v).positions[0]
    assert {c.channel for c in p.channels} == {"equity_asia", "sector_energy", "fx_idr"}
    assert p.moves["likely"].move_pct == pytest.approx(-2 + 3 - 1) and p.moves["worst"].move_pct == pytest.approx(-6 - 1 - 3)
    assert p.moves["best"].delta_usd == pytest.approx(10.0)


def test_structured_product_follows_its_underlyings_not_a_single_forecast():
    inputs = PortfolioInputs(simple_portfolio().portfolio, [holding("SYN-SP-0001", BASKET, 100)], ALL)
    v = vector(move("equity_asia", 0, -2, -4), move("sector_energy", 4, 2, 0), move("equity_us", 10, 6, 2), move("sector_technology", 0, 0, 0))
    p = impact(inputs, v).positions[0]
    assert p.mapping == "look_through"
    # half the note reaches Indonesian energy (asia + energy overlay), half US tech (us + technology overlay): likely = .5*(-2+2) + .5*(6+0)
    assert p.moves["likely"].move_pct == pytest.approx(3.0)
    assert {c.channel for c in p.channels} == {"equity_asia", "sector_energy", "equity_us", "sector_technology"}


def test_an_ambiguous_holding_is_untouched_with_a_gap_until_an_agent_places_it():
    inputs = PortfolioInputs(simple_portfolio().portfolio, [holding("SYN-EQ-0001", US_EQ, 50), holding("SYN-AL-0001", HEDGE, 50)], ALL)
    assert [a.instrument_id for a in ambiguous_holdings(inputs)] == ["SYN-AL-0001"]
    i = impact(inputs)
    hedge = next(p for p in i.positions if p.instrument_id == "SYN-AL-0001")
    assert hedge.mapping == "untouched" and any("SYN-AL-0001" in g.description for g in i.gaps) and i.status == "partial"
    placed = impact(inputs, agent_channels={"SYN-AL-0001": [("equity_us", "behaves like US equity")]})
    hedge = next(p for p in placed.positions if p.instrument_id == "SYN-AL-0001")
    assert hedge.mapping == "agent" and hedge.channels[0].agent_assigned and hedge.moves["likely"].move_pct == -5


def test_a_channel_missing_from_the_vector_leaves_the_holding_untouched_with_a_gap():
    i = impact(v=vector(move("rates_duration", 1, 0, -1)))
    eq = next(p for p in i.positions if p.instrument_id == "SYN-EQ-0001")
    assert eq.mapping == "untouched" and "equity_us" in eq.reason and any("equity_us" in g.description for g in i.gaps)


def test_fx_translates_non_usd_holdings():
    inputs = PortfolioInputs(simple_portfolio().portfolio, [holding("SYN-CA-0001", CASH, 100, ccy="SGD")], ALL)
    p = impact(inputs, vector(move("fx_sgd", 1, -2, -4))).positions[0]
    assert p.mapping == "rule" and p.moves["likely"].move_pct == -2


def test_worst_case_crosses_a_mandate_band_and_breaches_the_facility():
    i = impact()
    assert i.cases["likely"].bands == [] and not i.cases["likely"].collateral[0].breaches
    w = i.cases["worst"]
    fi = next(b for b in w.bands if b.asset_class == "Fixed Income")
    assert fi.crosses == "out" and fi.before_pct == 30.0 and fi.after_pct > 31.0 and fi.band_max_pct == 31.0
    f = w.collateral[0]
    assert f.facility == "CF-T" and f.ltv_before_pct == pytest.approx(66.67, abs=0.01) and f.ltv_after_pct > 70 and f.breaches
    assert f.shortfall_usd and f.shortfall_usd > 0
    assert not i.cases["best"].collateral[0].breaches


def test_custody_portfolios_have_no_bands():
    inputs = simple_portfolio()
    inputs.portfolio["service_model"] = "Custody"
    assert all(not c.bands for c in impact(inputs).cases.values())


def test_missing_vector_gives_insufficient_data_and_no_figures():
    i = impact(v=None)
    assert i.status == "insufficient_data" and i.cases == {} and i.positions == [] and i.gaps
    assert impact(v=vector()).status == "insufficient_data"


def test_summary_and_explainers_are_built_by_code_from_the_figures():
    i = impact()
    assert "-3.0%" in i.summary and "USD 3" in i.summary and "not probabilities" in i.summary
    assert {"likely", "best", "worst", "reached", "bands", "collateral"} <= set(i.explainers)
    assert "not probabilities" in i.explainers["likely"] and "excess" in i.explainers["likely"]


def test_mapping_is_independent_of_the_vector():
    m = map_holdings(simple_portfolio())
    assert [x.mapping for x in m] == ["rule", "rule", "untouched"]
    assert m[0].channels[0].channel == "equity_us"
