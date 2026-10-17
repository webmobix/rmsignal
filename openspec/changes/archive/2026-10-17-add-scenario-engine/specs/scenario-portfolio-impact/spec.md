## ADDED Requirements

### Requirement: Impact computed by code
For a portfolio, scenario and `as_of`, the system SHALL compute the portfolio's value and change in USD and percent for the best, likely and worst case by applying the scenario's shock vector to the portfolio's exposures. All figures SHALL be computed by code from holdings and the vector; a model-supplied figure SHALL NOT be used.

#### Scenario: Three cases
- **WHEN** the impact is computed for a portfolio with a 100 USD value and likely channel moves netting -3%
- **THEN** the likely after-value is 97 and best and worst bracket it

### Requirement: Exposure mapping without single-stock prediction
Each holding SHALL be mapped to channels via asset class, sector, region, currency and structured-product look-through. A holding with no reaching channel SHALL be reported as untouched. The impact SHALL report the share of portfolio value reached and the count of untouched holdings.

#### Scenario: Untouched holding
- **WHEN** a holding matches no channel of the vector
- **THEN** it has move 0, is counted as untouched and is excluded from the reached share

#### Scenario: Structured product
- **WHEN** a structured product references underlyings in a shocked sector
- **THEN** its move follows the look-through exposure, not a single-instrument forecast

### Requirement: Ambiguous mappings resolved and disclosed
Where code cannot map a holding to channels, an agent MAY propose the mapping. A proposed mapping SHALL be limited to channels in the vector, SHALL be marked as agent-assigned with its reason, and an unusable proposal SHALL leave the holding untouched with a gap.

#### Scenario: Proposed channel not in vector
- **WHEN** the agent assigns a channel absent from the vector
- **THEN** the assignment is dropped, the holding is untouched and a gap is recorded

### Requirement: Mandate bands and collateral
For each case the impact SHALL report asset-class bands crossed in or out of the mandate band, and the Lombard facility LTV before and after against its trigger, with shortfall when the trigger is breached.

#### Scenario: Band crossed in worst case
- **WHEN** the worst case lifts an asset class above its mandate maximum
- **THEN** the worst case lists that crossing with before, after and band limits

#### Scenario: Margin trigger
- **WHEN** the worst-case LTV exceeds the trigger
- **THEN** the case reports a breach and the shortfall in USD

### Requirement: Per-position moves with channels
Each result SHALL list per-position moves with weight, move, USD change per case and the channels that produced it, additive across channels.

#### Scenario: Two channels
- **WHEN** a holding is reached by shipping and energy channels
- **THEN** its move is the sum of both and both are listed

### Requirement: Summary and explainers
Each result SHALL carry a summary of the outcome and range, and an explainer for headline figures stating how it was derived. Every figure quoted in the summary SHALL equal a computed value, otherwise the summary is replaced by a code-built one and a gap is recorded.

#### Scenario: Wrong figure in summary
- **WHEN** the agent summary quotes a change that differs from the computed likely change
- **THEN** the summary is replaced by a code-built summary and a gap is recorded

### Requirement: Always delivered
A run SHALL return a result. Missing vector, unmapped data or model failure SHALL produce status `partial` or `insufficient_data` with gaps, not zero changes presented as outcomes.

#### Scenario: No vector
- **WHEN** no usable shock vector exists for the scenario and date
- **THEN** the result has status `insufficient_data` and no figures
