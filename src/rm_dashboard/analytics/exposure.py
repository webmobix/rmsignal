"""Weights and exposures with a stated denominator."""

import polars as pl

from rm_dashboard.domain import QualityFlag

from .base import Calc, insufficient, register

METHOD_WEIGHTS = register(
    "weights",
    "weight_pct = value / sum(value of the positions supplied) x 100; the denominator is the "
    "sum over exactly the positions given and is reported with its label.",
)
METHOD_EXPOSURE = register(
    "exposure",
    "Positions are grouped by the dimension; exposure_pct = group value / sum(value of the "
    "positions supplied) x 100. Missing classifications are grouped as 'unclassified'.",
)

UNCLASSIFIED = "unclassified"


def weights(positions: pl.DataFrame, *, value_col: str, denominator_label: str,
            key_cols: tuple[str, ...] = ("portfolio_id", "instrument_id")) -> Calc:
    if positions.is_empty():
        return insufficient("weights", "no positions supplied", METHOD_WEIGHTS)
    total = float(positions[value_col].sum())
    if total == 0:
        return insufficient("weights", "denominator is zero", METHOD_WEIGHTS)
    rows = []
    for r in positions.iter_rows(named=True):
        row = {k: r[k] for k in key_cols}
        row.update(value=r[value_col], weight_pct=r[value_col] / total * 100)
        rows.append(row)
    return Calc("weights", {
        "value_col": value_col, "denominator": total, "denominator_label": denominator_label,
        "sum_weight_pct": sum(r["weight_pct"] for r in rows), "weights": rows,
    }, METHOD_WEIGHTS)


def exposures(positions: pl.DataFrame, *, dimension: str, column: str, value_col: str,
              denominator_label: str) -> Calc:
    if positions.is_empty():
        return insufficient("exposure", "no positions supplied", METHOD_EXPOSURE)
    total = float(positions[value_col].sum())
    if total == 0:
        return insufficient("exposure", "denominator is zero", METHOD_EXPOSURE)
    df = positions.with_columns(
        pl.when(pl.col(column).is_null() | (pl.col(column).cast(pl.String).str.strip_chars() == ""))
        .then(pl.lit(UNCLASSIFIED)).otherwise(pl.col(column).cast(pl.String)).alias("_g")
    )
    flags = []
    missing = df.filter(pl.col("_g") == UNCLASSIFIED)
    if missing.height:
        subjects = [f"{r['portfolio_id']}/{r['instrument_id']}" for r in missing.iter_rows(named=True)]
        flags.append(QualityFlag(
            code=f"unclassified_{dimension}", subject=", ".join(subjects),
            message=f"{missing.height} position(s) have no {dimension}; grouped as '{UNCLASSIFIED}'",
        ))
    g = (df.group_by("_g").agg(pl.col(value_col).sum().alias("value"), pl.len().alias("positions"))
         .sort(["value", "_g"], descending=[True, False]))
    groups = [{"name": r["_g"], "value": r["value"], "exposure_pct": r["value"] / total * 100,
               "positions": r["positions"]} for r in g.iter_rows(named=True)]
    return Calc("exposure", {
        "dimension": dimension, "value_col": value_col, "denominator": total,
        "denominator_label": denominator_label, "groups": groups,
    }, METHOD_EXPOSURE, flags=flags)
