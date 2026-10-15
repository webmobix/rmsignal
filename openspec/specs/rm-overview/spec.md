# rm-overview Specification

## Purpose

Gives each relationship manager one ranked, categorised list of the next actions across their clients for a chosen date, linked to the clients, reports and findings behind each action.

## Requirements

### Requirement: Overview per RM and date
The system SHALL, given an `as_of`, build one overview per RM from the client actions persisted for that date, covering exactly that RM's clients.

#### Scenario: Overview for a date
- **WHEN** an overview is requested for as_of 2026-08-26 and client actions exist
- **THEN** one overview per RM is returned with the as_of, the RM id and name, and the clients covered

#### Scenario: No client outputs
- **WHEN** no client actions exist for the date
- **THEN** an overview with status `insufficient_data`, no actions and a gap naming the missing folder is returned

### Requirement: Ranked and categorised
The overview SHALL contain all client actions, sorted by importance (`critical` first), then horizon, then due date, then client AUM descending, then client id, then title, with a rank number and its category, and SHALL provide the same actions grouped by category with counts.

#### Scenario: Ordering
- **WHEN** actions of mixed importance exist
- **THEN** every `critical` action precedes every `high` action and so on down to `low`

#### Scenario: Stable order
- **WHEN** the overview is built twice from the same inputs
- **THEN** the actions appear in the same order

### Requirement: What, why and links
Each overview action SHALL carry its title, `what`, `why`, category, importance, horizon, due date, client id and name, and links to the client report path, the findings and any note-reconciliation results it rests on, with evidence ids, all copied from the client action.

#### Scenario: Link integrity
- **WHEN** an overview is delivered
- **THEN** every linked report file and finding reference exists

#### Scenario: Content not rewritten
- **WHEN** an action appears in the overview
- **THEN** its `what`, `why`, category and importance equal those in the client action

### Requirement: Coverage of every client
Every client of the RM SHALL appear in the overview either through at least one action or in a list of clients without actions, which gives the reason (report missing, actions missing, no action needed).

#### Scenario: Missing actions file
- **WHEN** a client has a report but no actions file
- **THEN** the client is listed as `actions_missing` and a `data_quality` action for it is included

#### Scenario: Missing report
- **WHEN** a client has neither report nor actions
- **THEN** a `data_quality` action states the report is missing

### Requirement: Optional model summary
The overview MAY include a summary and cross-client themes produced by one model call; every number in them SHALL equal a number in the actions it cites, and a failed or rejected summary SHALL leave the overview complete in all other respects with a gap recorded.

#### Scenario: Model failure
- **WHEN** the summary model call fails
- **THEN** the ranked actions are still delivered, the summary is empty and the status is `partial`

#### Scenario: Model does not reorder
- **WHEN** the model output suggests a different order
- **THEN** the order is unchanged

### Requirement: Always delivered
The run SHALL return an overview with status `complete`, `partial` or `insufficient_data` without unhandled errors; gaps from client stages SHALL be carried into the overview.

#### Scenario: Client-stage gap
- **WHEN** a client's actions file has gaps
- **THEN** the overview records them with the client id and has status at most `partial`

### Requirement: Privacy
Names sent to a model for the summary SHALL be pseudonymised and restored only in the delivered overview.

#### Scenario: Names in model input
- **WHEN** the summary input is prepared
- **THEN** it contains pseudonyms and no real client names

### Requirement: Persisted and reproducible
The overview SHALL be written to `overview/<rm_id>.json` under the as_of folder, and the same inputs and model output SHALL produce identical content.

#### Scenario: Rerun
- **WHEN** the overview command is run twice with the stub model
- **THEN** the written files are identical
