# Tasks

## 1. Endpoint skeleton and independent sections

- [x] 1.1 Add `api/callsheet.py` with the router, response models and a builder runner that turns a builder failure into a section gap; register it in the app; verify with API tests for an unknown id (404), a full portfolio, and a forced builder failure leaving the other sections intact
- [x] 1.2 Build the performance section (value, change, top contributors, report findings concerning the portfolio, events between snapshots); verify with tests that contributors equal the holdings data and that a missing report gives a gap and an empty findings list
- [x] 1.3 Build the cash-and-credit and conversation sections (facilities, client-level liquidity, needs and commitments labelled `client`, notes newest first up to `as_of`); verify with tests for a facility, client-level labels, point-in-time notes (a later note excluded) and no notes without a gap

## 2. Bank view and events

- [x] 2.1 Build the bank-view section joining every position to its instrument outlook (`as_of` or the latest earlier, marker for older, `outlook: null` plus `outlook_missing` gap otherwise, market segment views copied); verify with tests for all positions listed, a missing outlook, an older outlook and stored market views shown unchanged
- [x] 2.2 Build the events section with `relevant_events` per held instrument, grouped by event with matched attribute and concerned instruments, excluding events after `as_of`; verify with tests for an energy event matching an energy instrument and a later event excluded
- [x] 2.3 Check against the seeded data and committed outlooks at 2026-08-26 that every position of PF-0009 and PF-0017 is listed and the ones without outlook are explicit; verify with a test over those portfolios

## 3. Sections from the sibling changes

- [x] 3.1 Build the ownership section from the sector-exposure function of `add-portfolio-sector-exposure` (gap when unavailable); verify with a test that both views equal the portfolio detail's sector exposure
- [x] 3.2 Build the mandate section: bands, position limit and exclusion breaches, mandate-reconciliation status and quoted notes from `add-mandate-reconciliation` output, linked open actions, custody statement; verify with tests for a waiver-claimed breach (note quoted, breach still marked), `no_note` (no label, no gap), no mandate reconciliation file (gap) and a custody portfolio
- [x] 3.3 Regenerate the OpenAPI schema and `dashboard-ui/src/api/schema.ts` and document the endpoint in `docs/api.md`; verify the type check passes and the doc lists all sections

## 4. Call sheet tab

- [x] 4.1 Add the tabs to `PortfolioPage.tsx` (existing page first) and the Call sheet container with loading and error states, loading data when the tab opens; verify with a test that the other tab keeps working when the request fails
- [x] 4.2 Add the section components in order with the question headings, links to instrument, event and note, the as-of date and per-section gaps; verify with component tests for ordering, links and a section gap
- [x] 4.3 Add the bank-view rows with "Bank view as of <date>" wording, "no outlook" rows, the older-outlook marker and no recommendation wording; verify with tests for each of the three row kinds and a text check that no recommendation phrasing is rendered
- [x] 4.4 Add the mandate rows with the status and the quoted note, a claimed waiver shown as a claim to verify and never as a pass; verify with a component test
- [x] 4.5 Run the dashboard against the seeded database and look at PF-0009, PF-0007 and PF-0017 at laptop width; verify the sections render, nothing scrolls horizontally and there are no console errors

## 5. Integration

- [x] 5.1 Run the full pipeline on the sample database with the other two changes applied and open the call sheet of a multi-portfolio client; verify each section shows data or a named gap
- [x] 5.2 Run the Python test suite and the dashboard tests, lint and type check; verify all pass
