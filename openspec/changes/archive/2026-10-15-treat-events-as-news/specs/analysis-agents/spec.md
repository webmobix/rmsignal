# Spec Delta

## ADDED Requirements

### Requirement: Events are valid reasons
Agents SHALL treat events and news returned by tools as established facts, SHALL use them to explain market and price movements, SHALL cite them as evidence and SHALL weigh their stated severity. Agents SHALL NOT attribute a movement to an event that no tool returned.

#### Scenario: Movement explained by an event
- **WHEN** an agent explains a rise in oil-linked prices and an event dated before `as_of` describes a supply disruption
- **THEN** the finding cites that event's evidence id

#### Scenario: No supporting event
- **WHEN** no returned event relates to a movement
- **THEN** the report gives no event-based cause for it

### Requirement: Reading news is not a gap
A run that reads news or events SHALL NOT record a missing-news gap because no external news feed exists.

#### Scenario: Analysis that reads news
- **WHEN** an analyst calls the news tool and receives event-log items
- **THEN** the report contains no `no_data` gap for the news tool
