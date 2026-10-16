"""Client actions over persisted batch output; command line: ``rm-dashboard-actions --as-of DATE``."""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from rm_dashboard.actions import ClientActions
from rm_dashboard.actions.agent import ROLE, derive_actions
from rm_dashboard.agents import build_model
from rm_dashboard.agents.analyst import ModelFactory
from rm_dashboard.domain import Gap
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyEngine
from rm_dashboard.reportsource import FolderReportSource
from rm_dashboard.llmlog import llm_logging
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ToolRegistry

from .wiring import open_registry

SUBDIR = "actions"


@dataclass
class ActionsResult:
    as_of: date
    out_dir: Path
    results: dict[str, ClientActions]
    summary: dict


def run_actions(registry: ToolRegistry, *, as_of: date, reports_dir: Path, client_ids: list[str] | None = None,
                models: ModelFactory | None = None, engine: PolicyEngine | None = None, settings: Settings | None = None,
                progress: Callable[[str, ClientActions], None] | None = None) -> ActionsResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    ids = client_ids or registry.ctx.repo.clients(as_of=as_of).frame["client_id"].to_list()
    source = FolderReportSource(reports_dir)
    out_dir = source.run_dir(as_of) / SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    with llm_logging("actions", out_dir) as llm:
        audit_path = out_dir / "audit.jsonl"
        audit_path.unlink(missing_ok=True)
        audit = AuditLog(audit_path)
        engine = engine or MockPolicyEngine()

        def one(cid: str) -> tuple[str, ClientActions]:
            try:
                return cid, derive_actions(registry, cid, as_of=as_of, source=source, model=models(ROLE), engine=engine, audit=audit)
            except Exception as e:  # noqa: BLE001 - belt and braces: derive_actions already never raises
                return cid, ClientActions(client_id=cid, as_of=as_of, status="partial",
                                          gaps=[Gap(kind="agent_error", description=f"{type(e).__name__}: {e}")])

        results: dict[str, ClientActions] = {}
        with ThreadPoolExecutor(max_workers=max(1, settings.max_concurrency)) as pool:
            for cid, res in pool.map(one, ids):
                results[cid] = res
                (out_dir / f"{cid}.json").write_text(res.model_dump_json(indent=2))
                if progress:
                    progress(cid, res)

        status = Counter(r.status for r in results.values())
        importance = Counter(a.importance for r in results.values() for a in r.actions)
        summary = {
            "as_of": as_of.isoformat(), "model": settings.model_name, "clients": len(results),
            "status_counts": {s: status.get(s, 0) for s in ("complete", "partial", "insufficient_data")},
            "importance_counts": {i: importance.get(i, 0) for i in ("critical", "high", "medium", "low")},
            "clients_detail": {cid: {"status": r.status, "actions": len(r.actions), "not_actioned": len(r.not_actioned),
                                     "gaps": len(r.gaps), "file": f"{cid}.json"} for cid, r in results.items()},
            "audit_log": audit_path.name,
        }
        summary["llm"] = llm.counts()
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        return ActionsResult(as_of, out_dir, results, summary)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-actions",
                                description="Derive next actions per client from the persisted reports (and note reconciliation) of a date.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--clients", help="comma-separated client ids (default: all clients)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    p.add_argument("--reports-dir", default="reports", help="folder holding <as-of>/ batch output (default: reports)")
    p.add_argument("--concurrency", type=int, help="clients processed in parallel (default: RM_MAX_CONCURRENCY or 4)")
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
    with open_registry(settings, with_peer=False) as registry:
        result = run_actions(registry, as_of=args.as_of, reports_dir=Path(args.reports_dir), client_ids=ids, settings=settings,
                             progress=lambda cid, r: print(f"{cid}: {r.status} ({len(r.actions)} actions, {len(r.gaps)} gaps)"))
    c, i = result.summary["status_counts"], result.summary["importance_counts"]
    print(f"{result.summary['clients']} client action files written to {result.out_dir} "
          f"(complete {c['complete']}, partial {c['partial']}, insufficient_data {c['insufficient_data']}; "
          f"critical {i['critical']}, high {i['high']}, medium {i['medium']}, low {i['low']}); model: {settings.model_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
