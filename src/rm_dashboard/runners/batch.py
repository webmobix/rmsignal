"""Batch runner: one analysis per client at one ``as_of``, persisted as JSON with a run summary."""

import json
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
from rm_dashboard.policy import AuditLog, MockPolicyEngine, PolicyEngine, RunContext
from rm_dashboard.settings import Settings
from rm_dashboard.tools import ToolRegistry

ROLE = "relationship_analyst"


@dataclass
class BatchResult:
    as_of: date
    out_dir: Path
    reports: dict[str, Report]
    summary: dict


def run_batch(registry: ToolRegistry, *, as_of: date, out_dir: Path, client_ids: list[str] | None = None,
              models: ModelFactory | None = None, engine: PolicyEngine | None = None,
              settings: Settings | None = None, progress: Callable[[str, Report], None] | None = None) -> BatchResult:
    settings = settings or registry.ctx.settings
    models = models or (lambda role: build_model(settings, role=role))
    repo = registry.ctx.repo
    ids = client_ids or repo.clients(as_of=as_of).frame["client_id"].to_list()
    run_dir = Path(out_dir) / as_of.isoformat()
    (run_dir / "evidence").mkdir(parents=True, exist_ok=True)
    audit_path = run_dir / "audit.jsonl"
    audit_path.unlink(missing_ok=True)
    audit = AuditLog(audit_path)
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
            (run_dir / f"{cid}.json").write_text(report.model_dump_json(indent=2))
            evidence = [e.model_dump(mode="json") for e in scope.store.results.values()]
            (run_dir / "evidence" / f"{cid}.json").write_text(json.dumps(evidence, default=str))
            if progress:
                progress(cid, report)

    counts = Counter(r.status for r in reports.values())
    summary = {
        "as_of": as_of.isoformat(), "model": settings.model_name, "clients": len(reports),
        "status_counts": {s: counts.get(s, 0) for s in ("complete", "partial", "insufficient_data")},
        "reports": {cid: {"status": r.status, "findings": len(r.findings), "gaps": len(r.gaps),
                          "file": f"{cid}.json"} for cid, r in reports.items()},
        "audit_log": audit_path.name,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return BatchResult(as_of, run_dir, reports, summary)
