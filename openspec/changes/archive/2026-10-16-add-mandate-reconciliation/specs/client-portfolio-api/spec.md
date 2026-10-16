# Spec Delta

## MODIFIED Requirements

### Requirement: Portfolio list on the client
Each entry of `portfolios` SHALL carry id, name, mandate code and name, service model, base currency, AuM at `as_of`, change since the previous snapshot, a mandate status (`in_band`, `out_of_band`, or `no_mandate` for custody accounts) and, when a mandate reconciliation exists for the date, the reconciliation status of each breach with the ids of the notes it rests on.

#### Scenario: Custody account
- **WHEN** a client holds a custody portfolio
- **THEN** its mandate status is `no_mandate` and it is still included in the consolidated totals

#### Scenario: Reconciled breach
- **WHEN** a portfolio is out of band and its commodity breach is `client_directed` on note N-010
- **THEN** the entry lists that breach with status `client_directed` and note N-010

#### Scenario: No mandate reconciliation persisted
- **WHEN** no mandate reconciliation exists for the client and date
- **THEN** the reconciliation fields are empty and a gap states that none was persisted
