from datetime import date

import pytest
from pydantic import ValidationError

from rm_dashboard.actions import Action, ClientActions, SourceRef
from rm_dashboard.actions.horizon import due_date, horizon_for
from rm_dashboard.actions.rubric import apply_floor, floor_for
from rm_dashboard.domain import Computation, ToolResult

AS_OF = date(2026, 8, 26)


def ev(tool, data):
    return ToolResult(data=data, as_of=AS_OF, computation=Computation(tool=tool, version="1"))


def client_ev(days, due, overdue=False):
    return ev("clients.get", {"client": {"kyc_review_due": due, "days_to_kyc_due": days, "kyc_overdue": overdue}})


def action(**kw):
    base = dict(title="t", what="w", why="y", category="compliance_kyc", importance="high",
                sources=[SourceRef(kind="finding", ref="CL-0001#f1", evidence_ids=["ev_1"])])
    return Action(**{**base, **kw})


# ---- 1.1 contracts ------------------------------------------------------------------------------
def test_enums_are_closed_and_sources_required():
    with pytest.raises(ValidationError):
        action(category="other")
    with pytest.raises(ValidationError):
        action(importance="urgent")
    with pytest.raises(ValidationError):
        action(horizon="soon")
    with pytest.raises(ValidationError):
        action(sources=[])


def test_client_actions_round_trip():
    c = ClientActions(client_id="CL-0001", as_of=AS_OF, status="partial", actions=[action(due_date=date(2026, 11, 30), horizon="later")])
    assert ClientActions.model_validate_json(c.model_dump_json()) == c


# ---- 1.3 horizon -----------------------------------------------------------------------------------
@pytest.mark.parametrize("days,expected", [(-5, "immediate"), (0, "immediate"), (7, "immediate"), (8, "within_30_days"),
                                           (30, "within_30_days"), (31, "within_90_days"), (90, "within_90_days"),
                                           (96, "later")])
def test_horizon_buckets(days, expected):
    from datetime import timedelta

    assert horizon_for(AS_OF + timedelta(days=days), AS_OF) == expected
    assert horizon_for(None, AS_OF) == "none"


def test_kyc_due_in_96_days_is_later_with_date():
    d = due_date([client_ev(96, "2026-11-30")], [], AS_OF)
    assert d == date(2026, 11, 30) and horizon_for(d, AS_OF) == "later"


def test_overdue_structured_date_wins_over_upcoming():
    d = due_date([client_ev(-12, "2026-08-14", True), ev("cash_needs.list", [{"due_from": "2026-09-01"}])], [], AS_OF)
    assert d == date(2026, 8, 14) and horizon_for(d, AS_OF) == "immediate"


def test_earliest_upcoming_date_across_structured_and_text():
    liq = ev("analytics.liquidity", {"items": [{"due_from": "2027-03-01"}]})
    assert due_date([liq], ["Meeting planned 2026-10-01."], AS_OF) == date(2026, 10, 1)


def test_past_dates_in_prose_are_history_not_deadlines():
    assert due_date([], ["It was breached at the 2025-12-31 snapshot."], AS_OF) is None


def test_no_dates_gives_none():
    assert due_date([ev("analytics.weights", {"x": 1})], ["No dates here."], AS_OF) is None


# ---- 2.1 rubric ------------------------------------------------------------------------------------
def test_same_condition_same_floor_in_any_client():
    a, b = client_ev(-3, "2026-08-23", True), client_ev(-40, "2026-07-17", True)
    assert floor_for("compliance_kyc", [a]) == floor_for("compliance_kyc", [b]) == "critical"


@pytest.mark.parametrize("days,floor", [(10, "high"), (96, None), (60, "medium")])
def test_kyc_floors(days, floor):
    assert floor_for("compliance_kyc", [client_ev(days, "2026-12-01")]) == floor


def test_floor_only_applies_to_its_own_category():
    assert floor_for("concentration_risk", [client_ev(-3, "2026-08-23", True)]) is None


def test_credit_liquidity_mandate_concentration_floors():
    assert floor_for("credit_collateral", [ev("analytics.credit_ltv", {"breached": True, "ltv_gap_pp": -3})]) == "critical"
    assert floor_for("credit_collateral", [ev("analytics.credit_ltv", {"breached": False, "ltv_gap_pp": 3.0})]) == "high"
    assert floor_for("credit_collateral", [ev("analytics.credit_ltv", {"breached": False, "ltv_gap_pp": 10.85})]) is None
    assert floor_for("liquidity_cash_needs", [ev("analytics.liquidity", {"shortfall_usd": 5.0})]) == "high"
    assert floor_for("liquidity_cash_needs", [ev("analytics.liquidity", {"shortfall_usd": 0.0})]) is None
    assert floor_for("mandate_drift", [ev("analytics.mandate_drift", {"breaches": [{"x": 1}]})]) == "high"
    assert floor_for("mandate_drift", [ev("analytics.mandate_drift", {"breaches": [], "single_position_breaches": []})]) is None
    assert floor_for("concentration_risk", [ev("analytics.concentration", {"single_names": [{"share_pct": 42.6}]})]) == "high"
    assert floor_for("concentration_risk", [ev("analytics.concentration", {"single_names": [{"share_pct": 12.0}]})]) is None


def test_contradicted_note_floor_is_medium_and_floor_only_raises():
    assert floor_for("client_contact", [], contradicted_note=True) == "medium"
    assert apply_floor("low", "high") == "high"
    assert apply_floor("critical", "high") == "critical"
    assert apply_floor("low", None) == "low"
