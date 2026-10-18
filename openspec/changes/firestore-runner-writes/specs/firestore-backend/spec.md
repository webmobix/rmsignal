# Spec Delta

## MODIFIED Requirements

### Requirement: Firestore artifact store refuses writes
The Firestore artifact store SHALL accept saving and deleting artifacts when opened for writing, which runners and the loader do. When opened read-only, as the API does, saving or deleting SHALL fail with an error stating that the store was opened read-only, and SHALL change nothing. Saving an artifact for a date SHALL make that date appear in the store's list of dates.

#### Scenario: Runner pointed at Firestore
- **WHEN** a runner is started with the Firestore artifact backend configured
- **THEN** it saves its artifacts in Firestore and the run's date is listed by the store

#### Scenario: API store is read-only
- **WHEN** the API opens the Firestore artifact backend
- **THEN** any attempt to save or delete through it fails and changes nothing

#### Scenario: Scenario catalogue has no date
- **WHEN** an artifact with no date is saved
- **THEN** it is stored and no date is added to the list of dates
