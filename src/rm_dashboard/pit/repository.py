"""The point-in-time read contract. Analysis code reads wealth data only through this."""

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

import polars as pl

from rm_dashboard.domain import QualityFlag, Source
from rm_dashboard.domain.evidence import Status


class AsOfError(ValueError):
    """``as_of`` is missing or not a calendar date."""


@dataclass(frozen=True)
class Resolution:
    as_of: date
    effective_snapshot_date: date | None
    gap_days: int | None
    status: Status = "ok"
    reason: str | None = None


@dataclass
class PitResult:
    """Rows plus everything needed to build a ``ToolResult`` envelope."""

    frame: pl.DataFrame
    as_of: date
    dataset: str
    effective_snapshot_date: date | None = None
    gap_days: int | None = None
    status: Status = "ok"
    reason: str | None = None
    pit: str = "snapshot"  # snapshot | event | current_only
    current_only_attributes: list[str] = field(default_factory=list)
    flags: list[QualityFlag] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


class PitRepository(Protocol):
    """Every method requires a keyword-only ``as_of``; none has a default."""

    def snapshot_dates(self) -> list[date]: ...
    def resolve(self, *, as_of: date) -> Resolution: ...
    def clients(self, *, as_of: date, client_id: str | None = None) -> PitResult: ...
    def portfolios(self, *, as_of: date, client_id: str | None = None, portfolio_id: str | None = None) -> PitResult: ...
    def holdings(self, *, as_of: date, client_id: str | None = None, portfolio_id: str | None = None) -> PitResult: ...
    def instruments(self, *, as_of: date, instrument_ids: list[str] | None = None) -> PitResult: ...
    def instrument_prices(self, *, as_of: date, instrument_id: str | None = None) -> PitResult: ...
    def portfolio_aum(self, *, as_of: date, portfolio_id: str | None = None) -> PitResult: ...
    def facility_snapshots(self, *, as_of: date, client_id: str | None = None, facility_id: str | None = None) -> PitResult: ...
    def facility_terms(self, *, as_of: date, client_id: str | None = None, facility_id: str | None = None) -> PitResult: ...
    def mandates(self, *, as_of: date, mandate_code: str | None = None) -> PitResult: ...
    def market_context(self, *, as_of: date, series_id: str | None = None) -> PitResult: ...
    def transactions(self, *, as_of: date, client_id: str | None = None, portfolio_id: str | None = None) -> PitResult: ...
    def events(self, *, as_of: date) -> PitResult: ...
    def notes(self, *, as_of: date, client_id: str | None = None) -> PitResult: ...
    def cash_needs(self, *, as_of: date, client_id: str | None = None) -> PitResult: ...
    def commitments(self, *, as_of: date, client_id: str | None = None) -> PitResult: ...
