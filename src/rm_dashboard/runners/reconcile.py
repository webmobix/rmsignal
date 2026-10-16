"""Note reconciliation over persisted batch output; command line: ``rm-dashboard-reconcile --as-of DATE``."""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from rm_dashboard.agents import build_model
from rm_dashboard.agents.analyst import ModelFactory
from rm_dashboard.domain import Gap
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyEngine
from rm_dashboard.reconciliation import Reconciliation, reconcile
from rm_dashboard.reportsource import FolderReportSource
from rm_dashboard.llmlog import llm_logging
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ToolRegistry

from .wiring import open_registry

ROLE = "note_reconciler"
SUBDIR = "reconciliation"


@dataclass
class ReconcileResult:
    as_of: date
    out_dir: Path
    reconciliations: dict[str, Reconciliation]
    summary: dict


def run_reconcile(registry: ToolRegistry, *, as_of: date, reports_dir: Path, client_ids: list[str] | None = None,
                  models: ModelFactory | None = None, engine: PolicyEngine | None = None,
                  settings: Settings | None = None,
                  progress: Callable[[str, Reconciliation], None] | None = None) -> ReconcileResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    ids = client_ids or registry.ctx.repo.clients(as_of=as_of).frame["client_id"].to_list()
    source = FolderReportSource(reports_dir)
    out_dir = source.run_dir(as_of) / SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    with llm_logging("reconcile", out_dir) as llm:
        audit_path = out_dir / "audit.jsonl"
        audit_path.unlink(missing_ok=True)
        audit = AuditLog(audit_path)
        engine = engine or MockPolicyEngine()

        def one(cid: str) -> tuple[str, Reconciliation]:
            try:
                return cid, reconcile(registry, cid, as_of=as_of, source=source, model=models(ROLE), engine=engine, audit=audit)
            except Exception as e:  # noqa: BLE001 - belt and braces: reconcile already never raises
                gap = Gap(kind="agent_error", description=f"{type(e).__name__}: {e}")
                return cid, Reconciliation(client_id=cid, as_of=as_of, status="partial", gaps=[gap])

        recs: dict[str, Reconciliation] = {}
        with ThreadPoolExecutor(max_workers=max(1, settings.max_concurrency)) as pool:
            for cid, rec in pool.map(one, ids):
                recs[cid] = rec
                (out_dir / f"{cid}.json").write_text(rec.model_dump_json(indent=2))
                if progress:
                    progress(cid, rec)

        status = Counter(r.status for r in recs.values())
        verdicts = Counter(x.verdict for r in recs.values() for x in r.results)
        summary = {
            "as_of": as_of.isoformat(), "model": settings.model_name, "clients": len(recs),
            "status_counts": {s: status.get(s, 0) for s in ("complete", "partial", "insufficient_data")},
            "verdict_counts": {v: verdicts.get(v, 0) for v in ("consistent", "contradicted", "unverifiable")},
            "reconciliations": {cid: {"status": r.status, "notes": len(r.results), "gaps": len(r.gaps), "file": f"{cid}.json"}
                                for cid, r in recs.items()},
            "audit_log": audit_path.name,
        }
        summary["llm"] = llm.counts()
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        return ReconcileResult(as_of, out_dir, recs, summary)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-reconcile",
                                description="Reconcile RM notes with the persisted client reports of a date.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--clients", help="comma-separated client ids (default: all clients)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    p.add_argument("--reports-dir", default="reports", help="folder holding <as-of>/ batch output (default: reports)")
    p.add_argument("--concurrency", type=int, help="clients reconciled in parallel (default: RM_MAX_CONCURRENCY or 4)")
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
        result = run_reconcile(registry, as_of=args.as_of, reports_dir=Path(args.reports_dir), client_ids=ids, settings=settings,
                               progress=lambda cid, r: print(f"{cid}: {r.status} ({len(r.results)} notes, {len(r.gaps)} gaps)"))
    c, v = result.summary["status_counts"], result.summary["verdict_counts"]
    print(f"{result.summary['clients']} reconciliations written to {result.out_dir} "
          f"(complete {c['complete']}, partial {c['partial']}, insufficient_data {c['insufficient_data']}; "
          f"consistent {v['consistent']}, contradicted {v['contradicted']}, unverifiable {v['unverifiable']}); model: {settings.model_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
