# note-reconciliation Specification

## Purpose

Checks what an RM's notes say about a client against what the client's report and evidence show, so that contradictions and unsupported claims are visible before actions are decided.

## Requirements

### Requirement: Notes are the only reconciled source
The reconciliation SHALL compare RM notes against the client's persisted report and evidence, and every result SHALL name its source kind as `rm_note`. It SHALL NOT assess mandate, limit or policy compliance.

#### Scenario: Mandate not assessed
- **WHEN** a client's book breaches a mandate band and no note mentions it
- **THEN** the reconciliation contains no result about the breach

### Requirement: One verdict per note
For each note of the client dated on or before `as_of`, the system SHALL return exactly one result with the note id, note date, a verdict of `consistent`, `contradicted` or `unverifiable`, and a rationale.

#### Scenario: Contradicted note
- **WHEN** a note states the client wants to reduce an exposure and the report shows that exposure unchanged or higher
- **THEN** the verdict is `contradicted`

#### Scenario: Note beyond the evidence
- **WHEN** a note states an intention that no report finding or evidence addresses
- **THEN** the verdict is `unverifiable`

### Requirement: Point-in-time notes
Notes dated after `as_of` SHALL NOT be used, and a client without notes at `as_of` SHALL yield a reconciliation with no results and no error.

#### Scenario: Later note
- **WHEN** reconciling as_of 2026-03-31 and a note is dated 2026-04-14
- **THEN** that note does not appear in the output

### Requirement: Evidence on both sides
A `consistent` or `contradicted` result SHALL cite the note and at least one evidence id from the client's persisted evidence, and every number in its rationale SHALL equal a number in the cited evidence or be quoted from the cited note.

#### Scenario: Unsupported verdict
- **WHEN** a result cites no evidence or an unknown evidence id
- **THEN** its verdict is changed to `unverifiable` and a gap is recorded

#### Scenario: Invented figure
- **WHEN** a rationale contains a figure absent from the cited evidence and note
- **THEN** the result is removed, a gap is recorded and the status is at most `partial`

### Requirement: Notes are quoted, not trusted
Note text SHALL be treated as quoted statements by the RM: a number or waiver in a note SHALL NOT be used as a data figure, and a note SHALL NOT change any computed result.

#### Scenario: Waiver in a note
- **WHEN** a note says a limit was waived
- **THEN** the result may quote it but the limit evidence is unchanged

### Requirement: Always delivered and reproducible
The run SHALL return a reconciliation with status `complete`, `partial` or `insufficient_data` and never raise an unhandled error. With the same report, evidence, notes and model output it SHALL produce identical content, written to `reconciliation/<client>.json` under the as_of folder.

#### Scenario: Missing report
- **WHEN** no report exists for the client at the date
- **THEN** a reconciliation with status `insufficient_data` and a gap is returned and written

#### Scenario: Model failure
- **WHEN** the model raises or returns unparsable output
- **THEN** a `partial` reconciliation with every note `unverifiable` and a gap describing the failure is returned

### Requirement: Privacy
Client and person names in notes and reports SHALL be pseudonymised before reaching the model and restored only in the delivered output.

#### Scenario: Names in model input
- **WHEN** the model input is prepared
- **THEN** it contains pseudonyms and no real client names
