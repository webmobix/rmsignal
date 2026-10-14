# Tasks

## 1. Package and models

- [x] 1.1 Create `src/rm_dashboard/data/` with `__init__.py`, add a `tests/` dir and pytest as a dev dependency; verify `uv run pytest` collects with no errors
- [x] 1.2 Write `models.py` with the 12 frozen, slotted dataclasses (fields from the CSV headers and `rm_notes.json` keys, hyphens → underscores, nullable per Design) using `date`, `bool`, `int`, `float` per the Design type rules; add `tests/test_models.py` checking each model's fields against the real file headers, field types (every date column is `date`, the three flag columns are `bool`), nullability, and immutability, and verify it passes

## 2. Schema and datasource

- [x] 2.1 Write `schema.py`: file→table→model registry, DDL generated from the dataclasses (`date`→ISO TEXT, `bool`→INTEGER with 0/1 CHECK), a single text/storage codec per type, PKs and join-key indexes per Design; add tests that the schema applies to an in-memory DB with 12 tables whose columns equal the model fields, and verify it passes
- [x] 2.2 Write `datasource.py` (`SqliteDataSource`: read-only, context manager, `list_*`, `get_*`, `portfolios_for_client`, `holdings_for`); add tests against a small seeded fixture DB covering typed reads (dates and booleans round-trip as `date`/`bool`), `None` for NULL, unknown id, read-only write failure and missing-file error, and verify they pass

## 3. Seeder

- [x] 3.1 Write `seed.py` CLI (`--data-dir`, `--db`, `--replace`): CSV/JSON parsing with empty→NULL and strict number/date (`YYYY-MM-DD`)/flag (`Y`/`N`/`Yes`/`No`) parsing, header validation, single-transaction load, clear errors; verify with `tests/test_seed.py` on the real sample dataset asserting the row counts in the spec, NULL handling, and value preservation
- [x] 3.2 Add seeder failure-mode tests (missing file, wrong header, bad number, bad date, bad flag, re-seed refused, `--replace` no duplicates, failure leaves no partial data) using temp copies of the data, and verify they pass
- [x] 3.3 Register the `rm-dashboard-seed` console script in `pyproject.toml`; verify `uv run rm-dashboard-seed --data-dir sample/singhacks-jb-wealth-intelligence/data --db /tmp/rm.db` succeeds and `uv run python -m rm_dashboard.data.seed` gives the same result

## 4. Docs and integration

- [x] 4.1 Add a README section documenting the package, the 12 tables, the wide-column naming rule, and the seed command; verify the documented commands run as written
- [x] 4.2 End-to-end check: seed the sample data, open it with `SqliteDataSource`, and confirm a client → portfolios → holdings walk returns typed records; verify the full `uv run pytest` run passes
