"""Holdings across snapshots, in USD so portfolios of different base currencies can be added up.

``portfolio_aum`` in the dataset is in each portfolio's base currency; every figure that is summed across
portfolios here comes from ``market_value_usd``.
"""

from datetime import date

import polars as pl

from .context import ReadContext


def snapshots_at(ctx: ReadContext, as_of: date) -> tuple[date | None, date | None, list[date]]:
    """(effective snapshot, previous snapshot, all snapshots up to the effective one)."""
    eff = ctx.repo.resolve(as_of=as_of).effective_snapshot_date
    if eff is None:
        return None, None, []
    snaps = [s for s in ctx.repo.snapshot_dates() if s <= eff]
    return eff, (snaps[-2] if len(snaps) > 1 else None), snaps


def holdings_over_time(ctx: ReadContext, snaps: list[date], *, client_id: str | None = None,
                       portfolio_id: str | None = None) -> pl.DataFrame:
    """Holdings of every snapshot in ``snaps`` stacked, with the portfolio's service model joined on."""
    frames = [ctx.repo.holdings(as_of=s, client_id=client_id, portfolio_id=portfolio_id).frame for s in snaps]
    frames = [f for f in frames if f.height]
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="vertical_relaxed")


def at(frame: pl.DataFrame, snap: date | None) -> pl.DataFrame:
    if snap is None or frame.is_empty():
        return pl.DataFrame()
    return frame.filter(pl.col("snapshot_date") == snap)


def total_usd(frame: pl.DataFrame) -> float:
    return float(frame["market_value_usd"].sum()) if frame.height else 0.0


def change(now: float, before: float | None) -> tuple[float | None, float | None]:
    if before is None:
        return None, None
    return now - before, ((now - before) / before * 100 if before else None)
