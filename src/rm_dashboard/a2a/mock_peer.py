"""A mock KYC/compliance agent standing in for a bank system the MVP does not have."""

from google.protobuf.json_format import MessageToDict
from starlette.applications import Starlette

from a2a.helpers.proto_helpers import new_data_artifact_update_event, new_task_from_user_message, new_text_status_update_event
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue_v2 import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types.a2a_pb2 import (
    AgentCapabilities, AgentCard, AgentInterface, AgentSkill, TaskState,
)

from .server import requester_chain, task_payload

PEER_NAME = "mock-kyc-peer"


class MockKycExecutor(AgentExecutor):
    """Answers every client the same way. ``received`` records what callers sent, for tests."""

    def __init__(self):
        self.received: list[dict] = []

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        tid, cid = context.task_id, context.context_id
        await event_queue.enqueue_event(new_task_from_user_message(context.message))
        payload = task_payload(context)
        if not payload.get("client_id") or not payload.get("as_of"):
            await event_queue.enqueue_event(new_text_status_update_event(
                tid, cid, TaskState.TASK_STATE_INPUT_REQUIRED, "input required: client_id and as_of"))
            return
        self.received.append({**payload, "requester_chain": list(requester_chain(context))})
        answer = {"client_id": payload["client_id"], "as_of": payload["as_of"], "kyc_status": "no adverse findings",
                  "screening": "sanctions and PEP screening clear", "mock": True, "peer": PEER_NAME}
        await event_queue.enqueue_event(new_data_artifact_update_event(
            tid, cid, "kyc_status", answer, media_type="application/json", last_chunk=True))
        await event_queue.enqueue_event(new_text_status_update_event(tid, cid, TaskState.TASK_STATE_COMPLETED, "ok"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(new_text_status_update_event(
            context.task_id, context.context_id, TaskState.TASK_STATE_CANCELED, "cancelled"))


def build_mock_card(base_url: str) -> AgentCard:
    return AgentCard(
        name=PEER_NAME, description="MOCK KYC and compliance agent: returns a fixed answer for any client.", version="1",
        supported_interfaces=[AgentInterface(url=base_url, protocol_binding="JSONRPC", protocol_version="1.0")],
        capabilities=AgentCapabilities(streaming=False), default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[AgentSkill(id="kyc_status", name="KYC status", description="KYC and screening status. Requires client_id and as_of.",
                           tags=["kyc", "compliance", "mock"])],
    )


def create_mock_kyc_app(base_url: str = "http://kyc-peer") -> tuple[Starlette, MockKycExecutor]:
    card, executor = build_mock_card(base_url), MockKycExecutor()
    handler = DefaultRequestHandler(executor, InMemoryTaskStore(), card)
    return Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/")]), executor
