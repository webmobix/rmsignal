# Tasks

## 1. Contracts and data

- [x] 1.1 Create `rm_dashboard/outlook` with `MarketOutlook`, `View`, `Change`, closed sets for segment, direction, horizon, confidence; verify contract tests (round-trip, rejected values, no numeric forecast field)
- [x] 1.2 Add `market.history` to the domain tools and register it; verify rows per snapshot up to `as_of`, no later snapshot, `insufficient_data` before the first
- [x] 1.3 Add `analytics.market_trend` (level, change vs previous and vs first snapshot, snapshot count); verify values on the sample data and `insufficient_history` with one snapshot
- [x] 1.4 Add `ReportSource`-style previous-outlook lookup scanning `reports/*/outlook/market.json` for the greatest earlier `as_of`; add the reference-only `outlook.previous_market` tool; verify a later outlook is never returned and none gives `no_data`

## 2. Versioning

- [x] 2.1 Compute the data fingerprint (`market_snapshot_date`, `latest_event_date`, `event_count`) from the repository; verify tests for equal, new snapshot and new event
- [x] 2.2 Implement carry-forward (no model call, `unchanged`, `carried_forward_from`) and `--force`; verify with a model that fails if called

## 3. Agent and guard

- [x] 3.1 Add the outlook analyst prompt (events are facts and important reasons, closed output shape, no price targets), allow-list, gateway role `outlook_analyst` and a stub plan; verify the agent sees only its allow-listed tools
- [x] 3.2 Implement the outlook guard: closed sets, citations from this run, no `prior_view` support, number grounding, derived `change.kind`/`previous_direction`, reversion of unsupported direction changes, confidence caps, `unaddressed_events`; verify one test per rule including the stub failure modes
- [x] 3.3 Assemble status and gaps, deliver on model failure with previous views carried forward; verify a raising model, unparsable output and a policy denial

## 4. Runner, CLI and docs

- [x] 4.1 Persist `outlook/market.json`, `evidence/market.json`, `summary.json`, `audit.jsonl` without touching other dates; verify the reference chain across two dates
- [x] 4.2 Add `rm-dashboard-outlook --as-of DATE [--db] [--reports-dir] [--force]` and the script entry; verify the command on the seeded sample database with the stub model
- [x] 4.3 Document the outlook (contract, versioning, guard rules, command) in `docs/agents.md` and `docs/methods.md`; verify `tests/test_docs.py`
