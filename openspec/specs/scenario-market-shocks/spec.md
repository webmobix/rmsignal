# scenario-market-shocks Specification

## Purpose

TBD - created by archiving change add-scenario-engine. Update Purpose after archive.

## Requirements

### Requirement: Market shock vector per scenario and date
Given a scenario and an `as_of`, the system SHALL produce one market shock vector with, for each market segment or channel present in the data, a best, likely and worst percentage move over the scenario horizon. A vector SHALL contain no move for a single instrument.

#### Scenario: Vector produced
- **WHEN** a shock vector is requested for "Gulf deterioration" at 2026-08-26
- **THEN** each channel carries best, likely and worst moves and the horizon

#### Scenario: Single stock excluded
- **WHEN** the model returns a move keyed to a single instrument
- **THEN** that move is removed and a gap is recorded

### Requirement: Ordered cases
For every channel the system SHALL enforce worst <= likely <= best in value terms. A violating channel SHALL be corrected only by code reordering the three stated values, and a gap SHALL record it.

#### Scenario: Misordered
- **WHEN** the model returns likely above best for a channel
- **THEN** the values are reordered, a gap is recorded and the status is at most `partial`

### Requirement: Evidence and explainer per move
Each channel move SHALL carry a rationale, an explainer in plain language and citations to evidence produced in the same run. A move citing no run evidence SHALL be removed with a gap. A move SHOULD be anchored to a comparable past event from the event log when one exists, and SHALL say when none exists.

#### Scenario: Uncited move
- **WHEN** a channel move cites no evidence of this run
- **THEN** it is removed and a gap is recorded

#### Scenario: No comparable event
- **WHEN** no past event resembles the scenario
- **THEN** the move states that it is not anchored to history

### Requirement: Point-in-time only
A vector for an `as_of` SHALL use only market data and events dated on or before it.

#### Scenario: Historical date
- **WHEN** a vector is built for 2026-03-31
- **THEN** no evidence dated later is used

### Requirement: Scenario summary
Each vector SHALL carry a short summary of the scenario's market effect and a not-a-probability statement.

#### Scenario: Summary present
- **WHEN** a vector is returned
- **THEN** it has a summary and states that cases are conditional on the scenario, not probabilities

### Requirement: Always delivered
A run SHALL return a vector object. Model failure or unusable output SHALL yield status `partial` or `insufficient_data` with gaps, never an invented vector.

#### Scenario: Model failure
- **WHEN** the model raises an error
- **THEN** a result with no channels, status `insufficient_data` and a gap naming the failure is returned
