"""Tools that consult other bank agents over the agent-to-agent protocol."""

from rm_dashboard.domain import QualityFlag, Source, ToolResult

from .envelope import build_result
from .spec import ClientParams, ToolContext, ToolSpec

PEER_NAME = "kyc"


def kyc_status(ctx: ToolContext, p: ClientParams):
    peer = ctx.peers.get(PEER_NAME)
    if peer is None:
        return build_result(tool="peers.kyc_status", version="1", params=p, as_of=p.as_of, data=None,
                            status="no_data", reason="no KYC/compliance peer agent is configured")
    chain = [*(ctx.run.requester_chain if ctx.run else ()), ctx.agent]
    payload = {"client_id": p.client_id, "as_of": p.as_of.isoformat()}
    if ctx.run:
        ctx.run.a2a("outbound", ctx.agent, peer.name, payload)
    answer = peer.ask(payload, requester_chain=chain)
    if ctx.run:
        ctx.run.a2a("inbound", ctx.agent, peer.name, {"state": answer["state"]})
    flags = [
        QualityFlag(code="mock_peer", message=f"answer comes from a mock peer agent ({peer.name}), not a real KYC system"),
        QualityFlag(code="peer_answer_not_point_in_time", message="the peer's answer is not guaranteed to reflect as_of"),
    ]
    sources = [Source(dataset=f"a2a:{peer.name}", key=p.client_id)]
    if answer["state"] != "completed":
        return build_result(tool="peers.kyc_status", version="1", params=p, as_of=p.as_of, data=answer, status="no_data",
                            reason=f"peer {peer.name} returned task state {answer['state']}", extra_flags=flags, mock=True)
    result = build_result(tool="peers.kyc_status", version="1", params=p, as_of=p.as_of,
                          data={"peer": peer.name, **answer["data"]}, extra_flags=flags, mock=True, pit_tag="peer")
    # the peer's identity is the source of this evidence
    return ToolResult(**{**result.model_dump(exclude={"evidence_id"}), "sources": sources})


PEER_TOOLS = [
    ToolSpec("peers.kyc_status", "KYC and compliance status of a client from the bank's KYC peer agent (A2A).",
             ClientParams, kyc_status, "peer"),
]
