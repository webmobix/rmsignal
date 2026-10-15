"""Response models shared by the read endpoints."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from rm_dashboard.domain import Gap

Status = Literal["complete", "partial", "insufficient_data"]


class Placeholder(BaseModel):
    """Marks content that is not computed by the analysis layer."""

    status: Literal["placeholder"] = "placeholder"
    note: str = "Illustrative, not computed."


class AsOfResponse(BaseModel):
    as_of_dates: list[date]
    latest: date | None


class RmProfile(BaseModel):
    as_of: date
    rm_id: str
    rm_name: str
    rm_desk: str
    booking_centres: list[str]
    client_count: int
    total_aum_usd: float


class Slice(BaseModel):
    key: str
    value_usd: float
    weight_pct: float


class HasGaps(BaseModel):
    gaps: list[Gap] = Field(default_factory=list)


def gap(description: str, subject: str | None = None, kind: str = "no_data") -> Gap:
    return Gap(kind=kind, description=description, subject=subject)  # type: ignore[arg-type]


class EventOut(BaseModel):
    event_date: date
    event_type: str
    region: str
    description: str
    severity: str
    primary_transmission: str
