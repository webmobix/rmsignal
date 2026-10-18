# Spec Delta

## Purpose

Lets a developer load the source data and the generated artifacts into a chosen backend with one command, so a locally produced dataset can be published to the demo server.

## ADDED Requirements

### Requirement: Load source data into a backend
The loader SHALL read the 12 dataset files from a data directory and write them to the chosen source-data backend (SQLite file or Firestore project), preserving values and file order.

#### Scenario: Load sample data to SQLite
- **WHEN** the loader is run for the sample data directory with a new SQLite target
- **THEN** the database holds the counts listed for the seed command and equals what the seed command produces

#### Scenario: Load sample data to Firestore
- **WHEN** the loader is run for the sample data directory with a Firestore target
- **THEN** reading through the Firestore datasource returns the same records, in the same order, as the SQLite datasource

### Requirement: Validate before writing
The loader SHALL validate every input file as the seed command does, failing with a message naming the file, row and column, and SHALL write nothing to the target when any file is invalid.

#### Scenario: Bad cell
- **WHEN** a numeric cell contains `abc`
- **THEN** the loader exits non-zero naming the file, row and column and the target is unchanged

#### Scenario: Missing file
- **WHEN** the data directory lacks `holdings.csv`
- **THEN** the loader exits non-zero naming `holdings.csv` and the target is unchanged

### Requirement: Repeatable and replaceable
Running the loader again against the same target SHALL produce the same contents without duplicates. With the replace option it SHALL first remove the rows it owns in that target; without it, a target that already holds source data SHALL be refused.

#### Scenario: Re-run without replace
- **WHEN** the loader is run twice on the same target without the replace option
- **THEN** the second run exits non-zero and the data is unchanged

#### Scenario: Re-run with replace
- **WHEN** the loader is run with the replace option on a loaded target
- **THEN** the target contains exactly the file contents, with no duplicates and no leftovers

### Requirement: Copy artifacts between backends
The loader SHALL copy all artifacts, or those of selected dates, from a source (an artifact SQLite file or an existing `reports/` folder) to a target (SQLite or Firestore), keeping addresses and bodies unchanged and re-chunking evidence and audit entries into the per-record form.

#### Scenario: Publish local artifacts
- **WHEN** artifacts from a local SQLite store are copied to Firestore
- **THEN** every address in the source exists in the target with an equal body

#### Scenario: Import an existing reports folder
- **WHEN** the loader imports a `reports/<as_of>/` folder tree
- **THEN** the reports, evidence, reconciliations, actions, overviews, outlooks, scenario results, summaries and audit trails of each date are saved in the target

#### Scenario: Copy a single date
- **WHEN** the copy is limited to one date
- **THEN** only that date's artifacts are written and other dates in the target are unchanged

#### Scenario: Idempotent copy
- **WHEN** the same copy is run twice
- **THEN** the target holds the same artifacts as after the first run

### Requirement: Report what was loaded
On success the loader SHALL print the counts it wrote per table or per artifact kind, and on a failure after writing started SHALL say that a re-run with the same arguments completes the load.

#### Scenario: Summary printed
- **WHEN** a load succeeds
- **THEN** the output lists each table or kind with its count
