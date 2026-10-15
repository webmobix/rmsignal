# Spec Delta

## Purpose

Gives the bank one dated, evidence-bound view of where markets are heading and why, independent of any client or portfolio, which changes only when new data arrives and states what changed against the previous view.

## ADDED Requirements

### Requirement: Market outlook per date
The system SHALL, given an `as_of`, produce one market outlook containing a view for the overall market and for each market segment present in the data (equity, rates, FX, commodities, volatility). Each view SHALL state a direction (`positive`, `neutral` or `negative`), a horizon, a confidence, a rationale, drivers, risks and what would change the view. A view SHALL NOT contain a numeric price or level forecast.

#### Scenario: Outlook for a date
- **WHEN** a market outlook is requested for as_of 2026-08-26 and market data exists
- **THEN** the outlook contains the as_of, an overall view and one view per segment with direction, horizon, confidence, drivers and risks

#### Scenario: No market data
- **WHEN** an outlook is requested for an as_of earlier than every market snapshot
- **THEN** an outlook with status `insufficient_data`, no views and a gap naming the missing data is returned

### Requirement: Reasons rest on cited evidence
Every driver and risk SHALL cite evidence produced in the same run, every figure in a view SHALL equal a value in the cited evidence, and events returned by the news or events tools SHALL be usable and cited as reasons. The previous outlook SHALL NOT be accepted as support for a driver or risk.

#### Scenario: Uncited driver
- **WHEN** the model returns a view whose drivers cite no evidence of this run
- **THEN** the view is removed, a gap is recorded and the status is at most `partial`

#### Scenario: Event as reason
- **WHEN** a driver of the energy-related view cites a returned event about a supply disruption
- **THEN** the driver is kept with that event's evidence id

#### Scenario: Previous view cited as support
- **WHEN** a driver cites the evidence id of the previous outlook
- **THEN** the driver is removed and a gap is recorded

### Requirement: Events named by id
Events returned by the news and events tools SHALL carry a stable id, and a driver or risk SHALL name the events it rests on by that id. An id that was not returned in the run SHALL cause the driver or risk to be removed.

#### Scenario: Stable ids
- **WHEN** the events tool is called for two as_of dates
- **THEN** an event returned by both has the same id in both

### Requirement: Point-in-time only
An outlook for an `as_of` SHALL use only market snapshots and events dated on or before it and SHALL use as previous outlook only one with a strictly earlier as_of.

#### Scenario: Historical date
- **WHEN** an outlook is built for as_of 2026-03-31 while an outlook for 2026-08-26 exists
- **THEN** no evidence dated after 2026-03-31 is used and the 2026-08-26 outlook is not read

### Requirement: Changes only with new data
The outlook SHALL record the data it used (effective market snapshot date, latest event date, number of events). When these equal those of the previous outlook, the system SHALL carry the previous views forward without a model call, mark every view `unchanged` and state the date it was carried forward from. Otherwise the system SHALL generate a new outlook.

#### Scenario: No new data
- **WHEN** an outlook is requested for as_of 2026-09-15 and no market snapshot or event is dated after the previous outlook's inputs
- **THEN** the views equal the previous views, all are `unchanged`, the outlook names the previous as_of and no model is called

#### Scenario: New event
- **WHEN** an event dated after the previous outlook's as_of exists
- **THEN** a new outlook is generated

#### Scenario: Forced regeneration
- **WHEN** regeneration is forced
- **THEN** a new outlook is generated even without new data

#### Scenario: Same date again
- **WHEN** the outlook for an as_of is requested again with the same inputs and no forcing
- **THEN** nothing is regenerated or rewritten

### Requirement: Earlier outlooks stay as reference
Persisting an outlook SHALL NOT alter or delete the outlook of any other date.

#### Scenario: Reference chain
- **WHEN** an outlook for 2026-08-26 is written and an outlook for 2026-06-30 exists
- **THEN** the 2026-06-30 outlook is unchanged and the new outlook names it as `previous_as_of`

### Requirement: What changed and why
Each view of a new outlook SHALL state its change against the previous outlook as `new`, `unchanged`, `upgraded` or `downgraded`, the previous direction, and a reason citing evidence that is new since the previous as_of. The change kind and previous direction SHALL be derived by code from the two outlooks, not stated by the model.

#### Scenario: Direction changes with new evidence
- **WHEN** the energy view moves from `neutral` to `negative` and cites an event dated after the previous as_of
- **THEN** the view is `downgraded` with previous direction `neutral` and that event as the reason

#### Scenario: Direction changes without new evidence
- **WHEN** a view changes direction and cites no evidence dated after the previous as_of
- **THEN** the view keeps the previous direction and a gap records the rejected change

#### Scenario: First outlook
- **WHEN** no earlier outlook exists
- **THEN** every view is `new` and the outlook states that it is the first

### Requirement: Honest confidence and omissions
The system SHALL cap the confidence of a view that cites no event at `medium` and of a view built on insufficient market history at `low`, and SHALL list High or Severe events in the window since the previous as_of that no view cites.

#### Scenario: Thin history
- **WHEN** only one market snapshot exists at the as_of
- **THEN** no view has confidence above `low` and a gap states the history is insufficient

#### Scenario: Severe event not used
- **WHEN** a Severe event falls in the window and no driver or risk cites it
- **THEN** the outlook lists it under unaddressed events

### Requirement: Always delivered
Every outlook run SHALL return an outlook. Model failure, unparsable output, tool errors and policy denials SHALL appear as gaps with status `partial` or `insufficient_data`, and the previous views SHALL be carried forward when a failure prevents new ones.

#### Scenario: Model failure
- **WHEN** the model raises an error and a previous outlook exists
- **THEN** an outlook with status `partial`, the previous views marked `unchanged` and a gap naming the failure is returned

### Requirement: Persisted and runnable
The system SHALL persist each outlook with its evidence, a run summary and an audit log under the report folder for its as_of, and SHALL provide a command that takes the `as_of`.

#### Scenario: Command run
- **WHEN** the outlook command is run for as_of 2026-08-26
- **THEN** the market outlook file, its evidence file, the summary and the audit log exist under that date's outlook folder
