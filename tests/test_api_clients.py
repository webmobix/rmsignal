import pytest


def _client(api, cid):
    r = api.get(f"/api/clients/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


def test_client_list_covers_the_whole_book(api):
    rows = api.get("/api/clients").json()
    assert len(rows) == 20
    by = {r["client_id"]: r for r in rows}
    assert by["CL-0001"]["portfolio_count"] == 2 and by["CL-0017"]["portfolio_count"] == 3
    assert by["CL-0001"]["action_count"] == 5 and by["CL-0001"]["max_urgency"] > 0
    assert by["CL-0001"]["top_importance"] == "high" and by["CL-0001"]["report_status"] == "partial"
    assert by["CL-0004"]["action_count"] == 0 and by["CL-0004"]["max_urgency"] == 0 and by["CL-0004"]["top_importance"] is None
    assert sum(r["action_count"] for r in rows) == 16 and sum(r["action_count"] > 0 for r in rows) == 3
    assert all(r["aum_usd"] > 0 for r in rows)


def test_total_equals_sum_of_portfolios_for_a_multi_portfolio_client(api):
    j = _client(api, "CL-0017")
    assert len(j["portfolios"]) == 3
    assert j["consolidated"]["total_aum_usd"] == pytest.approx(sum(p["aum_usd"] for p in j["portfolios"]))
    assert sum(s["value_usd"] for s in j["consolidated"]["allocation"]) == pytest.approx(j["consolidated"]["total_aum_usd"])
    assert sum(s["weight_pct"] for s in j["consolidated"]["allocation"]) == pytest.approx(100)
    assert j["consolidated"]["total_aum_usd"] == pytest.approx(api.get("/api/clients").json()[16]["aum_usd"])


def test_single_portfolio_client_consolidates_to_the_portfolio(api):
    j = _client(api, "CL-0004")
    assert len(j["portfolios"]) == 1
    assert j["consolidated"]["total_aum_usd"] == pytest.approx(j["portfolios"][0]["aum_usd"])
    pf = api.get(f"/api/portfolios/{j['portfolios'][0]['portfolio_id']}").json()
    assert pf["portfolio"]["aum_usd"] == pytest.approx(j["consolidated"]["total_aum_usd"])


def test_custody_account_has_no_mandate_but_counts_in_totals(api):
    j = _client(api, "CL-0001")
    status = {p["portfolio_id"]: p for p in j["portfolios"]}
    assert status["PF-0002"]["service_model"] == "Custody" and status["PF-0002"]["mandate_status"] == "no_mandate"
    assert status["PF-0002"]["aum_usd"] > 0
    assert j["consolidated"]["total_aum_usd"] == pytest.approx(sum(p["aum_usd"] for p in j["portfolios"]))
    pf = api.get("/api/portfolios/PF-0002").json()
    assert pf["bands"] == [] and "custody" in pf["position_limit"]["note"]


def test_consolidated_change_vs_previous_snapshot(api):
    k = _client(api, "CL-0001")["consolidated"]
    assert (k["snapshot_date"], k["previous_snapshot_date"]) == ("2026-08-26", "2026-06-30")
    assert k["change_usd"] == pytest.approx(k["total_aum_usd"] - k["previous_aum_usd"])
    assert k["change_pct"] == pytest.approx(k["change_usd"] / k["previous_aum_usd"] * 100)


def test_look_through_shows_structured_product_underlyings(api):
    k = _client(api, "CL-0001")["consolidated"]
    assert any(e["via_look_through"] for e in k["look_through"]) and k["hhi"] > 0
    assert len(k["top_positions"]) <= 10 and k["top_positions"][0]["value_usd"] >= k["top_positions"][-1]["value_usd"]


def test_liquidity_and_credit_in_consolidated(api):
    k = _client(api, "CL-0002")["consolidated"]
    assert k["liquidity"]["horizon_days"] == 365 and k["liquidity"]["assets_by_tier"]
    f = k["facilities"][0]
    assert f["current"]["ltv_pct"] < f["margin_call_ltv_pct"] and f["ltv_gap_pp"] == pytest.approx(
        f["margin_call_ltv_pct"] - f["current"]["ltv_pct"]) and len(f["history"]) == 5


def test_client_without_persisted_actions_gets_the_gap_and_a_baseline_row(api):
    j = _client(api, "CL-0004")
    assert any(g["description"].startswith("actions_missing") for g in j["gaps"])
    assert [a["origin"] for a in j["actions"]] == ["coverage"]  # the overview's own placeholder, not a client action
    row = next(c for c in api.get("/api/overview").json()["client_rows"] if c["client_id"] == "CL-0004")
    assert row["action_count"] == 0 and row["max_urgency"] == 0.0 and row["top_importance"] is None
    assert not any(g["description"].startswith("actions_missing") for g in _client(api, "CL-0001")["gaps"])


def test_missing_reconciliation_is_a_gap_not_an_error(api):
    j = _client(api, "CL-0017")
    assert any("reconciliation" in g["description"] for g in j["gaps"])
    assert all(n["verdict"] is None for n in j["notes"])


def test_actions_findings_and_contradicted_notes(api):
    j = _client(api, "CL-0001")
    assert len(j["actions"]) == 5 and all(a["client_id"] == "CL-0001" for a in j["actions"])
    assert j["findings"] and all(f["evidence_ids"] for f in j["findings"])
    assert any(f["portfolio_id"] == "PF-0001" for f in j["findings"])
    contradicted = next(n for n in j["notes"] if n["verdict"] == "contradicted")
    assert contradicted["evidence_ids"] and contradicted["finding_refs"]
    assert {n["verdict"] for n in j["notes"]} == {"consistent", "contradicted"}


def test_unknown_client_is_404(api):
    for path in ("", "/aum-history", "/snapshot-changes", "/scenarios"):
        assert api.get(f"/api/clients/CL-9999{path}").status_code == 404


def test_aum_history_has_five_points_and_events(api):
    j = api.get("/api/clients/CL-0001/aum-history").json()
    dates = [p["snapshot_date"] for p in j["total"]]
    assert dates == ["2025-12-31", "2026-02-27", "2026-03-31", "2026-06-30", "2026-08-26"]
    assert len(j["portfolios"]) == 2 and all(len(s["points"]) == 5 for s in j["portfolios"])
    for i, p in enumerate(j["total"]):
        assert p["aum_usd"] == pytest.approx(sum(s["points"][i]["aum_usd"] for s in j["portfolios"]))
    assert j["events"] and all("2025-12-31" <= e["event_date"] <= "2026-08-26" for e in j["events"])
    assert j["events"][0]["event_date"] == "2025-12-31"  # the covered range includes the first snapshot


def test_portfolio_out_of_band_names_weight_and_limit(api):
    j = api.get("/api/portfolios/PF-0005").json()
    assert j["portfolio"]["mandate_status"] == "out_of_band" and j["portfolio"]["breach_count"] >= 1
    flagged = [b for b in j["bands"] if b["out_of_band"]]
    assert {b["asset_class"] for b in flagged} == {"Fixed Income", "Equity"}
    for b in flagged:
        assert (b["weight_pct"] > b["max_pct"]) or (b["weight_pct"] < b["min_pct"])
    assert j["position_limit"]["breaches"] and j["position_limit"]["max_single_position_pct"]


def test_portfolio_detail_content(api):
    j = api.get("/api/portfolios/PF-0003").json()
    assert j["client_id"] == "CL-0002" and len(j["aum_history"]) == 5
    assert sum(h["weight_pct"] for h in j["holdings"]) == pytest.approx(100, abs=0.5)
    assert j["facilities"][0]["portfolio_id"] == "PF-0003" and j["facilities"][0]["history"]
    assert j["position_limit"]["largest_weight_pct"] == max(h["weight_pct"] for h in j["holdings"])


def test_unknown_portfolio_is_404(api):
    assert api.get("/api/portfolios/PF-9999").status_code == 404


def test_snapshot_changes_between_two_snapshots(api):
    j = api.get("/api/clients/CL-0001/snapshot-changes?from=2026-02-27&to=2026-03-31").json()
    assert (j["from_date"], j["to_date"]) == ("2026-02-27", "2026-03-31")
    assert any("Hormuz" in e["description"] for e in j["events"])
    assert all("2026-02-27" < e["event_date"] <= "2026-03-31" for e in j["events"])
    assert j["change_usd"] == pytest.approx(sum(p["change_usd"] for p in j["portfolios"]))
    assert j["total_to_usd"] - j["total_from_usd"] == pytest.approx(j["change_usd"])


def test_snapshot_changes_default_is_previous_snapshot_to_as_of(api):
    j = api.get("/api/clients/CL-0001/snapshot-changes").json()
    assert (j["from_date"], j["to_date"]) == ("2026-06-30", "2026-08-26")


def test_snapshot_changes_lists_added_removed_and_resized(api):
    kinds = set()
    for cid in ("CL-0001", "CL-0002", "CL-0017"):
        for frm, to in (("2025-12-31", "2026-08-26"), ("2026-02-27", "2026-03-31")):
            j = api.get(f"/api/clients/{cid}/snapshot-changes?from={frm}&to={to}").json()
            for p in j["portfolios"]:
                for pos in p["positions"]:
                    kinds.add(pos["change"])
                    if pos["change"] == "added":
                        assert pos["quantity_from"] is None and pos["change_usd"] == pytest.approx(pos["value_usd_to"])
                    if pos["change"] == "removed":
                        assert pos["quantity_to"] is None and pos["change_usd"] == pytest.approx(-pos["value_usd_from"])
    assert kinds <= {"added", "removed", "resized"} and kinds


@pytest.mark.parametrize("q", ["from=2026-03-31&to=2026-02-27", "from=2026-02-28&to=2026-03-31",
                               "from=2026-02-27&to=2026-04-01", "from=2026-03-31&to=2026-03-31"])
def test_snapshot_changes_invalid_snapshots_are_422(api, q):
    assert api.get(f"/api/clients/CL-0001/snapshot-changes?{q}").status_code == 422
