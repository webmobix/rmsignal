# Proposal

## Why

When a client calls, the RM needs one place on the portfolio screen that answers what the client will ask: how am I doing and why, am I within my mandate, what do I own, what does the bank think of it, what is happening in the market, how is my cash, and what did we last agree. Today these answers are spread over the portfolio page, the client report, the instrument pages, the market page and the notes, and the bank's own views (market and instrument outlooks) reach the RM only for the largest positions through the analysis text.

## What Changes

- Add `GET /api/portfolios/{id}/call-sheet`: a read-only assembly of persisted output for one portfolio and date, with seven sections, each carrying its own gaps:
  1. **Performance:** value, change since the previous snapshot, position-level contributors to the change, and the report findings and events that explain it.
  2. **Mandate:** bands, position limits and exclusion breaches with their mandate-reconciliation status, the RM notes quoted, and the open actions linked to the portfolio.
  3. **What I own:** the sector exposure, direct and look-through.
  4. **What the bank thinks:** for **every** position, the instrument outlook (direction, horizon, confidence, reasons, dated) and the market-outlook segment views copied into it; a position without an outlook is listed as "no outlook".
  5. **What is happening:** events up to `as_of` that match the holdings, with what each matched on.
  6. **Cash and credit:** the portfolio's credit facilities and LTV headroom, and the client's liquidity against planned cash needs and commitments.
  7. **Last time we spoke:** the client's latest notes and open commitments.
- Add a **Call sheet** tab on the portfolio route that presents the sections as the questions above, with links to the instrument, event and note behind each figure.
- Outlooks are worded as "the bank's view as of <outlook date>" and never as advice; an outlook older than `as_of` is shown with its own date.
- Static: no model call, no Q&A box, no new batch stage. The sheet is computed on request from the seeded database and persisted batch output.
- This change **depends on** `add-portfolio-sector-exposure` (section 3) and `add-mandate-reconciliation` (section 2); it is applied after both. Until their data exists, those sections show a gap and the rest of the sheet still renders.

## Capabilities

### New Capabilities

- `portfolio-call-sheet-api`: the call-sheet endpoint and the rules for joining positions to outlooks, events and notes.
- `portfolio-call-sheet-ui`: the Call sheet tab on the portfolio route.

### Modified Capabilities

None. Existing portfolio detail, instrument, market and overview requirements are unchanged; `MeetingPrep` on the overview (what falls due across the RM's clients) stays as it is.

## Impact

- Code: new `src/rm_dashboard/api/callsheet.py` (router, models, assembly) reading `ctx.repo`, `ctx.outlooks`, `ctx.overviews` and the existing relevance matching in `outlook/relevance.py`; `dashboard-ui/src/features/portfolios/` (tab and section components), regenerated `schema.ts`.
- API: one new read-only endpoint; no change to existing responses.
- Data and batch: none added. Reads outlooks, reports, reconciliations, mandate reconciliation, actions and notes already persisted or seeded.
- Docs: `docs/api.md`.
- Out of scope: live Q&A, model-written talking points, printing or export, any recommendation or suitability statement.
