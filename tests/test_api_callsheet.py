import shutil
from datetime import date

import polars as pl
import pytest
from fastapi.testclient import TestClient

from rm_dashboard.agents import StubChatModel
from rm_dashboard.api import callsheet, create_app
from rm_dashboard.mandate_reconciliation import BreachResult, MandateReconciliation, NoteQuote
from rm_dashboard.runners import open_registry, run_batch
from rm_dashboard.settings import Settings
from rm_dashboard.store import Kind, as_store
from storehelp import mark_run

AS_OF = date(2026, 8, 26)
SECTIONS = ("performance", "mandate", "ownership", "bank_view", "events", "cash_credit", "conversation")
WAIVER = "Client instructed an additional gold purchase. Suitability waiver on file."


@pytest.fixture(scope="module")
def run_dir(seeded_db, outlook_dir, tmp_path_factory):
    out = tmp_path_factory.mktemp("callsheet_reports")
    shutil.copytree(outlook_dir, out, dirs_exist_ok=True)
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as reg:
        run_batch(reg, as_of=AS_OF, store=out, client_ids=["CL-0001", "CL-0005", "CL-0007", "CL-0017"],
                  models=lambda role: StubChatModel(role=role))
    return out


def write_mandate(base, cid, results):
    as_store(base).put(AS_OF, Kind.MANDATE_RECONCILIATION, cid,
                       MandateReconciliation(client_id=cid, as_of=AS_OF, status="complete", results=results).model_dump_json())


@pytest.fixture
def env(seeded_db, run_dir, tmp_path):
    base = tmp_path / "reports"
    shutil.copytree(run_dir, base)
    write_mandate(base, "CL-0007", [
        BreachResult(portfolio_id="PF-0009", kind="band", key="Commodities", evidence_id="ev_x", description="Commodities breach",
                     status="client_directed", rationale="r", waiver_claimed=True,
                     notes=[NoteQuote(note_id="N-010", note_date=date(2026, 1, 22), quote=WAIVER)]),
        BreachResult(portfolio_id="PF-0009", kind="band", key="Fixed Income", evidence_id="ev_x", description="FI breach")])
    mark_run(base, "2026-03-31")  # a run for the earlier date, so the API accepts it
    return TestClient(create_app(seeded_db, base)), base


def sheet(client, pid, as_of="2026-08-26"):
    r = client.get(f"/api/portfolios/{pid}/call-sheet", params={"as_of": as_of})
    assert r.status_code == 200, r.text
    return r.json()


# ---- 1.1 endpoint ---------------------------------------------------------------------------------------------
def test_unknown_portfolio_is_404(env):
    assert env[0].get("/api/portfolios/PF-9999/call-sheet", params={"as_of": "2026-08-26"}).status_code == 404


def test_full_portfolio_has_all_seven_sections(env):
    j = sheet(env[0], "PF-0009")
    assert all(s in j and "gaps" in j[s] for s in SECTIONS)
    assert j["portfolio_id"] == "PF-0009" and j["client_id"] == "CL-0007" and j["as_of"] == "2026-08-26"


def test_a_failing_builder_leaves_the_other_sections_intact(env, monkeypatch):
    client, _ = env
    good = sheet(client, "PF-0009")

    def boom(*a, **k):
        raise RuntimeError("outlook store unreadable")

    monkeypatch.setattr(callsheet, "bank_view", boom)
    j = sheet(client, "PF-0009")
    assert j["bank_view"]["entries"] == [] and "could not be built" in j["bank_view"]["gaps"][0]["description"]
    assert "outlook store unreadable" in j["bank_view"]["gaps"][0]["description"]
    for s in SECTIONS:
        if s != "bank_view":
            assert j[s] == good[s]


# ---- 1.2 performance --------------------------------------------------------------------------------------------
def test_contributors_equal_the_holdings_data(env, pit_repo):
    j = sheet(env[0], "PF-0009")["performance"]
    now = pit_repo.holdings(as_of=AS_OF, portfolio_id="PF-0009").frame
    prev = pit_repo.holdings(as_of=date(2026, 6, 30), portfolio_id="PF-0009").frame
    v1 = dict(now.select("instrument_id", "market_value_usd").iter_rows())
    v0 = dict(prev.select("instrument_id", "market_value_usd").iter_rows())
    assert j["previous_snapshot_date"] == "2026-06-30" and j["aum_usd"] == pytest.approx(sum(v1.values()))
    assert j["change_usd"] == pytest.approx(sum(v1.values()) - sum(v0.values()))
    assert 0 < len(j["contributors"]) <= 5
    assert abs(j["contributors"][0]["change_usd"]) >= abs(j["contributors"][-1]["change_usd"])
    for c in j["contributors"]:
        assert c["change_usd"] == pytest.approx(v1.get(c["instrument_id"], 0.0) - v0.get(c["instrument_id"], 0.0))
    assert all(e["event_date"] > "2026-06-30" and e["event_date"] <= "2026-08-26" and e["event_id"].startswith("EVT-") for e in j["events"])


def test_findings_concern_the_portfolio_and_a_missing_report_is_a_gap(env):
    client, _ = env
    j = sheet(client, "PF-0009")["performance"]
    assert j["findings"] and all("PF-0009" in f["ref"] for f in j["findings"])
    missing = sheet(client, "PF-0003")["performance"]  # CL-0002 has no persisted report in this fixture
    assert missing["findings"] == [] and any("no analysis report" in g["description"] for g in missing["gaps"])


# ---- 1.3 cash and credit, conversation -----------------------------------------------------------------------------
def test_facility_and_client_level_liquidity(env):
    j = sheet(env[0], "PF-0016")["cash_credit"]
    assert [f["facility_id"] for f in j["facilities"]] == ["CF-0002"] and j["facilities"][0]["current"]["ltv_pct"] > 0
    assert "Client level" in j["client_level_note"]
    assert j["client_liquidity"] is not None and j["client_liquidity"]["items"]
    assert sheet(env[0], "PF-0009")["cash_credit"]["facilities"] == []


def test_notes_are_point_in_time_and_newest_first(env):
    client, _ = env
    now = sheet(client, "PF-0001")["conversation"]
    assert [n["note_id"] for n in now["notes"]] == ["N-002", "N-001"] and now["scope"] == "client" and now["note_total"] == 2
    early = sheet(client, "PF-0001", "2026-03-31")["conversation"]
    assert [n["note_id"] for n in early["notes"]] == ["N-001"]


def test_no_notes_is_not_a_gap(env):
    client, base = env
    mark_run(base, "2026-01-01")
    c = sheet(client, "PF-0001", "2026-01-01")["conversation"]
    assert c["notes"] == [] and c["note_total"] == 0 and c["gaps"] == []


def test_open_commitments_are_client_level(env):
    c = sheet(env[0], "PF-0020")["conversation"]
    assert c["commitments"] and all(x["uncalled"] > 0 for x in c["commitments"])


# ---- 2.1 bank view ---------------------------------------------------------------------------------------------------
def test_every_position_is_listed_and_missing_outlooks_are_explicit(env):
    client, base = env
    detail = client.get("/api/portfolios/PF-0009", params={"as_of": "2026-08-26"}).json()
    j = sheet(client, "PF-0009")["bank_view"]
    assert [e["instrument_id"] for e in j["entries"]] == [h["instrument_id"] for h in detail["holdings"]]
    victim = j["entries"][0]["instrument_id"]
    as_store(base).delete_prefix(AS_OF, Kind.OUTLOOK_INSTRUMENT, victim)
    j2 = sheet(client, "PF-0009")["bank_view"]
    e = next(x for x in j2["entries"] if x["instrument_id"] == victim)
    assert len(j2["entries"]) == len(j["entries"]) and e["outlook"] is None
    assert any(g["description"].startswith("outlook_missing") and victim in g["description"] for g in j2["gaps"])


def test_older_outlook_carries_its_own_date_and_market_views_are_unchanged(env):
    client, base = env
    j = sheet(client, "PF-0009")["bank_view"]
    entry = next(x for x in j["entries"] if x["outlook"])
    iid = entry["instrument_id"]
    assert entry["outlook"]["older_than_as_of"] is False and entry["outlook"]["as_of"] == "2026-08-26"
    store = as_store(base)
    stored = store.get(AS_OF, Kind.OUTLOOK_INSTRUMENT, iid)
    store.put(date(2026, 6, 30), Kind.OUTLOOK_INSTRUMENT, iid, stored.replace('"as_of": "2026-08-26"', '"as_of": "2026-06-30"', 1))
    store.delete_prefix(AS_OF, Kind.OUTLOOK_INSTRUMENT, iid)
    again = next(x for x in sheet(client, "PF-0009")["bank_view"]["entries"] if x["instrument_id"] == iid)
    assert again["outlook"]["older_than_as_of"] is True and again["outlook"]["as_of"] == "2026-06-30"
    import json
    assert again["outlook"]["market_context"] == json.loads(stored)["market_context"]
    assert again["outlook"]["view"]["direction"] == json.loads(stored)["view"]["direction"]


# ---- 2.2 events --------------------------------------------------------------------------------------------------------
def test_energy_event_matches_an_energy_holding_and_later_events_are_excluded(env):
    client, _ = env
    j = sheet(client, "PF-0007")["events"]
    energy = [e for e in j["events"] if "energy" in e["primary_transmission"].lower()]
    assert energy
    hit = next(i for e in energy for i in e["instruments"] if i["instrument_id"] == "SYN-EQ-0008")
    assert any(m["field"] in ("sector", "sub_asset_class", "instrument_name") for m in hit["matched_on"])
    assert all(e["event_date"] <= "2026-08-26" for e in j["events"])
    early = sheet(client, "PF-0007", "2026-03-31")["events"]
    assert all(e["event_date"] <= "2026-03-31" for e in early["events"])
    assert len(early["events"]) <= len(j["events"])
    sev = {"High": 0, "Medium": 1, "Low": 2}
    assert [sev.get(e["severity"], 3) for e in j["events"]] == sorted(sev.get(e["severity"], 3) for e in j["events"])


# ---- 2.3 seeded portfolios ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("pid", ["PF-0009", "PF-0017"])
def test_seeded_portfolios_list_every_position(env, pid):
    client, _ = env
    detail = client.get(f"/api/portfolios/{pid}", params={"as_of": "2026-08-26"}).json()
    j = sheet(client, pid)["bank_view"]
    assert {e["instrument_id"] for e in j["entries"]} == {h["instrument_id"] for h in detail["holdings"]}
    missing = [e["instrument_id"] for e in j["entries"] if e["outlook"] is None]
    assert sorted(g["subject"] for g in j["gaps"]) == sorted(missing)


# ---- 3.1 ownership -------------------------------------------------------------------------------------------------------
def test_ownership_equals_the_portfolio_detail(env):
    client, _ = env
    for pid in ("PF-0009", "PF-0017"):
        detail = client.get(f"/api/portfolios/{pid}", params={"as_of": "2026-08-26"}).json()
        o = sheet(client, pid)["ownership"]
        assert o["sector_exposure"] == detail["sector_exposure"]
        assert set(o["unclassified_pct"]) == {"direct", "look_through"}


# ---- 3.2 mandate ---------------------------------------------------------------------------------------------------------
def test_waiver_claimed_breach_quotes_the_note_and_stays_a_breach(env):
    j = sheet(env[0], "PF-0009")["mandate"]
    r = next(x for x in j["breach_reconciliation"] if x["key"] == "Commodities")
    assert r["status"] == "client_directed" and r["waiver_claimed"] and r["notes"][0]["quote"] == WAIVER
    assert any(b["asset_class"] == "Commodities" and b["out_of_band"] for b in j["bands"])
    assert not any("mandate reconciliation" in g["description"] for g in j["gaps"])


def test_no_note_breach_has_no_label_and_no_gap(env):
    j = sheet(env[0], "PF-0009")["mandate"]
    r = next(x for x in j["breach_reconciliation"] if x["key"] == "Fixed Income")
    assert r["status"] == "no_note" and r["note_ids"] == [] and j["gaps"] == []


def test_missing_mandate_reconciliation_is_a_gap_and_exclusions_are_shown(env):
    j = sheet(env[0], "PF-0007")["mandate"]
    assert j["breach_reconciliation"] == [] and any("no mandate reconciliation persisted" in g["description"] for g in j["gaps"])
    assert {b["instrument_id"] for b in j["exclusion_breaches"]} == {"SYN-EQ-0008", "SYN-ST-0105"}


def test_custody_portfolio_states_that_no_mandate_applies(env):
    j = sheet(env[0], "PF-0002")["mandate"]
    assert j["applicable"] is False and "custody" in j["statement"].lower() and j["bands"] == []
    assert j["breach_reconciliation"] == [] and j["exclusion_breaches"] == []


def test_open_actions_linked_to_the_portfolio(env, seeded_db):
    from rm_dashboard.runners.actions import run_actions
    from rm_dashboard.runners.overview import run_overview

    client, base = env
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=2)) as reg:
        run_actions(reg, as_of=AS_OF, store=base, client_ids=["CL-0007"], models=lambda role: StubChatModel(role=role))
        run_overview(reg, as_of=AS_OF, store=base, models=lambda role: StubChatModel(role=role))
    j = sheet(client, "PF-0009")["mandate"]
    assert j["open_actions"], j
    assert any(a["category"] == "mandate_drift" and a["importance"] in ("high", "critical") for a in j["open_actions"])
    assert sheet(client, "PF-0001")["mandate"]["open_actions"] == []
