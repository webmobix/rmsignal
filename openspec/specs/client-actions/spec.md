# client-actions Specification

## Purpose

Turns one client's analysis and note reconciliation into a short list of concrete next actions for the RM, each saying what and why, with category, importance, time horizon and links back to its evidence.

## Requirements

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

### Requirement: Actions say what and why
Each action SHALL have a title, a `what` (the step for the RM) and a `why` (the reason grounded in the linked content).

#### Scenario: Action content
- **WHEN** a client has a single-name concentration finding
- **THEN** an action states the step to take and why, using figures from that finding

### Requirement: Fixed categories
Each action SHALL have exactly one category from: `compliance_kyc`, `concentration_risk`, `mandate_drift`, `liquidity_cash_needs`, `credit_collateral`, `client_contact`, `data_quality`.

#### Scenario: Unknown category
- **WHEN** the agent proposes a category outside the set
- **THEN** the action is removed and recorded as a gap

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

### Requirement: Time horizon derived from evidence
Each action SHALL have a horizon of `immediate`, `within_30_days`, `within_90_days`, `later` or `none`, computed from a due date found in the linked findings or evidence relative to `as_of`, and SHALL carry that `due_date` when one exists. A model-provided date or horizon SHALL NOT be used.

#### Scenario: KYC due in 96 days
- **WHEN** a linked finding states a KYC review due 96 days after as_of
- **THEN** the horizon is `later` (beyond 90 days) and the due date is shown

#### Scenario: Overdue
- **WHEN** the due date is before as_of
- **THEN** the horizon is `immediate`

#### Scenario: No date
- **WHEN** no linked content has a date
- **THEN** the horizon is `none` and no due date is shown

### Requirement: Links and grounded figures
Each action SHALL reference the report findings (client id, report path, finding reference) and any reconciliation results it rests on, with their evidence ids copied from those sources, and every number in `title`, `what` and `why` SHALL equal a number in the linked content.

#### Scenario: Broken link
- **WHEN** an action references a finding or note id that does not exist for the client
- **THEN** the action is removed and recorded as a gap

#### Scenario: Invented number
- **WHEN** an action states a figure absent from its linked content
- **THEN** the action is removed, a gap is recorded and the status is at most `partial`

### Requirement: Contradicted notes surface
A `contradicted` reconciliation result SHALL be covered by at least one action referencing it, or SHALL be listed in the output as not actioned.

#### Scenario: Contradicted note not actioned
- **WHEN** the agent produces no action for a contradicted note
- **THEN** the output lists that note under `not_actioned`

### Requirement: No duplicate actions
Actions of the same client and category whose linked sources overlap SHALL be merged into one with the union of links and the highest importance.

#### Scenario: Merge
- **WHEN** a contradicted note and a concentration finding lead to two concentration actions
- **THEN** one action remains with both sources linked

### Requirement: Always delivered and reproducible
The run SHALL return a result with status `complete`, `partial` or `insufficient_data` without unhandled errors, order actions deterministically (importance, horizon, due date, title), and write `actions/<client>.json`; the same inputs and model output SHALL give identical content.

#### Scenario: Model failure
- **WHEN** the model fails or returns unparsable output
- **THEN** a `partial` result with no model actions and a gap is returned

#### Scenario: Names
- **WHEN** model input is prepared
- **THEN** names are pseudonymised and restored only in the delivered output

### Requirement: Mandate actions reflect the reconciliation status
An action for a mandate, position-limit or exclusion breach SHALL link to the breach's mandate-reconciliation result and the notes it cites, and its wording SHALL follow the status: for `no_note` raise and resolve the breach, for `acknowledged` follow up the plan, for `client_directed` review the instruction and verify that any claimed waiver is on file, for `contradicted` correct the record with the client.

#### Scenario: Claimed waiver
- **WHEN** a breach is `client_directed` with a waiver claimed in note N-010
- **THEN** the action asks the RM to verify the waiver on file, links N-010 and keeps the breach visible

#### Scenario: Contradicted result not actioned
- **WHEN** the agent produces no action for a `contradicted` mandate result
- **THEN** the output lists it under `not_actioned`
