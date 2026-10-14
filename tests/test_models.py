import csv
import dataclasses
import json
import typing
from datetime import date

import pytest

from rm_dashboard.data import models
from rm_dashboard.data.schema import ENTITIES, columns, source_column


def _header(entity, data_dir):
    path = data_dir / entity.file
    if path.suffix == ".json":
        return list(json.loads(path.read_text(encoding="utf-8"))[0])
    with path.open(newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh))


def test_twelve_entities():
    assert len(ENTITIES) == 12


@pytest.mark.parametrize("entity", ENTITIES, ids=lambda e: e.table)
def test_fields_match_source_columns(entity, data_dir):
    sources = [source_column(f.name) for f in dataclasses.fields(entity.model)]
    assert sources == _header(entity, data_dir)


def test_hyphenated_columns_renamed():
    names = {f.name for f in dataclasses.fields(models.Portfolio)}
    assert "aum_2026_08_26" in names
    assert source_column("aum_2026_08_26") == "aum_2026-08-26"
    assert source_column("aum_usd_current") == "aum_usd_current"


def _types(model):
    return {c.name: (c.type, c.nullable) for c in columns(next(e for e in ENTITIES if e.model is model))}


def test_date_columns_are_dates():
    for name in ("client_since", "kyc_review_due"):
        assert _types(models.Client)[name] == (date, False)
    for name in ("snapshot_date", "valuation_date", "acquired_date"):
        assert _types(models.Holding)[name] == (date, False)
    assert _types(models.RMNote)["note_date"] == (date, False)
    assert _types(models.Transaction)["trade_date"] == (date, False)


def test_flag_columns_are_bool():
    assert _types(models.Client)["pep_status"] == (bool, False)
    assert _types(models.Instrument)["sustainability_excluded"] == (bool, False)
    assert _types(models.Instrument)["concentration_limit_applies"] == (bool, False)


def test_numbers_are_numeric():
    assert _types(models.Holding)["market_value_usd"] == (float, False)
    assert _types(models.Client)["risk_tolerance_score"] == (int, False)


def test_nullable_fields():
    assert _types(models.Client)["age"] == (int, True)
    t = _types(models.Transaction)
    assert all(t[n][1] for n in ("instrument_id", "instrument_name", "quantity", "price_local"))
    assert _types(models.Holding)["sector"][1]
    assert not _types(models.Client)["client_id"][1]


def test_no_string_typed_dates_or_numbers():
    for entity in ENTITIES:
        for c in columns(entity):
            if c.name.endswith(("_date", "_since", "_due", "_from", "_to")) and c.name != "called_to_date":
                assert c.type is date, (entity.table, c.name)
    assert typing.get_type_hints(models.Client)["total_aum_usd"] is float


def test_records_are_immutable():
    note = models.RMNote("N-1", "CL-1", date(2026, 1, 1), "RM", "Name", "Call", "text")
    with pytest.raises(dataclasses.FrozenInstanceError):
        note.note = "changed"
