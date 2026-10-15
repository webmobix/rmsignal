"""A2A client: call another agent and get its structured answer."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx
from google.protobuf.json_format import MessageToDict

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import get_message_text, new_data_part, new_message
from a2a.types.a2a_pb2 import Role, SendMessageRequest, TaskState


class PeerClient:
    """Synchronous facade over the async A2A client.

    ``transport`` may be an ASGI app for in-process peers (tests, the mock peer); otherwise ``base_url`` is a real endpoint.
    """

    def __init__(self, name: str, base_url: str, *, asgi_app: Any = None):
        self.name, self.base_url, self.asgi_app = name, base_url, asgi_app

    def _http(self) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=self.asgi_app) if self.asgi_app is not None else None
        return httpx.AsyncClient(transport=transport, base_url=self.base_url, timeout=60)

    async def fetch_card(self):
        async with self._http() as hc:
            return await A2ACardResolver(hc, self.base_url).get_agent_card()

    async def _ask(self, payload: dict, requester_chain: list[str]) -> dict:
        async with self._http() as hc:
            card = await A2ACardResolver(hc, self.base_url).get_agent_card()
            client = ClientFactory(ClientConfig(httpx_client=hc, streaming=False)).create(card)
            msg = new_message([new_data_part(payload, media_type="application/json")], role=Role.ROLE_USER)
            msg.metadata.update({"requester_chain": requester_chain})
            final = None
            async for resp in client.send_message(SendMessageRequest(message=msg)):
                if resp.HasField("task"):
                    final = resp.task
            if final is None:
                return {"state": "no_task", "data": {}, "text": ""}
            data: dict = {}
            for art in final.artifacts:
                for part in art.parts:
                    if part.HasField("data"):
                        v = MessageToDict(part.data)
                        data = v if isinstance(v, dict) else {"value": v}
            text = get_message_text(final.status.message) if final.status.HasField("message") else ""
            state = TaskState.Name(final.status.state).removeprefix("TASK_STATE_").lower()
            return {"state": state, "data": data, "text": text, "task_id": final.id}

    def ask(self, payload: dict, *, requester_chain: list[str] | None = None) -> dict:
        """Send a task and wait for the result: ``{state, data, text}`` (state e.g. ``completed``, ``input_required``)."""
        coro = self._ask(payload, list(requester_chain or []))
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        with ThreadPoolExecutor(1) as pool:  # called from inside a running loop: use a private one
            return pool.submit(asyncio.run, coro).result()
