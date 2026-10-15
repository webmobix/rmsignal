"""What the RM overview delivers."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from rm_dashboard.actions.contracts import Category, Horizon, Importance, SourceRef
from rm_dashboard.domain import Gap, PolicyDecisionRecord

OverviewStatus = Literal["complete", "partial", "insufficient_data"]
WithoutActionsReason = Literal["actions_missing", "report_missing", "no_action_needed"]


class OverviewAction(BaseModel):
    """A client action as the dashboard shows it. Content is copied from the client action, never rewritten."""

    rank: int
    action_id: str
    origin: Literal["client_actions", "coverage"] = "client_actions"
    client_id: str
    client_name: str
    title: str
    what: str
    why: str
    category: Category
    importance: Importance
    horizon: Horizon = "none"
    due_date: date | None = None
    sources: list[SourceRef] = Field(default_factory=list)


class CategoryGroup(BaseModel):
    category: Category
    count: int
    action_ids: list[str]


class ClientWithoutActions(BaseModel):
    client_id: str
    client_name: str
    reason: WithoutActionsReason


class Theme(BaseModel):
    title: str
    action_ids: list[str]


class Overview(BaseModel):
    rm_id: str
    rm_name: str
    as_of: date
    status: OverviewStatus
    agent: str = "rm_overview"
    summary: str = ""
    themes: list[Theme] = []
    actions: list[OverviewAction] = []
    by_category: list[CategoryGroup] = []
    clients_without_actions: list[ClientWithoutActions] = []
    clients: list[str] = []
    gaps: list[Gap] = []
    policy_decisions: list[PolicyDecisionRecord] = []
