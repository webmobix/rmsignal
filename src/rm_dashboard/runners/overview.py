"""RM overview over persisted client actions; command line: ``rm-dashboard-overview --as-of DATE``."""

import argparse
import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from rm_dashboard.agents import build_model
from rm_dashboard.agents.analyst import ModelFactory
from rm_dashboard.domain import Gap
from rm_dashboard.overview import Overview
from rm_dashboard.overview.source import StoreOverviewSource, rms_at
from rm_dashboard.overview.summary import ROLE, create_overview
from rm_dashboard.policy import MockPolicyEngine, PolicyEngine
from rm_dashboard.llmlog import llm_logging
from rm_dashboard.settings import Settings
from rm_dashboard.store import ArtifactStore, Kind, check_writable, log_dir
from rm_dashboard.store.summary import put_summary
from rm_dashboard.tools import ToolRegistry

from .stage import add_store_args, data_source_problem, open_audit, store_from_args
from .wiring import open_registry

STAGE = "overview"


@dataclass
class OverviewResult:
    as_of: date
    out_dir: Path
    overviews: dict[str, Overview]
    summary: dict
    store: ArtifactStore | None = None
    """Where the artifacts were saved; ``out_dir`` is the local folder of the run log."""


def run_overview(registry: ToolRegistry, *, as_of: date, store: ArtifactStore | str | Path, rm_ids: list[str] | None = None,
                 models: ModelFactory | None = None, engine: PolicyEngine | None = None,
                 settings: Settings | None = None) -> OverviewResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    source = StoreOverviewSource(store)
    store = source.store
    check_writable(store)
    out_dir = log_dir(store, as_of, STAGE)
    with llm_logging("overview", out_dir) as llm:
        audit = open_audit(store, as_of, STAGE)
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
            store.put(as_of, Kind.OVERVIEW, rm_id, ov.model_dump_json(indent=2))
        status = Counter(o.status for o in overviews.values())
        summary = {
            "as_of": as_of.isoformat(), "model": settings.model_name, "rms": len(overviews),
            "status_counts": {s: status.get(s, 0) for s in ("complete", "partial", "insufficient_data")},
            "overviews": {rid: {"status": o.status, "actions": len(o.actions), "clients": len(o.clients), "gaps": len(o.gaps),
                                "key": rid} for rid, o in overviews.items()},
            "audit_log": f"audit/{STAGE}",
        }
        summary["llm"] = llm.counts()
        put_summary(store, as_of, STAGE, summary)
        return OverviewResult(as_of, out_dir, overviews, summary, store)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-overview",
                                description="Build the RM overview of ranked next actions from the persisted client actions of a date.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--rm", help="comma-separated RM ids (default: all RMs)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    add_store_args(p)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.from_env()
    settings = replace(settings, **({"db_path": args.db} if args.db else {}))
    if (problem := data_source_problem(settings)) is not None:
        print(f"error: {problem}", file=sys.stderr)
        return 2
    ids = [r.strip() for r in args.rm.split(",") if r.strip()] if args.rm else None
    try:
        store = store_from_args(args, settings)
    except (ValueError, ImportError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    with open_registry(settings, with_peer=False) as registry:
        result = run_overview(registry, as_of=args.as_of, store=store, rm_ids=ids, settings=settings)
    for rid, o in result.overviews.items():
        print(f"{rid}: {o.status} ({len(o.actions)} actions across {len(o.clients)} clients, {len(o.gaps)} gaps)")
    c = result.summary["status_counts"]
    print(f"{result.summary['rms']} overviews written to {result.store.location} "
          f"(complete {c['complete']}, partial {c['partial']}, insufficient_data {c['insufficient_data']}); model: {settings.model_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
