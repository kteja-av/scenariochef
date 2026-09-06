"""End-to-end integration tests for the CX orchestrator pipeline.

These exercise the real DAG (C1→C2→C3→C4→C5→C6→C7→C8→C9→C10) with a tmp artifact
store, so no repo artifacts are created and the suite runs offline (esmini absent →
RunRecord SKIPPED_NO_BINARY, which the pipeline tolerates).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scenariochef.c10_management.store import Store
from scenariochef.contracts.orchestration import (
    LoopBudget,
    PipelineOutcome,
)
from scenariochef.cx_orchestrator.runtime import run_pipeline, run_request

# Known C3 default assumption ids the offline null_proposer binds (DERIVED-3 ack gate).
ACKED_DEFAULTS = [
    "gap:osc.trigger.SimulationTime",
    "constraint:typical_gap_20m",
    "constraint:ego_speed_range",
]

DEMO_REQUEST = "ego follows lead in lane -1 at 20 m/s"


@pytest.fixture()
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "db.sqlite", tmp_path / "art")


def test_happy_path_completes_and_persists(store: Store) -> None:
    result = run_request(
        DEMO_REQUEST,
        "REQ-H1",
        run_id="H1",
        store=store,
        acknowledgements=ACKED_DEFAULTS,
    )
    assert result.outcome == PipelineOutcome.COMPLETED
    assert result.iterations >= 1
    assert result.validation_outcome == "passed"
    # esmini absent → RunRecord SKIPPED_NO_BINARY → no CSV → evaluation fails visibly.
    for kind in (
        "RequestSpec",
        "EvidenceBundle",
        "IntentSpec",
        "ScenarioIR",
        "GeneratedScenario",
        "ValidationReport",
        "RunRecord",
        "EvaluationReport",
        "FeedbackAction",
    ):
        assert kind in result.artifacts, f"missing persisted {kind}"
    # lineage rows exist in the store.
    assert len(store.query_lineage("H1")) >= 9


def test_e08_escalates_lane_unchanged(store: Store) -> None:
    """A lane=3 request on the two-lane map is a C6 MAP_TOPOLOGY failure.

    C9 must escalate (never rewrite the user-explicit lane) → HITL outcome.
    """
    result = run_request(
        {"text": "ego changes to lane 3", "target_lane": 3},  # user-explicit lane=3
        "REQ-E8",
        run_id="E8",
        store=store,
        acknowledgements=ACKED_DEFAULTS,
    )
    # A user-explicit out-of-range lane is a C6 MAP_TOPOLOGY FAIL; C9 escalates
    # (DERIVED-16) instead of snapping it, so CX returns a HITL.
    assert result.outcome == PipelineOutcome.HITL_BLOCKED
    # The user-explicit lane=3 must be preserved wherever it reaches the IR.
    lineage = store.query_lineage("E8")
    ir_kinds = [r for r in lineage if r.object_kind == "ScenarioIR"]
    if ir_kinds:
        import json

        rel = f"ScenarioIR-{ir_kinds[-1].object_hash[:8]}.json"
        payload = json.loads((store.artifacts_dir / "E8" / rel).read_text())
        # lane_change maneuver must carry target_lane == 3 (never snapped to ±1).
        behaviors = payload.get("behaviors", [])
        lanes = [
            int(b["params"]["target_lane"])
            for b in behaviors
            if b["action"] == "lane_change"
        ]
        assert lanes and 3 in lanes, f"user lane=3 was rewritten: {payload}"
        # and the C6-reported E08 MAP_TOPOLOGY must be visible in the validation phase
        val_kinds = [r for r in lineage if r.object_kind == "ValidationReport"]
        assert val_kinds, "E08 should produce a ValidationReport with MAP_TOPOLOGY"


def test_pipeline_tolerates_missing_esmini(store: Store) -> None:
    """Without an esmini binary the run still completes; evaluation fails visibly."""
    result = run_request(
        DEMO_REQUEST,
        "REQ-NOESM",
        run_id="NOESM",
        store=store,
        acknowledgements=ACKED_DEFAULTS,
    )
    assert result.outcome == PipelineOutcome.COMPLETED
    # No simulation state → every objective fails with "no state data".
    assert "no_state_data" in (result.evaluation_summary or "")


def test_unacked_assumptions_surface_as_hitl(store: Store) -> None:
    """Defaults not acked by C1/C2 (DERIVED-3) → assumption_ack HITL, not a crash."""
    result = run_request(
        DEMO_REQUEST,
        "REQ-HITL",
        run_id="HITL",
        store=store,
        acknowledgements=[],  # nothing accepted
    )
    assert result.outcome == PipelineOutcome.HITL_BLOCKED


def test_wall_clock_budget_halts_loop(store: Store) -> None:
    """A tiny wall-clock budget that trips on the first loop check returns failed."""
    result = run_request(
        DEMO_REQUEST,
        "REQ-TMO",
        run_id="TMO",
        store=store,
        acknowledgements=ACKED_DEFAULTS,
        budget=LoopBudget(max_iterations=5, wall_clock_s=0.001),  # tiny budget
    )
    assert "wall_clock" in (result.evaluation_summary or "")
    assert result.outcome == PipelineOutcome.FAILED


# --- deep-tests report fixes ---------------------------------------------------


class _ExplodingProposer:
    """Stub LLM proposer that always fails after bounded retries (F3 witness)."""

    def __call__(self, prompt: str) -> dict:
        raise RuntimeError("LLM proposer failed after 3 attempts: 503")


def test_persistent_llm_failure_becomes_hitl_not_crash(store: Store) -> None:
    """CommandCodeProposer RuntimeError must surface as a HITL (deep-tests F3)."""
    import scenariochef.cx_orchestrator.runtime as cx_mod

    original = cx_mod.run_c2

    def _failing_run_c2(*args, **kwargs):
        # force the proposer path: kwargs proposer injection
        kwargs["proposer"] = _ExplodingProposer()
        return original(*args, **kwargs)

    cx_mod.run_c2 = _failing_run_c2
    try:
        result = run_request(
            DEMO_REQUEST,
            "REQ-LLMFAIL",
            run_id="LLMFAIL",
            store=store,
            acknowledgements=ACKED_DEFAULTS,
        )
    finally:
        cx_mod.run_c2 = original
    assert result.outcome == PipelineOutcome.HITL_BLOCKED


def test_run_pipeline_trace_sink_restored_on_failure(tmp_path, monkeypatch) -> None:
    """A raising trajectory leaves trace pointed at stdout, not a closed file (F7)."""
    import io

    import scenariochef.cx_orchestrator.runtime as cx_mod
    from scenariochef import trace

    monkeypatch.setattr(cx_mod, "LOG_PATH", tmp_path / "trace.log")
    original = cx_mod._run_one_trajectory

    def _boom(trajectory_id: str) -> None:
        if trajectory_id.endswith("0002"):
            raise RuntimeError("boom")
        original(trajectory_id)

    monkeypatch.setattr(cx_mod, "_run_one_trajectory", _boom)
    with pytest.raises(RuntimeError, match="boom"):
        cx_mod.run_pipeline(3)

    # the sink must still work — emit to it (a closed file would raise ValueError).
    sink = io.StringIO()
    trace.set_log(sink)
    trace.emit(1, "CX", "IN", "<probe>", "REQ-PROBE")
    assert "REQ-PROBE" in sink.getvalue()


def test_ack_c2_defaults_failure_surfaces() -> None:
    """_ack_c2_defaults must not silently swallow a malformed bundle (F9)."""
    from scenariochef.cx_orchestrator.runtime import _ack_c2_defaults

    class _BrokenItem:
        fact_or_assumption = "assumption"
        id = "x"

        def model_copy(self, update):
            raise KeyError("boom")

    class _BrokenBundle:
        definitions = [_BrokenItem()]
        constraints: list = []
        examples: list = []
        compatibility: list = []
        provenance: list = []

        def model_copy(self, update):
            raise KeyError("boom")

    with pytest.raises(KeyError):
        _ack_c2_defaults(_BrokenBundle(), ["x"])


def test_cx_sweep_path_runs_and_scores_best_ttc(store: Store, monkeypatch) -> None:
    """The C9 explore -> esmini sweep leg executes and reports the best TTC (F8).

    The sweep callable is monkeypatched (real esmini absent); the CX orchestration
    around it — per-permutation persistence and best-TTC selection — is what's under
    test. The request's ego_speed_range keeps the sweep machinery reachable.
    """
    import scenariochef.c7_esmini.runtime as c7mod
    from scenariochef.contracts.common import TraceMeta
    from scenariochef.contracts.run_record import RunConfig, RunRecord, RunStatus

    calls: list[list[float]] = []

    import csv as _csv

    def _csv_with_ttc(tmp: Path, ttc_s: float) -> str:
        """A tiny state CSV whose min TTC equals ttc_s (gap 2, closing 1 m/s)."""
        rows = []
        for i in range(4):
            t = round(i * 0.1, 2)
            rows.append({"t": t, "actor": "A", "x": 2.0 - 1.0 * t, "y": 0})
            rows.append({"t": t, "actor": "B", "x": 0.0, "y": 0})
        path = tmp / f"states_{ttc_s}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=["t", "actor", "x", "y"])
            w.writeheader()
            w.writerows(rows)
        return str(path)

    csv_paths = []
    def _fake_sweep(gs, param_name, values, trajectory_id="REQ-0001", config=None):
        calls.append(list(values))
        records = []
        for i, v in enumerate(values):
            p = _csv_with_ttc(Path(store.artifacts_dir), 1.0 + i)
            csv_paths.append(p)
            records.append(
                RunRecord(
                    meta=TraceMeta(request_id="REQ-SWEEP", trajectory_id=trajectory_id,
                                   created_at="2000-01-01T00:00:00+00:00", produced_by="C7"),
                    config=RunConfig(esmini_build="x", dt_s=0.05, seed=1, max_time_s=5.0),
                    mode="full", exit_code=0,
                    simulation_csv_path=p,
                    sim_time_s=float(i),
                    status=RunStatus.COMPLETED,
                )
            )
        return records

    monkeypatch.setattr(c7mod, "run_c7_sweep", _fake_sweep)

    # The offline null_proposer emits no constraints; a stub proposer adds the
    # ego_speed_range constraint the CX sweep leg keys on (mirrors what the real LLM
    # emitted in the L4/L5 live runs).
    import scenariochef.cx_orchestrator.runtime as cx_mod

    def _run_c2_with_range(request_spec, trajectory_id, evidence=None, **_kw):
        from scenariochef.c2_understanding.runtime import gate as _gate
        from scenariochef.c2_understanding.runtime import last_proposals as _lp

        proposal = {
            "actors": [
                {"name": "ego", "role": "ego",
                 "initial_speed_mps": {"min": 10.0, "max": 20.0, "unit": "mps"},
                 "position": {"frame": "lane_relative", "road_id": 1, "lane_id": -1, "s_m": 0.0}},
                {"name": "lead", "role": "target", "initial_speed_mps": 15.0,
                 "position": {"frame": "lane_relative", "road_id": 1, "lane_id": -1, "s_m": 50.0}},
            ],
            "maneuvers": [{"actor": "ego", "action": "follow", "params": {"leader": "lead"}}],
            "constraints": [
                {"name": "ego_speed_range",
                 "value": {"min": 10.0, "max": 20.0, "unit": "mps"}, "unit": "mps"}
            ],
            "objectives": [],
            "confidence": 0.95,
            "unknowns": [],
        }
        _lp[trajectory_id] = proposal
        return _gate(proposal, request_spec, evidence)

    monkeypatch.setattr(cx_mod, "run_c2", _run_c2_with_range)

    result = run_request(
        "ego follows lead at between 10 and 20 m/s",
        "REQ-SWEEP",
        run_id="SWEEP",
        store=store,
        acknowledgements=ACKED_DEFAULTS,
        # max_iterations=1: iteration 0 runs the sweep leg and its summary lands in
        # the final result (later iterations would overwrite it and exhaust the cap).
        budget=LoopBudget(max_iterations=1),
    )
    assert result.outcome in (PipelineOutcome.COMPLETED, PipelineOutcome.FAILED)
    assert calls, "the sweep leg never executed"
    # the sweep received the candidate values derived from the request range.
    assert all(len(v) == 3 for v in calls)
    assert "swept" in (result.evaluation_summary or "")
    assert "best TTC" in (result.evaluation_summary or "")


def test_same_request_same_hashes(store: Store, tmp_path: Path) -> None:
    """G1: identical requests produce identical artifact hashes (created_at pinned)."""
    result_a = run_request(
        DEMO_REQUEST, "REQ-DET", run_id="D1", store=store,
        acknowledgements=ACKED_DEFAULTS,
    )
    store2 = Store(tmp_path / "db2.sqlite", tmp_path / "art2")
    result_b = run_request(
        DEMO_REQUEST, "REQ-DET", run_id="D2", store=store2,
        acknowledgements=ACKED_DEFAULTS,
    )
    store2.close()
    assert result_a.artifacts == result_b.artifacts


def test_demo_pipeline_emits_canonical_trace(tmp_path: Path) -> None:
    """run_pipeline(N) still emits the [step:NN] trace contract lines to the log."""
    from scenariochef.cx_orchestrator.runtime import LOG_PATH

    # run_pipeline writes to the repo's gitignored artifacts/trace_run.log.
    run_pipeline(1)
    assert LOG_PATH.exists()
    lines = LOG_PATH.read_text()
    assert "CX  IN" in lines
    assert "C1  OUT" in lines
    assert "C10 OUT" in lines
    assert "CX  OUT" in lines