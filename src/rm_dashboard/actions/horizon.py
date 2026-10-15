"""Due dates and time horizons, derived in code from the content an action links to, never from the model."""

import re
from collections.abc import Iterable
from datetime import date

from rm_dashboard.domain import ToolResult

from .contracts import Horizon

ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
IMMEDIATE_DAYS = 7


def _iso(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def structured_dates(results: Iterable[ToolResult]) -> list[date]:
    """Dates that mean "due" in evidence: KYC review, cash-need start."""
    out: list[date] = []
    for r in results:
        d = r.data
        tool = r.computation.tool
        if tool == "clients.get" and isinstance(d, dict):
            out.append(_iso(((d.get("client") or {}).get("kyc_review_due"))))
        elif tool == "analytics.liquidity" and isinstance(d, dict):
            out += [_iso(i.get("due_from")) for i in d.get("items") or []]
        elif tool == "cash_needs.list" and isinstance(d, list):
            out += [_iso(i.get("due_from")) for i in d]
    return [x for x in out if x]


def text_dates(texts: Iterable[str], as_of: date) -> list[date]:
    """Dates written in linked findings. Only future ones count: past dates in prose are history, not deadlines."""
    found = (_iso(m) for t in texts for m in ISO_DATE.findall(t))
    return [d for d in found if d and d >= as_of]


def due_date(results: Iterable[ToolResult], texts: Iterable[str], as_of: date) -> date | None:
    """An overdue structured date wins; otherwise the earliest date on or after ``as_of``."""
    structured = structured_dates(results)
    overdue = [d for d in structured if d < as_of]
    if overdue:
        return min(overdue)
    upcoming = [d for d in [*structured, *text_dates(texts, as_of)] if d >= as_of]
    return min(upcoming) if upcoming else None


def horizon_for(due: date | None, as_of: date) -> Horizon:
    if due is None:
        return "none"
    days = (due - as_of).days
    if days <= IMMEDIATE_DAYS:
        return "immediate"
    if days <= 30:
        return "within_30_days"
    if days <= 90:
        return "within_90_days"
    return "later"
