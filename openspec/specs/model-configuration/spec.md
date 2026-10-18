# model-configuration Specification

## Purpose

Defines how the model used by every agent is selected from the environment, on a developer machine and on Google Cloud, and how an invalid selection is reported.

## Requirements

### Requirement: Model provider is configurable
The system SHALL support these model providers, selected by configuration: `gateway` (an OpenAI-compatible endpoint, the default) and `vertex` (Gemini models on Vertex AI). A model name of `stub` SHALL select the deterministic test model regardless of the provider. Selecting a provider SHALL NOT require any change to agent code, prompts or runner arguments.

#### Scenario: Default is unchanged
- **WHEN** no provider is configured and a model name other than `stub` is set
- **THEN** the model is reached through the configured gateway endpoint exactly as before

#### Scenario: Vertex Gemini selected
- **WHEN** the provider is `vertex` and the model name is a Gemini model id
- **THEN** every model-backed role calls that Gemini model on Vertex AI

#### Scenario: Stub wins
- **WHEN** the model name is `stub` and the provider is `vertex`
- **THEN** the deterministic test model is used and no Google call or credential lookup happens

### Requirement: Vertex project and location
With the `vertex` provider the Google Cloud project and location SHALL be configurable. If the project is not configured it SHALL be taken from the active Google credentials. A location SHALL always be in effect, with a documented default.

#### Scenario: Explicit project and location
- **WHEN** project and location are configured
- **THEN** calls go to that project and location

#### Scenario: Project from credentials
- **WHEN** the provider is `vertex` and no project is configured, and the credentials carry a project
- **THEN** that project is used

### Requirement: Google credentials, not keys
With the `vertex` provider the system SHALL authenticate with Google Application Default Credentials: the runtime service account on Google Cloud, and the developer's own credentials locally. It SHALL NOT require or accept an API key setting for Vertex, and SHALL NOT write credentials or tokens to logs.

#### Scenario: Running on Cloud Run
- **WHEN** the service runs on Cloud Run with a service account that may call Vertex AI
- **THEN** model calls succeed with no credential setting in the environment

#### Scenario: Running locally
- **WHEN** a developer has signed in with application default credentials and sets the provider and model name
- **THEN** the runners use Gemini on Vertex AI

### Requirement: Invalid configuration fails early
An unknown provider, a `vertex` provider without the Vertex dependencies installed, or a `vertex` provider without usable credentials SHALL raise an error when the model is built, before any agent work starts. The message SHALL name the setting or the install step to fix.

#### Scenario: Unknown provider
- **WHEN** the provider is set to a value that is not supported
- **THEN** building the model fails with a message listing the supported providers

#### Scenario: No credentials
- **WHEN** the provider is `vertex` and no Google credentials are available
- **THEN** building the model fails with a message that says how to sign in or attach a service account

#### Scenario: Dependency not installed
- **WHEN** the provider is `vertex` and the Vertex extra is not installed
- **THEN** building the model fails with a message naming the extra to install
