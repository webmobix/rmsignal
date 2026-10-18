"""Command line: ``rm-dashboard-analyse --as-of DATE [--clients CL-0001,CL-0002]``."""

import argparse
import sys
from dataclasses import replace
from datetime import date

from rm_dashboard.settings import Settings

from .batch import run_batch
from .stage import add_store_args, data_source_problem, store_from_args
from .wiring import open_registry


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-analyse", description="Analyse clients as of a date and write one JSON report per client.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--clients", help="comma-separated client ids (default: all clients)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    add_store_args(p, legacy="--out")
    p.add_argument("--concurrency", type=int, help="clients analysed in parallel (default: RM_MAX_CONCURRENCY or 4)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.from_env()
    overrides = {k: v for k, v in (("db_path", args.db), ("max_concurrency", args.concurrency)) if v}
    settings = replace(settings, **overrides)
    if (problem := data_source_problem(settings)) is not None:
        print(f"error: {problem}", file=sys.stderr)
        return 2

    ids = [c.strip() for c in args.clients.split(",") if c.strip()] if args.clients else None
    try:
        store = store_from_args(args, settings)
    except (ValueError, ImportError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    with open_registry(settings) as registry:
        result = run_batch(registry, as_of=args.as_of, store=store, client_ids=ids, settings=settings,
                           progress=lambda cid, r: print(f"{cid}: {r.status} ({len(r.findings)} findings, {len(r.gaps)} gaps)"))
    c = result.summary["status_counts"]
    print(f"{result.summary['clients']} reports written to {result.store.location} "
          f"(complete {c['complete']}, partial {c['partial']}, insufficient_data {c['insufficient_data']}); model: {settings.model_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
