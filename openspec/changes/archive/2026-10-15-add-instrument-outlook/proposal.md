# Proposal

## Why

Instrument analysis is done per client, through the portfolio analyst, so the same instrument is analysed again for every portfolio and client that holds it, and none of it says where the instrument is heading. The bank wants one view per instrument and date, set in the context of its industry, region and the market at that point in time, using price history and the event log, and independent of clients and portfolios. It is analysed once and reused everywhere.

## What Changes

- Extend the **outlook analyst** (from `add-market-outlook`) with an **instrument** subject. For each instrument held anywhere at `as_of` it produces an **instrument outlook**: what it is (asset class, sector, region, liquidity tier), its price path across snapshots, the events that bear on it, how it sits in the market outlook of the same date, and a view (direction, horizon, confidence, cited drivers and risks, what would change it).
- Add deterministic tools: `instruments.context` (reference data plus peers: instruments in the same sector or asset class and region with their price change over the same snapshots), `events.relevant` (candidate events for the instrument with the reason each matched: region, sector, asset class, underlying or name), `outlook.market` (the market outlook for the same `as_of`, carrying its evidence), `outlook.previous_instrument` (reference only). `analytics.risk` is reused.
- **Same versioning rule as the market outlook**: an instrument outlook is regenerated only when its inputs changed (latest price snapshot, set of relevant events, market outlook). Otherwise it is carried forward. Changes versus the previous outlook are stated with a reason citing new evidence.
- Add an **instrument stage** to `rm-dashboard-outlook`: market outlook first, then the union of held instruments in parallel, one file per instrument. Re-running is idempotent.
- Same output guard family as the market outlook (cited evidence, grounded numbers, derived change kind, confidence caps, reverted unsupported changes).

## Capabilities

### New Capabilities
- `instrument-outlook`: a dated, versioned, evidence-bound outlook per instrument in the context of its sector, region and the market, computed once and shared.

### Modified Capabilities
<!-- None -->

## Impact

- New code: instrument subject on the outlook analyst (prompt, stub plan, subject pattern), four tools and allow-list entries, instrument guard rules, held-instrument discovery, parallel stage, CLI option `--instruments`, docs, tests.
- Writes `reports/<as_of>/outlook/instruments/<instrument_id>.json` and `evidence/instruments/<instrument_id>.json`; reads the market outlook file and the point-in-time repository.
- Depends on `add-market-outlook`. Followed by `use-outlook-in-analysis`.
- Out of scope: using these outlooks in client analysis, removing the existing `instrument_analyst` role (it stays for interactive and A2A use), numeric price targets, issuer or credit research beyond the data, an external news feed.
