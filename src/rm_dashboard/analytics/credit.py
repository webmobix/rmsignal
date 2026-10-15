"""Loan-to-value, headroom, cure amount and the pledged-collateral funding test."""

from rm_dashboard.domain import QualityFlag

from .base import Calc, insufficient, register

METHOD_LTV = register(
    "credit_ltv",
    "LTV% = drawn / lending_value x 100 where lending value is market value after advance-rate "
    "haircuts. Headroom to trigger: ltv_gap_pp = trigger - LTV and lending_value_buffer = "
    "lending_value - drawn / (trigger/100). Cure by selling collateral at the average advance "
    "rate a = lending_value / collateral_value with proceeds repaying the loan: sale = "
    "(drawn - T x lending_value) / (1 - T x a), T = trigger/100, when LTV exceeds the trigger. "
    "The recomputed LTV is compared with the source figure.",
)
METHOD_FUNDING = register(
    "collateral_funding",
    "Cash need is met first from assets outside the pledged portfolio. Any remainder must be "
    "raised by selling collateral, which releases lending value at the average advance rate "
    "and forces repayment so LTV stays within the trigger. Required sale x satisfies "
    "x >= shortfall and x >= (drawn + shortfall - T x lending_value) / (1 - T x a); repayment "
    "= x - shortfall. All values in the facility currency.",
)

LTV_SOURCE_TOLERANCE_PP = 0.01


def ltv(*, drawn: float, lending_value: float, collateral_value: float, trigger_pct: float,
        source_ltv_pct: float | None = None) -> Calc:
    if lending_value <= 0:
        return insufficient("credit_ltv", "lending value is not positive", METHOD_LTV)
    t, a = trigger_pct / 100, lending_value / collateral_value if collateral_value else 0.0
    value = drawn / lending_value * 100
    breached = value > trigger_pct
    cure = 0.0
    if breached and (1 - t * a) > 0:
        cure = (drawn - t * lending_value) / (1 - t * a)
    flags = []
    if source_ltv_pct is not None and abs(value - source_ltv_pct) > LTV_SOURCE_TOLERANCE_PP:
        flags.append(QualityFlag(code="ltv_source_difference",
                                 message=f"recomputed LTV {value:.2f}% differs from source {source_ltv_pct:.2f}%"))
    return Calc("credit_ltv", {
        "ltv_pct": value, "trigger_pct": trigger_pct, "ltv_gap_pp": trigger_pct - value,
        "lending_value_buffer": lending_value - drawn / t if t else None,
        "breached": breached, "cure_sale_required": cure, "average_advance_rate": a,
        "drawn": drawn, "lending_value": lending_value, "collateral_value": collateral_value,
        "source_ltv_pct": source_ltv_pct,
    }, METHOD_LTV, flags=flags)


def collateral_funding(*, need: float, free_assets: float, drawn: float, lending_value: float,
                       collateral_value: float, trigger_pct: float, daily_collateral_value: float) -> Calc:
    t = trigger_pct / 100
    a = lending_value / collateral_value if collateral_value else 0.0
    shortfall = max(0.0, need - free_assets)
    if shortfall == 0:
        return Calc("collateral_funding", {"need": need, "shortfall": 0.0, "sale_required": 0.0,
                                           "repayment_required": 0.0, "fundable": True, "touches_collateral": False},
                    METHOD_FUNDING)
    denom = 1 - t * a
    x = max(shortfall, (drawn + shortfall - t * lending_value) / denom) if denom > 0 else float("inf")
    fundable = x <= daily_collateral_value
    post_lv = lending_value - a * x
    post_drawn = drawn - (x - shortfall)
    return Calc("collateral_funding", {
        "need": need, "free_assets": free_assets, "shortfall": shortfall, "sale_required": x,
        "repayment_required": x - shortfall, "fundable": fundable, "touches_collateral": True,
        "daily_collateral_value": daily_collateral_value,
        "ltv_after_pct": (post_drawn / post_lv * 100) if post_lv > 0 else None,
        "ltv_before_pct": drawn / lending_value * 100 if lending_value else None, "trigger_pct": trigger_pct,
    }, METHOD_FUNDING)
