"""Client actions over persisted batch output; command line: ``rm-dashboard-actions --as-of DATE``."""

import argparse
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
from rm_dashboard.policy import MockPolicyEngine, PolicyEngine
from rm_dashboard.reportsource import StoreReportSource
from rm_dashboard.llmlog import llm_logging
from rm_dashboard.settings import Settings
from rm_dashboard.store import ArtifactStore, Kind, check_writable, log_dir
from rm_dashboard.store.summary import put_summary
from rm_dashboard.tools import ToolRegistry

from .stage import add_store_args, data_source_problem, open_audit, store_from_args
from .wiring import open_registry

STAGE = "actions"


@dataclass
class ActionsResult:
    as_of: date
    out_dir: Path
    results: dict[str, ClientActions]
    summary: dict
    store: ArtifactStore | None = None
    """Where the artifacts were saved; ``out_dir`` is the local folder of the run log."""


def run_actions(registry: ToolRegistry, *, as_of: date, store: ArtifactStore | str | Path, client_ids: list[str] | None = None,
                models: ModelFactory | None = None, engine: PolicyEngine | None = None, settings: Settings | None = None,
                progress: Callable[[str, ClientActions], None] | None = None) -> ActionsResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    ids = client_ids or registry.ctx.repo.clients(as_of=as_of).frame["client_id"].to_list()
    source = StoreReportSource(store)
    store = source.store
    check_writable(store)
    out_dir = log_dir(store, as_of, STAGE)
    with llm_logging("actions", out_dir) as llm:
        audit = open_audit(store, as_of, STAGE)
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
                store.put(as_of, Kind.ACTIONS, cid, res.model_dump_json(indent=2))
                if progress:
                    progress(cid, res)

        status = Counter(r.status for r in results.values())
        importance = Counter(a.importance for r in results.values() for a in r.actions)
        summary = {
            "as_of": as_of.isoformat(), "model": settings.model_name, "clients": len(results),
            "status_counts": {s: status.get(s, 0) for s in ("complete", "partial", "insufficient_data")},
            "importance_counts": {i: importance.get(i, 0) for i in ("critical", "high", "medium", "low")},
            "clients_detail": {cid: {"status": r.status, "actions": len(r.actions), "not_actioned": len(r.not_actioned),
                                     "gaps": len(r.gaps), "key": cid} for cid, r in results.items()},
            "audit_log": f"audit/{STAGE}",
        }
        summary["llm"] = llm.counts()
        put_summary(store, as_of, STAGE, summary)
        return ActionsResult(as_of, out_dir, results, summary, store)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-actions",
                                description="Derive next actions per client from the persisted reports (and note reconciliation) of a date.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--clients", help="comma-separated client ids (default: all clients)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    add_store_args(p)
    p.add_argument("--concurrency", type=int, help="clients processed in parallel (default: RM_MAX_CONCURRENCY or 4)")
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
    with open_registry(settings, with_peer=False) as registry:
        result = run_actions(registry, as_of=args.as_of, store=store, client_ids=ids, settings=settings,
                             progress=lambda cid, r: print(f"{cid}: {r.status} ({len(r.actions)} actions, {len(r.gaps)} gaps)"))
    c, i = result.summary["status_counts"], result.summary["importance_counts"]
    print(f"{result.summary['clients']} client action files written to {result.store.location} "
          f"(complete {c['complete']}, partial {c['partial']}, insufficient_data {c['insufficient_data']}; "
          f"critical {i['critical']}, high {i['high']}, medium {i['medium']}, low {i['low']}); model: {settings.model_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
