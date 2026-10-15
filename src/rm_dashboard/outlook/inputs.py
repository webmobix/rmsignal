"""What an outlook rests on, computed by code from the repository, and what needs a view."""

from datetime import date

from rm_dashboard.analytics.risk import risk_measure
from rm_dashboard.tools.domain_tools import RISK_STATISTICS, with_event_ids

from .contracts import CATEGORY_SEGMENT, SEGMENTS, EventRef, InstrumentInputs, MarketContext, MarketOutlook, OutlookInputs
from .digest import market_digest
from .relevance import relevant_events
from .store import OutlookStore

SEVERE = ("High", "Severe")


def compute_inputs(repo, as_of: date) -> tuple[OutlookInputs, str | None]:
    """(fingerprint of the data available at ``as_of``, reason when there is no market data)."""
    m = repo.market_context(as_of=as_of)
    ev = repo.events(as_of=as_of)
    dates = ev.frame["event_date"].to_list() if ev.frame.height else []
    inputs = OutlookInputs(market_snapshot_date=m.effective_snapshot_date if m.status == "ok" else None,
                           latest_event_date=max(dates) if dates else None, event_count=len(dates))
    return inputs, (None if m.status == "ok" else m.reason or "no market data at as_of")


def required_segments(repo, as_of: date) -> list[str]:
    """``overall`` plus a segment for every market category present at ``as_of``."""
    m = repo.market_context(as_of=as_of)
    cats = set(m.frame["category"].to_list()) if m.status == "ok" and m.frame.height else set()
    present = {CATEGORY_SEGMENT[c] for c in cats if c in CATEGORY_SEGMENT}
    return [s for s in SEGMENTS if s == "overall" or s in present]


def all_events(repo, as_of: date) -> list[dict]:
    """Every event dated on or before ``as_of`` with its stable id."""
    ev = repo.events(as_of=as_of)
    return with_event_ids(ev.frame.to_dicts() if ev.frame.height else [])


def severe_events_in_window(events: list[dict], since: date | None, as_of: date) -> list[EventRef]:
    return [EventRef(event_id=e["event_id"], event_date=e["event_date"], severity=e["severity"], description=e["description"])
            for e in events if e["severity"] in SEVERE and e["event_date"] <= as_of and (since is None or e["event_date"] > since)]


# ---- instruments --------------------------------------------------------------------------------
CLASS_SEGMENTS = {"Equity": ["equity"], "Fixed Income": ["rates"], "Commodities": ["commodities"], "Cash and Equivalents": ["rates"],
                  "Structured Products": ["equity"], "Alternatives": []}
"""Asset class -> market segments that bear on it (besides ``overall``; ``fx`` is added for a non-USD instrument)."""


def held_instruments(repo, as_of: date) -> list[str]:
    """Instruments held in any portfolio at the snapshot effective at ``as_of``."""
    h = repo.holdings(as_of=as_of)
    return sorted({i for i in h.frame["instrument_id"].to_list() if i}) if h.status == "ok" and h.frame.height else []


def instrument_row(repo, as_of: date, instrument_id: str) -> dict | None:
    r = repo.instruments(as_of=as_of, instrument_ids=[instrument_id])
    return r.frame.to_dicts()[0] if r.frame.height else None


def instrument_prices(repo, as_of: date, instrument_id: str) -> list[tuple[date, float]]:
    pr = repo.instrument_prices(as_of=as_of, instrument_id=instrument_id)
    return sorted((r["snapshot_date"], r["price"]) for r in pr.frame.to_dicts()) if pr.frame.height else []


def unavailable_statistics(prices: list[float]) -> list[str]:
    return [n for n in RISK_STATISTICS if risk_measure(n, prices).status != "ok"]


def instrument_inputs(repo, store: OutlookStore, instrument_id: str, as_of: date) -> tuple[InstrumentInputs, dict | None, str | None]:
    """(fingerprint of what an instrument outlook would rest on at ``as_of``, the instrument row, reason when it cannot be made)."""
    row = instrument_row(repo, as_of, instrument_id)
    prices = instrument_prices(repo, as_of, instrument_id)
    market = store.latest_market(as_of)
    events = relevant_events(row, all_events(repo, as_of)) if row else []
    inputs = InstrumentInputs(price_snapshot_date=prices[-1][0] if prices else None, relevant_event_ids=[e["event_id"] for e in events],
                              market_outlook_as_of=market.as_of if market else None,
                              market_outlook_digest=market_digest(market) if market else None)
    why = None if row and prices else (f"instrument {instrument_id} not found" if not row else f"instrument {instrument_id} has no price at {as_of}")
    return inputs, row, why


def market_context_for(instrument: dict, market: MarketOutlook | None) -> list[MarketContext]:
    """The segment views of the market outlook that bear on the instrument, exactly as the outlook states them."""
    if market is None:
        return []
    wanted = {"overall", *CLASS_SEGMENTS.get(instrument["asset_class"], []), *(["fx"] if instrument.get("currency") not in (None, "USD") else [])}
    return [MarketContext(segment=v.segment, direction=v.direction, horizon=v.horizon, confidence=v.confidence)
            for v in market.views if v.segment in wanted]
