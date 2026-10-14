# database-seeding Specification

## Purpose

Lets a developer populate a SQLite database from the dataset CSV and JSON files with one standalone command, independent of the running app.

## Requirements

### Requirement: Standalone seed command
The package SHALL provide a command that creates the schema and loads all 12 dataset files into a SQLite database given a data directory and a database path. It SHALL run without the app being started and without third-party packages.

#### Scenario: Seed the sample dataset
- **WHEN** the command is run with the sample data directory and a new database path
- **THEN** the database contains 20 clients, 24 portfolios, 1,015 holdings, 62 instruments, 48 mandates, 393 transactions, 5 facilities, 5 commitments, 20 cash needs, 115 market series values, 16 events and 28 notes

### Requirement: Faithful loading
The seeder SHALL store values as given in the source files, loading empty cells as NULL and applying no rounding, trimming of content, or row filtering.

#### Scenario: Empty cell
- **WHEN** a source cell is empty
- **THEN** the stored value is NULL

#### Scenario: Values preserved
- **WHEN** a source value is `46571821.48`
- **THEN** the stored value is the float 46571821.48

#### Scenario: Typed values stored
- **WHEN** the sample data is seeded
- **THEN** dates are stored as ISO dates and flags as 0 or 1, and reading them back through the datasource yields dates and booleans

### Requirement: Input validation
The seeder SHALL fail with a message naming the file, and where applicable the row and column, when a file is missing, its header differs from the expected columns, or a numeric, date or flag cell cannot be parsed.

#### Scenario: Missing file
- **WHEN** the data directory lacks `holdings.csv`
- **THEN** the command exits non-zero naming `holdings.csv` and writes nothing

#### Scenario: Unparseable number
- **WHEN** a numeric cell contains `abc`
- **THEN** the command exits non-zero naming the file, row and column

#### Scenario: Unparseable date or flag
- **WHEN** a date cell contains `31/12/2026` or a flag cell contains `Maybe`
- **THEN** the command exits non-zero naming the file, row and column

### Requirement: Atomic and repeatable runs
The seeder SHALL load in a single transaction, SHALL refuse to run against a database that already contains the tables unless a replace option is given, and with that option SHALL rebuild the tables from the files.

#### Scenario: Re-seed refused
- **WHEN** the command is run twice on the same database path without the replace option
- **THEN** the second run exits non-zero and the data is unchanged

#### Scenario: Re-seed with replace
- **WHEN** the command is run with the replace option on a seeded database
- **THEN** the tables contain exactly the file contents, with no duplicates

#### Scenario: Failure leaves no partial data
- **WHEN** a later file fails validation mid-run
- **THEN** no rows from earlier files remain in the database
