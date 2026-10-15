# Design

## Context

`SqliteDataSource` opens the database read-only and returns frozen dataclasses through per-entity methods; `schema.ENTITIES` already registers all 12 tables with their model, primary key and typed columns (`schema.columns`). The app currently has no web layer. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- One generic route set that covers all 12 tables, driven by `ENTITIES`, so new tables appear without new code.
- Reuse the datasource's typed decoding; no second SQL/type path to drift.

**Non-Goals:**
- Per-table response schemas in OpenAPI, auth, CORS, caching, sorting, range or fuzzy filters.

## Decisions

- **Generic access on the datasource.** Add `select(table, filters, limit, offset)`, `count(table, filters)` and `get_by_key(table, key_values)` to `SqliteDataSource`, built on the existing `_select`. Table and column names are validated against `ENTITIES`/`columns()` before being placed in SQL; values are always bound parameters. *Alternative:* calling the 20+ typed methods per table from the API — rejected, they lack paging/filtering and would need a mapping per table.
- **Filter values parsed with `schema.parse_text`** against the column type, then `to_storage`, so `pep_status=true`, ISO dates and numbers match what is stored. Bool accepts `true/false` (plus the dataset's Y/N). A parse failure is a 422.
- **Serialisation via `dataclasses.asdict` + FastAPI's `jsonable_encoder`**, giving ISO dates and native bools/nulls without custom code.
- **Routes in `rm_dashboard.api`** (`app.py` with an app factory `create_app(db_path)`, `routes/sources.py` with an `APIRouter(prefix="/api/sources")`). Path `/{table}/{key:path}` carries composite keys as `/`-joined segments in primary-key order; segment count must equal the key length or 404. *Alternative:* query params for composite keys — rejected, less uniform.
- **Connection per request** through a FastAPI dependency that opens/closes a `SqliteDataSource`; sqlite connections are not shareable across the threadpool, and opening a read-only connection is cheap. The DB path is held in `app.state`.
- **Unknown query params** are detected by comparing `request.query_params` to `{limit, offset} ∪ columns`; a column literally named `limit`/`offset` does not exist in the dataset.
- **Pagination:** default `limit` 100, maximum 1000, ordered by `rowid` (storage order, matching the datasource).
- **Server command:** `rm-dashboard-serve [--db PATH] [--host 127.0.0.1] [--port 8000]` runs uvicorn on the app; default host is loopback because the data is sensitive-looking and the API unauthenticated. `--db` falls back to `RM_DASHBOARD_DB`; existence is checked up front with the same error message the datasource gives.
- **Only GET routes are registered**, so FastAPI answers 405 for other methods.

## Risks / Trade-offs

- [Unauthenticated access to client data] → bind to loopback by default; document as debug-only.
- [SQL injection via table/column names] → whitelist from `ENTITIES`; values bound as parameters; covered by a test with hostile names.
- [Large tables via `limit`] → hard max of 1000.
- [Dependencies on `fastapi`/`uvicorn` pull the app out of "stdlib only"] → the seeder stays standard-library only; only the API package imports FastAPI.
