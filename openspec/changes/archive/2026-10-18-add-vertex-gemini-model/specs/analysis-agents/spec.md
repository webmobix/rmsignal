# Spec Delta

## MODIFIED Requirements

### Requirement: Provider-neutral model access
Models SHALL be accessed through a configurable provider (an OpenAI-compatible gateway endpoint, or Gemini on Vertex AI) and model name, with no provider-specific behaviour in agent logic. Tool names, structured outputs and guard behaviour SHALL be the same for every provider.

#### Scenario: Swap model
- **WHEN** the configured model name changes
- **THEN** agents run unchanged

#### Scenario: Swap provider
- **WHEN** the configured provider changes between `gateway` and `vertex`
- **THEN** agents, tools, prompts and output guards run unchanged
