# Tasks

## 1. Contracts and tools

- [x] 1.1 Add `InstrumentOutlook` to `rm_dashboard/outlook/contracts.py` reusing `View`/`Change`; verify round-trip and that no client, portfolio or quantity field exists
- [x] 1.2 Add `instruments.context` (reference, price history with percent changes, peers by sector/sub-asset class and region); verify on the sample (equity fund with peers, a gold-linked instrument, an instrument without peers)
- [x] 1.3 Add `events.relevant` with `matched_on`; verify gold, oil/energy and rates instruments match the expected events, an unrelated event is excluded and no later event appears
- [x] 1.4 Add `outlook.market` (copies driver evidence into the run store, `no_data` when absent) and `outlook.previous_instrument` (reference-only, strictly earlier); verify citations resolve and a later outlook is never returned

## 2. Agent and guard

- [x] 2.1 Add the instrument subject to the outlook analyst (subject pattern, prompt section, stub plan) and narrow tools per subject in the runner; verify market-only tools are refused for an instrument run
- [x] 2.2 Extend the outlook guard for instruments (code-copied market context, confidence caps for thin history and unsupported views, relevant `unaddressed_events`); verify one test per rule
- [x] 2.3 Assemble status and gaps and carry-forward on failure; verify raising model, unparsable output and missing market outlook

## 3. Stage

- [x] 3.1 Discover held instruments at `as_of` from the point-in-time repository; verify the union across portfolios and the `--instruments` filter
- [x] 3.2 Implement the fingerprint, carry-forward and skip-if-same-inputs; verify a rerun makes zero model calls and one new relevant event regenerates only the affected instruments
- [x] 3.3 Run instruments in parallel (bounded by `max_concurrency`) after the market outlook and persist `outlook/instruments/<id>.json`, evidence, `summary.json`, `audit.jsonl`; verify isolation when one instrument fails
- [x] 3.4 Extend `rm-dashboard-outlook` with `--instruments` and `--force`; verify the full command on the seeded sample database with the stub model

## 4. Docs

- [x] 4.1 Document the instrument outlook (contract, matching rules, fingerprint, command) in `docs/agents.md` and `docs/methods.md`; verify `tests/test_docs.py`
