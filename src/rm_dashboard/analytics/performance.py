"""Unrealised P&L and exact price / FX / flow decomposition of a value change."""

import polars as pl

from rm_dashboard.domain import QualityFlag

from .base import Calc, insufficient, register
from .fx import FxTable, market_value

METHOD_PNL = register(
    "unrealised_pnl",
    "Unrealised P&L = sum of unrealised_pnl_base over positions with a cost basis; percentage "
    "= P&L / sum of cost basis of those positions x 100. Positions without a cost basis are "
    "excluded and counted.",
)
METHOD_DECOMP = register(
    "change_decomposition",
    "Per instrument, value V = quantity x price x fx (base per local). Between t0 and t1: "
    "flow = (q1 - q0) x p0 x f0; price = q1 x (p1 - p0) x f0; fx = q1 x p1 x (f1 - f0). "
    "The three sum exactly to V1 - V0 by construction. Values are recomputed from quantity, "
    "price and FX; the difference to the reported market values is returned as unexplained.",
)


def unrealised_pnl(positions: pl.DataFrame) -> Calc:
    if positions.is_empty():
        return insufficient("unrealised_pnl", "no positions supplied", METHOD_PNL)
    with_cost = positions.filter(pl.col("cost_basis_base").is_not_null())
    missing = positions.filter(pl.col("cost_basis_base").is_null())
    flags = []
    if missing.height:
        flags.append(QualityFlag(
            code="pnl_excludes_positions",
            subject=", ".join(f"{r['portfolio_id']}/{r['instrument_id']}" for r in missing.iter_rows(named=True)),
            message=f"{missing.height} position(s) without cost basis excluded from P&L",
        ))
    pnl = float(with_cost["unrealised_pnl_base"].sum()) if with_cost.height else 0.0
    cost = float(with_cost["cost_basis_base"].sum()) if with_cost.height else 0.0
    return Calc("unrealised_pnl", {
        "unrealised_pnl_base": pnl, "cost_basis_base": cost,
        "unrealised_pnl_pct": (pnl / cost * 100) if cost else None,
        "positions_included": with_cost.height, "positions_excluded": missing.height,
    }, METHOD_PNL, flags=flags)


def decompose_change(h0: pl.DataFrame, h1: pl.DataFrame, price0: dict[str, float], price1: dict[str, float],
                     fx0: FxTable, fx1: FxTable, *, base_ccy: str) -> Calc:
    """``h0``/``h1``: holdings at the two snapshots of one portfolio (quantity, instrument_ccy, market_value_base)."""
    q0 = {r["instrument_id"]: r for r in h0.iter_rows(named=True)}
    q1 = {r["instrument_id"]: r for r in h1.iter_rows(named=True)}
    rows = []
    for iid in sorted(set(q0) | set(q1)):
        ccy = (q1.get(iid) or q0[iid])["instrument_ccy"]
        a, b = q0.get(iid), q1.get(iid)
        qa, qb = (a["quantity"] if a else 0), (b["quantity"] if b else 0)
        pa, pb = price0[iid], price1[iid]
        fa, fb = fx0.base_per_local(ccy, base_ccy), fx1.base_per_local(ccy, base_ccy)
        v0, v1 = market_value(qa, pa) * fa, market_value(qb, pb) * fb
        flow, price, fxe = (qb - qa) * pa * fa, qb * (pb - pa) * fa, qb * pb * (fb - fa)
        rows.append({"instrument_id": iid, "value_t0": v0, "value_t1": v1, "flow": flow,
                     "price": price, "fx": fxe, "change": v1 - v0})
    tot = {k: sum(r[k] for r in rows) for k in ("value_t0", "value_t1", "flow", "price", "fx", "change")}
    reported0 = float(h0["market_value_base"].sum()) if h0.height else 0.0
    reported1 = float(h1["market_value_base"].sum()) if h1.height else 0.0
    return Calc("change_decomposition", {
        "base_currency": base_ccy, "total": tot, "by_instrument": rows,
        "reported_change": reported1 - reported0,
        "unexplained": (reported1 - reported0) - tot["change"],
    }, METHOD_DECOMP)
