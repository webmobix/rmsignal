# rm-overview-ui Specification

## Purpose
Defines the RM overview screen: metric strip, ranked and filterable next actions with a separate data-quality lane, the client matrix of AuM against urgency, the evidence drawer and meeting prep.

## Requirements

### Requirement: Overview page
The home route SHALL show the RM's overview for the latest date: a metric strip (clients, total AuM, actions, counts per importance tier), the model summary and themes when present, and the ranked next actions.

#### Scenario: Latest run
- **WHEN** the overview loads on the 2026-08-26 data
- **THEN** it shows 20 clients, 33 actions and the tier counts, with the status "partial" visible

### Requirement: Action list
The action list SHALL show rank, title, client, category, importance and horizon, SHALL be filterable by tier and category, and SHALL show the data-quality category as a separate lane so it does not crowd out client risks.

#### Scenario: Filter by tier
- **WHEN** the user selects the "high" tier
- **THEN** only high-importance actions remain and the other tiers show as dimmed counts

### Requirement: Client matrix
The overview SHALL include a matrix chart placing each client by AuM (horizontal, on a scale that copes with USD 8m to 88m) against urgency (vertical), coloured by top tier, with a tooltip of name, AuM and actions, and selecting a client SHALL open the client view. Clients without actions SHALL be shown at the baseline.

#### Scenario: Plot
- **WHEN** the matrix renders
- **THEN** all 20 clients appear once, and the clients without actions are on the baseline

#### Scenario: Open client
- **WHEN** the user selects a point
- **THEN** the client view for that client opens

### Requirement: Evidence drawer
Selecting an action SHALL open a drawer from the right showing what, why, category, importance, horizon and due date, the findings it rests on, the evidence behind each finding from `/api/evidence`, and links to the client, portfolio and instrument. The drawer SHALL close with Escape, the close control or a click outside, and SHALL be addressable by URL.

#### Scenario: Open and close
- **WHEN** the user selects an action and then presses Escape
- **THEN** the drawer opens with the action's evidence and closes again, leaving the list state unchanged

#### Scenario: Deep link
- **WHEN** the page is loaded with an action id in the URL
- **THEN** the drawer opens on that action

### Requirement: Meeting prep
The overview SHALL show the next 14 days as a panel: actions falling due, KYC reviews due or overdue, and the latest RM note per client, each linking to the client.

#### Scenario: Overdue KYC
- **WHEN** a client's KYC review is overdue
- **THEN** the panel shows it marked overdue with a link to the client
