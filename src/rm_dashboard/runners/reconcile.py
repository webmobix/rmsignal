"""Note reconciliation over persisted batch output; command line: ``rm-dashboard-reconcile --as-of DATE``."""

import argparse
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
from rm_dashboard.policy import MockPolicyEngine, PolicyEngine
from rm_dashboard.reconciliation import Reconciliation, reconcile
from rm_dashboard.reportsource import StoreReportSource
from rm_dashboard.llmlog import llm_logging
from rm_dashboard.settings import Settings
from rm_dashboard.store import ArtifactStore, Kind, check_writable, log_dir
from rm_dashboard.store.summary import put_summary
from rm_dashboard.tools import ToolRegistry

from .stage import add_store_args, data_source_problem, open_audit, store_from_args
from .wiring import open_registry

ROLE = "note_reconciler"
STAGE = "reconcile"


@dataclass
class ReconcileResult:
    as_of: date
    out_dir: Path
    reconciliations: dict[str, Reconciliation]
    summary: dict
    store: ArtifactStore | None = None
    """Where the artifacts were saved; ``out_dir`` is the local folder of the run log."""


def run_reconcile(registry: ToolRegistry, *, as_of: date, store: ArtifactStore | str | Path, client_ids: list[str] | None = None,
                  models: ModelFactory | None = None, engine: PolicyEngine | None = None,
                  settings: Settings | None = None,
                  progress: Callable[[str, Reconciliation], None] | None = None) -> ReconcileResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    ids = client_ids or registry.ctx.repo.clients(as_of=as_of).frame["client_id"].to_list()
    source = StoreReportSource(store)
    store = source.store
    check_writable(store)
    out_dir = log_dir(store, as_of, STAGE)
    with llm_logging("reconcile", out_dir) as llm:
        audit = open_audit(store, as_of, STAGE)
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
                store.put(as_of, Kind.RECONCILIATION, cid, rec.model_dump_json(indent=2))
                if progress:
                    progress(cid, rec)

        status = Counter(r.status for r in recs.values())
        verdicts = Counter(x.verdict for r in recs.values() for x in r.results)
        summary = {
            "as_of": as_of.isoformat(), "model": settings.model_name, "clients": len(recs),
            "status_counts": {s: status.get(s, 0) for s in ("complete", "partial", "insufficient_data")},
            "verdict_counts": {v: verdicts.get(v, 0) for v in ("consistent", "contradicted", "unverifiable")},
            "reconciliations": {cid: {"status": r.status, "notes": len(r.results), "gaps": len(r.gaps), "key": cid}
                                for cid, r in recs.items()},
            "audit_log": f"audit/{STAGE}",
        }
        summary["llm"] = llm.counts()
        put_summary(store, as_of, STAGE, summary)
        return ReconcileResult(as_of, out_dir, recs, summary, store)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rm-dashboard-reconcile",
                                description="Reconcile RM notes with the persisted client reports of a date.")
    p.add_argument("--as-of", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="analysis date (required)")
    p.add_argument("--clients", help="comma-separated client ids (default: all clients)")
    p.add_argument("--db", help="seeded SQLite database (or set RM_DASHBOARD_DB)")
    add_store_args(p)
    p.add_argument("--concurrency", type=int, help="clients reconciled in parallel (default: RM_MAX_CONCURRENCY or 4)")
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
        result = run_reconcile(registry, as_of=args.as_of, store=store, client_ids=ids, settings=settings,
                               progress=lambda cid, r: print(f"{cid}: {r.status} ({len(r.results)} notes, {len(r.gaps)} gaps)"))
    c, v = result.summary["status_counts"], result.summary["verdict_counts"]
    print(f"{result.summary['clients']} reconciliations written to {result.store.location} "
          f"(complete {c['complete']}, partial {c['partial']}, insufficient_data {c['insufficient_data']}; "
          f"consistent {v['consistent']}, contradicted {v['contradicted']}, unverifiable {v['unverifiable']}); model: {settings.model_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
