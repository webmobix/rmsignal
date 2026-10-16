# Spec Delta

## MODIFIED Requirements

### Requirement: Portfolio detail
`GET /api/portfolios/{id}` SHALL return the portfolio header, AuM history, mandate bands (min, target, max) against the actual asset-class weights, holdings at `as_of` with weight, value, unrealised P&L and liquidity tier, the largest-position check against `max_single_position_pct`, sector exposure in a direct and a look-through view with its denominator and quality flags, and any credit facility secured on it with its LTV history and margin-call trigger.

#### Scenario: Out of band
- **WHEN** an asset class weight exceeds its max
- **THEN** that band is flagged `out_of_band` with the weight and the limit

#### Scenario: Unknown portfolio
- **WHEN** the id does not exist
- **THEN** the response is 404

#### Scenario: Sector exposure present
- **WHEN** a portfolio with positions is requested
- **THEN** the response contains a direct and a look-through sector exposure, each summing to 100 within 0.01 percentage points

#### Scenario: Unclassified look-through
- **WHEN** a held structured product references an underlying that matches no instrument
- **THEN** the look-through exposure contains an `Unclassified (look-through)` group and the response lists a quality flag for it

#### Scenario: No positions
- **WHEN** a portfolio has no positions at `as_of`
- **THEN** the sector exposure is empty and a gap is recorded
