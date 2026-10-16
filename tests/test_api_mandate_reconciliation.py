import json
import shutil
from datetime import date

import pytest
from fastapi.testclient import TestClient

from rm_dashboard.agents import StubChatModel
from rm_dashboard.api import create_app
from rm_dashboard.mandate_reconciliation import BreachResult, MandateReconciliation, NoteQuote
from rm_dashboard.runners import open_registry, run_batch
from rm_dashboard.settings import Settings

AS_OF = date(2026, 8, 26)
WAIVER = "Client instructed an additional gold purchase. Suitability waiver on file."


@pytest.fixture(scope="module")
def run_dir(seeded_db, tmp_path_factory):
    out = tmp_path_factory.mktemp("api_reports")
    with open_registry(Settings(db_path=str(seeded_db), max_concurrency=4)) as reg:
        run_batch(reg, as_of=AS_OF, out_dir=out, client_ids=["CL-0001", "CL-0005", "CL-0007"], models=lambda role: StubChatModel(role=role))
    return out


def write(base, cid, results, status="complete"):
    d = base / AS_OF.isoformat() / "mandate-reconciliation"
    d.mkdir(exist_ok=True)
    (d / f"{cid}.json").write_text(MandateReconciliation(client_id=cid, as_of=AS_OF, status=status, results=results).model_dump_json())


def breach(pid, kind, key, status, notes=(), waiver=False):
    return BreachResult(portfolio_id=pid, kind=kind, key=key, evidence_id="ev_x", description=f"{key} breach", status=status,
                        rationale="r" if status != "no_note" else "", waiver_claimed=waiver,
                        notes=[NoteQuote(note_id=n, note_date=date(2026, 1, 22), quote=WAIVER) for n in notes])


@pytest.fixture
def api(seeded_db, run_dir, tmp_path):
    base = tmp_path / "reports"
    shutil.copytree(run_dir, base)
    write(base, "CL-0007", [breach("PF-0009", "band", "Commodities", "client_directed", ("N-010",), True),
                            breach("PF-0009", "band", "Fixed Income", "no_note")])
    return TestClient(create_app(seeded_db, base)), base


def rows(client, cid):
    return {p["portfolio_id"]: p for p in client.get(f"/api/clients/{cid}").json()["portfolios"]}


def test_reconciled_breach_is_listed_with_status_and_note_ids(api):
    client, _ = api
    pf = rows(client, "CL-0007")["PF-0009"]
    by = {r["key"]: r for r in pf["breach_reconciliation"]}
    assert pf["mandate_status"] == "out_of_band"
    assert (by["Commodities"]["status"], by["Commodities"]["note_ids"]) == ("client_directed", ["N-010"])
    assert by["Fixed Income"]["status"] == "no_note" and by["Fixed Income"]["note_ids"] == []
    assert by["Commodities"]["notes"] == []  # quotes are on the detail only


def test_detail_carries_the_quoted_notes_and_waiver_claim(api):
    client, _ = api
    j = client.get("/api/portfolios/PF-0009").json()
    r = next(x for x in j["breach_reconciliation"] if x["key"] == "Commodities")
    assert r["waiver_claimed"] is True and r["notes"][0]["quote"] == WAIVER and r["notes"][0]["note_id"] == "N-010"
    assert j["portfolio"]["mandate_status"] == "out_of_band"
    assert not any("mandate reconciliation" in g["description"] for g in j["gaps"])


def test_no_note_breach_is_plain_and_unreconciled_client_gets_a_gap(api):
    client, base = api
    detail = client.get("/api/portfolios/PF-0009").json()
    plain = next(x for x in detail["breach_reconciliation"] if x["key"] == "Fixed Income")
    assert plain["status"] == "no_note" and plain["notes"] == []
    # CL-0005 has no persisted mandate reconciliation: empty fields and a gap, not an error
    r = client.get("/api/clients/CL-0005")
    assert r.status_code == 200
    j = r.json()
    assert j["portfolios"][0]["breach_reconciliation"] == []
    assert any("no mandate reconciliation persisted for CL-0005" in g["description"] for g in j["gaps"])
    d = client.get("/api/portfolios/PF-0007").json()
    assert d["breach_reconciliation"] == [] and any("no mandate reconciliation persisted" in g["description"] for g in d["gaps"])


def test_exclusion_breaches_are_listed_with_their_status(api):
    client, base = api
    d = client.get("/api/portfolios/PF-0007").json()
    assert {b["instrument_id"] for b in d["exclusion_breaches"]} == {"SYN-EQ-0008", "SYN-ST-0105"}
    assert all(b["status"] == "no_note" and b["held"] == "direct" for b in d["exclusion_breaches"])
    assert d["portfolio"]["mandate_status"] == "out_of_band" and d["portfolio"]["breach_count"] >= 2
    write(base, "CL-0005", [breach("PF-0007", "exclusion", "SYN-EQ-0008", "contradicted", ("N-008",))])
    d = client.get("/api/portfolios/PF-0007").json()
    ex = {b["instrument_id"]: b for b in d["exclusion_breaches"]}
    assert (ex["SYN-EQ-0008"]["status"], ex["SYN-EQ-0008"]["note_ids"]) == ("contradicted", ["N-008"])
    assert ex["SYN-ST-0105"]["status"] == "no_note"


def test_custody_portfolio_has_no_breach_fields(api):
    client, _ = api
    pf = rows(client, "CL-0001")["PF-0002"]
    assert pf["mandate_status"] == "no_mandate" and pf["breach_reconciliation"] == [] and pf["breach_count"] == 0
    d = client.get("/api/portfolios/PF-0002").json()
    assert d["exclusion_breaches"] == [] and d["breach_reconciliation"] == []
    assert not any("mandate reconciliation" in g["description"] for g in d["gaps"])
