# firestore-backend Specification

## Purpose

Lets the demo server read source data and generated artifacts from Firestore through the same interfaces the local SQLite backends implement.

## Requirements

### Requirement: Firestore datasource returns the same typed records
The Firestore datasource SHALL return rows of each of the 12 source tables as the same record types as the SQLite datasource, with the same values, types (dates, booleans, integers, floats, `None` for missing values) and source file order.

#### Scenario: Same rows, same order
- **WHEN** the sample data is loaded into Firestore and a table is listed through the Firestore datasource
- **THEN** the records equal those the SQLite datasource returns for the same data, in the same order

#### Scenario: Table without a primary key
- **WHEN** the holdings table is loaded and listed
- **THEN** all 1,015 holdings are returned with none lost or merged

#### Scenario: Composite key table
- **WHEN** the mandates table is loaded
- **THEN** every (mandate code, asset class) row is kept as its own record

### Requirement: Firestore datasource is read-only
The Firestore datasource SHALL expose no write operations.

#### Scenario: No write path
- **WHEN** the datasource interface is inspected
- **THEN** it offers no operation that creates, changes or deletes a source row

### Requirement: Firestore artifact store reads like the SQLite store
The Firestore artifact store SHALL support reading, listing keys, listing dates and evidence lookup with the same results as the SQLite artifact store holding the same artifacts.

#### Scenario: Parity after copy
- **WHEN** the artifacts of a SQLite store are copied to Firestore
- **THEN** reading, listing and dating through either store gives equal results

#### Scenario: Keys with separators
- **WHEN** an artifact key contains a slash
- **THEN** it is stored and read back under the same key

#### Scenario: Dates listed
- **WHEN** artifacts exist for two dates in Firestore
- **THEN** the dates are listed oldest first

### Requirement: Firestore artifact store refuses writes
Saving or deleting an artifact through the Firestore artifact store SHALL fail with an error stating that the Firestore backend is read-only for runners and naming the loader command, and SHALL change nothing.

#### Scenario: Runner pointed at Firestore
- **WHEN** a runner is started with the Firestore artifact backend configured
- **THEN** it fails before calling any model, naming the loader as the way to publish artifacts

### Requirement: Optional dependency
Firestore support SHALL be an optional dependency; the application, the SQLite backends and the tests that do not use Firestore SHALL work without it installed.

#### Scenario: Not installed
- **WHEN** the Firestore backend is configured and the Firestore client library is not installed
- **THEN** startup fails with a message naming the extra to install

### Requirement: Credentials from the environment
The Firestore backends SHALL take the project and credentials from the environment and the configuration, SHALL honour the Firestore emulator when it is configured, and SHALL NOT embed or log credentials.

#### Scenario: Emulator
- **WHEN** the emulator host is set in the environment
- **THEN** the backends read from and the loader writes to the emulator
