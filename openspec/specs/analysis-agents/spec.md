# analysis-agents Specification

## Purpose

Defines the cooperating agents that produce evidence-based relationship, portfolio and instrument analysis for a chosen date, in batch and interactive use.

## Requirements

### Requirement: Agent hierarchy
The Relationship Analyst SHALL be able to delegate to the Portfolio Analyst, which returns a report in the shared report contract. The Portfolio Analyst SHALL obtain instrument-level analysis from the persisted instrument outlooks for the run's `as_of` and SHALL NOT run a separate instrument analysis for each position.

#### Scenario: Delegation chain
- **WHEN** a relationship analysis is requested for a client
- **THEN** the relationship report includes findings from portfolio analyses, and those findings' instrument evidence originates from the persisted instrument outlooks

### Requirement: Evidence-based claims
Every finding SHALL cite evidence ids of tool results produced in the same run, and every number in agent output SHALL equal a value in a cited result.

#### Scenario: Uncited number
- **WHEN** an agent output contains a figure absent from all cited evidence
- **THEN** the claim is removed, a gap is recorded, and the report status is at most `partial`

### Requirement: Always delivered
Every run SHALL return a report, never an unhandled error. Tool failures, missing data and policy denials SHALL appear as gaps, and status SHALL be `complete`, `partial` or `insufficient_data`.

#### Scenario: Tool failure
- **WHEN** a tool raises an error during a run
- **THEN** a report is returned with status `partial` naming the failed tool

#### Scenario: No data at as_of
- **WHEN** `as_of` precedes all data
- **THEN** a report with status `insufficient_data` is returned

### Requirement: Honest uncertainty
Agents SHALL state data-quality flags and limits that affect a conclusion and SHALL NOT infer relationships, persons or news that tools did not return.

#### Scenario: No related-party data
- **WHEN** a relationship analysis is run
- **THEN** the report states that related-party data was unavailable rather than listing inferred parties

### Requirement: Reproducible by date
A run SHALL be parameterised by subject and `as_of`, and with the same model outputs SHALL produce the same evidence ids.

#### Scenario: Historical run
- **WHEN** an analysis is run for as_of 2026-03-31
- **THEN** no evidence is derived from sources dated after 2026-03-31

### Requirement: Batch execution
The system SHALL run an analysis for a list of clients at an `as_of` and persist one report per client plus a run summary of statuses.

#### Scenario: Twenty clients
- **WHEN** a batch is run for all clients
- **THEN** 20 reports are persisted and the summary counts each status

### Requirement: Interactive execution
The same agents SHALL be usable in an interactive session identified by a thread id whose state persists across turns.

#### Scenario: Follow-up question
- **WHEN** a user asks a follow-up in an existing thread
- **THEN** the agent uses earlier evidence of that thread and keeps the original `as_of` unless changed explicitly

### Requirement: Provider-neutral model access
Models SHALL be accessed through a configurable gateway endpoint and model name, with no provider-specific behaviour in agent logic.

#### Scenario: Swap model
- **WHEN** the configured model name changes
- **THEN** agents run unchanged

### Requirement: Events are valid reasons
Agents SHALL treat events and news returned by tools as established facts, SHALL use them to explain market and price movements, SHALL cite them as evidence and SHALL weigh their stated severity. Agents SHALL NOT attribute a movement to an event that no tool returned.

#### Scenario: Movement explained by an event
- **WHEN** an agent explains a rise in oil-linked prices and an event dated before `as_of` describes a supply disruption
- **THEN** the finding cites that event's evidence id

#### Scenario: No supporting event
- **WHEN** no returned event relates to a movement
- **THEN** the report gives no event-based cause for it

### Requirement: Reading news is not a gap
A run that reads news or events SHALL NOT record a missing-news gap because no external news feed exists.

#### Scenario: Analysis that reads news
- **WHEN** an analyst calls the news tool and receives event-log items
- **THEN** the report contains no `no_data` gap for the news tool

### Requirement: Outlooks feed the analysis
Relationship and portfolio analyses SHALL be able to read the market outlook and, for portfolio analyses, the outlooks of held instruments for the run's `as_of`, and SHALL cite them as evidence like any other tool result. A claim that rests on an outlook SHALL be worded as the bank's view with its date and SHALL carry the house-view flag in the report.

#### Scenario: Position with an outlook
- **WHEN** a portfolio analysis covers a position whose instrument has an outlook for the as_of
- **THEN** a finding about the position cites the outlook evidence and the report carries the house-view flag

#### Scenario: Reasons remain cited
- **WHEN** a finding repeats the reason an outlook gives
- **THEN** it cites the event or price evidence behind that reason or the outlook result that carries it

### Requirement: Missing outlook is a gap
When no outlook exists for a position or the market at the run's `as_of`, the analysis SHALL still be delivered, SHALL record a `no_data` gap naming what is missing and SHALL NOT state a forward-looking view for it.

#### Scenario: Outlook stage not run
- **WHEN** a portfolio analysis runs and no instrument outlook files exist
- **THEN** the report has status `partial`, a gap per missing outlook and no forward-looking claim

### Requirement: Outlooks respect the run date
A run SHALL NOT use an outlook dated after its `as_of`. When only an earlier outlook exists, the analysis SHALL state the date it is effective from.

#### Scenario: Later outlook exists
- **WHEN** a run for as_of 2026-06-30 starts and an outlook for 2026-08-26 exists
- **THEN** the later outlook is not used

#### Scenario: Earlier outlook only
- **WHEN** a run for as_of 2026-08-26 finds only an outlook for 2026-06-30
- **THEN** the outlook is used with its effective date 2026-06-30 stated and a staleness gap
