import re
from datetime import date

from fastapi.testclient import TestClient

from rm_dashboard.api import create_app
from rm_dashboard.api.scenarios import ScenarioInfo, ScenarioResult, PlaceholderScenarioProvider

RESULT_FIELDS = {
    "scenario_id", "name", "premise", "mirrors", "caveat", "status", "note", "before_usd", "after_usd", "delta_usd",
    "delta_pct", "reached_pct", "untouched_count", "collateral", "bands", "positions",
}


def test_catalogue_comes_from_the_backend_and_is_a_placeholder(api):
    j = api.get("/api/scenarios").json()
    assert j["status"] == "placeholder" and "not computed" in j["note"]
    names = [s["name"] for s in j["scenarios"]]
    assert names == ["Gulf de-escalation", "Gulf deterioration", "Rates higher for longer"]
    assert all(s["premise"] and s["mirrors"] and s["caveat"] for s in j["scenarios"])


def test_catalogue_mirrors_real_event_log_entries(api):
    events = {e["event_date"] for e in api.get("/api/events").json()["events"]}
    for s in api.get("/api/scenarios").json()["scenarios"]:
        assert re.search(r"Event log (\d{4}-\d{2}-\d{2})", s["mirrors"]).group(1) in events


def test_client_results_have_every_contract_field(api):
    j = api.get("/api/clients/CL-0001/scenarios").json()
    assert j["status"] == "placeholder" and j["client_id"] == "CL-0001" and len(j["scenarios"]) == 3
    for r in j["scenarios"]:
        assert set(r) == RESULT_FIELDS and r["status"] == "placeholder" and "not computed" in r["note"]
        assert r["after_usd"] == r["before_usd"] + r["delta_usd"]
        assert r["collateral"] and r["bands"] and r["positions"]
        assert {"channel", "pct", "why"} <= set(r["positions"][0]["channels"][0])
        assert {"facility", "ltv_before_pct", "ltv_after_pct", "trigger_pct", "breaches"} <= set(r["collateral"][0])
        assert {"asset_class", "portfolio", "before_pct", "after_pct", "band_min_pct", "band_max_pct", "crosses"} <= set(r["bands"][0])


def test_results_are_not_derived_from_the_clients_holdings(api):
    a = api.get("/api/clients/CL-0001/scenarios").json()["scenarios"]
    b = api.get("/api/clients/CL-0017/scenarios").json()["scenarios"]
    assert a == b


def test_unknown_client_is_404(api):
    assert api.get("/api/clients/CL-9999/scenarios").status_code == 404


class _Computed:
    status = "computed"

    def catalogue(self, as_of: date):
        return [ScenarioInfo(scenario_id="x", name="Swapped", premise="p", mirrors="m", caveat="c")]

    def for_client(self, client_id: str, as_of: date):
        return [ScenarioResult(
            scenario_id="x", name="Swapped", premise="p", mirrors="m", caveat="c", status="computed", before_usd=1.0,
            after_usd=2.0, delta_usd=1.0, delta_pct=100.0, reached_pct=50.0, untouched_count=0, collateral=[], bands=[],
            positions=[])]


def test_a_provider_can_be_replaced_without_changing_routes_or_models(seeded_db, reports_dir):
    c = TestClient(create_app(seeded_db, reports_dir, scenarios=_Computed()))
    cat = c.get("/api/scenarios").json()
    assert cat["status"] == "computed" and cat["note"] == "" and cat["scenarios"][0]["name"] == "Swapped"
    r = c.get("/api/clients/CL-0001/scenarios").json()
    assert r["status"] == "computed" and r["scenarios"][0]["after_usd"] == 2.0
    assert set(r["scenarios"][0]) == RESULT_FIELDS


def test_default_provider_is_the_placeholder(api):
    assert isinstance(api.app.state.scenarios, PlaceholderScenarioProvider)
