# Spec Delta

## Purpose

Gives the bank one dated, evidence-bound analysis and outlook per instrument, set in the context of its sector, region and the market at that date, computed once and independent of clients and portfolios.

## ADDED Requirements

### Requirement: Outlook per held instrument and date
The system SHALL, given an `as_of`, produce one instrument outlook for each instrument held in any portfolio at that date, and SHALL produce an outlook for an explicitly requested instrument. Each outlook SHALL contain the instrument's reference data, its price path across the available snapshots, the events relevant to it, the market views it relied on, and a view with direction, horizon, confidence, rationale, drivers, risks and what would change it, without a numeric price forecast.

#### Scenario: Held instruments covered
- **WHEN** instrument outlooks are produced for as_of 2026-08-26
- **THEN** one outlook exists for every instrument held in any portfolio at that date and none for an instrument held nowhere

#### Scenario: Instrument without price
- **WHEN** an instrument has no price at the as_of
- **THEN** its outlook has status `insufficient_data`, no view and a gap, and no model is called for it

### Requirement: Sector, region and market context
An instrument outlook SHALL relate the instrument to its peers (same sector or sub-asset class, and region) using computed price changes over the same snapshots, and to the market outlook of the same date, whose relevant segment views SHALL be copied into the outlook by the system.

#### Scenario: Relative performance
- **WHEN** an instrument and peers in its sector have prices at the same snapshots
- **THEN** the outlook cites computed price changes for the instrument and the peer group

#### Scenario: Market context copied
- **WHEN** the market outlook for the date rates equities `positive`
- **THEN** the outlook of an equity instrument shows the equity segment as `positive` exactly as in the market outlook

#### Scenario: Market outlook missing
- **WHEN** no market outlook exists for the date or earlier
- **THEN** instrument outlooks are produced with status `partial` and a gap stating the market context was unavailable

### Requirement: Relevant events as reasons
The system SHALL offer the model the events dated on or before `as_of` that match the instrument by region, sector, asset class, sub-asset class, name or underlying reference, showing what each matched on. Events SHALL be usable and cited as reasons, weighted by their severity, and an event the model cites SHALL be one that was returned.

#### Scenario: Gold instrument
- **WHEN** an outlook is produced for a gold-linked instrument and gold events exist before the as_of
- **THEN** those events are offered as relevant and a driver cites at least one of them

#### Scenario: Unrelated event
- **WHEN** an event matches neither the instrument's region nor any of its attributes
- **THEN** it is not offered as relevant

#### Scenario: Invented event
- **WHEN** a driver cites evidence of an event that was not returned in the run
- **THEN** the driver is removed and a gap is recorded

### Requirement: Computed once, shared by all
The system SHALL compute an instrument's outlook once per `as_of`, store it in one file, and carry it forward without a model call when its inputs (latest price snapshot, relevant events, the market outlook used) equal those of the previous outlook or of an existing outlook for the same date. Running the stage again for the same inputs SHALL produce no new model calls.

#### Scenario: Rerun
- **WHEN** the instrument stage is run twice for the same as_of and data
- **THEN** the second run calls no model and leaves the files unchanged

#### Scenario: Two portfolios hold the instrument
- **WHEN** two portfolios of different clients hold the same instrument
- **THEN** exactly one outlook for it exists for that date

#### Scenario: New event for one instrument
- **WHEN** a new relevant event exists for one instrument since the previous outlook
- **THEN** only the outlooks of instruments for which it is relevant are regenerated

### Requirement: Changes explained
An instrument outlook SHALL state its change against the previous outlook of the same instrument (`new`, `unchanged`, `upgraded`, `downgraded`) with the previous direction and a reason citing evidence new since the previous as_of; code SHALL derive the kind and previous direction, and a direction change without new evidence SHALL be reverted with a gap.

#### Scenario: Downgrade after an event
- **WHEN** an airline's view moves from `neutral` to `negative` and cites an event dated after the previous as_of
- **THEN** the outlook is `downgraded` with previous direction `neutral` and that event as the reason

### Requirement: Point-in-time and evidence-bound
An instrument outlook SHALL use only data dated on or before its as_of and a previous outlook with a strictly earlier as_of, every driver and risk SHALL cite evidence of the same run, and figures SHALL equal values in the cited evidence. Confidence SHALL be capped at `low` when the price history is insufficient and at `medium` when neither an event nor a peer comparison supports the view.

#### Scenario: Short history
- **WHEN** the risk statistics are unavailable for lack of history
- **THEN** the view's confidence is `low` and the outlook states which statistics were unavailable

#### Scenario: Uncited number
- **WHEN** a driver states a percentage absent from the cited evidence
- **THEN** the driver is removed and the outlook is at most `partial`

### Requirement: No client data
Instrument outlooks SHALL contain no client, portfolio or position-size information.

#### Scenario: Output content
- **WHEN** an instrument outlook file is inspected
- **THEN** it contains no client id, portfolio id, client name or quantity

### Requirement: Always delivered and persisted
Each instrument SHALL receive an outlook file whatever happens: failures, denials and unparsable output SHALL appear as gaps with the previous view carried forward when one exists. The files SHALL be written under the as_of's outlook folder with evidence, a run summary listing each instrument's status, and an audit log.

#### Scenario: One instrument fails
- **WHEN** the model fails for one instrument
- **THEN** that instrument's outlook is `partial` with a gap, all other instruments are unaffected and the summary lists the status of each
