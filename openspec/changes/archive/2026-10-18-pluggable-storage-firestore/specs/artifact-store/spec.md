# Spec Delta

## Purpose

Gives every stage that produces or consumes generated artifacts one backend-agnostic way to save and read them, so the storage backend can change without changing the agents, runners or API.

## ADDED Requirements

### Requirement: Artifacts are addressed by date, kind and key
An artifact SHALL be identified by an as-of date, a kind (for example report, reconciliation, actions, overview, outlook, scenario vector, scenario impact) and a key within the kind, and SHALL hold a JSON body. Saving to an existing address SHALL replace the previous body.

#### Scenario: Save and read back
- **WHEN** an artifact is saved at (2026-08-26, report, CL-0001) and then read at the same address
- **THEN** the body read equals the body saved

#### Scenario: Replace
- **WHEN** a second body is saved at the same address
- **THEN** a read returns the second body only

#### Scenario: Missing artifact
- **WHEN** an address that was never saved is read
- **THEN** the result is "not found", not an error

### Requirement: Artifacts can be listed and dated
The store SHALL list the keys saved under a date and kind, optionally under a key prefix, in a stable order, and SHALL list the as-of dates that have at least one artifact, oldest first. It SHALL NOT read the clock.

#### Scenario: List keys
- **WHEN** reports for CL-0001 and CL-0002 are saved for a date and the report keys are listed
- **THEN** both keys are returned in ascending order

#### Scenario: List dates
- **WHEN** artifacts exist for 2026-06-30 and 2026-08-26
- **THEN** the dates are returned as those two dates, oldest first

#### Scenario: Other dates untouched
- **WHEN** artifacts are saved for one date
- **THEN** artifacts of other dates are unchanged

### Requirement: Evidence is stored per tool result
Evidence SHALL be stored one record per tool result, addressed by its evidence id, together with a per-subject ordered list of the evidence ids that subject cites. Reading a subject's evidence SHALL return its results in the order they were saved, and any result SHALL be retrievable by evidence id alone.

#### Scenario: Subject evidence order
- **WHEN** a subject's evidence is saved in a given order and read back
- **THEN** the results are returned in that order

#### Scenario: Lookup by id
- **WHEN** an evidence id saved for any subject of a date is requested without naming the subject
- **THEN** that tool result is returned

#### Scenario: Shared result saved once
- **WHEN** two subjects cite a tool result with the same evidence id
- **THEN** both read it, and it is stored once

#### Scenario: Large evidence set
- **WHEN** a subject's evidence totals more than 1 MiB
- **THEN** it is saved and read back in full

### Requirement: Audit trail is stored per entry
Audit entries SHALL be stored one record per entry, in sequence order per run stage, and SHALL be append-only: the store offers no way to change or delete an entry other than re-running the stage with the replace option.

#### Scenario: Audit read in order
- **WHEN** a stage appends entries 1 to 3 and the stage's audit trail is read
- **THEN** the entries are returned in sequence order

### Requirement: Unreadable artifacts count as absent
A stored body that no longer validates against its record type SHALL be reported to typed readers as not found, as for a missing artifact, without raising.

#### Scenario: Stale scenario result
- **WHEN** a stored scenario impact no longer parses
- **THEN** reading it returns "not found" and other artifacts are unaffected

### Requirement: Saves are whole or absent
A saved artifact SHALL be visible either complete or not at all; an interrupted save SHALL NOT leave a partial body for a later reader.

#### Scenario: Interrupted save
- **WHEN** a save is interrupted before it completes
- **THEN** a later read returns the previous body, or "not found" if there was none

### Requirement: Local SQLite backend in its own file
The default backend SHALL keep artifacts in a SQLite database file separate from the source-data database, created on first write. Opening the artifact store SHALL NOT modify the source-data database, and re-seeding the source data SHALL NOT remove artifacts.

#### Scenario: Re-seed keeps artifacts
- **WHEN** the source data is re-seeded with the replace option
- **THEN** all saved artifacts are still readable

#### Scenario: Created on first write
- **WHEN** the first artifact is saved with no artifact database file present
- **THEN** the file is created and the artifact is readable

### Requirement: Backend chosen by configuration
The artifact backend SHALL be selected by configuration (a setting or environment variable naming SQLite with a path, or Firestore with a project), and all runners, the read API and the agent tools SHALL use the configured backend through the same interface.

#### Scenario: Runner writes through the configured store
- **WHEN** a runner is run with the SQLite backend configured
- **THEN** its outputs are readable through the store and no per-artifact files are written beside it

#### Scenario: Unknown backend
- **WHEN** the configured backend name is not recognised
- **THEN** startup fails with a message listing the valid backends
