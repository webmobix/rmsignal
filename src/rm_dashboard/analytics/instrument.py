"""Instrument price path and comparison with its peers. The model reads these figures, it never computes them."""

from datetime import date
from typing import Any

from .base import Calc, register

METHOD_INSTRUMENT_CONTEXT = register(
    "instrument_context",
    "From an instrument's prices at every snapshot up to the effective one: percent change (change / earlier price x "
    "100, 2 decimals) against the previous snapshot and against the first snapshot. Peers are the other instruments of "
    "the same asset class with the same sector, or with the same sub-asset class when the sector is generic "
    "(Diversified, Multi, Cash or empty), those in the instrument's region first, at most 8; the group average is the "
    "mean of the peers' percent changes and the relative performance is the instrument's change minus that average, in "
    "percentage points. With fewer than 2 prices it returns insufficient_history; with none, insufficient_data.",
)

GENERIC_SECTORS = ("Diversified", "Multi", "Cash", "")
MAX_PEERS = 8


def _pct(latest: float, earlier: float) -> float | None:
    return round((latest - earlier) / earlier * 100, 2) if earlier else None


def price_path(points: list[tuple[date, float]]) -> dict[str, Any]:
    pts = sorted(points)
    rows = [{"snapshot_date": d, "price": p, "change_pct_vs_previous": _pct(p, pts[i - 1][1]) if i else None}
            for i, (d, p) in enumerate(pts)]
    out: dict[str, Any] = {"price_path": rows, "snapshots": len(pts)}
    if pts:
        (fd, first), (ld, latest) = pts[0], pts[-1]
        out |= {"first_date": fd, "first": first, "latest_date": ld, "latest": latest}
    if len(pts) >= 2:
        pd_, prev = pts[-2]
        out |= {"previous_date": pd_, "previous": prev, "vs_previous_pct": _pct(latest, prev), "vs_first_pct": _pct(latest, first)}
    return out


def peer_basis(instrument: dict[str, Any]) -> tuple[str, str]:
    sector = instrument.get("sector") or ""
    return ("sector", sector) if sector not in GENERIC_SECTORS else ("sub_asset_class", instrument["sub_asset_class"])


def select_peers(instrument: dict[str, Any], others: list[dict[str, Any]]) -> list[dict[str, Any]]:
    basis, value = peer_basis(instrument)
    same = [o for o in others if o["instrument_id"] != instrument["instrument_id"]
            and o["asset_class"] == instrument["asset_class"] and (o.get(basis) or "") == value]
    same.sort(key=lambda o: (o.get("region") != instrument.get("region"), o["instrument_id"]))
    return same[:MAX_PEERS]


def instrument_context(instrument: dict[str, Any], series: dict[str, list[tuple[date, float]]],
                       others: list[dict[str, Any]]) -> Calc:
    own = price_path(series.get(instrument["instrument_id"], []))
    basis, value = peer_basis(instrument)
    members = []
    for o in select_peers(instrument, others):
        p = price_path(series.get(o["instrument_id"], []))
        members.append({"instrument_id": o["instrument_id"], "instrument_name": o["instrument_name"], "region": o.get("region"),
                        "vs_previous_pct": p.get("vs_previous_pct"), "vs_first_pct": p.get("vs_first_pct")})
    peers: dict[str, Any] = {"basis": basis, "basis_value": value, "members": members}
    for key in ("vs_previous_pct", "vs_first_pct"):
        vals = [m[key] for m in members if m[key] is not None]
        avg = round(sum(vals) / len(vals), 2) if vals else None
        peers[f"group_avg_{key}"] = avg
        peers[f"relative_{key[:-4]}_pp"] = round(own[key] - avg, 2) if avg is not None and own.get(key) is not None else None
    data = {"instrument": {k: instrument.get(k) for k in ("instrument_id", "instrument_name", "asset_class", "sub_asset_class",
                                                          "sector", "region", "currency", "liquidity_tier", "underlying_reference")},
            "summary": {k: v for k, v in own.items() if k != "price_path"}, "price_path": own["price_path"], "peers": peers}
    n = own["snapshots"]
    if n == 0:
        return Calc("instrument_context", data, METHOD_INSTRUMENT_CONTEXT, "insufficient_data", "no price for this instrument at as_of")
    if n < 2:
        return Calc("instrument_context", data, METHOD_INSTRUMENT_CONTEXT, "insufficient_history", f"a price path needs 2 prices; {n} available")
    return Calc("instrument_context", data, METHOD_INSTRUMENT_CONTEXT)
