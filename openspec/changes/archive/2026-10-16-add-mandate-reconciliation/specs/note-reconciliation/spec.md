# Spec Delta

## MODIFIED Requirements

### Requirement: Notes are the only reconciled source
The reconciliation SHALL compare RM notes against the client's persisted report and evidence, and every result SHALL name its source kind as `rm_note`. It SHALL NOT assess mandate, limit or policy compliance; reconciling notes with mandate, position-limit and exclusion breaches is done by the `mandate-reconciliation` stage.

#### Scenario: Mandate not assessed
- **WHEN** a client's book breaches a mandate band and no note mentions it
- **THEN** the note reconciliation contains no result about the breach
