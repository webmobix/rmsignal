"""The artifact seam: generated artifacts are addressed by ``(as_of, kind, key)`` and hold JSON text."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

GLOBAL = date.min
"""The as-of of artifacts that belong to no date (the scenario catalogue). Never listed by ``dates()``."""


class Kind(StrEnum):
    REPORT = "report"
    RECONCILIATION = "reconciliation"
    MANDATE_RECONCILIATION = "mandate-reconciliation"
    ACTIONS = "actions"
    OVERVIEW = "overview"
    OUTLOOK_MARKET = "outlook-market"
    OUTLOOK_INSTRUMENT = "outlook-instrument"
    SCENARIO_VECTOR = "scenario-vector"
    SCENARIO_IMPACT = "scenario-impact"
    SCENARIO_CLIENT = "scenario-client"
    SCENARIO_ROLLUP = "scenario-rollup"
    SCENARIO_CATALOGUE = "scenario-catalogue"
    RUN_SUMMARY = "run-summary"
    AUDIT = "audit"
    EVIDENCE = "evidence"
    EVIDENCE_INDEX = "evidence-index"


@dataclass(frozen=True)
class Artifact:
    as_of: date
    kind: Kind
    key: str
    body: str


class ReadOnlyStore(ValueError):
    """Raised by a backend that publishes artifacts but does not accept them from runners."""


class ArtifactStore(Protocol):
    """Whole-or-absent saves, replace on an existing address, stable (ascending key) listings. Never reads the clock."""

    @property
    def location(self) -> str: ...
    def put(self, as_of: date, kind: Kind, key: str, body: str) -> None: ...
    def put_many(self, items: Iterable[Artifact]) -> None: ...
    def get(self, as_of: date, kind: Kind, key: str) -> str | None: ...
    def get_many(self, as_of: date, kind: Kind, keys: Iterable[str]) -> dict[str, str]: ...
    def keys(self, as_of: date, kind: Kind, prefix: str = "") -> list[str]: ...
    def dates(self) -> list[date]: ...
    def delete_prefix(self, as_of: date, kind: Kind, prefix: str = "") -> int: ...


M = TypeVar("M", bound=BaseModel)


def read_model(store: ArtifactStore, as_of: date, kind: Kind, key: str, model: type[M]) -> M | None:
    """A typed read. A body that no longer validates is as good as absent."""
    body = store.get(as_of, kind, key)
    if body is None:
        return None
    try:
        return model.model_validate_json(body)
    except ValueError:
        return None


def read_json(store: ArtifactStore, as_of: date, kind: Kind, key: str):
    """The decoded JSON body, or ``None`` when absent or not JSON."""
    import json

    body = store.get(as_of, kind, key)
    if body is None:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def check_writable(store: ArtifactStore) -> None:
    """Raise ``ReadOnlyStore`` (naming the way to publish) when the backend does not accept artifacts from runners."""
    require = getattr(store, "require_writable", None)
    if require is not None:
        require()


def log_dir(store: ArtifactStore, as_of: date, stage: str) -> Path:
    """A local folder for a stage's operational log (``run.log``), beside a local store and never inside it."""
    path = getattr(store, "path", None)
    root = Path(path).parent if path is not None else Path("logs")
    return root / "logs" / as_of.isoformat() / stage
