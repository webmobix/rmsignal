"""What the client-actions stage delivers."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rm_dashboard.domain import Gap, PolicyDecisionRecord

Category = Literal["compliance_kyc", "concentration_risk", "mandate_drift", "liquidity_cash_needs", "credit_collateral",
                   "client_contact", "data_quality"]
Importance = Literal["critical", "high", "medium", "low"]
Horizon = Literal["immediate", "within_30_days", "within_90_days", "later", "none"]
ActionsStatus = Literal["complete", "partial", "insufficient_data"]

CATEGORIES = ("compliance_kyc", "concentration_risk", "mandate_drift", "liquidity_cash_needs", "credit_collateral",
              "client_contact", "data_quality")
IMPORTANCE_ORDER = ("critical", "high", "medium", "low")
HORIZON_ORDER = ("immediate", "within_30_days", "within_90_days", "later", "none")


class SourceRef(BaseModel):
    """What an action rests on: a report finding (``CL-0001#f7``), a reconciled note (``N-001``) or a mandate
    reconciliation result (``PF-0009/band/Commodities``, with its status, breach kind and the notes it cites)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["finding", "note", "mandate"]
    ref: str
    report_path: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    mandate_status: Literal["no_note", "acknowledged", "client_directed", "contradicted"] | None = None
    breach_kind: Literal["band", "position", "exclusion"] | None = None
    note_ids: list[str] = Field(default_factory=list)


class Action(BaseModel):
    rank: int = 0
    title: str
    what: str
    why: str
    category: Category
    importance: Importance
    importance_raised_from: Importance | None = None
    horizon: Horizon = "none"
    due_date: date | None = None
    sources: list[SourceRef] = Field(min_length=1)


class NotActioned(BaseModel):
    """A contradicted note or mandate result that no action covers; ``note_id`` is the mandate result's ref when ``kind`` is ``mandate``."""

    model_config = ConfigDict(frozen=True)

    note_id: str
    rationale: str
    kind: Literal["note", "mandate"] = "note"


class ClientActions(BaseModel):
    client_id: str
    as_of: date
    status: ActionsStatus
    agent: str = "client_actions"
    actions: list[Action] = []
    not_actioned: list[NotActioned] = []
    gaps: list[Gap] = []
    policy_decisions: list[PolicyDecisionRecord] = []
