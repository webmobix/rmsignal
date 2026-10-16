# portfolio-analytics Specification

## Purpose

Provides deterministic, reproducible portfolio and instrument calculations so that no figure in any analysis is produced by a language model.

## Requirements

### Requirement: Calculations are pure and reproducible
Each calculation SHALL depend only on its inputs, perform no I/O and read no clock, and SHALL return the same output for the same input.

#### Scenario: Repeatability
- **WHEN** a calculation is run twice on identical inputs
- **THEN** outputs are equal

### Requirement: Weights and exposures
The system SHALL compute position weights and exposures by asset class, currency, sector and region, with weights of a portfolio summing to 100% within a stated rounding tolerance, and SHALL state the denominator used.

#### Scenario: Weights sum
- **WHEN** weights are computed for any portfolio at any snapshot
- **THEN** they sum to 100 within 0.01 percentage points

#### Scenario: Missing sector
- **WHEN** a position has no sector
- **THEN** it is grouped as `unclassified` and a quality flag is returned

### Requirement: Client-level concentration
The system SHALL compute concentration across all of a client's portfolios, including look-through to referenced underlyings, returning top-N shares, an HHI, and single-name exposure, each with an explicit denominator (total wealth or investable, custody included or not).

#### Scenario: Shared underlying
- **WHEN** two portfolios of one client hold structured products referencing the same underlying
- **THEN** the single-name exposure to that underlying aggregates both and cites both positions

#### Scenario: Basket wrapper
- **WHEN** a product references a basket
- **THEN** the method states how its value is attributed to underlyings and flags that the attribution is an assumption

### Requirement: Mandate band drift
The system SHALL compare asset class weights with the mandate's minimum, target and maximum, reporting the gap in percentage points, and SHALL exclude custody portfolios from mandate comparison while including them in client totals.

#### Scenario: Above maximum
- **WHEN** an asset class weight exceeds the mandate maximum
- **THEN** the breach is returned with weight, limit and gap

### Requirement: Liquidity coverage
The system SHALL compute liquid assets by liquidity tier and their coverage of planned cash needs and uncalled commitments falling within a stated horizon after `as_of`, converting currencies at the rate for the effective snapshot and reporting each need's certainty.

#### Scenario: Shortfall
- **WHEN** daily-liquid assets are lower than needs within the horizon
- **THEN** the shortfall amount and the contributing needs are returned

#### Scenario: Aspirational needs
- **WHEN** a need is marked aspirational
- **THEN** it is excluded from the coverage total and listed separately

### Requirement: Credit and collateral
The system SHALL compute loan-to-value as drawn amount over lending value, headroom to the margin-call trigger, and the sale needed to cure a breach, using lending values that reflect advance rates.

#### Scenario: Recomputed LTV
- **WHEN** LTV is computed for a facility and snapshot
- **THEN** it equals drawn divided by lending value and any difference from the source figure is flagged

### Requirement: Performance and change decomposition
The system SHALL compute unrealised profit and loss and decompose the change in value between two snapshots into price, FX and flow effects that sum exactly to the total change.

#### Scenario: Exact decomposition
- **WHEN** a decomposition is computed between two snapshots
- **THEN** price + FX + flow equals the total change

### Requirement: Insufficient history is explicit
Measures requiring a return series longer than the available snapshots (volatility, value-at-risk, drawdown, Sharpe ratio) SHALL return status `insufficient_history` and no number.

#### Scenario: Volatility requested
- **WHEN** volatility is requested with five price points
- **THEN** the result is `insufficient_history` with the number of points available and required

### Requirement: Market conventions are explicit
Currency conversion SHALL account for the quote direction of each currency pair, and bond quantities SHALL account for their nominal unit, with both recorded in the computation method.

#### Scenario: Quote direction
- **WHEN** an amount in SGD is converted to USD using a pair quoted as SGD per USD
- **THEN** the amount is divided by the rate

### Requirement: Portfolio sector exposure with look-through
The system SHALL compute, for one portfolio, sector exposure in two views over the same denominator: a direct view grouping each position by its instrument's sector, and a look-through view that replaces each structured product by its referenced underlyings, each classified by the sector of the instrument it matches by normalised name. The denominator SHALL be stated.

#### Scenario: Direct view
- **WHEN** a portfolio holds positions in three sectors
- **THEN** the direct view lists those sectors with value and exposure percentage, summing to 100 within 0.01 percentage points

#### Scenario: Look-through classifies a matched underlying
- **WHEN** a portfolio holds a structured product whose single underlying matches an instrument with a sector
- **THEN** the look-through view attributes the product's value to that sector and lists the product as a contributor

#### Scenario: Look-through view sums to the same total
- **WHEN** any portfolio is computed
- **THEN** the look-through exposures sum to 100 within 0.01 percentage points of the same denominator as the direct view

### Requirement: Unclassified exposure is explicit
The system SHALL group value that cannot be assigned a sector into an unclassified group and SHALL NOT infer, map or add sector data. Underlyings that match no instrument, products whose underlying cannot be resolved, and positions without a sector SHALL be reported as unclassified, each with a quality flag naming the position or underlying.

#### Scenario: Unmatched underlying
- **WHEN** a structured product references an underlying that matches no instrument
- **THEN** that underlying's share of the product is reported under `Unclassified (look-through)` and a quality flag names the product and the underlying

#### Scenario: Unresolvable reference
- **WHEN** a structured product's underlyings cannot be identified from its reference
- **THEN** its value is reported under `Unclassified (look-through)` and a quality flag names the product

#### Scenario: Asset-type labels are not remapped
- **WHEN** an instrument's sector is `Diversified`, `Corporate`, `Sovereign`, `Cash`, `Gold`, `Multi` or `Macro`
- **THEN** it is reported as a group of that name and is not reassigned to another sector

### Requirement: Basket attribution is stated
The sector look-through SHALL attribute the value of a product referencing a basket equally to each underlying and SHALL state that this attribution is an assumption.

#### Scenario: Worst-of basket
- **WHEN** a product references three underlyings
- **THEN** each underlying receives one third of the product's value and a quality flag states that basket attribution is an assumption

### Requirement: Sustainability exclusion breach
The system SHALL report an exclusion breach for a managed portfolio whose mandate carries binding exclusions and which holds an instrument flagged `sustainability_excluded`, directly or through a structured product whose underlying matches such an instrument by normalised name. Each breach SHALL state the instrument, the held value and weight and how it is held, and the denominator.

#### Scenario: Direct holding in a bound mandate
- **WHEN** the Sustainable Balanced portfolio PF-0007 holds Global Energy Majors Equity Fund and Sunrise Palm Resources, both flagged excluded
- **THEN** two exclusion breaches are returned with their weights of the portfolio

#### Scenario: Flag in a mandate without exclusions
- **WHEN** a Balanced portfolio holds a defence fund flagged excluded
- **THEN** no exclusion breach is returned

#### Scenario: Held through a structured product
- **WHEN** a bound portfolio holds a product whose underlying matches an excluded instrument
- **THEN** a breach is returned marked as held through look-through, naming the product

#### Scenario: Custody portfolio
- **WHEN** the portfolio is a custody account
- **THEN** no exclusion check applies and the result says it is not applicable
