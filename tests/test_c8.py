"""C8 — Observation & Evaluation tests.

Covers the C8 metrics + rulebook evaluation behavior with synthetic CSVs in
``tmp_path``: TTC/PET pairing (C8-Q4), collision, completion, the CSV data source
(C8-Q5), rulebook threshold grading (C8-Q1), custom-kind fallback, determinism, and
rulebook-version reporting. All offline, no LLM.
"""

from __future__ import annotations

import csv
from pathlib import Path

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


def test_no_collision_when_actors_stay_apart(tmp_path):
    """Actors never closer than 5 m must NOT produce a collision metric.

    Regression: the collision check unpacked the (t, gap) series as (gap, t),
    so the minimum *timestamp* (0.0) was compared against the threshold and
    every run with state data reported a collision.
    """
    rows = []
    for i in range(11):  # t = 0.0 .. 1.0
        t = round(i * 0.1, 2)
        rows.append({"t": t, "actor": "A", "x": 10 * t, "y": 0})
        rows.append({"t": t, "actor": "B", "x": 5 + 10 * t, "y": 0})  # constant 5 m gap
    rows.sort(key=lambda r: (r["actor"], r["t"]))
    metrics = compute_metrics(__import__("pathlib").Path(_csv(tmp_path, rows)))
    assert not any(m.name == "collision" for m in metrics)


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


# --- F2: a collision invalidates proximity objectives (deep-tests report) ------


def test_collision_auto_fails_ttc_objective(tmp_path):
    """RB-TTC-01 is 'ttc <= 3.0'; a crash yields TTC=0.0 which must NOT pass (F2).

    L1 witness: completed run, 1/1 objectives passed, and a 0.000 m gap in the same
    report. Collision on the measured pair now auto-fails the objective.
    """
    rows = []
    for i in range(6):  # approach then contact: gap 3.0 -> 0.0
        t = round(i * 0.1, 2)
        rows.append({"t": t, "actor": "A", "x": 3.0 - 6.0 * t, "y": 0})
        rows.append({"t": t, "actor": "B", "x": 0.0, "y": 0})
    rows.sort(key=lambda r: (r["actor"], r["t"]))
    report = evaluate(
        _run(csv_path=_csv(tmp_path, rows), sim_time=1.0),
        _ir([_objective("o-ttc", "ttc")]),
    )
    assert any(m.name == "collision" for m in report.metrics)
    r = report.objective_results[0]
    assert r.passed is False
    assert "collision" in r.detail


def test_collision_auto_fails_pet_objective(tmp_path):
    rows = []
    for i in range(6):
        t = round(i * 0.1, 2)
        rows.append({"t": t, "actor": "A", "x": 3.0 - 6.0 * t, "y": 0})
        rows.append({"t": t, "actor": "B", "x": 0.0, "y": 0})
    rows.sort(key=lambda r: (r["actor"], r["t"]))
    report = evaluate(
        _run(csv_path=_csv(tmp_path, rows), sim_time=1.0),
        _ir([_objective("o-pet", "pet")]),
    )
    assert report.objective_results[0].passed is False
    assert "collision" in report.objective_results[0].detail


def test_collision_does_not_auto_fail_other_pair_objective(tmp_path):
    """A collision on pair (A,B) leaves a ttc objective scoped to a clean pair alone.

    Stub params ['target']='C' scopes the aggregation to pairs involving C (the
    min_ttc_s/target param the LLM emits selects WHAT is measured, never the bound).
    """
    rows = []
    # A collides with B.
    for i in range(6):
        t = round(i * 0.1, 2)
        rows.append({"t": t, "actor": "A", "x": 3.0 - 6.0 * t, "y": 0})
        rows.append({"t": t, "actor": "B", "x": 0.0, "y": 0})
        # C approaches D fast enough for TTC=2.0 (<= 3.0) without contact.
        rows.append({"t": t, "actor": "C", "x": 0.0, "y": 0})
        rows.append({"t": t, "actor": "D", "x": 10.0 - 5.0 * t, "y": 0})
    rows.sort(key=lambda r: (r["actor"], r["t"]))
    ir = _ir([ObjectiveStub(id="o-c", kind="ttc", description="d", params={"target": "D"})])
    report = evaluate(_run(csv_path=_csv(tmp_path, rows), sim_time=1.0), ir)
    # The C<->D pair has a healthy TTC (2.0 s) and never collides: the objective must
    # PASS even though the unrelated A<->B pair collided.
    r = report.objective_results[0]
    assert r.passed is True, r.detail
    assert "collision" not in r.detail


def test_ttc_stub_param_scopes_pair_but_not_threshold(tmp_path):
    """params['target']='B' restricts aggregation to B-pairs; threshold stays 3.0."""
    rows = []
    # (A,B): fast approach -> small TTC. (A,C): slow approach -> large TTC.
    for i in range(11):
        t = round(i * 0.1, 2)
        rows.append({"t": t, "actor": "A", "x": 10.0 - t, "y": 0})
        rows.append({"t": t, "actor": "B", "x": 8.0, "y": 0})   # closing 1 m/s, gap 2
        rows.append({"t": t, "actor": "C", "x": 30.0 - 0.1 * t, "y": 20.0})  # far
    rows.sort(key=lambda r: (r["actor"], r["t"]))
    ir = _ir([ObjectiveStub(id="o-b", kind="ttc", description="d", params={"target": "B"})])
    report = evaluate(_run(csv_path=_csv(tmp_path, rows), sim_time=1.0), ir)
    r = report.objective_results[0]
    # B pair: gap 2.0 closing at 1 m/s -> TTC 1.0 <= 3.0 -> passes with the value
    # scoped to the B pair (the far C pair contributes nothing).
    assert r.passed is True
    assert "observed=1" in r.detail


# --- F8: the esmini --csv_logger wide format (what C7 actually emits) ----------


def _write_wide_csv(tmp_path, frames: list[tuple[float, dict[str, tuple[float, float]]]]):
    """frames: (t, {entity: (x, y)}) in the real esmini 3.7.2 layout."""
    entities = ["ego", "lead"]
    header_cells = ["Index [-]", "TimeStamp [s]"]
    for i, name in enumerate(entities, start=1):
        header_cells += [
            f"#{i} Entity_Name [-]",
            f"#{i} Entity_ID [-]",
            f"#{i} World_Position_X [m]",
            f"#{i} World_Position_Y [m]",
        ]
    lines = [
        "esmini GIT REV: v3.7.2-0-4b8fbafb",
        "Scenario File Name: /tmp/x/L1-v0.xosc",
        "Number of Vehicles: 2",
        ", ".join(header_cells) + ",",
    ]
    # units row (skipped by the parser)
    lines.append(", ".join(["-"] * len(header_cells)) + ",")
    for t, positions in frames:
        cells = [str(0), f"{t:.6f}"]
        for name in entities:
            x, y = positions[name]
            cells += [name, "0", f"{x:.6f}", f"{y:.6f}"]
        lines.append(", ".join(cells) + ", ")
    path = tmp_path / "wide_states.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_wide_esmini_csv_collision_detected(tmp_path):
    """Wide-format CSV with a closing pair must yield ttc/pet/collision (F8).

    Regression guard for the L1 unsoundness: this is the production C7->C8 data
    format, and a 'collision implies objective fails' test on it catches the case.
    """
    frames = []
    for i in range(6):
        t = round(i * 0.1, 2)
        gap = 3.0 - 0.6 * i  # 3.0, 2.4, ..., 0.0
        frames.append((t, {"ego": (gap, 0.0), "lead": (0.0, 0.0)}))
    csv_path = _write_wide_csv(tmp_path, frames)
    report = evaluate(
        _run(csv_path=csv_path, sim_time=1.0),
        _ir([_objective("o-ttc", "ttc")]),
    )
    names = {m.name for m in report.metrics}
    assert {"ttc", "pet", "collision"} <= names
    assert report.objective_results[0].passed is False
    assert "collision" in report.objective_results[0].detail


def test_wide_esmini_csv_no_collision_when_apart(tmp_path):
    frames = [(round(i * 0.1, 2), {"ego": (10.0 * i, 0.0), "lead": (50.0 + 10.0 * i, 0.0)})
              for i in range(5)]
    csv_path = _write_wide_csv(tmp_path, frames)
    metrics = compute_metrics(Path(csv_path))
    assert not any(m.name == "collision" for m in metrics)


def test_dispatch_rejects_garbage_file(tmp_path):
    """A CSV with neither the simple header nor an esmini 'Index' header yields no states."""
    p = tmp_path / "garbage.csv"
    p.write_text("hello,world\n1,2\n", encoding="utf-8")
    assert compute_metrics(p) == []


def test_empty_csv_yields_no_metrics(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    assert compute_metrics(p) == []


# --- 8. rulebook version reported from the YAML -------------------------------


def test_rulebook_version_reported():
    report = evaluate(_run(csv_path=None))
    assert report.rulebook_version == "1"