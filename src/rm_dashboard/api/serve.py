"""``rm-dashboard-serve``: run the API with uvicorn."""

import argparse
import os
import sys

import uvicorn

from .app import create_app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rm-dashboard-serve", description=__doc__)
    parser.add_argument(
        "--db", default=os.environ.get("RM_DASHBOARD_DB"),
        help="seeded SQLite database (default: $RM_DASHBOARD_DB)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if not args.db:
        parser.error("no database given: pass --db or set RM_DASHBOARD_DB")
    try:
        app = create_app(args.db)
    except FileNotFoundError as exc:
        sys.exit(f"error: {exc}")
    uvicorn.run(app, host=args.host, port=args.port)
