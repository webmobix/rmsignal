"""Agent middleware: tool visibility and personal-data minimisation on every model call."""

from collections.abc import Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langchain_core.messages import BaseMessage, ToolMessage

from rm_dashboard.policy import PolicyDenied, PolicyEscalated

from .scope import RunScope

DELEGATION_TOOL = "task"


class AllowListMiddleware(AgentMiddleware):
    """Only allow-listed tools (and the delegation tool) are shown to the model or executed.

    Deep Agents adds filesystem, planning and general-purpose tools; none of them may reach the model.
    """

    def __init__(self, allowed: set[str], delegates: set[str]):
        super().__init__()
        self.allowed = set(allowed)
        self.delegates = set(delegates)

    def _visible(self) -> set[str]:
        return self.allowed | ({DELEGATION_TOOL} if self.delegates else set())

    def wrap_model_call(self, request: ModelRequest, handler: Callable):
        tools = [t for t in request.tools if getattr(t, "name", None) in self._visible()]
        return handler(request.override(tools=tools))

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        name = call["name"]
        if name not in self._visible():
            return ToolMessage(content=f"tool {name!r} is not available", tool_call_id=call["id"], name=name, status="error")
        if name == DELEGATION_TOOL and call["args"].get("subagent_type") not in self.delegates:
            return ToolMessage(content="unknown subagent", tool_call_id=call["id"], name=name, status="error")
        return handler(request)


class PrivacyMiddleware(AgentMiddleware):
    """Routes every model call through the run's PII checkpoint and pseudonymiser, tool results included."""

    def __init__(self, scope: RunScope, agent: str):
        super().__init__()
        self.scope, self.agent = scope, agent

    def _protect(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        plain = [{"role": m.type, "content": m.content if isinstance(m.content, str) else str(m.content)} for m in messages]
        safe = self.scope.run.model_call(self.agent, plain)
        return [m.model_copy(update={"content": s["content"]}) if isinstance(m.content, str) else m
                for m, s in zip(messages, safe)]

    def wrap_model_call(self, request: ModelRequest, handler: Callable):
        system = request.system_message
        if system is not None and isinstance(system.content, str):
            system = system.model_copy(update={"content": self.scope.run.pseudonymiser.protect(system.content)})
        try:
            messages = self._protect(request.messages)
        except (PolicyDenied, PolicyEscalated):
            raise
        return handler(request.override(messages=messages, system_message=system))


class NoSummarizationMiddleware(AgentMiddleware):
    """Replaces Deep Agents' summarizer, which calls the model directly and would bypass the PII checkpoint,
    the pseudonymiser and the audit record, and would also drop tool results that findings must cite.

    Analyst conversations are bounded by their tool set, so no compaction is needed.
    """

    @property
    def name(self) -> str:
        return "SummarizationMiddleware"
