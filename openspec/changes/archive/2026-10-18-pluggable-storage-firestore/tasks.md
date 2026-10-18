# Tasks

## 1. Artifact store seam (SQLite)

- [x] 1.1 Define the `ArtifactStore` Protocol, address types, kind enum and a shared "typed read, unparseable counts as absent" helper in a new `store` package; verify with unit tests on the helper and import of the package.
- [x] 1.2 Implement `SqliteArtifactStore` (single table, transactional `put`/`put_many`, prefix `keys`, `dates`, `delete_prefix`, created on first write) and a parametrised contract test suite; verify the suite passes for SQLite, covering replace, missing, ordering, dates and interrupted save.
- [x] 1.3 Add evidence split support (per-result records, per-subject index, lookup by id) and the audit sink (per-entry records); verify with tests for order, shared results, a >1 MiB subject and append-only audit.
- [x] 1.4 Add `Settings.artifact_store`, `RM_ARTIFACT_STORE` and a store factory with `sqlite:` parsing, the `--reports-dir` compatibility form and the unknown-backend error; verify with settings tests.

## 2. Re-point readers and writers

- [x] 2.1 Re-point `OutlookStore`, `CatalogueStore` and `ScenarioStore` onto the store, keeping method signatures; verify the existing outlook and scenario tests pass unchanged.
- [x] 2.2 Re-point `FolderReportSource`/`FolderOverviewSource` (rename to store-based sources) and `actions/agent.py`, `AsOfIndex`, `api/evidence.py`, `api/overview.py` and `api/context.py`; verify the existing API tests pass and `find_result` no longer scans.
- [x] 2.3 Replace `ToolContext.reports_dir` with a store handle and update the outlook, scenario and overview tools and agents; verify the tool and agent tests pass.
- [x] 2.4 Convert runners (batch, reconcile, mandate-reconcile, actions, overview, outlook, scenarios) and `AuditLog` to the store, including summaries and force/replace behaviour; verify the runner tests pass and a run writes no per-artifact files beside the store.
- [x] 2.5 Add a check that `src/` has no remaining `write_text`/`read_text`/`iterdir`/`glob` on report paths (a grep-based test) and update README and docs for the new settings; verify the test and a documented local run end to end with the stub model.

## 3. Datasource contract

- [x] 3.1 Extract a `DataSource` Protocol (12 typed list/look-up reads plus select, count, get_by_key) and make `SqliteDataSource`, `PolarsPitRepository` and `api/sources.py` depend on it; verify existing data, PIT and sources-API tests pass and add a contract suite parametrised over datasources.
- [x] 3.2 Add `Settings.data_source`/`RM_DATA_SOURCE` and a factory used by `open_registry`, `ReadContext.build` and `serve`; verify with settings tests and an API start-up test on SQLite.

## 4. Loader

- [x] 4.1 Extract backend-neutral parsing and validation from `data/seed.py` returning typed records per table, keeping seed behaviour byte-for-byte; verify the existing seeding tests pass and a test shows seed and loader emit identical errors.
- [x] 4.2 Implement `rm-dashboard-load source` for SQLite targets (refuse existing, `--replace`, all-or-nothing); verify it reproduces the seed command's database and covers re-run and failure-leaves-nothing.
- [x] 4.3 Implement `rm-dashboard-load artifacts` for SQLite and `reports/`-folder sources to a SQLite target, re-chunking evidence and audit, with date selection and idempotency; verify by importing the repository's `reports/` folder and comparing reads through the facades with the folder-based originals.

## 5. Firestore backend

- [x] 5.1 Add the optional `firestore` extra, lazy import and the "not installed" error; verify with a test that runs without the library and a documented install command.
- [x] 5.2 Implement the Firestore codec (including `_seq` and keyless-table ids) and `FirestoreDataSource`; verify with the datasource contract suite against the in-memory Firestore fake, including holdings count and composite-key mandates.
- [x] 5.3 Implement `FirestoreArtifactStore` (read, keys, dates via `runs` markers, id encoding, read-only refusal naming the loader); verify with the artifact contract suite against the fake and a test that runners fail before any model call.
- [x] 5.4 Extend the loader with Firestore targets (batching, deterministic ids, `runs` markers, `--replace`, completion hint on failure); verify parity tests (SQLite vs Firestore fake) for source data and artifacts, and run once against the emulator if available.
- [x] 5.5 Document the demo flow in the README (generate locally, `rm-dashboard-load source` and `artifacts` to Firestore, start the server with Firestore settings) and verify by following it against the emulator or fake end to end with the read API returning the same overview as the SQLite setup.
