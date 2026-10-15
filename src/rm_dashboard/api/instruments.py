"""``/api/instruments``: the master with what the book holds and the outlook where one exists."""

from datetime import date

import polars as pl
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rm_dashboard.outlook.contracts import InstrumentOutlook

from .clientdata import client_rows
from .context import ReadContext
from .deps import AsOf, Ctx
from .holdings import at, snapshots_at
from .models import HasGaps, gap

router = APIRouter(prefix="/api", tags=["instruments"])


class InstrumentRow(BaseModel):
    instrument_id: str
    instrument_name: str
    asset_class: str
    sub_asset_class: str
    sector: str | None = None
    region: str
    currency: str
    liquidity_tier: str
    latest_price: float | None = None
    previous_price: float | None = None
    price_change_pct: float | None = None
    holder_portfolios: int
    holder_clients: int
    held_usd: float
    has_outlook: bool


class PricePoint(BaseModel):
    snapshot_date: date
    price: float


class Holder(BaseModel):
    client_id: str
    client_name: str
    portfolio_id: str
    quantity: float
    value_usd: float
    weight_pct: float


class InstrumentDetail(HasGaps):
    as_of: date
    instrument: InstrumentRow
    underlying_reference: str | None = None
    sustainability_excluded: bool
    concentration_limit_applies: bool
    price_path: list[PricePoint]
    holders: list[Holder]
    outlook: InstrumentOutlook | None = None


def _prices(ctx: ReadContext, as_of: date) -> dict[str, list[tuple[date, float]]]:
    f = ctx.repo.instrument_prices(as_of=as_of).frame
    out: dict[str, list[tuple[date, float]]] = {}
    for r in f.sort("instrument_id", "snapshot_date").iter_rows(named=True) if f.height else []:
        out.setdefault(r["instrument_id"], []).append((r["snapshot_date"], r["price"]))
    return out


def instrument_rows(ctx: ReadContext, as_of: date) -> list[InstrumentRow]:
    eff, _, _ = snapshots_at(ctx, as_of)
    inst = ctx.repo.instruments(as_of=as_of).frame
    h = ctx.repo.holdings(as_of=as_of).frame
    held: dict[str, tuple[int, int, float]] = {}
    if h.height:
        agg = h.group_by("instrument_id").agg(
            pl.col("portfolio_id").n_unique().alias("p"), pl.col("client_id").n_unique().alias("c"),
            pl.col("market_value_usd").sum().alias("v"))
        held = {r["instrument_id"]: (r["p"], r["c"], r["v"]) for r in agg.iter_rows(named=True)}
    prices = _prices(ctx, as_of)
    outlooks = set(ctx.outlooks.instrument_ids(as_of))
    rows = []
    for i in inst.sort("instrument_id").iter_rows(named=True) if inst.height else []:
        series = prices.get(i["instrument_id"], [])
        last = series[-1][1] if series else None
        prev = series[-2][1] if len(series) > 1 else None
        p, c, v = held.get(i["instrument_id"], (0, 0, 0.0))
        rows.append(InstrumentRow(
            **{k: i[k] for k in ("instrument_id", "instrument_name", "asset_class", "sub_asset_class", "sector",
                                  "region", "currency", "liquidity_tier")},
            latest_price=last, previous_price=prev, price_change_pct=((last - prev) / prev * 100 if last and prev else None),
            holder_portfolios=p, holder_clients=c, held_usd=v, has_outlook=i["instrument_id"] in outlooks))
    return rows


@router.get("/instruments")
def list_instruments(ctx: Ctx, as_of: AsOf) -> list[InstrumentRow]:
    return instrument_rows(ctx, as_of)


@router.get("/instruments/{instrument_id}")
def get_instrument(ctx: Ctx, as_of: AsOf, instrument_id: str) -> InstrumentDetail:
    row = next((r for r in instrument_rows(ctx, as_of) if r.instrument_id == instrument_id), None)
    if row is None:
        raise HTTPException(404, f"no instrument {instrument_id!r}")
    master = ctx.repo.instruments(as_of=as_of, instrument_ids=[instrument_id]).frame.row(0, named=True)
    names = {cid: c["client_name"] for cid, c in client_rows(ctx, as_of).items()}
    h = ctx.repo.holdings(as_of=as_of).frame
    mine = h.filter(pl.col("instrument_id") == instrument_id) if h.height else h
    holders = [Holder(client_id=r["client_id"], client_name=names.get(r["client_id"], r["client_id"]),
                      portfolio_id=r["portfolio_id"], quantity=r["quantity"], value_usd=r["market_value_usd"],
                      weight_pct=r["weight_pct"])
               for r in mine.sort("market_value_usd", descending=True).iter_rows(named=True)] if mine.height else []
    outlook = ctx.outlooks.load_instrument(as_of, instrument_id)
    gaps = [] if outlook else [gap(f"outlook_missing: no outlook persisted for {instrument_id} at {as_of}", instrument_id)]
    return InstrumentDetail(
        as_of=as_of, instrument=row, underlying_reference=master["underlying_reference"],
        sustainability_excluded=bool(master["sustainability_excluded"]),
        concentration_limit_applies=bool(master["concentration_limit_applies"]),
        price_path=[PricePoint(snapshot_date=d, price=p) for d, p in _prices(ctx, as_of).get(instrument_id, [])],
        holders=holders, outlook=outlook, gaps=gaps)
