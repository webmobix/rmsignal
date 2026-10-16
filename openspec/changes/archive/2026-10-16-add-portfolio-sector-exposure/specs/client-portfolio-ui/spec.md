# Spec Delta

## MODIFIED Requirements

### Requirement: Portfolio view
The portfolio route SHALL show the header, AuM history, mandate bands as min-target-max ranges with the actual weight marked, a sector exposure chart with a direct / look-through toggle, holdings with weight, value, unrealised P&L and liquidity tier, and the LTV history against the margin trigger where a facility exists. Instrument ids SHALL link to the instrument view.

#### Scenario: Out of band
- **WHEN** a weight is outside its band
- **THEN** the band is marked and states weight and limit

#### Scenario: Toggle to look-through
- **WHEN** the RM switches the sector chart from direct to look-through
- **THEN** the chart shows the look-through exposure, with unclassified value as its own labelled group

#### Scenario: Unclassified is visible
- **WHEN** part of the portfolio cannot be assigned a sector
- **THEN** the chart shows it as its own group and a note states the amount that is unclassified

#### Scenario: No sector limit implied
- **WHEN** the sector chart is shown
- **THEN** it carries no limit marker or breach state, because the mandate defines no sector limits
