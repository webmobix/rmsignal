"""Where scenario results live: ``<reports>/<as_of>/scenarios/<scenario_id>/``. Other dates and scenarios are never touched.

    vector.json                      the shock vector              evidence/vector.json
    impacts/<portfolio_id>.json      portfolio impacts             evidence/impacts/<portfolio_id>.json
    clients/<client_id>.json         client roll-ups
    rollup.json                      the RM book roll-up
    ../summary.json, ../audit.jsonl  the run's summary and audit trail (one per date)
"""

import json
import os
import tempfile
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from rm_dashboard.domain import ToolResult

from .contracts import ClientRollup, PortfolioImpact, RMRollup, ShockVector

SUBDIR = "scenarios"


def _write(path: Path, text: str) -> None:
    """Write whole or not at all: an interrupted run never leaves half a result for the next run to trust."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class ScenarioStore:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    # ---- paths --------------------------------------------------------------------------
    def run_dir(self, as_of: date) -> Path:
        return self.base_dir / as_of.isoformat() / SUBDIR

    def scenario_dir(self, as_of: date, scenario_id: str) -> Path:
        return self.run_dir(as_of) / scenario_id

    def vector_path(self, as_of: date, scenario_id: str) -> Path:
        return self.scenario_dir(as_of, scenario_id) / "vector.json"

    def vector_evidence_path(self, as_of: date, scenario_id: str) -> Path:
        return self.scenario_dir(as_of, scenario_id) / "evidence" / "vector.json"

    def impact_path(self, as_of: date, scenario_id: str, portfolio_id: str) -> Path:
        return self.scenario_dir(as_of, scenario_id) / "impacts" / f"{portfolio_id}.json"

    def impact_evidence_path(self, as_of: date, scenario_id: str, portfolio_id: str) -> Path:
        return self.scenario_dir(as_of, scenario_id) / "evidence" / "impacts" / f"{portfolio_id}.json"

    def client_path(self, as_of: date, scenario_id: str, client_id: str) -> Path:
        return self.scenario_dir(as_of, scenario_id) / "clients" / f"{client_id}.json"

    def rollup_path(self, as_of: date, scenario_id: str) -> Path:
        return self.scenario_dir(as_of, scenario_id) / "rollup.json"

    # ---- reading ------------------------------------------------------------------------
    @staticmethod
    def _load(path: Path, model: type[BaseModel]):
        if not path.is_file():
            return None
        try:
            return model.model_validate_json(path.read_text())
        except ValueError:  # a result that no longer parses is a result that does not exist
            return None

    @staticmethod
    def _evidence(path: Path) -> list[ToolResult]:
        return [ToolResult.model_validate(x) for x in json.loads(path.read_text())] if path.is_file() else []

    def load_vector(self, as_of: date, scenario_id: str) -> ShockVector | None:
        return self._load(self.vector_path(as_of, scenario_id), ShockVector)

    def load_vector_evidence(self, as_of: date, scenario_id: str) -> list[ToolResult]:
        return self._evidence(self.vector_evidence_path(as_of, scenario_id))

    def load_impact(self, as_of: date, scenario_id: str, portfolio_id: str) -> PortfolioImpact | None:
        return self._load(self.impact_path(as_of, scenario_id, portfolio_id), PortfolioImpact)

    def load_impact_evidence(self, as_of: date, scenario_id: str, portfolio_id: str) -> list[ToolResult]:
        return self._evidence(self.impact_evidence_path(as_of, scenario_id, portfolio_id))

    def load_client(self, as_of: date, scenario_id: str, client_id: str) -> ClientRollup | None:
        return self._load(self.client_path(as_of, scenario_id, client_id), ClientRollup)

    def load_rollup(self, as_of: date, scenario_id: str) -> RMRollup | None:
        return self._load(self.rollup_path(as_of, scenario_id), RMRollup)

    def scenario_ids(self, as_of: date) -> list[str]:
        d = self.run_dir(as_of)
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []

    # ---- writing ------------------------------------------------------------------------
    def save_vector(self, vector: ShockVector, evidence: list[ToolResult]) -> None:
        _write(self.vector_evidence_path(vector.as_of, vector.scenario_id), json.dumps([e.model_dump(mode="json") for e in evidence], default=str))
        _write(self.vector_path(vector.as_of, vector.scenario_id), vector.model_dump_json(indent=2))

    def save_impact(self, impact: PortfolioImpact, evidence: list[ToolResult] | None = None) -> None:
        if evidence:
            _write(self.impact_evidence_path(impact.as_of, impact.scenario_id, impact.portfolio_id),
                   json.dumps([e.model_dump(mode="json") for e in evidence], default=str))
        _write(self.impact_path(impact.as_of, impact.scenario_id, impact.portfolio_id), impact.model_dump_json(indent=2))

    def save_client(self, rollup: ClientRollup) -> None:
        _write(self.client_path(rollup.as_of, rollup.scenario_id, rollup.client_id), rollup.model_dump_json(indent=2))

    def save_rollup(self, rollup: RMRollup) -> None:
        _write(self.rollup_path(rollup.as_of, rollup.scenario_id), rollup.model_dump_json(indent=2))
