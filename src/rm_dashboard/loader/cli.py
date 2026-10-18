"""``rm-dashboard-load source|artifacts``."""

import argparse
import sys
from datetime import date

from rm_dashboard.data.dataset import DEFAULT_DATA_DIR
from .artifacts import LoadError, copy_artifacts, open_artifact_source, open_target_store
from .source import load_source


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-load", description="Load source data or generated artifacts into a backend.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("source", help="the 12 dataset files into SQLite or Firestore")
    s.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="directory with the dataset files")
    s.add_argument("--to", required=True, metavar="TARGET", help="sqlite:<file> (or a path) or firestore:<project>[/<database>]")
    s.add_argument("--replace", action="store_true", help="remove the rows this loader owns in the target first")

    a = sub.add_parser("artifacts", help="artifacts from an artifact database or a reports/ folder into SQLite or Firestore")
    a.add_argument("--from", dest="source", required=True, metavar="SOURCE",
                   help="sqlite:<file or folder>, a reports/ folder (or folder:<path>), or firestore:<project>")
    a.add_argument("--to", required=True, metavar="TARGET", help="sqlite:<file or folder> or firestore:<project>[/<database>]")
    a.add_argument("--as-of", action="append", type=date.fromisoformat, metavar="YYYY-MM-DD",
                   help="copy only this date; repeat for more (default: every date)")
    a.add_argument("--catalogue", action="store_true", help="also copy the scenario catalogue when limiting to dates")
    a.add_argument("--replace", action="store_true", help="remove the target's artifacts for the copied dates first")
    return p.parse_args(argv)


def _run_source(args: argparse.Namespace) -> int:
    counts = load_source(args.data_dir, args.to, args.replace)
    for table, n in counts.items():
        print(f"{table:<20} {n:>5} rows")
    return 0


def _run_artifacts(args: argparse.Namespace) -> int:
    source = open_artifact_source(args.source)
    target = open_target_store(args.to)
    counts = copy_artifacts(source, target, dates=args.as_of, replace=args.replace, catalogue=args.catalogue,
                            progress=lambda d: print(f"{d.isoformat()} copied", file=sys.stderr))
    if not counts:
        print(f"nothing to copy from {source.location}")
        return 0
    for kind, n in sorted(counts.items()):
        print(f"{kind:<24} {n:>6}")
    print(f"{sum(counts.values())} artifacts written to {target.location}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return _run_source(args) if args.command == "source" else _run_artifacts(args)
    except (LoadError, ValueError, ImportError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
