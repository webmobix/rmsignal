# Spec Delta

## Purpose

Reconciles the mandate, position-limit and exclusion breaches computed for a client's portfolios with what the RM's notes say about them, so that the RM and the actions stage know which breaches are acknowledged, client-directed or misunderstood.

## ADDED Requirements

### Requirement: Computed breaches are the only subject
The stage SHALL reconcile only breaches present in the client's persisted evidence for the date (asset-class band breaches, single-position limit breaches and exclusion breaches) and SHALL NOT compute a breach from a note. Custody portfolios SHALL NOT be reconciled.

#### Scenario: Breach in evidence
- **WHEN** the evidence of a client contains a band breach for portfolio PF-0009
- **THEN** the result contains one entry for that breach naming the portfolio, the breach and its evidence id

#### Scenario: Note without a breach
- **WHEN** a note says a limit was waived and no breach is in the evidence
- **THEN** no result is produced for that note

#### Scenario: Custody portfolio
- **WHEN** a client's custody portfolio holds a concentrated position
- **THEN** it has no entry

#### Scenario: Breach check missing from evidence
- **WHEN** a managed portfolio has no persisted mandate or exclusion check in the evidence
- **THEN** a gap names the portfolio and the status is at most `partial`

### Requirement: One status per breach
Each reconciled breach SHALL have exactly one status: `no_note`, `acknowledged`, `client_directed` or `contradicted`, with a rationale and, except for `no_note`, the ids of the notes it rests on.

#### Scenario: Waiver claimed
- **WHEN** a note says the client instructed a purchase beyond the commodity ceiling and a waiver is on file
- **THEN** the breach is `client_directed` and the rationale quotes the waiver claim

#### Scenario: Client declines to act
- **WHEN** a note says the client will not deploy excess cash or sell the position that breaches a limit
- **THEN** the breach is `client_directed`

#### Scenario: Aware but nothing decided
- **WHEN** a note shows the client knows a position has grown beyond its original sizing and no instruction is recorded
- **THEN** the breach is `acknowledged`

#### Scenario: Book said to be aligned
- **WHEN** a note says the client believes the portfolio is fully aligned with its exclusions and the evidence shows an excluded holding
- **THEN** the breach is `contradicted`

### Requirement: No note is neutral
A breach no note bears on SHALL have status `no_note`, and the absence of a note SHALL NOT be reported as a gap, a contradiction or a reduction of importance.

#### Scenario: Client without notes
- **WHEN** a client has breaches and no notes up to `as_of`
- **THEN** every breach is `no_note`, no model is called and the status is `complete`

#### Scenario: Notes about other topics
- **WHEN** a client's notes concern liquidity only
- **THEN** every breach is `no_note`

### Requirement: Notes are claims, not evidence
A note SHALL NOT remove, reduce or change a computed breach. A waiver, instruction or belief in a note SHALL be quoted as the RM's statement and SHALL NOT be treated as verified.

#### Scenario: Waiver claimed
- **WHEN** a note claims a suitability waiver is on file
- **THEN** the breach remains reported with its computed gap and the result states that the waiver is a claim to verify

### Requirement: Notes matched to the right portfolio
Notes belong to a client. For a client with several managed portfolios, the stage SHALL attribute a note to a portfolio's breach only when the note names or clearly implies the asset class, instrument or portfolio, and otherwise SHALL list the note as ambiguous without applying it to any portfolio.

#### Scenario: Two portfolios, one note
- **WHEN** a client has breaches in two portfolios and a note concerns gold held in only one of them
- **THEN** the status applies to that portfolio's breach and the other breach is unaffected

#### Scenario: Cannot be attributed
- **WHEN** a note could concern breaches in either portfolio and nothing decides between them
- **THEN** it is listed as ambiguous and both breaches keep their other status

### Requirement: Evidence on both sides
A result with a status other than `no_note` SHALL cite the breach evidence id from the client's persisted evidence and at least one note dated on or before `as_of`, and every number in its rationale SHALL equal a number in the cited evidence or be quoted from the cited note.

#### Scenario: Unsupported status
- **WHEN** a model result cites no note, an unknown note, a note dated after `as_of` or an unknown evidence id
- **THEN** its status becomes `no_note` and a gap is recorded

#### Scenario: Invented figure
- **WHEN** a rationale contains a figure absent from the cited evidence and note
- **THEN** the result is reset to `no_note`, a gap is recorded and the status is at most `partial`

### Requirement: Point-in-time
Notes dated after `as_of` SHALL NOT be used, and a client without a persisted report at `as_of` SHALL yield a result with status `insufficient_data`.

#### Scenario: Later note
- **WHEN** reconciling as_of 2026-03-31 and a note is dated 2026-04-14
- **THEN** that note is not used

### Requirement: Always delivered and reproducible
The stage SHALL return a result with status `complete`, `partial` or `insufficient_data` and never raise an unhandled error, write it to `mandate-reconciliation/<client>.json` under the as_of folder, and give identical content for the same evidence, notes and model output.

#### Scenario: Model failure
- **WHEN** the model raises or returns unparsable output
- **THEN** a `partial` result with every breach `no_note` and a gap describing the failure is written

#### Scenario: Names
- **WHEN** model input is prepared
- **THEN** client and person names are pseudonymised and restored only in the delivered output
