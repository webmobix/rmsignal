# client-actions Specification

## Purpose

Turns one client's analysis and note reconciliation into a short list of concrete next actions for the RM, each saying what and why, with category, importance, time horizon and links back to its evidence.

## Requirements

### Requirement: Actions for a single client
The system SHALL, given a client and `as_of`, produce actions using only that client's persisted report and, if present, that client's note reconciliation for the same date.

#### Scenario: Other clients not used
- **WHEN** actions are produced for CL-0001
- **THEN** no finding or reconciliation result of another client is read or referenced

#### Scenario: No reconciliation file
- **WHEN** no reconciliation exists for the client and date
- **THEN** actions are produced from the report alone and a gap records that notes were not reconciled

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
Each action SHALL have an importance of `critical`, `high`, `medium` or `low` defined by documented conditions (for example a breach or overdue review is at least `high`; a client-stated contradiction with a material exposure is at least `medium`), so that equal conditions give equal importance in any client.

#### Scenario: Same condition, different clients
- **WHEN** two clients each have an overdue KYC review
- **THEN** both actions have the same importance

#### Scenario: Importance below rubric floor
- **WHEN** the agent proposes `low` for a condition whose rubric floor is `high`
- **THEN** importance is raised to the floor and recorded

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
