# Tasks

## 1. Setup

- [x] 1.1 Add `polars`, `pydantic`, `langgraph`, `deepagents`, `langchain-openai`, `a2a-sdk` and dev `hypothesis` to `pyproject.toml` (pin versions after checking current docs) and verify `uv sync` and `uv run pytest` still pass
- [x] 1.2 Create empty packages `pit`, `domain`, `analytics`, `tools`, `policy`, `agents`, `a2a`, `runners` under `src/rm_dashboard/` and verify they import
- [x] 1.3 Add a settings module (db path, gateway URL, model name, horizon defaults) and verify values load from environment in a unit test

## 2. Domain contracts

- [x] 2.1 Implement entity models (Party, Person, Relationship, Client, Portfolio, Position, Instrument, Event) and verify construction/validation tests
- [x] 2.2 Implement `ToolResult` with content-hash `evidence_id`, status values and quality flags; verify same input gives same id and different `as_of` gives different id
- [x] 2.3 Implement `Report` and `Finding` (evidence required); verify a finding without evidence is rejected
- [x] 2.4 Document the contracts in `docs/contracts.md` and verify example JSON in it validates against the models in a test

## 3. Point-in-time repository

- [x] 3.1 Implement `PitRepository` protocol and Polars loader from `SqliteDataSource`, melting wide date columns into `portfolio_aum`, `instrument_price`, `facility_snapshot`; verify row counts (5 snapshots x entities) and AUM reconciliation to holdings in tests
- [x] 3.2 Implement snapshot resolution with `effective_snapshot_date` and gap; verify `as_of` 2026-02-01 resolves to 2025-12-31 and an `as_of` before all snapshots yields `insufficient_data`
- [x] 3.3 Implement event-dated filtering for notes, events, transactions and cash needs; verify no row dated after `as_of` is returned
- [x] 3.4 Implement `current_only` tagging for unversioned attributes and verify on a historical `as_of`
- [x] 3.5 Implement data-quality flags (stale mark, missing cost basis, mid-year positions, subscription-currency mismatch, facility drawdown mismatch) from config; verify each against its known row (Aranya SYN-AL-0308, PF-0005, CF-0002/TXN-0013)
- [x] 3.6 Add PIT tests: KYC-overdue differs for `as_of` 2026-08-26 vs 2026-10-15, and a test failing if any package module calls the wall clock; document the PIT contract in `docs/point-in-time.md`

## 4. Analytics

- [x] 4.1 Port FX normalisation (quote direction per pair from config) and bond nominal handling; verify conversions with hand-checked cases
- [x] 4.2 Implement weights and exposures (asset class, currency, sector, region) with stated denominator; verify weights sum to 100 with property tests
- [x] 4.3 Implement client-level concentration incl. look-through, HHI, top-N; verify shared-underlying aggregation and basket assumption flag
- [x] 4.4 Implement mandate band drift excluding custody; verify against a hand-computed portfolio
- [x] 4.5 Implement liquidity coverage vs needs and commitments with certainty handling; verify shortfall and aspirational exclusion cases
- [x] 4.6 Implement LTV/headroom/cure amount and pledged-collateral funding test (re-implemented from SY `liquidity`); verify LTV equals drawn/lending value for all facility snapshots
- [x] 4.7 Implement unrealised P&L and price/FX/flow decomposition; verify exact sum with property tests
- [x] 4.8 Implement `insufficient_history` for volatility/VaR/drawdown/Sharpe; verify no number is returned
- [x] 4.9 Document each metric's method in `docs/analytics.md` and verify every analytic has a method string tested for presence

## 5. Tools

- [x] 5.1 Implement tool wrapper that builds the envelope (sources, computation, flags, evidence id); verify via a sample tool test
- [x] 5.2 Implement domain tools: clients, relationships, persons, portfolios, positions, instruments, market, events/news, notes (quoted, `derived_from_text`), credit, cash needs; verify each requires `as_of` and returns sources
- [x] 5.3 Implement `no_data` adapters for persons, related parties and news; verify status and reason
- [x] 5.4 Implement analytics tools taking identifiers only; verify an agent-style call needs no numeric inputs
- [x] 5.5 Implement tool registry with per-agent allow-lists; verify out-of-list call is refused and recorded
- [x] 5.6 Verify an inventory test that no tool accepts a file path or SQL string

## 6. Policy and audit

- [x] 6.1 Implement `PolicyEngine` interface, `Decision`, and mock engine; verify mock returns allow with mock reason
- [x] 6.2 Implement checkpoint hooks at run start, tool call, model call, A2A edges, report assembly and approval gate; verify one decision per reached checkpoint in a run trace
- [x] 6.3 Implement append-only audit log (run id, agent, as_of, input hash, evidence ids, decision); verify every tool call has a record
- [x] 6.4 Implement PII pseudonymisation for model input; verify prompt contains pseudonym not name
- [x] 6.5 Verify deny degrades to a gap and escalate pauses the step, using a test engine; document checkpoints in `docs/policy-checkpoints.md`

## 7. Agents

- [x] 7.1 Implement LLM gateway client from settings and a deterministic stub model for tests; verify swapping model name needs no code change
- [x] 7.2 Implement Instrument Analyst agent with allow-listed tools and prompt; verify with stub model that it returns a valid `Report`
- [x] 7.3 Implement Portfolio Analyst delegating to Instrument Analyst; verify delegated evidence appears in the portfolio report
- [x] 7.4 Implement Relationship Analyst delegating to Portfolio Analyst, stating unavailable related-party data; verify no inferred parties
- [x] 7.5 Implement output guard (numbers must match cited evidence); verify an injected uncited number is removed and status becomes `partial`
- [x] 7.6 Implement always-deliver wrapper converting tool errors, denials and guard removals into gaps; verify a failing tool still yields a report
- [x] 7.7 Implement checkpointed interactive session (thread id, fixed `as_of`); verify a follow-up reuses earlier evidence
- [x] 7.8 Document agents, prompts and extension steps (new analyst = prompt + allow-list + card) in `docs/agents.md`

## 8. A2A

- [x] 8.1 Implement Agent Cards for the three analysts; verify cards list skills and required `as_of`
- [x] 8.2 Implement A2A server adapters returning the report as task result and input-required on missing `as_of`; verify with a test client
- [x] 8.3 Implement mock KYC/compliance peer and A2A client in the Relationship Analyst; verify peer answer is recorded as mock-flagged evidence
- [x] 8.4 Wire policy checkpoints and delegation chain into A2A calls; verify audit records list the original requester

## 9. Batch runner and integration

- [x] 9.1 Implement batch runner (`rm-dashboard-analyse --as-of DATE [--clients …]`) writing one JSON report per client and a run summary; verify CLI on the seeded db with the stub model
- [x] 9.2 End-to-end check: run all 20 clients at 2026-08-26 and 2026-03-31, verify 20 valid reports each, no look-ahead evidence for the earlier date, and statuses summarised
- [x] 9.3 End-to-end failure check: stub model failure and a denied tool still produce `partial` reports; run `uv run pytest` and verify all tests pass
- [x] 9.4 Update `README.md` with the analysis layer overview and run commands, and verify the documented commands run as written
