# Design

## Context

62 instruments (asset class, sub-asset class, sector, region, currency, liquidity tier, underlying reference) with a price per snapshot; five snapshots. Events carry region, severity and a free-text `primary_transmission` ("Gold, precious metals", "Energy, shipping, airlines"). Today the instrument analyst runs as a child of the portfolio analyst inside each client's run, with its own evidence store, so nothing is shared. `analytics.risk` already needs enough history and reports `insufficient_history` otherwise. See proposal.md.

## Goals / Non-Goals

**Goals:** one reusable analysis and outlook per instrument and date; industry and market context; same trust rules as the market outlook.
**Non-Goals:** client context, using the result in client reports (next change), forecasts of numeric prices.

## Decisions

1. **Subject kind added to the same agent.** `outlook_analyst` accepts `MKT` and `SYN-[A-Z]{2}-\d{4}`; the prompt has a market section and an instrument section; allow-list is the union, but the tools an instrument run may use are narrowed per subject by the runner (market-only tools are refused for an instrument run). *Alternative:* second agent: rejected in `add-market-outlook`.

2. **Contract `InstrumentOutlook`** = market `View` fields plus `instrument` (id, name, asset class, sector, region, liquidity tier), `price_path` summary (copied from tool results, not written by the model), `market_context` (the market segment views it relied on, by segment and direction, copied by code), `relevant_events[]` (cited event ids), `inputs` fingerprint and `previous_as_of`. One view per instrument; `change` as in the market outlook.

3. **Tools.**
   - `instruments.context`: reference row, price history by snapshot with percent changes, and peers (same sector, else same sub-asset class, and same region) with the same changes, so relative performance is computed by code. A single instrument without peers returns `peers: []` and a flag.
   - `events.relevant`: events dated on or before `as_of` whose region is `Global` or equals the instrument's region, or whose transmission text shares a token with the instrument's sector, asset class, sub-asset class, name or underlying reference. Each row carries `matched_on` (field and token). Candidates only: the model decides which are relevant and must cite them; matching is lexical and the tool says so. *Alternative:* give the model all events: rejected, it makes relevance un-auditable and wastes tokens as the log grows.
   - `outlook.market`: the persisted market outlook for the same `as_of` (exact date, or the latest carried-forward one that covers it, i.e. the greatest outlook `as_of` not later than the run's). Its driver evidence is copied into the instrument run's store so citations resolve. If none exists the tool returns `no_data` and the instrument outlook is `partial` with a gap.
   - `outlook.previous_instrument`: reference-only, strictly earlier `as_of`, as in the market outlook.

4. **Held instruments.** The union of instruments in the positions snapshot effective at `as_of` across all portfolios, from the point-in-time repository; `--instruments` narrows it. An instrument with no price at `as_of` yields `insufficient_data` without a model call.

5. **Fingerprint and carry-forward.** `inputs = {price_snapshot_date, relevant_event_ids, market_outlook_as_of, market_outlook_digest}`. Equal to the previous instrument outlook's inputs: carry forward with no model call. This is also the sharing mechanism: one instrument, one file per `as_of`, read by every client.

6. **Guard** reuses the market rules (closed sets, citations from this run, no prior-view support, grounded numbers, derived change kind, reverted unsupported direction changes, `unaddressed_events` among the relevant High/Severe ones) and adds: the market context is copied by code, never written by the model; confidence capped at `low` when `analytics.risk` or the price path is insufficient, and at `medium` when no cited event or peer comparison supports the view.

7. **Stage and concurrency.** `run_outlook(as_of)`: market outlook, then instruments through a thread pool bounded by `max_concurrency`, each with its own `RunScope`; files are written by the main thread. Skipping an instrument whose fingerprint matches an existing file for the same `as_of` makes reruns cheap; `--force` overrides.

8. **Privacy.** No client data enters an instrument run; positions are read only for the set of instrument ids, not for quantities or owners.

9. **Refinements made during implementation.**
   - *Event matching:* a `Global` event is never a candidate by region alone (it would match everything); it needs a shared word. A regional event matches an instrument of that region (`United States` also covers `North America`) on its own. Currency codes and generic words are ignored.
   - *Fingerprint:* equality ignores the date of the market outlook and uses its digest, so an unchanged market view with a later date does not regenerate every instrument.
   - *Risk statistics* come from `instruments.context` (volatility and drawdown availability), so `analytics.risk` is not in the allow-list. With five snapshots both are always unavailable, so every confidence is `low` until the history is longer; this follows the requirement as written.
   - *Evidence files* keep what the run's tools produced plus what the view cites; the market outlook's evidence that `outlook.market` makes resolvable stays in the market outlook's own file.
   - *Audit* is append-only across runs of the same date, and a run that changes nothing writes nothing.

## Risks / Trade-offs

- [Lexical event matching misses or over-matches] → candidates only, matched token shown, model cites its own selection; matching rules are documented and tested on the sample (gold, oil, rates).
- [Outlook of 60 instruments costs 60 model calls per changed date] → carry-forward, parallelism, and the fingerprint skip; only instruments with new inputs call the model.
- [Instrument view contradicts the market view] → allowed, but the instrument rationale must cite its own evidence and the market context is shown next to it.
- [Market outlook missing] → partial with a gap rather than a failure.
