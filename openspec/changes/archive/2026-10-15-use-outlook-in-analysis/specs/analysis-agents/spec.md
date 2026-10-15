# Spec Delta

## MODIFIED Requirements

### Requirement: Agent hierarchy
The Relationship Analyst SHALL be able to delegate to the Portfolio Analyst, which returns a report in the shared report contract. The Portfolio Analyst SHALL obtain instrument-level analysis from the persisted instrument outlooks for the run's `as_of` and SHALL NOT run a separate instrument analysis for each position.

#### Scenario: Delegation chain
- **WHEN** a relationship analysis is requested for a client
- **THEN** the relationship report includes findings from portfolio analyses, and those findings' instrument evidence originates from the persisted instrument outlooks

## ADDED Requirements

### Requirement: Outlooks feed the analysis
Relationship and portfolio analyses SHALL be able to read the market outlook and, for portfolio analyses, the outlooks of held instruments for the run's `as_of`, and SHALL cite them as evidence like any other tool result. A claim that rests on an outlook SHALL be worded as the bank's view with its date and SHALL carry the house-view flag in the report.

#### Scenario: Position with an outlook
- **WHEN** a portfolio analysis covers a position whose instrument has an outlook for the as_of
- **THEN** a finding about the position cites the outlook evidence and the report carries the house-view flag

#### Scenario: Reasons remain cited
- **WHEN** a finding repeats the reason an outlook gives
- **THEN** it cites the event or price evidence behind that reason or the outlook result that carries it

### Requirement: Missing outlook is a gap
When no outlook exists for a position or the market at the run's `as_of`, the analysis SHALL still be delivered, SHALL record a `no_data` gap naming what is missing and SHALL NOT state a forward-looking view for it.

#### Scenario: Outlook stage not run
- **WHEN** a portfolio analysis runs and no instrument outlook files exist
- **THEN** the report has status `partial`, a gap per missing outlook and no forward-looking claim

### Requirement: Outlooks respect the run date
A run SHALL NOT use an outlook dated after its `as_of`. When only an earlier outlook exists, the analysis SHALL state the date it is effective from.

#### Scenario: Later outlook exists
- **WHEN** a run for as_of 2026-06-30 starts and an outlook for 2026-08-26 exists
- **THEN** the later outlook is not used

#### Scenario: Earlier outlook only
- **WHEN** a run for as_of 2026-08-26 finds only an outlook for 2026-06-30
- **THEN** the outlook is used with its effective date 2026-06-30 stated and a staleness gap
