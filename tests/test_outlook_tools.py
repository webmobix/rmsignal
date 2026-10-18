from datetime import date

import pytest


def call(registry, name, as_of="2026-08-26", **args):
    return registry.toolbox("test", registry.names()).call(name, {"as_of": as_of, **args})


# ---- market.history ---------------------------------------------------------------------
def test_market_history_has_a_value_per_snapshot(registry):
    r = call(registry, "market.history")
    assert r.status == "ok" and r.effective_snapshot_date == date(2026, 8, 26)
    spx = next(s for s in r.data if s["series_id"] == "SPX")
    assert [v["snapshot_date"] for v in spx["values"]] == sorted(v["snapshot_date"] for v in spx["values"])
    assert len(spx["values"]) == 5 and spx["category"] == "Equity index"


def test_market_history_has_no_look_ahead(registry):
    r = call(registry, "market.history", as_of="2026-03-31")
    dates = {v["snapshot_date"] for s in r.data for v in s["values"]}
    assert max(dates) == date(2026, 3, 31) and len(dates) == 3


def test_market_history_before_first_snapshot(registry):
    r = call(registry, "market.history", as_of="2025-12-30")
    assert r.status == "insufficient_data" and not r.data


# ---- event ids ----------------------------------------------------------------------------
def test_events_and_news_carry_the_same_stable_ids(registry):
    ev = call(registry, "events.list")
    news = call(registry, "news.list")
    ids = [e["event_id"] for e in ev.data]
    assert ids == [n["event_id"] for n in news.data["news"]] and len(set(ids)) == len(ids)
    assert all(i.startswith("EVT-" + str(e["event_date"])) for i, e in zip(ids, ev.data))


def test_event_ids_do_not_change_when_later_events_exist(registry):
    early = {e["event_id"] for e in call(registry, "events.list", as_of="2026-03-31").data}
    late = {e["event_id"] for e in call(registry, "events.list").data}
    assert early < late


# ---- analytics.market_trend --------------------------------------------------------------
def trend(registry, **kw):
    r = call(registry, "analytics.market_trend", **kw)
    return r, {s["series_id"]: s for s in (r.data["series"] if r.data else [])}


def test_market_trend_values_on_sample(registry):
    r, by = trend(registry)
    assert r.status == "ok" and r.data["snapshots"] == 5 and r.data["latest_snapshot_date"] == date(2026, 8, 26)
    spx = by["SPX"]
    assert spx["latest"] == 7530.0 and spx["previous"] == 7410.0 and spx["first"] == 6902.0
    assert spx["vs_previous"] == {"change": 120.0, "change_pct": 1.62}
    assert spx["vs_first"]["change_pct"] == 9.1
    brent = by["BRENT_USD_BBL"]
    assert brent["vs_previous"]["change"] == 5.5 and brent["vs_first"]["change_pct"] == 47.1
    assert r.computation.method.startswith("Per market series")


def test_market_trend_with_one_snapshot_is_insufficient_history(registry):
    r, by = trend(registry, as_of="2025-12-31")
    assert r.status == "insufficient_history" and "2 snapshots" in r.reason
    assert by["SPX"]["latest"] == 6902.0 and "vs_previous" not in by["SPX"]


def test_market_trend_before_first_snapshot(registry):
    r, _ = trend(registry, as_of="2025-12-30")
    assert r.status == "insufficient_data"


# ---- outlook.previous_market -------------------------------------------------------------
import dataclasses

from rm_dashboard.outlook import Change, MarketOutlook, OutlookInputs, Reason, View
from rm_dashboard.outlook.store import OutlookStore
from rm_dashboard.tools import ToolRegistry


def outlook(as_of, direction="neutral"):
    v = View(segment="overall", direction=direction, confidence="medium", rationale="steady",
             drivers=[Reason(claim="Equities rose.", evidence_ids=["ev_1"])], change=Change(kind="new"))
    return MarketOutlook(as_of=as_of, status="complete", views=[v], inputs=OutlookInputs(event_count=2))


@pytest.fixture
def with_reports(registry, tmp_path):
    store = OutlookStore(tmp_path)
    for d in ("2026-03-31", "2026-06-30", "2026-08-26"):
        store.save_market(outlook(d, "negative" if d == "2026-06-30" else "neutral"), [])
    return ToolRegistry(dataclasses.replace(registry.ctx, artifacts=tmp_path))


def test_previous_market_is_the_latest_strictly_earlier(with_reports):
    r = call(with_reports, "outlook.previous_market", as_of="2026-08-26")
    assert r.status == "ok" and r.data["previous_as_of"] == "2026-06-30"
    assert r.data["views"][0]["direction"] == "negative"
    assert [f.code for f in r.flags] == ["prior_view"]


def test_previous_market_never_returns_a_later_outlook(with_reports):
    r = call(with_reports, "outlook.previous_market", as_of="2026-03-31")
    assert r.status == "no_data" and "first outlook" in r.reason and r.data is None
    r = call(with_reports, "outlook.previous_market", as_of="2026-07-15")
    assert r.data["previous_as_of"] == "2026-06-30"


def test_previous_market_without_an_artifact_store(registry):
    r = call(registry, "outlook.previous_market")
    assert r.status == "no_data" and "artifact store" in r.reason


def test_previous_view_offers_no_evidence_ids(with_reports):
    r = call(with_reports, "outlook.previous_market", as_of="2026-08-26")
    assert "ev_1" not in str(r.data)


# ---- instruments.context ------------------------------------------------------------------
def context(registry, iid, **kw):
    return call(registry, "instruments.context", instrument_id=iid, **kw)


def test_context_for_an_equity_fund_with_peers(registry):
    r = context(registry, "SYN-EQ-0003")
    d = r.data
    assert r.status == "ok" and d["instrument"]["sector"] == "Information Technology"
    assert [p["price"] for p in d["price_path"]][-1] == 592.1 and len(d["price_path"]) == 5
    assert d["summary"]["vs_previous_pct"] == 3.23 and d["summary"]["snapshots"] == 5
    assert d["peers"]["basis"] == "sector" and {m["instrument_id"] for m in d["peers"]["members"]} == {"SYN-ST-0102", "SYN-ST-0103"}
    avg = d["peers"]["group_avg_vs_previous_pct"]
    assert d["peers"]["relative_vs_previous_pp"] == round(d["summary"]["vs_previous_pct"] - avg, 2)
    assert "SYN-EQ-0003" not in {m["instrument_id"] for m in d["peers"]["members"]}


def test_context_for_a_gold_linked_instrument(registry):
    d = context(registry, "SYN-CM-0401").data
    assert d["instrument"]["sector"] == "Gold" and d["peers"]["basis_value"] == "Gold"
    assert [m["instrument_id"] for m in d["peers"]["members"]] == ["SYN-CM-0402"]
    assert d["summary"]["latest"] == 4622.6


def test_context_for_an_instrument_without_peers(registry):
    r = context(registry, "SYN-AL-0303")
    assert r.status == "ok" and r.data["peers"]["members"] == [] and r.data["peers"]["group_avg_vs_previous_pct"] is None
    assert r.data["peers"]["relative_vs_previous_pp"] is None


def test_context_with_generic_sector_uses_the_sub_asset_class(registry):
    d = context(registry, "SYN-CA-0601").data
    assert d["peers"]["basis"] == "sub_asset_class" and d["peers"]["basis_value"] == "Deposit"
    assert all(m["instrument_id"].startswith("SYN-CA-") for m in d["peers"]["members"])


def test_context_says_which_risk_statistics_the_history_cannot_give(registry):
    stats = context(registry, "SYN-EQ-0001").data["risk_statistics"]
    assert {k: v["status"] for k, v in stats.items()} == {"volatility": "insufficient_history", "max_drawdown": "insufficient_history"}
    assert stats["volatility"]["value"] is None and stats["volatility"]["points_available"] == 5


def test_context_respects_the_date(registry):
    early = context(registry, "SYN-EQ-0001", as_of="2026-03-31")
    assert len(early.data["price_path"]) == 3 and early.data["summary"]["latest_date"] == date(2026, 3, 31)
    one = context(registry, "SYN-EQ-0001", as_of="2025-12-31")
    assert one.status == "insufficient_history" and len(one.data["price_path"]) == 1
    none = context(registry, "SYN-EQ-0001", as_of="2025-12-30")
    assert none.status == "insufficient_data"


def test_context_unknown_instrument(registry):
    r = context(registry, "SYN-EQ-9999")
    assert r.status == "no_data" and r.data is None


# ---- events.relevant ----------------------------------------------------------------------
def relevant(registry, iid, **kw):
    r = call(registry, "events.relevant", instrument_id=iid, **kw)
    return r, {e["event_id"]: e for e in (r.data["events"] if r.data else [])}


def tokens_of(event):
    return {m["token"] for m in event["matched_on"]}


def test_gold_instrument_gets_the_gold_events(registry):
    r, ev = relevant(registry, "SYN-CM-0401")
    assert r.status == "ok" and "lexical" in r.data["matching"]
    assert {"EVT-2025-12-31-1", "EVT-2026-01-26-1", "EVT-2026-01-28-1"} <= set(ev)
    assert all("gold" in tokens_of(e) and {"field": "sector", "token": "gold"} in e["matched_on"] for e in ev.values())
    assert not any("Energy" in e["primary_transmission"] for e in ev.values())


def test_energy_instrument_gets_the_energy_events_with_severity(registry):
    _, ev = relevant(registry, "SYN-EQ-0008")
    assert {"EVT-2026-03-04-1", "EVT-2026-05-04-1", "EVT-2026-08-05-1"} <= set(ev)
    assert ev["EVT-2026-03-04-1"]["severity"] == "Severe" and {"field": "sector", "token": "energy"} in ev["EVT-2026-03-04-1"]["matched_on"]


def test_a_regional_event_matches_by_region_alone(registry):
    _, ev = relevant(registry, "SYN-FI-0202")          # US Treasury, region North America
    fed = ev["EVT-2026-06-17-1"]                         # region United States, transmission without any shared word
    assert fed["matched_on"] == [{"field": "region", "token": "United States"}]


def test_global_events_need_a_word_in_common(registry):
    _, ev = relevant(registry, "SYN-CA-0601")           # USD call deposit: nothing in common with the log
    assert ev == {}
    r, _ = relevant(registry, "SYN-CA-0601")
    assert r.status == "ok" and r.data["events"] == []


def test_unrelated_events_are_not_offered(registry):
    _, ev = relevant(registry, "SYN-EQ-0001")           # global developed equity fund
    assert not any("Gold" in e["primary_transmission"] or "Energy" in e["primary_transmission"] for e in ev.values())
    assert "EVT-2026-02-28-1" not in ev                  # Middle East war: no word or region in common


def test_relevant_events_have_no_look_ahead(registry):
    _, ev = relevant(registry, "SYN-EQ-0008", as_of="2026-03-31")
    assert max(e["event_date"] for e in ev.values()) <= date(2026, 3, 31) and "EVT-2026-08-05-1" not in ev


def test_relevant_events_ids_match_the_event_tools(registry):
    _, ev = relevant(registry, "SYN-EQ-0008")
    ids = {e["event_id"] for e in call(registry, "events.list").data}
    assert set(ev) <= ids


def test_relevant_events_unknown_instrument(registry):
    r, _ = relevant(registry, "SYN-EQ-9999")
    assert r.status == "no_data"


# ---- outlook.market / outlook.previous_instrument ---------------------------------------------
from rm_dashboard.outlook import InstrumentOutlook, InstrumentView


def instrument_outlook(iid, as_of, direction="neutral"):
    v = InstrumentView(direction=direction, confidence="low", rationale="steady", change=Change(kind="new"),
                       drivers=[Reason(claim="Price rose.", evidence_ids=["ev_9"])])
    return InstrumentOutlook(subject=iid, as_of=as_of, status="complete", view=v)


@pytest.fixture
def with_instruments(with_reports, tmp_path):
    store = OutlookStore(tmp_path)
    for d, direction in (("2026-03-31", "positive"), ("2026-06-30", "negative"), ("2026-08-26", "neutral")):
        store.save_instrument(instrument_outlook("SYN-EQ-0001", d, direction), [])
    store.save_instrument(instrument_outlook("SYN-EQ-0002", "2026-06-30"), [])
    return with_reports


def test_outlook_market_returns_the_latest_not_after_the_date(with_reports):
    r = call(with_reports, "outlook.market", as_of="2026-08-26")
    assert r.status == "ok" and r.data["market_outlook_as_of"] == "2026-08-26" and len(r.data["digest"]) == 16
    assert [f.code for f in r.flags] == ["house_view"]
    r = call(with_reports, "outlook.market", as_of="2026-07-15")
    assert r.data["market_outlook_as_of"] == "2026-06-30" and {f.code for f in r.flags} == {"house_view", "stale_outlook"}


def test_outlook_market_refuses_look_ahead_and_missing(with_reports, registry):
    r = call(with_reports, "outlook.market", as_of="2026-01-15")
    assert r.status == "no_data" and "no market outlook" in r.reason and r.data is None
    assert call(registry, "outlook.market").status == "no_data"


def test_market_digest_changes_with_the_views(with_reports, tmp_path):
    a = call(with_reports, "outlook.market", as_of="2026-08-26").data["digest"]
    b = call(with_reports, "outlook.market", as_of="2026-06-30").data["digest"]
    assert a != b


def test_previous_instrument_is_strictly_earlier_and_per_instrument(with_instruments):
    r = call(with_instruments, "outlook.previous_instrument", as_of="2026-08-26", instrument_id="SYN-EQ-0001")
    assert r.status == "ok" and r.data["previous_as_of"] == "2026-06-30" and r.data["view"]["direction"] == "negative"
    assert [f.code for f in r.flags] == ["prior_view"] and "ev_9" not in str(r.data)
    r = call(with_instruments, "outlook.previous_instrument", as_of="2026-03-31", instrument_id="SYN-EQ-0001")
    assert r.status == "no_data" and "first" in r.reason
    r = call(with_instruments, "outlook.previous_instrument", as_of="2026-08-26", instrument_id="SYN-EQ-0003")
    assert r.status == "no_data"
    r = call(with_instruments, "outlook.previous_instrument", as_of="2026-08-26", instrument_id="SYN-EQ-0002")
    assert r.data["previous_as_of"] == "2026-06-30"


def test_previous_instrument_skips_outlooks_without_a_view(with_instruments, tmp_path):
    OutlookStore(tmp_path).save_instrument(InstrumentOutlook(subject="SYN-EQ-0001", as_of="2026-07-15", status="insufficient_data"), [])
    r = call(with_instruments, "outlook.previous_instrument", as_of="2026-08-26", instrument_id="SYN-EQ-0001")
    assert r.data["previous_as_of"] == "2026-06-30"


def test_outlook_market_makes_the_outlook_evidence_resolvable(registry, tmp_path):
    from rm_dashboard.agents import StubChatModel
    from rm_dashboard.outlook.agent import produce_market_outlook
    from rm_dashboard.tools import EvidenceStore

    store = OutlookStore(tmp_path)
    out, ev = produce_market_outlook(registry, as_of=date(2026, 8, 26), store=store, models=lambda r: StubChatModel(role=r))
    store.save_market(out, ev)
    reg = ToolRegistry(dataclasses.replace(registry.ctx, artifacts=tmp_path))
    run_store = EvidenceStore()
    r = reg.toolbox("test", reg.names(), store=run_store).call("outlook.market", {"as_of": "2026-08-26"})
    cited = {i for v in out.views for d in (*v.drivers, *v.risks) for i in d.evidence_ids}
    assert cited and all(i in run_store for i in cited) and r.evidence_id in run_store


# ---- outlook.instrument -------------------------------------------------------------------------
def test_outlook_instrument_returns_the_view_with_house_view_flag(with_instruments):
    r = call(with_instruments, "outlook.instrument", as_of="2026-08-26", instrument_id="SYN-EQ-0001")
    assert r.status == "ok" and r.data["outlook_as_of"] == "2026-08-26" and r.data["direction"] == "neutral"
    assert r.data["drivers"][0]["claim"] == "Price rose." and [f.code for f in r.flags] == ["house_view"]


def test_outlook_instrument_earlier_only_is_effective_with_a_stale_flag(with_instruments):
    r = call(with_instruments, "outlook.instrument", as_of="2026-07-15", instrument_id="SYN-EQ-0001")
    assert r.data["outlook_as_of"] == "2026-06-30" and {f.code for f in r.flags} == {"house_view", "stale_outlook"}


def test_outlook_instrument_never_returns_a_later_one(with_instruments):
    r = call(with_instruments, "outlook.instrument", as_of="2026-01-15", instrument_id="SYN-EQ-0001")
    assert r.status == "no_data" and r.data is None and "SYN-EQ-0001" in r.reason and "rm-dashboard-outlook" in r.reason


def test_outlook_instrument_without_outlook_or_reports(with_instruments, registry):
    r = call(with_instruments, "outlook.instrument", as_of="2026-08-26", instrument_id="SYN-EQ-0003")
    assert r.status == "no_data" and "SYN-EQ-0003" in r.reason
    assert call(registry, "outlook.instrument", instrument_id="SYN-EQ-0001").status == "no_data"


def test_each_missing_outlook_has_its_own_reason(with_instruments):
    a = call(with_instruments, "outlook.instrument", as_of="2026-08-26", instrument_id="SYN-EQ-0003").reason
    b = call(with_instruments, "outlook.instrument", as_of="2026-08-26", instrument_id="SYN-EQ-0004").reason
    assert a != b


def test_outlook_instrument_makes_the_outlook_evidence_resolvable(registry, tmp_path):
    from rm_dashboard.agents import StubChatModel
    from rm_dashboard.outlook.agent import produce_instrument_outlook, produce_market_outlook
    from rm_dashboard.tools import EvidenceStore

    store = OutlookStore(tmp_path)
    m, mev = produce_market_outlook(registry, as_of=date(2026, 8, 26), store=store, models=lambda r: StubChatModel(role=r))
    store.save_market(m, mev)
    o, ev = produce_instrument_outlook(registry, instrument_id="SYN-CM-0401", as_of=date(2026, 8, 26), store=store, models=lambda r: StubChatModel(role=r))
    store.save_instrument(o, ev)
    reg = ToolRegistry(dataclasses.replace(registry.ctx, artifacts=tmp_path))
    run_store = EvidenceStore()
    r = reg.toolbox("test", reg.names(), store=run_store).call("outlook.instrument", {"as_of": "2026-08-26", "instrument_id": "SYN-CM-0401"})
    cited = {i for d in (*o.view.drivers, *o.view.risks) for i in d.evidence_ids}
    assert cited and all(i in run_store for i in cited) and r.evidence_id in run_store


# ---- allow-lists ------------------------------------------------------------------------------
from rm_dashboard.tools import ALLOWLISTS, ToolRefused


def test_client_analysts_may_read_outlooks_and_the_instrument_analyst_may_not(registry):
    assert {"outlook.market", "outlook.instrument"} <= set(ALLOWLISTS["portfolio_analyst"])
    assert "outlook.market" in ALLOWLISTS["relationship_analyst"] and "outlook.instrument" not in ALLOWLISTS["relationship_analyst"]
    tb = registry.toolbox("instrument_analyst", ALLOWLISTS["instrument_analyst"])
    for tool, args in (("outlook.market", {}), ("outlook.instrument", {"instrument_id": "SYN-EQ-0001"})):
        with pytest.raises(ToolRefused):
            tb.call(tool, {"as_of": "2026-08-26", **args})


def test_outlook_tools_accept_no_path_and_start_no_run(registry):
    for name in ("outlook.market", "outlook.instrument"):
        fields = set(registry.specs[name].params.model_fields)
        assert fields <= {"as_of", "instrument_id"}
