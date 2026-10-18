# Spec Delta

## ADDED Requirements

### Requirement: Seeding and loading share validation
The seed command and the loader SHALL parse and validate the dataset files with the same code, so that an input accepted or rejected by one is accepted or rejected by the other with the same message.

#### Scenario: Same rejection
- **WHEN** a date cell contains `31/12/2026`
- **THEN** the seed command and the loader both exit non-zero with the same file, row and column in the message

#### Scenario: Seed command unchanged
- **WHEN** the seed command is run on the sample data
- **THEN** it still needs no third-party packages and produces the same database as before
