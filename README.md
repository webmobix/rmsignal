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

### Tests

```sh
uv run pytest
```
