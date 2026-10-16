"""RM overview over persisted client actions; command line: ``rm-dashboard-overview --as-of DATE``."""

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from rm_dashboard.agents import build_model
from rm_dashboard.agents.analyst import ModelFactory
from rm_dashboard.domain import Gap
from rm_dashboard.overview import Overview
from rm_dashboard.overview.source import FolderOverviewSource, rms_at
from rm_dashboard.overview.summary import ROLE, create_overview
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyEngine
from rm_dashboard.llmlog import llm_logging
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ToolRegistry

from .wiring import open_registry

SUBDIR = "overview"


@dataclass
class OverviewResult:
    as_of: date
    out_dir: Path
    overviews: dict[str, Overview]
    summary: dict


def run_overview(registry: ToolRegistry, *, as_of: date, reports_dir: Path, rm_ids: list[str] | None = None,
                 models: ModelFactory | None = None, engine: PolicyEngine | None = None,
                 settings: Settings | None = None) -> OverviewResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    source = FolderOverviewSource(reports_dir)
    out_dir = source.reports.run_dir(as_of) / SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    with llm_logging("overview", out_dir) as llm:
        audit_path = out_dir / "audit.jsonl"
        audit_path.unlink(missing_ok=True)
        audit = AuditLog(audit_path)
        engine = engine or MockPolicyEngine()
        rms = rms_at(registry.ctx.repo, as_of)
        overviews: dict[str, Overview] = {}
        for rm_id, rm in rms.items():
            if rm_ids and rm_id not in rm_ids:
                continue
            try:
                ov = create_overview(registry, rm, as_of=as_of, source=source, model=models(ROLE), engine=engine, audit=audit)
            except Exception as e:  # noqa: BLE001 - belt and braces: create_overview already never raises
                ov = Overview(rm_id=rm_id, rm_name=rm.rm_name, as_of=as_of, status="partial", clients=[c.client_id for c in rm.clients],
                              gaps=[Gap(kind="agent_error", description=f"{type(e).__name__}: {e}")])
            overviews[rm_id] = ov
            (out_dir / f"{rm_id}.json").write_text(ov.model_dump_json(indent=2))
        status = Counter(o.status for o in overviews.values())
        summary = {
            "as_of": as_of.isoformat(), "model": settings.model_name, "rms": len(overviews),
            "status_counts": {s: status.get(s, 0) for s in ("complete", "partial", "insufficient_data")},
            "overviews": {rid: {"status": o.status, "actions": len(o.actions), "clients": len(o.clients), "gaps": len(o.gaps),
                                "file": f"{rid}.json"} for rid, o in overviews.items()},
            "audit_log": audit_path.name,
        }
        summary["llm"] = llm.counts()
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        return OverviewResult(as_of, out_dir, overviews, summary)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-overview",
                                description="Build the RM overview of ranked next actions from the persisted client actions of a date.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--rm", help="comma-separated RM ids (default: all RMs)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    p.add_argument("--reports-dir", default="reports", help="folder holding <as-of>/ output of the earlier stages (default: reports)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.from_env()
    settings = replace(settings, **({"db_path": args.db} if args.db else {}))
    if not settings.db_path:
        print("error: no database given: pass --db rm.db or set RM_DASHBOARD_DB", file=sys.stderr)
        return 2
    if not Path(settings.db_path).is_file():
        print(f"error: database not found: {settings.db_path} (create it with `rm-dashboard-seed --db {settings.db_path}`)", file=sys.stderr)
        return 2
    ids = [r.strip() for r in args.rm.split(",") if r.strip()] if args.rm else None
    with open_registry(settings, with_peer=False) as registry:
        result = run_overview(registry, as_of=args.as_of, reports_dir=Path(args.reports_dir), rm_ids=ids, settings=settings)
    for rid, o in result.overviews.items():
        print(f"{rid}: {o.status} ({len(o.actions)} actions across {len(o.clients)} clients, {len(o.gaps)} gaps)")
    c = result.summary["status_counts"]
    print(f"{result.summary['rms']} overviews written to {result.out_dir} "
          f"(complete {c['complete']}, partial {c['partial']}, insufficient_data {c['insufficient_data']}); model: {settings.model_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
