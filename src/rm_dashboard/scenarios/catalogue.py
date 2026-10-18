"""The scenario catalogue: stored text records (one artifact, not tied to a date), seeded with the three first scenarios."""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from rm_dashboard.store import GLOBAL, ArtifactStore, Kind, as_store

from .contracts import NOT_A_PROBABILITY, ScenarioRecord

KEY = "catalogue"

SEED_SCENARIOS = (
    ScenarioRecord(
        scenario_id="gulf-de-escalation", name="Gulf de-escalation",
        premise="Shipping through the Strait of Hormuz normalises and the energy risk premium unwinds.",
        mirrors="Event log 2026-03-04: Strait of Hormuz effectively closed, read in reverse."),
    ScenarioRecord(
        scenario_id="gulf-deterioration", name="Gulf deterioration",
        premise="The naval blockade widens and energy and shipping stay under pressure.",
        mirrors="Event log 2026-08-05: United States reimposes a naval blockade; energy risk premium re-widens."),
    ScenarioRecord(
        scenario_id="rates-higher-for-longer", name="Rates higher for longer",
        premise="The Federal Reserve stays on hold and the 10-year yield rises further.",
        mirrors="Event log 2026-07-29: Federal Reserve holds again; US 10-year yield reaches 4.71%."),
)
"""Used when the catalogue store holds no record, so the product works without authoring."""


@dataclass
class Catalogue:
    scenarios: list[ScenarioRecord]
    rejected: list[str] = field(default_factory=list)
    """One message per record that could not be loaded. The others are unaffected."""

    def get(self, scenario_id: str) -> ScenarioRecord | None:
        return next((s for s in self.scenarios if s.scenario_id == scenario_id), None)


def scenario_hash(s: ScenarioRecord) -> str:
    """What the scenario says: editing the text, the mirrored event or the horizon changes it; the creation time does not."""
    body = json.dumps({"id": s.scenario_id, "premise": s.premise, "mirrors": s.mirrors, "horizon": s.horizon_months}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def _describe(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in err['loc']) or 'record'}: {err['msg']}" for err in e.errors())


class CatalogueStore:
    def __init__(self, store: ArtifactStore | str | Path):
        self.store = as_store(store)

    def _text(self) -> str | None:
        return self.store.get(GLOBAL, Kind.SCENARIO_CATALOGUE, KEY)

    def exists(self) -> bool:
        return self._text() is not None

    def load(self) -> Catalogue:
        """Every valid record; a record without a premise (or any other field problem) is reported and skipped."""
        text = self._text()
        if text is None:
            return Catalogue(list(SEED_SCENARIOS))
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            return Catalogue(list(SEED_SCENARIOS), [f"catalogue is not valid JSON ({e.msg}): seeded scenarios used"])
        items = raw.get("scenarios") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return Catalogue(list(SEED_SCENARIOS), ["catalogue has no scenarios list: seeded scenarios used"])
        good: list[ScenarioRecord] = []
        rejected: list[str] = []
        seen: set[str] = set()
        for i, item in enumerate(items):
            label = item.get("scenario_id") or item.get("name") or f"#{i + 1}" if isinstance(item, dict) else f"#{i + 1}"
            try:
                rec = ScenarioRecord.model_validate(item)
            except ValidationError as e:
                rejected.append(f"scenario {label} rejected: {_describe(e)}")
                continue
            if rec.scenario_id in seen:
                rejected.append(f"scenario {rec.scenario_id} rejected: duplicate id")
                continue
            seen.add(rec.scenario_id)
            good.append(rec)
        return Catalogue(good or list(SEED_SCENARIOS) if not items else good, rejected)

    def save(self, scenarios: list[ScenarioRecord]) -> None:
        self.store.put(GLOBAL, Kind.SCENARIO_CATALOGUE, KEY, json.dumps({"scenarios": [s.model_dump(mode="json") for s in scenarios]}, indent=2))

    def ensure_seeded(self) -> Catalogue:
        """Write the seeded scenarios when the store holds no catalogue; an existing one is never overwritten."""
        if not self.exists():
            self.save(list(SEED_SCENARIOS))
        return self.load()

    def add(self, record: ScenarioRecord) -> ScenarioRecord:
        """Add (or replace by id) a scenario. An empty store is first seeded, so adding one does not drop the three.

        The store never reads the clock (no module does): the creation time is whatever the caller put in the record."""
        existing = [s for s in self.ensure_seeded().scenarios if s.scenario_id != record.scenario_id]
        self.save([*existing, record])
        return record


__all__ = ["Catalogue", "CatalogueStore", "NOT_A_PROBABILITY", "SEED_SCENARIOS", "scenario_hash"]
