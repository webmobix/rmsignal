"""A number for how soon an action asks for the RM, finer than the importance tier.

The persisted overview ranks by importance, horizon and due date; the data holds only ``high`` and ``medium``.
``urgency`` exists to spread a chart axis. It never reorders the overview.

    urgency = importance base + horizon bonus + within-tier term (0..4, from days to the due date)

The tiers are 24 apart and the bonus and term add at most 22, so a higher tier always scores higher. The range is 4..98.
"""

from datetime import date

IMPORTANCE_BASE = {"critical": 76.0, "high": 52.0, "medium": 28.0, "low": 4.0}
HORIZON_BONUS = {"immediate": 18.0, "within_30_days": 13.0, "within_90_days": 8.0, "later": 0.0, "none": 0.0}
DUE_TERM_MAX = 4.0
DUE_TERM_DAYS = 365


def urgency(importance: str, horizon: str, due_date: date | None, as_of: date) -> float:
    """Overdue and same-day due dates take the full term; the term fades linearly to zero over a year."""
    u = IMPORTANCE_BASE[importance] + HORIZON_BONUS[horizon]
    if due_date is not None:
        days = (due_date - as_of).days
        u += DUE_TERM_MAX * max(0.0, 1.0 - max(days, 0) / DUE_TERM_DAYS)
    return round(u, 1)
