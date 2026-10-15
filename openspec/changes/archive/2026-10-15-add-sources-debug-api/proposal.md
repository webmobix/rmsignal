# Proposal

## Why

The 12 dataset tables are only reachable through Python or raw SQLite, so checking what was seeded (row counts, odd values, the deliberate data-quality artefacts) means opening a shell. A small HTTP API over the tables makes the data inspectable from a browser or `curl`, and starts the FastAPI server the dashboard will need anyway.

## What Changes

- Add a FastAPI application, started with a new `rm-dashboard-serve` command, backed by the existing read-only datasource.
- Expose debug endpoints under `/api/sources/...`:
  - `GET /api/sources` lists every table with its columns and row count.
  - `GET /api/sources/{table}` returns rows, paginated (`limit`, `offset`), optionally filtered by exact match on any column.
  - `GET /api/sources/{table}/{key}` returns one row by primary key (composite keys are addressed with repeated path segments or query params per design).
- Return values in their typed JSON form (dates as ISO strings, flags as booleans, empty cells as `null`).
- Unknown tables, unknown filter columns and missing rows return 404/422 with a clear message.
- Add `fastapi` and `uvicorn` as runtime dependencies and `httpx` as a dev dependency (for `TestClient`).

## Capabilities

### New Capabilities
- `sources-debug-api`: read-only HTTP endpoints under `/api/sources` for listing, paging, filtering and fetching rows of every dataset table.

### Modified Capabilities
<!-- None: the existing datasource requirements are unchanged; the API is additive. -->

## Impact

- New package `rm_dashboard.api` and a `rm-dashboard-serve` script entry in `pyproject.toml`.
- `rm_dashboard.data.datasource` gains generic table access (list by table name with filter, count, get by key) used by the API; existing methods keep their behavior.
- New dependencies: `fastapi`, `uvicorn` (runtime); `httpx` (dev).
- Database path is configured via `--db` / `RM_DASHBOARD_DB`; no schema change.
- Out of scope: writes, authentication, the dashboard UI, and non-debug business endpoints. The API is meant for local debugging only.
