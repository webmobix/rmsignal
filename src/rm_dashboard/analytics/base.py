"""Shared result type and method registry for the deterministic analytics."""

from dataclasses import dataclass, field
from typing import Any

from rm_dashboard.domain import QualityFlag

METHODS: dict[str, str] = {}
"""Analytic name -> method string. Every analytic registers exactly one."""


def register(name: str, method: str) -> str:
    METHODS[name] = method
    return method


@dataclass(frozen=True)
class Calc:
    """Output of one pure calculation. ``data`` is JSON-serialisable."""

    name: str
    data: dict[str, Any]
    method: str
    status: str = "ok"
    reason: str | None = None
    flags: list[QualityFlag] = field(default_factory=list)


def insufficient(name: str, reason: str, method: str, status: str = "insufficient_data", **data: Any) -> Calc:
    return Calc(name, dict(data), method, status, reason)
