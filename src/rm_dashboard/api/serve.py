"""``rm-dashboard-serve``: run the API with uvicorn."""

import argparse
import os
import sys

import uvicorn

from ..settings import Settings
from ..store import open_store
from .app import create_app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rm-dashboard-serve", description=__doc__)
    parser.add_argument(
        "--db", default=os.environ.get("RM_DASHBOARD_DB"),
        help="seeded SQLite database (default: $RM_DASHBOARD_DB)",
    )
    parser.add_argument(
        "--data-source", default=None,
        help="where the source data is read from: sqlite:<file> or firestore:<project> (default: $RM_DATA_SOURCE, else --db)",
    )
    parser.add_argument(
        "--artifact-store", default=None,
        help="where the runs were saved: sqlite:<file or folder> or firestore:<project> (default: $RM_ARTIFACT_STORE or reports/artifacts.db)",
    )
    parser.add_argument(
        "--reports", default=None,
        help="folder holding artifacts.db (older form of --artifact-store; $RM_DASHBOARD_REPORTS)",
    )
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"), help="bind address (default: $HOST, else 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)), help="port (default: $PORT, which Cloud Run sets, else 8000)")
    args = parser.parse_args(argv)
    data_source = args.data_source or os.environ.get("RM_DATA_SOURCE") or args.db
    if not data_source:
        parser.error("no database given: pass --db or set RM_DASHBOARD_DB (or --data-source / RM_DATA_SOURCE)")
    spec = args.artifact_store or args.reports or os.environ.get("RM_ARTIFACT_STORE") or os.environ.get("RM_DASHBOARD_REPORTS") \
        or Settings().artifact_store
    try:
        app = create_app(data_source, open_store(spec))
    except (FileNotFoundError, ValueError, ImportError) as exc:
        sys.exit(f"error: {exc}")
    uvicorn.run(app, host=args.host, port=args.port)
