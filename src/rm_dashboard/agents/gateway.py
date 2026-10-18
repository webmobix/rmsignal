"""Provider-neutral model access: an OpenAI-compatible gateway, or Gemini on Vertex AI, plus a model name."""

from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from rm_dashboard.settings import Settings

from .stub import StubChatModel

STUB_MODEL = "stub"
PROVIDERS = ("gateway", "vertex")


def build_model(settings: Settings, *, role: str = "instrument_analyst", mode: str = "normal",
                credentials: Callable[[], tuple[Any, str | None]] | None = None) -> BaseChatModel:
    """Model for one agent. ``stub`` selects the deterministic test model; otherwise ``settings.model_provider`` decides.

    ``credentials`` replaces ``google.auth.default`` (tests).
    """
    if settings.model_name == STUB_MODEL:
        return StubChatModel(role=role, mode=mode)
    if settings.model_provider == "gateway":
        return ChatOpenAI(
            model=settings.model_name, base_url=settings.gateway_url, api_key=settings.gateway_api_key, temperature=0,
        )
    if settings.model_provider == "vertex":
        return _vertex_model(settings, credentials)
    raise ValueError(f"unsupported RM_MODEL_PROVIDER {settings.model_provider!r}; supported: {', '.join(PROVIDERS)}")


def _vertex_model(settings: Settings, credentials: Callable[[], tuple[Any, str | None]] | None) -> BaseChatModel:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:
        raise RuntimeError("RM_MODEL_PROVIDER=vertex needs the Vertex dependencies: uv sync --extra vertex") from e
    try:
        if credentials is None:
            import google.auth
            credentials = google.auth.default
        creds, creds_project = credentials()
    except Exception as e:  # google.auth.exceptions.DefaultCredentialsError and friends
        raise RuntimeError(
            "RM_MODEL_PROVIDER=vertex found no Google credentials: run `gcloud auth application-default login` "
            f"locally, or attach a service account on Google Cloud ({e})") from e
    project = settings.vertex_project or creds_project
    if not project:
        raise RuntimeError("RM_MODEL_PROVIDER=vertex needs a project: set RM_VERTEX_PROJECT or GOOGLE_CLOUD_PROJECT")
    return ChatGoogleGenerativeAI(
        model=settings.model_name, vertexai=True, project=project, location=settings.vertex_location,
        credentials=creds, temperature=0,
    )
