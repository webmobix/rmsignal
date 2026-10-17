## ADDED Requirements

### Requirement: Client roll-up
For a client and scenario the system SHALL aggregate the client's portfolio results into best, likely and worst totals in USD and percent, the portfolios most affected, and a client summary.

#### Scenario: Two portfolios
- **WHEN** a client has two portfolios with computed results
- **THEN** the client likely change equals the sum of the portfolio likely changes in USD

### Requirement: RM book roll-up
For an RM and scenario the system SHALL aggregate all the RM's clients into book totals for the three cases, rank the most-hit clients by worst-case USD loss, list clients who benefit in the likely case, and list mandate bands and LTV triggers crossed per case with the client.

#### Scenario: Ranked clients
- **WHEN** the roll-up is requested for a scenario
- **THEN** clients are ranked by worst-case loss and each entry has client id, USD and percent

#### Scenario: Crossings listed
- **WHEN** a client's worst case breaches a facility trigger
- **THEN** the roll-up lists the client, facility and case

### Requirement: Aggregates by code, summary by agent
Totals, rankings and crossings SHALL be computed by code. A short agent summary MAY be added; every figure in it SHALL equal an aggregate, otherwise a code-built summary replaces it.

#### Scenario: Summary figure mismatch
- **WHEN** the agent quotes a book total that differs from the aggregate
- **THEN** the code-built summary is used

### Requirement: Honest coverage
A roll-up SHALL state how many of the RM's clients or portfolios had a computed result and SHALL NOT present a partial book as complete.

#### Scenario: Missing results
- **WHEN** 3 of 20 clients have no computed result
- **THEN** the roll-up states 17 of 20 covered and names the missing clients
