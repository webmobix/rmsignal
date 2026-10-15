# Spec Delta

## Purpose

Defines the tool surface through which agents obtain structured data and calculations, so agents never touch raw files or compute figures themselves.

## ADDED Requirements

### Requirement: Structured domain tools
The system SHALL provide tools for relationships, persons, clients, portfolios, positions, instruments, market data, events and news, notes, credit and cash needs, each returning the evidence envelope and each requiring `as_of`.

#### Scenario: Positions at a date
- **WHEN** the positions tool is called for a portfolio with `as_of` 2026-06-30
- **THEN** positions of the 2026-06-30 snapshot are returned with sources

#### Scenario: News unavailable
- **WHEN** the news tool is called and no news source exists
- **THEN** it returns `no_data` and, separately, curated events dated on or before `as_of`

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
