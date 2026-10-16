## Purpose
The Actions page is the complete, filterable list of the RM's next actions, together with the data quality and coverage items that the dashboard leaves out.

## ADDED Requirements

### Requirement: Actions tab
The primary navigation SHALL include a top-level "Actions" tab opening `/actions`, which SHALL show the date in its masthead like every other page.

#### Scenario: Navigate
- **WHEN** the user selects "Actions" in the top bar
- **THEN** the Actions page opens and the tab is marked active

### Requirement: All actions with filters
The page SHALL list every client-risk action for the latest date (all tiers and horizons, excluding `data_quality`) with rank, title, client, category, importance, horizon and due date. It SHALL offer filters by tier, category and horizon, and the tier filter SHALL be held in the URL as `tier` so links and the back button restore it. Opening an action SHALL open the evidence drawer.

#### Scenario: Filter by tier from URL
- **WHEN** the page is loaded as `/actions?tier=low`
- **THEN** only low-importance actions are listed and the "low" filter is shown as selected

#### Scenario: Filter by horizon
- **WHEN** the user selects the horizon "Immediate"
- **THEN** only actions with horizon `immediate` remain

#### Scenario: Open evidence
- **WHEN** the user selects an action title
- **THEN** the evidence drawer opens over the Actions page

### Requirement: Data quality and coverage lane
The page SHALL show the `data_quality` actions in a separate lane below the main list, with its count, using the same table. The tier filter SHALL narrow it; the category and horizon filters SHALL NOT.

#### Scenario: Lane present
- **WHEN** the overview holds data-quality actions
- **THEN** the lane lists them apart from the client-risk list and shows their count

#### Scenario: Empty lane
- **WHEN** there are no data-quality actions
- **THEN** the lane shows "No data-quality items."
