# point-in-time-data Specification

## Purpose

Provides the only read path that analysis code may use for wealth data, answering every query as of an explicit date and reporting how stale or unversioned the answer is.

## Requirements

### Requirement: As-of date is mandatory
Every query SHALL require an explicit `as_of` date and SHALL NOT supply a default. The system SHALL NOT read the wall clock when answering a query.

#### Scenario: Missing as_of
- **WHEN** a query is made without `as_of`
- **THEN** it is rejected with a validation error and no data is returned

#### Scenario: Same answer on any day
- **WHEN** the same query with `as_of` 2026-08-26 is run on two different calendar days
- **THEN** the results are identical

### Requirement: Snapshot resolution
For snapshot-dated data the system SHALL return the latest snapshot on or before `as_of`, together with `effective_snapshot_date` and the gap in days between `as_of` and that snapshot.

#### Scenario: Between snapshots
- **WHEN** `as_of` is 2026-02-01 and snapshots exist for 2025-12-31 and 2026-02-27
- **THEN** holdings of 2025-12-31 are returned with `effective_snapshot_date` 2025-12-31 and a gap of 32 days

#### Scenario: Before first snapshot
- **WHEN** `as_of` is earlier than every snapshot
- **THEN** the result has status `insufficient_data` and no rows

### Requirement: Event-dated data has no look-ahead
Transactions, events and RM notes SHALL be returned only if their own date is on or before `as_of`. Planned cash needs and commitments have no knowledge date; they SHALL be treated as known since the start of the client relationship, returned from that date onwards, and flagged as assumed.

#### Scenario: Later note excluded
- **WHEN** a note is dated 2026-08-19 and `as_of` is 2026-08-01
- **THEN** the note is not returned

#### Scenario: Needs without a knowledge date
- **WHEN** a planned cash need has no creation date and the client relationship began on or before `as_of`
- **THEN** the need is returned with a flag stating it is assumed known since the relationship start

### Requirement: Unversioned attributes are labelled
Attributes without history (risk profile, mandate, KYC review date, tax domicile, benchmark) SHALL be returned tagged `pit: current_only`.

#### Scenario: Historical as_of
- **WHEN** a client is requested with `as_of` 2026-03-31
- **THEN** the risk profile is returned tagged `current_only`

### Requirement: Dataset snapshot columns are normalised
Per-date column groups in the source (AUM, prices, facility figures) SHALL be exposed as one row per entity and snapshot date.

#### Scenario: Price history
- **WHEN** the prices of an instrument are requested
- **THEN** one row per snapshot date is returned

### Requirement: Known data traps become quality flags
The system SHALL flag, rather than silently correct or hide, known dataset issues: stale valuation dates, missing cost basis, positions that appear between snapshots and bond quantities expressed in units of 100 nominal.

#### Scenario: Stale mark
- **WHEN** a holding has a `valuation_date` earlier than its snapshot date
- **THEN** the row carries a `stale_mark` flag stating both dates

#### Scenario: Missing cost basis
- **WHEN** a holding has no cost basis
- **THEN** it carries a `missing_cost_basis` flag and is excluded from P&L figures, which state the exclusion
