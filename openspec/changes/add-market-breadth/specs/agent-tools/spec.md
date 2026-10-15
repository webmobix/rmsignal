# Spec Delta

## ADDED Requirements

### Requirement: Breadth tool
The system SHALL provide a deterministic tool that returns the breadth of the instrument universe at an `as_of` (per asset class and, within equities, per sector: count, number and share that rose, median change, range, against the previous and the first snapshot) with the evidence envelope. It SHALL take only the `as_of`, SHALL read instrument prices and classification and nothing else, and SHALL return `insufficient_history` when fewer than two snapshots exist.

#### Scenario: Breadth at a date
- **WHEN** the breadth tool is called for as_of 2026-08-26
- **THEN** it returns an entry per asset class with the number of instruments and the share that rose against the previous snapshot, with sources

#### Scenario: Unchanged prices
- **WHEN** an asset class consists of instruments whose price did not change
- **THEN** none of them counts as up and the share that rose is zero

#### Scenario: One snapshot
- **WHEN** the tool is called for as_of 2025-12-31
- **THEN** it returns `insufficient_history` with a reason
