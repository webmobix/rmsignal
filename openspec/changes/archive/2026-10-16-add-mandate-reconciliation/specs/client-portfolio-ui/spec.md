# Spec Delta

## MODIFIED Requirements

### Requirement: Portfolio list on the client
Below the summary the client route SHALL list the client's portfolios with name, mandate, service model, AuM, change since the previous snapshot and mandate status, each row linking to the portfolio view. Custody accounts SHALL show "no mandate" and not a pass. An out-of-band portfolio SHALL show the reconciliation status of its breaches (for example "waiver claimed") with the note ids behind it.

#### Scenario: Open portfolio
- **WHEN** the user selects a portfolio row
- **THEN** the portfolio view opens

#### Scenario: Single portfolio
- **WHEN** a client has one portfolio
- **THEN** the list shows one row and the page layout is unchanged

#### Scenario: Waiver claimed
- **WHEN** a portfolio's breach is `client_directed` on note N-010
- **THEN** the row shows the breach as out of band with "waiver claimed (N-010)" and the breach is not shown as a pass

#### Scenario: No note
- **WHEN** a breach has status `no_note`
- **THEN** the row shows the plain out-of-band state with no reconciliation label

### Requirement: Portfolio view
The portfolio route SHALL show the header, AuM history, mandate bands as min-target-max ranges with the actual weight marked, the reconciliation status of each breach with the quoted note, holdings with weight, value, unrealised P&L and liquidity tier, and the LTV history against the margin trigger where a facility exists. Instrument ids SHALL link to the instrument view.

#### Scenario: Out of band
- **WHEN** a weight is outside its band
- **THEN** the band is marked and states weight and limit

#### Scenario: Exclusion breach
- **WHEN** a Sustainable Balanced portfolio holds an excluded instrument
- **THEN** the view lists the instrument and its weight as an exclusion breach with its reconciliation status

#### Scenario: Waiver is a claim
- **WHEN** a breach is `client_directed` with a claimed waiver
- **THEN** the note is quoted as the RM's statement and the breach is still marked
