# Proposal

## Why

Generated artifacts (client reports, evidence, reconciliations, actions, overviews, outlooks, scenario results) exist only as JSON files under `reports/<as_of>/`, and the source data only in a local SQLite file. The demo runs on a server, where both must live in Firestore. File paths leak through about seven store classes, six runners, the API and the tool context, so there is no seam to swap the backend behind.

## What Changes

- Introduce a backend-agnostic **artifact store**: artifacts are addressed by `(as_of, kind, key)` and hold a JSON body. SQLite is the local backend, in its own `artifacts.db` file (not `rm.db`, which stays read-only).
- Re-point `OutlookStore`, `ScenarioStore`, `CatalogueStore`, the report/overview sources, all runners (batch, reconcile, mandate-reconcile, actions, overview, outlook, scenarios), the evidence/overview API code and the tool context onto the store. Their public methods keep their shapes; `reports_dir: Path` is replaced by a store handle.
- Persist evidence one record per tool result (plus a small per-subject index) and the audit trail one record per entry, so no stored record approaches Firestore's 1 MiB document limit (today `evidence/CL-0017.json` is ~960 KB, `audit.jsonl` 1.3 MB).
- Introduce a backend-agnostic **datasource** contract for the 12 source tables, with SQLite and Firestore implementations.
- Add a **Firestore** backend for source data and for artifacts. Artifacts are read-only there: the demo server reads, the runners still write locally. Writing artifacts from the runners to Firestore is deferred.
- Add a **loader** command: source CSV/JSON into SQLite or Firestore, and existing artifacts (a `reports/` folder or an `artifacts.db`) into SQLite or Firestore, so artifacts generated locally can be pushed to the demo server.
- Select backends by configuration (`RM_ARTIFACT_STORE`, `RM_DATA_SOURCE`); `google-cloud-firestore` is an optional extra.

## Capabilities

### New Capabilities
- `artifact-store`: backend-agnostic persistence and retrieval of generated artifacts, with SQLite as the local implementation.
- `firestore-backend`: Firestore implementations of the datasource and the read side of the artifact store.
- `store-loader`: command that loads source data and artifacts into a chosen backend.

### Modified Capabilities
- `sqlite-datasource`: the SQLite datasource becomes one implementation of a backend-agnostic datasource contract.
- `database-seeding`: seeding and loading share one validation, so both reject the same bad input the same way.

## Impact

- Code: `outlook/store.py`, `scenarios/store.py`, `scenarios/catalogue.py`, `reportsource.py`, `overview/source.py`, `runners/*`, `api/context.py`, `api/evidence.py`, `api/overview.py`, `api/sources.py`, `actions/agent.py`, `tools/spec.py` and the tool modules using `reports_dir`, `policy/audit.py`, `pit/polars_repo.py`, `data/seed.py`, `settings.py`; new store, Firestore and loader modules.
- CLI: new `rm-dashboard-load`; runners take a store setting instead of `--reports-dir` (the folder form stays accepted as a SQLite location for compatibility).
- Dependencies: optional `google-cloud-firestore` extra.
- Existing `reports/` folders are not read directly any more; they are imported once with the loader.
- Open changes `clarify-overview-summary` and `add-market-breadth` touch overview and outlook code and must be sequenced with this one.
