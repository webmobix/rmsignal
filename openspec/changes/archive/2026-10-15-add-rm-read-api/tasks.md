# Tasks

## 1. Foundation: reports location, as-of, RM profile

- [x] 1.1 Add `--reports` / `RM_DASHBOARD_REPORTS` (default `reports`) to `api/serve.py` and `create_app`, failing with a message naming the folder when it is missing; verify with a test that starts `create_app` on a missing folder and on `reports/`
- [x] 1.2 Add `AsOfIndex` (newest ISO-named run folder, no wall clock) and the `as_of` dependency (`latest` default, 404 listing available dates, 404 naming the batch commands when empty); verify with tests for default, explicit, unknown and empty folder
- [x] 1.3 Add `GET /api/as-of` and `GET /api/rm` (id, name, desk, booking centres from client data); verify `/api/rm` returns Priscilla Ong on the committed data
- [x] 1.4 Add the shared response conventions (`gaps`, `status: "placeholder"` field type, 405 on non-GET under `/api`) and verify with tests that POST/PUT/PATCH/DELETE answer 405 and `/docs` lists the new endpoints with schemas
- [x] 1.5 Document the API and its configuration in `docs/api.md` and the README; verify `tests/test_docs.py` (or an added check) passes and the documented `rm-dashboard-serve` command runs as written

## 2. Overview, meeting prep, evidence

- [x] 2.1 Add the `urgency` rule (importance + horizon + days-to-due term, documented table) as a pure function; verify unit tests for tier ordering, horizon bonus and the dated-versus-undated tie from the spec
- [x] 2.2 Implement `GET /api/overview`: persisted overview with `client_aum_usd`, wealth band and `urgency` per action and max urgency per client; verify against the committed run (33 actions, 20 clients, clients without actions with reasons)
- [x] 2.3 Add the `meeting_prep` block (14-day window: due or near-horizon actions, KYC due/overdue, latest RM note per client); verify with a test that an overdue KYC client appears marked overdue
- [x] 2.4 Implement `GET /api/evidence/{evidence_id}` returning the tool result plus the citing findings/actions, 404 for unknown ids; verify with the `CL-0001#f10` example and an unknown id
- [x] 2.5 Resolve source references into client, portfolio and finding ids on every overview action so the UI never parses `CL-0001/PF-0001#f8`; verify with a test on that reference
- [x] 2.6 Document the overview, urgency and evidence endpoints in `docs/api.md`; verify the examples match actual responses in a test

## 3. Clients and portfolios

- [x] 3.1 Implement `GET /api/clients` (list rows with AuM, portfolio count, action count, highest urgency, report status, KYC due); verify 20 rows including clients without actions
- [x] 3.2 Implement the consolidated block (total AuM and change vs previous snapshot, combined allocation, currency exposure, largest positions) reusing `analytics`; verify total equals the sum of portfolio AuMs for a multi-portfolio client and equals the portfolio for a single-portfolio client
- [x] 3.3 Add look-through exposure, liquidity (commitments, planned cash needs) and credit facilities with headroom to the consolidated block, emitting gaps where analytics lack the figure; verify a structured-product client shows look-through and a gap is emitted where data is missing
- [x] 3.4 Implement `GET /api/clients/{id}` with the `portfolios[]` list (mandate status `in_band` / `out_of_band` / `no_mandate`), actions, findings with evidence ids, and note-reconciliation results; verify the custody account is `no_mandate` yet counted in totals, and a contradicted note lists its evidence
- [x] 3.5 Implement `GET /api/clients/{id}/aum-history` (per portfolio and total across snapshots, plus events in range); verify five points per series for 2026-08-26
- [x] 3.6 Implement `GET /api/portfolios/{id}` (header, AuM history, mandate bands vs actual with out-of-band flag, holdings, single-position check, facility with LTV history and trigger); verify an out-of-band case and 404 for an unknown id
- [x] 3.7 Implement `GET /api/clients/{id}/snapshot-changes` (AuM, P&L, added/removed/resized positions, events between; 422 for invalid snapshots); verify 2026-02-27 to 2026-03-31 includes the Hormuz events and invalid input answers 422
- [x] 3.8 Document the client, portfolio and snapshot endpoints in `docs/api.md`; verify the documented examples against responses in a test

## 4. Instruments, market, events

- [x] 4.1 Implement `GET /api/instruments` (master fields, latest price and change, holder count, USD held, `has_outlook`); verify every instrument is listed, two have outlooks, and unheld ones have zero held USD
- [x] 4.2 Implement `GET /api/instruments/{id}` (master data with `underlying_reference`, price path, holders, outlook with context and evidence ids, `outlook_missing` gap, 404); verify a structured product, an outlooked instrument and an unknown id
- [x] 4.3 Implement `GET /api/market-outlook` from the persisted outlook; verify it matches `outlook/market.json` summary and views
- [x] 4.4 Implement `GET /api/events` with the explicit channel-keyword table producing `derived: true` reach (clients, instruments); verify an energy-channel event lists held tagged instruments and their clients
- [x] 4.5 Document the instrument, market and event endpoints, including the channel table, in `docs/api.md`; verify examples in a test

## 5. Scenarios (placeholder)

- [x] 5.1 Define the scenario response models in the final contract shape and the `ScenarioProvider` protocol; verify with a type-checked test that a stub provider satisfies it
- [x] 5.2 Implement `PlaceholderScenarioProvider` with fixed catalogue (de-escalation, deterioration, rates) mirroring real event-log entries, and `GET /api/scenarios` plus `GET /api/clients/{id}/scenarios` carrying `status: "placeholder"`; verify all contract fields are present, 404 for unknown clients, and that results are not derived from the client's holdings
- [x] 5.3 Verify provider replacement: inject a different provider in a test and confirm routes and models are unchanged
- [x] 5.4 Document the scenario contract and the placeholder rule in `docs/api.md`; verify the examples in a test

## 6. Integration

- [x] 6.1 Run the full suite and `rm-dashboard-serve` against `rm.db` and `reports/`, fetch every endpoint once, and verify no 5xx and that `/openapi.json` generates (this is what the UI change will consume for types)
- [x] 6.2 Confirm no endpoint writes to `rm.db` or `reports/` (file hashes unchanged after the integration run) and that `/api/sources` behaviour is unchanged
