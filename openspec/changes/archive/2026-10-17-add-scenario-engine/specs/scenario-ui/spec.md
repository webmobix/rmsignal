## MODIFIED Requirements

### Requirement: Scenario result layout
For the selected scenario the tab SHALL show best, likely and worst cases as a range with change in percent and USD, the share of wealth reached and untouched holdings, the scenario summary, the portfolio summary, the premise, the event it mirrors, the horizon, collateral effects and mandate bands crossed per case, and the per-position table with channels. Each headline figure SHALL offer its explainer.

#### Scenario: Selected scenario
- **WHEN** the user picks a scenario
- **THEN** all listed parts render from the API payload, with the three cases visible together

#### Scenario: Explainer
- **WHEN** the user opens the explainer of the likely change
- **THEN** the text states how the figure was derived

### Requirement: Placeholder marking
Scenario results with `status: "placeholder"` SHALL be marked "Illustrative, not computed". Computed results SHALL carry a banner stating that cases are conditional on the scenario, the likely case is a central case and not a probability, and the horizon. Gaps and `partial` status SHALL be visible. Neither banner SHALL use alarm styling that implies a real breach.

#### Scenario: Computed banner
- **WHEN** a computed result is shown
- **THEN** the conditional, not-a-probability banner and horizon are visible

#### Scenario: Banner
- **WHEN** a placeholder result is shown
- **THEN** the "Illustrative, not computed" banner is visible and breach colours are neutral

## ADDED Requirements

### Requirement: Scenario comparison
The tab SHALL offer a side-by-side comparison of the likely and worst case across all scenarios for the client.

#### Scenario: Compare
- **WHEN** the user opens the comparison
- **THEN** each scenario shows likely and worst change in percent and USD
