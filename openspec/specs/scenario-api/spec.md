# scenario-api Specification

## Purpose

Serves the scenario catalogue and per-client results from the backend as clearly marked placeholders behind a replaceable provider.

## Requirements

### Requirement: Scenario catalogue from the backend
`GET /api/scenarios` SHALL return the scenario catalogue: id, name, premise, the event or series it mirrors, and a caveat. Scenario names SHALL be defined in the backend only. The payload SHALL carry `status: "placeholder"`.

#### Scenario: Catalogue
- **WHEN** a client requests `GET /api/scenarios`
- **THEN** it receives at least a de-escalation, a deterioration and a rates scenario by name, with `status: "placeholder"`

### Requirement: Per-client placeholder results
`GET /api/clients/{id}/scenarios` SHALL return, for each catalogue scenario, a result in the final contract shape: before and after value, change in USD and percent, share of wealth reached, count of untouched holdings, collateral effects, mandate bands crossed, and per-position moves with channels. Values SHALL be produced server-side from fixed placeholder data and SHALL NOT be computed from the client's holdings. Each result SHALL carry `status: "placeholder"` and a note stating that it is illustrative.

#### Scenario: Shape complete
- **WHEN** the endpoint is requested for any client
- **THEN** every scenario result contains all contract fields, and `status` is `placeholder`

#### Scenario: Unknown client
- **WHEN** the client id does not exist
- **THEN** the response is 404

### Requirement: Replaceable producer
The scenario payloads SHALL be built behind a single provider interface, so that replacing the placeholder provider with a computed one does not change routes or response models.

#### Scenario: Swap
- **WHEN** a different provider implementation is injected in a test
- **THEN** the endpoints return its results with the same response models
