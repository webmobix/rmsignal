from datetime import date

import pytest

from rm_dashboard.domain import Report
from rm_dashboard.policy import (
    CHECKPOINTS, AuditLog, MockPolicyEngine, PolicyDenied, PolicyEscalated, Pseudonymiser, RunContext,
    ScriptedEngine,
)
from rm_dashboard.tools import ALLOWLISTS, ToolRefused

AS_OF = date(2026, 8, 26)
ARGS = {"client_id": "CL-0001", "as_of": "2026-08-26"}


def run(engine=None, **kw):
    return RunContext("CL-0001", AS_OF, engine=engine or MockPolicyEngine(), **kw)


# ---- 6.1 ----------------------------------------------------------------------------
def test_mock_engine_allows_with_mock_reason():
    for cp in CHECKPOINTS:
        d = MockPolicyEngine().check(cp, {})
        assert d.decision == "allow" and d.mock and "mock" in d.reason and d.policy_id and d.checkpoint == cp


def test_ten_checkpoints_defined():
    assert len(CHECKPOINTS) == len(set(CHECKPOINTS)) == 10


# ---- 6.2 one decision per reached checkpoint ----------------------------------------
def test_run_trace_has_every_reached_checkpoint(registry):
    ctx = run()
    tb = registry.toolbox("relationship_analyst", ALLOWLISTS["relationship_analyst"], observer=ctx.tool_observer())
    ctx.run_start("relationship_analyst")
    tb.call("clients.get", ARGS)
    ctx.model_call("relationship_analyst", [{"role": "user", "content": "hello"}])
    ctx.a2a("outbound", "relationship_analyst", "kyc-peer", {"q": 1})
    ctx.a2a("inbound", "relationship_analyst", "kyc-peer", {"a": 1})
    report = ctx.assemble(Report(subject="CL-0001", as_of=AS_OF, status="complete", agent="relationship_analyst"),
                          "relationship_analyst")
    got = {r.checkpoint for r in report.policy_decisions}
    assert got == set(CHECKPOINTS)
    assert len(report.policy_decisions) == len(CHECKPOINTS)
    assert all(r.mock and r.decision == "allow" for r in report.policy_decisions)
    assert report.status == "complete"


def test_unreached_checkpoints_are_not_listed(registry):
    ctx = run()
    ctx.run_start("a")
    assert [r.checkpoint for r in ctx.report_decisions()] == ["request_entitlement"]


def test_decisions_aggregate_with_count(registry):
    ctx = run()
    tb = registry.toolbox("a", ALLOWLISTS["relationship_analyst"], observer=ctx.tool_observer())
    tb.call("clients.get", ARGS)
    tb.call("portfolios.list", ARGS)
    rec = {r.checkpoint: r for r in ctx.report_decisions()}
    assert rec["tool_authorisation"].count == 2 and rec["freshness_pit"].count == 2


# ---- 6.3 audit ----------------------------------------------------------------------
def test_every_tool_call_has_an_audit_record(registry):
    ctx = run()
    tb = registry.toolbox("instrument_analyst", ALLOWLISTS["instrument_analyst"], observer=ctx.tool_observer())
    calls = [("instruments.get", {"instrument_id": "SYN-EQ-0001", "as_of": "2026-08-26"}),
             ("instruments.prices", {"instrument_id": "SYN-EQ-0001", "as_of": "2026-08-26"}),
             ("credit.facilities", ARGS),                                   # refused: not in list
             ("instruments.get", {"instrument_id": "SYN-EQ-0001"})]         # invalid: no as_of
    outcomes = 0
    for name, args in calls:
        try:
            tb.call(name, args)
        except Exception:
            pass
        outcomes += 1
    recs = [r for r in ctx.audit.for_run(ctx.run_id) if r.kind in ("tool_call", "tool_refused", "tool_error")]
    assert len(recs) == outcomes == 4
    ok = [r for r in recs if r.kind == "tool_call"]
    assert len(ok) == 2 and all(r.evidence_ids and r.evidence_ids[0].startswith("ev_") for r in ok)
    for r in recs:
        assert r.run_id == ctx.run_id and r.agent == "instrument_analyst" and r.subject == "CL-0001"
        assert r.as_of == "2026-08-26" and r.input_hash


def test_audit_is_append_only_and_hash_is_stable():
    sunk = []
    log = AuditLog(sink=lambda seq, rec: sunk.append((seq, rec)))
    a = log.append(run_id="r", kind="decision", agent="x", subject="s", as_of="2026-08-26", input_hash="h")
    log.append(run_id="r", kind="decision", agent="x", subject="s", as_of="2026-08-26", input_hash="h")
    assert [r.seq for r in log.records] == [1, 2]
    assert not hasattr(log, "delete") and not hasattr(log, "update")
    with pytest.raises(Exception):
        a.kind = "other"
    assert [seq for seq, _ in sunk] == [1, 2] and sunk[0][1]["subject"] == "s"
    from rm_dashboard.policy import input_hash
    assert input_hash({"a": 1, "b": 2}) == input_hash({"b": 2, "a": 1})


# ---- 6.4 PII ------------------------------------------------------------------------
def test_prompt_contains_pseudonym_not_name():
    ctx = run()
    pseudo = ctx.pseudonymiser.register("Hartono Wijaya Kusuma", key="CL-0001")
    msgs = [{"role": "user", "content": "Review Hartono Wijaya Kusuma. Mr Wijaya prefers yield; HARTONO called."},
            {"role": "tool", "content": '{"client_name": "Hartono Wijaya Kusuma"}'}]
    safe = ctx.model_call("a", msgs)
    text = " ".join(m["content"] for m in safe)
    assert pseudo in text and "Hartono" not in text and "Wijaya" not in text and "Kusuma" not in text
    assert msgs[0]["content"].startswith("Review Hartono")                       # input untouched
    assert ctx.pseudonymiser.restore(safe[0]["content"]) == (
        "Review Hartono Wijaya Kusuma. Mr Hartono Wijaya Kusuma prefers yield; Hartono Wijaya Kusuma called.")


def test_pseudonyms_are_stable_and_entities_not_split():
    a, b = Pseudonymiser(), Pseudonymiser()
    assert a.register("Chen Wei Ling", key="CL-0008") == b.register("Chen Wei Ling", key="CL-0008")
    assert a.pseudonym("CL-0008") != a.pseudonym("CL-0009")
    p = Pseudonymiser()
    p.register("Fong Enterprises Family Office", key="CL-0017", entity=True)
    assert p.protect("Family wealth at the office; Fong Enterprises Family Office") .startswith("Family wealth at the office; PERSON_")


# ---- 6.5 deny / escalate ------------------------------------------------------------
def test_deny_blocks_tool_but_run_continues(registry):
    eng = ScriptedEngine(by_tool={"credit.facilities": "deny"})
    ctx = run(eng)
    tb = registry.toolbox("relationship_analyst", ALLOWLISTS["relationship_analyst"], observer=ctx.tool_observer())
    with pytest.raises(PolicyDenied) as e:
        tb.call("credit.facilities", ARGS)
    assert isinstance(e.value, ToolRefused) and "denied" in e.value.reason
    assert not tb.store.results                                   # tool never executed
    assert tb.call("clients.get", ARGS).status == "ok"            # run continues
    assert any(r.kind == "tool_refused" or (r.kind == "decision" and r.detail["decision"] == "deny") for r in ctx.audit.records)


def test_escalate_pauses_step_until_human_decides(registry):
    eng = ScriptedEngine(by_tool={"clients.get": "escalate"})
    ctx = run(eng)
    tb = registry.toolbox("relationship_analyst", ALLOWLISTS["relationship_analyst"], observer=ctx.tool_observer())
    with pytest.raises(PolicyEscalated) as e:
        tb.call("clients.get", ARGS)
    pid = e.value.pending_id
    assert not tb.store.results and not ctx.pending[pid].resolved
    ctx.resolve_escalation(pid, approve=True, by="compliance-officer")
    assert tb.call("clients.get", ARGS).status == "ok"            # same step now proceeds
    assert ctx.pending[pid].resolved and ctx.pending[pid].by == "compliance-officer"
    with pytest.raises(PolicyEscalated):                          # a different call is still gated
        tb.call("clients.get", {**ARGS, "client_id": "CL-0002"})


def test_report_assembly_denial_becomes_gap():
    eng = ScriptedEngine(rules={"compliance_content": "deny", "human_approval": "escalate"})
    ctx = run(eng)
    r = ctx.assemble(Report(subject="CL-0001", as_of=AS_OF, status="complete", agent="a"), "a")
    kinds = {(g.kind, g.subject) for g in r.gaps}
    assert ("policy_denied", "compliance_content") in kinds and ("policy_denied", "human_approval") in kinds
    assert r.status == "partial"
    by = {d.checkpoint: d.decision for d in r.policy_decisions}
    assert by["compliance_content"] == "deny" and by["human_approval"] == "escalate"


def test_child_context_extends_delegation_chain_and_shares_trace():
    ctx = run()
    ctx.run_start("relationship_analyst", requester="rm-priscilla")
    child = ctx.child("relationship_analyst")
    child.a2a("outbound", "portfolio_analyst", "peer", {})
    last = [r for r in ctx.audit.records if r.kind == "a2a_call"][-1]
    assert last.requester_chain == ("rm-priscilla", "relationship_analyst")
    assert child.decisions is ctx.decisions and child.run_id == ctx.run_id
