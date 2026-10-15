"""The market outlook: dated, evidence-bound views per segment and what changed since the previous outlook."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rm_dashboard.domain import Gap, PolicyDecisionRecord

Segment = Literal["overall", "equity", "rates", "fx", "commodities", "volatility"]
Direction = Literal["positive", "neutral", "negative"]
Horizon = Literal["1m", "3m", "6m"]
Confidence = Literal["high", "medium", "low"]
ChangeKind = Literal["new", "unchanged", "upgraded", "downgraded"]
OutlookStatus = Literal["complete", "partial", "insufficient_data"]

SEGMENTS: tuple[str, ...] = ("overall", "equity", "rates", "fx", "commodities", "volatility")
DIRECTIONS: tuple[str, ...] = ("negative", "neutral", "positive")
HORIZONS: tuple[str, ...] = ("1m", "3m", "6m")
CONFIDENCES: tuple[str, ...] = ("low", "medium", "high")
DEFAULT_HORIZON = "3m"
CATEGORY_SEGMENT = {"Equity index": "equity", "Rates": "rates", "FX": "fx", "Commodity": "commodities", "Volatility": "volatility"}
"""Market series category -> outlook segment. A segment exists in an outlook when the data has a series of that category."""
SUBJECT = "MKT"


class Reason(BaseModel):
    """A driver or risk: a claim, the evidence it rests on and the events it names (by event id)."""

    model_config = ConfigDict(frozen=True)

    claim: str
    evidence_ids: list[str] = Field(min_length=1)
    event_refs: list[str] = []


class Change(BaseModel):
    """What changed against the previous outlook. ``kind`` and ``previous_direction`` are derived by code."""

    model_config = ConfigDict(frozen=True)

    kind: ChangeKind
    previous_direction: Direction | None = None
    why: str = ""
    new_evidence_ids: list[str] = []
    new_event_refs: list[str] = []


class ViewBody(BaseModel):
    """What a view says, whatever it is about."""

    model_config = ConfigDict(frozen=True)

    direction: Direction
    horizon: Horizon = DEFAULT_HORIZON
    confidence: Confidence
    rationale: str = ""
    drivers: list[Reason] = Field(min_length=1)
    risks: list[Reason] = []
    would_change_if: str = ""
    change: Change


class View(ViewBody):
    """A view of one market segment."""

    segment: Segment


class InstrumentView(ViewBody):
    """The view of one instrument."""


class OutlookInputs(BaseModel):
    """The data an outlook rests on; equal inputs mean nothing new has arrived."""

    model_config = ConfigDict(frozen=True)

    market_snapshot_date: date | None = None
    latest_event_date: date | None = None
    event_count: int = 0


class EventRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    event_date: date
    severity: str
    description: str


class MarketOutlook(BaseModel):
    subject: str = SUBJECT
    as_of: date
    status: OutlookStatus
    agent: str = "outlook_analyst"
    summary: str = ""
    views: list[View] = []
    inputs: OutlookInputs = OutlookInputs()
    previous_as_of: date | None = None
    is_first: bool = False
    carried_forward_from: date | None = None
    changes_summary: str = ""
    unaddressed_events: list[EventRef] = []
    gaps: list[Gap] = []
    policy_decisions: list[PolicyDecisionRecord] = []
    evidence_ids: list[str] = []


class InstrumentRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    instrument_name: str
    asset_class: str
    sub_asset_class: str
    sector: str | None = None
    region: str | None = None
    liquidity_tier: str | None = None


class PricePoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_date: date
    price: float


class MarketContext(BaseModel):
    """A segment view of the market outlook, copied by code and shown as it stands there."""

    model_config = ConfigDict(frozen=True)

    segment: Segment
    direction: Direction
    horizon: Horizon
    confidence: Confidence


class InstrumentInputs(BaseModel):
    """The data an instrument outlook rests on; equal inputs mean nothing new has arrived."""

    model_config = ConfigDict(frozen=True)

    price_snapshot_date: date | None = None
    relevant_event_ids: list[str] = []
    market_outlook_as_of: date | None = None
    market_outlook_digest: str | None = None

    def same_as(self, other: "InstrumentInputs") -> bool:
        """Nothing new: same latest price, same relevant events, same market view. The date of an unchanged market outlook is not news."""
        return (self.price_snapshot_date, self.relevant_event_ids, self.market_outlook_digest) == \
               (other.price_snapshot_date, other.relevant_event_ids, other.market_outlook_digest)


class InstrumentOutlook(BaseModel):
    subject: str
    as_of: date
    status: OutlookStatus
    agent: str = "outlook_analyst"
    summary: str = ""
    instrument: InstrumentRef | None = None
    price_path: list[PricePoint] = []
    unavailable_statistics: list[str] = []
    market_outlook_as_of: date | None = None
    market_context: list[MarketContext] = []
    relevant_events: list[EventRef] = []
    view: InstrumentView | None = None
    inputs: InstrumentInputs = InstrumentInputs()
    previous_as_of: date | None = None
    is_first: bool = False
    carried_forward_from: date | None = None
    changes_summary: str = ""
    unaddressed_events: list[EventRef] = []
    gaps: list[Gap] = []
    policy_decisions: list[PolicyDecisionRecord] = []
    evidence_ids: list[str] = []
