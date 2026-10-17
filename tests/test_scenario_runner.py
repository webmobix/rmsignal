import json
from datetime import date

import pytest

from rm_dashboard.agents import StubChatModel
from rm_dashboard.runners import open_registry
from rm_dashboard.runners import scenarios as runner
from rm_dashboard.runners.scenarios import main, run_scenarios
from rm_dashboard.scenarios import CatalogueStore, ScenarioRecord
from rm_dashboard.scenarios.store import ScenarioStore
from rm_dashboard.settings import Settings

AS_OF = date(2026, 8, 26)
PFS = ["PF-0001", "PF-0002", "PF-0003"]  # CL-0001 has two portfolios, CL-0002 one


class Models:
    def __init__(self, **modes):
        self.made, self.modes = [], modes

    def __call__(self, role):
        m = StubChatModel(role=role, mode=self.modes.get(role, "normal"))
        self.made.append(m)
        return m

    @property
    def calls(self):
        return sum(m.calls for m in self.made)


@pytest.fixture(scope="module")
def reg(seeded_db):
    with open_registry(Settings(db_path=str(seeded_db)), with_peer=False) as r:
        yield r


def run(reg, tmp_path, models=None, scenario="gulf-deterioration", portfolios=PFS, **kw):
    models = models or Models()
    ids = [scenario] if isinstance(scenario, str) else scenario
    return run_scenarios(reg, as_of=AS_OF, reports_dir=tmp_path, models=models, scenario_ids=ids, portfolio_ids=portfolios, **kw), models


def files(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file() and p.name not in ("audit.jsonl", "run.log")}


def test_a_run_writes_vector_impacts_roll_ups_evidence_summary_and_audit(reg, tmp_path):
    res, _ = run(reg, tmp_path)
    d = tmp_path / "2026-08-26" / "scenarios"
    sd = d / "gulf-deterioration"
    for name in ("vector.json", "evidence/vector.json", "impacts/PF-0001.json", "impacts/PF-0003.json", "clients/CL-0001.json", "clients/CL-0002.json",
                 "rollup.json"):
        assert (sd / name).is_file(), name
    assert (d / "summary.json").is_file() and (d / "audit.jsonl").read_text().strip() and (tmp_path / "scenarios" / "catalogue.json").is_file()
    assert res.produced == {"vector": 1, "impact": 3, "client": 2, "rollup": 1} and not res.failures
    s = json.loads((d / "summary.json").read_text())
    assert s["model"] == "stub" and s["scenarios"]["gulf-deterioration"]["impacts"]["count"] == 3 and s["scenarios"]["gulf-deterioration"]["vector"]["status"] == "complete"
    roll = ScenarioStore(tmp_path).load_rollup(AS_OF, "gulf-deterioration")
    assert roll.coverage.computed == 2 and roll.coverage.total == 20 and roll.status == "partial" and roll.rm_id == "RM-SG-014"


def test_the_audit_lists_run_start_and_tool_calls(reg, tmp_path):
    res, _ = run(reg, tmp_path)
    kinds = {json.loads(l)["kind"] for l in (res.out_dir / "audit.jsonl").read_text().splitlines()}
    assert {"decision", "tool_call"} <= kinds
    decisions = {json.loads(l).get("detail", {}).get("checkpoint") for l in (res.out_dir / "audit.jsonl").read_text().splitlines()}
    assert "request_entitlement" in decisions


def test_same_inputs_make_no_model_call_and_change_no_file(reg, tmp_path):
    run(reg, tmp_path)
    before = files(tmp_path)
    res, models = run(reg, tmp_path)
    assert models.calls == 0 and res.untouched and files(tmp_path) == before
    assert sum(res.skipped.values()) == 1 + 3 + 2 + 1


def test_force_regenerates(reg, tmp_path):
    run(reg, tmp_path)
    res, models = run(reg, tmp_path, force=True)
    assert models.calls > 0 and res.produced["vector"] == 1 and res.produced["impact"] == 3


def test_an_edited_premise_regenerates_the_vector_and_every_dependent_impact(reg, tmp_path):
    run(reg, tmp_path)
    store = CatalogueStore(tmp_path)
    s = store.load().get("gulf-deterioration")
    store.add(s.model_copy(update={"premise": s.premise + " Insurers withdraw cover."}))
    res, models = run(reg, tmp_path)
    assert res.produced["vector"] == 1 and res.produced["impact"] == 3 and res.produced["client"] == 2 and res.produced["rollup"] == 1 and models.calls > 0


def test_adding_a_scenario_from_text_runs_only_that_scenario(reg, tmp_path):
    run(reg, tmp_path)
    before = files(tmp_path / "2026-08-26" / "scenarios" / "gulf-deterioration")
    CatalogueStore(tmp_path).add(ScenarioRecord(scenario_id="taiwan-strait", name="Taiwan Strait", premise="Shipping lanes around Taiwan close."))
    res, _ = run(reg, tmp_path, scenario=["gulf-deterioration", "taiwan-strait"])
    assert res.produced == {"vector": 1, "impact": 3, "client": 2, "rollup": 1}
    assert files(tmp_path / "2026-08-26" / "scenarios" / "gulf-deterioration") == before
    assert ScenarioStore(tmp_path).scenario_ids(AS_OF) == ["gulf-deterioration", "taiwan-strait"]
    s = json.loads((tmp_path / "2026-08-26" / "scenarios" / "summary.json").read_text())
    assert set(s["scenarios"]) == {"gulf-deterioration", "taiwan-strait"}


def test_an_interrupted_run_resumes_with_only_the_missing_units(reg, tmp_path):
    run(reg, tmp_path)
    sd = tmp_path / "2026-08-26" / "scenarios" / "gulf-deterioration"
    (sd / "impacts" / "PF-0002.json").unlink()
    (sd / "clients" / "CL-0001.json").unlink()
    (sd / "rollup.json").unlink()
    res, _ = run(reg, tmp_path)
    assert res.produced == {"impact": 1, "client": 1, "rollup": 1} and res.skipped["vector"] == 1 and res.skipped["impact"] == 2
    assert (sd / "impacts" / "PF-0002.json").is_file() and (sd / "rollup.json").is_file()


def test_one_failing_unit_does_not_stop_the_others(reg, tmp_path, monkeypatch):
    real = runner.produce_portfolio_impact

    def flaky(registry, **kw):
        if kw["portfolio_id"] == "PF-0003":
            raise RuntimeError("model gateway down")
        return real(registry, **kw)

    monkeypatch.setattr(runner, "produce_portfolio_impact", flaky)
    res, _ = run(reg, tmp_path)
    store = ScenarioStore(tmp_path)
    assert [f.unit for f in res.failures] == ["impact gulf-deterioration x PF-0003"] and "model gateway down" in res.failures[0].error
    assert store.load_impact(AS_OF, "gulf-deterioration", "PF-0001").status != "insufficient_data"
    failed = store.load_impact(AS_OF, "gulf-deterioration", "PF-0003")
    assert failed.status == "insufficient_data" and "model gateway down" in failed.gaps[0].description
    s = json.loads((res.out_dir / "summary.json").read_text())
    assert s["failures"][0]["unit"].endswith("PF-0003") and s["scenarios"]["gulf-deterioration"]["impacts"]["failed"] == ["PF-0003"]
    assert store.load_client(AS_OF, "gulf-deterioration", "CL-0001").status != "insufficient_data"
    monkeypatch.setattr(runner, "produce_portfolio_impact", real)
    again, _ = run(reg, tmp_path)  # the failed unit is retried, the finished ones are not
    assert again.produced["impact"] == 1 and not again.failures


def test_a_model_failure_in_a_unit_is_a_gap_in_that_unit_only(reg, tmp_path):
    res, _ = run(reg, tmp_path, models=Models(scenario_impact="raise"))
    imp = ScenarioStore(tmp_path).load_impact(AS_OF, "gulf-deterioration", "PF-0001")
    assert imp.status == "partial" and imp.cases and any(g.kind == "agent_error" for g in imp.gaps)


def test_filters_reject_unknown_ids(reg, tmp_path):
    with pytest.raises(ValueError, match="unknown scenario"):
        run(reg, tmp_path, scenario="no-such")
    with pytest.raises(ValueError, match="unknown portfolio"):
        run(reg, tmp_path, portfolios=["PF-9999"])


def test_other_dates_are_never_touched(reg, tmp_path):
    other = tmp_path / "2026-06-30" / "scenarios" / "x.txt"
    other.parent.mkdir(parents=True)
    other.write_text("keep")
    run(reg, tmp_path)
    assert other.read_text() == "keep" and not (tmp_path / "2026-06-30" / "scenarios" / "summary.json").exists()


def test_command_line(seeded_db, tmp_path, capsys):
    argv = ["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(tmp_path), "--scenario", "gulf-deterioration",
            "--portfolio", "PF-0003"]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "1 vector" in out and "1 impact" in out and "model: stub" in out
    assert main(argv) == 0 and "unchanged" in capsys.readouterr().out
    assert main(["--as-of", "2026-08-26", "--db", str(seeded_db), "--reports-dir", str(tmp_path), "--scenario", "nope"]) == 2
