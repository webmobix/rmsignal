# Spec Delta

## Purpose

Lets the analysis agents be discovered and called by other bank agents, and call other agents, over a standard agent-to-agent protocol.

## ADDED Requirements

### Requirement: Published agent descriptions
Each analyst SHALL publish an agent card at a well-known location stating its name, version, skills, accepted inputs (including a required `as_of`) and authentication scheme.

#### Scenario: Fetch card
- **WHEN** a client requests the Portfolio Analyst's card
- **THEN** it lists the portfolio analysis skill and requires `as_of` and a portfolio or client id

### Requirement: Callable over the protocol
Each analyst SHALL accept tasks over the protocol and return the report contract as the task result, with task states reflecting progress and failure.

#### Scenario: Remote portfolio analysis
- **WHEN** a peer agent sends a task for a client and `as_of`
- **THEN** a task result containing a report is returned

#### Scenario: Missing as_of
- **WHEN** a task omits `as_of`
- **THEN** the task fails with an input-required state and no analysis runs

### Requirement: Consuming external agents
The Relationship Analyst SHALL be able to call a peer agent over the protocol and treat its answer as evidence with the peer's identity as source. A mock KYC/compliance peer SHALL be provided.

#### Scenario: KYC peer
- **WHEN** the Relationship Analyst asks the mock peer for a client's KYC status
- **THEN** the answer is recorded as evidence sourced to the peer and flagged `mock`

### Requirement: Policy at the boundary
Inbound and outbound protocol calls SHALL request policy decisions and be audited, and SHALL carry the delegation chain of the original requester.

#### Scenario: Delegation chain
- **WHEN** a remote task triggers further agent calls
- **THEN** the audit record of each call lists the original requester
