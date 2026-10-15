# rm-dashboard

## Data layer (`rm_dashboard.data`)

Typed access to the SingHacks Julius Baer wealth intelligence dataset
(`sample/singhacks-jb-wealth-intelligence/data/`).

| Module | Purpose |
|---|---|
| `models` | One frozen dataclass per file |
| `schema` | SQLite tables derived from the dataclasses, plus value codecs |
| `datasource` | `SqliteDataSource`: read-only, returns the dataclasses |
| `seed` | Standalone seeder (standard library only; not called by the app) |

### Tables

`clients`, `portfolios`, `holdings`, `instruments`, `mandates`, `transactions`,
`credit_facilities`, `commitments`, `planned_cash_needs`, `market_context`,
`event_log`, `rm_notes`. Each has the same columns as its source file.

- Columns with a date suffix keep one column per snapshot, with hyphens replaced by
  underscores: `aum_2026-08-26` is `aum_2026_08_26`.
- Types: dates are `datetime.date` (stored as ISO text), flags (`pep_status`,
  `sustainability_excluded`, `concentration_limit_applies`) are `bool` (stored as 0/1),
  numbers are `int`/`float`. Empty source cells are `None`/NULL.
- No foreign keys are declared; the dataset contains deliberate data-quality artefacts
  and is loaded as given.

### Seed a database

```sh
uv run rm-dashboard-seed --db rm.db          # defaults to the sample data directory
uv run python -m rm_dashboard.data.seed --db rm.db --data-dir path/to/data --replace
```

The seeder refuses to run on a database that already has the tables unless `--replace`
is given. The load is one transaction; any invalid file leaves the database untouched.

### Read it

```python
from datetime import date
from rm_dashboard.data.datasource import SqliteDataSource

with SqliteDataSource("rm.db") as ds:
    for p in ds.portfolios_for_client("CL-0001"):
        print(p.portfolio_name, len(ds.holdings_for(p.portfolio_id, date(2026, 8, 26))))
```

## Debug API (`rm_dashboard.api`)

A read-only FastAPI app for inspecting the seeded tables. It is unauthenticated and
binds to `127.0.0.1` by default; use it for local debugging only.

```sh
uv run rm-dashboard-seed --db rm.db
uv run rm-dashboard-serve --db rm.db        # or set RM_DASHBOARD_DB; --host, --port
curl localhost:8000/api/sources
```

| Endpoint | Returns |
|---|---|
| `GET /api/sources` | every table with columns, primary key and row count |
| `GET /api/sources/{table}` | `{total, limit, offset, rows}`; `limit` (1-1000, default 100), `offset` |
| `GET /api/sources/{table}/{key}` | one row by primary key; composite keys as `a/b` in key-column order |

Any column name works as an exact-match filter, e.g.
`/api/sources/portfolios?client_id=CL-0001` or `/api/sources/clients?pep_status=true`
(`total` counts the filtered rows). Unknown tables answer 404, unknown filter columns or
bad values 422. `holdings` and `event_log` have no primary key, so only list them.

### Interactive docs

Open <http://127.0.0.1:8000/docs> for a Swagger UI where every endpoint can be tried
out; the raw schema is at `/openapi.json`. The Swagger assets are bundled in
`src/rm_dashboard/api/static/swagger/` (swagger-ui-dist 5.17.14), so the page works
offline and inside IDE-embedded browsers. If it still looks blank, check that
`/static/swagger/swagger-ui-bundle.js` loads (browser dev tools, Network tab) and that
you are using the same host and port the server printed on startup.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `error: database not found ... rm-dashboard-seed` | run the seed command first, or fix `--db` |
| `no database given` | pass `--db rm.db` or set `RM_DASHBOARD_DB` |
| `address already in use` | choose another `--port` |
| `422` on a list request | unknown filter column, bad value, or `limit` outside 1-1000 |

### Tests

```sh
uv run pytest
```
