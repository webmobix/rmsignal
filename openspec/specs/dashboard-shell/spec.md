# dashboard-shell Specification

## Purpose
Defines the RMSignal app frame: Global WM Bank branding, the mocked RM identity, the design tokens, data fetching through TanStack Query against the read API, the shared loading, error, gap and placeholder states, reusable components and cross-linking.

## Requirements

### Requirement: Branding
The app SHALL be titled *RMSignal* and SHALL present the bank as *Global WM Bank* using a text mark. It SHALL NOT include the Julius Baer name, logo or assets.

#### Scenario: Top bar
- **WHEN** any page is shown
- **THEN** the top bar shows the Global WM Bank mark, the name RMSignal, and no Julius Baer name or logo

### Requirement: Mocked RM identity
The top bar SHALL show an avatar with the RM's initials, the RM's name and the role "Relationship Manager", loaded from `/api/rm`. The app SHALL have no sign-in, session or access control.

#### Scenario: Avatar
- **WHEN** `/api/rm` returns Priscilla Ong
- **THEN** the top bar shows the initials "PO", the name and the role

### Requirement: Design language
The app SHALL use the sample's visual system as Tailwind CSS v4 theme tokens: ivory canvas, deep navy ink, brick alert, muted blue-greys, Source Serif 4 for headings and Public Sans for text, flat surfaces with hairline rules and tabular numerals. The app SHALL be a single light theme.

#### Scenario: Tokens
- **WHEN** a component needs a colour or font
- **THEN** it uses a theme token and not a literal value

### Requirement: Latest point in time
The app SHALL fetch `/api/as-of` and use the latest date for every request, and SHALL show that date in the masthead of each page.

#### Scenario: Date shown
- **WHEN** the latest date is 2026-08-26
- **THEN** every page shows "26 Aug 2026" and every data request carries that `as_of`

### Requirement: Data fetching with TanStack Query
All server data SHALL be fetched through TanStack Query against the FastAPI `/api` through a single typed client, with query keys that include the `as_of`. Pages SHALL NOT use Server Functions or direct file access.

#### Scenario: Cached navigation
- **WHEN** the user returns to a page already visited
- **THEN** its data is served from cache and refreshed in the background

### Requirement: Loading, error, gap and placeholder states
Every data region SHALL render distinct loading, error, empty and gap states, SHALL list `gaps` returned by the API, and SHALL mark any payload with `status: "placeholder"` as "Illustrative, not computed".

#### Scenario: API down
- **WHEN** a request fails
- **THEN** the region shows an error with a retry action and the rest of the page remains usable

#### Scenario: Placeholder
- **WHEN** a payload has `status: "placeholder"`
- **THEN** a visible banner marks the region as illustrative

### Requirement: Reusable components
Recurring elements SHALL be implemented once as components: page header, metric strip, tier badge, data table, chart frame, side drawer, tabs, id link, empty and gap notice.

#### Scenario: Reuse
- **WHEN** two pages show a table of clients or actions
- **THEN** both use the shared data table component

### Requirement: Cross-linking
Every client, portfolio, instrument, evidence and finding identifier SHALL render as a link to its view or drawer.

#### Scenario: Follow an id
- **WHEN** the user selects `PF-0001` anywhere
- **THEN** the portfolio view for PF-0001 opens
