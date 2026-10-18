# Proposal

## Why

On Google Cloud each stage (outlook, analyse, reconcile, mandate reconcile, actions, overview, scenarios) is deployed and run on its own, so there is no shared disk for a SQLite file and no step that could load one into Firestore afterwards. Runners must write their artifacts straight to Firestore, which is also where the API reads them.

## What Changes

- **BREAKING (behaviour):** the Firestore artifact store is writable for runners. Pointing a runner at `firestore:<project>` no longer fails at start-up; it saves reports, evidence, audit trails, run summaries and every other artifact kind there.
- The API keeps a read-only Firestore store: it still cannot save or delete artifacts.
- A date becomes visible to `dates()` as soon as a runner has written an artifact for it (the `runs` marker is set by the writing store, once per date), not only after `rm-dashboard-load`.
- `rm-dashboard-load artifacts` stays as the way to copy an existing SQLite store or reports folder into Firestore; `rm-dashboard-load source` stays the way to load the dataset.
- Deployment docs describe one Cloud Run job per runner, all on the same image and all using Firestore, with no SQLite.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `firestore-backend`: "Firestore artifact store refuses writes" becomes "accepts writes from runners, refuses them when opened read-only"; date markers are maintained by writes.

## Impact

- `src/rm_dashboard/store/firestore.py`, `store/factory.py` (`open_store(..., writable=)`), `runners/stage.py`.
- `tests/test_firestore.py`; README, `docs/architecture.md`, `docs/deploy-cloud-run.md`.
- Audit entries are saved one document per entry, so a run makes many small Firestore writes; slower than SQLite, within quota.
- Cloud Run service account needs `roles/datastore.user` (already required for reading).
