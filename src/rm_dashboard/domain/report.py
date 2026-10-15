"""The report every analysis run delivers, whatever happens."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .evidence import QualityFlag

ReportStatus = Literal["complete", "partial", "insufficient_data"]


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim: str
    confidence: Literal["high", "medium", "low"] = "medium"
    evidence_ids: list[str] = Field(min_length=1)


class Gap(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["tool_error", "no_data", "policy_denied", "guard_removed", "agent_error", "other"]
    description: str
    subject: str | None = None


class PolicyDecisionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    checkpoint: str
    decision: Literal["allow", "deny", "escalate"]
    reason: str
    policy_id: str
    mock: bool = False
    count: int = 1


class Report(BaseModel):
    subject: str
    as_of: date
    status: ReportStatus
    agent: str
    summary: str = ""
    findings: list[Finding] = []
    gaps: list[Gap] = []
    flags: list[QualityFlag] = []
    policy_decisions: list[PolicyDecisionRecord] = []
    evidence_ids: list[str] = []
    children: list["Report"] = []
