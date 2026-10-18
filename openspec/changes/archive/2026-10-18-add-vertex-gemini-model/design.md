# Design

## Context

`build_model(settings, role=, mode=)` in `agents/gateway.py` is the single place models are made: `stub` gives `StubChatModel`, anything else gives `ChatOpenAI` pointed at `RM_GATEWAY_URL`. All runners and the interactive session call it, and `Settings.from_env` is the only reader of the environment. LLM logging is a LangChain callback (`llmlog.py`) that reads `usage_metadata` from the response, so it is model-class agnostic. Tool names are already provider-safe (`lc_name` replaces dots). The container image is built with `uv sync --extra firestore`, which is the pattern for optional Google dependencies. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Gemini Flash on Vertex AI selectable by configuration on Cloud Run and locally, through the existing `build_model` seam.
- Gateway stays the default and behaves as before.
- Misconfiguration surfaces at build time with an actionable message.

**Non-Goals:**
- Per-role model overrides (every role uses the one configured model, as today).
- Gemini Developer API (AI Studio API key) access; only Vertex AI.
- Non-Gemini Vertex models (Claude on Vertex, Model Garden).
- Tuning generation parameters beyond today's `temperature=0`.
- Provisioning IAM or enabling the API.

## Decisions

**Provider is a separate setting, not inferred from the model name.** New `RM_MODEL_PROVIDER` (`gateway` default, `vertex`). Inferring from a `gemini-` prefix would silently reroute a gateway that serves Gemini under that name (LiteLLM does), breaking today's setups. `stub` is checked first so tests never touch Google. Alternative: a `vertex:gemini-...` prefix in `RM_MODEL_NAME`; rejected because it overloads one variable and `docs` already name it a plain model name.

**LangChain class: `langchain-google-genai` `ChatGoogleGenerativeAI` with `vertexai=True`.** It is the maintained integration for Gemini, supports Vertex via ADC, tool calling and structured output, and fills `usage_metadata`. Alternative: `langchain-google-vertexai` `ChatVertexAI`; kept as fallback only if the first cannot satisfy the tool-calling smoke test in the tasks. The exact version is pinned in `pyproject.toml` after checking it against `langchain-core` as resolved by `deepagents==0.7.25`.

**Settings.** `model_provider: str = "gateway"`, `vertex_project: str | None`, `vertex_location: str = "global"` from `RM_MODEL_PROVIDER`, `RM_VERTEX_PROJECT`, `RM_VERTEX_LOCATION`. Project falls back to `GOOGLE_CLOUD_PROJECT`, then to the project in ADC. The default location is `global` because newer Gemini Flash models are served there; users pin a region (for example `europe-west1`) when data residency requires it. The gateway variables are ignored for `vertex`. Alternative: reuse the Firestore project spec; rejected, the two services can live in different projects.

**Credentials: ADC only.** No key setting. Build time calls `google.auth.default()` to fail early with a message ("run `gcloud auth application-default login` or attach a service account") instead of failing on the first agent call. Local and Cloud Run differ only in where ADC comes from.

**Optional extra `vertex`.** Mirrors `firestore`. Import is lazy inside the vertex branch; `ImportError` is re-raised as a configuration error naming `uv sync --extra vertex`. The Dockerfile installs `--extra firestore --extra vertex` so the Cloud Run image works with `RM_MODEL_PROVIDER=vertex` alone.

**Shape of the code.** `build_model` keeps its signature and dispatches to two small private builders (`_gateway_model`, `_vertex_model`). The module name `gateway.py` stays to avoid churning imports; its docstring is updated. Unknown provider raises `ValueError` listing the supported values.

**No agent-side changes.** Prompts, guards, and tool adapters are unchanged; provider differences must not leak there (spec requirement).

## Risks / Trade-offs

- [Gemini tool-schema strictness: Gemini rejects some JSON-schema constructs OpenAI accepts, and newer Gemini models require thought signatures to be echoed in multi-turn tool use] → A live smoke task runs one real analyst with tools against Vertex; any rejected schema is fixed in the tool adapter without changing OpenAI behaviour. Version of `langchain-google-genai` chosen to handle signatures.
- [Quota and latency differ from the gateway; `RM_MAX_CONCURRENCY` may hit 429s] → Document the setting; the LLM log already records error outcomes. No retry change in this proposal.
- [`global` location may not satisfy residency] → Location is configurable and documented.
- [New dependency weight in the image] → Optional extra; stub and gateway installs unaffected.
- [Credentials check at build time makes unit tests need ADC] → Tests inject a fake credentials lookup; no test touches the network.

## Migration Plan

Additive. Existing environments keep working with no new variables. To adopt on Cloud Run: enable the Vertex AI API, grant the service account Vertex AI User, set `RM_MODEL_PROVIDER=vertex`, `RM_MODEL_NAME=<gemini flash id>`, optionally `RM_VERTEX_LOCATION`. Rollback: unset `RM_MODEL_PROVIDER`.
