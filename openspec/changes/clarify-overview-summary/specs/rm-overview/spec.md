## MODIFIED Requirements

### Requirement: Optional model summary
The overview MAY include a summary and cross-client themes produced by one model call; every number in them SHALL equal a number in the actions it cites, and a failed or rejected summary SHALL leave the overview complete in all other respects with a gap recorded. The summary MAY mark each client it mentions as `[[<client_id>]]` and the action to take as `_<action>_`; every marked client id SHALL belong to an action given to the model, and client ids SHALL NOT count as figures.

#### Scenario: Model failure
- **WHEN** the summary model call fails
- **THEN** the ranked actions are still delivered, the summary is empty and the status is `partial`

#### Scenario: Model does not reorder
- **WHEN** the model output suggests a different order
- **THEN** the order is unchanged

#### Scenario: Marked clients and actions kept
- **WHEN** the summary reads "[[CL-0001]] _call before Friday's maturity_."
- **THEN** it is delivered unchanged and no figure in it is flagged

#### Scenario: Unknown client reference
- **WHEN** the summary marks a client id that is in none of the actions
- **THEN** the summary is removed, a `guard_removed` gap is recorded and the status is `partial`
