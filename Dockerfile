# Python app image; which script runs is chosen by APP_ENTRYPOINT.
# Build:  docker build -t rm-dashboard --build-arg APP_ENTRYPOINT="uv run rm-dashboard-serve" .
# Run:    docker run --rm -p 8080:8080 -e PORT=8080 -e RM_DATA_SOURCE=... -e RM_ARTIFACT_STORE=... rm-dashboard
# Cloud Run: sets $PORT (8080) itself; override the script per service with --set-env-vars APP_ENTRYPOINT=...

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app

# deps first, for layer caching
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --extra firestore --extra vertex --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --extra firestore --extra vertex

ENV PATH="/opt/venv/bin:$PATH" UV_NO_SYNC=1
ENV HOST=0.0.0.0

# Model: Gemini on Vertex AI via the runtime service account; override per service with --set-env-vars.
ENV RM_MODEL_PROVIDER=vertex
ENV RM_MODEL_NAME=gemini-3.8-flash
ENV PORT=8080

# Script or command to run: build arg sets the default, a runtime env var overrides it.
ARG APP_ENTRYPOINT="uv run rm-dashboard-serve"
ENV APP_ENTRYPOINT=${APP_ENTRYPOINT}

CMD sh -c "${APP_ENTRYPOINT}"
