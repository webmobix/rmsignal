"""Liquidity coverage of planned cash needs and uncalled commitments."""

import re
from datetime import date, timedelta

import polars as pl

from rm_dashboard.domain import QualityFlag

from .base import Calc, register
from .fx import FxTable

METHOD_LIQUIDITY = register(
    "liquidity_coverage",
    "Liquid assets (market value in USD) are summed by liquidity tier. Needs and uncalled "
    "commitments whose due window overlaps (as_of, as_of + horizon_days] are converted to USD "
    "at the rate of the effective snapshot and summed. Aspirational needs are excluded and "
    "listed separately. A cash need that restates the commitments replaces them (no double "
    "count). Shortfall = max(0, needs - Daily-tier assets); coverage = Daily assets / needs. "
    "Each item keeps its stated certainty; amounts are not probability-weighted.",
)

EXCLUDED_CERTAINTY = ("Aspirational",)
_QUARTER = re.compile(r"(\d{4})\s*Q([1-4])")


def _quarter_start(y: int, q: int) -> date:
    return date(y, 3 * (q - 1) + 1, 1)


def _quarter_end(y: int, q: int) -> date:
    nxt = _quarter_start(y + (q == 4), 1 if q == 4 else q + 1)
    return nxt - timedelta(days=1)


def parse_call_window(text: str) -> tuple[date, date] | None:
    q = _QUARTER.findall(text or "")
    if not q:
        return None
    (y1, q1), (y2, q2) = q[0], q[-1]
    return _quarter_start(int(y1), int(q1)), _quarter_end(int(y2), int(q2))


def liquidity_coverage(positions: pl.DataFrame, needs: pl.DataFrame, commitments: pl.DataFrame,
                       fx: FxTable, *, as_of: date, horizon_days: int,
                       value_col: str = "market_value_usd") -> Calc:
    end = as_of + timedelta(days=horizon_days)
    tiers = {}
    if positions.height:
        tiers = dict(positions.group_by("liquidity_tier").agg(pl.col(value_col).sum()).iter_rows())
    daily = tiers.get("Daily", 0.0)
    flags: list[QualityFlag] = []
    items, excluded = [], []
    restates = False
    for n in needs.iter_rows(named=True):
        usd = fx.convert(n["amount"], n["currency"], "USD")
        item = {"id": n["need_id"], "description": n["description"], "currency": n["currency"],
                "amount": n["amount"], "usd": usd, "certainty": n["certainty"],
                "due_from": n["due_from"].isoformat(), "due_to": n["due_to"].isoformat(), "kind": "cash_need"}
        if n["certainty"] in EXCLUDED_CERTAINTY:
            excluded.append(item)
            continue
        if n["due_from"] <= end and n["due_to"] > as_of:
            items.append(item)
            restates = restates or "commitment" in n["description"].lower()
    for c in commitments.iter_rows(named=True):
        window = parse_call_window(c["expected_call_window"])
        if window is None:
            flags.append(QualityFlag(code="unparsed_call_window", subject=c["commitment_id"],
                                     message=f"cannot read call window {c['expected_call_window']!r}"))
            continue
        if not (window[0] <= end and window[1] > as_of):
            continue
        if restates:
            flags.append(QualityFlag(code="commitment_restated", subject=c["commitment_id"],
                                     message="a planned cash need already restates the client's commitments; not counted twice"))
            continue
        usd = fx.convert(c["uncalled"], c["currency"], "USD")
        items.append({"id": c["commitment_id"], "description": f"Uncalled: {c['fund_name']}", "currency": c["currency"],
                      "amount": c["uncalled"], "usd": usd, "certainty": "Contractual",
                      "due_from": window[0].isoformat(), "due_to": window[1].isoformat(), "kind": "commitment"})
    total = sum(i["usd"] for i in items)
    shortfall = max(0.0, total - daily)
    return Calc("liquidity_coverage", {
        "as_of": as_of.isoformat(), "horizon_end": end.isoformat(), "horizon_days": horizon_days,
        "assets_by_tier_usd": tiers, "daily_liquid_usd": daily, "needs_total_usd": total,
        "coverage_ratio": (daily / total) if total else None, "shortfall_usd": shortfall,
        "items": sorted(items, key=lambda i: (-i["usd"], i["id"])),
        "contributing": sorted(items, key=lambda i: (-i["usd"], i["id"])) if shortfall else [],
        "excluded_aspirational": excluded,
    }, METHOD_LIQUIDITY, flags=flags)
