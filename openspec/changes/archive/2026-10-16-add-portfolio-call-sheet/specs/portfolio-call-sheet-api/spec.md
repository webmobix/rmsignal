# Spec Delta

## Purpose

Gives the RM everything needed to take a client call about one portfolio in one read-only response, assembled from persisted output without a model.

## ADDED Requirements

### Requirement: Call sheet endpoint
`GET /api/portfolios/{id}/call-sheet` SHALL return, for the portfolio and `as_of`, the sections performance, mandate, ownership, bank view, events, cash and credit, and conversation history, each with its own gaps, and SHALL NOT call a model or start any batch stage.

#### Scenario: Portfolio with full data
- **WHEN** a managed portfolio is requested on a date with a report, outlooks and notes
- **THEN** all seven sections are present

#### Scenario: Unknown portfolio
- **WHEN** the id does not exist at `as_of`
- **THEN** the response is 404

#### Scenario: A section cannot be built
- **WHEN** the data behind one section is missing
- **THEN** that section is empty with a gap naming what is missing and the other sections are returned unchanged

### Requirement: Performance and what drove it
The performance section SHALL contain the portfolio value and its change since the previous snapshot, the positions contributing most to the change by value, the report findings that concern the portfolio with their references, and the events dated between the two snapshots.

#### Scenario: Contributors
- **WHEN** a portfolio's value fell between two snapshots
- **THEN** the positions with the largest value change are listed with their amounts and the section's figures equal the holdings data

#### Scenario: No report persisted
- **WHEN** the client has no persisted report at `as_of`
- **THEN** the findings list is empty and a gap states that no report exists

### Requirement: Mandate status with what the RM has noted
The mandate section SHALL contain the asset-class bands, the position-limit check and the exclusion breaches, and for each breach its mandate-reconciliation status, the note ids and quoted note text it rests on, and the open actions linked to the portfolio. A custody portfolio SHALL state that it is not measured against a mandate.

#### Scenario: Waiver claimed
- **WHEN** a breach is `client_directed` on note N-010
- **THEN** the section shows the breach, the status, and N-010 quoted as the RM's statement, and does not show the breach as resolved

#### Scenario: Breach without a note
- **WHEN** a breach has status `no_note`
- **THEN** it is shown as a breach with no reconciliation label and without a gap

#### Scenario: Mandate reconciliation not persisted
- **WHEN** no mandate reconciliation exists for the client and date
- **THEN** breaches are shown without status and a gap states that none was persisted

#### Scenario: Custody portfolio
- **WHEN** the portfolio is a custody account
- **THEN** the section states that no mandate applies and lists no bands

### Requirement: Ownership by sector
The ownership section SHALL contain the portfolio's sector exposure in its direct and look-through views with the denominator and the unclassified share.

#### Scenario: Sector exposure available
- **WHEN** the portfolio has positions
- **THEN** both views are present and equal the sector exposure of the portfolio detail

#### Scenario: Sector exposure not available
- **WHEN** the sector exposure cannot be built
- **THEN** the section is empty and a gap states why

### Requirement: Bank view of every position
The bank-view section SHALL contain one entry for every position of the portfolio, joined by instrument id to the instrument outlook dated `as_of` or, if none, the latest earlier one, giving the direction, horizon, confidence, reasons, the outlook date and the market-outlook segment views copied into it. An entry without an outlook SHALL be listed with `outlook: null` and a gap, not omitted. Wording SHALL present each view as the bank's view as of its date and SHALL NOT state a recommendation.

#### Scenario: All positions listed
- **WHEN** a portfolio has twelve positions and nine have an outlook
- **THEN** twelve entries are returned, three with `outlook: null`

#### Scenario: Earlier outlook
- **WHEN** the latest outlook of an instrument is dated before `as_of`
- **THEN** the entry carries that date and is marked as older than `as_of`

#### Scenario: Market view copied, not recomputed
- **WHEN** an instrument outlook carries a market segment view
- **THEN** the entry shows that view exactly as stored

### Requirement: Events that match the holdings
The events section SHALL contain the events dated on or before `as_of` that match any held instrument by region, sector, asset class, sub-asset class, name or underlying reference, each with severity, date, what it matched on and the held instruments it concerns.

#### Scenario: Energy event
- **WHEN** an energy event is dated before `as_of` and the portfolio holds an energy instrument
- **THEN** the event is listed with the instrument and the matching attribute

#### Scenario: Later event
- **WHEN** an event is dated after `as_of`
- **THEN** it is not listed

### Requirement: Cash and credit
The cash-and-credit section SHALL contain the credit facilities secured on the portfolio with drawn amount, LTV, margin-call trigger and headroom, and the client's liquidity against planned cash needs and commitments, labelled as client level where it spans portfolios.

#### Scenario: Facility on the portfolio
- **WHEN** a facility is secured on the portfolio
- **THEN** its LTV, trigger and headroom at `as_of` are shown

#### Scenario: Client-level needs
- **WHEN** the client has planned cash needs
- **THEN** they are listed marked as client level with dates and amounts

### Requirement: Conversation history
The conversation section SHALL contain the client's notes dated on or before `as_of`, newest first, with id, date and quoted text, and the client's open commitments, marked as client level.

#### Scenario: Point in time
- **WHEN** the call sheet is requested for 2026-03-31 and a note is dated 2026-04-14
- **THEN** that note is not listed

#### Scenario: No notes
- **WHEN** the client has no notes up to `as_of`
- **THEN** the list is empty without a gap
