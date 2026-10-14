# Proposal

## Why

The dashboard has no data layer yet. The SingHacks Julius Baer dataset (12 files in `sample/singhacks-jb-wealth-intelligence/data/`) is the source of truth for the RM dashboard, but it exists only as loose CSV/JSON files. The app needs typed records and a queryable store before any dashboard feature can be built.

## What Changes

- Add a new package `rm_dashboard.data` inside the Python app (`src/rm_dashboard/`).
- Add one dataclass per source file: `Client`, `Portfolio`, `Holding`, `Instrument`, `Mandate`, `Transaction`, `CreditFacility`, `Commitment`, `PlannedCashNeed`, `MarketContext`, `Event`, `RMNote`.
- Use real types in the dataclasses: `date` for dates, `bool` for flags (`pep_status`, `sustainability_excluded`, `concentration_limit_applies`), `int`/`float` for numbers.
- Add a SQLite datasource with one table per file, a schema that mirrors the dataclasses, and read access that returns the dataclasses.
- Add a standalone seed script that loads the CSV files and `rm_notes.json` into a SQLite database. It is run on its own and is not called by the app.
- No new third-party dependencies (stdlib `dataclasses`, `sqlite3`, `csv`, `json` only).

## Capabilities

### New Capabilities
- `data-models`: typed dataclass records for each of the 12 dataset files, with proper date, boolean and numeric types, nullable fields, and column naming for date-suffixed columns.
- `sqlite-datasource`: a SQLite-backed datasource exposing one table per dataset file and returning the typed records.
- `database-seeding`: a standalone command that creates the schema and loads the dataset files into a SQLite database.

### Modified Capabilities
<!-- None: no existing specs. -->

## Impact

- New code under `src/rm_dashboard/data/`, new tests under `tests/`, a console script entry in `pyproject.toml`, and a short README section.
- No change to the existing `main()` entry point.
- Out of scope: derived analytics (LTV, drift, scenario), any UI, normalising the wide date-suffixed columns into long form, and fixing the dataset's deliberate data-quality artefacts (they are loaded as-is).
