"""Mandate band drift. Custody portfolios are not measured against a mandate."""

import polars as pl

from rm_dashboard.domain import QualityFlag

from .base import Calc, register

METHOD_MANDATE = register(
    "mandate_drift",
    "Asset-class weight = class value / portfolio total x 100 (portfolio base currency). "
    "Each weight is compared with the mandate min/target/max; gap_pp is the distance beyond "
    "the nearest breached band edge, drift_pp the distance from target. Positions flagged "
    "concentration_limit_applies are compared with max_single_position_pct. Custody "
    "portfolios are excluded from this comparison (they remain in client totals).",
)

CUSTODY_MODELS = ("Custody",)


def mandate_drift(positions: pl.DataFrame, bands: pl.DataFrame, *, service_model: str,
                  value_col: str = "market_value_base", instruments: pl.DataFrame | None = None) -> Calc:
    """``bands``: asset_class, min_pct, target_pct, max_pct, max_single_position_pct."""
    if service_model in CUSTODY_MODELS:
        return Calc("mandate_drift", {"applicable": False}, METHOD_MANDATE, "ok",
                    f"service model {service_model!r}: not measured against a mandate")
    total = float(positions[value_col].sum()) if positions.height else 0.0
    if total <= 0 or bands.is_empty():
        return Calc("mandate_drift", {"applicable": True}, METHOD_MANDATE, "insufficient_data",
                    "no positions or no mandate bands")
    by_class = dict(positions.group_by("asset_class").agg(pl.col(value_col).sum()).iter_rows())
    flags: list[QualityFlag] = []
    rows, breaches = [], []
    band_classes = set()
    for b in bands.iter_rows(named=True):
        band_classes.add(b["asset_class"])
        w = by_class.get(b["asset_class"], 0.0) / total * 100
        gap = (w - b["max_pct"]) if w > b["max_pct"] else (w - b["min_pct"]) if w < b["min_pct"] else 0.0
        row = {"asset_class": b["asset_class"], "weight_pct": w, "min_pct": b["min_pct"],
               "target_pct": b["target_pct"], "max_pct": b["max_pct"], "drift_pp": w - b["target_pct"],
               "gap_pp": gap, "breach": "above_max" if gap > 0 else "below_min" if gap < 0 else None}
        rows.append(row)
        if gap:
            breaches.append(row)
    for cls in sorted(set(by_class) - band_classes):
        flags.append(QualityFlag(code="no_mandate_band", subject=cls,
                                 message=f"asset class {cls!r} has no band in the mandate"))
    position_breaches = []
    limit = float(bands["max_single_position_pct"][0])
    inst_flag = {}
    if instruments is not None and instruments.height:
        inst_flag = dict(instruments.select("instrument_id", "concentration_limit_applies").iter_rows())
    for r in positions.iter_rows(named=True):
        w = r[value_col] / total * 100
        if inst_flag.get(r["instrument_id"]) and w > limit:
            position_breaches.append({"instrument_id": r["instrument_id"], "instrument_name": r["instrument_name"],
                                      "weight_pct": w, "limit_pct": limit, "gap_pp": w - limit})
    return Calc("mandate_drift", {
        "applicable": True, "denominator": total, "bands": rows, "breaches": breaches,
        "single_position_breaches": position_breaches, "max_single_position_pct": limit,
    }, METHOD_MANDATE, flags=flags)
