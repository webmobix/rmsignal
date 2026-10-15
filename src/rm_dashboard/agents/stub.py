"""Deterministic stand-in for an LLM, so whole runs can be tested without a provider."""

import json
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr


class StubModelError(RuntimeError):
    pass


class StubChatModel(BaseChatModel):
    """Plays a scripted analyst. ``role`` selects the plan; ``mode`` injects failures.

    modes: ``normal``; ``uncited_number`` adds a finding with a figure absent from its evidence;
    ``raise`` fails on the first call; ``raise_after_tools`` fails when asked to write the answer.
    """

    role: str = "instrument_analyst"
    mode: str = "normal"
    _bound: list[list[str]] = PrivateAttr(default_factory=list)
    _calls: int = PrivateAttr(default=0)
    _seen: list[list[BaseMessage]] = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "stub"

    @property
    def bound_tool_names(self) -> list[list[str]]:
        return self._bound

    @property
    def seen(self) -> list[list[BaseMessage]]:
        """Every message list this model was asked to complete (what a provider would have received)."""
        return self._seen

    @property
    def calls(self) -> int:
        return self._calls

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001
        self._bound.append([getattr(t, "name", None) or t.get("name") or t["function"]["name"] for t in tools])
        return self

    # ---- generation ----------------------------------------------------------------
    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        self._calls += 1
        self._seen.append(list(messages))
        if self.mode == "raise":
            raise StubModelError("stub model failure")
        from .stubplans import plan_for  # local import: plans know tool and subagent names

        msg = plan_for(self.role, self.mode, messages)
        return ChatResult(generations=[ChatGeneration(message=msg)])


def tool_results(messages: list[BaseMessage]) -> list[dict]:
    """Parsed JSON payloads of every tool message in the conversation."""
    out = []
    for m in messages:
        if isinstance(m, ToolMessage) and isinstance(m.content, str):
            try:
                out.append(json.loads(m.content))
            except json.JSONDecodeError:
                pass
    return out


def human_text(messages: list[BaseMessage]) -> list[str]:
    return [m.content for m in messages if isinstance(m, HumanMessage) and isinstance(m.content, str)]


def first_id(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(0) if m else None
