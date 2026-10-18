"""What every runner shares: choosing the artifact store and opening a stage's audit trail."""

import argparse
from datetime import date
from pathlib import Path

from rm_dashboard.data.factory import parse_spec
from rm_dashboard.policy import AuditLog
from rm_dashboard.settings import Settings
from rm_dashboard.store import ArtifactStore, check_writable, open_store
from rm_dashboard.store.audit import StoreAuditSink


def add_store_args(p: argparse.ArgumentParser, *, legacy: str = "--reports-dir") -> None:
    p.add_argument("--artifact-store", metavar="SPEC",
                   help="where artifacts are saved: sqlite:<file or folder> or firestore:<project> "
                        "(default: $RM_ARTIFACT_STORE or sqlite:reports/artifacts.db)")
    p.add_argument(legacy, dest="legacy_dir", metavar="DIR", help="folder holding artifacts.db (older form of --artifact-store)")


def store_from_args(args: argparse.Namespace, settings: Settings) -> ArtifactStore:
    """Flag, then the older folder flag, then ``RM_ARTIFACT_STORE``, then the default; Firestore is opened writable. Raises ValueError
    for an unknown backend (before anything is read or any model is called), ImportError without the client library."""
    store = open_store(args.artifact_store or args.legacy_dir or settings.artifact_store, writable=True)
    check_writable(store)
    return store


def open_audit(store: ArtifactStore, as_of: date, stage: str, *, resume: bool = False) -> AuditLog:
    """The stage's audit trail in the store. A stage that replaces its results starts the trail again; one that adds to the
    results of earlier runs (``resume``) continues the numbering, so nothing is ever overwritten."""
    sink = StoreAuditSink(store, as_of, stage, replace=not resume)
    return AuditLog(sink=sink, start_seq=sink.last_seq if resume else 0)


def data_source_problem(settings: Settings) -> str | None:
    """Why the configured source data cannot be used (a message for the command line), or ``None``."""
    spec = settings.data_source_spec
    if spec is None:
        return "no database given: pass --db rm.db or set RM_DASHBOARD_DB"
    try:
        backend, rest = parse_spec(spec)
    except ValueError as e:
        return str(e)
    if backend == "sqlite" and not Path(rest).is_file():
        return f"database not found: {rest} (create it with `rm-dashboard-seed --db {rest}`)"
    return None


__all__ = ["add_store_args", "check_writable", "data_source_problem", "open_audit", "store_from_args"]
