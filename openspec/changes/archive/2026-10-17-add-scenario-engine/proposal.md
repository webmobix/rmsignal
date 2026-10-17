# Proposal

## Why

The scenario tab (client view and the sample app) shows fixed placeholder figures behind a `ScenarioProvider` seam. RMs cannot see how a portfolio would move under a stated scenario, and the single placeholder number has no range, no reasoning and no summary. The data (point-in-time holdings, market context, event log) and the agent pattern (outlook pipeline) already exist, so the placeholder can now be replaced by a computed result.

## What Changes

- Scenarios become stored text records (id, name, premise, optional "mirrors" event, horizon). Adding a scenario means adding text, not code.
- **Layer A, scenario agent**: one run per `scenario x as_of` turns the scenario text plus point-in-time evidence into a market shock vector (per segment/channel, no single stocks) with best, likely and worst values, each with rationale, cited evidence and an explainer. Result is cached and shared by all portfolios.
- **Layer B, impact run**: one run per `portfolio x scenario`. Code applies the shock vector to the portfolio's exposures (asset class, sector, region, currency, structured-product look-through) and computes best/likely/worst value, USD and %, mandate bands crossed, Lombard LTV effects and untouched holdings. The agent only resolves ambiguous holding-to-channel mappings and writes summary and explainers.
- A guard rejects outputs where ordering (worst <= likely <= best) breaks, figures differ from computed values, citations are not from the run, or holdings are neither mapped nor declared untouched.
- Summaries and explainers at four levels: scenario, portfolio x scenario, client, RM book. The RM roll-up is code-aggregated (book totals, most-hit and benefiting clients, band/LTV crossings) with a thin agent summary.
- Results persisted under `reports/<as_of>/scenarios/`, cached by input hash, produced by a resumable batch command.
- `ComputedScenarioProvider` replaces the placeholder (`status: "computed"`); scenario API and UI gain three cases, summaries and explainers; the market page gets a scenario roll-up panel fed by the scenario API.
- Copy changes from "nothing forecasts" to "conditional on this scenario, central case, not a probability". Default horizon 3 months, shown in the UI.
- **BREAKING**: `ScenarioResult` response model changes (single delta replaced by best/likely/worst). The UI is updated in the same change.

## Capabilities

### New Capabilities
- `scenario-catalogue`: scenarios as stored text records with horizon, added without code changes.
- `scenario-market-shocks`: the scenario agent and guard producing cached, evidence-bound best/likely/worst shock vectors per scenario and as-of.
- `scenario-portfolio-impact`: deterministic portfolio impact of a shock vector, with agent-written summary and explainers.
- `scenario-rollups`: client and RM-book aggregation and summaries of scenario results.
- `scenario-run-pipeline`: persistence, input-hash caching, batch runner and audit for scenario runs.

### Modified Capabilities
- `scenario-api`: computed provider, three-case results, summaries, explainers, client and RM roll-up endpoints.
- `scenario-ui`: three-case range display, summaries, explainers, conditional banner, scenario comparison.
- `instrument-market-ui`: scenario roll-up panel on the market page.

## Impact

- Code: `src/rm_dashboard/api/scenarios.py`, a new `src/rm_dashboard/scenarios/` package (contracts, agent, guard, store, impact), `src/rm_dashboard/runners/` (new scenario runner and CLI), `agents/prompts.py`, `tools/allowlists.py` and tools, `api/app.py`.
- UI: `dashboard-ui/src/features/scenarios/`, market page, `api/schema.ts`; `sample/SY/app` data shape optionally aligned.
- Data: new files under `reports/<as_of>/scenarios/`; no database schema change.
- Dependencies: reuses existing LLM gateway, policy engine, audit and LLM logging; no new packages expected.
- Risks: LLM nondeterminism (mitigated by caching and guard), unmapped holdings, and the numeric-forecast departure from `market-outlook` (kept as a separate, conditional capability).
