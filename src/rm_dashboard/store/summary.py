"""Run summaries: one JSON document per stage and date, kind ``run-summary``, key = the stage name."""

import json
from datetime import date

from .base import ArtifactStore, Kind, read_json


def put_summary(store: ArtifactStore, as_of: date, stage: str, summary: dict) -> None:
    store.put(as_of, Kind.RUN_SUMMARY, stage, json.dumps(summary, indent=2))


def get_summary(store: ArtifactStore, as_of: date, stage: str) -> dict | None:
    got = read_json(store, as_of, Kind.RUN_SUMMARY, stage)
    return got if isinstance(got, dict) else None
