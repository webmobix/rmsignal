# Spec Delta

## MODIFIED Requirements

### Requirement: Structured domain tools
The system SHALL provide tools for relationships, persons, clients, portfolios, positions, instruments, market data, events and news, notes, credit and cash needs, each returning the evidence envelope and each requiring `as_of`.

#### Scenario: Positions at a date
- **WHEN** the positions tool is called for a portfolio with `as_of` 2026-06-30
- **THEN** positions of the 2026-06-30 snapshot are returned with sources

#### Scenario: News from the event log
- **WHEN** the news tool is called and events dated on or before `as_of` exist
- **THEN** it returns those events as news items with date, type, region, description, transmission, severity and the source name `event_log`, with status `ok`

#### Scenario: News unavailable
- **WHEN** the news tool is called and no event is dated on or before `as_of`
- **THEN** it returns `no_data` with a reason stating that no news exists up to that date

#### Scenario: No look-ahead in news
- **WHEN** an event is dated 2026-08-05 and the news tool is called with `as_of` 2026-08-01
- **THEN** that event is not returned
