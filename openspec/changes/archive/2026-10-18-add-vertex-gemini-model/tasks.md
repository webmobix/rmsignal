# Tasks

## 1. Settings and dependency

- [x] 1.1 Add `model_provider`, `vertex_project`, `vertex_location` to `Settings` and read `RM_MODEL_PROVIDER`, `RM_VERTEX_PROJECT` (fallback `GOOGLE_CLOUD_PROJECT`), `RM_VERTEX_LOCATION` in `from_env`. Verify: new `Settings.from_env` tests cover defaults, overrides and the project fallback; `uv run pytest tests -k settings` passes.
- [x] 1.2 Add optional extra `vertex` with `langchain-google-genai` to `pyproject.toml`, resolve against the pinned `langchain-core`/`deepagents`, update `uv.lock`. Verify: `uv sync --extra vertex` succeeds and `uv run python -c "import langchain_google_genai"` works.
- [x] 1.3 Install the extra in the `Dockerfile` (`--extra firestore --extra vertex`, both sync steps). Verify: `docker build` succeeds and the image can import `langchain_google_genai`.

## 2. Provider switch in `build_model`

- [x] 2.1 Split `build_model` into `stub` check, `_gateway_model` (unchanged behaviour) and `_vertex_model` (`ChatGoogleGenerativeAI(vertexai=True, model, project, location, temperature=0)`), unknown provider raising an error that lists supported values. Verify: tests in `tests/test_agents.py` assert the returned class and parameters per provider, that `stub` ignores the provider, and the unknown-provider message.
- [x] 2.2 Add the early checks for `vertex`: missing extra becomes an error naming `uv sync --extra vertex`; missing ADC (`google.auth.default()`) becomes an error naming `gcloud auth application-default login` or a service account; project resolved from credentials when unset. Verify: tests with an injected credentials lookup and a simulated `ImportError` cover all three spec scenarios, with no network.
- [x] 2.3 Confirm the LLM call logger records a Vertex model call (duration, tokens, outcome `ok`/`error`). Verify: a test drives `LlmCallLogger` with a fake chat model emitting Gemini-shaped `usage_metadata` and asserts one record with token counts.

## 3. Live verification

- [x] 3.1 Smoke test locally with ADC: run one analyst with tools (`rm-dashboard-analyse` for one client) using `RM_MODEL_PROVIDER=vertex` and a Gemini Flash id. Verify: run completes, the guard accepts the output, the LLM log shows token counts; fix any Gemini tool-schema rejection in the tool adapter and re-run the OpenAI-path tests.
- [ ] 3.2 Run the same on Cloud Run (or with a service-account-impersonated local run) with no credential variables set. Verify: model calls succeed using only the attached service account.

## 4. Documentation

- [x] 4.1 Update the README "Models" section and variable table with the three new variables, a local ADC example and a Cloud Run example. Verify: the documented commands match `Settings.from_env` names.
- [x] 4.2 Update `docs/architecture.md` (model section) and `docs/agents.md` (`build_model`) to describe both providers and the early configuration errors. Verify: no remaining text says the gateway is the only model path.
