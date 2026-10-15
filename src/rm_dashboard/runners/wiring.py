"""Builds the object graph for a run: data source, repository, registry with the mock KYC peer."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from rm_dashboard.a2a import PEER_NAME, PeerClient, create_mock_kyc_app
from rm_dashboard.data.datasource import SqliteDataSource
from rm_dashboard.pit import PolarsPitRepository
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ToolContext, ToolRegistry


@contextmanager
def open_registry(settings: Settings, *, with_peer: bool = True, reports_dir: Path | str | None = None) -> Iterator[ToolRegistry]:
    """A tool registry over the seeded database. The KYC peer is the in-process mock unless disabled."""
    if not settings.db_path:
        raise ValueError("no database given: pass --db or set RM_DASHBOARD_DB")
    peers = {}
    if with_peer:
        app, _ = create_mock_kyc_app()
        peers["kyc"] = PeerClient(PEER_NAME, "http://kyc-peer", asgi_app=app)
    with SqliteDataSource(Path(settings.db_path)) as ds:
        yield ToolRegistry(ToolContext(PolarsPitRepository(ds), settings, peers=peers,
                                       reports_dir=Path(reports_dir) if reports_dir else None))
