## Purpose
Defines the scenario tab on the client view: a picker fed by the backend and a result layout, clearly marked as illustrative placeholder content until real scenario results exist.

## ADDED Requirements

### Requirement: Scenario picker from the backend
The client route SHALL offer a scenario tab whose picker lists the scenario names returned by `/api/scenarios`. The UI SHALL contain no scenario names, premises or caveats of its own.

#### Scenario: Names from API
- **WHEN** the API returns a new scenario name
- **THEN** it appears in the picker without a UI change

### Requirement: Scenario result layout
For the selected scenario the tab SHALL show the headline change in percent and USD, the share of wealth reached and untouched holdings, the premise, the event it mirrors, the caveat, collateral effects, mandate bands crossed and the per-position table with channels.

#### Scenario: Selected scenario
- **WHEN** the user picks a scenario
- **THEN** all listed parts render from the API payload

### Requirement: Placeholder marking
Scenario results with `status: "placeholder"` SHALL be marked "Illustrative, not computed" in a banner above the result, and SHALL not use alarm styling that implies a real breach.

#### Scenario: Banner
- **WHEN** a placeholder result is shown
- **THEN** the banner is visible and breach colours are replaced by neutral ones
