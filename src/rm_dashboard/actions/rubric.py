"""Importance rubric: fixed conditions, read from evidence, set a floor so equal conditions rank equally in any client.

The model proposes an importance; the floor can only raise it. The same table is rendered into the prompt.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from rm_dashboard.domain import ToolResult

from .contracts import IMPORTANCE_ORDER, Category, Importance

KYC_SOON_DAYS = 30
KYC_UPCOMING_DAYS = 90
LTV_NEAR_TRIGGER_PP = 5.0
SINGLE_NAME_HIGH_PCT = 25.0


@dataclass(frozen=True)
class Condition:
    category: Category
    floor: Importance
    text: str


def _rank(i: Importance) -> int:
    return IMPORTANCE_ORDER.index(i)


MANDATE_STATUSES = ("no_note", "acknowledged", "client_directed", "contradicted")
MANDATE_FLOORS: dict[str, dict[str, Importance]] = {
    "band or position": {"no_note": "high", "acknowledged": "medium", "client_directed": "high", "contradicted": "critical"},
    "exclusion": {"no_note": "high", "acknowledged": "high", "client_directed": "high", "contradicted": "critical"},
}
MANDATE_TABLE = "\n".join([
    "| Breach | " + " | ".join(f"`{s}`" for s in MANDATE_STATUSES) + " |",
    "|---|" + "---|" * len(MANDATE_STATUSES),
    *(f"| {kind} | " + " | ".join(floors[s] for s in MANDATE_STATUSES) + " |" for kind, floors in MANDATE_FLOORS.items()),
])


def mandate_floor(breach_kind: str, status: str) -> Importance:
    return MANDATE_FLOORS["exclusion" if breach_kind == "exclusion" else "band or position"][status]


def conditions(results: Iterable[ToolResult]) -> list[Condition]:
    """Conditions met by the evidence an action links to."""
    out: list[Condition] = []
    for r in results:
        d, tool = r.data, r.computation.tool
        if not isinstance(d, (dict, list)):
            continue
        if tool == "clients.get" and isinstance(d, dict) and d.get("client"):
            c = d["client"]
            if c.get("kyc_overdue"):
                out.append(Condition("compliance_kyc", "critical", "KYC review overdue"))
            elif (c.get("days_to_kyc_due") is not None) and c["days_to_kyc_due"] <= KYC_SOON_DAYS:
                out.append(Condition("compliance_kyc", "high", f"KYC review due within {KYC_SOON_DAYS} days"))
            elif (c.get("days_to_kyc_due") is not None) and c["days_to_kyc_due"] <= KYC_UPCOMING_DAYS:
                out.append(Condition("compliance_kyc", "medium", f"KYC review due within {KYC_UPCOMING_DAYS} days"))
        elif tool == "analytics.credit_ltv" and isinstance(d, dict):
            if d.get("breached"):
                out.append(Condition("credit_collateral", "critical", "Lombard LTV above its trigger"))
            elif d.get("ltv_gap_pp") is not None and d["ltv_gap_pp"] < LTV_NEAR_TRIGGER_PP:
                out.append(Condition("credit_collateral", "high", f"Lombard LTV within {LTV_NEAR_TRIGGER_PP:g} points of its trigger"))
        elif tool == "analytics.liquidity" and isinstance(d, dict):
            if (d.get("shortfall_usd") or 0) > 0:
                out.append(Condition("liquidity_cash_needs", "high", "Daily-liquid assets fall short of needs within the horizon"))
        elif tool == "analytics.mandate_drift" and isinstance(d, dict):
            if d.get("breaches") or d.get("single_position_breaches"):
                out.append(Condition("mandate_drift", "high", "Mandate band or single-position limit breached"))
        elif tool == "analytics.exclusion_breaches" and isinstance(d, dict):
            if d.get("breaches"):
                out.append(Condition("mandate_drift", "high", "A held instrument violates the mandate's binding exclusions"))
        elif tool == "analytics.concentration" and isinstance(d, dict):
            if any(s.get("share_pct", 0) >= SINGLE_NAME_HIGH_PCT for s in d.get("single_names") or []):
                out.append(Condition("concentration_risk", "high", f"A single name is at least {SINGLE_NAME_HIGH_PCT:g}% of the client's assets"))
    return out


def floor_for(category: Category, results: Iterable[ToolResult], *, contradicted_note: bool = False,
              mandate: Iterable[tuple[str, str]] = ()) -> Importance | None:
    """Highest floor among the met conditions of this category (and `medium` for any contradicted RM note).

    ``mandate`` holds (breach kind, status) of the mandate-reconciliation results the action links. For
    ``mandate_drift`` they replace the flat evidence condition, so the status sets the floor; without them the
    flat condition applies, as before mandate reconciliation existed."""
    mandate = list(mandate)
    floors = [c.floor for c in conditions(results) if c.category == category and not (mandate and category == "mandate_drift")]
    if category == "mandate_drift":
        floors += [mandate_floor(k, s) for k, s in mandate]
    if contradicted_note:
        floors.append("medium")
    return min(floors, key=_rank) if floors else None


def apply_floor(proposed: Importance, floor: Importance | None) -> Importance:
    return floor if floor is not None and _rank(floor) < _rank(proposed) else proposed


RUBRIC_TEXT = f"""Importance is anchored to conditions (a floor you cannot go below; you may rate higher):
- compliance_kyc: KYC review overdue -> critical; due within {KYC_SOON_DAYS} days -> high; due within {KYC_UPCOMING_DAYS} days -> medium.
- credit_collateral: LTV above its trigger -> critical; within {LTV_NEAR_TRIGGER_PP:g} percentage points of the trigger -> high.
- liquidity_cash_needs: daily-liquid assets short of needs within the horizon -> high.
- mandate_drift: a mandate band or single-position limit is breached, or a held instrument violates the mandate's binding exclusions -> high, unless the action links a mandate-reconciliation result; then the floor follows its status:
{MANDATE_TABLE}
- concentration_risk: a single name is at least {SINGLE_NAME_HIGH_PCT:g}% of the client's assets -> high.
- Any action resting on a contradicted RM note -> at least medium.
Use critical only for breaches and overdue obligations. Otherwise rate by consequence: high (act this month), medium (plan it), low (watch)."""
