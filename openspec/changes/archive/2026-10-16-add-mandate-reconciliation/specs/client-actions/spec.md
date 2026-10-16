# Spec Delta

## MODIFIED Requirements

### Requirement: Actions for a single client
The system SHALL, given a client and `as_of`, produce actions using only that client's persisted report and, if present, that client's note reconciliation and mandate reconciliation for the same date.

#### Scenario: Other clients not used
- **WHEN** actions are produced for CL-0001
- **THEN** no finding or reconciliation result of another client is read or referenced

#### Scenario: No reconciliation file
- **WHEN** no reconciliation exists for the client and date
- **THEN** actions are produced from the report alone and a gap records that notes were not reconciled

#### Scenario: No mandate reconciliation file
- **WHEN** no mandate reconciliation exists for the client and date
- **THEN** actions are produced without it, every mandate action is treated as `no_note` and a gap records that mandate breaches were not reconciled with notes

### Requirement: Rubric-based importance
Each action SHALL have an importance of `critical`, `high`, `medium` or `low` defined by documented conditions (for example an overdue review is at least `high`; a client-stated contradiction with a material exposure is at least `medium`), so that equal conditions give equal importance in any client. For `mandate_drift`, the floor SHALL depend on the mandate-reconciliation status of the breach: `no_note` and `client_directed` at least `high`, `acknowledged` at least `medium`, `contradicted` `critical`; an exclusion breach SHALL be at least `high` whatever its status.

#### Scenario: Same condition, different clients
- **WHEN** two clients each have an overdue KYC review
- **THEN** both actions have the same importance

#### Scenario: Importance below rubric floor
- **WHEN** the agent proposes `low` for a condition whose rubric floor is `high`
- **THEN** importance is raised to the floor and recorded

#### Scenario: Breach nobody has discussed
- **WHEN** a band breach has status `no_note`
- **THEN** its action has importance at least `high`, the same as before mandate reconciliation existed

#### Scenario: Acknowledged breach
- **WHEN** a band breach has status `acknowledged`
- **THEN** its action is a follow-up with a floor of `medium`

#### Scenario: Contradicted breach
- **WHEN** a breach has status `contradicted`
- **THEN** its action has importance `critical`

#### Scenario: Excluded holding that is acknowledged
- **WHEN** an exclusion breach has status `acknowledged`
- **THEN** its action has importance at least `high`

## ADDED Requirements

### Requirement: Mandate actions reflect the reconciliation status
An action for a mandate, position-limit or exclusion breach SHALL link to the breach's mandate-reconciliation result and the notes it cites, and its wording SHALL follow the status: for `no_note` raise and resolve the breach, for `acknowledged` follow up the plan, for `client_directed` review the instruction and verify that any claimed waiver is on file, for `contradicted` correct the record with the client.

#### Scenario: Claimed waiver
- **WHEN** a breach is `client_directed` with a waiver claimed in note N-010
- **THEN** the action asks the RM to verify the waiver on file, links N-010 and keeps the breach visible

#### Scenario: Contradicted result not actioned
- **WHEN** the agent produces no action for a `contradicted` mandate result
- **THEN** the output lists it under `not_actioned`
