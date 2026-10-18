# Proposal

## Why

Models are reachable only through an OpenAI-compatible gateway, so running on Google Cloud means standing up a gateway in front of Gemini. The service already runs on Cloud Run with Firestore; calling Gemini Flash on Vertex AI directly, with the service's own Google identity, removes that hop and keeps the same setup usable on a developer machine.

## What Changes

- A new setting selects the model provider: `gateway` (today's behaviour, the default) or `vertex` (Gemini on Vertex AI). `stub` stays the deterministic test model and still wins when `RM_MODEL_NAME=stub`.
- With `vertex`, `RM_MODEL_NAME` is the Gemini model id (for example a Flash model), and project and location are configurable. When project is not set it is taken from the Google credentials.
- Authentication uses Google Application Default Credentials: the attached service account on Cloud Run, `gcloud auth application-default login` locally. No API key is configured or logged.
- `build_model` returns a LangChain Gemini chat model for `vertex`; every runner and interactive session keeps calling `build_model(settings, role=...)` unchanged.
- LLM call logging keeps working for the Gemini model (duration, token counts, outcome).
- The Vertex dependency is an optional extra (`vertex`), installed in the container image, so a gateway-only or stub install does not pull Google libraries.
- Misconfiguration (unknown provider, missing extra, no credentials) fails at model construction with a message naming the setting to fix, not midway through a run.
- README, architecture and agents docs describe the new settings and the local and Cloud Run setups.

## Capabilities

### New Capabilities

- `model-configuration`: how the model provider, model name, project, location and credentials are chosen from the environment, and how a bad configuration is reported.

### Modified Capabilities

- `analysis-agents`: "Provider-neutral model access" widens from a gateway endpoint to a configurable provider (gateway or Vertex AI Gemini), still with no provider-specific behaviour in agent logic.
- `llm-call-logging`: one record per call, with token counts, SHALL hold for Vertex Gemini calls too.

## Impact

- `src/rm_dashboard/settings.py` (new provider, project, location fields), `src/rm_dashboard/agents/gateway.py` (provider switch; likely renamed in spirit, kept as the import point).
- `pyproject.toml` / `uv.lock`: new optional extra `vertex`; `Dockerfile` installs it.
- `tests/test_agents.py`: provider selection and error cases, with no network or credentials.
- `README.md`, `docs/architecture.md`, `docs/agents.md`.
- Cloud Run deployment needs the service account to hold Vertex AI User and the Vertex AI API enabled (operational, outside the code).
- No change to the HTTP API, stored artifacts or agent prompts.
