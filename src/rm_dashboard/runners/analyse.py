"""Command line: ``rm-dashboard-analyse --as-of DATE [--clients CL-0001,CL-0002]``."""

import argparse
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

from rm_dashboard.settings import Settings

from .batch import run_batch
from .wiring import open_registry


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-analyse", description="Analyse clients as of a date and write one JSON report per client.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--clients", help="comma-separated client ids (default: all clients)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    p.add_argument("--out", default="reports", help="output directory (default: reports)")
    p.add_argument("--concurrency", type=int, help="clients analysed in parallel (default: RM_MAX_CONCURRENCY or 4)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.from_env()
    overrides = {k: v for k, v in (("db_path", args.db), ("max_concurrency", args.concurrency)) if v}
    settings = replace(settings, **overrides)
    if not settings.db_path:
        print("error: no database given: pass --db rm.db or set RM_DASHBOARD_DB", file=sys.stderr)
        return 2
    if not Path(settings.db_path).is_file():
        print(f"error: database not found: {settings.db_path} (create it with `rm-dashboard-seed --db {settings.db_path}`)", file=sys.stderr)
        return 2
    ids = [c.strip() for c in args.clients.split(",") if c.strip()] if args.clients else None
    with open_registry(settings) as registry:
        result = run_batch(registry, as_of=args.as_of, out_dir=Path(args.out), client_ids=ids, settings=settings,
                           progress=lambda cid, r: print(f"{cid}: {r.status} ({len(r.findings)} findings, {len(r.gaps)} gaps)"))
    c = result.summary["status_counts"]
    print(f"{result.summary['clients']} reports written to {result.out_dir} "
          f"(complete {c['complete']}, partial {c['partial']}, insufficient_data {c['insufficient_data']}); model: {settings.model_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
