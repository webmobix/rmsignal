## Purpose

Defines how the read API resolves the point in time, identifies the RM, and conveys gaps and placeholders, so a dashboard can rely on one set of conventions.

## ADDED Requirements

### Requirement: As-of resolution
Every read endpoint other than `/api/sources` SHALL accept an `as_of` query parameter (ISO date) or the literal `latest`, defaulting to `latest`. `latest` SHALL resolve to the newest date for which a persisted run exists, never to the wall clock. `GET /api/as-of` SHALL list the available dates and the latest one.

#### Scenario: Default is latest
- **WHEN** a client requests `GET /api/overview` without `as_of` and the newest run is 2026-08-26
- **THEN** the response is for 2026-08-26 and states that `as_of`

#### Scenario: Unknown date
- **WHEN** a client requests an `as_of` for which no run exists
- **THEN** the response is 404 and lists the available dates

#### Scenario: No runs
- **WHEN** the reports folder contains no dated run
- **THEN** `GET /api/as-of` returns an empty list and `latest: null`, and data endpoints answer 404 with a message naming the batch commands

### Requirement: RM profile
`GET /api/rm` SHALL return the RM's id, name, desk and booking centres for the resolved `as_of`, derived from the client data, so a UI can show a user without authentication.

#### Scenario: Profile
- **WHEN** a client requests `GET /api/rm` on the committed data
- **THEN** the response contains `Priscilla Ong`, her RM id and her desk

### Requirement: Read-only and typed
The read API SHALL expose only GET operations, SHALL declare Pydantic response models for every endpoint, and SHALL NOT modify the database or the reports folder.

#### Scenario: Write method
- **WHEN** a client sends POST, PUT, PATCH or DELETE to any `/api` path
- **THEN** the response is 405

#### Scenario: OpenAPI
- **WHEN** the server runs
- **THEN** `/docs` shows every endpoint with its response schema

### Requirement: Gaps are data
When a section cannot be produced (missing report, missing outlook, insufficient history), the response SHALL still be delivered with that section empty and a `gaps` entry naming what is missing and why, and SHALL NOT answer 500 or fabricate values.

#### Scenario: Client without actions
- **WHEN** a client has a report but no persisted actions
- **THEN** the client detail is returned with a gap whose description starts with `actions_missing`, and its own actions are none; the overview's coverage placeholder for that client (`origin: "coverage"`) may be listed but is not counted as an action of the client

### Requirement: Placeholder flag
Any payload whose content is not computed from the analysis layer SHALL carry `status: "placeholder"` at its top level so that consumers can mark it.

#### Scenario: Flag present
- **WHEN** a placeholder payload is returned
- **THEN** its top-level `status` is `placeholder`

### Requirement: Reports location
`rm-dashboard-serve` SHALL take the reports folder from `--reports` or `RM_DASHBOARD_REPORTS`, defaulting to `reports`, and SHALL fail with a message naming the folder when it does not exist.

#### Scenario: Missing folder
- **WHEN** the server is started with a reports path that does not exist
- **THEN** it exits with an error that names the path
