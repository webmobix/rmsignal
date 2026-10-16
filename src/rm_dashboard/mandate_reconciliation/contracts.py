"""What a mandate reconciliation delivers: one status per computed breach, with the notes it rests on."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from rm_dashboard.domain import Gap, PolicyDecisionRecord

BreachKind = Literal["band", "position", "exclusion"]
BreachStatus = Literal["no_note", "acknowledged", "client_directed", "contradicted"]
MandateReconciliationStatus = Literal["complete", "partial", "insufficient_data"]

STATUSES: tuple[str, ...] = ("no_note", "acknowledged", "client_directed", "contradicted")
PRECEDENCE: tuple[str, ...] = ("contradicted", "client_directed", "acknowledged", "no_note")
"""Most consequential reading first: it wins when several notes bear on one breach."""


class NoteQuote(BaseModel):
    model_config = ConfigDict(frozen=True)

    note_id: str
    note_date: date
    quote: str


class BreachResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: str
    kind: BreachKind
    key: str
    evidence_id: str
    description: str
    status: BreachStatus = "no_note"
    rationale: str = ""
    notes: list[NoteQuote] = Field(default_factory=list)
    waiver_claimed: bool = False

    @computed_field
    @property
    def ref(self) -> str:
        return f"{self.portfolio_id}/{self.kind}/{self.key}"

    @computed_field
    @property
    def note_ids(self) -> list[str]:
        return [n.note_id for n in self.notes]


class AmbiguousNote(BaseModel):
    model_config = ConfigDict(frozen=True)

    note_id: str
    note_date: date
    quote: str
    reason: str


class MandateReconciliation(BaseModel):
    client_id: str
    as_of: date
    status: MandateReconciliationStatus
    agent: str = "mandate_reconciler"
    results: list[BreachResult] = []
    ambiguous_notes: list[AmbiguousNote] = []
    gaps: list[Gap] = []
    policy_decisions: list[PolicyDecisionRecord] = []
