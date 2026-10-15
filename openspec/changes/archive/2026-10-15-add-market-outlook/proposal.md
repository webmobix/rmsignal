# Proposal

## Why

The analysts describe what has happened; nothing says where markets are heading or why. The bank needs one house view of the market, independent of any client or portfolio, built from the market history and the event log (the MVP's news), that can feed every analysis. The view must change when new data arrives, keep the older view as a reference and explain what changed and why.

## What Changes

- Add an **outlook analyst** (one agent, one prompt) with a **market** subject. It produces one market outlook per `as_of`: a view per market segment (equity indices, rates, FX, commodities, volatility, plus an overall view) with direction (`positive`, `neutral`, `negative`), horizon, confidence, cited drivers, cited risks and "what would change this view". No numeric forecasts.
- Add deterministic tools: `market.history` (market series across all snapshots up to `as_of`), `analytics.market_trend` (level, change versus previous snapshot and versus first snapshot per series), `outlook.previous_market` (the latest earlier market outlook, reference only).
- **Versioning by data, not by clock.** The new outlook records the data it used (effective market snapshot date, latest event date, event count). If nothing new exists since the previous outlook, it is carried forward without a model call. Otherwise a new outlook is generated; each view states `new`, `unchanged`, `upgraded` or `downgraded` against the previous outlook and why, citing only evidence that is new since the previous `as_of`. Earlier outlooks stay on disk as references.
- Code decides what a view may rest on (output guard): every driver and risk cites evidence produced in this run; numbers must exist in the cited evidence; a change in direction without new evidence is reverted; High and Severe events in the window that no view cites are listed.
- Persist `reports/<as_of>/outlook/market.json` (+ evidence, `summary.json`, `audit.jsonl`); CLI `rm-dashboard-outlook --as-of DATE`.

## Capabilities

### New Capabilities
- `market-outlook`: the dated, versioned, evidence-bound house view of the market and how it changed since the previous one.

### Modified Capabilities
<!-- None -->

## Impact

- New code: `outlook` package (contracts, previous-outlook source, data fingerprint, guard, runner), outlook analyst prompt and stub plan, three tools and allow-list, settings role `outlook_analyst`, CLI entry point, docs, tests.
- Reads the market and event datasets through the point-in-time repository; writes only under `reports/<as_of>/outlook/`.
- Depends on `treat-events-as-news`. Followed by `add-instrument-outlook` and `use-outlook-in-analysis`.
- Out of scope: instrument outlooks, using the outlook in client analysis, an external news feed, numeric price targets, scoring past outlooks against later data, A2A exposure of the new agent.
