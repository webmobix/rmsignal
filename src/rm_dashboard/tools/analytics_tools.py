"""Analytics tools: each fetches its own inputs for the scope and date, so agents pass identifiers only."""

from datetime import date
from typing import Literal

import polars as pl

from rm_dashboard.analytics import concentration, credit, exposure, liquidity, mandate, performance, risk
from rm_dashboard.analytics.fx import FxTable, fx_table
from rm_dashboard.analytics.base import Calc

from .envelope import build_result
from .spec import ClientParams, FacilityParams, InstrumentParams, Params, PortfolioParams, ToolContext, ToolSpec

VALUE_COL_PORTFOLIO = "market_value_base"
VALUE_COL_CLIENT = "market_value_usd"


class ExposureParams(PortfolioParams):
    dimension: Literal["asset_class", "currency", "sector", "region"]


class ConcentrationParams(ClientParams):
    include_custody: bool = True
    top_n: int = 5


class LiquidityParams(ClientParams):
    horizon_days: int | None = None


class ChangeParams(PortfolioParams):
    from_date: date


class RiskParams(InstrumentParams):
    measure: Literal["volatility", "var", "max_drawdown", "sharpe"]


DIMENSION_COLUMN = {"asset_class": "asset_class", "currency": "instrument_ccy", "sector": "sector", "region": "region"}


def _fx(ctx: ToolContext, as_of: date) -> tuple[FxTable, object]:
    m = ctx.repo.market_context(as_of=as_of)
    return fx_table(m.frame.iter_rows(named=True)) if m.frame.height else FxTable([]), m


def _client_positions(ctx: ToolContext, as_of: date, client_id: str):
    h = ctx.repo.holdings(as_of=as_of, client_id=client_id)
    pf = ctx.repo.portfolios(as_of=as_of, client_id=client_id)
    if h.frame.height:
        h.frame = h.frame.join(pf.frame.select("portfolio_id", "service_model"), on="portfolio_id", how="left")
    return h, pf


def _wrap(tool: str, p: Params, calc: Calc, pits: list, data=None):
    return build_result(tool=tool, version="1", params=p, as_of=p.as_of, pits=pits, calc=calc,
                        data=calc.data if data is None else data)


def weights_tool(ctx: ToolContext, p: PortfolioParams):
    h = ctx.repo.holdings(as_of=p.as_of, portfolio_id=p.portfolio_id)
    calc = exposure.weights(h.frame, value_col=VALUE_COL_PORTFOLIO,
                            denominator_label=f"portfolio {p.portfolio_id} total in base currency") if h.frame.height \
        else exposure.weights(pl.DataFrame(), value_col=VALUE_COL_PORTFOLIO, denominator_label="")
    return _wrap("analytics.weights", p, calc, [h])


def exposure_tool(ctx: ToolContext, p: ExposureParams):
    h = ctx.repo.holdings(as_of=p.as_of, portfolio_id=p.portfolio_id)
    calc = exposure.exposures(h.frame, dimension=p.dimension, column=DIMENSION_COLUMN[p.dimension],
                              value_col=VALUE_COL_PORTFOLIO,
                              denominator_label=f"portfolio {p.portfolio_id} total in base currency") if h.frame.height \
        else exposure.exposures(pl.DataFrame(), dimension=p.dimension, column="x", value_col="v", denominator_label="")
    return _wrap("analytics.exposure", p, calc, [h])


def concentration_tool(ctx: ToolContext, p: ConcentrationParams):
    h, pf = _client_positions(ctx, p.as_of, p.client_id)
    inst = ctx.repo.instruments(as_of=p.as_of)
    if not h.frame.height:
        calc = concentration.client_concentration(pl.DataFrame(), inst.frame, value_col=VALUE_COL_CLIENT,
                                                  include_custody=p.include_custody)
    else:
        calc = concentration.client_concentration(h.frame, inst.frame, value_col=VALUE_COL_CLIENT,
                                                  include_custody=p.include_custody, top_n=p.top_n)
    return _wrap("analytics.concentration", p, calc, [h, inst])


def mandate_tool(ctx: ToolContext, p: PortfolioParams):
    pf = ctx.repo.portfolios(as_of=p.as_of, portfolio_id=p.portfolio_id)
    h = ctx.repo.holdings(as_of=p.as_of, portfolio_id=p.portfolio_id)
    if not pf.frame.height:
        return build_result(tool="analytics.mandate_drift", version="1", params=p, as_of=p.as_of, pits=[pf], data=None,
                            status="no_data", reason=f"portfolio {p.portfolio_id} not found at {p.as_of}")
    row = pf.frame.row(0, named=True)
    bands = ctx.repo.mandates(as_of=p.as_of, mandate_code=row["mandate_code"])
    inst = ctx.repo.instruments(as_of=p.as_of)
    calc = mandate.mandate_drift(h.frame, bands.frame, service_model=row["service_model"], instruments=inst.frame)
    data = {**calc.data, "portfolio_id": p.portfolio_id, "mandate_code": row["mandate_code"], "service_model": row["service_model"]}
    return _wrap("analytics.mandate_drift", p, calc, [pf, h, bands], data)


def liquidity_tool(ctx: ToolContext, p: LiquidityParams):
    h, _ = _client_positions(ctx, p.as_of, p.client_id)
    needs = ctx.repo.cash_needs(as_of=p.as_of, client_id=p.client_id)
    com = ctx.repo.commitments(as_of=p.as_of, client_id=p.client_id)
    fx, m = _fx(ctx, p.as_of)
    horizon = p.horizon_days or ctx.settings.horizon_days
    calc = liquidity.liquidity_coverage(h.frame, needs.frame, com.frame, fx, as_of=p.as_of, horizon_days=horizon)
    p2 = p.model_copy(update={"horizon_days": horizon})
    return build_result(tool="analytics.liquidity", version="1", params=p2, as_of=p.as_of, pits=[h, needs, com, m],
                        calc=calc, data=calc.data)


def _facility_inputs(ctx: ToolContext, p: FacilityParams):
    terms = ctx.repo.facility_terms(as_of=p.as_of, facility_id=p.facility_id)
    snaps = ctx.repo.facility_snapshots(as_of=p.as_of, facility_id=p.facility_id)
    return terms, snaps


def _not_found(tool, p, pits):
    return build_result(tool=tool, version="1", params=p, as_of=p.as_of, pits=pits, data=None,
                        status="no_data", reason=f"facility {p.facility_id} not found or has no snapshot at {p.as_of}")


def credit_ltv_tool(ctx: ToolContext, p: FacilityParams):
    terms, snaps = _facility_inputs(ctx, p)
    if not terms.frame.height or not snaps.frame.height:
        return _not_found("analytics.credit_ltv", p, [terms, snaps])
    t = terms.frame.row(0, named=True)
    eff = snaps.effective_snapshot_date
    path = snaps.frame.sort("snapshot_date")
    cur = path.filter(pl.col("snapshot_date") == eff).row(0, named=True)
    calc = credit.ltv(drawn=cur["drawn"], lending_value=cur["lending_value"], collateral_value=cur["collateral_market_value"],
                      trigger_pct=t["margin_call_ltv_pct"], source_ltv_pct=cur["ltv_pct"])
    history = [{"snapshot_date": r["snapshot_date"], "ltv_pct": r["drawn"] / r["lending_value"] * 100,
                "breached": r["drawn"] / r["lending_value"] * 100 > t["margin_call_ltv_pct"]}
               for r in path.iter_rows(named=True)]
    data = {**calc.data, "facility_id": p.facility_id, "facility_ccy": t["facility_ccy"], "history": history}
    return _wrap("analytics.credit_ltv", p, calc, [terms, snaps], data)


def collateral_funding_tool(ctx: ToolContext, p: FacilityParams):
    terms, snaps = _facility_inputs(ctx, p)
    if not terms.frame.height or not snaps.frame.height:
        return _not_found("analytics.collateral_funding", p, [terms, snaps])
    t = terms.frame.row(0, named=True)
    cur = snaps.frame.filter(pl.col("snapshot_date") == snaps.effective_snapshot_date).row(0, named=True)
    client_id, pledged, ccy = t["client_id"], t["collateral_portfolio_id"], t["facility_ccy"]
    h, _ = _client_positions(ctx, p.as_of, client_id)
    fx, m = _fx(ctx, p.as_of)
    horizon = p.horizon_days or ctx.settings.horizon_days
    needs = ctx.repo.cash_needs(as_of=p.as_of, client_id=client_id)
    com = ctx.repo.commitments(as_of=p.as_of, client_id=client_id)
    liq = liquidity.liquidity_coverage(h.frame, needs.frame, com.frame, fx, as_of=p.as_of, horizon_days=horizon)
    need_fc = fx.convert(liq.data["needs_total_usd"], "USD", ccy)
    daily = h.frame.filter(pl.col("liquidity_tier") == "Daily") if h.frame.height else h.frame
    free = daily.filter(pl.col("portfolio_id") != pledged)["market_value_usd"].sum() if daily.height else 0.0
    dcol = daily.filter(pl.col("portfolio_id") == pledged)["market_value_usd"].sum() if daily.height else 0.0
    calc = credit.collateral_funding(
        need=need_fc, free_assets=fx.convert(free, "USD", ccy), drawn=cur["drawn"], lending_value=cur["lending_value"],
        collateral_value=cur["collateral_market_value"], trigger_pct=t["margin_call_ltv_pct"],
        daily_collateral_value=fx.convert(dcol, "USD", ccy))
    p2 = p.model_copy(update={"horizon_days": horizon})
    data = {**calc.data, "facility_id": p.facility_id, "currency": ccy, "horizon_days": horizon, "pledged_portfolio_id": pledged}
    return build_result(tool="analytics.collateral_funding", version="1", params=p2, as_of=p.as_of,
                        pits=[terms, snaps, h, needs, com, m], calc=calc, data=data)


def pnl_tool(ctx: ToolContext, p: PortfolioParams):
    h = ctx.repo.holdings(as_of=p.as_of, portfolio_id=p.portfolio_id)
    calc = performance.unrealised_pnl(h.frame)
    return _wrap("analytics.pnl", p, calc, [h])


def change_tool(ctx: ToolContext, p: ChangeParams):
    r0 = ctx.repo.resolve(as_of=p.from_date)
    r1 = ctx.repo.resolve(as_of=p.as_of)
    h1 = ctx.repo.holdings(as_of=p.as_of, portfolio_id=p.portfolio_id)
    h0 = ctx.repo.holdings(as_of=p.from_date, portfolio_id=p.portfolio_id)
    pf = ctx.repo.portfolios(as_of=p.as_of, portfolio_id=p.portfolio_id)
    if p.from_date >= p.as_of or r0.status != "ok" or r1.status != "ok" or not pf.frame.height \
            or r0.effective_snapshot_date == r1.effective_snapshot_date:
        why = ("from_date must precede as_of and resolve to an earlier snapshot" if r0.status == "ok" and r1.status == "ok"
               else (r0.reason or r1.reason))
        return build_result(tool="analytics.change", version="1", params=p, as_of=p.as_of, pits=[h1], data=None,
                            status="insufficient_data", reason=why or "portfolio not found")
    base = pf.frame["base_currency"][0]
    fx0, m0 = _fx(ctx, p.from_date)
    fx1, m1 = _fx(ctx, p.as_of)

    def prices(snap_date: date):
        f = ctx.repo.instrument_prices(as_of=snap_date).frame
        return dict(f.filter(pl.col("snapshot_date") == ctx.repo.resolve(as_of=snap_date).effective_snapshot_date)
                    .select("instrument_id", "price").iter_rows())

    calc = performance.decompose_change(h0.frame, h1.frame, prices(p.from_date), prices(p.as_of), fx0, fx1, base_ccy=base)
    data = {**calc.data, "from_snapshot": r0.effective_snapshot_date.isoformat(), "to_snapshot": r1.effective_snapshot_date.isoformat()}
    return _wrap("analytics.change", p, calc, [h0, h1, m0, m1], data)


def risk_tool(ctx: ToolContext, p: RiskParams):
    pr = ctx.repo.instrument_prices(as_of=p.as_of, instrument_id=p.instrument_id)
    prices = pr.frame.sort("snapshot_date")["price"].to_list() if pr.frame.height else []
    calc = risk.risk_measure(p.measure, prices)
    return _wrap("analytics.risk", p, calc, [pr])


def _a(name, desc, params, fn):
    return ToolSpec(name, desc, params, fn, "analytics")


ANALYTICS_TOOLS = [
    _a("analytics.weights", "Position weights of a portfolio, with the denominator stated.", PortfolioParams, weights_tool),
    _a("analytics.exposure", "Portfolio exposure by asset_class, currency, sector or region.", ExposureParams, exposure_tool),
    _a("analytics.concentration", "Client-level concentration across portfolios with look-through, HHI and top-N.", ConcentrationParams, concentration_tool),
    _a("analytics.mandate_drift", "Asset-class weights against mandate bands; custody portfolios are not applicable.", PortfolioParams, mandate_tool),
    _a("analytics.liquidity", "Liquid assets against planned needs and uncalled commitments within a horizon.", LiquidityParams, liquidity_tool),
    _a("analytics.credit_ltv", "Loan-to-value, headroom to trigger and cure amount for a facility.", FacilityParams, credit_ltv_tool),
    _a("analytics.collateral_funding", "Whether a client's needs can be funded without breaching the facility when collateral is pledged.", FacilityParams, collateral_funding_tool),
    _a("analytics.pnl", "Unrealised profit and loss of a portfolio, excluding positions without cost basis.", PortfolioParams, pnl_tool),
    _a("analytics.change", "Change in portfolio value between two dates decomposed into price, FX and flow.", ChangeParams, change_tool),
    _a("analytics.risk", "Volatility, VaR, drawdown or Sharpe; insufficient_history when the series is too short.", RiskParams, risk_tool),
]
