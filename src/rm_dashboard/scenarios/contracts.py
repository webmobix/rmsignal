"""Scenario contracts: the catalogue record, the market shock vector, the portfolio impact and the client and RM roll-ups.

Every figure in an impact or roll-up is computed by code. A model supplies channel moves (layer A), mapping proposals and prose (layer B).
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rm_dashboard.domain import Gap, PolicyDecisionRecord
from rm_dashboard.outlook.contracts import EventRef

Case = Literal["best", "likely", "worst"]
CASES: tuple[str, ...] = ("best", "likely", "worst")
RunStatus = Literal["complete", "partial", "insufficient_data"]
Mapping = Literal["rule", "look_through", "agent", "untouched"]
ChannelKind = Literal["market", "overlay", "fx"]

DEFAULT_HORIZON_MONTHS = 3
NOT_A_PROBABILITY = ("Conditional on this scenario: the likely case is a central case, not a probability. "
                     "Best and worst bracket it; they are not forecasts of the extremes.")
NOT_ANCHORED = "Not anchored to history: no comparable past event exists in the event log."


# ---- catalogue ----------------------------------------------------------------------------------
class ScenarioRecord(BaseModel):
    """A scenario is text. Adding one never needs a code change."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1)
    premise: str = Field(min_length=1)
    mirrors: str = ""
    """The event or series the scenario mirrors, written as ``Event log YYYY-MM-DD: ...`` when it is an event."""
    horizon_months: int = Field(default=DEFAULT_HORIZON_MONTHS, ge=1, le=36)
    caveat: str = NOT_A_PROBABILITY
    created_at: datetime | None = None

    @field_validator("name", "premise")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


# ---- layer A: the market shock vector -----------------------------------------------------------
class ChannelMove(BaseModel):
    """Best, likely and worst move of one channel over the horizon, in percent. Worst <= likely <= best."""

    channel: str
    best: float
    likely: float
    worst: float
    rationale: str = ""
    explainer: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    anchored_event: EventRef | None = None
    anchor_note: str = ""
    """Empty when anchored to an event; otherwise the statement that no comparable event exists."""


class ShockVector(BaseModel):
    scenario_id: str
    as_of: date
    status: RunStatus
    horizon_months: int = DEFAULT_HORIZON_MONTHS
    agent: str = "scenario_analyst"
    summary: str = ""
    not_a_probability: str = NOT_A_PROBABILITY
    channels: list[ChannelMove] = []
    gaps: list[Gap] = []
    policy_decisions: list[PolicyDecisionRecord] = []
    evidence_ids: list[str] = []
    inputs_hash: str = ""
    vector_hash: str = ""
    model: str = ""

    def by_channel(self) -> dict[str, ChannelMove]:
        return {c.channel: c for c in self.channels}


# ---- layer B: the portfolio impact --------------------------------------------------------------
class CasePoint(BaseModel):
    move_pct: float
    delta_usd: float


class PositionChannel(BaseModel):
    """What one channel contributes to a position's move, in percent of the position, per case."""

    channel: str
    best_pct: float
    likely_pct: float
    worst_pct: float
    why: str = ""
    agent_assigned: bool = False


class PositionImpact(BaseModel):
    portfolio_id: str
    instrument_id: str
    instrument: str
    asset_class: str
    value_usd: float
    weight_pct: float
    """Share of the portfolio's USD value."""
    mapping: Mapping
    reason: str = ""
    moves: dict[Case, CasePoint]
    channels: list[PositionChannel] = []


class BandCrossing(BaseModel):
    asset_class: str
    portfolio: str
    before_pct: float
    after_pct: float
    band_min_pct: float
    band_max_pct: float
    crosses: Literal["out", "in"]


class CollateralEffect(BaseModel):
    facility: str
    portfolio: str = ""
    ltv_before_pct: float
    ltv_after_pct: float | None
    trigger_pct: float
    breaches: bool
    shortfall_usd: float | None = None


class Totals(BaseModel):
    before_usd: float
    after_usd: float
    delta_usd: float
    delta_pct: float


class CaseImpact(Totals):
    bands: list[BandCrossing] = []
    collateral: list[CollateralEffect] = []


class AgentMapping(BaseModel):
    """A mapping an agent proposed for a holding code could not map."""

    instrument_id: str
    channels: list[str]
    reason: str
    accepted: bool = True


class PortfolioImpact(BaseModel):
    scenario_id: str
    portfolio_id: str
    client_id: str
    as_of: date
    status: RunStatus
    horizon_months: int = DEFAULT_HORIZON_MONTHS
    agent: str = "scenario_impact"
    before_usd: float = 0.0
    cases: dict[Case, CaseImpact] = {}
    reached_pct: float = 0.0
    untouched_count: int = 0
    position_count: int = 0
    positions: list[PositionImpact] = []
    agent_mappings: list[AgentMapping] = []
    summary: str = ""
    explainers: dict[str, str] = {}
    gaps: list[Gap] = []
    policy_decisions: list[PolicyDecisionRecord] = []
    evidence_ids: list[str] = []
    inputs_hash: str = ""
    vector_hash: str = ""
    model: str = ""


# ---- roll-ups -----------------------------------------------------------------------------------
class Coverage(BaseModel):
    computed: int
    total: int
    missing: list[str] = []


class PortfolioLine(BaseModel):
    portfolio_id: str
    name: str = ""
    before_usd: float
    cases: dict[Case, Totals]


class ClientRollup(BaseModel):
    scenario_id: str
    client_id: str
    as_of: date
    status: RunStatus
    horizon_months: int = DEFAULT_HORIZON_MONTHS
    before_usd: float = 0.0
    cases: dict[Case, CaseImpact] = {}
    reached_pct: float = 0.0
    untouched_count: int = 0
    positions: list[PositionImpact] = []
    portfolios: list[PortfolioLine] = []
    coverage: Coverage = Coverage(computed=0, total=0)
    summary: str = ""
    explainers: dict[str, str] = {}
    gaps: list[Gap] = []
    inputs_hash: str = ""
    model: str = ""


class ClientLine(BaseModel):
    client_id: str
    before_usd: float
    cases: dict[Case, Totals]


class Crossing(BaseModel):
    client_id: str
    portfolio_id: str
    case: Case
    kind: Literal["band", "ltv"]
    label: str
    """The asset class or the facility."""
    detail: str


class RMRollup(BaseModel):
    scenario_id: str
    as_of: date
    rm_id: str | None = None
    status: RunStatus
    horizon_months: int = DEFAULT_HORIZON_MONTHS
    before_usd: float = 0.0
    cases: dict[Case, Totals] = {}
    most_hit: list[ClientLine] = []
    """Ranked by worst-case USD loss, largest loss first."""
    beneficiaries: list[ClientLine] = []
    """Clients with a positive likely change, largest first."""
    crossings: list[Crossing] = []
    coverage: Coverage = Coverage(computed=0, total=0)
    summary: str = ""
    gaps: list[Gap] = []
    inputs_hash: str = ""
    model: str = ""
