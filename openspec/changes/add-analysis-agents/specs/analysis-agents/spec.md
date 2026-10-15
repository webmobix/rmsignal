# Spec Delta

## Purpose

Defines the cooperating agents that produce evidence-based relationship, portfolio and instrument analysis for a chosen date, in batch and interactive use.

## ADDED Requirements

### Requirement: Agent hierarchy
The Relationship Analyst SHALL be able to delegate to the Portfolio Analyst, and the Portfolio Analyst to the Instrument Analyst, with each returning a report in the shared report contract.

#### Scenario: Delegation chain
- **WHEN** a relationship analysis is requested for a client
- **THEN** the relationship report includes findings whose evidence originates from portfolio and instrument analyses

### Requirement: Evidence-based claims
Every finding SHALL cite evidence ids of tool results produced in the same run, and every number in agent output SHALL equal a value in a cited result.

#### Scenario: Uncited number
- **WHEN** an agent output contains a figure absent from all cited evidence
- **THEN** the claim is removed, a gap is recorded, and the report status is at most `partial`

### Requirement: Always delivered
Every run SHALL return a report, never an unhandled error. Tool failures, missing data and policy denials SHALL appear as gaps, and status SHALL be `complete`, `partial` or `insufficient_data`.

#### Scenario: Tool failure
- **WHEN** a tool raises an error during a run
- **THEN** a report is returned with status `partial` naming the failed tool

#### Scenario: No data at as_of
- **WHEN** `as_of` precedes all data
- **THEN** a report with status `insufficient_data` is returned

### Requirement: Honest uncertainty
Agents SHALL state data-quality flags and limits that affect a conclusion and SHALL NOT infer relationships, persons or news that tools did not return.

#### Scenario: No related-party data
- **WHEN** a relationship analysis is run
- **THEN** the report states that related-party data was unavailable rather than listing inferred parties

### Requirement: Reproducible by date
A run SHALL be parameterised by subject and `as_of`, and with the same model outputs SHALL produce the same evidence ids.

#### Scenario: Historical run
- **WHEN** an analysis is run for as_of 2026-03-31
- **THEN** no evidence is derived from sources dated after 2026-03-31

### Requirement: Batch execution
The system SHALL run an analysis for a list of clients at an `as_of` and persist one report per client plus a run summary of statuses.

#### Scenario: Twenty clients
- **WHEN** a batch is run for all clients
- **THEN** 20 reports are persisted and the summary counts each status

### Requirement: Interactive execution
The same agents SHALL be usable in an interactive session identified by a thread id whose state persists across turns.

#### Scenario: Follow-up question
- **WHEN** a user asks a follow-up in an existing thread
- **THEN** the agent uses earlier evidence of that thread and keeps the original `as_of` unless changed explicitly

### Requirement: Provider-neutral model access
Models SHALL be accessed through a configurable gateway endpoint and model name, with no provider-specific behaviour in agent logic.

#### Scenario: Swap model
- **WHEN** the configured model name changes
- **THEN** agents run unchanged
