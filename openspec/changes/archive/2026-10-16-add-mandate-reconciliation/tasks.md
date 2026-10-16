# Tasks

## 1. Exclusion breach calculation and tool

- [x] 1.1 Add `exclusion_breaches` in `src/rm_dashboard/analytics/` (bound mandates from `mandate_notes`, direct holdings and structured-product look-through, base-currency weights, custody not applicable); verify with unit tests for a direct holding, a flag in an unbound mandate (no breach), a look-through hit, custody and weights of the portfolio total
- [x] 1.2 Register the tool `analytics.exclusion_breaches`, add it to the Portfolio Analyst allow-list and require it in the prompt for managed portfolios; verify with a tool test that the result carries an evidence id and with a scripted-model agent test that the tool is called
- [x] 1.3 Check against the seeded data at 2026-08-26 that PF-0007 returns Global Energy Majors Equity Fund and Sunrise Palm Resources and that no other portfolio does; verify with a test over all portfolios
- [x] 1.4 Add the `mandate_drift`-category condition for an exclusion breach to the rubric (at least high) and document the calculation in `docs/methods.md`; verify with a rubric test and that the method text appears in the docs

## 2. Mandate-reconciliation stage

- [x] 2.1 Add the `mandate_reconciliation` package with contracts (result per breach, `ambiguous_notes`, gaps, status, policy decisions) mirroring `reconciliation/contracts.py`; verify with contract tests for allowed statuses and frozen models
- [x] 2.2 Build breach subjects from persisted evidence (`analytics.mandate_drift`, `analytics.exclusion_breaches`), excluding custody and flagging a missing check as a gap; verify with tests for a band, a position and an exclusion breach, a custody portfolio and a missing check
- [x] 2.3 Add the agent: no model call without breaches or notes, one call per client otherwise, prompt that states the four statuses, precedence and that a waiver is a claim; verify with scripted-model tests for no notes, notes about other topics and a model failure (`partial`, all `no_note`)
- [x] 2.4 Add the guard (evidence id is the breach's own, notes exist and are dated on or before `as_of`, numbers checked, multi-portfolio attribution to `ambiguous_notes`); verify with tests for unsupported status, later-dated note, invented figure and two portfolios with one note
- [x] 2.5 Run the stage on seeded data with a scripted model for N-008 (PF-0007), N-010 (PF-0009), N-013 (PF-0011) and N-024 (PF-0022) and check the expected statuses and that the waiver is quoted and the breach unchanged; verify with an integration test
- [x] 2.6 Add the runner `rm-dashboard-mandate-reconcile` (arguments as `rm-dashboard-reconcile`, writes `mandate-reconciliation/<client>.json`, `summary.json`, `audit.jsonl`) and the script entry in `pyproject.toml`; verify with a runner test and that `--help` works
- [x] 2.7 Document the stage and its place in the pipeline in the README, `docs/agents.md` and `docs/policy-checkpoints.md`; verify the documented commands run as written on the sample database

## 3. Actions

- [x] 3.1 Add the `mandate` source kind and link mandate results in the actions contracts, input builder and guard; verify with tests that a mandate source with an unknown ref removes the action and records a gap
- [x] 3.2 Make the rubric status-aware per the table in design.md and render the same table in `RUBRIC_TEXT`; verify with tests for every cell, an action without a mandate source keeping `high`, and the text matching the table
- [x] 3.3 Teach the actions prompt the wording per status and list contradicted mandate results under `not_actioned`; verify with scripted-model tests for `client_directed` (verify waiver), `contradicted` (correct the record) and `acknowledged` (follow up)
- [x] 3.4 Treat a missing mandate reconciliation as a gap with every mandate action as `no_note`; verify with a test that the output equals today's for a client without the file plus the gap
- [x] 3.5 Update `docs/agents.md` and the README for the new input and the rubric table; verify the table in the docs equals `RUBRIC_TEXT`

## 4. API and UI

- [x] 4.1 Read the persisted mandate reconciliation in the API layer and add `breach_reconciliation` to the portfolio list entry and the quoted notes to the portfolio detail; verify with API tests for a reconciled breach, `no_note`, no file (gap) and a custody portfolio
- [x] 4.2 Regenerate the OpenAPI schema and `dashboard-ui/src/api/schema.ts`; update `docs/api.md`; verify the type check passes and the docs list the fields
- [x] 4.3 Show the status label and note ids in `PortfolioList.tsx`/`status.ts` and the status with the quoted note and exclusion breaches in `PortfolioPage.tsx`; verify with component tests for "waiver claimed (N-010)", `no_note` (no label), an exclusion breach and a claimed waiver still marked as a breach
- [x] 4.4 Run the dashboard against the seeded database and look at PF-0007, PF-0009 and PF-0011; verify the labels and quotes render and the page has no console errors

## 5. Integration

- [x] 5.1 Run the full pipeline order `outlook` → `analyse` → `reconcile` → `mandate-reconcile` → `actions` → `overview` on the sample database with a scripted model; verify each stage reads the previous output and the overview ranks the new actions
- [ ] 5.2 Run the Python test suite and the dashboard tests, lint and type check; verify all pass
