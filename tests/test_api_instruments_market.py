import pytest

from storehelp import mark_run, saved_json

from rm_dashboard.api.market import CHANNEL_RULES, reach_for
from rm_dashboard.store import Kind


def test_every_instrument_is_listed_with_holdings_and_outlook_flag(api):
    rows = api.get("/api/instruments").json()
    assert len(rows) == 62
    outlooked = {r["instrument_id"] for r in rows if r["has_outlook"]}
    assert outlooked == {"SYN-EQ-0001", "SYN-CM-0401"}
    by = {r["instrument_id"]: r for r in rows}
    assert by["SYN-EQ-0001"]["held_usd"] > 0 and by["SYN-EQ-0001"]["holder_portfolios"] >= by["SYN-EQ-0001"]["holder_clients"] > 0
    assert by["SYN-EQ-0001"]["price_change_pct"] == pytest.approx(
        (by["SYN-EQ-0001"]["latest_price"] / by["SYN-EQ-0001"]["previous_price"] - 1) * 100)
    for r in rows:
        assert (r["held_usd"] == 0) == (r["holder_portfolios"] == 0)


def test_unheld_instruments_have_zero_held(api):
    rows = api.get("/api/instruments").json()
    zero = [r for r in rows if r["held_usd"] == 0]
    assert all(r["holder_clients"] == 0 for r in zero)
    assert sum(r["held_usd"] for r in rows) == pytest.approx(
        sum(c["aum_usd"] for c in api.get("/api/clients").json()))


def test_structured_product_detail_has_underlying_and_holders(api):
    j = api.get("/api/instruments/SYN-SP-0501").json()
    assert j["underlying_reference"].startswith("Worst-of basket")
    assert j["holders"] and all(h["client_name"] and h["value_usd"] > 0 for h in j["holders"])
    assert len(j["price_path"]) == 5 and j["price_path"][0]["snapshot_date"] == "2025-12-31"
    assert j["instrument"]["held_usd"] == pytest.approx(sum(h["value_usd"] for h in j["holders"]))


def test_instrument_with_outlook_carries_it(api):
    j = api.get("/api/instruments/SYN-EQ-0001").json()
    assert j["outlook"]["view"]["direction"] and j["outlook"]["evidence_ids"] and j["gaps"] == []
    assert j["instrument"]["has_outlook"] and len(j["holders"]) > 1


def test_instrument_without_outlook_is_a_gap(api):
    j = api.get("/api/instruments/SYN-SP-0501").json()
    assert j["outlook"] is None
    assert any(g["description"].startswith("outlook_missing") for g in j["gaps"])


def test_unknown_instrument_is_404(api):
    assert api.get("/api/instruments/NOPE").status_code == 404


def test_market_outlook_matches_the_persisted_file(api, reports_dir):
    import json

    persisted = saved_json(reports_dir, "2026-08-26", Kind.OUTLOOK_MARKET, "market")
    j = api.get("/api/market-outlook").json()
    assert j["gaps"] == [] and j["outlook"]["summary"] == persisted["summary"]
    assert [v["segment"] for v in j["outlook"]["views"]] == [v["segment"] for v in persisted["views"]]
    assert j["outlook"]["evidence_ids"] == persisted["evidence_ids"]


def test_market_outlook_missing_is_a_gap(seeded_db, tmp_path):
    from fastapi.testclient import TestClient

    from rm_dashboard.api import create_app

    mark_run(tmp_path, "2026-08-26")
    j = TestClient(create_app(seeded_db, tmp_path)).get("/api/market-outlook").json()
    assert j["outlook"] is None and j["gaps"]


def test_events_are_the_event_log_up_to_as_of(api):
    ev = api.get("/api/events").json()["events"]
    assert len(ev) == 16 and [e["event_date"] for e in ev] == sorted(e["event_date"] for e in ev)
    assert all(e["reach"]["derived"] is True for e in ev)


def test_energy_event_reaches_held_energy_instruments_and_their_clients(api):
    ev = {e["event_date"]: e for e in api.get("/api/events").json()["events"]}
    e = ev["2026-03-02"]  # Energy, transport, shipping
    assert "Energy" in e["reach"]["matched_channels"] and e["reach"]["instruments"] and e["reach"]["clients"]
    ids = {i["instrument_id"] for i in e["reach"]["instruments"]}
    holders = {h["client_id"] for iid in ids for h in api.get(f"/api/instruments/{iid}").json()["holders"]}
    assert {c["client_id"] for c in e["reach"]["clients"]} == holders
    assert all(i["held_usd"] > 0 for i in e["reach"]["instruments"])


def test_a_specific_channel_does_not_pull_in_the_general_one(api):
    ev = {e["event_date"]: e for e in api.get("/api/events").json()["events"]}
    european, duration = ev["2026-04-30"]["reach"], ev["2026-06-19"]["reach"]  # European fixed income / Long-duration fixed income
    ids = {i["instrument_id"] for i in european["instruments"]}
    rows = {r["instrument_id"]: r for r in api.get("/api/instruments").json()}
    assert ids and all(rows[i]["asset_class"] == "Fixed Income" and rows[i]["region"] == "Europe" for i in ids)
    assert ids < {i["instrument_id"] for i in duration["instruments"]}
    assert len(european["clients"]) < len(duration["clients"])


def test_unrecognised_channels_are_reported_not_guessed(api):
    ev = {e["event_date"]: e for e in api.get("/api/events").json()["events"]}
    assert "inflation-sensitive assets" in ev["2026-03-12"]["reach"]["unmatched_channels"]


def test_reach_for_uses_only_held_instruments():
    held = [
        {"instrument_id": "A", "instrument_name": "Oil Co", "sector": "Energy", "sub_asset_class": "", "asset_class": "Equity",
         "region": "Global", "underlying_reference": None},
        {"instrument_id": "B", "instrument_name": "Bond", "sector": "Sovereign", "sub_asset_class": "", "asset_class": "Fixed Income",
         "region": "Europe", "underlying_reference": None},
    ]
    matched, unmatched, hit = reach_for("Energy, European fixed income, mystery", held)
    assert matched == ["Energy", "European fixed income"] and unmatched == ["mystery"]
    assert {i["instrument_id"] for i in hit} == {"A", "B"}
    assert reach_for("Duration", held)[2] == [held[1]]
    general = [{**held[1], "instrument_id": "C", "region": "Asia"}, held[1]]
    assert [i["instrument_id"] for i in reach_for("European fixed income", general)[2]] == ["B"]
    assert CHANNEL_RULES
