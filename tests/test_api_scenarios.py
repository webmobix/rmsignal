import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from rm_dashboard.api import create_app
from rm_dashboard.api.scenarios import (
    ComputedScenarioProvider, MarketShock, PlaceholderScenarioProvider, ScenarioInfo, ScenarioResult, ScenarioRollup,
)

RESULT_FIELDS = {
    "scenario_id", "name", "premise", "mirrors", "caveat", "horizon_months", "market", "status", "note", "before_usd", "cases", "reached_pct",
    "untouched_count", "positions", "portfolios", "coverage", "summary", "explainers", "gaps",
}
CASE_FIELDS = {"before_usd", "after_usd", "delta_usd", "delta_pct", "bands", "collateral"}
DET = "gulf-deterioration"


# ---- the computed provider ----------------------------------------------------------------------------
def test_catalogue_comes_from_the_backend_with_horizon_and_the_vector_when_computed(scenario_api):
    j = scenario_api.get("/api/scenarios").json()
    assert [s["name"] for s in j["scenarios"]] == ["Gulf de-escalation", "Gulf deterioration", "Rates higher for longer"]
    assert all(s["premise"] and s["mirrors"] and s["caveat"] and s["horizon_months"] == 3 for s in j["scenarios"])
    by = {s["scenario_id"]: s for s in j["scenarios"]}
    det = by[DET]["market"]
    assert det["status"] == "computed" and det["summary"] and det["horizon_months"] == 3 and det["channels"]
    assert {"channel", "best", "likely", "worst", "rationale", "explainer", "evidence_ids", "anchored_event", "anchor_note"} <= set(det["channels"][0])
    assert by["gulf-de-escalation"]["market"] is None
    assert j["status"] == "placeholder"  # not every vector is computed


def test_catalogue_status_is_computed_when_every_vector_is(scenario_api, seeded_db, scenario_reports):
    only = ScenarioInfo(scenario_id="x", name="x", premise="p", mirrors="m", caveat="c")
    provider = type("P", (), {"catalogue": lambda self, a: [only.model_copy(update={"market": MarketShock(
        status="computed", horizon_months=3, summary="s", not_a_probability="n", channels=[])})], "for_client": lambda *a: [], "rollup": lambda *a: None})()
    c = TestClient(create_app(seeded_db, scenario_reports, scenarios=provider))
    j = c.get("/api/scenarios").json()
    assert j["status"] == "computed" and j["note"] == ""


def test_catalogue_mirrors_real_event_log_entries(scenario_api):
    events = {e["event_date"] for e in scenario_api.get("/api/events").json()["events"]}
    for s in scenario_api.get("/api/scenarios").json()["scenarios"]:
        assert re.search(r"Event log (\d{4}-\d{2}-\d{2})", s["mirrors"]).group(1) in events


def test_client_results_have_three_cases_summary_and_explainers(scenario_api):
    j = scenario_api.get("/api/clients/CL-0002/scenarios").json()
    assert j["client_id"] == "CL-0002" and len(j["scenarios"]) == 3
    r = next(s for s in j["scenarios"] if s["scenario_id"] == DET)
    assert set(r) == RESULT_FIELDS and r["status"] in ("computed", "partial")
    assert set(r["cases"]) == {"best", "likely", "worst"} and all(set(c) == CASE_FIELDS for c in r["cases"].values())
    assert r["cases"]["worst"]["delta_usd"] <= r["cases"]["likely"]["delta_usd"] <= r["cases"]["best"]["delta_usd"]
    assert r["summary"] and {"likely", "best", "worst"} <= set(r["explainers"]) and r["positions"] and r["reached_pct"] > 0
    p = r["positions"][0]
    assert {"instrument", "asset_class", "weight_pct", "moves", "channels", "mapping"} <= set(p) and set(p["moves"]) == {"best", "likely", "worst"}
    assert r["coverage"] == {"computed": 2, "total": 2, "missing": []}  # CL-0002 holds two portfolios


def test_values_follow_the_clients_holdings(scenario_api):
    a = scenario_api.get("/api/clients/CL-0001/scenarios").json()["scenarios"][1]
    b = scenario_api.get("/api/clients/CL-0017/scenarios").json()["scenarios"][1]
    assert a["before_usd"] != b["before_usd"] and a["cases"]["likely"]["delta_usd"] != b["cases"]["likely"]["delta_usd"]


def test_client_totals_equal_the_sum_of_their_portfolios(scenario_api):
    r = scenario_api.get("/api/clients/CL-0001/scenarios").json()["scenarios"][1]
    assert len(r["portfolios"]) == 2
    assert r["cases"]["likely"]["delta_usd"] == pytest.approx(sum(p["cases"]["likely"]["delta_usd"] for p in r["portfolios"]), abs=0.05)


def test_a_scenario_that_was_not_run_has_no_figures_and_says_why(scenario_api):
    j = scenario_api.get("/api/clients/CL-0001/scenarios").json()
    r = next(s for s in j["scenarios"] if s["scenario_id"] == "gulf-de-escalation")
    assert r["status"] == "placeholder" and r["cases"] == {} and r["positions"] == [] and r["summary"] == "" and "not been run" in r["note"]
    assert j["status"] == "placeholder"


def test_default_api_without_any_run_returns_the_catalogue_without_figures(api):
    j = api.get("/api/clients/CL-0001/scenarios").json()
    assert len(j["scenarios"]) == 3 and all(s["status"] == "placeholder" and s["cases"] == {} for s in j["scenarios"])
    assert isinstance(api.app.state.scenarios, ComputedScenarioProvider)


def test_unknown_client_is_404(scenario_api):
    assert scenario_api.get("/api/clients/CL-9999/scenarios").status_code == 404


def test_rollup_has_book_totals_ranking_coverage_and_summary(scenario_api):
    j = scenario_api.get(f"/api/scenarios/{DET}/rollup").json()
    assert j["status"] in ("computed", "partial") and j["scenario_id"] == DET and j["rm_id"] == "RM-SG-014"
    assert set(j["cases"]) == {"best", "likely", "worst"} and j["summary"] and j["coverage"]["total"] == 20 and j["coverage"]["computed"] == 20
    worst = [c["cases"]["worst"]["delta_usd"] for c in j["most_hit"]]
    assert worst == sorted(worst) and len(worst) == 20
    assert j["cases"]["likely"]["delta_usd"] == pytest.approx(sum(c["cases"]["likely"]["delta_usd"] for c in j["most_hit"]), abs=0.5)
    ltv = [c for c in j["crossings"] if c["kind"] == "ltv" and c["case"] == "worst"]
    assert {"client_id", "portfolio_id", "case", "kind", "label", "detail"} <= set(ltv[0]) and ("CL-0002", "CF-0001") in {(c["client_id"], c["label"]) for c in ltv}


def test_rollup_of_a_scenario_not_run_has_no_figures(scenario_api):
    j = scenario_api.get("/api/scenarios/gulf-de-escalation/rollup").json()
    assert j["status"] == "placeholder" and j["cases"] == {} and j["most_hit"] == [] and "not been run" in j["note"]


def test_rollup_of_an_unknown_scenario_is_404(scenario_api):
    assert scenario_api.get("/api/scenarios/no-such/rollup").status_code == 404


# ---- providers can be swapped ---------------------------------------------------------------------------
def test_the_placeholder_provider_has_the_new_shape_and_says_it_is_illustrative(seeded_db, reports_dir):
    c = TestClient(create_app(seeded_db, reports_dir, scenarios=PlaceholderScenarioProvider()))
    j = c.get("/api/clients/CL-0001/scenarios").json()
    assert j["status"] == "placeholder" and "not computed" in j["note"]
    for r in j["scenarios"]:
        assert set(r) == RESULT_FIELDS and r["status"] == "placeholder" and "not computed" in r["note"]
        assert set(r["cases"]) == {"best", "likely", "worst"} and r["cases"]["worst"]["delta_usd"] < r["cases"]["best"]["delta_usd"]
        assert r["cases"]["likely"]["after_usd"] == r["cases"]["likely"]["before_usd"] + r["cases"]["likely"]["delta_usd"]
        assert r["positions"][0]["channels"] and r["summary"]
    assert c.get("/api/scenarios/gulf-deterioration/rollup").json()["status"] == "placeholder"
    assert c.get("/api/scenarios/nope/rollup").status_code == 404
    other = c.get("/api/clients/CL-0017/scenarios").json()["scenarios"]
    assert other == j["scenarios"]  # nothing here reads a holding


class _Swapped:
    def catalogue(self, as_of: date):
        return [ScenarioInfo(scenario_id="x", name="Swapped", premise="p", mirrors="m", caveat="c")]

    def for_client(self, client_id: str, as_of: date):
        return [ScenarioResult(scenario_id="x", name="Swapped", premise="p", mirrors="m", caveat="c", status="computed", before_usd=1.0, summary="s")]

    def rollup(self, scenario_id: str, as_of: date):
        return ScenarioRollup(scenario_id="x", name="Swapped", premise="p", mirrors="m", caveat="c", status="computed", as_of=as_of) if scenario_id == "x" else None


def test_a_provider_can_be_replaced_without_changing_routes_or_models(seeded_db, reports_dir):
    c = TestClient(create_app(seeded_db, reports_dir, scenarios=_Swapped()))
    assert c.get("/api/scenarios").json()["scenarios"][0]["name"] == "Swapped"
    r = c.get("/api/clients/CL-0001/scenarios").json()
    assert r["status"] == "computed" and r["note"] == "" and r["scenarios"][0]["before_usd"] == 1.0 and set(r["scenarios"][0]) == RESULT_FIELDS
    assert c.get("/api/scenarios/x/rollup").json()["scenario_id"] == "x" and c.get("/api/scenarios/y/rollup").status_code == 404
