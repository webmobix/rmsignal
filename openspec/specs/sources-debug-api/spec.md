# sources-debug-api Specification

## Purpose

Lets developers inspect every dataset table over read-only HTTP endpoints under `/api/sources`, to debug seeded data without direct database access.

## Requirements

### Requirement: Source catalogue
`GET /api/sources` SHALL list every dataset table with its name, column names and types, primary key columns, and current row count.

#### Scenario: List tables
- **WHEN** a client requests `GET /api/sources` on a seeded database
- **THEN** the response is 200 and contains the 12 tables, each with its columns and row count

### Requirement: Paginated row listing
`GET /api/sources/{table}` SHALL return the table's rows in storage order together with the total row count, honouring `limit` and `offset` query parameters.

#### Scenario: Default page
- **WHEN** a client requests `GET /api/sources/clients`
- **THEN** the response contains `total` of 20, and the rows up to the default limit

#### Scenario: Explicit page
- **WHEN** a client requests `GET /api/sources/transactions?limit=5&offset=10`
- **THEN** exactly 5 rows are returned, starting after the first 10, and `total` is the unpaged count

#### Scenario: Invalid paging
- **WHEN** `limit` is below 1 or above the maximum, or `offset` is negative
- **THEN** the response is 422

### Requirement: Column filtering
`GET /api/sources/{table}` SHALL filter rows by exact match when a query parameter is named after a column of that table, and the `total` SHALL reflect the filtered count.

#### Scenario: Filter by column
- **WHEN** a client requests `GET /api/sources/portfolios?client_id=CL-0001`
- **THEN** only portfolios of that client are returned and `total` equals their number

#### Scenario: Typed filter value
- **WHEN** a client filters a boolean column with `pep_status=true`, or a date column with an ISO date
- **THEN** rows matching that value are returned

#### Scenario: Unknown filter column
- **WHEN** a client passes a query parameter that is not a column of the table
- **THEN** the response is 422 and names the unknown parameter

### Requirement: Fetch by primary key
`GET /api/sources/{table}/{key}` SHALL return the single row whose primary key matches. For composite keys the segments SHALL be joined by `/` in primary-key column order. Tables without a primary key SHALL answer 404 for this form.

#### Scenario: Existing row
- **WHEN** a client requests `GET /api/sources/portfolios/PF-0001`
- **THEN** the response is 200 with that portfolio

#### Scenario: Composite key
- **WHEN** a client requests a `mandates` row with the mandate code and asset class as path segments
- **THEN** the response is 200 with that row

#### Scenario: Missing row
- **WHEN** a client requests a key that does not exist
- **THEN** the response is 404

### Requirement: Typed JSON values
Rows SHALL be serialised with dates as ISO-8601 strings, flags as JSON booleans, numbers as JSON numbers and empty cells as `null`, using the dataset's column names including underscore date suffixes.

#### Scenario: Value types
- **WHEN** a client fetches a client row with `pep_status` false and a `client_since` date
- **THEN** `pep_status` is JSON `false` and `client_since` is an ISO date string

### Requirement: Unknown table
Requests naming a table that is not one of the 12 dataset tables SHALL answer 404 and SHALL NOT reach SQL.

#### Scenario: Unknown table
- **WHEN** a client requests `GET /api/sources/nope`
- **THEN** the response is 404 listing the valid table names

### Requirement: Read-only API
The API SHALL expose only GET operations on `/api/sources` and SHALL NOT modify the database.

#### Scenario: Write method
- **WHEN** a client sends POST, PUT, PATCH or DELETE to any `/api/sources` path
- **THEN** the response is 405

### Requirement: Server startup
The `rm-dashboard-serve` command SHALL start the API against the database given by `--db` or the `RM_DASHBOARD_DB` environment variable, and SHALL fail with a message naming the seed command when the database does not exist.

#### Scenario: Missing database
- **WHEN** the server is started with a path that does not exist
- **THEN** it exits with an error that mentions `rm-dashboard-seed`

#### Scenario: Interactive docs
- **WHEN** the server is running
- **THEN** the OpenAPI docs are served at `/docs`
