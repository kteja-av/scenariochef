"""C8 — Observation & Evaluation tests.

Covers the C8 metrics + rulebook evaluation behavior with synthetic CSVs in
``tmp_path``: TTC/PET pairing (C8-Q4), collision, completion, the CSV data source
(C8-Q5), rulebook threshold grading (C8-Q1), custom-kind fallback, determinism, and
rulebook-version reporting. All offline, no LLM.
"""

from __future__ import annotations

import csv

from scenariochef.c8_evaluation.runtime import compute_metrics, evaluate
from scenariochef.contracts.common import TraceMeta
from scenariochef.contracts.intent_spec import ObjectiveStub
from scenariochef.contracts.run_record import RunConfig, RunRecord, RunStatus
from scenariochef.contracts.scenario_ir import IRHeader, IRMap, ScenarioIR

SHA256_PLACEHOLDER = "0" * 64


def _csv(tmp_path, rows: list[dict]) -> str:
    path = tmp_path / "states.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["t", "actor", "x", "y"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


def _run(
    csv_path: str | None = None, sim_time: float | None = None, max_time: float = 30.0
) -> RunRecord:
    return RunRecord(
        meta=TraceMeta(
            request_id="REQ-0001",
            trajectory_id="REQ-0001",
            produced_by="test-c8",
        ),
        config=RunConfig(
            esmini_build="esmini-0.10",
            dt_s=0.1,
            seed=42,
            max_time_s=max_time,
        ),
        mode="full",
        exit_code=0,
        simulation_csv_path=csv_path,
        sim_time_s=sim_time,
        status=RunStatus.COMPLETED,
    )


def _ir(objectives: list[ObjectiveStub]) -> ScenarioIR:
    return ScenarioIR(
        meta=TraceMeta(
            request_id="REQ-0001",
            trajectory_id="REQ-0001",
            produced_by="test-c8",
        ),
        header=IRHeader(request_id="REQ-0001", intent_spec_hash="h", esmini_pin="p"),
        map=IRMap(map_asset_id="m", sha256=SHA256_PLACEHOLDER),
        objectives=objectives,
    )


def _objective(obj_id: str, kind: str) -> ObjectiveStub:
    return ObjectiveStub(id=obj_id, kind=kind, description="objective", params={})


# --- 1. approaching pair: TTC + PET both present for the same pair -------------


def test_ttc_and_pet_paired_for_approaching_pair(tmp_path):
    rows = []
    for i in range(16):  # t = 0.0 .. 1.5
        t = round(i * 0.1, 2)
        rows.append({"t": t, "actor": "A", "x": 10 - 2 * t, "y": 0})
        rows.append({"t": t, "actor": "B", "x": 6.0, "y": 0})
    rows.sort(key=lambda r: (r["actor"], r["t"]))
    metrics = compute_metrics(__import__("pathlib").Path(_csv(tmp_path, rows)))
    pair = ("A", "B")
    assert any(m.name == "ttc" and m.actor_pair == pair for m in metrics)
    assert any(m.name == "pet" and m.actor_pair == pair for m in metrics)


# --- 2. colliding CSV -> collision 1.0 ----------------------------------------


def test_collision_metric(tmp_path):
    rows = []
    for i in range(11):  # t = 0.0 .. 1.0
        t = round(i * 0.1, 2)
        rows.append({"t": t, "actor": "A", "x": 10 - 10 * t, "y": 0})
        rows.append({"t": t, "actor": "B", "x": 5.1, "y": 0})
    rows.sort(key=lambda r: (r["actor"], r["t"]))
    metrics = compute_metrics(__import__("pathlib").Path(_csv(tmp_path, rows)))
    pair = ("A", "B")
    assert any(m.name == "collision" and m.actor_pair == pair and m.value == 1.0 for m in metrics)


# --- 3. completion: sim_time vs max_time --------------------------------------


def test_completion_pass_and_fail(tmp_path):
    rows = [{"t": 0.0, "actor": "A", "x": 0.0, "y": 0.0}]
    path = _csv(tmp_path, rows)
    report_yes = evaluate(_run(csv_path=path, sim_time=29.0, max_time=30.0))
    report_no = evaluate(_run(csv_path=path, sim_time=10.0, max_time=30.0))
    comp_yes = [m for m in report_yes.metrics if m.name == "completion"]
    comp_no = [m for m in report_no.metrics if m.name == "completion"]
    assert comp_yes and comp_yes[0].value == 1.0
    assert comp_no and comp_no[0].value == 0.0


# --- 4. no CSV -> empty metrics, objectives fail "no state data" --------------


def test_no_csv_empty_metrics_and_no_state_data():
    ir = _ir([_objective("o1", "ttc")])
    report = evaluate(_run(csv_path=None), ir)
    assert report.metrics == []
    assert report.failure_class == "no_state_data"
    assert len(report.objective_results) == 1
    r = report.objective_results[0]
    assert r.passed is False
    assert r.detail == "no state data"


# --- 5. TTC threshold: RB-TTC-01 (<= 3.0) -------------------------------------


def test_ttc_below_threshold_passes(tmp_path):
    report = evaluate(
        _run(csv_path=_csv(tmp_path, _rows_for_ttc(2.0)), sim_time=1.0),
        _ir([_objective("o-ttc", "ttc")]),
    )
    r = report.objective_results[0]
    assert r.passed is True
    assert r.threshold_source == "RB-TTC-01"


def test_ttc_above_threshold_fails(tmp_path):
    report = evaluate(
        _run(csv_path=_csv(tmp_path, _rows_for_ttc(4.5)), sim_time=1.0),
        _ir([_objective("o-ttc", "ttc")]),
    )
    r = report.objective_results[0]
    assert r.passed is False
    assert r.threshold_source == "RB-TTC-01"


def _rows_for_ttc(min_ttc: float):
    rows = []
    n = int(min_ttc * 10)
    for i in range(n + 1):
        t = round(i * 0.1, 2)
        gap = min_ttc + (n - i) * 0.1  # gap shrinks by closing speed 1
        rows.append({"t": t, "actor": "A", "x": 10.0 - gap, "y": 0})
        rows.append({"t": t, "actor": "B", "x": 10.0, "y": 0})
    rows.sort(key=lambda r: (r["actor"], r["t"]))
    return rows


# --- 6. custom kind -> threshold_source "none", passed False ------------------


def test_custom_kind_no_rule(tmp_path):
    rows = _rows_for_ttc(2.0)
    report = evaluate(
        _run(csv_path=_csv(tmp_path, rows), sim_time=1.0),
        _ir([_objective("o-custom", "custom")]),
    )
    r = report.objective_results[0]
    assert r.passed is False
    assert r.threshold_source == "none"


# --- 7. determinism: evaluate twice -> identical metric sequences -------------


def test_deterministic_evaluate(tmp_path):
    rows = _rows_for_ttc(2.0)
    path = _csv(tmp_path, rows)
    ir = _ir([_objective("o-ttc", "ttc")])
    first = evaluate(_run(csv_path=path, sim_time=29.0), ir)
    second = evaluate(_run(csv_path=path, sim_time=29.0), ir)

    def seq(rep) -> list:
        return [(m.name, m.actor_pair, m.value) for m in rep.metrics]

    assert seq(first) == seq(second)


# --- 8. rulebook version reported from the YAML -------------------------------


def test_rulebook_version_reported():
    report = evaluate(_run(csv_path=None))
    assert report.rulebook_version == "1"