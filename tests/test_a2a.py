from datetime import date

import pytest

from rm_dashboard.a2a import (
    PEER_NAME, AnalystRuntime, PeerClient, build_card, create_analyst_app, create_mock_kyc_app, required_inputs,
)
from rm_dashboard.agents import ANALYSTS, RunScope, StubChatModel, analyse
from rm_dashboard.domain import Report
from rm_dashboard.policy import AuditLog, RunContext, ScriptedEngine
from rm_dashboard.tools import ToolContext, ToolRegistry

AS_OF = "2026-08-26"


def stub(role):
    return StubChatModel(role=role)


@pytest.fixture
def mock_kyc():
    app, executor = create_mock_kyc_app()
    return PeerClient(PEER_NAME, "http://kyc-peer", asgi_app=app), executor


@pytest.fixture
def peer_registry(pit_repo, mock_kyc):
    client, _ = mock_kyc
    return ToolRegistry(ToolContext(pit_repo, peers={"kyc": client}))


def server(role, registry, engine=None):
    rt = AnalystRuntime(registry, stub, engine=engine, audit=AuditLog())
    return PeerClient(role, f"http://{role}", asgi_app=create_analyst_app(role, rt, f"http://{role}")), rt


# ---- 8.1 agent cards ------------------------------------------------------------------------
@pytest.mark.parametrize("role,key", [("relationship_analyst", "client_id"), ("portfolio_analyst", "portfolio_id"),
                                      ("instrument_analyst", "instrument_id")])
def test_cards_list_skills_and_required_inputs(registry, role, key):
    client, _ = server(role, registry)
    import asyncio
    card = asyncio.run(client.fetch_card())
    assert card.name == role and len(card.skills) == 1 and card.skills[0].id.endswith("analysis")
    ext = next(iter(card.capabilities.extensions))
    required = list(ext.params["required"])
    assert required == ["as_of", key] == required_inputs(role)
    assert "as_of" in card.skills[0].description
    assert "bearer" in card.security_schemes and card.security_requirements
    assert card.supported_interfaces[0].protocol_binding == "JSONRPC"


def test_card_served_at_well_known_location(registry):
    import httpx
    from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH

    rt = AnalystRuntime(registry, stub)
    app = create_analyst_app("portfolio_analyst", rt)

    async def get():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://x") as hc:
            return await hc.get(AGENT_CARD_WELL_KNOWN_PATH)

    import asyncio
    r = asyncio.run(get())
    assert r.status_code == 200 and r.json()["name"] == "portfolio_analyst" and r.json()["skills"]
    assert build_card("portfolio_analyst", "http://x").version


# ---- 8.2 callable over the protocol -----------------------------------------------------------
def test_remote_portfolio_analysis_returns_report(registry):
    client, rt = server("portfolio_analyst", registry)
    out = client.ask({"as_of": AS_OF, "portfolio_id": "PF-0001"}, requester_chain=["rm-priscilla"])
    assert out["state"] == "completed"
    report = Report.model_validate(out["data"])
    assert report.subject == "PF-0001" and report.agent == "portfolio_analyst" and report.findings
    assert report.as_of == date(2026, 8, 26)
    assert "report status" in out["text"]


@pytest.mark.parametrize("payload", [{"portfolio_id": "PF-0001"}, {"as_of": AS_OF}, {"as_of": "26/08/2026", "portfolio_id": "PF-0001"}, {}])
def test_missing_inputs_is_input_required_and_runs_nothing(registry, payload):
    client, rt = server("portfolio_analyst", registry)
    out = client.ask(payload)
    assert out["state"] == "input_required" and "input required" in out["text"]
    assert out["data"] == {} and rt.audit.records == ()


def test_wrong_subject_key_for_role_is_input_required(registry):
    client, _ = server("portfolio_analyst", registry)
    assert client.ask({"as_of": AS_OF, "client_id": "CL-0001"})["state"] == "input_required"


def test_inbound_policy_denial_rejects_task(registry):
    client, rt = server("portfolio_analyst", registry, engine=ScriptedEngine(rules={"a2a_inbound": "deny"}))
    out = client.ask({"as_of": AS_OF, "portfolio_id": "PF-0001"})
    assert out["state"] == "rejected" and "denied" in out["text"]


def test_no_data_at_as_of_still_returns_report_over_protocol(registry):
    client, _ = server("portfolio_analyst", registry)
    out = client.ask({"as_of": "2025-01-01", "portfolio_id": "PF-0001"})
    assert out["state"] == "completed" and out["data"]["status"] == "insufficient_data"


# ---- 8.3 consuming an external agent ----------------------------------------------------------
def test_kyc_peer_answer_is_mock_flagged_evidence(peer_registry, mock_kyc):
    _, executor = mock_kyc
    run = RunContext("CL-0001", date(2026, 8, 26), audit=AuditLog())
    scope = RunScope(run=run, registry=peer_registry)
    report = analyse("relationship_analyst", "CL-0001", scope, stub)
    ev = next(r for r in scope.store.results.values() if r.computation.tool == "peers.kyc_status")
    assert ev.status == "ok" and ev.mock and ev.data["peer"] == PEER_NAME and ev.data["mock"] is True
    assert [s.dataset for s in ev.sources] == [f"a2a:{PEER_NAME}"]
    assert {"mock_peer", "peer_answer_not_point_in_time"} <= {f.code for f in ev.flags}
    claim = next(f for f in report.findings if "KYC peer" in f.claim)
    assert ev.evidence_id in claim.evidence_ids and "mock" in claim.claim
    assert "mock_peer" in {f.code for f in report.flags}
    assert executor.received and executor.received[0]["client_id"] == "CL-0001"
    assert not any(g.subject == "peers.kyc_status" for g in report.gaps)


def test_missing_peer_is_a_gap_not_a_failure(registry):
    scope = RunScope(run=RunContext("CL-0001", date(2026, 8, 26)), registry=registry)
    report = analyse("relationship_analyst", "CL-0001", scope, stub)
    assert any(g.subject == "peers.kyc_status" and "no KYC" in g.description for g in report.gaps)
    assert report.findings


def test_peer_outbound_and_inbound_checkpoints(peer_registry):
    run = RunContext("CL-0001", date(2026, 8, 26), audit=AuditLog())
    report = analyse("relationship_analyst", "CL-0001", RunScope(run=run, registry=peer_registry), stub)
    by = {d.checkpoint: d for d in report.policy_decisions}
    assert "a2a_outbound" in by and "a2a_inbound" in by and by["a2a_outbound"].mock


def test_outbound_denial_becomes_gap(peer_registry):
    run = RunContext("CL-0001", date(2026, 8, 26), engine=ScriptedEngine(rules={"a2a_outbound": "deny"}), audit=AuditLog())
    report = analyse("relationship_analyst", "CL-0001", RunScope(run=run, registry=peer_registry), stub)
    assert any(g.kind == "policy_denied" and g.subject == "peers.kyc_status" for g in report.gaps)
    assert report.status == "partial" and report.findings


# ---- 8.4 delegation chain ---------------------------------------------------------------------
def test_audit_lists_original_requester_across_hops(peer_registry, mock_kyc):
    _, executor = mock_kyc
    client, rt = server("relationship_analyst", peer_registry)
    out = client.ask({"as_of": AS_OF, "client_id": "CL-0001"}, requester_chain=["rm-priscilla", "workbench"])
    assert out["state"] == "completed"
    recs = rt.audit.records
    assert recs and all(r.requester_chain[:2] == ("rm-priscilla", "workbench") for r in recs)
    agents = {r.agent for r in recs}
    assert {"relationship_analyst", "portfolio_analyst"} <= agents and "instrument_analyst" not in agents
    inbound = [r for r in recs if r.kind == "a2a_call" and r.detail["direction"] == "inbound"]
    outbound = [r for r in recs if r.kind == "a2a_call" and r.detail["direction"] == "outbound"]
    assert inbound and outbound
    # the peer we called saw the whole chain, ending with the calling agent
    got = executor.received[0]["requester_chain"]
    assert got[:2] == ["rm-priscilla", "workbench"] and got[-1] == "relationship_analyst"
    report = Report.model_validate(out["data"])
    assert {"a2a_inbound", "a2a_outbound"} <= {d.checkpoint for d in report.policy_decisions}


def test_default_requester_when_none_given(registry):
    client, rt = server("instrument_analyst", registry)
    client.ask({"as_of": AS_OF, "instrument_id": "SYN-EQ-0001"})
    assert {r.requester_chain[0] for r in rt.audit.records} == {"a2a-peer"}
