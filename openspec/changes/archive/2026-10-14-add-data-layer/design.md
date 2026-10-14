# Design

## Context

The app is a fresh `uv_build` package (`rm_dashboard`, Python >=3.13, no dependencies). The dataset is: 11 CSVs plus `rm_notes.json` (28 notes). Observed in the data:

- Some columns are date-suffixed (`aum_2026-08-26`, `price_2025-12-31`, `drawn_2026-06-30`, ...), five snapshot dates; `credit_facilities.csv` has 25 such columns.
- Empty values exist: `clients.age` (1), `holdings.sector/avg_cost_local/cost_basis_base/unrealised_pnl_*` (5), `instruments.sector` (1) and `underlying_reference` (53), and most of `transactions.instrument_id/instrument_name/quantity/price_local` (non-trade rows).
- `holdings.valuation_date` sometimes differs from `snapshot_date`.
- All date columns are plain `YYYY-MM-DD` (no time-of-day or timestamp columns exist): `client_since`, `kyc_review_due`, `inception_date`, `snapshot_date`, `valuation_date`, `acquired_date`, `trade_date`, `settlement_date`, `due_from`, `due_to`, `event_date`, `note_date`.
- Flag columns use text codes: `pep_status` (`Yes`/`No`), `sustainability_excluded` and `concentration_limit_applies` (`Y`/`N`).
- `holdings.csv` has no obvious natural key beyond (snapshot, portfolio, instrument), unverified.
- `market_context.csv` has an undocumented `snapshot_label` column; `clients.csv` has undocumented `client_name`, `client_since`, `pep_status`, `reporting_language`. The CSV headers, not the data dictionary, are authoritative.

## Goals / Non-Goals

**Goals:**
- One table, one dataclass per file, 1:1 field/column naming.
- Seeder usable with nothing but the standard library and a CSV directory.
- Loading is faithful: no value cleaning, rounding or row dropping.

**Non-Goals:**
- No ORM, no migrations framework, no async access.
- No analytics or dashboard queries beyond simple typed reads.

## Decisions

1. **Package layout** `src/rm_dashboard/data/`: `models.py` (dataclasses), `schema.py` (table DDL + file→table/model registry), `datasource.py` (`SqliteDataSource`), `seed.py` (CLI). Alternative: single module; rejected, the seeder must be separable from the app-facing datasource.

2. **Dataclasses are frozen, with `slots=True`, and use real types, not strings:** `datetime.date` for date columns, `bool` for flag columns, `int`/`float` for numbers, `str` only for genuine text and identifiers; any of them `| None` where the source can be empty. No column in the dataset carries a time of day, so no `datetime` field is used (add one only if a future file needs it). Alternative: ISO strings throughout; rejected, it pushes parsing and invalid-value handling onto every consumer.

   Storage mapping in SQLite: `date` → TEXT in ISO `YYYY-MM-DD` (sorts and compares correctly, readable in any SQLite tool); `bool` → INTEGER 0/1 with `CHECK (col IN (0,1))`; `int` → INTEGER; `float` → REAL. Conversion lives in one place (a codec table keyed by field type, in `schema.py`) used by both the seeder (text → value → storage) and the datasource (storage → value). Source parsing: dates via `date.fromisoformat`; booleans accept exactly `Y`/`N` and `Yes`/`No`; anything else is an error. Which columns are `bool` is declared by the field's type in the dataclass, so a new flag column needs only a type annotation.

3. **Wide columns kept wide, hyphens become underscores** (`aum_2026-08-26` → `aum_2026_08_26`). This keeps "a table for each file" literal and the seeder trivial. Alternative: normalise to long tables (`portfolio_aum(portfolio_id, snapshot_date, aum)`); better for querying but is a modelling decision beyond this change, and can be a view/later change.

4. **Schema is derived from the dataclasses** (field type → `TEXT`/`INTEGER`/`REAL`, `| None` → nullable) plus a small hand-written per-table metadata (primary key, indexes on join keys from the data dictionary). One source of truth prevents model/table drift; a test asserts the two match.

5. **Keys:** natural primary keys where the id is unique (`client_id`, `portfolio_id`, `instrument_id`, `transaction_id`, `facility_id`, `commitment_id`, `need_id`, `note_id`; `(mandate_code, asset_class)`; `(snapshot_date, series_id)`). `holdings` and `event_log` declare no primary key (SQLite's implicit rowid is used, so table columns still equal the dataclass fields) and are indexed on their lookup columns. Foreign keys are *not* declared: the dataset has deliberate quality artefacts and a seeder that rejects them would violate "load faithfully". Join-key indexes are created instead.

6. **Empty CSV cells load as NULL**, for every typed column including text. Parsing is strict for every non-text type: a non-empty value that is not a valid number, `YYYY-MM-DD` date, or recognised flag code aborts the seed with the file, row and column.

7. **Seeder is standalone:** `python -m rm_dashboard.data.seed --data-dir DIR --db PATH [--replace]`, also exposed as console script `rm-dashboard-seed`. It imports only the package's `models`/`schema` (stdlib-only) and never starts or imports the app entry point. Default `--data-dir` is the sample dataset path relative to the repo; `--db` is required. Existing tables are an error unless `--replace`, which drops and recreates them. The whole load runs in one transaction, so a failure leaves the database untouched.

8. **Datasource API:** `SqliteDataSource(path)` with `list_<entity>()` returning dataclasses, `get_<entity>(id)` for id-keyed tables, and a few filters used by the documented joins (`portfolios_for_client`, `holdings_for(portfolio_id, snapshot_date)`). Read-only connection (`mode=ro` URI) so the app cannot mutate seeded data. Each call opens no global state; the datasource is a context manager.

## Risks / Trade-offs

- [Wide credit-facility table is awkward to query] → Accepted for now; normalised views can be added later without changing the stored tables.
- [Schema drift between CSV headers and dataclasses] → Seeder validates the CSV header against the dataclass fields and fails with a clear message; a test runs it against the real dataset.
- [A malformed date or flag in the data breaks the whole seed] → Intended (fail loudly with file/row/column); the real dataset is validated by a test, and the deliberate quality artefacts observed so far are blanks and out-of-sync `valuation_date`, not malformed values.
- [Holdings key assumption wrong] → No declared key, so no uniqueness is assumed.
- [Read-only connection fails on a missing DB] → `SqliteDataSource` raises a clear `FileNotFoundError` pointing to the seed command.

## Open Questions

- Whether to model currency codes or enumerated text (risk profile, liquidity tier) as enums later (safe to defer; they stay `str` now).
