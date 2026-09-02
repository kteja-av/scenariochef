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