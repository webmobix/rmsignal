# Design

## Context

Persisted output lives in `reports/<as_of>/` (client reports, `evidence/`, `actions/`, `overview/<rm>.json`, `reconciliation/`, `outlook/market.json`, `outlook/instruments/`). Structured data lives in `rm.db`. `FolderReportSource` and `FolderOverviewSource` already read the former; `SqliteDataSource` and the point-in-time repository read the latter. The API only has `/api/sources`.

## Decisions

**Thin routers, one assembly layer.** Routers in `api/` do parsing and error mapping only. A new `api/assemble/` package builds the response models (consolidated client, portfolio detail, snapshot changes, meeting prep) from the existing sources. No SQL in routers; no new persisted formats.

**Reuse contracts, add view models.** `Overview`, `Report`, `ToolResult` and the outlook models are returned as they are persisted. New view models (client row, consolidated block, portfolio detail, instrument row) live next to the routers. The UI generates its TypeScript types from `/openapi.json`, so Pydantic stays the one source of shapes.

**`latest` is "newest folder with a run".** A small `AsOfIndex` scans the reports folder for ISO-named directories on each request (cheap: a handful of directories). It never reads the clock. All data reads go through the point-in-time repository with an explicit `as_of`, which keeps the API consistent with the analysis layer's reproducibility rule.

**Computation stays deterministic and shared.** Consolidation, look-through and mandate bands reuse `analytics` functions (weights, look-through concentration, mandate drift, liquidity, LTV). The API does not add new financial logic beyond summing, differencing and joining; where a figure is not available from analytics or a report it appears as a gap.

**Urgency.** `urgency` is a number in [0, 100] from a fixed table: importance (critical 76, high 52, medium 28, low 4) plus horizon (immediate +18, within_30_days +13, within_90_days +8, later or none +0) with a within-tier term of 0 to 4 from days to the due date. Tiers are 24 apart and the additions total at most 22, so a higher tier always scores higher. It exists only to spread the matrix's y-axis, because the data has only `high` and `medium`. The rule is documented and tested; it does not reorder the overview (that ranking is the persisted one).

**Event reach is derived and labelled.** `primary_transmission` is free text. The API maps channel keywords to instrument attributes (sector, asset class, region) with a small explicit table and marks the result `derived: true`. It is a linking aid, not analysis.

**Snapshot comparison.** Compares holdings by `(portfolio_id, instrument_id)` between two snapshot dates; added, removed, resized, and value change split into price and quantity effects only where the stored data supports it, otherwise total change.

**Scenarios behind a provider.** `ScenarioProvider` is a Protocol with `catalogue()` and `for_client(client_id, as_of)`. The only implementation, `PlaceholderScenarioProvider`, returns fixed data in the final contract shape. Names, premises, mirrors and caveats come from here, so the UI holds no scenario text. Mirrors reference real event-log entries so the placeholders are plausible, but their numbers are not derived from holdings, and every payload says so.

**No CORS.** The UI runs behind a Vite proxy in development and the same origin in deployment; enabling CORS would widen the surface for no benefit.

## Risks and trade-offs

- Reports exist for only some stages (3 clients have action files, 2 instruments have outlooks). Mitigation: gaps as data, covered by tests on the committed run.
- Re-scanning the reports folder per request is simple but not free; acceptable for 20 clients, and a cache keyed on directory mtime can be added without contract change.
- Event reach by keyword is coarse; it is labelled `derived` so the UI can say so.

## Open questions

- Whether `urgency` should live in the persisted overview instead (would need a change to the overview builder); kept in the API for now to avoid touching the analysis layer.
