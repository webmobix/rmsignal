# Spec Delta

## ADDED Requirements

### Requirement: Typography scale
The app SHALL size text only with the Tailwind type scale and theme tokens, never with arbitrary pixel values. Normal text SHALL be 16px. Blocks of text (paragraphs, list items, descriptions, rationales, notes, captions, empty and loading messages) SHALL render at normal size or larger and SHALL NOT be smaller than normal.

#### Scenario: Body text
- **WHEN** a paragraph, description or rationale is shown on any page
- **THEN** it renders at the normal 16px size or larger, with no smaller size override

#### Scenario: No arbitrary sizes
- **WHEN** a component sets a text size
- **THEN** it uses a Tailwind scale class or a theme token and not a literal pixel value

### Requirement: Small text limited to labels
Text smaller than normal SHALL be limited to short non-prose labels: navigation, tabs, filter controls, badges, avatar initials, metric hints, table headers and cells, and uppercase eyebrow headings.

#### Scenario: Badge
- **WHEN** a tier badge or avatar initials are shown
- **THEN** they may render below normal size

#### Scenario: Sentence content
- **WHEN** content is a sentence or longer explanation
- **THEN** it does not render below normal size

### Requirement: Page headline token
The page headline SHALL use a fluid size defined as a theme token built from the Tailwind scale, scaling between the 3xl and 4xl sizes with viewport width.

#### Scenario: Headline scaling
- **WHEN** the viewport width changes
- **THEN** the page headline scales between the 3xl and 4xl sizes without an arbitrary clamp in markup
