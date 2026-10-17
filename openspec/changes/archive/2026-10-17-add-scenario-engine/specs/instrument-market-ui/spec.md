## ADDED Requirements

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
