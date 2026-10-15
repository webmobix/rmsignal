"""Provider-neutral model access: an OpenAI-compatible gateway endpoint plus a model name."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from rm_dashboard.settings import Settings

from .stub import StubChatModel

STUB_MODEL = "stub"


def build_model(settings: Settings, *, role: str = "instrument_analyst", mode: str = "normal") -> BaseChatModel:
    """Model for one agent. ``stub`` selects the deterministic test model; anything else is a gateway model name."""
    if settings.model_name == STUB_MODEL:
        return StubChatModel(role=role, mode=mode)
    return ChatOpenAI(
        model=settings.model_name, base_url=settings.gateway_url, api_key=settings.gateway_api_key, temperature=0,
    )
