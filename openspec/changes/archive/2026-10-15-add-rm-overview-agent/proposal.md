# Proposal

## Why

With per-client actions available (`add-client-actions`), the RM still needs one view across all their clients: the top next actions as of a date, ranked, categorised and linked to clients and reports. This should not re-judge the clients; it should aggregate reliably.

## What Changes

- Add an **RM Overview** stage that reads all `actions/<client>.json` (and the client reports they link to) for a date and builds one overview per RM for the dashboard view.
- Ranking, grouping by category, coverage of clients without actions or reports, and link resolution are **done in code**. Order: importance, horizon, due date, client AUM descending, client id, title.
- An **optional single model call** writes a short summary and cross-client themes; it is guarded like other output (numbers must exist in linked actions) and its failure never blocks the overview.
- Persist `reports/<as_of>/overview/<rm_id>.json`; add a CLI (`rm-dashboard-overview --as-of DATE`).

## Capabilities

### New Capabilities
- `rm-overview`: the RM-level, date-based overview aggregating and ranking client actions with links to clients and reports.

### Modified Capabilities
<!-- None -->

## Impact

- New code: `overview` package (aggregation, ranking, coverage, optional summary guard), summary prompt and stub plan, CLI, docs, tests.
- Reads `actions/<client>.json`, report files for link checks, and `clients` (rm_id, name, AUM) through the point-in-time repository.
- Depends on `add-client-actions` (and indirectly `add-note-reconciliation`). Out of scope: HTTP/UI serving, desk-level rollups, re-ranking by a model.
