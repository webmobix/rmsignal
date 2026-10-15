# agent-tools Specification

## Purpose

Defines the tool surface through which agents obtain structured data and calculations, so agents never touch raw files or compute figures themselves.

## Requirements

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

### Requirement: Analytics tools
The system SHALL expose each deterministic calculation as a tool that fetches its own inputs for the given scope and `as_of`, so agents pass identifiers, not numbers.

#### Scenario: Agent passes identifiers
- **WHEN** an agent requests concentration for a client
- **THEN** it supplies client id and `as_of` only, and receives computed figures with evidence

### Requirement: Agents have no direct data access
Agents SHALL have no tool or capability that reads source files or the database other than the defined tools.

#### Scenario: Tool inventory
- **WHEN** an agent's tool list is inspected
- **THEN** every tool is from the defined set and none accepts a file path or SQL

### Requirement: Narrow tool allow-lists
Each agent SHALL be configured with an explicit allow-list of tools, and calls outside it SHALL be refused.

#### Scenario: Out-of-scope call
- **WHEN** the Instrument Analyst attempts to call a credit tool not in its list
- **THEN** the call is refused and recorded

### Requirement: Free text is evidence, not computation
RM notes SHALL be returned as dated, quoted text with note id; values derived from text SHALL be flagged `derived_from_text` with the source quote.

#### Scenario: Waiver mention
- **WHEN** a note mentions a waiver
- **THEN** the note is returned as quoted evidence and no breach calculation changes because of it

### Requirement: Outlook read tools
The system SHALL provide read-only tools that return the persisted market outlook and the persisted outlook of one instrument for an `as_of`, each returning the evidence envelope with the outlook's effective date, its source file, and a house-view quality flag, and each making the evidence cited by the outlook resolvable in the run. The tools SHALL NOT start an outlook run and SHALL NOT accept a file path.

#### Scenario: Instrument outlook returned
- **WHEN** the instrument outlook tool is called for an instrument with an outlook for the as_of
- **THEN** the view, drivers and risks are returned with their evidence ids, the source file and a house-view flag

#### Scenario: No outlook
- **WHEN** the tool is called and no outlook exists on or before the as_of
- **THEN** it returns `no_data` with a reason naming the missing outlook

#### Scenario: Look-ahead refused
- **WHEN** only an outlook dated after the as_of exists
- **THEN** it is not returned

#### Scenario: Evidence resolvable
- **WHEN** an agent cites an evidence id listed in a returned outlook's drivers
- **THEN** the citation resolves in the run and the number guard can check figures against it
