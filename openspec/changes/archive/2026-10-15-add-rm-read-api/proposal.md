# Proposal

## Why

The analysis layer persists everything an RM needs (ranked actions, client reports with evidence, note reconciliation, market and instrument outlooks), but the only HTTP surface is `/api/sources`, which exposes raw tables. A dashboard would have to read JSON files and SQLite itself and re-implement the linking between action, finding, evidence, client, portfolio, instrument and market view. One read-only API, owned by the code that already knows the stable references, keeps the UI a plain client and keeps the Pydantic contracts the single source of shapes.

## What Changes

- Add read-only FastAPI endpoints under `/api`, beside `/api/sources`, keyed by `as_of` with `latest` resolving to the newest persisted run (today 2026-08-26):
  - `GET /api/as-of` (available dates, latest), `GET /api/rm` (profile for the avatar and masthead).
  - `GET /api/overview`: the persisted RM overview (ranked actions, categories, themes, clients without actions) plus a **meeting-prep** block (actions due or horizon-bound in the next 14 days, KYC reviews due, recent RM notes per client).
  - `GET /api/evidence/{evidence_id}`: one tool result with the findings that cite it, for the evidence drawer.
  - `GET /api/clients`, `GET /api/clients/{id}`: list rows (AuM, band, risk, action count, top importance, report status) and the detail with a **consolidated block across all of the client's portfolios** plus a `portfolios[]` list; findings, note reconciliation, credit facilities, liquidity (commitments, planned cash needs), look-through exposure.
  - `GET /api/clients/{id}/aum-history`, `GET /api/portfolios/{id}`: AuM over the five snapshots (per portfolio and total), mandate bands against actual weights, holdings, LTV history.
  - `GET /api/clients/{id}/snapshot-changes?from=&to=`: **snapshot comparison** (AuM, P&L and position changes between two snapshots, with the events in between).
  - `GET /api/instruments`, `GET /api/instruments/{id}`: master data, price path, holders, outlook where one exists.
  - `GET /api/market-outlook`, `GET /api/events`: market views and the event log with transmission channels.
  - `GET /api/scenarios`, `GET /api/clients/{id}/scenarios`: scenario catalogue and per-client results as **placeholders**, every payload carrying `status: "placeholder"`; names and metadata come from the backend. The contract mirrors the fields of the sample's scenario view so the real scenario agent can replace the producer without a contract change.
- Add `--reports` / `RM_DASHBOARD_REPORTS` to `rm-dashboard-serve` for the reports folder; fail with a clear message when it is missing.
- All responses are typed (Pydantic), reuse existing contracts where they exist, and never expose wall-clock time.

## Capabilities

### New Capabilities
- `read-api-core`: as-of resolution, RM profile, shared conventions (read-only, errors, gaps, placeholder flag), server configuration.
- `overview-api`: RM overview, meeting prep and evidence lookup.
- `client-portfolio-api`: client list and detail with consolidated view and portfolio list, AuM history, portfolio detail, snapshot comparison.
- `instrument-market-api`: instrument list and detail, market outlook, event log.
- `scenario-api`: scenario catalogue and per-client placeholder results.

### Modified Capabilities
<!-- None. `sources-debug-api` is unchanged; its server startup requirement is extended only through the new `read-api-core` options. -->

## Impact

- New code: `src/rm_dashboard/api/` routers and response models, an assembly module that combines `FolderReportSource`, `FolderOverviewSource`, the point-in-time repository and the persisted outlook files; tests against the committed `reports/2026-08-26` and `rm.db`.
- `api/app.py` and `api/serve.py` gain the reports option; CORS is not enabled (the UI uses a dev proxy).
- No change to agents, analytics, persisted file formats or the database.
- Out of scope: writes of any kind, authentication, running analyses from the API, real scenario computation (placeholder only), pagination beyond what the lists need, the UI (`add-rm-dashboard-ui` depends on this change).
