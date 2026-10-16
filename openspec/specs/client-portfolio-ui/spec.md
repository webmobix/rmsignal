# client-portfolio-ui Specification

## Purpose
Defines the clients list, the client view with a consolidated summary across portfolios, the client portfolio list, portfolio health, actions and notes, snapshot comparison, and the portfolio view.

## Requirements

### Requirement: Clients list
The clients route SHALL list all clients in a sortable table with AuM, wealth band, risk profile, portfolio count, action count, highest tier, report status and KYC due, and a chart of AuM by client.

#### Scenario: Sort
- **WHEN** the user sorts by AuM
- **THEN** the rows reorder and the chart keeps the same order

### Requirement: Consolidated client summary
The client route SHALL open with a summary across all of the client's portfolios: total AuM and change since the previous snapshot, a stacked AuM-history chart by portfolio with event markers, combined allocation, currency exposure, largest positions with look-through, liquidity against commitments and planned cash needs, and credit headroom against the margin-call trigger.

#### Scenario: Multi-portfolio client
- **WHEN** a client with three portfolios is opened
- **THEN** the summary shows the total and a stacked history with three series

#### Scenario: Missing section
- **WHEN** the API lists gaps for the client or a section has no data
- **THEN** the gaps are listed once at the top of the page, the section without data shows an empty notice, and the other sections render normally

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

### Requirement: Portfolio health
The client route SHALL show a health view: concentration, mandate status, liquidity, credit and KYC each as a status with its figure and a link to the finding or evidence behind it.

#### Scenario: Evidence link
- **WHEN** the user selects a health item
- **THEN** the evidence drawer opens on the finding behind it

### Requirement: Client actions and notes
The client route SHALL list the client's actions and show the RM notes with their reconciliation verdict (consistent, contradicted, unverifiable).

#### Scenario: Contradicted note
- **WHEN** a note is contradicted
- **THEN** it is marked and the evidence for the verdict opens from it

### Requirement: Snapshot comparison
The client route SHALL let the user pick two snapshots and show AuM and P&L change per portfolio, positions added, removed and resized, and the events between the dates.

#### Scenario: Compare
- **WHEN** the user selects 2026-02-27 and 2026-03-31
- **THEN** the changes and the events between those dates are shown

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
