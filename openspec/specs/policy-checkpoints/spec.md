# policy-checkpoints Specification

## Purpose

Defines where policy decisions are requested during an analysis and how they are recorded, so real policy engines can be introduced later without changing agents or tools.

## Requirements

### Requirement: Policy decision interface
Policy checks SHALL go through one interface taking a checkpoint name and context and returning a decision of `allow`, `deny` or `escalate` with a reason and policy id. The initial implementation SHALL return `allow` with a reason stating that it is a mock.

#### Scenario: Mock decision
- **WHEN** any checkpoint is evaluated with the mock
- **THEN** the decision is `allow` and the reason identifies the mock

### Requirement: Checkpoint placement
The system SHALL request a decision at: request entitlement, tool-call authorisation, A2A inbound and outbound, PII minimisation before model calls, data freshness and point-in-time validity, suitability and mandate before any recommendation, evidence provenance of output, compliance content of output, and human approval before client-facing or action-proposing output.

#### Scenario: Run trace
- **WHEN** a run completes
- **THEN** the report's policy decisions list contains one entry per applicable checkpoint reached

### Requirement: Denials degrade gracefully
A `deny` SHALL block the guarded step only and be reported as a gap; an `escalate` SHALL pause the guarded step pending a human decision.

#### Scenario: Tool denied
- **WHEN** a tool-authorisation decision is `deny`
- **THEN** the tool is not executed, the run continues, and the report names the gap

### Requirement: Audit trail
Every decision, tool call and model call SHALL be written to an append-only audit record containing run id, agent, subject, `as_of`, a hash of inputs, evidence ids and decision details.

#### Scenario: Audit completeness
- **WHEN** a run finishes
- **THEN** each tool call in the run has an audit record

### Requirement: Personal data minimised before models
Client names and direct identifiers SHALL be replaced by stable pseudonyms in model input and restored only in the final report.

#### Scenario: Prompt content
- **WHEN** a prompt is sent to a model
- **THEN** it contains the pseudonym and not the client's name
