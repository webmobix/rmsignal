"""The API document names every endpoint and matches the constants and shapes it states."""

import re
from pathlib import Path

from rm_dashboard.api.urgency import HORIZON_BONUS, IMPORTANCE_BASE

DOC = (Path(__file__).parent.parent / "docs" / "api.md").read_text()


def _doc_paths() -> set[str]:
    return set(re.findall(r"`GET (/api/[^`\s?]+)", DOC))


def test_every_documented_endpoint_exists(api):
    paths = api.get("/openapi.json").json()["paths"]
    missing = {p for p in _doc_paths() if p not in paths}
    assert not missing


def test_every_read_endpoint_is_documented(api):
    paths = api.get("/openapi.json").json()["paths"]
    read = {p for p in paths if p.startswith("/api/") and not p.startswith("/api/sources")}
    assert read <= _doc_paths(), read - _doc_paths()


def test_urgency_table_matches_the_code():
    for tier, base in IMPORTANCE_BASE.items():
        assert re.search(rf"`{tier}` \| {base:g} \|", DOC), tier
    for horizon, bonus in HORIZON_BONUS.items():
        if horizon in ("later", "none"):
            continue
        assert re.search(rf"`{horizon}` \| {bonus:g} \|", DOC), horizon


def test_documented_overview_fields_exist(api):
    o = api.get("/api/overview").json()
    for key in ("client_rows", "total_aum_usd", "clients_without_actions", "by_category"):
        assert key in o and f"`{key}`" in DOC
    a = o["actions"][0]
    for key in ("client_aum_usd", "wealth_band", "urgency", "refs"):
        assert key in a and f"`{key}`" in DOC
    e = api.get("/api/evidence/ev_09ac6f68f9808003").json()
    assert {"result", "cited_by"} <= set(e)


def test_documented_client_fields_exist(api):
    j = api.get("/api/clients/CL-0001").json()
    for key in ("consolidated", "portfolios", "actions", "findings", "notes"):
        assert key in j and f"`{key}`" in DOC
    for key in ("total_aum_usd", "previous_aum_usd", "change_usd", "change_pct", "allocation", "currency_exposure",
                "top_positions", "look_through", "hhi", "liquidity", "facilities"):
        assert key in j["consolidated"] and f"`{key}`" in DOC
    for key in ("aum_usd", "aum_base", "change_pct", "mandate_status", "breach_count"):
        assert key in j["portfolios"][0] and f"`{key}`" in DOC
    for status in ("in_band", "out_of_band", "no_mandate"):
        assert f"`{status}`" in DOC
    row = api.get("/api/clients").json()[0]
    for key in row:
        assert f"`{key}`" in DOC, key


def test_documented_history_and_portfolio_fields_exist(api):
    h = api.get("/api/clients/CL-0001/aum-history").json()
    assert {"total", "portfolios", "events"} <= set(h) and "`total`" in DOC and "`events`" in DOC
    s = api.get("/api/clients/CL-0001/snapshot-changes").json()
    for key in ("aum_usd_from", "positions", "events"):
        assert key in s["portfolios"][0] or key in s
    for word in ("added", "removed", "resized", "pnl_base_from", "from", "to"):
        assert f"`{word}" in DOC, word
    p = api.get("/api/portfolios/PF-0005").json()
    for key in ("bands", "position_limit", "holdings", "facilities"):
        assert key in p and f"`{key}`" in DOC
    for key in ("min_pct", "target_pct", "max_pct", "weight_pct", "out_of_band", "max_single_position_pct"):
        assert f"`{key}`" in DOC


def test_documented_instrument_and_event_fields_exist(api):
    row = api.get("/api/instruments").json()[0]
    for key in row:
        assert f"`{key}`" in DOC, key
    d = api.get("/api/instruments/SYN-SP-0501").json()
    for key in ("instrument", "underlying_reference", "sustainability_excluded", "concentration_limit_applies",
                "price_path", "holders", "outlook"):
        assert key in d and f"`{key}`" in DOC
    ev = api.get("/api/events").json()["events"][0]
    for key in list(ev) + list(ev["reach"]):
        assert f"`{key}`" in DOC, key
    assert "outlook_missing" in DOC and set(api.get("/api/market-outlook").json()) == {"as_of", "outlook", "gaps"}


def test_channel_table_lists_every_rule():
    from rm_dashboard.api.market import CHANNEL_RULES

    table = DOC.split("| Channel text contains |")[1]
    assert table.count("\n| ") >= len(CHANNEL_RULES)


def test_documented_scenario_fields_exist(api):
    r = api.get("/api/clients/CL-0001/scenarios").json()["scenarios"][0]
    for key in r:
        assert f"`{key}`" in DOC, key
    for key in ("collateral", "bands", "positions", "channels"):
        assert f"`{key}`" in DOC
    for key in api.get("/api/scenarios").json()["scenarios"][0]:
        assert f"`{key}`" in DOC, key
    assert "ScenarioProvider" in DOC and "placeholder" in DOC
