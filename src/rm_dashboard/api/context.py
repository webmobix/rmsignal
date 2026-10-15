"""What the read endpoints share: the point-in-time repository and the persisted run folders."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rm_dashboard.data.datasource import SqliteDataSource
from rm_dashboard.outlook.store import OutlookStore
from rm_dashboard.overview.source import FolderOverviewSource
from rm_dashboard.pit import PolarsPitRepository
from rm_dashboard.reportsource import FolderReportSource


class AsOfIndex:
    """Dates for which a run folder exists under the reports folder. Never reads the clock."""

    def __init__(self, reports_dir: Path | None):
        self.reports_dir = reports_dir

    def dates(self) -> list[date]:
        if self.reports_dir is None or not self.reports_dir.is_dir():
            return []
        out = []
        for p in self.reports_dir.iterdir():
            if p.is_dir():
                try:
                    out.append(date.fromisoformat(p.name))
                except ValueError:
                    continue
        return sorted(out)

    def latest(self) -> date | None:
        ds = self.dates()
        return ds[-1] if ds else None


@dataclass
class ReadContext:
    repo: PolarsPitRepository
    reports_dir: Path | None
    asof_index: AsOfIndex
    reports: FolderReportSource
    overviews: FolderOverviewSource
    outlooks: OutlookStore

    @classmethod
    def build(cls, db_path: Path, reports_dir: Path | None) -> "ReadContext":
        with SqliteDataSource(db_path) as ds:
            repo = PolarsPitRepository(ds)  # frames are loaded into memory, the connection can close
        base = reports_dir if reports_dir is not None else Path("__no_reports__")
        return cls(repo, reports_dir, AsOfIndex(reports_dir), FolderReportSource(base),
                   FolderOverviewSource(base), OutlookStore(base))
