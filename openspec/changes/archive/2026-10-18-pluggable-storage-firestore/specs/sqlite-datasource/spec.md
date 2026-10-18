# Spec Delta

## ADDED Requirements

### Requirement: Implements the datasource contract
The SQLite datasource SHALL implement a backend-agnostic datasource contract consisting of the typed list and look-up reads for the 12 source tables plus the generic table select, count and key look-up, so that callers (the point-in-time repository, the sources debug API) depend on the contract and not on SQLite.

#### Scenario: Repository over any backend
- **WHEN** the point-in-time repository is built over an object that satisfies the contract
- **THEN** it works unchanged, whether that object is the SQLite or the Firestore datasource

#### Scenario: Same results as before
- **WHEN** the existing typed-read scenarios are run through the contract
- **THEN** their results are unchanged
