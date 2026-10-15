"""Where outlooks live: ``<reports>/<as_of>/outlook/market.json`` with its evidence beside it. Other dates are never touched."""

import json
from datetime import date
from pathlib import Path

from rm_dashboard.domain import ToolResult

from .contracts import InstrumentOutlook, MarketOutlook

SUBDIR = "outlook"


class OutlookStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    def outlook_dir(self, as_of: date) -> Path:
        return self.base_dir / as_of.isoformat() / SUBDIR

    def market_path(self, as_of: date) -> Path:
        return self.outlook_dir(as_of) / "market.json"

    def market_evidence_path(self, as_of: date) -> Path:
        return self.outlook_dir(as_of) / "evidence" / "market.json"

    def load_market(self, as_of: date) -> MarketOutlook | None:
        p = self.market_path(as_of)
        return MarketOutlook.model_validate_json(p.read_text()) if p.is_file() else None

    def load_market_evidence(self, as_of: date) -> list[ToolResult]:
        p = self.market_evidence_path(as_of)
        return [ToolResult.model_validate(x) for x in json.loads(p.read_text())] if p.is_file() else []

    def dates(self) -> list[date]:
        """As-of dates that have a market outlook, oldest first."""
        out = []
        if self.base_dir.is_dir():
            for d in self.base_dir.iterdir():
                try:
                    day = date.fromisoformat(d.name)
                except ValueError:
                    continue
                if (d / SUBDIR / "market.json").is_file():
                    out.append(day)
        return sorted(out)

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
    def instrument_path(self, as_of: date, instrument_id: str) -> Path:
        return self.outlook_dir(as_of) / "instruments" / f"{instrument_id}.json"

    def instrument_evidence_path(self, as_of: date, instrument_id: str) -> Path:
        return self.outlook_dir(as_of) / "evidence" / "instruments" / f"{instrument_id}.json"

    def load_instrument(self, as_of: date, instrument_id: str) -> InstrumentOutlook | None:
        p = self.instrument_path(as_of, instrument_id)
        return InstrumentOutlook.model_validate_json(p.read_text()) if p.is_file() else None

    def load_instrument_evidence(self, as_of: date, instrument_id: str) -> list[ToolResult]:
        p = self.instrument_evidence_path(as_of, instrument_id)
        return [ToolResult.model_validate(x) for x in json.loads(p.read_text())] if p.is_file() else []

    def instrument_ids(self, as_of: date) -> list[str]:
        d = self.outlook_dir(as_of) / "instruments"
        return sorted(p.stem for p in d.glob("*.json")) if d.is_dir() else []

    def instrument_dates(self, instrument_id: str) -> list[date]:
        out = []
        if self.base_dir.is_dir():
            for d in self.base_dir.iterdir():
                try:
                    day = date.fromisoformat(d.name)
                except ValueError:
                    continue
                if self.instrument_path(day, instrument_id).is_file():
                    out.append(day)
        return sorted(out)

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

    def save_instrument(self, outlook: InstrumentOutlook, evidence: list[ToolResult]) -> None:
        self.instrument_evidence_path(outlook.as_of, outlook.subject).parent.mkdir(parents=True, exist_ok=True)
        self.instrument_path(outlook.as_of, outlook.subject).parent.mkdir(parents=True, exist_ok=True)
        self.instrument_path(outlook.as_of, outlook.subject).write_text(outlook.model_dump_json(indent=2))
        self.instrument_evidence_path(outlook.as_of, outlook.subject).write_text(
            json.dumps([e.model_dump(mode="json") for e in evidence], default=str))

    def save_market(self, outlook: MarketOutlook, evidence: list[ToolResult]) -> None:
        self.market_evidence_path(outlook.as_of).parent.mkdir(parents=True, exist_ok=True)
        self.market_path(outlook.as_of).write_text(outlook.model_dump_json(indent=2))
        self.market_evidence_path(outlook.as_of).write_text(json.dumps([e.model_dump(mode="json") for e in evidence], default=str))
