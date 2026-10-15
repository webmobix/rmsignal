# Spec Delta

## ADDED Requirements

### Requirement: Outlook read tools
The system SHALL provide read-only tools that return the persisted market outlook and the persisted outlook of one instrument for an `as_of`, each returning the evidence envelope with the outlook's effective date, its source file, and a house-view quality flag, and each making the evidence cited by the outlook resolvable in the run. The tools SHALL NOT start an outlook run and SHALL NOT accept a file path.

#### Scenario: Instrument outlook returned
- **WHEN** the instrument outlook tool is called for an instrument with an outlook for the as_of
- **THEN** the view, drivers and risks are returned with their evidence ids, the source file and a house-view flag

#### Scenario: No outlook
- **WHEN** the tool is called and no outlook exists on or before the as_of
- **THEN** it returns `no_data` with a reason naming the missing outlook

#### Scenario: Look-ahead refused
- **WHEN** only an outlook dated after the as_of exists
- **THEN** it is not returned

#### Scenario: Evidence resolvable
- **WHEN** an agent cites an evidence id listed in a returned outlook's drivers
- **THEN** the citation resolves in the run and the number guard can check figures against it
