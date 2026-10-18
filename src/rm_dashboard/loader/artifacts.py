"""Copying artifacts between backends: from an artifact store or an older ``reports/`` folder, to an artifact store."""

import re
from collections import Counter
from collections.abc import Iterable, Iterator
from datetime import date
from pathlib import Path
from typing import Protocol

from rm_dashboard.store import GLOBAL, Artifact, ArtifactStore, Kind, SqliteArtifactStore, open_store
from rm_dashboard.store.factory import sqlite_path
from rm_dashboard.store.folder import FolderArtifactSource, looks_like_reports_folder

BATCH = 400
"""Artifacts written per call: under the 500-operation limit of a Firestore batch."""

# Evidence before what cites it, results before the summaries that describe them.
_ORDER = [Kind.EVIDENCE, Kind.EVIDENCE_INDEX, Kind.AUDIT, Kind.SCENARIO_CATALOGUE, Kind.REPORT, Kind.RECONCILIATION,
          Kind.MANDATE_RECONCILIATION, Kind.ACTIONS, Kind.OVERVIEW, Kind.OUTLOOK_MARKET, Kind.OUTLOOK_INSTRUMENT,
          Kind.SCENARIO_VECTOR, Kind.SCENARIO_IMPACT, Kind.SCENARIO_CLIENT, Kind.SCENARIO_ROLLUP, Kind.RUN_SUMMARY]
assert set(_ORDER) == set(Kind)


class LoadError(Exception):
    """The load could not be done. The message says what to change, or that a re-run completes it."""


class ArtifactSource(Protocol):
    @property
    def location(self) -> str: ...
    def dates(self) -> list[date]: ...
    def items(self, as_of: date) -> Iterator[Artifact]: ...


class StoreSource:
    """An artifact store as a source."""

    def __init__(self, store: ArtifactStore):
        self.store = store

    @property
    def location(self) -> str:
        return self.store.location

    def dates(self) -> list[date]:
        return self.store.dates()

    def items(self, as_of: date) -> Iterator[Artifact]:
        for kind in _ORDER:
            keys = self.store.keys(as_of, kind)
            for i in range(0, len(keys), BATCH):
                bodies = self.store.get_many(as_of, kind, keys[i:i + BATCH])
                for k in keys[i:i + BATCH]:
                    if k in bodies:
                        yield Artifact(as_of, kind, k, bodies[k])


def open_artifact_source(spec: str | Path) -> ArtifactSource:
    """``sqlite:<file or folder>`` or ``firestore:<project>`` name a store; ``folder:<path>`` a ``reports/`` folder tree. A bare
    path is a ``reports/`` folder when it holds date folders, else the store in it (or the ``.db`` file itself)."""
    text = str(spec)
    if text.startswith("folder:"):
        root = Path(text[len("folder:"):])
        if not root.is_dir():
            raise LoadError(f"reports folder not found: {root}")
        return FolderArtifactSource(root)
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", text):
        return StoreSource(open_store(text))
    path = Path(text)
    if path.is_dir():
        has_db, has_dates = (path / "artifacts.db").is_file(), looks_like_reports_folder(path)
        if has_db and has_dates:
            raise LoadError(f"{path} holds both artifacts.db and date folders: say which with sqlite:{path / 'artifacts.db'} or folder:{path}")
        if has_dates:
            return FolderArtifactSource(path)
        if has_db:
            return StoreSource(SqliteArtifactStore(sqlite_path(path)))
        raise LoadError(f"nothing to load in {path}: no artifacts.db and no <as-of> folders")
    if path.is_file():
        return StoreSource(SqliteArtifactStore(path))
    raise LoadError(f"artifact source not found: {path}")


def open_target_store(spec: str | Path) -> ArtifactStore:
    """The store the loader writes to: like ``open_store``, but a Firestore target accepts writes."""
    text = str(spec)
    if text.startswith("firestore:"):
        from rm_dashboard.store.firestore import open_firestore_store  # lazy: the Firestore client library is optional

        return open_firestore_store(text[len("firestore:"):], writable=True)
    return open_store(text)


def _batches(items: Iterable[Artifact]) -> Iterator[list[Artifact]]:
    batch: list[Artifact] = []
    for a in items:
        batch.append(a)
        if len(batch) >= BATCH:
            yield batch
            batch = []
    if batch:
        yield batch


def _dates_to_copy(source: ArtifactSource, selected: list[date] | None) -> list[date]:
    have = source.dates()
    if not selected:
        return have
    missing = [d for d in selected if d not in have]
    if missing:
        raise LoadError(f"no artifacts for {', '.join(d.isoformat() for d in missing)} in {source.location}; "
                        f"it has {', '.join(d.isoformat() for d in have) or 'none'}")
    return sorted(set(selected))


def copy_artifacts(source: ArtifactSource, target: ArtifactStore, *, dates: list[date] | None = None, replace: bool = False,
                   catalogue: bool = False, progress=None) -> Counter:
    """Copy the artifacts of ``dates`` (default: all) to ``target``, addresses and bodies unchanged apart from the re-chunking of an
    older folder tree. The scenario catalogue (no date) goes with a full copy, or with ``catalogue``. With ``replace`` the target's
    artifacts for those dates are removed first. Returns the number written per kind. Raises LoadError."""
    chosen = _dates_to_copy(source, dates)
    with_catalogue = catalogue or not dates
    counts: Counter = Counter()
    started = False
    try:
        if replace:
            for d in [*(chosen if dates else sorted({*chosen, *target.dates()})), *([GLOBAL] if with_catalogue else [])]:
                for kind in Kind:
                    target.delete_prefix(d, kind)
                if d != GLOBAL and hasattr(target, "unmark_run"):
                    target.unmark_run(d)
                started = True
        for d in [*chosen, *([GLOBAL] if with_catalogue else [])]:
            wrote = False
            for batch in _batches(source.items(d)):
                target.put_many(batch)
                started = wrote = True
                counts.update(str(a.kind) for a in batch)
            if wrote and d != GLOBAL and hasattr(target, "mark_run"):
                target.mark_run(d)  # last: a date is listed only once all of its artifacts are in
            if progress and wrote:
                progress(d)
    except LoadError:
        raise
    except Exception as e:
        hint = "; the target may hold part of the load: run the same command again to complete it" if started else ""
        raise LoadError(f"{type(e).__name__}: {e}{hint}") from e
    return counts
