## MODIFIED Requirements

### Requirement: Overview page
The home route SHALL show the RM's overview for the latest date: a metric strip (clients, total AuM, actions, counts per importance tier), the model summary and themes when present, and a table of urgent actions. The tier counts SHALL link to the Actions page filtered to that tier, so that medium and low actions, which the home page does not list, remain one click away. In the summary, each marked client SHALL show as the client's name in bold, linking to the client view, and each marked action in italic; all other text SHALL show as plain text.

#### Scenario: Latest run
- **WHEN** the overview loads on the 2026-08-26 data
- **THEN** it shows 20 clients, 33 actions and the tier counts, with the status "partial" visible

#### Scenario: Tier count link
- **WHEN** the user selects the "medium" count in the metric strip
- **THEN** the Actions page opens filtered to the medium tier

#### Scenario: Client and action in the summary
- **WHEN** the summary reads "[[CL-0001]] _call before Friday_."
- **THEN** the client's name appears in bold as a link to that client's view, followed by "call before Friday" in italic

#### Scenario: Plain or unresolvable summary
- **WHEN** the summary has no markup, or marks a client id that is not among the overview's clients
- **THEN** the text shows as written, the unresolvable id as plain text, and no markup characters beyond that are interpreted
