## ADDED Requirements

### Requirement: Scenarios are stored text records
The system SHALL keep each scenario as a stored record with id, name, premise text, optional mirrored event reference, horizon in months (default 3), and creation time. Adding or editing a scenario SHALL NOT require a code change.

#### Scenario: Add a scenario from text
- **WHEN** a record with a name and premise text is added to the catalogue store
- **THEN** it appears in `GET /api/scenarios` with horizon 3 months

#### Scenario: Missing premise
- **WHEN** a record without premise text is loaded
- **THEN** it is rejected with a message naming the missing field and the other scenarios are unaffected

### Requirement: Seeded initial scenarios
The catalogue SHALL be seeded with the three existing scenarios (Gulf de-escalation, Gulf deterioration, Rates higher for longer) so the product works without authoring.

#### Scenario: Fresh install
- **WHEN** the catalogue store is empty
- **THEN** the three seeded scenarios are listed
