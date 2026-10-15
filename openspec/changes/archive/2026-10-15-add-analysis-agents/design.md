# Design

## Context

Existing: `rm_dashboard.data` mirrors the 12 dataset files into SQLite (`rm.db`) with frozen dataclasses and a read-only `SqliteDataSource`; the debug API exposes raw tables without dates. See proposal.md for motivation.

Dataset facts that constrain the design: five snapshots (2025-12-31 … 2026-08-26) with wide per-date columns in `portfolios`, `instruments`, `credit_facilities`; event-dated transactions, events, notes and cash needs; no history for risk profile, mandate, KYC or domicile; no persons, related parties, news or event-to-instrument mapping; known traps (FX quote direction, bond units of 100, stale Aranya mark, missing cost basis, mid-year positions, custody portfolios). Dataset "today" is 2026-08-26 while real time is later, so clock use is a correctness bug, not a style issue.

SY's engine was reviewed as reference: its FX normalisation, look-through, pledged-collateral funding test and evidence-bearing finding schema are worth porting; its last-snapshot-only evaluation, note-regex waivers, hindsight event attribution and sample-tuned severity are not.

## Goals / Non-Goals

**Goals:**
- Point-in-time correctness by construction; reproducible runs.
- Every number from a deterministic tool; every claim traceable to evidence.
- Same agents for batch and interactive use; extendable by configuration.
- Policy checkpoints placed and audited, implementations mocked.
- Agents addressable by other bank agents.

**Non-Goals:**
- UI, triage ranking/severity scoring, scenario shock libraries.
- Real policy rules, real person/KYC/news sources, MCP server, production datastore.
- Return-series risk statistics (needs daily data).

## Decisions

**1. A new `pit` layer over the existing SQLite, not a rewrite.** `pit` is the only consumer of `SqliteDataSource`; it loads tables into Polars, melts wide date columns into long tables, and exposes a `PitRepository` protocol. *Alternative:* query SQLite directly per call — rejected: Polars frames are needed for analytics and the protocol lets a warehouse replace SQLite. *Alternative:* re-seed into a long schema — rejected: churns a finished, tested change; normalisation at read is cheap at this size.

**2. `as_of` required, no default; resolution is a repository concern.** Latest snapshot ≤ `as_of` plus gap reported; event-dated sources filtered `<= as_of`; unversioned attributes tagged `current_only`. A test scans the package for clock calls. Bitemporal storage (valid + knowledge time) is the documented production path, not built.

**3. Evidence envelope as the single result type** (`ToolResult`) with content-hash `evidence_id`. Agents cite ids; the output guard validates numbers against cited results. *Alternative:* trust-the-prompt — rejected; "agents don't calculate" must be enforceable. The guard generalises SY's `narrate.verify()` allow-list.

**4. Analytics: in-house Polars functions, pure and I/O-free; tools fetch inputs.** Agents pass identifiers only. Libraries: Polars, pydantic v2, hypothesis. Risk/optimisation libraries (quantstats/empyrical-reloaded, skfolio/Riskfolio-Lib, QuantLib) are deferred until daily series exist and sit behind the same tool interface, converting pandas at the boundary. Volatility/VaR return `insufficient_history`. *Alternative:* adopt a pandas performance library now — rejected: five points per instrument give nothing meaningful and it breaks the Polars preference.

**5. Dataset traps are config and flags, not literals.** FX quote direction per pair, bond nominal unit, custody service model, stale-mark rule, advance rates come from reference config/data; violations produce `data_quality_flags`. No client IDs, years or domiciles appear in logic.

**6. Agent topology: Deep Agents subagents in-process, A2A at service boundaries.** Relationship → Portfolio → Instrument are separate agents with narrow tool allow-lists; subagents are precompiled graphs. Deep Agents has no built-in A2A, so an adapter layer on the official `a2a-sdk` exposes each analyst (Agent Card + task handler returning the report) and a client consumes the mock KYC peer. MCP exposure of the tools is a later extension point. *Alternative:* one flat agent with all tools — rejected: context bloat and no per-agent authorisation scope. *Alternative:* A2A between in-process agents too — rejected: latency and complexity with no boundary benefit.

**7. One graph, two entry points.** Batch runner = one graph invocation per client per `as_of` (concurrency bounded), persisted as JSON; interactive = same graph with thread ids and a checkpointer (SQLite now, Postgres later). Human approval uses LangGraph interrupts.

**8. Always-deliver is a graph property.** Tool errors, policy denials and guard removals are caught at node boundaries and converted to `gaps`; the final node always assembles a `Report`. Status derives from gaps (`complete` none, `partial` some, `insufficient_data` core data absent).

**9. Policy via `PolicyEngine.check(checkpoint, context) -> Decision`.** Mock allows with reason. Checkpoints are applied by decorators/middleware at tool call, model call, A2A edge, run start and report assembly, so real engines (OPA, Cedar) swap in without touching agents. Every decision and call is appended to an audit log.

**10. LLM access through a gateway.** OpenAI-compatible base URL + model name from settings; PII pseudonymisation wraps the model call.

**11. Missing entities are modelled, not faked.** Party/Person/Relationship and news have schemas, tools and `no_data` adapters; the Relationship agent is instructed to report absence.

## Risks / Trade-offs

- [Five snapshots make "point in time" coarse] → report `effective_snapshot_date` and gap on every result; policy checkpoint can reject stale data.
- [LLM may phrase numbers differently from tool output (rounding, units)] → guard compares normalised values with a stated tolerance; agents are given pre-formatted display values by tools.
- [Look-through of baskets is an assumption] → method states attribution and flags it; alternative attributions can be added as parameters.
- [`deepagents` and `a2a-sdk` APIs move quickly] → pin versions; isolate behind `agents/` and `a2a/` adapters; verify against current docs when implementing.
- [Mock policies give false comfort] → every mock decision is labelled as mock in the report.
- [Scope is large] → delivered as ordered, independently testable task groups; stubbed LLM allows end-to-end tests without a provider.
- [Unversioned attributes can silently mislead historical runs] → `current_only` tag plus freshness/PIT policy checkpoint.

## Migration Plan

Additive. New packages and dependencies only; `rm.db` and the existing data package, seeder and debug API are untouched. Rollback = remove the new packages and dependencies. Complete and archive `add-sources-debug-api` independently.

## Open Questions

- Which batch concurrency and checkpointer backend for the first deployment (defaults: bounded thread pool, SQLite).
- Exact tolerance rules for the numeric output guard (start: relative 0.5% or display rounding).
