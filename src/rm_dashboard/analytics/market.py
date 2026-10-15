"""Market series trend: level and change between snapshots. The model reads these figures, it never computes them."""

from typing import Any

from .base import Calc, register

METHOD_MARKET_TREND = register(
    "market_trend",
    "Per market series, from its values at every snapshot up to the effective one: latest level; absolute change "
    "and percent change (change / earlier level x 100, 2 decimals) against the previous snapshot and against the "
    "first snapshot; number of snapshots. Rates and volatility are levels, so their percent change is a change in "
    "the level, not in basis points. With fewer than 2 snapshots it returns insufficient_history.",
)


def pivot_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Long market rows (one per series and snapshot) -> one entry per series with its values, oldest first."""
    series: dict[str, dict[str, Any]] = {}
    for r in sorted(rows, key=lambda r: (r["series_id"], r["snapshot_date"])):
        s = series.setdefault(r["series_id"], {"series_id": r["series_id"], "series_name": r["series_name"],
                                               "category": r["category"], "unit": r["unit"], "values": []})
        s["values"].append({"snapshot_date": r["snapshot_date"], "value": r["value"]})
    return list(series.values())


def _change(latest: float, earlier: float) -> dict[str, Any]:
    pct = round((latest - earlier) / earlier * 100, 2) if earlier else None
    return {"change": round(latest - earlier, 4), "change_pct": pct}


def market_trend(series: list[dict[str, Any]]) -> Calc:
    if not series:
        return Calc("market_trend", {"snapshots": 0, "series": []}, METHOD_MARKET_TREND, "insufficient_data", "no market series supplied")
    out = []
    for s in series:
        v = s["values"]
        latest, first = v[-1], v[0]
        row: dict[str, Any] = {
            "series_id": s["series_id"], "series_name": s["series_name"], "category": s["category"], "unit": s["unit"],
            "snapshots": len(v), "latest_date": latest["snapshot_date"], "latest": latest["value"],
            "first_date": first["snapshot_date"], "first": first["value"],
        }
        if len(v) >= 2:
            prev = v[-2]
            row |= {"previous_date": prev["snapshot_date"], "previous": prev["value"],
                    "vs_previous": _change(latest["value"], prev["value"]), "vs_first": _change(latest["value"], first["value"])}
        out.append(row)
    n = max(len(s["values"]) for s in series)
    data = {"snapshots": n, "latest_snapshot_date": max(s["values"][-1]["snapshot_date"] for s in series),
            "first_snapshot_date": min(s["values"][0]["snapshot_date"] for s in series), "series": out}
    if n < 2:
        return Calc("market_trend", data, METHOD_MARKET_TREND, "insufficient_history",
                    f"a trend needs 2 snapshots; {n} available")
    return Calc("market_trend", data, METHOD_MARKET_TREND)
