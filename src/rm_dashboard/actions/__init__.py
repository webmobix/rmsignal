"""Per-client next actions: what to do, why, how important, by when, and what it rests on."""

from .contracts import Action, ClientActions, NotActioned, SourceRef

__all__ = ["Action", "ClientActions", "NotActioned", "SourceRef", "derive_actions"]


def __getattr__(name: str):  # derive_actions pulls in the agent stack; import it lazily
    if name == "derive_actions":
        from .agent import derive_actions

        return derive_actions
    raise AttributeError(name)
