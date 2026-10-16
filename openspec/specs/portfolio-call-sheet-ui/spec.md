# portfolio-call-sheet-ui Specification

## Purpose

Lets the RM open one tab on the portfolio screen during a client call and find the answer to each question the client is likely to ask.

## Requirements

### Requirement: Call sheet tab
The portfolio route SHALL offer a Call sheet tab beside the existing view, presenting the sections as the questions "How am I doing?", "Am I within my mandate?", "What do I own?", "What does the bank think?", "What is happening?", "How are my cash and credit?" and "When did we last speak?".

#### Scenario: Open the tab
- **WHEN** the RM selects the Call sheet tab
- **THEN** the seven sections are shown in that order without leaving the portfolio route

#### Scenario: Section with a gap
- **WHEN** a section has a gap
- **THEN** the section shows what is missing and the other sections render normally

### Requirement: Every position shows the bank's view
The bank-view section SHALL list every position with its outlook direction, horizon, confidence, date and reasons, and SHALL state "no outlook" for a position without one. Views SHALL be worded as the bank's view as of their date and SHALL NOT use recommendation wording.

#### Scenario: Position without outlook
- **WHEN** a position has no outlook
- **THEN** its row says "no outlook" and is not hidden

#### Scenario: Older outlook
- **WHEN** an outlook is older than the sheet's date
- **THEN** its own date is shown beside the view

### Requirement: Mandate answers show what the RM has noted
The mandate section SHALL show each breach with its reconciliation status and the note text quoted as the RM's statement, and a claimed waiver SHALL NOT be shown as a pass.

#### Scenario: Claimed waiver
- **WHEN** a breach is `client_directed` with a claimed waiver
- **THEN** the note is quoted, the status reads as a claim to verify and the breach stays marked

### Requirement: Figures link to their source
Instrument ids, event entries and note ids on the call sheet SHALL link to the instrument view, the events view or the note, and the sheet SHALL show the date it is as of.

#### Scenario: Open an instrument
- **WHEN** the RM selects an instrument in the bank-view section
- **THEN** the instrument view opens

### Requirement: Usable during a call
The call sheet SHALL render all sections from one request, show a loading and an error state, and remain readable at laptop width without horizontal scrolling of the page.

#### Scenario: Request fails
- **WHEN** the call-sheet request fails
- **THEN** the tab shows an error state and the rest of the portfolio page remains usable
