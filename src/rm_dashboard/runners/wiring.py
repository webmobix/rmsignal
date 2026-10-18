"""Builds the object graph for a run: data source, repository, registry with the mock KYC peer."""

from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from rm_dashboard.a2a import PEER_NAME, PeerClient, create_mock_kyc_app
from rm_dashboard.data.factory import open_data_source
from rm_dashboard.pit import PolarsPitRepository
from rm_dashboard.settings import Settings
from rm_dashboard.store import ArtifactStore, as_store
from rm_dashboard.tools import ToolContext, ToolRegistry


@contextmanager
def open_registry(settings: Settings, *, with_peer: bool = True, artifacts: ArtifactStore | str | Path | None = None) -> Iterator[ToolRegistry]:
    """A tool registry over the seeded database. The KYC peer is the in-process mock unless disabled."""
    spec = settings.data_source_spec
    if spec is None:
        raise ValueError("no database given: pass --db or set RM_DASHBOARD_DB")
    peers = {}
    if with_peer:
        app, _ = create_mock_kyc_app()
        peers["kyc"] = PeerClient(PEER_NAME, "http://kyc-peer", asgi_app=app)
    with closing(open_data_source(spec)) as ds:
        yield ToolRegistry(ToolContext(PolarsPitRepository(ds), settings, peers=peers,
                                       artifacts=as_store(artifacts) if artifacts is not None else None))
