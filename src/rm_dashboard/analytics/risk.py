"""History-dependent risk measures. With too few observations they return no number."""

import math
import statistics

from .base import Calc, register

METHOD_RISK = register(
    "risk_measures",
    "Volatility, value-at-risk, drawdown and Sharpe need a return series; they return "
    "insufficient_history (no number) when fewer observations than the stated minimum are "
    "available. With enough data: volatility = sample stdev of simple returns; historical VaR "
    "= negative quantile of returns; drawdown = worst peak-to-trough decline of the price path; "
    "Sharpe = mean excess return / volatility (per-period, not annualised).",
)

MIN_POINTS = {"volatility": 30, "var": 250, "max_drawdown": 30, "sharpe": 30}


def risk_measure(name: str, prices: list[float], *, risk_free_per_period: float = 0.0,
                 confidence: float = 0.95, min_points: dict[str, int] | None = None) -> Calc:
    need = (min_points or MIN_POINTS)[name]
    if len(prices) < need:
        return Calc("risk_measures", {"measure": name, "points_available": len(prices), "points_required": need},
                    METHOD_RISK, "insufficient_history",
                    f"{name} needs {need} price points; {len(prices)} available")
    rets = [b / a - 1 for a, b in zip(prices, prices[1:])]
    if name == "volatility":
        value = statistics.stdev(rets)
    elif name == "var":
        k = max(0, math.ceil((1 - confidence) * len(rets)) - 1)
        value = -sorted(rets)[k]
    elif name == "max_drawdown":
        peak, worst = prices[0], 0.0
        for p in prices:
            peak = max(peak, p)
            worst = min(worst, p / peak - 1)
        value = worst
    else:
        sd = statistics.stdev(rets)
        value = (statistics.fmean(rets) - risk_free_per_period) / sd if sd else None
    return Calc("risk_measures", {"measure": name, "value": value, "points_available": len(prices)}, METHOD_RISK)
