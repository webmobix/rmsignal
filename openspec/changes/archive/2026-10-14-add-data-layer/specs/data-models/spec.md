# Spec Delta

## Purpose

Defines the typed record model for each file in the Julius Baer wealth intelligence dataset, so the rest of the app works with typed objects instead of raw CSV rows.

## ADDED Requirements

### Requirement: One record type per dataset file
The data package SHALL provide one dataclass for each of the 12 dataset files (clients, portfolios, holdings, instruments, mandates, transactions, credit facilities, commitments, planned cash needs, market context, event log, RM notes), with one field per source column.

#### Scenario: Fields match the source columns
- **WHEN** a dataset file's header is compared with its record type's field names
- **THEN** every column has a field of the same name and no field lacks a column

### Requirement: Date-suffixed columns map to valid field names
Source columns containing hyphens, such as `aum_2026-08-26`, SHALL map to fields with hyphens replaced by underscores, such as `aum_2026_08_26`.

#### Scenario: Snapshot column renamed
- **WHEN** the `portfolios.csv` column `aum_2026-08-26` is represented
- **THEN** the portfolio record exposes it as `aum_2026_08_26`

### Requirement: Missing values are representable
Fields whose source cells may be empty SHALL be nullable and SHALL hold `None` rather than an empty string or zero.

#### Scenario: Client without an age
- **WHEN** a client row has an empty `age`
- **THEN** the resulting client record has `age` equal to `None`

#### Scenario: Non-trade transaction
- **WHEN** a transaction row has no instrument, quantity or price
- **THEN** those fields are `None` on the transaction record

### Requirement: Dates are date values
Columns holding calendar dates SHALL be typed as dates, parsed from `YYYY-MM-DD`, and not held as strings.

#### Scenario: Date parsed
- **WHEN** a client row has `kyc_review_due` of `2026-11-30`
- **THEN** the client record's `kyc_review_due` is the date 30 November 2026

#### Scenario: Invalid date rejected
- **WHEN** a date cell contains `2026-13-45`
- **THEN** building the record fails with an error naming the column

### Requirement: Flags are booleans
Columns holding yes/no flags (`pep_status`, `sustainability_excluded`, `concentration_limit_applies`) SHALL be typed as booleans, parsed from `Yes`/`No` or `Y`/`N`.

#### Scenario: Flag parsed
- **WHEN** an instrument row has `sustainability_excluded` of `Y`
- **THEN** the instrument record's field is `True`

#### Scenario: Unknown flag value rejected
- **WHEN** a flag cell contains `Maybe`
- **THEN** building the record fails with an error naming the column

### Requirement: Records are immutable and typed
Records SHALL be immutable, and numeric columns SHALL be typed as integers or floats rather than strings.

#### Scenario: Numeric value type
- **WHEN** a holding record is created from a row with `market_value_usd` of `6552000.0`
- **THEN** the field is a float equal to 6552000.0

#### Scenario: Mutation rejected
- **WHEN** code assigns to a field of an existing record
- **THEN** the assignment raises an error
