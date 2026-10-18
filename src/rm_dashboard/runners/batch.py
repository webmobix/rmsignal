"""Batch runner: one analysis per client at one ``as_of``, persisted as JSON with a run summary."""

import dataclasses
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rm_dashboard.agents import RunScope, analyse, build_model
from rm_dashboard.agents.analyst import ModelFactory
from rm_dashboard.agents.scope import register_people
from rm_dashboard.domain import Gap, Report
from rm_dashboard.policy import MockPolicyEngine, PolicyEngine, RunContext
from rm_dashboard.llmlog import llm_logging
from rm_dashboard.settings import Settings
from rm_dashboard.store import ArtifactStore, Kind, as_store, check_writable, log_dir
from rm_dashboard.store.evidence import REPORT, put_evidence
from rm_dashboard.store.summary import put_summary
from rm_dashboard.tools import ToolRegistry

from .stage import open_audit

ROLE = "relationship_analyst"
STAGE = "analyse"


@dataclass
class BatchResult:
    as_of: date
    out_dir: Path
    """The local folder of the run log (``run.log``)."""
    reports: dict[str, Report]
    summary: dict
    store: ArtifactStore | None = None


def run_batch(registry: ToolRegistry, *, as_of: date, store: ArtifactStore | str | Path, client_ids: list[str] | None = None,
              models: ModelFactory | None = None, engine: PolicyEngine | None = None,
              settings: Settings | None = None, progress: Callable[[str, Report], None] | None = None) -> BatchResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    store = as_store(store)
    check_writable(store)
    if registry.ctx.artifacts is None:  # the outlooks live beside the reports
        registry = ToolRegistry(dataclasses.replace(registry.ctx, artifacts=store), registry.specs.values())
    repo = registry.ctx.repo
    ids = client_ids or repo.clients(as_of=as_of).frame["client_id"].to_list()
    run_dir = log_dir(store, as_of, STAGE)
    with llm_logging("analyse", run_dir) as llm:
        audit = open_audit(store, as_of, STAGE)
        engine = engine or MockPolicyEngine()

        def one(cid: str) -> tuple[str, Report, RunScope]:
            run = RunContext(cid, as_of, engine=engine, audit=audit)
            register_people(run, repo, as_of)
            scope = RunScope(run=run, registry=registry)
            try:
                report = analyse(ROLE, cid, scope, models)
            except Exception as e:  # noqa: BLE001 - belt and braces: analyse already never raises
                report = Report(subject=cid, as_of=as_of, status="partial", agent=ROLE,
                                gaps=[Gap(kind="agent_error", description=f"{type(e).__name__}: {e}")])
            return cid, report, scope

        reports: dict[str, Report] = {}
        with ThreadPoolExecutor(max_workers=max(1, settings.max_concurrency)) as pool:
            for cid, report, scope in pool.map(one, ids):
                reports[cid] = report
                put_evidence(store, as_of, REPORT, cid, list(scope.store.results.values()))  # evidence first, the report last
                store.put(as_of, Kind.REPORT, cid, report.model_dump_json(indent=2))
                if progress:
                    progress(cid, report)

        counts = Counter(r.status for r in reports.values())
        summary = {
            "as_of": as_of.isoformat(), "model": settings.model_name, "clients": len(reports),
            "status_counts": {s: counts.get(s, 0) for s in ("complete", "partial", "insufficient_data")},
            "reports": {cid: {"status": r.status, "findings": len(r.findings), "gaps": len(r.gaps),
                              "key": cid} for cid, r in reports.items()},
            "audit_log": f"audit/{STAGE}",
        }
        summary["llm"] = llm.counts()
        put_summary(store, as_of, STAGE, summary)
        return BatchResult(as_of, run_dir, reports, summary, store)
