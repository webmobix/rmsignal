# Design

## Context

Observed in the code:
- `api/portfolios.py` assembles `PortfolioDetail` (header, AuM history, bands, holdings, facilities) from `ctx.repo`. `api/clients.py` assembles the client view incl. notes, findings and actions from persisted files through `ctx.overviews`. `api/instruments.py` and `api/market.py` serve the instrument outlook and market outlook from `ctx.outlooks` (`OutlookStore`: `load_instrument`, `latest_instrument(id, not_after)`, `latest_market(not_after)`), and events with derived reach.
- `outlook/relevance.py` `relevant_events(instrument, events)` matches events to an instrument by region, sector, asset class, sub-asset class, name and underlying reference and says what matched. An `InstrumentOutlook` already carries `view` (direction, horizon, confidence, reasons), `market_context` (segment views copied by code), `relevant_events` and its `as_of`.
- The Portfolio Analyst reads outlooks only for the largest positions; the API has no portfolio-level join of positions to outlooks.
- The portfolio page has no tabs today; a `Tabs` component exists.

See proposal.md for motivation and the dependency on `add-portfolio-sector-exposure` and `add-mandate-reconciliation`.

## Goals / Non-Goals

**Goals:**
- One deterministic response per portfolio and date; every figure is copied from stored data or computed by existing code.
- All positions get a bank view, joined by instrument id, not chosen by a model or by size.
- A missing input degrades one section, never the sheet.

**Non-Goals:**
- No model call, no generated talking points, no export or print layout.
- No new persisted file or batch stage.
- No new recommendation or suitability logic.

## Decisions

**A new router `api/callsheet.py` with its own response models, reusing assembly helpers.** It calls the existing functions for holdings, bands (`mandate_check`), facilities (`facilities_for`), notes and events instead of re-querying. Alternative: extend `PortfolioDetail`; rejected, as the detail response would grow by three times and every portfolio page load would read all outlooks, though only the call sheet needs them. The UI requests the call sheet when the tab opens.

**Sections are independent builders.** Each returns `(data, gaps)`; the assembler never lets a builder's exception escape, turning it into a section gap. This is how "one section down, the rest renders" is guaranteed.

**Bank view join.** For each position, `ctx.outlooks.latest_instrument(instrument_id, not_after=as_of)`; the entry carries the outlook's own `as_of` and `older_than_as_of`. No outlook gives `outlook: null` plus a gap `outlook_missing`, the same gap code the instrument detail uses. The market context is the `market_context` already stored in the outlook; the sheet adds no segment mapping of its own. Alternative: map asset class to market segment in the API; rejected, as that would duplicate what the outlook stage already decided.

**Wording.** The API returns structured fields; the UI renders the label "Bank view as of <date>". Reason texts are the stored ones. No field carries a recommendation.

**Events.** Reuse `relevant_events` per held instrument against events dated on or before `as_of`; group by event so one event lists all concerned instruments, ordered by severity then date. Events between the two snapshots feed the performance section from the same event list.

**Performance drivers.** Contributors are the largest absolute value changes per instrument between the two snapshots (existing snapshot-change helpers). The "findings that concern the portfolio" are report findings whose evidence refers to the portfolio id, shown with their finding refs. No attribution is invented by the API; explaining the change in words stays with the persisted report.

**Mandate section reuses the other changes' outputs.** Bands and position limits come from `mandate_check`; reconciliation status and quoted notes from the persisted mandate reconciliation (`add-mandate-reconciliation`); exclusion breaches from the persisted evidence; open actions are the persisted actions whose sources link the portfolio's mandate results or whose evidence names the portfolio id.

**Ownership section embeds the sector exposure** produced by `add-portfolio-sector-exposure`, using the same function, so the two views cannot diverge.

**Cash and credit.** Facilities secured on the portfolio (existing helper). Liquidity, planned cash needs and commitments are client level in the data; the response labels them `scope: "client"` rather than pretending they belong to the portfolio.

**Conversation.** Notes via the existing notes read (`as_of` applied) and commitments from the repo, labelled client level, newest first with a limit that the response states.

**UI.** A `Tabs` control on `PortfolioPage` with the existing page as the first tab and the Call sheet as the second; sections are cards headed by the question. Data loads with the tab.

## Risks / Trade-offs

- [Joining every position reads one file per held instrument, up to a few dozen] → the files are small and local; one request per tab open; if slow, add a store-level batch read, not a cache.
- [An older outlook is mistaken for a current view] → every entry shows its own date and a marker when older than `as_of`.
- [Dependency order: sections 2 and 3 need the other two changes] → each degrades to a gap when its data is absent; applying this change last is the plan, not a runtime requirement.
- [Client-level notes and needs shown on a portfolio page for a multi-portfolio client] → labelled client level, and notes tied to a breach appear in the mandate section only through the mandate reconciliation attribution.
- [The sheet repeats information from other pages] → it adds links to the source rather than copies of the detail pages, and it is the only place that lists every position's bank view.

## Open Questions

- Whether the tab should be reachable from the client route and the overview action list by a direct link (a UI routing detail that does not change the API or tasks).
