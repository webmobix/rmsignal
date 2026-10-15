from datetime import date

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rm_dashboard.analytics import concentration, credit, exposure, liquidity, mandate, performance, risk
from rm_dashboard.analytics.base import METHODS
from rm_dashboard.analytics.fx import (
    FxQuote, FxTable, MissingRate, bond_nominal, fx_table, market_value, quote_from_market_row,
)

D = date
SNAPS = [D(2025, 12, 31), D(2026, 2, 27), D(2026, 3, 31), D(2026, 6, 30), D(2026, 8, 26)]


def fx_at(pit_repo, snap):
    return fx_table(pit_repo.market_context(as_of=snap).frame.iter_rows(named=True))


# ---- 4.1 FX and bond nominal --------------------------------------------------------
def test_fx_quote_direction_hand_checked():
    fx = FxTable([FxQuote("USD", "SGD", 1.352), FxQuote("EUR", "USD", 1.092), FxQuote("USD", "CHF", 0.831)])
    assert fx.convert(1352, "SGD", "USD") == pytest.approx(1000)       # SGD per USD: divide
    assert fx.convert(100, "EUR", "USD") == pytest.approx(109.2)       # USD per EUR: multiply
    assert fx.convert(100, "USD", "CHF") == pytest.approx(83.1)
    assert fx.convert(100, "EUR", "SGD") == pytest.approx(100 * 1.092 * 1.352)
    assert fx.convert(5, "USD", "USD") == 5
    with pytest.raises(MissingRate):
        fx.usd_per("XYZ")


def test_quote_direction_comes_from_unit():
    q = quote_from_market_row("USDSGD", "SGD per USD", 1.352)
    assert (q.base, q.quote) == ("USD", "SGD")
    q = quote_from_market_row("EURUSD", "USD per EUR", 1.092)
    assert (q.base, q.quote) == ("EUR", "USD")
    assert quote_from_market_row("SPX", "points", 6900) is None
    assert quote_from_market_row("USDSGD", "USD per SGD", 0.7) is None


def test_fx_reproduces_dataset_usd_values(pit_repo):
    for snap in SNAPS:
        fx = fx_at(pit_repo, snap)
        for r in pit_repo.holdings(as_of=snap).frame.iter_rows(named=True):
            assert r["market_value_local"] * fx.usd_per(r["instrument_ccy"]) == pytest.approx(r["market_value_usd"], rel=1e-5)
            assert r["market_value_local"] * fx.base_per_local(r["instrument_ccy"], r["portfolio_ccy"]) == pytest.approx(
                r["market_value_base"], rel=1e-5)


def test_bond_nominal_and_market_value(pit_repo):
    assert bond_nominal(250) == 25000
    assert market_value(250, 98.5) == pytest.approx(24625)
    h = pit_repo.holdings(as_of=SNAPS[-1]).frame
    for r in h.iter_rows(named=True):
        assert market_value(r["quantity"], r["price_local"]) == pytest.approx(r["market_value_local"], rel=1e-6)


# ---- 4.2 weights and exposures ------------------------------------------------------
def test_weights_hand_checked():
    df = pl.DataFrame({"portfolio_id": ["P"] * 2, "instrument_id": ["A", "B"], "v": [30.0, 70.0]})
    c = exposure.weights(df, value_col="v", denominator_label="portfolio")
    assert [w["weight_pct"] for w in c.data["weights"]] == [30.0, 70.0]
    assert c.data["denominator"] == 100 and c.data["denominator_label"] == "portfolio"


@given(st.lists(st.floats(min_value=0.01, max_value=1e9, allow_nan=False), min_size=1, max_size=40))
def test_weights_sum_to_100(values):
    df = pl.DataFrame({"portfolio_id": ["P"] * len(values), "instrument_id": [str(i) for i in range(len(values))], "v": values})
    c = exposure.weights(df, value_col="v", denominator_label="x")
    assert c.data["sum_weight_pct"] == pytest.approx(100, abs=0.01)


def test_weights_sum_on_every_portfolio_and_snapshot(pit_repo):
    for snap in SNAPS:
        h = pit_repo.holdings(as_of=snap).frame
        for pf in h["portfolio_id"].unique():
            c = exposure.weights(h.filter(pl.col("portfolio_id") == pf), value_col="market_value_base", denominator_label="p")
            assert c.data["sum_weight_pct"] == pytest.approx(100, abs=0.01)


def test_exposures_and_unclassified(pit_repo):
    df = pl.DataFrame({"portfolio_id": ["P"] * 3, "instrument_id": ["A", "B", "C"], "sector": ["Tech", None, "Tech"], "v": [1.0, 1.0, 2.0]})
    c = exposure.exposures(df, dimension="sector", column="sector", value_col="v", denominator_label="p")
    groups = {g["name"]: g["exposure_pct"] for g in c.data["groups"]}
    assert groups == {"Tech": 75.0, "unclassified": 25.0}
    assert any(f.code == "unclassified_sector" for f in c.flags)
    h = pit_repo.holdings(as_of=SNAPS[-1], portfolio_id="PF-0001").frame
    for dim, col in [("asset_class", "asset_class"), ("currency", "instrument_ccy"), ("region", "region"), ("sector", "sector")]:
        c = exposure.exposures(h, dimension=dim, column=col, value_col="market_value_base", denominator_label="p")
        assert sum(g["exposure_pct"] for g in c.data["groups"]) == pytest.approx(100, abs=0.01)


def test_empty_positions_insufficient():
    assert exposure.weights(pl.DataFrame(), value_col="v", denominator_label="x").status == "insufficient_data"


# ---- 4.3 concentration --------------------------------------------------------------
def client_frames(pit_repo, cid, snap=SNAPS[-1]):
    h = pit_repo.holdings(as_of=snap, client_id=cid).frame.join(
        pit_repo.portfolios(as_of=snap, client_id=cid).frame.select("portfolio_id", "service_model"), on="portfolio_id")
    return h, pit_repo.instruments(as_of=snap).frame


def test_shared_underlying_aggregates_across_portfolios(pit_repo):
    h, inst = client_frames(pit_repo, "CL-0001")
    c = concentration.client_concentration(h, inst, value_col="market_value_usd", include_custody=True)
    bara = next(e for e in c.data["single_names"] if e["name"].startswith("Bara Nusantara"))
    assert {x["portfolio_id"] for x in bara["contributions"]} == {"PF-0001", "PF-0002"} or len({x["portfolio_id"] for x in bara["contributions"]}) == 2
    assert {x["via"] for x in bara["contributions"]} == {"direct", "look_through"}
    assert bara["value"] == pytest.approx(sum(x["value"] for x in bara["contributions"]))
    assert bara["share_pct"] == pytest.approx(bara["value"] / c.data["denominator"] * 100)


def test_basket_flag_and_equal_attribution(pit_repo):
    h, inst = client_frames(pit_repo, "CL-0001")
    c = concentration.client_concentration(h, inst, value_col="market_value_usd", include_custody=True)
    assert any(f.code == "basket_attribution_assumption" for f in c.flags)
    assert "equally" in c.method
    sp = h.filter(pl.col("instrument_id") == "SYN-SP-0505")
    assert sp.height == 1
    shares = [x["value"] for e in c.data["top"] + c.data["single_names"] for x in e["contributions"]
              if x["instrument_id"] == "SYN-SP-0505"]
    assert len(set(round(s, 6) for s in shares)) == 1


def test_denominator_and_hhi_and_topn(pit_repo):
    h, inst = client_frames(pit_repo, "CL-0001")
    all_ = concentration.client_concentration(h, inst, value_col="market_value_usd", include_custody=True, top_n=3)
    managed = concentration.client_concentration(h, inst, value_col="market_value_usd", include_custody=False)
    assert all_.data["denominator"] > managed.data["denominator"]
    assert all_.data["denominator"] == pytest.approx(h["market_value_usd"].sum())
    assert len(all_.data["top"]) == 3 and "custody" in all_.data["denominator_label"]
    assert 0 < all_.data["hhi"] <= 10000
    assert sum(e["value"] for e in all_.data["top"]) <= all_.data["denominator"]


def test_name_normalisation_and_parsing():
    n = concentration.normalise_name
    assert n("Helios Cloud Systems Inc") == n("Helios Cloud Systems") == "helios cloud systems"
    assert n("Golden Harbour Properties 5.25% Perpetual") == n("Golden Harbour Properties Ltd")
    p = concentration.parse_underlyings
    assert p("Worst-of basket: A Corp / B Ltd / C", "x") == (["A Corp", "B Ltd", "C"], True)
    assert p("Single underlying: Helios Cloud Systems Inc", "x") == (["Helios Cloud Systems Inc"], True)
    assert p("Daily accumulation at strike HKD 17.20", "Accumulator ref. Golden Harbour Properties Ltd, 12M") == (["Golden Harbour Properties Ltd"], True)
    assert p("Worst-of basket: three Asian banking majors, autocall", "Autocallable ref. Asia Banks Basket, 7.8%")[1] is False


def test_unresolved_underlying_flagged(pit_repo):
    h, inst = client_frames(pit_repo, "CL-0003")
    c = concentration.client_concentration(h, inst, value_col="market_value_usd", include_custody=True)
    assert any(f.code == "unresolved_underlying" for f in c.flags)


# ---- 4.4 mandate drift --------------------------------------------------------------
BANDS = pl.DataFrame({"asset_class": ["Equity", "Fixed Income", "Cash"], "min_pct": [30.0, 20.0, 15.0],
                      "target_pct": [50.0, 30.0, 20.0], "max_pct": [55.0, 40.0, 30.0],
                      "max_single_position_pct": [10.0] * 3})


def test_mandate_drift_hand_computed():
    pos = pl.DataFrame({"instrument_id": ["A", "B", "C"], "instrument_name": ["a", "b", "c"],
                        "asset_class": ["Equity", "Fixed Income", "Cash"], "v": [60.0, 30.0, 10.0]})
    inst = pl.DataFrame({"instrument_id": ["A", "B", "C"], "concentration_limit_applies": [True, False, False]})
    c = mandate.mandate_drift(pos, BANDS, service_model="Advisory", value_col="v", instruments=inst)
    by = {b["asset_class"]: b for b in c.data["bands"]}
    assert by["Equity"]["gap_pp"] == pytest.approx(5.0) and by["Equity"]["breach"] == "above_max"
    assert by["Fixed Income"]["gap_pp"] == 0 and by["Fixed Income"]["drift_pp"] == pytest.approx(0.0)
    assert by["Cash"]["gap_pp"] == pytest.approx(-5.0) and by["Cash"]["breach"] == "below_min"
    assert len(c.data["breaches"]) == 2
    assert c.data["single_position_breaches"][0]["gap_pp"] == pytest.approx(50.0)


def test_custody_excluded_from_mandate(pit_repo):
    h = pit_repo.holdings(as_of=SNAPS[-1], portfolio_id="PF-0002").frame
    c = mandate.mandate_drift(h, BANDS, service_model="Custody")
    assert c.data == {"applicable": False} and "mandate" in c.reason


def test_mandate_drift_real_portfolio(pit_repo):
    h = pit_repo.holdings(as_of=SNAPS[-1], portfolio_id="PF-0001").frame
    bands = pit_repo.mandates(as_of=SNAPS[-1], mandate_code="BALG").frame
    c = mandate.mandate_drift(h, bands, service_model="Discretionary")
    assert sum(b["weight_pct"] for b in c.data["bands"]) == pytest.approx(100, abs=0.01)
    assert not c.flags


# ---- 4.5 liquidity ------------------------------------------------------------------
def liq_fx():
    return FxTable([FxQuote("USD", "SGD", 1.352)])


NEEDS = pl.DataFrame({
    "need_id": ["N1", "N2", "N3", "N4"], "description": ["fees", "tax", "boat", "old"],
    "currency": ["SGD", "USD", "USD", "USD"], "amount": [1_352_000.0, 500_000.0, 9_999_999.0, 7.0],
    "due_from": [D(2026, 10, 1), D(2027, 1, 1), D(2026, 10, 1), D(2025, 1, 1)],
    "due_to": [D(2026, 10, 31), D(2027, 2, 1), D(2027, 1, 1), D(2025, 2, 1)],
    "certainty": ["Confirmed", "Likely", "Aspirational", "Confirmed"], "recurrence": ["One-off"] * 4})
NO_COMMIT = pl.DataFrame(schema={"commitment_id": pl.String, "fund_name": pl.String, "currency": pl.String,
                                 "uncalled": pl.Float64, "expected_call_window": pl.String})


def test_liquidity_shortfall_and_aspirational():
    pos = pl.DataFrame({"liquidity_tier": ["Daily", "Illiquid"], "market_value_usd": [1_000_000.0, 5_000_000.0]})
    c = liquidity.liquidity_coverage(pos, NEEDS, NO_COMMIT, liq_fx(), as_of=D(2026, 8, 26), horizon_days=365)
    assert c.data["needs_total_usd"] == pytest.approx(1_500_000)
    assert c.data["shortfall_usd"] == pytest.approx(500_000)
    assert c.data["coverage_ratio"] == pytest.approx(1_000_000 / 1_500_000)
    assert {i["id"] for i in c.data["contributing"]} == {"N1", "N2"}
    assert [i["id"] for i in c.data["excluded_aspirational"]] == ["N3"]
    assert "N4" not in {i["id"] for i in c.data["items"]}      # already past
    assert c.data["assets_by_tier_usd"]["Illiquid"] == 5_000_000


def test_liquidity_horizon_limits_needs():
    pos = pl.DataFrame({"liquidity_tier": ["Daily"], "market_value_usd": [10.0]})
    c = liquidity.liquidity_coverage(pos, NEEDS, NO_COMMIT, liq_fx(), as_of=D(2026, 8, 26), horizon_days=60)
    assert {i["id"] for i in c.data["items"]} == {"N1"}


def test_call_window_parsing():
    assert liquidity.parse_call_window("2026 Q4 to 2028 Q2") == (D(2026, 10, 1), D(2028, 6, 30))
    assert liquidity.parse_call_window("2026 Q4") == (D(2026, 10, 1), D(2026, 12, 31))
    assert liquidity.parse_call_window("whenever") is None


def test_commitments_counted_and_restatement_not_doubled(pit_repo):
    snap = SNAPS[-1]
    fx = fx_at(pit_repo, snap)
    h = pit_repo.holdings(as_of=snap, client_id="CL-0017").frame
    needs = pit_repo.cash_needs(as_of=snap, client_id="CL-0017").frame
    com = pit_repo.commitments(as_of=snap, client_id="CL-0017").frame
    c = liquidity.liquidity_coverage(h, needs, com, fx, as_of=snap, horizon_days=730)
    restated = any("commitment" in d.lower() for d in needs["description"])
    assert restated == any(f.code == "commitment_restated" for f in c.flags)
    assert c.data["needs_total_usd"] > 0


# ---- 4.6 credit ---------------------------------------------------------------------
def facility_rows(pit_repo):
    snap = SNAPS[-1]
    trig = {r["facility_id"]: r["margin_call_ltv_pct"] for r in pit_repo._facilities.iter_rows(named=True)}
    for r in pit_repo.facility_snapshots(as_of=snap).frame.iter_rows(named=True):
        yield r, trig[r["facility_id"]]


def test_ltv_equals_drawn_over_lending_for_all_snapshots(pit_repo):
    n = 0
    for r, trig in facility_rows(pit_repo):
        c = credit.ltv(drawn=r["drawn"], lending_value=r["lending_value"], collateral_value=r["collateral_market_value"],
                       trigger_pct=trig, source_ltv_pct=r["ltv_pct"])
        assert c.data["ltv_pct"] == pytest.approx(r["drawn"] / r["lending_value"] * 100)
        assert not c.flags, (r["facility_id"], r["snapshot_date"], c.flags)
        n += 1
    assert n == 25


def test_ltv_difference_flagged():
    c = credit.ltv(drawn=70, lending_value=100, collateral_value=200, trigger_pct=75, source_ltv_pct=60)
    assert any(f.code == "ltv_source_difference" for f in c.flags)


def test_breach_cure_amount_hand_checked():
    # drawn 80, lending 100, collateral 200 -> a = 0.5; trigger 75% -> x = (80-75)/(1-0.375) = 8
    c = credit.ltv(drawn=80, lending_value=100, collateral_value=200, trigger_pct=75)
    assert c.data["breached"] and c.data["cure_sale_required"] == pytest.approx(8.0)
    assert c.data["ltv_gap_pp"] == pytest.approx(-5.0)
    after = (80 - 8) / (100 - 0.5 * 8) * 100
    assert after == pytest.approx(75.0)
    ok = credit.ltv(drawn=50, lending_value=100, collateral_value=200, trigger_pct=75)
    assert not ok.data["breached"] and ok.data["cure_sale_required"] == 0
    assert ok.data["lending_value_buffer"] == pytest.approx(100 - 50 / 0.75)


def test_known_breach_in_dataset(pit_repo):
    rows = {(r["facility_id"], r["snapshot_date"]): (r, t) for r, t in facility_rows(pit_repo)}
    r, t = rows[("CF-0001", D(2026, 6, 30))]
    c = credit.ltv(drawn=r["drawn"], lending_value=r["lending_value"], collateral_value=r["collateral_market_value"], trigger_pct=t)
    assert c.data["breached"] and c.data["cure_sale_required"] > 0


def test_collateral_funding_test():
    # nothing free: need 10, drawn 73, lending 100, collateral 200 (a=0.5), trigger 75%
    c = credit.collateral_funding(need=10, free_assets=0, drawn=73, lending_value=100, collateral_value=200,
                                  trigger_pct=75, daily_collateral_value=200)
    d = c.data
    assert d["touches_collateral"] and d["sale_required"] > d["shortfall"] == 10
    assert d["sale_required"] == pytest.approx(12.8) and d["ltv_after_pct"] == pytest.approx(75.0)
    assert d["repayment_required"] == pytest.approx(d["sale_required"] - 10)
    free = credit.collateral_funding(need=10, free_assets=50, drawn=70, lending_value=100, collateral_value=200,
                                     trigger_pct=75, daily_collateral_value=200)
    assert free.data["fundable"] and not free.data["touches_collateral"]
    tight = credit.collateral_funding(need=10, free_assets=0, drawn=73, lending_value=100, collateral_value=200,
                                      trigger_pct=75, daily_collateral_value=1)
    assert not tight.data["fundable"]


@given(drawn=st.floats(1, 90), need=st.floats(0.1, 40))
def test_funding_test_keeps_ltv_within_trigger(drawn, need):
    c = credit.collateral_funding(need=need, free_assets=0, drawn=drawn, lending_value=100, collateral_value=200,
                                  trigger_pct=75, daily_collateral_value=1e9)
    if c.data["ltv_after_pct"] is not None and drawn / 100 * 100 <= 75:
        assert c.data["ltv_after_pct"] <= 75 + 1e-6
    assert c.data["sale_required"] >= need - 1e-9


# ---- 4.7 P&L and decomposition ------------------------------------------------------
def test_unrealised_pnl_excludes_missing_cost(pit_repo):
    h = pit_repo.holdings(as_of=SNAPS[-1], portfolio_id="PF-0005").frame
    c = performance.unrealised_pnl(h)
    assert c.data["positions_excluded"] == 1 and c.data["positions_included"] == h.height - 1
    assert any(f.code == "pnl_excludes_positions" and "SYN-ST-0107" in f.subject for f in c.flags)
    ok = h.filter(pl.col("cost_basis_base").is_not_null())
    assert c.data["unrealised_pnl_base"] == pytest.approx(ok["unrealised_pnl_base"].sum())


def price_map(pit_repo, snap):
    f = pit_repo.instrument_prices(as_of=snap).frame.filter(pl.col("snapshot_date") == snap)
    return dict(f.select("instrument_id", "price").iter_rows())


def test_decomposition_exact_on_real_data(pit_repo):
    for s0, s1 in zip(SNAPS, SNAPS[1:]):
        fx0, fx1, p0, p1 = fx_at(pit_repo, s0), fx_at(pit_repo, s1), price_map(pit_repo, s0), price_map(pit_repo, s1)
        for pf, base in pit_repo.portfolios(as_of=SNAPS[-1]).frame.select("portfolio_id", "base_currency").iter_rows():
            h0 = pit_repo.holdings(as_of=s0, portfolio_id=pf).frame
            h1 = pit_repo.holdings(as_of=s1, portfolio_id=pf).frame
            c = performance.decompose_change(h0, h1, p0, p1, fx0, fx1, base_ccy=base)
            t = c.data["total"]
            assert t["flow"] + t["price"] + t["fx"] == pytest.approx(t["change"], rel=1e-9, abs=1e-6)
            assert abs(c.data["unexplained"]) <= 1e-3 * max(1.0, abs(t["value_t1"]))


@settings(max_examples=60)
@given(q0=st.integers(0, 10_000), q1=st.integers(0, 10_000), p0=st.floats(0.5, 1000), p1=st.floats(0.5, 1000),
       r0=st.floats(0.5, 200), r1=st.floats(0.5, 200))
def test_decomposition_exact_property(q0, q1, p0, p1, r0, r1):
    h0 = pl.DataFrame({"instrument_id": ["I"], "quantity": [q0], "instrument_ccy": ["EUR"], "market_value_base": [0.0]})
    h1 = pl.DataFrame({"instrument_id": ["I"], "quantity": [q1], "instrument_ccy": ["EUR"], "market_value_base": [0.0]})
    fx0, fx1 = FxTable([FxQuote("EUR", "USD", r0)]), FxTable([FxQuote("EUR", "USD", r1)])
    c = performance.decompose_change(h0, h1, {"I": p0}, {"I": p1}, fx0, fx1, base_ccy="USD")
    t = c.data["total"]
    assert t["flow"] + t["price"] + t["fx"] == pytest.approx(t["change"], rel=1e-9, abs=1e-6)
    assert t["change"] == pytest.approx(q1 * p1 * r1 - q0 * p0 * r0, rel=1e-9, abs=1e-6)


def test_new_position_is_pure_flow():
    h0 = pl.DataFrame(schema={"instrument_id": pl.String, "quantity": pl.Int64, "instrument_ccy": pl.String, "market_value_base": pl.Float64})
    h1 = pl.DataFrame({"instrument_id": ["I"], "quantity": [10], "instrument_ccy": ["USD"], "market_value_base": [1000.0]})
    fx = FxTable([])
    c = performance.decompose_change(h0, h1, {"I": 90.0}, {"I": 100.0}, fx, fx, base_ccy="USD")
    t = c.data["total"]
    assert t["flow"] == pytest.approx(900) and t["price"] == pytest.approx(100) and t["fx"] == 0


# ---- 4.8 insufficient history -------------------------------------------------------
@pytest.mark.parametrize("name", ["volatility", "var", "max_drawdown", "sharpe"])
def test_insufficient_history_returns_no_number(name, pit_repo):
    prices = pit_repo.instrument_prices(as_of=SNAPS[-1], instrument_id="SYN-EQ-0001").frame["price"].to_list()
    assert len(prices) == 5
    c = risk.risk_measure(name, prices)
    assert c.status == "insufficient_history" and "value" not in c.data
    assert c.data["points_available"] == 5 and c.data["points_required"] == risk.MIN_POINTS[name]


def test_risk_measures_with_enough_points():
    prices = [100 + i for i in range(60)]
    assert risk.risk_measure("volatility", prices).data["value"] > 0
    assert risk.risk_measure("max_drawdown", prices).data["value"] == 0
    assert risk.risk_measure("max_drawdown", [100, 50] * 20).data["value"] == pytest.approx(-0.5)


# ---- purity -------------------------------------------------------------------------
def test_calculations_repeatable(pit_repo):
    h, inst = client_frames(pit_repo, "CL-0001")
    a = concentration.client_concentration(h, inst, value_col="market_value_usd", include_custody=True)
    b = concentration.client_concentration(h, inst, value_col="market_value_usd", include_custody=True)
    assert a == b


def test_every_calc_has_method_string(pit_repo):
    h, inst = client_frames(pit_repo, "CL-0001")
    calcs = [
        exposure.weights(h, value_col="market_value_usd", denominator_label="x"),
        exposure.exposures(h, dimension="asset_class", column="asset_class", value_col="market_value_usd", denominator_label="x"),
        concentration.client_concentration(h, inst, value_col="market_value_usd", include_custody=True),
        mandate.mandate_drift(h, BANDS, service_model="Custody"),
        credit.ltv(drawn=1, lending_value=2, collateral_value=4, trigger_pct=75),
        credit.collateral_funding(need=1, free_assets=0, drawn=1, lending_value=2, collateral_value=4, trigger_pct=75, daily_collateral_value=4),
        performance.unrealised_pnl(h),
        risk.risk_measure("var", [1.0, 2.0]),
    ]
    for c in calcs:
        assert c.method and c.method == METHODS[c.name], c.name


def test_docs_list_every_method():
    from pathlib import Path
    text = (Path(__file__).parent.parent / "docs" / "analytics.md").read_text()
    assert METHODS
    for name, method in METHODS.items():
        assert f"## {name}\n" in text and method in text, name
        assert len(method) > 40
