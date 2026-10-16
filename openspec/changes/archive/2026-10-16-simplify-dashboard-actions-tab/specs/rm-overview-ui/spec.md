## MODIFIED Requirements

### Requirement: Overview page
The home route SHALL show the RM's overview for the latest date: a metric strip (clients, total AuM, actions, counts per importance tier), the model summary and themes when present, and a table of urgent actions. The tier counts SHALL link to the Actions page filtered to that tier, so that medium and low actions, which the home page does not list, remain one click away.

#### Scenario: Latest run
- **WHEN** the overview loads on the 2026-08-26 data
- **THEN** it shows 20 clients, 33 actions and the tier counts, with the status "partial" visible

#### Scenario: Tier count link
- **WHEN** the user selects the "medium" count in the metric strip
- **THEN** the Actions page opens filtered to the medium tier

## REMOVED Requirements

### Requirement: Action list
**Reason**: Filters and the data-quality lane move to the Actions page; the home page lists urgent actions only.
**Migration**: See "Urgent action list" below and the `actions-ui` capability.

## ADDED Requirements

### Requirement: Urgent action list
The home page SHALL list only urgent actions: those with importance `critical` or `high` and horizon `immediate`, excluding the `data_quality` category. The list SHALL show rank, title, client, category, importance and horizon, SHALL NOT offer tier or category filters, and SHALL NOT show the data-quality lane. Below the list it SHALL state how many further actions exist and link to the Actions page.

#### Scenario: Only urgent actions
- **WHEN** the overview holds a high action with horizon `within_30_days`, a critical action with horizon `immediate` and a medium action with horizon `immediate`
- **THEN** only the critical immediate action is listed

#### Scenario: Nothing urgent
- **WHEN** no action is urgent
- **THEN** the list shows an empty notice and still links to the Actions page

#### Scenario: See the rest
- **WHEN** 28 of 33 actions are not urgent
- **THEN** a link reading "28 more actions" opens the Actions page

#### Scenario: Data quality hidden
- **WHEN** a `data_quality` action is critical with horizon `immediate`
- **THEN** it is not listed on the home page
