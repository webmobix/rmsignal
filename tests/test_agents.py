import json
from datetime import date

import pytest
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI

from rm_dashboard.agents import ANALYSTS, AnalystSession, RunScope, StubChatModel, analyse, build_model, guard_output
from rm_dashboard.agents.guard import evidence_numbers, extract_numbers, unsupported_numbers
from rm_dashboard.agents.middleware import AllowListMiddleware
from rm_dashboard.agents.tooladapter import lc_name
from rm_dashboard.domain import Report
from rm_dashboard.policy import CHECKPOINTS, RunContext, ScriptedEngine
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ALLOWLISTS, EvidenceStore

AS_OF = date(2026, 8, 26)


class Models:
    """Model factory that remembers every stub it handed out."""

    def __init__(self, mode=None, modes=None):
        self.made: dict[str, list[StubChatModel]] = {}
        self.modes = modes or {}
        self.mode = mode

    def __call__(self, role):
        m = StubChatModel(role=role, mode=self.modes.get(role, self.mode or "normal"))
        self.made.setdefault(role, []).append(m)
        return m


def run_role(make_scope, role, subject, models=None, **kw):
    scope = make_scope(subject=subject, **kw)
    models = models or Models()
    return analyse(role, subject, scope, models), scope, models


# ---- gate: what the model actually sees ---------------------------------------------------
@pytest.mark.parametrize("role,subject", [("instrument_analyst", "SYN-EQ-0001"), ("portfolio_analyst", "PF-0001"),
                                          ("relationship_analyst", "CL-0001")])
def test_model_sees_only_allow_list_and_delegation(make_scope, role, subject):
    report, scope, models = run_role(make_scope, role, subject)
    expected = {lc_name(n) for n in ALLOWLISTS[role]} | ({"task"} if ANALYSTS[role].delegates else set())
    stubs = models.made[role]
    assert stubs and all(set(names) == expected for m in stubs for names in m.bound_tool_names)
    for banned in ("read_file", "write_file", "edit_file", "ls", "glob", "grep", "execute", "write_todos"):
        assert banned not in expected
    assert report.status in ("complete", "partial")


def test_default_backend_never_touches_disk(make_scope, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_role(make_scope, "relationship_analyst", "CL-0001")
    assert list(tmp_path.iterdir()) == []


def test_only_declared_subagents_can_be_called():
    mw = AllowListMiddleware({"clients_get"}, {"portfolio_analyst"})

    class Req:
        def __init__(self, name, args):
            self.tool_call = {"name": name, "args": args, "id": "x"}

    ok = mw.wrap_tool_call(Req("task", {"subagent_type": "portfolio_analyst"}), lambda r: "ran")
    assert ok == "ran"
    for name, args in [("task", {"subagent_type": "general-purpose"}), ("read_file", {"file_path": "/etc/passwd"}),
                       ("execute", {"command": "ls"})]:
        res = mw.wrap_tool_call(Req(name, args), lambda r: "ran")
        assert isinstance(res, ToolMessage) and res.status == "error"


# ---- 7.1 gateway --------------------------------------------------------------------------
def test_gateway_swap_model_name_needs_no_code_change(make_scope):
    a = build_model(Settings(model_name="gpt-a", gateway_url="http://gw.example/v1", gateway_api_key="k"))
    b = build_model(Settings(model_name="claude-b", gateway_url="http://gw.example/v1", gateway_api_key="k"))
    assert isinstance(a, ChatOpenAI) and a.model_name == "gpt-a" and b.model_name == "claude-b"
    assert "gw.example" in str(a.openai_api_base)
    assert isinstance(build_model(Settings(model_name="stub"), role="portfolio_analyst"), StubChatModel)
    # the analysts take any model factory: nothing in agent logic names a provider
    r1, *_ = run_role(make_scope, "instrument_analyst", "SYN-EQ-0001", Models())
    r2, *_ = run_role(make_scope, "instrument_analyst", "SYN-EQ-0001", lambda role: build_model(Settings(model_name="stub"), role=role))
    assert r1.evidence_ids == r2.evidence_ids and r1.findings == r2.findings
    import rm_dashboard.agents.analyst as an
    src = open(an.__file__).read()
    assert "openai" not in src.lower() and "anthropic" not in src.lower()


# ---- 7.2 instrument analyst ---------------------------------------------------------------
def test_instrument_analyst_returns_valid_report(make_scope):
    r, scope, _ = run_role(make_scope, "instrument_analyst", "SYN-AL-0308")
    Report.model_validate(r.model_dump())
    assert r.agent == "instrument_analyst" and r.subject == "SYN-AL-0308" and r.as_of == AS_OF
    assert r.findings and all(set(f.evidence_ids) <= set(scope.store.results) for f in r.findings)
    assert r.status == "complete" and not r.gaps and r.flags


def test_same_run_same_evidence_ids(make_scope):
    a, *_ = run_role(make_scope, "portfolio_analyst", "PF-0001")
    b, *_ = run_role(make_scope, "portfolio_analyst", "PF-0001")
    assert a.evidence_ids == b.evidence_ids and a.findings == b.findings


# ---- 7.3 portfolio analyst delegates ------------------------------------------------------
def test_portfolio_reads_outlooks_instead_of_delegating(make_scope):
    r, scope, models = run_role(make_scope, "portfolio_analyst", "PF-0001", outlooks=True)
    assert r.children == [] and "instrument_analyst" not in models.made
    tools = {x.computation.tool for x in scope.store.results.values()}
    assert {"outlook.market", "outlook.instrument"} <= tools
    cited = {i for f in r.findings for i in f.evidence_ids}
    outlook_ids = {x.evidence_id for x in scope.store.results.values() if x.computation.tool.startswith("outlook.")}
    assert cited & outlook_ids and any(f.claim.startswith("The bank's view of") for f in r.findings)
    assert any(f.code == "house_view" for f in r.flags)


def test_custody_portfolio_not_measured_against_mandate(make_scope):
    r, *_ = run_role(make_scope, "portfolio_analyst", "PF-0002")
    assert any("custody" in f.claim and "not measured against a mandate" in f.claim for f in r.findings)


def test_mandate_breach_reported_from_tool_figures(make_scope):
    scope = make_scope()
    drift = scope.registry.toolbox("t", ["analytics.mandate_drift"], store=scope.store)
    import itertools
    from rm_dashboard.pit import PolarsPitRepository  # noqa: F401
    breached = None
    for pf in ("PF-%04d" % i for i in range(1, 25)):
        res = drift.call("analytics.mandate_drift", {"portfolio_id": pf, "as_of": "2026-08-26"})
        if res.data and res.data.get("breaches"):
            breached = pf
            break
    assert breached, "dataset has at least one mandate breach"
    r, *_ = run_role(make_scope, "portfolio_analyst", breached)
    assert any("against a maximum" in f.claim or "against a minimum" in f.claim for f in r.findings)


# ---- 7.4 relationship analyst -------------------------------------------------------------
def test_relationship_chain_and_honest_uncertainty(make_scope):
    r, scope, _ = run_role(make_scope, "relationship_analyst", "CL-0001", outlooks=True)
    assert [c.agent for c in r.children] == ["portfolio_analyst", "portfolio_analyst"]
    assert all(not g.children for g in r.children)
    deep = {i for c in r.children for i in c.evidence_ids}
    assert deep <= set(r.evidence_ids)
    assert any(f.claim.startswith("The bank's market view as of") for f in r.findings)
    assert any("Related-party data was unavailable" in f.claim for f in r.findings)
    assert {g.subject for g in r.gaps} >= {"relationships.list", "persons.list"} and r.status == "partial"
    text = " ".join(f.claim for f in r.findings)
    assert "spouse" not in text.lower() and "beneficial" not in text.lower()


def test_report_status_derived_from_gaps(make_scope):
    r, *_ = run_role(make_scope, "portfolio_analyst", "PF-0001")
    assert r.status == ("partial" if r.gaps else "complete")


# ---- 7.5 output guard ---------------------------------------------------------------------
def test_injected_uncited_number_removed_and_partial(make_scope):
    r, *_ = run_role(make_scope, "portfolio_analyst", "PF-0001", Models(mode="uncited_number"))
    assert not any("7351.24" in f.claim for f in r.findings)
    assert any(g.kind == "guard_removed" and "7351.24" in g.description for g in r.gaps)
    assert r.status == "partial"
    clean, *_ = run_role(make_scope, "portfolio_analyst", "PF-0001")
    assert len(r.findings) == len(clean.findings)


def evidence_with(**data):
    from rm_dashboard.domain import Computation, ToolResult
    store = EvidenceStore()
    r = ToolResult(data=data, as_of=AS_OF, computation=Computation(tool="t", version="1"))
    store.add(r)
    return store, r.evidence_id


def test_guard_number_rules():
    store, eid = evidence_with(share_pct=42.613, amount=1_234_567.0, count=5, name="Note ref. 8.50% p.a., 12M")
    ok = ["Share is 42.6%.", "Share is 42.61%.", "Amount is 1.23m.", "Amount is 1,234,567.", "There are 5 positions.",
          "Coupon 8.5% on 12M note.", "As of 2026-08-26 for CL-0001 and SYN-EQ-0001 see ev_0123456789abcdef.", "Rounded 1.2m",
          "Display rounding 43%."]
    bad = ["Share is 44%.", "Amount is 2.5m.", "There are 6 positions.", "Share is 42.9%."]
    out = guard_output([{"claim": c, "evidence_ids": [eid]} for c in ok + bad], "", store)
    kept = {f.claim for f in out.findings}
    assert kept == set(ok)
    assert {g.subject for g in out.gaps} >= set(b[:80] for b in bad)


def test_guard_rejects_unknown_evidence_and_missing_citations():
    store, eid = evidence_with(x=1)
    out = guard_output([{"claim": "Fine."}, {"claim": "Fine.", "evidence_ids": []},
                        {"claim": "Fine.", "evidence_ids": ["ev_deadbeefdeadbeef"]}, "junk"], "A summary with 77 in it", store)
    assert out.findings == [] and len(out.gaps) == 5
    assert out.summary == ""


def test_guard_helpers():
    assert [n.value for n in extract_numbers("up 12.5% to 3,400 or 2bn")] == [12.5, 3400.0, 2e9]
    assert evidence_numbers({"a": [1, {"b": -2.5}], "s": "see 7%"}) == {1.0, 2.5, 7.0}
    assert unsupported_numbers("value 100", {100.4}) == [] and unsupported_numbers("value 100", {101.0}) == [100.0]


# ---- 7.6 always delivered -----------------------------------------------------------------
def test_failing_tool_still_yields_report(make_scope, registry, monkeypatch):
    spec = registry.specs["analytics.pnl"]

    def boom(ctx, p):
        raise RuntimeError("pnl service down")

    monkeypatch.setitem(registry.specs, "analytics.pnl", type(spec)(**{**spec.__dict__, "fn": boom}))
    r, *_ = run_role(make_scope, "portfolio_analyst", "PF-0001")
    assert r.status == "partial"
    assert any(g.kind == "tool_error" and g.subject == "analytics.pnl" and "pnl service down" in g.description for g in r.gaps)
    assert r.findings


def test_model_failure_still_yields_report(make_scope):
    r, *_ = run_role(make_scope, "instrument_analyst", "SYN-EQ-0001", Models(mode="raise"))
    assert r.status == "partial" and any(g.kind == "agent_error" for g in r.gaps) and r.findings == []


def test_child_failure_does_not_lose_parent_report(make_scope):
    models = Models(modes={"portfolio_analyst": "raise"})
    r, *_ = run_role(make_scope, "relationship_analyst", "CL-0001", models, outlooks=True)
    assert r.status == "partial" and r.findings and len(r.children) == 2
    assert all(c.status == "partial" and any(g.kind == "agent_error" for g in c.gaps) for c in r.children)


def test_no_data_at_as_of_is_insufficient_and_calls_no_model(make_scope):
    scope = make_scope(as_of=date(2025, 1, 1))
    models = Models()
    r = analyse("relationship_analyst", "CL-0001", scope, models)
    assert r.status == "insufficient_data" and r.gaps[0].kind == "no_data" and not models.made


def test_policy_denied_tool_becomes_gap(make_scope):
    scope = make_scope(engine=ScriptedEngine(by_tool={"credit.facilities": "deny"}))
    r = analyse("relationship_analyst", "CL-0001", scope, Models())
    assert r.status == "partial"
    assert any(g.kind == "policy_denied" and g.subject == "credit.facilities" for g in r.gaps)
    assert r.findings


def test_entitlement_denied_delivers_report(make_scope):
    scope = make_scope(engine=ScriptedEngine(rules={"request_entitlement": "deny"}))
    models = Models()
    r = analyse("relationship_analyst", "CL-0001", scope, models)
    assert r.status == "insufficient_data" and r.gaps[0].kind == "policy_denied" and not models.made


# ---- policy wiring through a real run (group 6 re-check) ----------------------------------
def test_policy_and_audit_wired_through_run(make_scope):
    r, scope, _ = run_role(make_scope, "relationship_analyst", "CL-0001", outlooks=True)
    got = {d.checkpoint for d in r.policy_decisions}
    assert got >= {"request_entitlement", "tool_authorisation", "freshness_pit", "pii_minimisation", "suitability_mandate",
                   "evidence_provenance", "compliance_content", "human_approval"}
    assert all(d.mock for d in r.policy_decisions)
    recs = scope.run.audit.for_run(scope.run.run_id)
    tool_calls = [x for x in recs if x.kind == "tool_call"]
    called = {i for x in tool_calls for i in x.evidence_ids}
    assert called <= set(scope.store.results)
    # whatever else is in the store was made resolvable by an outlook tool: it is the evidence behind the outlooks
    extra = {scope.store.get(i).computation.tool for i in set(scope.store.results) - called}
    assert extra and extra <= {"instruments.context", "events.relevant", "outlook.market", "outlook.previous_market",
                               "outlook.previous_instrument", "analytics.market_trend", "news.list"}
    assert {x.agent for x in tool_calls} == {"relationship_analyst", "portfolio_analyst"}
    chains = {x.requester_chain for x in recs if x.agent == "portfolio_analyst"}
    assert chains and all(c[0] == "user" for c in chains)
    assert [x.seq for x in recs] == sorted(x.seq for x in recs) and len({x.seq for x in recs}) == len(recs)


def test_every_tool_call_has_exactly_one_audit_record(make_scope):
    r, scope, models = run_role(make_scope, "portfolio_analyst", "PF-0001")
    tool_msgs = 0
    for stubs in models.made.values():
        pass
    recs = [x for x in scope.run.audit.records if x.kind == "tool_call"]
    # count tool messages the portfolio analyst saw on its last model call
    last = models.made["portfolio_analyst"][0].seen[-1]
    seen = [m for m in last if isinstance(m, ToolMessage) and not m.name == "task"]
    own = [x for x in recs if x.agent == "portfolio_analyst"]
    assert len(own) == len(seen)


def test_prompts_contain_pseudonym_not_name(make_scope):
    r, scope, models = run_role(make_scope, "relationship_analyst", "CL-0001")
    text = " ".join(str(m.content) for stubs in models.made.values() for s in stubs for batch in s.seen for m in batch)
    assert "Hartono" not in text and "Wijaya" not in text and "Priscilla" not in text
    assert "PERSON_" in text
    assert any(rec.kind == "model_call" for rec in scope.run.audit.records)


def test_names_restored_only_in_final_report(make_scope):
    r, scope, models = run_role(make_scope, "relationship_analyst", "CL-0001")
    pseudo = scope.run.pseudonymiser.pseudonym("CL-0001")
    assert pseudo not in json.dumps(r.model_dump(mode="json"))


# ---- historical dates ---------------------------------------------------------------------
def test_historical_run_has_no_lookahead(make_scope):
    scope = make_scope(as_of=date(2026, 3, 31))
    r = analyse("relationship_analyst", "CL-0001", scope, Models())
    assert r.status in ("partial", "complete") and r.as_of == date(2026, 3, 31)
    for ev in scope.store.results.values():
        assert ev.as_of == date(2026, 3, 31)
        assert ev.effective_snapshot_date is None or ev.effective_snapshot_date <= date(2026, 3, 31)
        assert all(s.snapshot_date is None or s.snapshot_date <= date(2026, 3, 31) for s in ev.sources)


def test_model_cannot_choose_the_date(make_scope):
    scope = make_scope()
    from rm_dashboard.agents.tooladapter import make_tools
    tb = scope.registry.toolbox("x", ["clients.get"], store=scope.store)
    tool = make_tools(tb, scope)[0]
    assert "as_of" not in tool.args
    out = json.loads(tool.invoke({"client_id": "CL-0001"}))
    assert out["as_of"] == "2026-08-26"


# ---- 7.7 interactive ----------------------------------------------------------------------
def test_follow_up_reuses_earlier_evidence_and_date(make_scope):
    scope = make_scope()
    s = AnalystSession("relationship_analyst", "CL-0001", scope, Models())
    first = s.start()
    ids_before = set(scope.store.results)
    n_calls = len(s.toolbox.produced)
    second = s.ask("What about concentration?")
    assert len(s.toolbox.produced) == n_calls                       # no new tool calls
    assert second.findings and set(second.findings[0].evidence_ids) <= ids_before
    assert "single-name" in second.findings[0].claim
    assert s.as_of == AS_OF and second.as_of == AS_OF
    assert first.as_of == second.as_of
    assert s.thread_id.startswith("thread_")


def test_date_changes_only_explicitly(make_scope):
    scope = make_scope()
    s = AnalystSession("relationship_analyst", "CL-0001", scope, Models(), thread_id="t1")
    s.start()
    s.set_as_of(date(2026, 3, 31))
    r = s.ask("Re-check liquidity")
    assert s.as_of == date(2026, 3, 31) and r.as_of == date(2026, 3, 31)


# ---- point-in-time integrity of citations -------------------------------------------------
def test_session_report_never_cites_evidence_from_another_date(make_scope):
    scope = make_scope()
    s = AnalystSession("relationship_analyst", "CL-0001", scope, Models(), thread_id="t2")
    s.start()
    s.set_as_of(date(2026, 3, 31))
    r = s.ask("What about concentration?")        # the stub answers from the earlier (2026-08-26) evidence
    assert r.as_of == date(2026, 3, 31)
    assert all(scope.store.get(i).as_of == r.as_of for f in r.findings for i in f.evidence_ids)
    assert any(g.kind == "guard_removed" and "2026-08-26" in g.description for g in r.gaps)
    assert r.status == "partial"


def test_same_date_follow_up_still_reuses_evidence(make_scope):
    scope = make_scope()
    s = AnalystSession("relationship_analyst", "CL-0001", scope, Models(), thread_id="t3")
    s.start()
    r = s.ask("What about concentration?")
    assert r.findings and not [g for g in r.gaps if g.kind == "guard_removed"]


def test_guard_checks_evidence_date():
    store, eid = evidence_with(x=1)
    out = guard_output([{"claim": "Fine.", "evidence_ids": [eid]}], "", store, date(2026, 3, 31))
    assert out.findings == [] and "2026-08-26" in out.gaps[0].description
    assert guard_output([{"claim": "Fine.", "evidence_ids": [eid]}], "", store, AS_OF).findings


def test_summarizer_that_bypasses_privacy_is_replaced(make_scope, monkeypatch):
    import rm_dashboard.agents.analyst as an
    from rm_dashboard.agents.middleware import NoSummarizationMiddleware

    seen = {}
    real = an.create_deep_agent
    monkeypatch.setattr(an, "create_deep_agent", lambda **kw: seen.setdefault("mw", kw["middleware"]) and real(**kw))
    run_role(make_scope, "instrument_analyst", "SYN-EQ-0001")
    named = [m for m in seen["mw"] if m.name == "SummarizationMiddleware"]
    assert len(named) == 1 and isinstance(named[0], NoSummarizationMiddleware)


# ---- events as news ----------------------------------------------------------------------
def _news_run(make_scope):
    from rm_dashboard.agents.analyst import assemble_report

    scope = make_scope(subject="SYN-EQ-0001")
    spec = ANALYSTS["instrument_analyst"]
    tb = scope.registry.toolbox(spec.name, spec.allowlist, store=scope.store, run=scope.run)
    news = tb.call("news.list", {"as_of": AS_OF.isoformat()})
    return spec, scope, tb, news, assemble_report


def test_reading_news_records_no_news_gap(make_scope):
    spec, scope, tb, news, assemble_report = _news_run(make_scope)
    assert news.status == "ok"
    text = json.dumps({"summary": "Energy risk premium re-widened.", "findings": [
        {"claim": "A naval blockade was reimposed on 2026-08-05.", "confidence": "high", "evidence_ids": [news.evidence_id]}]})
    report = assemble_report(spec, "SYN-EQ-0001", scope, tb.produced, text, top_level=False)
    assert report.findings and not [g for g in report.gaps if g.subject == "news.list" or g.kind == "no_data"]


def test_finding_citing_event_keeps_figure_from_its_description(make_scope):
    _, scope, tb, news, _ = _news_run(make_scope)
    out = guard_output([{"claim": "Brent peaked at approximately USD 114 per barrel in May.", "confidence": "high",
                         "evidence_ids": [news.evidence_id]}], "", scope.store, AS_OF)
    assert len(out.findings) == 1 and not out.gaps
