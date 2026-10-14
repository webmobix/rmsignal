# sqlite-datasource Specification

## Purpose

Provides a SQLite-backed datasource holding one table per dataset file and returning typed records, as the app's single read path to the dashboard data.

## Requirements

### Requirement: One table per dataset file
The SQLite schema SHALL contain one table per dataset file (12 tables), whose columns match the corresponding record type's fields and whose nullability matches the record type.

#### Scenario: Schema created
- **WHEN** the schema is applied to an empty database
- **THEN** 12 tables exist, each with columns equal to its record type's field names

### Requirement: Typed values round-trip
Dates, booleans, integers and floats SHALL be stored in forms that preserve their value and SHALL be returned as the same types on read.

#### Scenario: Date round-trip
- **WHEN** a record with a date field is stored and read back
- **THEN** the field is an equal date value, not a string

#### Scenario: Boolean round-trip
- **WHEN** a record with `concentration_limit_applies` of `False` is stored and read back
- **THEN** the field is the boolean `False`, not `0`

#### Scenario: Invalid flag storage prevented
- **WHEN** a value other than 0 or 1 is written to a boolean column
- **THEN** the database rejects it

### Requirement: Join keys are indexed
The schema SHALL index the join keys defined in the dataset's data dictionary (client, portfolio, instrument, mandate code, snapshot date), and SHALL NOT declare foreign key constraints.

#### Scenario: Orphan reference loads
- **WHEN** a row references a `client_id` absent from `clients`
- **THEN** the row is stored without a constraint error

### Requirement: Typed reads
The datasource SHALL return rows as the corresponding record types, with NULLs returned as `None`.

#### Scenario: List all clients
- **WHEN** a caller lists clients on a seeded database
- **THEN** it receives 20 client records

#### Scenario: Look up by id
- **WHEN** a caller requests the portfolio `PF-0001`
- **THEN** it receives that portfolio record, and `None` for an unknown id

#### Scenario: Join-based filter
- **WHEN** a caller requests the holdings of a portfolio at a snapshot date
- **THEN** only holdings matching both are returned

### Requirement: Read-only access
The datasource SHALL open the database read-only, and SHALL fail with an error naming the seed command when the database file does not exist.

#### Scenario: Write attempt
- **WHEN** a write statement is executed through the datasource connection
- **THEN** it fails and the database is unchanged

#### Scenario: Missing database
- **WHEN** the datasource is opened on a path that does not exist
- **THEN** a `FileNotFoundError` is raised that mentions seeding
