"""Where outlooks live: one market outlook and one outlook per instrument for each date, with their evidence, in the
artifact store. Other dates are never touched."""

from datetime import date
from pathlib import Path

from rm_dashboard.domain import ToolResult
from rm_dashboard.store import ArtifactStore, Kind, as_store, read_model
from rm_dashboard.store import evidence as ev

from .contracts import InstrumentOutlook, MarketOutlook

MARKET_KEY = "market"


class OutlookStore:
    def __init__(self, store: ArtifactStore | str | Path):
        self.store = as_store(store)

    def load_market(self, as_of: date) -> MarketOutlook | None:
        return read_model(self.store, as_of, Kind.OUTLOOK_MARKET, MARKET_KEY, MarketOutlook)

    def load_market_evidence(self, as_of: date) -> list[ToolResult]:
        return ev.get_evidence(self.store, as_of, ev.OUTLOOK_MARKET, MARKET_KEY) or []

    def dates(self) -> list[date]:
        """As-of dates that have a market outlook, oldest first."""
        return [d for d in self.store.dates() if self.store.keys(d, Kind.OUTLOOK_MARKET, MARKET_KEY)]

    def previous_market(self, before: date) -> MarketOutlook | None:
        """The latest market outlook with views whose as_of is strictly earlier than ``before`` (never a later one)."""
        return self._latest_with_views([d for d in self.dates() if d < before])

    def latest_market(self, not_after: date) -> MarketOutlook | None:
        """The latest market outlook with views whose as_of is on or before ``not_after``."""
        return self._latest_with_views([d for d in self.dates() if d <= not_after])

    def _latest_with_views(self, dates: list[date]) -> MarketOutlook | None:
        for d in reversed(dates):
            o = self.load_market(d)
            if o is not None and o.views:
                return o
        return None

    # ---- instruments -------------------------------------------------------------------
    def load_instrument(self, as_of: date, instrument_id: str) -> InstrumentOutlook | None:
        return read_model(self.store, as_of, Kind.OUTLOOK_INSTRUMENT, instrument_id, InstrumentOutlook)

    def load_instrument_evidence(self, as_of: date, instrument_id: str) -> list[ToolResult]:
        return ev.get_evidence(self.store, as_of, ev.OUTLOOK_INSTRUMENT, instrument_id) or []

    def instrument_ids(self, as_of: date) -> list[str]:
        return self.store.keys(as_of, Kind.OUTLOOK_INSTRUMENT)

    def instrument_dates(self, instrument_id: str) -> list[date]:
        return [d for d in self.store.dates() if self.store.get(d, Kind.OUTLOOK_INSTRUMENT, instrument_id) is not None]

    def previous_instrument(self, instrument_id: str, before: date) -> InstrumentOutlook | None:
        """The latest outlook of the instrument with a view whose as_of is strictly earlier than ``before``."""
        for d in reversed([d for d in self.instrument_dates(instrument_id) if d < before]):
            o = self.load_instrument(d, instrument_id)
            if o is not None and o.view is not None:
                return o
        return None

    def latest_instrument(self, instrument_id: str, not_after: date) -> InstrumentOutlook | None:
        """The latest outlook of the instrument with a view whose as_of is on or before ``not_after``."""
        for d in reversed([d for d in self.instrument_dates(instrument_id) if d <= not_after]):
            o = self.load_instrument(d, instrument_id)
            if o is not None and o.view is not None:
                return o
        return None

    # ---- writing: evidence first, the outlook last, so a reader never sees an outlook whose evidence is missing --------------
    def save_instrument(self, outlook: InstrumentOutlook, evidence: list[ToolResult]) -> None:
        ev.put_evidence(self.store, outlook.as_of, ev.OUTLOOK_INSTRUMENT, outlook.subject, evidence)
        self.store.put(outlook.as_of, Kind.OUTLOOK_INSTRUMENT, outlook.subject, outlook.model_dump_json(indent=2))

    def save_market(self, outlook: MarketOutlook, evidence: list[ToolResult]) -> None:
        ev.put_evidence(self.store, outlook.as_of, ev.OUTLOOK_MARKET, MARKET_KEY, evidence)
        self.store.put(outlook.as_of, Kind.OUTLOOK_MARKET, MARKET_KEY, outlook.model_dump_json(indent=2))
