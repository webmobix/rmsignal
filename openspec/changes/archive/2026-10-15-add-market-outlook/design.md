# Design

## Context

Data in the sample: five market snapshots (2025-12-31 to 2026-08-26) across indices, rates, FX, commodities and volatility (`market_context`), and a 16-row dated event log with region, severity and the assets each event transmits to. `market.snapshot` returns only the effective snapshot, so the series history is not reachable today. Reports live in `reports/<as_of>/`; each stage reads the previous stage's files (`add-rm-overview-agent` pattern). The agent stack (Deep Agents, allow-list and privacy middleware, `Toolbox`, evidence store, output guard, always-delivered reports) exists in `rm_dashboard.agents`. See proposal.md.

## Goals / Non-Goals

**Goals:** an evidence-bound, explainable view that changes only when data changes and keeps its history.
**Non-Goals:** numeric forecasts, client or instrument specifics, scoring forecast accuracy, a news feed.

## Decisions

1. **One agent, role `outlook_analyst`, subject kinds added over time.** Subject `MKT` here; `add-instrument-outlook` adds `SYN-xx-nnnn`. Same pipeline as the analysts (`analyse`, `Toolbox`, `RunContext`, always-delivered). *Alternative:* a market agent and a separate instrument agent: rejected, the reasoning (history plus events plus previous view) is the same.

2. **Output contract `MarketOutlook`** in `outlook/contracts.py`: `as_of`, `status`, `agent`, `summary`, `views[]`, `inputs`, `previous_as_of`, `changes_summary`, `unaddressed_events[]`, `gaps[]`, `evidence_ids[]`. A `View` has `segment` (closed set: `overall`, `equity`, `rates`, `fx`, `commodities`, `volatility`, taken from the market categories), `direction`, `horizon` (closed set, MVP default `3m`), `confidence`, `rationale`, `drivers[]` and `risks[]` (each `{claim, evidence_ids}`), `would_change_if`, and `change` (`kind`, `previous_direction`, `why`, `new_evidence_ids`). Closed sets keep the model from inventing structure.

3. **Tools** (registered in `ToolRegistry`, allow-listed only for the outlook analyst):
   - `market.history`: all series values per snapshot date up to `as_of`.
   - `analytics.market_trend`: per series, level at the effective snapshot, absolute and percent change versus the previous and the first snapshot, number of snapshots; `insufficient_history` with one snapshot. The model interprets, code computes.
   - `outlook.previous_market`: the latest persisted market outlook with `as_of` strictly earlier than the current one (never later: no look-ahead), tagged as a prior view. Its result is **reference-only**: the guard refuses it as support for a driver or risk. If none exists it returns `no_data` ("first outlook").
   - `news.list` / `events.list` (existing, now with events as news).

4. **Data fingerprint and carry-forward.** `inputs = {market_snapshot_date, latest_event_date, event_count}` computed in code from the repository. If it equals the previous outlook's `inputs`, the run writes a carried-forward outlook (`status` as the previous, views copied, every `change.kind = unchanged`, `carried_forward_from = previous as_of`, no model call). This implements "changes when there is new data since the last call" and keeps cost flat when dates advance without data. A `--force` flag regenerates.

5. **The model proposes, code decides** (`outlook/guard.py`):
   - Segment, direction, horizon, confidence must be in their closed sets, else the view is removed with a `guard_removed` gap.
   - Each view needs at least one driver; every driver and risk cites evidence produced in this run, none of kind `prior_view`; figures must appear in the cited evidence (existing number guard).
   - `change` is partly computed: `previous_direction` is copied from the previous file, `kind` is derived from the previous and new direction (the model cannot claim `unchanged` for a different direction). A direction change must cite at least one piece of **new** evidence: an event dated after the previous `as_of`, or a market snapshot dated after it. Otherwise the view reverts to the previous direction and a gap records why.
   - `unaddressed_events`: events with severity `High` or `Severe` dated in the window `(previous as_of, as_of]` (first run: all up to `as_of`) that no driver or risk cites. Informational; makes omissions visible without forcing a status.
   - Confidence is capped at `medium` for a view whose drivers cite no event, and at `low` when `analytics.market_trend` is `insufficient_history`.

6. **Status.** `complete` without gaps, `partial` with gaps, `insufficient_data` when no market data exists at `as_of`; model failure or unparsable output yields `partial` with the previous views carried forward when available, otherwise no views and a gap (always delivered).

7. **Persistence and CLI.** `reports/<as_of>/outlook/market.json`, `evidence/market.json`, `summary.json`, `audit.jsonl`. Older dates are left untouched and serve as the reference chain. `rm-dashboard-outlook --as-of DATE [--db] [--reports-dir] [--force]`. The previous outlook is found by scanning `reports/*/outlook/market.json` for the greatest `as_of` below the current one.

8. **Privacy and policy.** Subject `MKT` has no personal data; the entitlement, PII and report-assembly checkpoints and the audit log still run through `RunContext`.

9. **Events are named by id** (added during implementation). Evidence ids identify whole tool results, not single events, so "which events does a driver cite" needs a finer key. `events.list` and `news.list` give every event a stable `event_id` (`EVT-<date>-<n>`, n counts events of the same date). A driver or risk lists `event_refs`; code verifies each was returned in this run and copies the evidence ids of the tool results that returned it. `unaddressed_events` and "newer than the previous outlook" (event date after the previous `as_of`) work on these ids.

10. **Reruns and empty outlooks** (added during implementation). Running the same `as_of` again with equal inputs and no `--force` changes nothing. The previous outlook is the latest earlier one *with views*, so an `insufficient_data` outlook never hides the history. A run whose model produced no valid view falls back to carrying the previous views forward (`carried_forward_from` set), and a segment the model skipped keeps its previous view with a gap.

## Risks / Trade-offs

- [The model writes a plausible but unfounded outlook] → drivers must cite run evidence, numbers are grounded, direction changes need new evidence, confidence is capped when thin; a numeric target is not representable.
- [Five snapshots are a short history] → `market_trend` states the count; low confidence and a gap when too short.
- [Carry-forward hides stale views] → the file says `carried_forward_from` and shows the inputs fingerprint, so the dashboard can show "unchanged since DATE".
- [Previous outlook anchors the model] → it is read for change descriptions only and cannot be cited as support.
- [Backfilling out of order] → only strictly earlier outlooks are used as previous, so running a past date after a later one stays reproducible.
