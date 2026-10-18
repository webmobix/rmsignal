"""Tool specification and shared parameter models. Parameters are identifiers and dates only."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from rm_dashboard.domain import ToolResult
from rm_dashboard.pit import PitRepository
from rm_dashboard.settings import Settings
from rm_dashboard.store import ArtifactStore, as_store

VERSION = "1"


class Params(BaseModel):
    """Base for tool parameters: ``as_of`` is required and there is no default."""

    model_config = ConfigDict(extra="forbid")

    as_of: date


class ClientParams(Params):
    client_id: str


class PortfolioParams(Params):
    portfolio_id: str


class InstrumentParams(Params):
    instrument_id: str


class FacilityParams(Params):
    facility_id: str
    horizon_days: int | None = None


class AsOfOnly(Params):
    pass


@dataclass
class ToolContext:
    """Shared by all tools. ``run`` and ``agent`` are filled in per call by the toolbox."""

    repo: PitRepository
    settings: Settings = Settings()
    peers: dict[str, Any] = field(default_factory=dict)  # name -> peer agent client (``ask`` method)
    run: Any = None
    agent: str = ""
    artifacts: ArtifactStore | None = None  # where generated artifacts live (outlooks, scenario results)
    store: Any = None  # the run's EvidenceStore, filled in per call by the toolbox

    def __post_init__(self) -> None:
        if isinstance(self.artifacts, (str, Path)):  # a folder or file path names a SQLite store
            self.artifacts = as_store(self.artifacts)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params: type[Params]
    fn: Callable[[ToolContext, Any], ToolResult]
    kind: str  # "domain" | "analytics"
    version: str = VERSION
