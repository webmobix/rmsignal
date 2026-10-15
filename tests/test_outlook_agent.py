import json
from datetime import date

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from rm_dashboard.agents import StubChatModel
from rm_dashboard.domain import Computation, ToolResult
from rm_dashboard.outlook import Change, EventRef, MarketOutlook, OutlookInputs, Reason, View
from rm_dashboard.outlook.agent import ROLE, can_carry_forward, produce_market_outlook
from rm_dashboard.outlook.guard import GuardInput, guard_market_outlook
from rm_dashboard.outlook.inputs import compute_inputs, required_segments, severe_events_in_window
from rm_dashboard.outlook.store import OutlookStore
from rm_dashboard.policy import ScriptedEngine
from rm_dashboard.runners import open_registry
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ALLOWLISTS, EvidenceStore

AS_OF = date(2026, 8, 26)


class Models:
    """Factory that remembers the stubs it made, so tests can count model calls."""

    def __init__(self, mode="normal"):
        self.mode, self.made = mode, []

    def __call__(self, role):
        m = StubChatModel(role=role, mode=self.mode)
        self.made.append(m)
        return m

    @property
    def calls(self):
        return sum(m.calls for m in self.made)


@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db)), with_peer=False) as r:
        yield r


def make(reg, tmp_path, as_of=AS_OF, mode="normal", **kw):
    models = kw.pop("models", None) or Models(mode)
    store = kw.pop("store", None) or OutlookStore(tmp_path)
    out, ev = produce_market_outlook(reg, as_of=as_of, store=store, models=models, **kw)
    return out, ev, models, store


def save(store, out, ev):
    store.save_market(out, ev)


# ---- 2.1 fingerprint ------------------------------------------------------------------------
def test_inputs_equal_when_nothing_new_arrived(reg):
    a, _ = compute_inputs(reg.ctx.repo, date(2026, 8, 26))
    b, _ = compute_inputs(reg.ctx.repo, date(2026, 9, 15))
    assert a == b and a.market_snapshot_date == date(2026, 8, 26) and a.latest_event_date == date(2026, 8, 5) and a.event_count == 16


def test_inputs_change_with_a_new_event_or_snapshot(reg):
    base, _ = compute_inputs(reg.ctx.repo, date(2026, 8, 4))
    event, _ = compute_inputs(reg.ctx.repo, date(2026, 8, 5))
    assert event.event_count == base.event_count + 1 and event != base and event.market_snapshot_date == base.market_snapshot_date
    snap, _ = compute_inputs(reg.ctx.repo, date(2026, 8, 26))
    assert snap.market_snapshot_date != base.market_snapshot_date and snap != base


def test_inputs_without_market_data_give_a_reason(reg):
    inputs, why = compute_inputs(reg.ctx.repo, date(2025, 12, 30))
    assert why and inputs.market_snapshot_date is None


def test_required_segments_follow_the_data(reg):
    assert required_segments(reg.ctx.repo, AS_OF) == ["overall", "equity", "rates", "fx", "commodities", "volatility"]
    assert required_segments(reg.ctx.repo, date(2025, 12, 30)) == ["overall"]


# ---- first outlook and tools ----------------------------------------------------------------
def test_first_outlook_has_new_views_and_is_complete(reg, tmp_path):
    out, ev, models, _ = make(reg, tmp_path)
    assert out.status == "complete" and out.is_first and out.previous_as_of is None and not out.gaps
    assert [v.segment for v in out.views] == ["overall", "equity", "rates", "fx", "commodities", "volatility"]
    assert all(v.change.kind == "new" and v.horizon == "3m" and v.drivers for v in out.views)
    assert "First outlook" in out.changes_summary
    ids = {e.evidence_id for e in ev}
    assert all(i in ids for v in out.views for r in (*v.drivers, *v.risks) for i in r.evidence_ids)
    assert models.calls == 2 and {c.checkpoint for c in out.policy_decisions} >= {"request_entitlement", "evidence_provenance"}


def test_model_sees_only_the_outlook_tools(reg, tmp_path):
    from rm_dashboard.agents.tooladapter import lc_name

    _, _, models, _ = make(reg, tmp_path)
    expected = {lc_name(n) for n in ALLOWLISTS[ROLE]}
    assert models.made and all(set(names) == expected for m in models.made for names in m.bound_tool_names)


def test_events_are_cited_as_reasons(reg, tmp_path):
    out, *_ = make(reg, tmp_path)
    cited = {e for v in out.views for r in v.drivers for e in r.event_refs}
    assert cited and all(e.startswith("EVT-") for e in cited)


def test_unaddressed_severe_events_are_listed(reg, tmp_path):
    out, *_ = make(reg, tmp_path)
    cited = {e for v in out.views for r in (*v.drivers, *v.risks) for e in r.event_refs}
    assert out.unaddressed_events and not cited & {e.event_id for e in out.unaddressed_events}
    assert all(e.severity in ("High", "Severe") for e in out.unaddressed_events)


# ---- 2.2 carry-forward ----------------------------------------------------------------------
class Boom:
    def __call__(self, role):
        raise AssertionError("no model may be called")


def test_no_new_data_carries_the_previous_views_forward(reg, tmp_path):
    first, ev, _, store = make(reg, tmp_path)
    save(store, first, ev)
    out, ev2, _, _ = make(reg, tmp_path, as_of=date(2026, 9, 15), models=Boom(), store=store)
    assert out.carried_forward_from == AS_OF and out.previous_as_of == AS_OF and out.as_of == date(2026, 9, 15)
    assert [v.model_copy(update={"change": None}) for v in out.views] == [v.model_copy(update={"change": None}) for v in first.views]
    assert all(v.change.kind == "unchanged" and v.change.previous_direction == v.direction for v in out.views)
    assert "Carried forward" in out.changes_summary and out.status == first.status
    assert {e.evidence_id for e in ev2} == {e.evidence_id for e in ev}


def test_force_regenerates_without_new_data(reg, tmp_path):
    first, ev, _, store = make(reg, tmp_path)
    save(store, first, ev)
    out, _, models, _ = make(reg, tmp_path, as_of=date(2026, 9, 15), store=store, force=True)
    assert models.calls == 2 and out.carried_forward_from is None and out.previous_as_of == AS_OF


def test_a_new_event_generates_a_new_outlook(reg, tmp_path):
    first, ev, _, store = make(reg, tmp_path, as_of=date(2026, 8, 4))
    save(store, first, ev)
    out, _, models, _ = make(reg, tmp_path, as_of=date(2026, 8, 5), store=store)
    assert models.calls == 2 and out.carried_forward_from is None and out.previous_as_of == date(2026, 8, 4)
    assert not out.is_first and "Compared with 2026-08-04" in out.changes_summary


def test_can_carry_forward_rules():
    inputs = OutlookInputs(event_count=1)
    prev = MarketOutlook(as_of="2026-06-30", status="complete", inputs=inputs, views=[view("overall", "neutral")])
    assert can_carry_forward(prev, inputs, False)
    assert not can_carry_forward(prev, inputs, True)
    assert not can_carry_forward(prev, OutlookInputs(event_count=2), False)
    assert not can_carry_forward(None, inputs, False)
    assert not can_carry_forward(prev.model_copy(update={"views": []}), inputs, False)


# ---- always delivered -----------------------------------------------------------------------
def test_model_failure_without_previous_gives_partial_without_views(reg, tmp_path):
    out, ev, *_ = make(reg, tmp_path, mode="raise")
    assert out.status == "partial" and not out.views and any(g.kind == "agent_error" for g in out.gaps)


def test_model_failure_carries_previous_views_forward(reg, tmp_path):
    first, ev, _, store = make(reg, tmp_path, as_of=date(2026, 6, 30))
    save(store, first, ev)
    out, *_ = make(reg, tmp_path, store=store, mode="raise")
    assert out.status == "partial" and len(out.views) == len(first.views) and all(v.change.kind == "unchanged" for v in out.views)
    assert any(g.kind == "agent_error" for g in out.gaps) and out.carried_forward_from == date(2026, 6, 30)


def test_unparsable_answer_is_a_gap(reg, tmp_path):
    out, *_ = make(reg, tmp_path, mode="unparsable")
    assert out.status == "partial" and not out.views and any("not JSON" in g.description for g in out.gaps)


def test_policy_denial_is_a_gap_not_an_error(reg, tmp_path):
    out, ev, models, _ = make(reg, tmp_path, engine=ScriptedEngine({"request_entitlement": "deny"}))
    assert out.status == "insufficient_data" and not out.views and any(g.kind == "policy_denied" for g in out.gaps) and models.calls == 0


def test_no_market_data_means_no_model_call(reg, tmp_path):
    out, ev, models, _ = make(reg, tmp_path, as_of=date(2025, 12, 30))
    assert out.status == "insufficient_data" and not out.views and models.calls == 0 and not ev
    assert any(g.kind == "no_data" for g in out.gaps)


def test_thin_history_caps_confidence_at_low(reg, tmp_path):
    out, *_ = make(reg, tmp_path, as_of=date(2025, 12, 31))
    assert out.views and all(v.confidence == "low" for v in out.views)
    assert any("insufficient" in g.description for g in out.gaps) and out.status == "partial"


def test_uncited_figure_removes_only_that_driver(reg, tmp_path):
    out, *_ = make(reg, tmp_path, mode="uncited_number")
    equity = next(v for v in out.views if v.segment == "equity")
    assert equity.drivers and not any("98765" in d.claim for d in equity.drivers)
    assert out.status == "partial" and any(g.kind == "guard_removed" and "98765" in g.description for g in out.gaps)


# ---- 3.2 guard rules ------------------------------------------------------------------------
def result(tool, data, as_of=AS_OF, status="ok"):
    return ToolResult(data=data, as_of=as_of, status=status, reason=None if status == "ok" else "short",
                      computation=Computation(tool=tool, version="1"))


def event(i, day, severity="High", text="Brent crude peaked at approximately USD 114 per barrel."):
    return {"event_id": i, "event_date": day, "severity": severity, "description": text, "primary_transmission": "Energy"}


def view(seg, direction, snap=None, **kw):
    r = Reason(claim="Equities rose.", evidence_ids=["ev_x"])
    return View(segment=seg, direction=direction, confidence="medium", drivers=[r], change=Change(kind="new"), **kw)


@pytest.fixture
def env():
    store = EvidenceStore()
    news = result("news.list", {"news": [event("EVT-2026-07-01-1", date(2026, 7, 1)), event("EVT-2026-05-01-1", date(2026, 5, 1))],
                                "source": "event_log"})
    trend = result("analytics.market_trend", {"snapshots": 5, "latest_snapshot_date": date(2026, 8, 26),
                                              "series": [{"series_id": "SPX", "latest": 7530.0, "previous": 7410.0}]})
    for r in (news, trend):
        store.add(r)
    return store, news, trend


def gi(store, prev=None, required=("overall", "equity"), severe=()):
    return GuardInput(store=store, as_of=AS_OF, required=list(required), prev=prev, severe_in_window=list(severe))


def raw_view(trend, seg="equity", direction="positive", **kw):
    base = {"segment": seg, "direction": direction, "horizon": "3m", "confidence": "high", "rationale": "Equities rose.",
            "drivers": [{"claim": "SPX stands at 7530.", "evidence_ids": [trend.evidence_id]}], "risks": []}
    return {**base, **kw}


def run_guard(env, raws, prev=None, **kw):
    store, news, trend = env
    return guard_market_outlook(raws, "", gi(store, prev, **kw))


@pytest.mark.parametrize("field,value", [("segment", "crypto"), ("direction", "bullish"), ("horizon", "2y"), ("confidence", "certain")])
def test_guard_rejects_values_outside_the_closed_sets(env, field, value):
    out = run_guard(env, [raw_view(env[2], **{field: value})])
    assert not [v for v in out.views if v.segment == "equity"] and any(g.kind == "guard_removed" for g in out.gaps)


def test_guard_removes_a_view_whose_drivers_cite_nothing_valid(env):
    out = run_guard(env, [raw_view(env[2], drivers=[{"claim": "Equities rose.", "evidence_ids": ["ev_unknown"]}])])
    assert not [v for v in out.views if v.segment == "equity"]
    assert any("not produced in this run" in g.description for g in out.gaps)


def test_guard_event_reference_copies_evidence_and_is_kept(env):
    store, news, trend = env
    d = {"claim": "Brent crude peaked at approximately USD 114 per barrel.", "evidence_ids": [], "event_refs": ["EVT-2026-07-01-1"]}
    out = run_guard(env, [raw_view(trend, drivers=[d])])
    r = next(v for v in out.views if v.segment == "equity").drivers[0]
    assert r.evidence_ids == [news.evidence_id] and r.event_refs == ["EVT-2026-07-01-1"]


def test_guard_rejects_an_event_that_was_not_returned(env):
    d = {"claim": "A war began.", "evidence_ids": [env[2].evidence_id], "event_refs": ["EVT-2026-07-09-1"]}
    out = run_guard(env, [raw_view(env[2], drivers=[d])])
    assert not [v for v in out.views if v.segment == "equity"] and any("not returned" in g.description for g in out.gaps)


def test_guard_rejects_a_previous_outlook_as_support():
    store = EvidenceStore()
    prior = result("outlook.previous_market", {"previous_as_of": "2026-06-30", "views": []})
    store.add(prior)
    raw = {"segment": "overall", "direction": "neutral", "horizon": "3m", "confidence": "low",
           "drivers": [{"claim": "The last view was neutral.", "evidence_ids": [prior.evidence_id]}]}
    out = guard_market_outlook([raw], "", gi(store, required=["overall"]))
    assert not out.views and any("reference, not support" in g.description for g in out.gaps)


def test_guard_rejects_evidence_of_another_date(env):
    store, _, trend = env
    old = result("analytics.market_trend", {"snapshots": 3, "latest_snapshot_date": date(2026, 3, 31)}, as_of=date(2026, 3, 31))
    store.add(old)
    out = run_guard(env, [raw_view(trend, drivers=[{"claim": "Equities rose.", "evidence_ids": [old.evidence_id]}])])
    assert not [v for v in out.views if v.segment == "equity"] and any("not 2026-08-26" in g.description for g in out.gaps)


def test_guard_blanks_a_rationale_with_an_unsupported_figure(env):
    out = run_guard(env, [raw_view(env[2], rationale="Equities will reach 98765 points.", would_change_if="Below 4242.")])
    v = next(v for v in out.views if v.segment == "equity")
    assert v.rationale == "" and v.would_change_if == "" and v.drivers


def test_guard_summary_figures_must_be_grounded(env):
    store, _, trend = env
    out = guard_market_outlook([raw_view(trend)], "SPX at 123456.", gi(store))
    assert out.summary == "" and any(g.subject == "summary" for g in out.gaps)
    ok = guard_market_outlook([raw_view(trend)], "SPX at 7530.", gi(store))
    assert ok.summary == "SPX at 7530."


def test_confidence_is_capped_without_events_and_with_short_history(env):
    store, news, trend = env
    out = run_guard(env, [raw_view(trend)])
    assert next(v for v in out.views if v.segment == "equity").confidence == "medium"
    d = {"claim": "Brent crude peaked at approximately USD 114 per barrel.", "evidence_ids": [], "event_refs": ["EVT-2026-07-01-1"]}
    out = run_guard(env, [raw_view(trend, drivers=[d])])
    assert next(v for v in out.views if v.segment == "equity").confidence == "high"
    short = result("analytics.market_trend", {"snapshots": 1, "latest_snapshot_date": date(2026, 8, 26)}, status="insufficient_history")
    store.add(short)
    out = run_guard([], [raw_view(trend, drivers=[d])]) if False else guard_market_outlook([raw_view(trend, drivers=[d])], "", gi(store))
    assert next(v for v in out.views if v.segment == "equity").confidence == "low"


def prev_outlook(direction="neutral", snap=date(2026, 6, 30), as_of=date(2026, 6, 30)):
    return MarketOutlook(as_of=as_of, status="complete", inputs=OutlookInputs(market_snapshot_date=snap, event_count=1),
                         views=[view("overall", "neutral"), view("equity", direction)])


def test_direction_change_with_new_evidence_is_derived_as_downgrade(env):
    store, news, trend = env
    d = {"claim": "Brent crude peaked at approximately USD 114 per barrel.", "evidence_ids": [], "event_refs": ["EVT-2026-07-01-1"]}
    out = run_guard(env, [raw_view(trend, direction="negative", drivers=[d], change={"why": "Oil spiked."})], prev=prev_outlook("neutral"))
    v = next(v for v in out.views if v.segment == "equity")
    assert v.direction == "negative" and v.change.kind == "downgraded" and v.change.previous_direction == "neutral"
    assert v.change.new_event_refs == ["EVT-2026-07-01-1"] and "Compared with 2026-06-30" in out.changes_summary


def test_direction_change_with_a_newer_snapshot_is_an_upgrade(env):
    out = run_guard(env, [raw_view(env[2], direction="positive")], prev=prev_outlook("neutral"))
    v = next(v for v in out.views if v.segment == "equity")
    assert v.change.kind == "upgraded" and v.change.new_evidence_ids == [env[2].evidence_id]


def test_direction_change_without_new_evidence_is_reverted(env):
    store, news, trend = env
    old_event = {"claim": "Brent crude peaked at approximately USD 114 per barrel.", "evidence_ids": [], "event_refs": ["EVT-2026-05-01-1"]}
    prev = prev_outlook("neutral", snap=date(2026, 8, 26), as_of=date(2026, 8, 1))
    out = run_guard(env, [raw_view(trend, direction="negative", drivers=[old_event])], prev=prev)
    v = next(v for v in out.views if v.segment == "equity")
    assert v.direction == "neutral" and v.change.kind == "unchanged"
    assert any("rejected" in g.description and "equity" in g.description for g in out.gaps)


def test_same_direction_is_unchanged_and_a_new_segment_is_new(env):
    out = run_guard(env, [raw_view(env[2], direction="neutral")], prev=prev_outlook("neutral"))
    assert next(v for v in out.views if v.segment == "equity").change.kind == "unchanged"
    prev = MarketOutlook(as_of="2026-06-30", status="complete", inputs=OutlookInputs(), views=[view("overall", "neutral")])
    out = run_guard(env, [raw_view(env[2], direction="neutral")], prev=prev)
    assert next(v for v in out.views if v.segment == "equity").change.kind == "new"


def test_missing_segment_carries_the_previous_view_or_is_a_gap(env):
    out = run_guard(env, [raw_view(env[2], seg="overall", direction="neutral")], prev=prev_outlook("negative"))
    v = next(v for v in out.views if v.segment == "equity")
    assert v.direction == "negative" and v.change.kind == "unchanged" and any("equity" in g.description for g in out.gaps)
    out = run_guard(env, [raw_view(env[2], seg="overall", direction="neutral")])
    assert [v.segment for v in out.views] == ["overall"] and any(g.kind == "no_data" and g.subject == "equity" for g in out.gaps)


def test_unaddressed_severe_events_exclude_cited_ones(env):
    store, news, trend = env
    sev = [EventRef(event_id="EVT-2026-07-01-1", event_date="2026-07-01", severity="Severe", description="x"),
           EventRef(event_id="EVT-2026-05-01-1", event_date="2026-05-01", severity="High", description="y")]
    d = {"claim": "Brent crude peaked at approximately USD 114 per barrel.", "evidence_ids": [], "event_refs": ["EVT-2026-07-01-1"]}
    out = run_guard(env, [raw_view(trend, drivers=[d])], severe=sev)
    assert [e.event_id for e in out.unaddressed] == ["EVT-2026-05-01-1"]


def test_severe_events_window_starts_after_the_previous_as_of(reg):
    from rm_dashboard.outlook.inputs import all_events

    events = all_events(reg.ctx.repo, AS_OF)
    first = severe_events_in_window(events, None, AS_OF)
    later = severe_events_in_window(events, date(2026, 6, 30), AS_OF)
    assert len(later) < len(first) and all(e.event_date > date(2026, 6, 30) for e in later)
    assert all(e.severity in ("High", "Severe") for e in first)
