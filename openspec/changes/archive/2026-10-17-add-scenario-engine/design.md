# Design

## Context

- The scenario API serves fixed placeholder data behind `ScenarioProvider` (`api/scenarios.py`); routes and response models are meant to stay stable while the provider is swapped. The three-case, summary and explainer fields change the models, so this change is knowingly breaking for the scenario UI, which is updated with it.
- The outlook pipeline (`outlook/`, `runners/outlook.py`) is the pattern to copy: an `AnalystSpec` with a tool allow-list, a guard that checks citations against the run's evidence, a store under `reports/<as_of>/`, input comparison for carry-forward, "always delivered" results with gaps, a policy engine, audit and LLM logs.
- Point-in-time data comes from the PIT repository (holdings, market_context, event_log, credit_facilities, mandates). Existing analytics (exposure, sector look-through, mandate drift, credit LTV) already compute much of what the impact needs.
- `market-outlook` forbids numeric forecasts. Scenario shocks are numeric but conditional on a stated premise, so they live in their own capability and never feed back into the outlook.

## Goals / Non-Goals

**Goals:**
- Replace placeholder figures with computed best/likely/worst results for every portfolio x scenario.
- Keep every number in client-facing results computed by code; the model supplies judgment, rationale and prose only.
- Make a new scenario cost one text record plus one run.

**Non-Goals:**
- Single-instrument predictions, probabilities, hedge netting, execution of any action.
- Time paths within the horizon (only end-of-horizon moves).
- Scenario authoring UI (records are added through the store or CLI for the MVP).
- Feeding scenario results into the actions pipeline.

## Decisions

**1. Two layers: shared shock vector, per-portfolio impact.**
Layer A runs once per `scenario x as_of` and is cached; layer B runs per `portfolio x scenario`. Alternative: one self-contained agent per pair. Rejected: it gives different market calls for the same scenario across portfolios and repeats market reasoning for every portfolio.

**2. Code computes every figure.**
The model returns channel moves (layer A) and optional mapping proposals plus prose (layer B). Portfolio value, USD, %, bands, LTV, rankings and totals are computed by deterministic code. The guard compares every figure quoted in prose against the computed values and substitutes a code-built summary on mismatch. Alternative: let the model compute impact with tools. Rejected: arithmetic errors in client-facing P&L are unacceptable and hard to audit.

**3. Channels as the shared vocabulary.**
A shock vector is keyed by a fixed channel set derived from data (asset class, sector, region, currency, plus named macro channels such as energy, shipping, gold, credit spreads, rates already present in the sample). Holdings map to channels by rules on instrument attributes, using the existing look-through for structured products. Unmapped holdings are untouched by default; the agent may propose a mapping only to channels in the vector, flagged agent-assigned. Alternative: per-instrument betas. Rejected: no single-stock predictions and no beta data.

**4. Best/likely/worst are conditional cases, not probabilities.**
The vector stores three values per channel over one horizon (default 3 months). Code enforces worst <= likely <= best per channel and corrects only by reordering. Cases for a portfolio are computed by applying all-best, all-likely and all-worst channel values; this is stated in the explainer, as it ignores diversification between channels and therefore brackets rather than estimates a tail.

**5. Scenarios as data.**
A JSON catalogue store (`reports/scenarios/catalogue.json`, seeded with the three existing scenarios) replaces the Python constant. Catalogue edits change the input hash, which invalidates dependent results.

**6. Input-hash caching instead of date-based carry-forward.**
Scenarios depend on text, not just on new data. Each stored result carries a hash of scenario text and horizon, as_of data fingerprint (as in `OutlookInputs`), holdings snapshot fingerprint, prompt version and model id. Equal hash and no force means no regeneration. A vector change invalidates dependent impacts by hash chain (impact hash includes the vector hash).

**7. Storage layout.**
`reports/<as_of>/scenarios/<scenario_id>/vector.json`, `evidence/vector.json`, `impacts/<portfolio_id>.json`, `clients/<client_id>.json`, and `rollup.json` (RM book); `summary.json` and `audit.jsonl` per run. Mirrors outlook; other dates and scenarios are never touched.

**8. Roll-ups by code, thin summary by agent.**
Client and RM roll-ups sum computed impacts. One small agent call writes each summary from the aggregates under the same figure check as decision 2. Coverage (computed vs missing) is part of the aggregate.

**9. Runner.**
`rm-dashboard-scenarios --as-of DATE [--scenario ID] [--portfolio ID] [--force]` lists units (vector per scenario, impact per portfolio x scenario), skips those whose hash matches, runs the missing ones in a thread pool like the outlook runner, writes after each unit (so interruption resumes), and isolates failures per unit.

**10. API and UI.**
`ComputedScenarioProvider` reads stored results for the resolved `as_of` and returns `placeholder` or `insufficient_data` entries for gaps; the placeholder provider stays for tests. New `GET /api/scenarios/{id}/rollup`. UI: three-case range bar, summaries, explainer popovers, comparison view, banner copy; the market page panel calls the roll-up endpoint. Alternative: compute on request. Rejected: LLM latency and nondeterminism on a page load.

**11. Agent wiring.**
Two new `AnalystSpec`s (`scenario_analyst`, `scenario_impact`) with allow-lists: market history/snapshot, trend, events and news (A); portfolio positions, exposure, mandate and credit tools plus the vector (B). A new tool returns a stored vector as evidence. Prompts require JSON output, evidence ids and stating when no comparable past event exists.

## Risks / Trade-offs

- [Model invents or misorders moves] → schema validation, ordering enforcement, citation requirement, gaps and `partial` status.
- [All-best/all-worst bracketing overstates range] → disclosed in explainer; correlation-aware ranges deferred.
- [Rule-based mapping misses holdings] → "untouched" is explicit and counted; reached share shown; agent proposal only fills gaps and is flagged.
- [Nondeterminism between runs] → cache by hash, store results, `--force` is explicit; low temperature via model factory settings.
- [Numeric conditional forecasts read as predictions] → banner, horizon and not-a-probability text on every surface, no alarm colours.
- [Breaking response model] → UI and `schema.ts` updated together; placeholder provider migrated to the new shape.
- [Cost of portfolios x scenarios runs] → layer B prose is short, mapping calls only for ambiguous holdings, hash caching.

## Migration Plan

1. Add models and catalogue; migrate placeholder provider to the new shape so the UI can change first.
2. Add engine, runner and computed provider behind provider injection; default to computed when stored results exist for the `as_of`, otherwise placeholder.
3. Update UI; commit generated results for the 2026-08-26 run like other report data.
Rollback: switch the default provider back to the placeholder (one line in `api/app.py`); stored results are inert files.

## Open Questions

Settled while implementing (channel list and mapping rules; `scenarios/channels.py` holds the vocabulary):

- **Layered channels, no double counting.** Market channels carry an asset-class bucket (`equity_global|us|europe|japan|asia`, `rates_duration`, `gold`, `commodities_broad`, `real_estate`). Overlay channels carry an *excess* over that market move (`sector_*` over the holding's equity market, `credit_spreads` over `rates_duration`). FX channels (`fx_<ccy>`) carry a non-USD currency against USD as translation. A holding reaches one market channel, the overlays its sector or credit quality call for, and one fx channel; its move is their sum. The analyst prompt and the explainers state that overlays are relative.
- **Shipping.** The data has no shipping sector, so there is no shipping channel; shipping pressure is expressed through `sector_industrials`. No sector is invented.
- **Currency basis.** Dollar impact is computed on `market_value_usd`; FX is the move of `instrument_ccy` against USD. Mandate bands are measured on `market_value_base` (as `mandate_drift` does) and Lombard LTV in the facility currency, scaling collateral and lending value by the same position moves. The base currency itself is not shocked.
- **Ambiguous mapping.** Code cannot map: alternatives without a property link (hedge funds, private credit, private equity, infrastructure), commodities other than gold or diversified, and structured products whose underlyings do not resolve and whose own sector names no channel. Cash reaches no market channel by design and is not ambiguous. Only ambiguous holdings go to the agent.
- **RM book.** The data holds one RM; the roll-up covers all clients in the point-in-time client table and records the RM id when it is unique.
