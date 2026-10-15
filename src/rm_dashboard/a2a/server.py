"""A2A server adapters: each analyst answers tasks with the report contract."""

import asyncio
import json
from dataclasses import dataclass
from datetime import date

from google.protobuf.json_format import MessageToDict
from starlette.applications import Starlette

from a2a.helpers.proto_helpers import (
    get_message_text, new_data_artifact_update_event, new_task_from_user_message, new_text_status_update_event,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue_v2 import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types.a2a_pb2 import TaskState

from rm_dashboard.agents import RunScope, analyse
from rm_dashboard.agents.analyst import ANALYSTS, ModelFactory
from rm_dashboard.agents.scope import register_people
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyDenied, PolicyEscalated, PolicyEngine, RunContext
from rm_dashboard.tools import ToolRegistry

from .cards import build_card, required_inputs

DEFAULT_REQUESTER = "a2a-peer"


@dataclass
class AnalystRuntime:
    """Everything an A2A server needs to run an analysis for a remote caller."""

    registry: ToolRegistry
    models: ModelFactory
    engine: PolicyEngine = None  # type: ignore[assignment]
    audit: AuditLog = None  # type: ignore[assignment]

    def __post_init__(self):
        self.engine = self.engine or MockPolicyEngine()
        self.audit = self.audit if self.audit is not None else AuditLog()


def task_payload(context: RequestContext) -> dict:
    """The structured request: a data part, else a JSON text part."""
    msg = context.message
    for part in msg.parts if msg else []:
        if part.HasField("data"):
            v = MessageToDict(part.data)
            if isinstance(v, dict):
                return v
    try:
        v = json.loads(get_message_text(msg)) if msg else {}
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        return {}


def requester_chain(context: RequestContext) -> tuple[str, ...]:
    md = MessageToDict(context.message.metadata) if context.message and context.message.HasField("metadata") else {}
    chain = md.get("requester_chain")
    return tuple(str(c) for c in chain) if isinstance(chain, list) and chain else (DEFAULT_REQUESTER,)


class AnalystExecutor(AgentExecutor):
    def __init__(self, role: str, runtime: AnalystRuntime):
        self.role, self.runtime = role, runtime
        self.spec = ANALYSTS[role]

    def _validate(self, payload: dict) -> tuple[date | None, str | None, str | None]:
        need = required_inputs(self.role)
        raw_date, subject = payload.get("as_of"), payload.get(need[1])
        try:
            as_of = date.fromisoformat(raw_date) if isinstance(raw_date, str) else None
        except ValueError:
            as_of = None
        missing = [n for n, v in (("as_of", as_of), (need[1], subject)) if not v]
        if missing:
            return None, None, f"input required: {', '.join(missing)} (as_of is YYYY-MM-DD)"
        return as_of, str(subject), None

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id, ctx_id = context.task_id, context.context_id
        await event_queue.enqueue_event(new_task_from_user_message(context.message))
        as_of, subject, problem = self._validate(task_payload(context))
        if problem:
            await event_queue.enqueue_event(new_text_status_update_event(task_id, ctx_id, TaskState.TASK_STATE_INPUT_REQUIRED, problem))
            return
        chain = requester_chain(context)
        await event_queue.enqueue_event(new_text_status_update_event(task_id, ctx_id, TaskState.TASK_STATE_WORKING, "analysing"))
        try:
            outcome = await asyncio.to_thread(self._run, subject, as_of, chain)
        except Exception as e:  # noqa: BLE001 - a crashed adapter is a failed task, never a hung one
            await event_queue.enqueue_event(new_text_status_update_event(
                task_id, ctx_id, TaskState.TASK_STATE_FAILED, f"{type(e).__name__}: {e}"))
            return
        if isinstance(outcome, str):
            await event_queue.enqueue_event(new_text_status_update_event(task_id, ctx_id, TaskState.TASK_STATE_REJECTED, outcome))
            return
        await event_queue.enqueue_event(new_data_artifact_update_event(
            task_id, ctx_id, "report", outcome.model_dump(mode="json"), media_type="application/json", last_chunk=True))
        await event_queue.enqueue_event(new_text_status_update_event(
            task_id, ctx_id, TaskState.TASK_STATE_COMPLETED, f"report status: {outcome.status}"))

    def _run(self, subject: str, as_of: date, chain: tuple[str, ...]):
        rt = self.runtime
        run = RunContext(subject, as_of, engine=rt.engine, audit=rt.audit, requester_chain=chain)
        register_people(run, rt.registry.ctx.repo, as_of)
        try:
            run.a2a("inbound", self.role, chain[-1], {"subject": subject, "as_of": as_of.isoformat()})
        except (PolicyDenied, PolicyEscalated) as e:
            return e.reason
        scope = RunScope(run=run, registry=rt.registry)
        return analyse(self.role, subject, scope, rt.models, requester=chain[0])

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(new_text_status_update_event(
            context.task_id, context.context_id, TaskState.TASK_STATE_CANCELED, "cancelled"))


def create_analyst_app(role: str, runtime: AnalystRuntime, base_url: str = "http://localhost") -> Starlette:
    card = build_card(role, base_url)
    handler = DefaultRequestHandler(AnalystExecutor(role, runtime), InMemoryTaskStore(), card)
    return Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/")])
