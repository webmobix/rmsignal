# Spec Delta

## ADDED Requirements

### Requirement: Logging is provider-independent
The one-record-per-call log SHALL be produced for every supported model provider, including Gemini on Vertex AI, with the same fields. Token counts SHALL be taken from the provider's reported usage; when a provider reports none, the counts SHALL be absent and the call SHALL be counted as without usage, as for any other model.

#### Scenario: Vertex Gemini call
- **WHEN** an agent makes a model call through the `vertex` provider
- **THEN** one record is logged with run id, thread id, agent, runner, duration, token counts and outcome `ok`

#### Scenario: Vertex call fails
- **WHEN** a Vertex call raises an error such as permission denied
- **THEN** one record with outcome `error` and the error type is logged, and the run continues as for any failed call
