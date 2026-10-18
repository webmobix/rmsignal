"""What the read endpoints share: the point-in-time repository and the artifact store."""

from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rm_dashboard.data.contract import DataSource
from rm_dashboard.data.factory import open_data_source
from rm_dashboard.outlook.store import OutlookStore
from rm_dashboard.overview.source import StoreOverviewSource
from rm_dashboard.pit import PolarsPitRepository
from rm_dashboard.reportsource import StoreReportSource
from rm_dashboard.store import ArtifactStore, SqliteArtifactStore

NO_ARTIFACTS = SqliteArtifactStore(Path("__no_artifacts__") / "artifacts.db")
"""Stands in when no store is configured: it never gets created, so every read finds nothing."""


class AsOfIndex:
    """Dates for which the store holds an artifact. Never reads the clock."""

    def __init__(self, store: ArtifactStore | None):
        self.store = store

    def dates(self) -> list[date]:
        return self.store.dates() if self.store is not None else []

    def latest(self) -> date | None:
        ds = self.dates()
        return ds[-1] if ds else None


@dataclass
class ReadContext:
    repo: PolarsPitRepository
    store: ArtifactStore | None
    asof_index: AsOfIndex
    reports: StoreReportSource
    overviews: StoreOverviewSource
    outlooks: OutlookStore

    @classmethod
    def build(cls, source: DataSource | str | Path, store: ArtifactStore | None) -> "ReadContext":
        """``source`` is a datasource or the spec/path of one; the frames are loaded into memory, so it is closed again."""
        with closing(open_data_source(source) if isinstance(source, (str, Path)) else source) as ds:
            repo = PolarsPitRepository(ds)
        base = store if store is not None else NO_ARTIFACTS
        return cls(repo, store, AsOfIndex(store), StoreReportSource(base), StoreOverviewSource(base), OutlookStore(base))
