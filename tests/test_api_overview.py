from datetime import date

from rm_dashboard.api.overview import meeting_prep
from rm_dashboard.api.urgency import IMPORTANCE_BASE, urgency

AS_OF = date(2026, 8, 26)


def test_a_higher_tier_always_wins():
    top_of_lower = urgency("high", "immediate", AS_OF, AS_OF)
    assert urgency("critical", "none", None, AS_OF) > top_of_lower
    assert urgency("high", "none", None, AS_OF) > urgency("medium", "immediate", AS_OF, AS_OF)
    assert urgency("medium", "none", None, AS_OF) > urgency("low", "immediate", AS_OF, AS_OF)


def test_urgency_orders_by_tier_then_horizon_then_due_date():
    assert urgency("high", "immediate", None, AS_OF) > urgency("high", "within_30_days", None, AS_OF) \
        > urgency("high", "within_90_days", None, AS_OF) > urgency("high", "later", None, AS_OF)


def test_dated_action_is_more_urgent_than_undated_with_same_tier():
    dated = urgency("high", "within_90_days", date(2026, 10, 1), AS_OF)
    undated = urgency("high", "none", None, AS_OF)
    assert dated > undated


def test_due_term_fades_and_overdue_takes_the_full_term():
    base = IMPORTANCE_BASE["high"]
    near = urgency("high", "later", date(2026, 9, 1), AS_OF)
    mid = urgency("high", "later", date(2027, 2, 26), AS_OF)
    far = urgency("high", "later", date(2028, 1, 1), AS_OF)
    overdue = urgency("high", "later", date(2026, 8, 1), AS_OF)
    assert overdue >= near > mid > far == base
    assert overdue == base + 4.0


def test_overview_committed_run(api):
    r = api.get("/api/overview")
    assert r.status_code == 200
    o = r.json()
    assert o["as_of"] == "2026-08-26" and o["rm_name"] == "Priscilla Ong" and o["status"] == "partial"
    assert len(o["actions"]) == 33 and len(o["client_rows"]) == 20 and len(o["clients"]) == 20
    assert o["clients_without_actions"] and {c["reason"] for c in o["clients_without_actions"]} <= {
        "actions_missing", "report_missing", "no_action_needed"}
    assert [a["rank"] for a in o["actions"]] == sorted(a["rank"] for a in o["actions"])
    assert sum(g["count"] for g in o["by_category"]) == 33
    assert sum(a["origin"] == "coverage" for a in o["actions"]) == 17  # one placeholder per client without actions
    assert sum(c["action_count"] for c in o["client_rows"]) == 16


def test_every_action_carries_aum_band_and_urgency(api):
    o = api.get("/api/overview").json()
    rows = {c["client_id"]: c for c in o["client_rows"]}
    for a in o["actions"]:
        assert a["client_aum_usd"] == rows[a["client_id"]]["aum_usd"] > 0
        assert a["wealth_band"] in ("HNW", "UHNW") and 0 < a["urgency"] <= 100
    for c in o["client_rows"]:
        mine = [a["urgency"] for a in o["actions"] if a["client_id"] == c["client_id"] and a["origin"] == "client_actions"]
        assert c["max_urgency"] == (max(mine) if mine else 0.0) and c["action_count"] == len(mine)


def test_source_refs_are_resolved(api):
    o = api.get("/api/overview").json()
    refs = [r for a in o["actions"] for r in a["refs"]]
    pf = next(r for r in refs if r["ref"] == "CL-0001/PF-0001#f8")
    assert pf["client_id"] == "CL-0001" and pf["portfolio_id"] == "PF-0001" and pf["claim"] and pf["evidence_ids"]
    assert all(r["client_id"].startswith("CL-") for r in refs)


def test_meeting_prep_lists_near_actions_and_due_kyc(api):
    mp = api.get("/api/overview").json()["meeting_prep"]
    assert mp["from_date"] == "2026-08-26" and mp["to_date"] == "2026-09-09"
    by = {c["client_id"]: c for c in mp["clients"]}
    assert any(i["kind"] == "action" and i["status"] == "immediate" for i in by["CL-0002"]["items"])
    kyc = next(i for i in by["CL-0011"]["items"] if i["kind"] == "kyc")
    assert kyc["status"] == "due" and kyc["due_date"] == "2026-08-31"
    assert by["CL-0011"]["latest_note"]["note_id"] == "N-015"


def test_meeting_prep_marks_overdue_kyc(api):
    ctx = api.app.state.read
    mp = meeting_prep(ctx, date(2026, 10, 20), [], {})
    kyc = {c.client_id: i for c in mp.clients for i in c.items if i.kind == "kyc"}
    assert kyc["CL-0011"].status == "overdue" and kyc["CL-0008"].status == "overdue"
    assert all(i.status != "overdue" or i.due_date < date(2026, 10, 20) for i in kyc.values())


def test_evidence_with_citations(api):
    r = api.get("/api/evidence/ev_09ac6f68f9808003")
    assert r.status_code == 200
    j = r.json()
    assert j["result"]["evidence_id"] == "ev_09ac6f68f9808003" and j["result"]["computation"]["tool"]
    refs = {c["ref"] for c in j["cited_by"]}
    assert "CL-0001#f10" in refs and "CL-0001-A1" in refs
    pf = next(c for c in j["cited_by"] if c["ref"] == "CL-0001/PF-0001#f8")
    assert pf["client_id"] == "CL-0001" and pf["portfolio_id"] == "PF-0001"


def test_unknown_evidence_is_404(api):
    assert api.get("/api/evidence/ev_does_not_exist").status_code == 404


def test_market_evidence_cites_the_view(api):
    r = api.get("/api/evidence/ev_d76c116a1ea241e1")
    assert r.status_code == 200 and any(c["kind"] == "market_view" for c in r.json()["cited_by"])
