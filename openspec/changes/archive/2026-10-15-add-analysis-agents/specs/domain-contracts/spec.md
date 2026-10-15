# Spec Delta

## Purpose

Defines the shared data shapes exchanged between data, tools, agents and other bank systems, including the evidence envelope that makes every result traceable.

## ADDED Requirements

### Requirement: Evidence envelope on every tool result
Every tool result SHALL carry its data, `as_of`, effective snapshot, status, a list of sources (dataset, key, snapshot date), the computation that produced it (tool, version, parameters, method), data-quality flags, and a stable `evidence_id` derived from its content.

#### Scenario: Deterministic evidence id
- **WHEN** the same tool is called twice with the same parameters and data
- **THEN** both results have the same `evidence_id`

#### Scenario: Different inputs
- **WHEN** the same tool is called with a different `as_of` that resolves to different data
- **THEN** the `evidence_id` differs

### Requirement: Tool status values
A tool result SHALL have status `ok`, `partial`, `insufficient_data`, `insufficient_history` or `no_data`, and a human-readable reason for any status other than `ok`.

#### Scenario: Unavailable domain
- **WHEN** persons are requested for a client and no person source is configured
- **THEN** the result status is `no_data` with a reason, not an empty `ok`

### Requirement: Entities for parties and relationships
The system SHALL define Party, Person and Relationship (typed, directed, with optional validity dates and a source) alongside Client, Portfolio, Position, Instrument and Event, so that richer sources can be added without changing consumers.

#### Scenario: Client as party
- **WHEN** a client is requested as a party
- **THEN** it is returned with kind individual or organisation, and its relationships list states that related-party data is unavailable

### Requirement: Report contract
An analysis report SHALL contain subject, `as_of`, status (`complete`, `partial` or `insufficient_data`), findings each with claim, confidence and one or more evidence ids, gaps, data-quality flags, policy decisions, and the producing agent.

#### Scenario: Finding without evidence
- **WHEN** a finding is built with no evidence id
- **THEN** it is rejected as invalid
