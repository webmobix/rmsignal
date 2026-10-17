# overview-api Specification

## Purpose

Serves the RM overview with what a dashboard needs to plot, link and prepare meetings from it, and the stored evidence behind each action.

## Requirements

### Requirement: Overview endpoint
`GET /api/overview` SHALL return the persisted RM overview for the resolved `as_of`: status, summary, themes, all actions ranked with category, importance, horizon, due date, client id and name and source references, the actions grouped by category with counts, and the clients without actions with their reason.

#### Scenario: Committed run
- **WHEN** a client requests `GET /api/overview` on the 2026-08-26 run
- **THEN** the response contains the 33 ranked actions, the 20 clients, and the clients without actions with their reasons

### Requirement: Client position data on actions
Each action in the overview response SHALL carry the client's AuM in USD and wealth band so a consumer can plot urgency against AuM without a second request.

#### Scenario: AuM present
- **WHEN** the overview is returned
- **THEN** every action has `client_aum_usd` equal to the client's total AuM at that `as_of`

### Requirement: Urgency score
Each action SHALL carry a numeric `urgency` derived deterministically from importance, horizon and due date relative to `as_of`, and each overview client SHALL carry the maximum urgency of its own actions (`origin: "client_actions"`; the overview's coverage placeholders for clients without actions are not counted, so such a client has an action count and urgency of 0), so that consumers can place clients on an axis finer than the importance tier.

#### Scenario: Ties are ordered
- **WHEN** two actions share importance `high` but one is due within 90 days and the other has no horizon
- **THEN** the dated action has the higher urgency

### Requirement: Evidence lookup
`GET /api/evidence/{evidence_id}` SHALL return the stored tool result (tool, arguments, values, as-of, source) and the findings and actions that cite it, with their references.

#### Scenario: Known evidence
- **WHEN** a client requests an evidence id cited by a finding of CL-0001
- **THEN** the response contains the tool result and the finding reference `CL-0001#f10`

#### Scenario: Unknown evidence
- **WHEN** the id does not exist at the `as_of`
- **THEN** the response is 404

### Requirement: Resolvable references
Every source reference in an overview action SHALL be resolvable through the API: the client report path to a client or portfolio endpoint, and each evidence id to the evidence endpoint.

#### Scenario: Follow a reference
- **WHEN** an action cites `CL-0001/PF-0001#f8`
- **THEN** the response includes the client id, portfolio id and finding detail needed to link to `/api/portfolios/PF-0001` without parsing the reference
