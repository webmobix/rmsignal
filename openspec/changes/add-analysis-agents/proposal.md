# Proposal

## Why

The repo can mirror the SingHacks wealth dataset and expose raw tables, but nothing answers "what should the RM know about this client and portfolio as of date X, and why". The samples (SingHacks starter, SY "BaerSignal") are fixed-date rule engines that read only the last snapshot, parse free text with regexes, and let nothing be traced to evidence. We need an MVP that can grow into a production component of a bank's agent ecosystem: relationship and portfolio analysis by cooperating agents, where every number comes from a deterministic tool, every claim cites evidence, every analysis is reproducible for a chosen point in time, and policy checks have defined places to plug in.

## What Changes

- Add a point-in-time repository over the existing SQLite mirror: `as_of` is required everywhere, snapshots resolve to the latest one on or before `as_of`, event-dated sources are filtered to `date <= as_of`, unversioned attributes are tagged `current_only`. The wall clock is never read.
- Add domain contracts (pydantic): Party, Person, Relationship, Client, Portfolio, Position, Instrument, Event, and the evidence-carrying `ToolResult` and `Report`. Party/Person/Relationship/News are defined now and backed by adapters that return an explicit `no_data`, because the dataset has none of them.
- Add a deterministic analytics library in Polars (weights, exposures, look-through, concentration, mandate drift, liquidity coverage, LTV/collateral, P&L and price/FX/flow decomposition). History-dependent measures (volatility, VaR, drawdown) return `insufficient_history`.
- Add agent tools wrapping repository + analytics in the `ToolResult` envelope. Agents never read CSV/SQLite and never compute numbers.
- Add Deep Agents / LangGraph agents: Relationship Analyst delegating to Portfolio Analyst delegating to Instrument Analyst, with batch and interactive modes on the same graph and an LLM gateway that is provider-agnostic.
- Add an output guard so every number in agent output matches a cited tool value, and a report contract that always delivers (`complete | partial | insufficient_data`) with gaps listed.
- Add a `PolicyEngine` interface with a mock (allow + reason) and ten checkpoints (entitlement, tool authorisation, A2A, PII minimisation, freshness/PIT, suitability, provenance, compliance content, human approval, audit) wired in but not implemented.
- Add an A2A boundary (official `a2a-sdk`): Agent Cards and servers for each analyst, and a consumed mock bank peer (KYC/compliance).
- Add a batch runner producing one report per client per `as_of`.
- No **BREAKING** changes. The existing `data/` package, seeder and debug API are unchanged.

## Capabilities

### New Capabilities
- `point-in-time-data`: as_of-aware repository, snapshot resolution, normalised long tables, PIT tagging, data-quality flags for known dataset traps.
- `domain-contracts`: entity models, the ToolResult evidence envelope and the Report contract, including no-data adapters for parties, persons, relationships and news.
- `portfolio-analytics`: deterministic Polars calculations and their input/insufficient-history behaviour.
- `agent-tools`: the namespaced, evidence-returning tool surface agents use.
- `analysis-agents`: agent topology, delegation, always-deliver reporting, output guard, batch and interactive execution, LLM gateway.
- `policy-checkpoints`: PolicyEngine interface, mock, checkpoint placement and audit log.
- `agent-interoperability`: A2A Agent Cards, server, client and the mock peer.

### Modified Capabilities
<!-- none: existing sqlite-datasource, data-models, database-seeding requirements are unchanged -->

## Impact

- New packages under `src/rm_dashboard/`: `pit`, `domain`, `analytics`, `tools`, `policy`, `agents`, `a2a`, `runners`.
- New dependencies: `polars`, `pydantic`, `langgraph`, `deepagents`, `langchain-openai`, `a2a-sdk`; dev: `hypothesis`.
- Reads the existing `rm.db` through `SqliteDataSource` only. No schema change.
- Reference-only inputs: `sample/SY/engine/*` (logic to re-implement and test, not import).
- Out of scope: UI, severity scoring/triage ranking, scenario shock libraries, real policy rules, real persons/KYC/news data, MCP server, production datastore.
