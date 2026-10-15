"""The evidence envelope: every tool result carries data, provenance and a content-hash id."""

import hashlib
import json
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

Status = Literal["ok", "partial", "insufficient_data", "insufficient_history", "no_data"]


class Source(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset: str
    key: str
    snapshot_date: date | None = None


class Computation(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool: str
    version: str
    parameters: dict[str, Any] = {}
    method: str = ""


class QualityFlag(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    subject: str | None = None


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


class ToolResult(BaseModel):
    """Result of one tool call. ``evidence_id`` is derived from the content, never supplied."""

    model_config = ConfigDict(frozen=True)

    data: Any = None
    as_of: date
    effective_snapshot_date: date | None = None
    gap_days: int | None = None
    status: Status = "ok"
    reason: str | None = None
    sources: list[Source] = []
    computation: Computation
    flags: list[QualityFlag] = []
    pit: str | None = None
    mock: bool = False
    evidence_id: str = ""

    @model_validator(mode="after")
    def _seal(self) -> "ToolResult":
        if self.status != "ok" and not self.reason:
            raise ValueError(f"status {self.status!r} requires a reason")
        digest = hashlib.sha256(
            canonical(self.model_dump(mode="json", exclude={"evidence_id"})).encode()
        ).hexdigest()
        object.__setattr__(self, "evidence_id", f"ev_{digest[:16]}")
        return self
