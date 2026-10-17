# scenario-run-pipeline Specification

## Purpose

TBD - created by archiving change add-scenario-engine. Update Purpose after archive.

## Requirements

### Requirement: Persisted results
The system SHALL persist each shock vector, portfolio impact, client roll-up and RM roll-up under the report folder of its `as_of`, with evidence, run summary and audit log. Persisting SHALL NOT alter any other date or scenario.

#### Scenario: Files written
- **WHEN** a scenario run completes for 2026-08-26
- **THEN** the vector, impacts, roll-ups, evidence, summary and audit log exist under that date's scenarios folder

### Requirement: Cache by inputs
Each run SHALL record a hash of its inputs (scenario text, horizon, as_of data, holdings snapshot, model). When the hash matches a stored result and regeneration is not forced, nothing SHALL be regenerated or model-called.

#### Scenario: Same inputs
- **WHEN** the same scenario and date are run again
- **THEN** no model call is made and files are unchanged

#### Scenario: Scenario text edited
- **WHEN** the premise text changes
- **THEN** the vector and all dependent impacts are regenerated

### Requirement: One portfolio and scenario at a time
The system SHALL run an impact for exactly one portfolio and one scenario per run unit, and SHALL provide a command that takes `as_of` and optional scenario and portfolio filters, running the missing units in parallel and resuming after interruption.

#### Scenario: Add a scenario
- **WHEN** a new scenario is added and the command is run
- **THEN** one vector and one impact per portfolio are produced, and existing results are untouched

#### Scenario: Resume
- **WHEN** a run is interrupted after some units finished
- **THEN** a rerun only produces the missing units

### Requirement: Failure isolation
A failure in one unit SHALL NOT prevent other units from completing, and SHALL appear as a gap and in the run summary.

#### Scenario: One portfolio fails
- **WHEN** the model fails for one portfolio
- **THEN** the other portfolios' results are written and the failed unit is listed

### Requirement: Policy and audit
Runs SHALL pass through the policy engine and record audit and LLM call logs like other agent runs.

#### Scenario: Audit present
- **WHEN** a run completes
- **THEN** the audit log lists run start and end and each tool call
