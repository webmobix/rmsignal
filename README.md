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

## Analysis layer

Evidence-based relationship, portfolio and instrument analysis for a chosen date. Every number comes
from a deterministic tool, every finding cites evidence ids, and every run is reproducible for its `as_of`.

| Package | Purpose | Docs |
|---|---|---|
| `pit` | point-in-time repository over the SQLite mirror (`as_of` mandatory, no wall clock) | [docs/point-in-time.md](docs/point-in-time.md) |
| `domain` | entities, `ToolResult` evidence envelope, `Report` | [docs/contracts.md](docs/contracts.md) |
| `analytics` | pure Polars calculations (weights, look-through concentration, mandate drift, liquidity, LTV, P&L decomposition) | [docs/analytics.md](docs/analytics.md) |
| `tools` | the only data and calculation surface agents have, with per-agent allow-lists | |
| `policy` | `PolicyEngine` interface (mock), ten checkpoints, audit log, PII pseudonymisation | [docs/policy-checkpoints.md](docs/policy-checkpoints.md) |
| `agents` | Relationship -> Portfolio -> Instrument analysts (Deep Agents), output guard, interactive sessions | [docs/agents.md](docs/agents.md) |
| `a2a` | Agent Cards and servers for each analyst, client, mock KYC peer | |
| `runners` | batch CLI | [docs/methods.md](docs/methods.md) (all methods) |

### Run a batch

```sh
uv run rm-dashboard-seed --db rm.db
uv run rm-dashboard-analyse --as-of 2026-08-26 --db rm.db --out reports
uv run rm-dashboard-analyse --as-of 2026-03-31 --db rm.db --clients CL-0001,CL-0017
```

Writes `reports/<as-of>/<client>.json` (one `Report` per client), `evidence/<client>.json` (every tool
result behind it), `audit.jsonl` and `summary.json` with status counts. A run always delivers a report:
`complete`, `partial` (gaps listed) or `insufficient_data` (nothing at that date). `--as-of` is required;
`--db` can be replaced by `RM_DASHBOARD_DB`.

### Reading the reports

- **"Relationship" means the RM and the client.** The Relationship Analyst looks at one client as the RM
  sees them: profile, KYC, concentration across all portfolios, liquidity needs, credit, notes. The dataset
  has no persons, beneficial owners or related parties, so every report lists that as a gap and the
  status is `partial`. That is deliberate: the report says what it could not see rather than guessing who
  else is involved in a portfolio. When such a source is added, only its tool needs to be filled in.
- **Names:** pseudonyms exist only in what is sent to a model. Reports, the JSON files and the RM's view
  always show real names.
- **Needs without a knowledge date** (planned cash needs, commitments) are assumed known since the start
  of the client relationship and are never dropped, so advice always accounts for them.

### Output guard

Agents never calculate. Their findings are checked in code (`agents/guard.py`) before they reach a report:

- each finding must cite evidence ids that were produced in this run, at the report's own `as_of`;
- each number in a claim must equal a number in the cited tool results, within a **relative tolerance of
  0.5%** or the rounding implied by how it is written (`43%` matches 42.613; `42.9%` does not; `1.2m`
  matches 1,234,567);
- ids, dates and pseudonyms are not treated as numbers; `%`, `m`, `bn`, `k` and thousands separators
  are normalised; sign is ignored.

A finding that fails is removed and listed as a `guard_removed` gap, and the status drops to `partial`.
Limits: the check proves a number *exists* in the cited evidence, not that it is the right one. In a
large payload with integer rounding, a wrong figure that happens to be within tolerance of some value
passes (99.99 matches a total of 100). Cite narrow evidence and prefer the tools' own figures; stricter
matching (field-level citations) is the next step.

All methods are listed in [docs/methods.md](docs/methods.md).

### Models

By default the deterministic `stub` model runs the whole pipeline without a provider. For a real model
point the gateway at any OpenAI-compatible endpoint:

```sh
export RM_MODEL_NAME=<model> RM_GATEWAY_URL=https://gateway.example/v1 RM_GATEWAY_API_KEY=...
uv run rm-dashboard-analyse --as-of 2026-08-26 --db rm.db --clients CL-0001
```

| Variable | Default | Meaning |
|---|---|---|
| `RM_DASHBOARD_DB` | none | seeded database |
| `RM_MODEL_NAME` | `stub` | gateway model name; `stub` = deterministic test model |
| `RM_GATEWAY_URL` / `RM_GATEWAY_API_KEY` | `http://localhost:4000/v1` / `not-set` | OpenAI-compatible endpoint |
| `RM_HORIZON_DAYS` | `365` | liquidity look-ahead horizon |
| `RM_MAX_CONCURRENCY` | `4` | clients analysed in parallel |

Policy decisions come from a mock engine that allows everything and says so in every report.
The KYC peer is an in-process mock agent.

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
