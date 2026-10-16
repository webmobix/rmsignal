# Analytics

Deterministic calculations in `rm_dashboard.analytics`. They are pure: inputs are Polars
frames or plain values, there is no I/O and no clock, and the same input gives the same output.
No figure in any analysis is produced by a language model. Each function returns a `Calc` with
a `data` payload, a `method` string, a status and quality flags.

`risk_measures` returns `insufficient_history` and no number when fewer observations than
the stated minimum exist (the dataset has five price points per instrument).

The method strings below are the source of truth, are returned with every result, and
`tests/test_analytics.py::test_docs_list_every_method` keeps this file in sync with them.

## concentration

Value is aggregated per exposure entity across all supplied portfolios. Structured products are looked through to their referenced underlyings; a product referencing a basket attributes its value equally to each underlying (an assumption, not a sensitivity). Single names are positions flagged concentration_limit_applies, matched by normalised issuer name. share_pct = entity value / denominator x 100; HHI = sum of squared shares in percent (0-10000) over all entities, diversified positions counted individually. The denominator is stated.

## credit_ltv

LTV% = drawn / lending_value x 100 where lending value is market value after advance-rate haircuts. Headroom to trigger: ltv_gap_pp = trigger - LTV and lending_value_buffer = lending_value - drawn / (trigger/100). Cure by selling collateral at the average advance rate a = lending_value / collateral_value with proceeds repaying the loan: sale = (drawn - T x lending_value) / (1 - T x a), T = trigger/100, when LTV exceeds the trigger. The recomputed LTV is compared with the source figure.

## collateral_funding

Cash need is met first from assets outside the pledged portfolio. Any remainder must be raised by selling collateral, which releases lending value at the average advance rate and forces repayment so LTV stays within the trigger. Required sale x satisfies x >= shortfall and x >= (drawn + shortfall - T x lending_value) / (1 - T x a); repayment = x - shortfall. All values in the facility currency.

## sector_look_through

Direct: positions are grouped by the sector of their instrument, exposure_pct = group value / portfolio value x 100 (portfolio base currency). Look-through: each structured product is replaced by its referenced underlyings, each classified by the sector of the non-structured instrument whose normalised name it matches; a product referencing a basket attributes its value equally to each underlying (an assumption, not a sensitivity). An underlying that matches no instrument or has no sector, and a product whose underlyings cannot be identified, is grouped as 'Unclassified (look-through)'; a position without a sector is 'unclassified'. Sector labels that are asset types (Diversified, Corporate, Sovereign, Cash, Gold, Multi, Macro) are shown as their own groups. No sector data is added. Both views use the same denominator, which is stated.

## weights

weight_pct = value / sum(value of the positions supplied) x 100; the denominator is the sum over exactly the positions given and is reported with its label.

## exposure

Positions are grouped by the dimension; exposure_pct = group value / sum(value of the positions supplied) x 100. Missing classifications are grouped as 'unclassified'.

## fx

Each pair is a quote: 1 base = rate quote (USDSGD 1.352 means SGD 1.352 per USD). A currency's USD value is rate when it is the base of a pair quoted in USD, and 1/rate when it is the quote of a pair based in USD. Amounts convert as amount x usd_per(from) / usd_per(to).

## bond_nominal

Bond quantity is in units of 100 nominal; nominal = quantity x 100 and market value = quantity x price, the same formula as every other asset class.

## liquidity_coverage

Liquid assets (market value in USD) are summed by liquidity tier. Needs and uncalled commitments whose due window overlaps (as_of, as_of + horizon_days] are converted to USD at the rate of the effective snapshot and summed. Aspirational needs are excluded and listed separately. A cash need that restates the commitments replaces them (no double count). Shortfall = max(0, needs - Daily-tier assets); coverage = Daily assets / needs. Each item keeps its stated certainty; amounts are not probability-weighted.

## mandate_drift

Asset-class weight = class value / portfolio total x 100 (portfolio base currency). Each weight is compared with the mandate min/target/max; gap_pp is the distance beyond the nearest breached band edge, drift_pp the distance from target. Positions flagged concentration_limit_applies are compared with max_single_position_pct. Custody portfolios are excluded from this comparison (they remain in client totals).

## unrealised_pnl

Unrealised P&L = sum of unrealised_pnl_base over positions with a cost basis; percentage = P&L / sum of cost basis of those positions x 100. Positions without a cost basis are excluded and counted.

## change_decomposition

Per instrument, value V = quantity x price x fx (base per local). Between t0 and t1: flow = (q1 - q0) x p0 x f0; price = q1 x (p1 - p0) x f0; fx = q1 x p1 x (f1 - f0). The three sum exactly to V1 - V0 by construction. Values are recomputed from quantity, price and FX; the difference to the reported market values is returned as unexplained.

## risk_measures

Volatility, value-at-risk, drawdown and Sharpe need a return series; they return insufficient_history (no number) when fewer observations than the stated minimum are available. With enough data: volatility = sample stdev of simple returns; historical VaR = negative quantile of returns; drawdown = worst peak-to-trough decline of the price path; Sharpe = mean excess return / volatility (per-period, not annualised).


## market_trend

Per market series, from its values at every snapshot up to the effective one: latest level; absolute change and percent change (change / earlier level x 100, 2 decimals) against the previous snapshot and against the first snapshot; number of snapshots. Rates and volatility are levels, so their percent change is a change in the level, not in basis points. With fewer than 2 snapshots it returns insufficient_history.

## instrument_context

From an instrument's prices at every snapshot up to the effective one: percent change (change / earlier price x 100, 2 decimals) against the previous snapshot and against the first snapshot. Peers are the other instruments of the same asset class with the same sector, or with the same sub-asset class when the sector is generic (Diversified, Multi, Cash or empty), those in the instrument's region first, at most 8; the group average is the mean of the peers' percent changes and the relative performance is the instrument's change minus that average, in percentage points. With fewer than 2 prices it returns insufficient_history; with none, insufficient_data.
