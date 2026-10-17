## MODIFIED Requirements

### Requirement: Scenario catalogue from the backend
`GET /api/scenarios` SHALL return the scenario catalogue: id, name, premise, the event or series it mirrors, horizon in months and a not-a-probability note, plus the scenario's market summary and shock vector when computed for the `as_of`. Scenario names SHALL be defined in the backend only. The payload SHALL carry `status` `computed` when all vectors are computed and `placeholder` otherwise.

#### Scenario: Catalogue
- **WHEN** a client requests `GET /api/scenarios`
- **THEN** it receives at least a de-escalation, a deterioration and a rates scenario by name with horizon 3, and computed vectors where they exist

### Requirement: Per-client placeholder results
`GET /api/clients/{id}/scenarios` SHALL return, for each catalogue scenario, a result with best, likely and worst cases, each with after-value, change in USD and percent, bands crossed and collateral effects; share of wealth reached; count of untouched holdings; per-position moves with channels; a summary; explainers; and status. Values SHALL be computed from the client's holdings. A scenario without a computed result SHALL be returned with status `placeholder` or `insufficient_data` and no invented figures.

#### Scenario: Shape complete
- **WHEN** the endpoint is requested for a client with computed results
- **THEN** every result contains three cases, summary, explainers and status `computed`

#### Scenario: Not yet computed
- **WHEN** no result exists for a scenario
- **THEN** that scenario is returned without figures and with a status naming why

#### Scenario: Unknown client
- **WHEN** the client id does not exist
- **THEN** the response is 404

### Requirement: Replaceable producer
The scenario payloads SHALL be built behind a single provider interface. The computed provider reads persisted results; the placeholder provider remains available for tests and as fallback with the same response models.

#### Scenario: Swap
- **WHEN** a different provider implementation is injected in a test
- **THEN** the endpoints return its results with the same response models

## ADDED Requirements

### Requirement: RM roll-up endpoint
`GET /api/scenarios/{scenario_id}/rollup` SHALL return the RM book roll-up for the scenario: totals for three cases, most-hit clients, beneficiaries, crossings, coverage and summary. An unknown scenario SHALL return 404.

#### Scenario: Roll-up
- **WHEN** a client requests the roll-up of a computed scenario
- **THEN** it receives book totals, ranked clients, coverage and summary

#### Scenario: Unknown scenario
- **WHEN** the scenario id does not exist
- **THEN** the response is 404
