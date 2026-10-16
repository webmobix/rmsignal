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


METHOD_EXCLUSIONS = register(
    "exclusion_breaches",
    "A mandate is bound by exclusions when its mandate_notes state 'binding exclusions'. In a bound "
    "managed portfolio, every held instrument flagged sustainability_excluded is a breach (held "
    "'direct'); a structured product not itself flagged is looked through to its referenced "
    "underlyings and each underlying matching a flagged instrument by normalised name is a breach "
    "(held 'look_through', the product named; a basket attributes value equally to each underlying, "
    "an assumption). weight_pct = value / portfolio total x 100 (portfolio base currency). Flags in "
    "mandates without binding exclusions are not breaches; custody portfolios are not measured.",
)

BINDING_EXCLUSIONS_TEXT = "binding exclusions"


def exclusions_bound(mandate_notes: str | None) -> bool:
    return BINDING_EXCLUSIONS_TEXT in (mandate_notes or "").lower()


def exclusion_breaches(positions: pl.DataFrame, instruments: pl.DataFrame, *, service_model: str,
                       mandate_notes: str | None, value_col: str = "market_value_base") -> Calc:
    """``positions``: instrument_id, instrument_name, asset_class, ``value_col``;
    ``instruments``: instrument_id, instrument_name, asset_class, underlying_reference, sustainability_excluded."""
    from .concentration import normalise_name, parse_underlyings

    if service_model in CUSTODY_MODELS:
        return Calc("exclusion_breaches", {"applicable": False}, METHOD_EXCLUSIONS, "ok",
                    f"service model {service_model!r}: not measured against a mandate")
    if not exclusions_bound(mandate_notes):
        return Calc("exclusion_breaches", {"applicable": True, "bound": False, "breaches": []}, METHOD_EXCLUSIONS)
    total = float(positions[value_col].sum()) if positions.height else 0.0
    if total <= 0:
        return Calc("exclusion_breaches", {"applicable": True, "bound": True}, METHOD_EXCLUSIONS,
                    "insufficient_data", "no positions")
    inst = {r["instrument_id"]: r for r in instruments.iter_rows(named=True)}
    excluded_by_name = {normalise_name(r["instrument_name"]): r for r in inst.values()
                        if r["sustainability_excluded"] and r["asset_class"] != "Structured Products"}
    flags: list[QualityFlag] = []
    breaches: list[dict] = []
    basket = False
    for r in positions.iter_rows(named=True):
        i = inst.get(r["instrument_id"], {})
        v = r[value_col]
        if i.get("sustainability_excluded"):
            breaches.append({"instrument_id": r["instrument_id"], "instrument_name": r["instrument_name"],
                             "held": "direct", "via_instrument_id": None, "via_instrument_name": None,
                             "value": v, "weight_pct": v / total * 100})
            continue
        if r["asset_class"] != "Structured Products":
            continue
        names, ok = parse_underlyings(i.get("underlying_reference"), r["instrument_name"])
        if not ok:
            flags.append(QualityFlag(code="unresolved_underlying", subject=r["instrument_id"],
                                     message="underlying names not identifiable from the reference; exclusions not checked through this product"))
            continue
        basket = basket or len(names) > 1
        for n in names:
            hit = excluded_by_name.get(normalise_name(n))
            if hit:
                part = v / len(names)
                breaches.append({"instrument_id": hit["instrument_id"], "instrument_name": hit["instrument_name"],
                                 "held": "look_through", "via_instrument_id": r["instrument_id"],
                                 "via_instrument_name": r["instrument_name"], "value": part,
                                 "weight_pct": part / total * 100})
    if basket:
        flags.append(QualityFlag(code="basket_attribution_assumption",
                                 message="basket products attribute value equally to each underlying; actual sensitivity differs"))
    breaches.sort(key=lambda b: (-b["weight_pct"], b["instrument_id"], b["via_instrument_id"] or ""))
    return Calc("exclusion_breaches", {"applicable": True, "bound": True, "denominator": total,
                                       "denominator_label": "portfolio value in base currency",
                                       "breaches": breaches}, METHOD_EXCLUSIONS, flags=flags)
