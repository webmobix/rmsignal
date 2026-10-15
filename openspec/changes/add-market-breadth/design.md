# Design

## Context

The market outlook (`outlook_analyst`, market subject) has `market.history`, `analytics.market_trend`, `events.list`, `news.list` and `outlook.previous_market`. Instrument outlooks are conditioned on the market outlook (`outlook.market`). The instrument master has 62 instruments with a price at each of the five snapshots, the same dates as the market snapshots. See proposal.md.

## Goals / Non-Goals

**Goals:** let instrument-level facts inform the market view without a dependency cycle; keep the market outlook client-independent, reproducible and versioned by data.
**Non-Goals:** using instrument views, weighting by holdings, new market segments, iteration to a fixed point.

## Decisions

1. **The flow rule: facts up, opinions down.** The market outlook may read anything computed from data (prices, events, breadth). It may not read anything an agent concluded about instruments. Instrument outlooks read the market outlook. This makes the dependency graph a tree (data -> market outlook -> instrument outlooks -> client analysis). *Alternatives:* (a) instrument outlooks feed the market outlook: rejected, circular and double-counted; (b) iterate both until stable: rejected, not reproducible, several times the model cost, no guarantee of convergence; (c) do nothing: leaves the gap.

2. **Universe = the instrument master, not holdings.** Using held instruments would make the market view depend on what clients own and break its independence from clients. The master (62 instruments) is the universe; instruments without a price at `as_of` are excluded and counted.

3. **`analytics.breadth` (deterministic, `analytics/breadth.py`).** Input: prices per instrument across snapshots up to the effective one, plus asset class and sector. Output per group (every asset class; every sector within `Equity`): `n`, `n_up_vs_previous`, `share_up_vs_previous_pct`, `median_change_vs_previous_pct`, `min`/`max`, the same against the first snapshot, `small: n < 3`. An instrument is "up" if its price is strictly higher; unchanged prices count as neither up nor down (cash stays flat and is reported as such). Method string registered like the other analytics (and documented in `docs/analytics.md`, `docs/methods.md`). Status `insufficient_history` with fewer than 2 snapshots, `insufficient_data` with no prices.

4. **Agent wiring.** The tool is added to the market allow-list only. The prompt gains one rule: breadth tells whether a move is broad or narrow and where it is led; cite it; a small group is weak evidence. No instrument tool is added, and a test asserts the market allow-list contains no tool that reads outlooks of instruments.

5. **Guard.** Breadth figures go through the existing number check against the cited result. For "newer than the previous outlook", `analytics.breadth` counts when its latest snapshot is later than the previous outlook's market snapshot (same helper as the trend). The `low` confidence cap applies when the trend or the breadth result is `insufficient_history`.

6. **Versioning unchanged.** Breadth rests on the same snapshots as the market series, so `OutlookInputs` (market snapshot date, latest event date, event count) already covers it. A task verifies that the instrument price snapshots equal the market snapshots; if a dataset ever differs, the instrument price snapshot date is added to the inputs, which regenerates the outlook when prices alone change.

## Risks / Trade-offs

- [The model over-reads a small group] → groups under 3 are marked `small`; the prompt says so; confidence caps remain.
- [Breadth duplicates the index trend] → it adds the distribution (share up, median, dispersion) the index hides, which is the point; the model must cite both if it makes a claim about narrowness.
- [Someone later adds an instrument-outlook tool to the market agent] → the allow-list test fails.
- [Five snapshots are few] → `insufficient_history` and the `low` cap behave as for the trend.
