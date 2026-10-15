"""What a reconciliation delivers. ``kind`` names the source that is reconciled; only RM notes for now."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rm_dashboard.domain import Gap, PolicyDecisionRecord

Verdict = Literal["consistent", "contradicted", "unverifiable"]
ReconciliationStatus = Literal["complete", "partial", "insufficient_data"]


class NoteResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["rm_note"] = "rm_note"
    note_id: str
    note_date: date
    note_quote: str
    verdict: Verdict
    rationale: str
    finding_refs: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class Reconciliation(BaseModel):
    client_id: str
    as_of: date
    status: ReconciliationStatus
    agent: str = "note_reconciler"
    results: list[NoteResult] = []
    gaps: list[Gap] = []
    policy_decisions: list[PolicyDecisionRecord] = []
