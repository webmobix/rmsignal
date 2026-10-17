# instrument-market-ui Specification

## Purpose
Defines the instruments list and view, the market outlook view and the event timeline with derived reach.

## Requirements

### Requirement: Instruments list
The instruments route SHALL list instruments with asset class, sector, region, latest price, change since the previous snapshot, amount held across the book and whether an outlook exists, with a chart of USD held by asset class.

#### Scenario: Held filter
- **WHEN** the user filters to held instruments
- **THEN** instruments with zero held USD are hidden

### Requirement: Instrument view
The instrument route SHALL show master data including the underlying reference, the price path over the snapshots, the holders linked to their clients and portfolios with a chart of USD held per client, and the outlook with its context and evidence when one exists.

#### Scenario: No outlook
- **WHEN** an instrument has no outlook
- **THEN** the outlook region shows the gap notice and the rest of the view renders

### Requirement: Market view
The market route SHALL show the market outlook summary and views, what changed since the previous outlook, and events not yet addressed, with evidence opening in the drawer.

#### Scenario: Open evidence
- **WHEN** the user selects the evidence on a view
- **THEN** the drawer opens with the tool result

### Requirement: Event timeline with reach
The market route SHALL show the event log as a timeline with severity and channels, and for each event the clients and instruments it reaches, labelled as derived, each linking to its view.

#### Scenario: Event to client
- **WHEN** the user selects a client under an event
- **THEN** the client view opens

### Requirement: Scenario roll-up panel on the market view
The market page SHALL show a scenario panel, between the market views and the event timeline, with a scenario picker, book totals for best, likely and worst, the most-hit clients linking to their scenario tab, crossings, the roll-up summary, coverage and the conditional banner. Content SHALL come from the roll-up endpoint. The overview page SHALL NOT show this panel.

#### Scenario: Panel shown
- **WHEN** the market page loads and computed roll-ups exist
- **THEN** the panel shows the selected scenario's book totals and ranked clients

#### Scenario: Open client
- **WHEN** the user selects a client in the ranking
- **THEN** that client's scenario tab opens on the same scenario

#### Scenario: No roll-up
- **WHEN** no computed roll-up exists
- **THEN** the panel states that scenarios have not been run for this date
