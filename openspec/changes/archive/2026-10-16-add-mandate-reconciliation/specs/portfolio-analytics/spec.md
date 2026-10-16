# Spec Delta

## ADDED Requirements

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
