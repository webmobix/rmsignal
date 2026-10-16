# Spec Delta

## ADDED Requirements

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
