# Spec Delta

## ADDED Requirements

### Requirement: Breadth of the instrument universe as evidence
The market outlook SHALL be able to rest on the breadth of the instrument universe: for each asset class, and for each sector within equities, the number of instruments, how many rose and the share that rose, the median change and the range, against the previous snapshot and the first snapshot. Breadth SHALL be computed from instrument prices at the effective snapshot and earlier, SHALL treat an unchanged price as neither up nor down, and SHALL mark a group of fewer than three instruments as small. A driver or risk about whether a move is broad or narrow SHALL cite the breadth result.

#### Scenario: Broad or narrow
- **WHEN** the market outlook is produced and instrument prices exist at two or more snapshots
- **THEN** a breadth result with the share of instruments that rose per asset class is available as evidence and a driver may cite it

#### Scenario: Small group
- **WHEN** an asset class or sector has fewer than three priced instruments
- **THEN** its breadth entry is marked small

#### Scenario: Breadth figures are checked
- **WHEN** a driver states a share or median that the cited breadth result does not contain
- **THEN** the driver is removed and a gap is recorded

#### Scenario: Short history
- **WHEN** fewer than two snapshots exist at the as_of
- **THEN** the breadth result is `insufficient_history` and no view has confidence above `low`

### Requirement: Facts up, opinions down
The market outlook SHALL NOT use instrument outlooks or any aggregate of instrument views as evidence, and SHALL be independent of holdings and clients: the instrument universe for breadth SHALL be the instrument master, not the instruments held. Instrument outlooks MAY use the market outlook.

#### Scenario: No instrument opinions
- **WHEN** the tools available to the market outlook are inspected
- **THEN** none returns an instrument outlook or a summary of instrument views

#### Scenario: Universe independent of clients
- **WHEN** the set of instruments held by clients changes and no price changes
- **THEN** the breadth result and the market outlook's inputs are unchanged

#### Scenario: Breadth as new evidence
- **WHEN** a view changes direction and cites a breadth result whose latest snapshot is later than the previous outlook's market snapshot
- **THEN** the change is accepted as resting on newer evidence
