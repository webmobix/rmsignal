# Spec Delta

## MODIFIED Requirements

### Requirement: Client actions and notes
The client route SHALL list the client's actions and show the RM notes with their reconciliation verdict (consistent, contradicted, unverifiable). The client's actions list SHALL NOT show a Client column, because the page is scoped to a single client.

#### Scenario: Contradicted note
- **WHEN** a note is contradicted
- **THEN** it is marked and the evidence for the verdict opens from it

#### Scenario: No Client column on the client's actions
- **WHEN** the Actions tab of a client is opened
- **THEN** the actions table shows rank, action, category, importance, horizon and due date, with no Client column

#### Scenario: Other action lists keep the Client column
- **WHEN** the Overview or the Actions page lists actions
- **THEN** the table still shows the Client column
