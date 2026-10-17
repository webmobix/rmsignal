## 1. Contracts and catalogue

- [x] 1.1 Create `src/rm_dashboard/scenarios/` with pydantic contracts: scenario record, shock vector (channel, best/likely/worst, rationale, explainer, evidence ids, anchored-event), impact (three cases, bands, collateral, positions with channels, summary, explainers, gaps, status, input hash), client and RM roll-ups
- [x] 1.2 Implement the catalogue store (`reports/scenarios/catalogue.json`) with validation and seeding of the three existing scenarios
- [x] 1.3 Define the channel vocabulary from the data (read instruments and market_context) and document it

## 2. Layer A: scenario agent

- [x] 2.1 Add `scenario_analyst` prompt, allow-list and `AnalystSpec`; add a tool exposing the stored vector as evidence
- [x] 2.2 Implement the guard: schema, no single-instrument keys, ordering worst <= likely <= best, citations from the run, point-in-time check, anchored-event or "not anchored" statement
- [x] 2.3 Implement `produce_shock_vector` with always-delivered behaviour and gaps; unit tests with the stub model, including failure and misordered cases
- [x] 2.4 Input hashing and vector store under `reports/<as_of>/scenarios/<id>/`

## 3. Layer B: portfolio impact

- [x] 3.1 Implement holding-to-channel mapping rules reusing exposure and sector look-through; untouched and reached-share computation
- [x] 3.2 Implement impact arithmetic for best/likely/worst, per-position channel moves, additive channels
- [x] 3.3 Implement mandate band crossings and Lombard LTV/shortfall per case using existing analytics
- [x] 3.4 Add `scenario_impact` agent for ambiguous mappings and prose; guard for channel membership and figure matching with code-built summary fallback
- [x] 3.5 Tests with fixture portfolios: three cases, untouched holding, structured product, band cross, margin breach, missing vector

## 4. Roll-ups

- [x] 4.1 Client roll-up aggregation and summary with figure check
- [x] 4.2 RM book roll-up: totals, most-hit, beneficiaries, crossings, coverage; thin agent summary with figure check
- [x] 4.3 Tests for sums, ranking, partial coverage and summary mismatch

## 5. Pipeline and runner

- [x] 5.1 Hash chain (scenario text, data fingerprint, holdings, prompt version, model; impact includes vector hash) and cache skip logic
- [x] 5.2 Runner `rm-dashboard-scenarios` with filters, `--force`, parallel units, per-unit write, failure isolation, run summary, policy and audit/LLM logs; register CLI in `pyproject.toml`
- [x] 5.3 Tests: same inputs no model call, edited text regenerates dependents, resume, one failing unit

## 6. API

- [x] 6.1 Update response models; migrate `PlaceholderScenarioProvider` to the new shape
- [x] 6.2 Implement `ComputedScenarioProvider` reading stored results, with placeholder/insufficient entries for gaps; wire default selection in `api/app.py`
- [x] 6.3 Add `GET /api/scenarios/{scenario_id}/rollup` and 404 handling; update `docs/api.md` and tests (`test_api_scenarios`, docs test)

## 7. UI

- [x] 7.1 Regenerate/update `dashboard-ui/src/api/schema.ts` for the new models
- [x] 7.2 Scenario tab: three-case range bar, summaries, explainers, per-case bands/collateral, banner copy, partial/gaps display, comparison view; update `ScenarioTab.test.tsx`
- [x] 7.3 Market page scenario panel (RM book roll-up) with picker, totals, ranked clients linking to the client tab, crossings, coverage and empty state; tests
- [ ] 7.4 Optionally align `sample/SY/app` scenario data shape and copy

## 8. Data and verification

- [ ] 8.1 Run the engine for 2026-08-26 and commit the results under `reports/`
- [x] 8.2 Check one scenario against the Hormuz event in the event log for plausibility of the anchored moves
- [x] 8.3 Run the full test suites, `openspec validate add-scenario-engine`, and update architecture docs
