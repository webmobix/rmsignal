# Tasks

## 1. Dependencies and datasource access

- [x] 1.1 Add `fastapi`, `uvicorn` (runtime) and `httpx` (dev) via `uv add`, and verify `uv run python -c "import fastapi, uvicorn"` and `uv run pytest` still pass
- [x] 1.2 Add generic `select`, `count` and `get_by_key` to `SqliteDataSource` with table/column whitelisting and typed filter values; verify new tests in `tests/test_datasource.py` cover filtering, paging, counts, composite keys, unknown table/column and a hostile name

## 2. API

- [x] 2.1 Create `rm_dashboard.api` with `create_app(db_path)`, per-request datasource dependency, and `GET /api/sources` catalogue; verify with `TestClient` that 12 tables with columns and counts are returned
- [x] 2.2 Add `GET /api/sources/{table}` with `limit`/`offset`, column filters, `total`, and 404/422 errors; verify tests for default page, explicit page, invalid paging, typed filters, unknown filter column and unknown table
- [x] 2.3 Add `GET /api/sources/{table}/{key:path}` for single and composite keys; verify tests for existing, composite, missing, keyless table and wrong segment count
- [x] 2.4 Verify typed JSON output (ISO dates, booleans, nulls, underscore date-suffix names) and that POST/PUT/PATCH/DELETE return 405, in `tests/test_api_sources.py`

## 3. Server command and docs

- [x] 3.1 Add `rm-dashboard-serve` (`--db`/`RM_DASHBOARD_DB`, `--host`, `--port`) and its `pyproject.toml` script entry; verify a missing database exits with a message mentioning `rm-dashboard-seed` (test) and that `/docs` loads
- [x] 3.2 Document the endpoints and how to run the server in `README.md`, and verify the documented `seed` + `serve` + `curl /api/sources` sequence works as written against the sample data
