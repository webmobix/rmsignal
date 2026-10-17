"""Tool registry with per-agent allow-lists and a run-scoped evidence store."""

from collections.abc import Iterable
import dataclasses
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import ValidationError

from rm_dashboard.domain import ToolResult

from .analytics_tools import ANALYTICS_TOOLS
from .domain_tools import DOMAIN_TOOLS
from .outlook_tools import OUTLOOK_TOOLS
from .peer_tools import PEER_TOOLS
from .scenario_tools import SCENARIO_TOOLS
from .spec import ToolContext, ToolSpec


class ToolRefused(Exception):
    """The call is outside the agent's allow-list or was denied by policy."""

    def __init__(self, agent: str, tool: str, reason: str):
        super().__init__(f"{agent} may not call {tool}: {reason}")
        self.agent, self.tool, self.reason = agent, tool, reason


class ToolObserver(Protocol):
    """Hook for policy and audit. ``before`` may raise ``ToolRefused``."""

    def before(self, agent: str, tool: str, args: dict[str, Any]) -> None: ...
    def after(self, agent: str, tool: str, args: dict[str, Any], result: ToolResult) -> None: ...
    def refused(self, agent: str, tool: str, reason: str) -> None: ...
    def failed(self, agent: str, tool: str, args: dict[str, Any], error: Exception) -> None: ...


@dataclass
class EvidenceStore:
    """Every tool result produced in one run, by evidence id."""

    results: dict[str, ToolResult] = field(default_factory=dict)

    def add(self, r: ToolResult) -> None:
        self.results[r.evidence_id] = r

    def get(self, evidence_id: str) -> ToolResult | None:
        return self.results.get(evidence_id)

    def __contains__(self, evidence_id: str) -> bool:
        return evidence_id in self.results


@dataclass(frozen=True)
class Refusal:
    agent: str
    tool: str
    reason: str


class ToolRegistry:
    def __init__(self, ctx: ToolContext, specs: Iterable[ToolSpec] | None = None):
        self.ctx = ctx
        self.specs: dict[str, ToolSpec] = {s.name: s for s in (specs or [*DOMAIN_TOOLS, *ANALYTICS_TOOLS, *PEER_TOOLS, *OUTLOOK_TOOLS, *SCENARIO_TOOLS])}

    def names(self) -> list[str]:
        return sorted(self.specs)

    def toolbox(self, agent: str, allowed: Iterable[str], *, store: EvidenceStore | None = None,
                observer: ToolObserver | None = None, run: Any = None) -> "Toolbox":
        allowed = tuple(allowed)
        unknown = [a for a in allowed if a not in self.specs]
        if unknown:
            raise KeyError(f"allow-list of {agent} names unknown tools: {unknown}")
        return Toolbox(self, agent, allowed, store or EvidenceStore(), observer, run)


class Toolbox:
    def __init__(self, registry: ToolRegistry, agent: str, allowed: tuple[str, ...], store: EvidenceStore,
                 observer: ToolObserver | None, run: Any = None):
        self.registry, self.agent, self.allowed = registry, agent, allowed
        self.store, self.observer, self.run = store, observer, run
        self.refusals: list[Refusal] = []
        self.produced: list[ToolResult] = []

    def specs(self) -> list[ToolSpec]:
        return [self.registry.specs[n] for n in self.allowed]

    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        if name not in self.allowed:
            return self._refuse(name, "not in the agent's allow-list")
        spec = self.registry.specs[name]
        try:
            params = spec.params.model_validate(args)
        except ValidationError:
            if self.observer:
                self.observer.failed(self.agent, name, args, ValueError("invalid arguments"))
            raise
        clean = params.model_dump(mode="json")
        if self.observer:
            try:
                self.observer.before(self.agent, name, clean)
            except ToolRefused as e:
                self.refusals.append(Refusal(self.agent, name, e.reason))
                raise
        try:
            ctx = dataclasses.replace(self.registry.ctx, run=self.run, agent=self.agent, store=self.store)
            result = spec.fn(ctx, params)
        except Exception as e:
            if self.observer:
                self.observer.failed(self.agent, name, clean, e)
            raise
        self.store.add(result)
        self.produced.append(result)
        if self.observer:
            try:
                self.observer.after(self.agent, name, clean, result)
            except ToolRefused as e:
                self.store.results.pop(result.evidence_id, None)
                self.produced.pop()
                self.refusals.append(Refusal(self.agent, name, e.reason))
                raise
        return result

    def _refuse(self, name: str, reason: str):
        self.refusals.append(Refusal(self.agent, name, reason))
        if self.observer:
            self.observer.refused(self.agent, name, reason)
        raise ToolRefused(self.agent, name, reason)
