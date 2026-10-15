# Methods

Every figure, flag and check in the analysis layer, with the method behind it. Tool and analytic method strings are also returned in every `ToolResult.computation.method`. `tests/test_docs.py` keeps this file in sync with the code.

## 1. Point-in-time rules

Source: `pit/polars_repo.py`, details in [point-in-time.md](point-in-time.md).

- **Snapshot resolution:** latest snapshot on or before `as_of`; `gap_days = as_of - snapshot`. None earlier gives `insufficient_data`.
- **Event-dated data** (transactions, events, notes): kept only if dated on or before `as_of`.
- **Planned cash needs and commitments:** no knowledge date, so assumed known since `client_since`; kept from then on.
- **Unversioned attributes** (risk profile, mandate bands, KYC date, domicile, benchmark, instrument classification): returned as held today and tagged `current_only`.
- **Client AUM:** the source's current total is dropped; `aum_usd` is the sum of USD market values at the effective snapshot.
- **KYC overdue:** `kyc_review_due < as_of`; `days_to_kyc_due = kyc_review_due - as_of`.
- **Quality flags:** `stale_mark` (valuation date before snapshot), `missing_cost_basis`, `mid_period_position` (absent at previous snapshot), `bond_nominal_unit`, `subscription_currency_mismatch` (settled outside portfolio base currency), `facility_drawdown_mismatch` (rise in drawn amount vs booked drawdowns), `snapshot_lag`, `current_only`, `assumed_known_since_relationship_start`.

## 2. Analytics (deterministic, Polars)

### concentration

Value is aggregated per exposure entity across all supplied portfolios. Structured products are looked through to their referenced underlyings; a product referencing a basket attributes its value equally to each underlying (an assumption, not a sensitivity). Single names are positions flagged concentration_limit_applies, matched by normalised issuer name. share_pct = entity value / denominator x 100; HHI = sum of squared shares in percent (0-10000) over all entities, diversified positions counted individually. The denominator is stated.

### credit_ltv

LTV% = drawn / lending_value x 100 where lending value is market value after advance-rate haircuts. Headroom to trigger: ltv_gap_pp = trigger - LTV and lending_value_buffer = lending_value - drawn / (trigger/100). Cure by selling collateral at the average advance rate a = lending_value / collateral_value with proceeds repaying the loan: sale = (drawn - T x lending_value) / (1 - T x a), T = trigger/100, when LTV exceeds the trigger. The recomputed LTV is compared with the source figure.

### collateral_funding

Cash need is met first from assets outside the pledged portfolio. Any remainder must be raised by selling collateral, which releases lending value at the average advance rate and forces repayment so LTV stays within the trigger. Required sale x satisfies x >= shortfall and x >= (drawn + shortfall - T x lending_value) / (1 - T x a); repayment = x - shortfall. All values in the facility currency.

### weights

weight_pct = value / sum(value of the positions supplied) x 100; the denominator is the sum over exactly the positions given and is reported with its label.

### exposure

Positions are grouped by the dimension; exposure_pct = group value / sum(value of the positions supplied) x 100. Missing classifications are grouped as 'unclassified'.

### fx

Each pair is a quote: 1 base = rate quote (USDSGD 1.352 means SGD 1.352 per USD). A currency's USD value is rate when it is the base of a pair quoted in USD, and 1/rate when it is the quote of a pair based in USD. Amounts convert as amount x usd_per(from) / usd_per(to).

### bond_nominal

Bond quantity is in units of 100 nominal; nominal = quantity x 100 and market value = quantity x price, the same formula as every other asset class.

### liquidity_coverage

Liquid assets (market value in USD) are summed by liquidity tier. Needs and uncalled commitments whose due window overlaps (as_of, as_of + horizon_days] are converted to USD at the rate of the effective snapshot and summed. Aspirational needs are excluded and listed separately. A cash need that restates the commitments replaces them (no double count). Shortfall = max(0, needs - Daily-tier assets); coverage = Daily assets / needs. Each item keeps its stated certainty; amounts are not probability-weighted.

### mandate_drift

Asset-class weight = class value / portfolio total x 100 (portfolio base currency). Each weight is compared with the mandate min/target/max; gap_pp is the distance beyond the nearest breached band edge, drift_pp the distance from target. Positions flagged concentration_limit_applies are compared with max_single_position_pct. Custody portfolios are excluded from this comparison (they remain in client totals).

### unrealised_pnl

Unrealised P&L = sum of unrealised_pnl_base over positions with a cost basis; percentage = P&L / sum of cost basis of those positions x 100. Positions without a cost basis are excluded and counted.

### change_decomposition

Per instrument, value V = quantity x price x fx (base per local). Between t0 and t1: flow = (q1 - q0) x p0 x f0; price = q1 x (p1 - p0) x f0; fx = q1 x p1 x (f1 - f0). The three sum exactly to V1 - V0 by construction. Values are recomputed from quantity, price and FX; the difference to the reported market values is returned as unexplained.

### risk_measures

Volatility, value-at-risk, drawdown and Sharpe need a return series; they return insufficient_history (no number) when fewer observations than the stated minimum are available. With enough data: volatility = sample stdev of simple returns; historical VaR = negative quantile of returns; drawdown = worst peak-to-trough decline of the price path; Sharpe = mean excess return / volatility (per-period, not annualised).

## 3. Tools

Each tool takes identifiers and `as_of` only (the agent layer supplies `as_of`; the model cannot choose it). Parameters below exclude `as_of`.

| Tool | Kind | Parameters | What it returns | Agents allowed |
|---|---|---|---|---|
| `analytics.change` | analytics | portfolio_id, from_date | Change in portfolio value between two dates decomposed into price, FX and flow. | portfolio_analyst |
| `analytics.collateral_funding` | analytics | facility_id, horizon_days | Whether a client's needs can be funded without breaching the facility when collateral is pledged. | relationship_analyst |
| `analytics.concentration` | analytics | client_id, include_custody, top_n | Client-level concentration across portfolios with look-through, HHI and top-N. | relationship_analyst |
| `analytics.credit_ltv` | analytics | facility_id, horizon_days | Loan-to-value, headroom to trigger and cure amount for a facility. | relationship_analyst |
| `analytics.exposure` | analytics | portfolio_id, dimension | Portfolio exposure by asset_class, currency, sector or region. | portfolio_analyst |
| `analytics.liquidity` | analytics | client_id, horizon_days | Liquid assets against planned needs and uncalled commitments within a horizon. | relationship_analyst |
| `analytics.mandate_drift` | analytics | portfolio_id | Asset-class weights against mandate bands; custody portfolios are not applicable. | portfolio_analyst |
| `analytics.pnl` | analytics | portfolio_id | Unrealised profit and loss of a portfolio, excluding positions without cost basis. | portfolio_analyst |
| `analytics.risk` | analytics | instrument_id, measure | Volatility, VaR, drawdown or Sharpe; insufficient_history when the series is too short. | instrument_analyst |
| `analytics.weights` | analytics | portfolio_id | Position weights of a portfolio, with the denominator stated. | portfolio_analyst |
| `cash_needs.list` | domain | client_id | Planned cash needs of a client with stated certainty. | relationship_analyst |
| `clients.get` | domain | client_id | Client profile as of a date. Unversioned attributes are tagged current_only. | relationship_analyst |
| `clients.list` | domain | - | Clients that exist at a date, with a few identifying fields. | - |
| `commitments.list` | domain | client_id | Private-markets commitments of a client. | relationship_analyst |
| `credit.facilities` | domain | client_id | Credit facilities of a client with figures per snapshot up to as_of. | relationship_analyst |
| `events.list` | domain | - | Curated dated events up to as_of. | instrument_analyst, portfolio_analyst, relationship_analyst |
| `instruments.get` | domain | instrument_id | Instrument reference data. | instrument_analyst, portfolio_analyst |
| `instruments.prices` | domain | instrument_id | Instrument price history, one row per snapshot up to as_of. | instrument_analyst |
| `market.snapshot` | domain | - | Market series (indices, rates, FX, commodities) at the effective snapshot. | instrument_analyst, portfolio_analyst, relationship_analyst |
| `news.list` | domain | - | News for the period. Currently no news source: returns no_data plus curated events. | instrument_analyst, relationship_analyst |
| `notes.list` | domain | client_id | Relationship-manager notes up to as_of, as dated quoted text. | relationship_analyst |
| `parties.get` | domain | client_id | The client as a party (individual or organisation) with its relationships list. | relationship_analyst |
| `peers.kyc_status` | peer | client_id | KYC and compliance status of a client from the bank's KYC peer agent (A2A). | relationship_analyst |
| `persons.list` | domain | client_id | Persons linked to a client. Currently no data source: returns no_data. | relationship_analyst |
| `portfolios.get` | domain | portfolio_id | One portfolio with AUM at the effective snapshot. | portfolio_analyst |
| `portfolios.list` | domain | client_id | Portfolios of a client with AUM at the effective snapshot. | relationship_analyst |
| `positions.list` | domain | portfolio_id | Positions of a portfolio at the effective snapshot, with data-quality flags. | portfolio_analyst |
| `relationships.list` | domain | client_id | Related parties of a client. Currently no data source: returns no_data. | relationship_analyst |

## 4. Output guard

Source: `agents/guard.py`. See the README for the tolerance and its limits.

1. A finding must cite at least one evidence id, and every id must exist in this run's evidence store.
2. Every cited result must have the report's own `as_of`.
3. Every number in the claim must match a number in the cited results (numeric leaves and numbers inside their strings). Ids (`CL-0001`, `SYN-EQ-0001`, `ev_...`), ISO dates and pseudonyms are ignored; `%`, `m`, `bn`, `k` and thousands separators are normalised; sign is ignored.
4. The summary is checked against all cited evidence.
A failing finding is removed and recorded as a `guard_removed` gap; the report status becomes at most `partial`.

## 5. Report status

`complete`: no gaps and no non-complete child report. `partial`: any gap (tool error, policy denial, guard removal, `no_data`, `insufficient_*` result) or a child that is not complete. `insufficient_data`: nothing exists at `as_of` (or entitlement denied, or every tool result was `insufficient_data`).

## 6. Policy, audit and privacy

Source: `policy/`, see [policy-checkpoints.md](policy-checkpoints.md). Ten checkpoints, mock engine allows all. The audit log is append-only and records every decision, tool call, model call and agent-to-agent call with the requester chain. Names are pseudonymised only in what is sent to a model; reports for the RM always show real names.

## 7. Agents and A2A

Source: `agents/`, `a2a/`, see [agents.md](agents.md). Relationship Analyst (the RM's view of one client and the client's portfolios) delegates to Portfolio Analyst, which delegates to Instrument Analyst. Each is also served over A2A with an Agent Card.
