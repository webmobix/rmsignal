"""The RM overview: client actions of a date, ranked and linked, for the dashboard view."""

from .contracts import CategoryGroup, ClientWithoutActions, Overview, OverviewAction, Theme

__all__ = ["CategoryGroup", "ClientWithoutActions", "Overview", "OverviewAction", "Theme", "create_overview"]


def __getattr__(name: str):  # create_overview pulls in the agent stack; import it lazily
    if name == "create_overview":
        from .summary import create_overview

        return create_overview
    raise AttributeError(name)
