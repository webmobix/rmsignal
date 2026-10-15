from datetime import date

import pytest

from rm_dashboard.agents import StubChatModel
from rm_dashboard.agents.tooladapter import lc_name
from rm_dashboard.domain import Computation, ToolResult
from rm_dashboard.outlook import Change, EventRef, InstrumentInputs, InstrumentOutlook, InstrumentView, Reason
from rm_dashboard.outlook.agent import (
    INSTRUMENT_SPEC, ROLE, SPEC, can_carry_forward_instrument, produce_instrument_outlook, produce_market_outlook,
)
from rm_dashboard.outlook.digest import market_digest
from rm_dashboard.outlook.guard import InstrumentGuardInput, guard_instrument_outlook
from rm_dashboard.outlook.inputs import held_instruments, instrument_inputs, market_context_for
from rm_dashboard.outlook.store import OutlookStore
from rm_dashboard.policy import ScriptedEngine
from rm_dashboard.runners import open_registry
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ALLOWLISTS, EvidenceStore, ToolRefused

AS_OF = date(2026, 8, 26)


class Models:
    def __init__(self, mode="normal"):
        self.mode, self.made = mode, []

    def __call__(self, role):
        m = StubChatModel(role=role, mode=self.mode)
        self.made.append(m)
        return m

    @property
    def calls(self):
        return sum(m.calls for m in self.made)


class Boom:
    def __call__(self, role):
        raise AssertionError("no model may be called")


@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db)), with_peer=False) as r:
        yield r


@pytest.fixture
def store(reg, tmp_path):
    """A reports folder with the market outlook of 2026-08-26 in it."""
    st = OutlookStore(tmp_path)
    m, ev = produce_market_outlook(reg, as_of=AS_OF, store=st, models=Models())
    st.save_market(m, ev)
    return st


def make(reg, store, iid="SYN-EQ-0003", as_of=AS_OF, mode="normal", **kw):
    models = kw.pop("models", None) or Models(mode)
    out, ev = produce_instrument_outlook(reg, instrument_id=iid, as_of=as_of, store=store, models=models, **kw)
    return out, ev, models


# ---- 2.1 one agent, narrower tools --------------------------------------------------------------
def test_instrument_run_sees_only_instrument_tools(reg, store):
    _, _, models = make(reg, store)
    expected = {lc_name(n) for n in ALLOWLISTS["outlook_instrument"]}
    assert models.made and all(set(names) == expected for m in models.made for names in m.bound_tool_names)
    assert not expected & {lc_name(n) for n in ALLOWLISTS["outlook_analyst"]}


def test_market_only_tools_are_refused_for_an_instrument_run(reg, store):
    tb = reg.toolbox(INSTRUMENT_SPEC.name, INSTRUMENT_SPEC.allowlist)
    for tool in ("market.history", "analytics.market_trend", "news.list", "events.list", "outlook.previous_market"):
        with pytest.raises(ToolRefused):
            tb.call(tool, {"as_of": "2026-08-26"})
    market = reg.toolbox(SPEC.name, SPEC.allowlist)
    with pytest.raises(ToolRefused):
        market.call("instruments.context", {"as_of": "2026-08-26", "instrument_id": "SYN-EQ-0003"})


def test_the_two_runs_are_one_agent_with_different_prompts():
    assert SPEC.name == INSTRUMENT_SPEC.name == ROLE and SPEC.prompt != INSTRUMENT_SPEC.prompt
    assert "ONE instrument" in INSTRUMENT_SPEC.prompt and "event_id" in INSTRUMENT_SPEC.prompt


# ---- the outlook of one instrument ---------------------------------------------------------------
def test_first_outlook_of_an_instrument(reg, store):
    out, ev, models = make(reg, store)
    assert out.status == "complete" and out.is_first and out.previous_as_of is None and out.view.change.kind == "new"
    assert out.instrument.instrument_id == "SYN-EQ-0003" and out.instrument.sector == "Information Technology"
    assert [p.price for p in out.price_path][-1] == 592.1 and len(out.price_path) == 5
    assert out.unavailable_statistics == ["volatility", "max_drawdown"]
    ids = {e.evidence_id for e in ev}
    assert all(i in ids for r in (*out.view.drivers, *out.view.risks) for i in r.evidence_ids)
    assert models.calls == 2 and {c.checkpoint for c in out.policy_decisions} >= {"request_entitlement", "evidence_provenance"}


def test_market_context_is_copied_by_code_from_the_market_outlook(reg, store):
    out, *_ = make(reg, store)
    market = store.load_market(AS_OF)
    by_segment = {v.segment: v for v in market.views}
    assert [c.segment for c in out.market_context] == ["overall", "equity"] and out.market_outlook_as_of == AS_OF
    assert all((c.direction, c.horizon, c.confidence) == (by_segment[c.segment].direction, by_segment[c.segment].horizon,
                                                         by_segment[c.segment].confidence) for c in out.market_context)
    assert out.inputs.market_outlook_digest == market_digest(market)


def test_relevant_segments_follow_the_asset_class(reg, store):
    market = store.load_market(AS_OF)
    row = lambda i: instrument_inputs(reg.ctx.repo, store, i, AS_OF)[1]
    assert [c.segment for c in market_context_for(row("SYN-CM-0401"), market)] == ["overall", "commodities"]
    assert [c.segment for c in market_context_for(row("SYN-FI-0201"), market)] == ["overall", "rates"]
    assert [c.segment for c in market_context_for(row("SYN-AL-0303"), market)] == ["overall"]
    assert market_context_for(row("SYN-AL-0303"), None) == []


def test_events_are_cited_and_only_relevant_ones(reg, store):
    out, *_ = make(reg, store, "SYN-CM-0401")
    cited = {e for r in out.view.drivers for e in r.event_refs}
    assert cited and all(e.event_id in cited for e in out.relevant_events)
    gold = {"EVT-2025-12-31-1", "EVT-2026-01-26-1", "EVT-2026-01-28-1"}
    assert cited <= gold and {e.event_id for e in out.unaddressed_events} == gold - cited


def test_no_client_data_in_the_outlook(reg, store):
    out, ev, _ = make(reg, store)
    text = out.model_dump_json()
    for needle in ("CL-0", "PF-0", "quantity", "client_name"):
        assert needle not in text, needle


# ---- 2.3 always delivered ------------------------------------------------------------------------
def test_instrument_without_a_price_means_no_model_call(reg, store):
    out, ev, models = make(reg, store, as_of=date(2025, 12, 30), models=Boom())
    assert out.status == "insufficient_data" and out.view is None and not ev
    assert any(g.kind == "no_data" for g in out.gaps)


def test_unknown_instrument_is_insufficient_data(reg, store):
    out, _, _ = make(reg, store, "SYN-EQ-9999", models=Boom())
    assert out.status == "insufficient_data" and "not found" in out.gaps[0].description


def test_missing_market_outlook_is_a_gap_not_a_failure(reg, tmp_path):
    out, _, models = make(reg, OutlookStore(tmp_path))
    assert out.status == "partial" and out.view is not None and out.market_context == [] and out.market_outlook_as_of is None
    assert any("market context is unavailable" in g.description for g in out.gaps)


def test_model_failure_without_previous_gives_partial_without_a_view(reg, store):
    out, _, _ = make(reg, store, mode="raise")
    assert out.status == "partial" and out.view is None and any(g.kind == "agent_error" for g in out.gaps)


def test_model_failure_carries_the_previous_view_forward(reg, store):
    first, ev, _ = make(reg, store, as_of=date(2026, 6, 30))
    store.save_instrument(first, ev)
    out, *_ = make(reg, store, mode="raise")
    assert out.status == "partial" and out.view.direction == first.view.direction and out.view.change.kind == "unchanged"
    assert out.carried_forward_from == date(2026, 6, 30) and any(g.kind == "agent_error" for g in out.gaps)


def test_unparsable_answer_is_a_gap(reg, store):
    out, _, _ = make(reg, store, mode="unparsable")
    assert out.status == "partial" and out.view is None and any("not JSON" in g.description for g in out.gaps)


def test_policy_denial_is_a_gap(reg, store):
    out, _, models = make(reg, store, engine=ScriptedEngine({"request_entitlement": "deny"}))
    assert out.status == "insufficient_data" and out.view is None and models.calls == 0 and any(g.kind == "policy_denied" for g in out.gaps)


def test_uncited_figure_removes_only_that_driver(reg, store):
    out, *_ = make(reg, store, mode="uncited_number")
    assert out.view and not any("98765" in d.claim for d in out.view.drivers) and out.view.drivers
    assert out.status == "partial" and any("98765" in g.description for g in out.gaps)


def test_fingerprint_changes_with_price_event_or_market_outlook(reg, store):
    repo = reg.ctx.repo
    a, _, _ = instrument_inputs(repo, store, "SYN-EQ-0008", AS_OF)
    assert a.price_snapshot_date == AS_OF and a.market_outlook_as_of == AS_OF and "EVT-2026-08-05-1" in a.relevant_event_ids
    earlier, _, _ = instrument_inputs(repo, store, "SYN-EQ-0008", date(2026, 8, 4))
    assert "EVT-2026-08-05-1" not in earlier.relevant_event_ids and earlier.price_snapshot_date == date(2026, 6, 30)
    unrelated, _, _ = instrument_inputs(repo, store, "SYN-CM-0401", date(2026, 8, 5))
    gold_before, _, _ = instrument_inputs(repo, store, "SYN-CM-0401", date(2026, 8, 4))
    assert unrelated.relevant_event_ids == gold_before.relevant_event_ids            # an unrelated new event changes nothing for gold
    store.save_market(store.load_market(AS_OF).model_copy(update={"views": store.load_market(AS_OF).views[:-1]}), [])
    b, _, _ = instrument_inputs(repo, store, "SYN-EQ-0008", AS_OF)
    assert b.market_outlook_digest != a.market_outlook_digest


def test_held_instruments_are_the_union_across_portfolios(reg):
    held = held_instruments(reg.ctx.repo, AS_OF)
    assert held == sorted(set(held)) and 20 < len(held) <= 62 and all(i.startswith("SYN-") for i in held)
    assert held_instruments(reg.ctx.repo, date(2025, 12, 30)) == []


def test_can_carry_forward_rules():
    inputs = InstrumentInputs(price_snapshot_date=AS_OF)
    view = InstrumentView(direction="neutral", confidence="low", change=Change(kind="new"),
                          drivers=[Reason(claim="x", evidence_ids=["ev_1"])])
    prev = InstrumentOutlook(subject="SYN-EQ-0001", as_of="2026-06-30", status="complete", view=view, inputs=inputs)
    assert can_carry_forward_instrument(prev, inputs, False)
    assert not can_carry_forward_instrument(prev, inputs, True)
    assert not can_carry_forward_instrument(prev, InstrumentInputs(price_snapshot_date=date(2026, 6, 30)), False)
    assert not can_carry_forward_instrument(prev.model_copy(update={"view": None}), inputs, False)
    assert not can_carry_forward_instrument(None, inputs, False)


# ---- 2.2 guard rules specific to instruments --------------------------------------------------------
def result(tool, data, as_of=AS_OF, status="ok"):
    return ToolResult(data=data, as_of=as_of, status=status, reason=None if status == "ok" else "short",
                      computation=Computation(tool=tool, version="1"))


def event(i, day, severity="High", text="Spot gold trades above USD 5,000 per ounce for the first time."):
    return {"event_id": i, "event_date": day, "severity": severity, "description": text, "primary_transmission": "Gold"}


def context(peers=True, stats="insufficient_history", latest=AS_OF, status="ok"):
    return result("instruments.context", {
        "summary": {"latest_date": latest, "latest": 592.1, "previous": 573.6, "vs_previous_pct": 3.23},
        "peers": {"members": [{"instrument_id": "SYN-ST-0102"}] if peers else []},
        "risk_statistics": {"volatility": {"status": stats}, "max_drawdown": {"status": stats}}}, status=status)


def env(**ctx):
    store = EvidenceStore()
    c = context(**ctx)
    ev = result("events.relevant", {"events": [event("EVT-2026-07-01-1", date(2026, 7, 1)), event("EVT-2026-05-01-1", date(2026, 5, 1))]})
    mk = result("outlook.market", {"market_outlook_as_of": "2026-08-26", "digest": "abc", "views": []})
    for r in (c, ev, mk):
        store.add(r)
    return store, c, ev, mk


def raw(ids, **kw):
    base = {"direction": "positive", "horizon": "3m", "confidence": "high", "rationale": "Price rose.",
            "drivers": [{"claim": "The price moved from 573.6 to 592.1.", "evidence_ids": ids}], "risks": []}
    return {**base, **kw}


def guard(store, raw_view, prev=None, severe=()):
    return guard_instrument_outlook(raw_view, "", InstrumentGuardInput(store=store, as_of=AS_OF, prev=prev, severe_in_window=list(severe)))


EVENT_DRIVER = {"claim": "Spot gold trades above USD 5,000 per ounce for the first time.", "evidence_ids": [], "event_refs": ["EVT-2026-07-01-1"]}


def test_confidence_is_low_while_risk_statistics_are_unavailable():
    store, c, *_ = env()
    out = guard(store, raw([c.evidence_id], drivers=[EVENT_DRIVER]))
    assert out.view.confidence == "low" and out.unavailable_statistics == ["max_drawdown", "volatility"]


def test_confidence_is_low_when_the_price_path_is_insufficient():
    store, c, *_ = env(stats="ok", status="insufficient_history")
    assert guard(store, raw([c.evidence_id], drivers=[EVENT_DRIVER])).view.confidence == "low"


def test_confidence_needs_an_event_or_a_peer_comparison_for_more_than_medium():
    store, c, *_ = env(stats="ok", peers=False)
    assert guard(store, raw([c.evidence_id])).view.confidence == "medium"
    assert guard(store, raw([c.evidence_id], drivers=[EVENT_DRIVER])).view.confidence == "high"
    store, c, *_ = env(stats="ok", peers=True)
    assert guard(store, raw([c.evidence_id])).view.confidence == "high"


def test_cited_events_are_listed_and_the_rest_of_the_severe_ones_are_unaddressed():
    store, c, *_ = env(stats="ok")
    sev = [EventRef(event_id="EVT-2026-07-01-1", event_date="2026-07-01", severity="Severe", description="x"),
           EventRef(event_id="EVT-2026-05-01-1", event_date="2026-05-01", severity="High", description="y")]
    out = guard(store, raw([c.evidence_id], drivers=[EVENT_DRIVER]), severe=sev)
    assert [e.event_id for e in out.cited_events] == ["EVT-2026-07-01-1"] and [e.event_id for e in out.unaddressed] == ["EVT-2026-05-01-1"]


def test_an_event_that_was_not_offered_is_refused():
    store, c, *_ = env(stats="ok")
    bad = {"claim": "A war began.", "evidence_ids": [c.evidence_id], "event_refs": ["EVT-2026-07-09-1"]}
    out = guard(store, raw([c.evidence_id], drivers=[bad]))
    assert out.view is None and any("not returned" in g.description for g in out.gaps)


def test_the_previous_instrument_outlook_is_not_support():
    store, c, *_ = env(stats="ok")
    prior = result("outlook.previous_instrument", {"previous_as_of": "2026-06-30", "view": {}})
    store.add(prior)
    out = guard(store, raw([prior.evidence_id]))
    assert out.view is None and any("reference, not support" in g.description for g in out.gaps)


def previous(direction="neutral", price_date=date(2026, 6, 30), digest="abc", as_of=date(2026, 6, 30)):
    view = InstrumentView(direction=direction, confidence="low", change=Change(kind="new"),
                          drivers=[Reason(claim="x", evidence_ids=["ev_1"])])
    return InstrumentOutlook(subject="SYN-EQ-0003", as_of=as_of, status="complete", view=view,
                             inputs=InstrumentInputs(price_snapshot_date=price_date, market_outlook_digest=digest))


def test_a_newer_price_justifies_a_direction_change():
    store, c, *_ = env(stats="ok")
    out = guard(store, raw([c.evidence_id]), prev=previous("negative"))
    assert out.view.change.kind == "upgraded" and out.view.change.new_evidence_ids == [c.evidence_id]
    assert "negative -> positive" in out.changes_summary


def test_a_new_event_justifies_a_direction_change():
    store, c, *_ = env(stats="ok", latest=date(2026, 6, 30))
    out = guard(store, raw([c.evidence_id], direction="negative", drivers=[EVENT_DRIVER]), prev=previous("neutral", price_date=date(2026, 6, 30)))
    assert out.view.change.kind == "downgraded" and out.view.change.new_event_refs == ["EVT-2026-07-01-1"]


def test_a_changed_market_outlook_justifies_a_direction_change():
    store, c, ev, mk = env(stats="ok", latest=date(2026, 6, 30))
    d = {"claim": "The market view worsened.", "evidence_ids": [mk.evidence_id]}
    out = guard(store, raw([mk.evidence_id], direction="negative", drivers=[d]), prev=previous("neutral", price_date=date(2026, 6, 30), digest="old"))
    assert out.view.change.kind == "downgraded" and out.view.change.new_evidence_ids == [mk.evidence_id]


def test_a_direction_change_without_anything_new_is_reverted():
    store, c, ev, mk = env(stats="ok", latest=date(2026, 6, 30))
    out = guard(store, raw([c.evidence_id, mk.evidence_id], direction="negative"), prev=previous("neutral", price_date=date(2026, 6, 30)))
    assert out.view.direction == "neutral" and out.view.change.kind == "unchanged"
    assert any("rejected" in g.description for g in out.gaps)


def test_no_valid_view_keeps_the_previous_one_or_is_a_gap():
    store, c, *_ = env(stats="ok")
    out = guard(store, {"direction": "bullish"}, prev=previous("negative"))
    assert out.view.direction == "negative" and out.view.change.kind == "unchanged" and not out.fresh
    out = guard(store, None)
    assert out.view is None and any(g.kind == "no_data" for g in out.gaps)
