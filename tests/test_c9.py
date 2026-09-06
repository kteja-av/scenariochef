"""C9 — Feedback & Improvement tests: repair and explore.

Hand-builds ValidationReports/EvaluationReports and ScenarioIRs from the contracts to
exercise the decision rules without any pipeline machinery. Verifies ARCH-0002 (no
rewrites of user-explicit slots), ARCH-0001 (pure rules — no LLM), C9-Q4 (loop budget),
C9-Q5 (revised_ir is a NEW object), and the per-taxonomy repair mapping.
"""

from __future__ import annotations

from scenariochef.c9_feedback.runtime import plan_explore, plan_repair, run_c9
from scenariochef.contracts.common import (
    FrameTag,
    Position,
    Range,
    Severity,
    TraceMeta,
    Unit,
)
from scenariochef.contracts.evaluation_report import DataSource, EvaluationReport, Metric
from scenariochef.contracts.scenario_ir import (
    IRBehavior,
    IRConstraint,
    IRHeader,
    IRMap,
    ScenarioIR,
)
from scenariochef.contracts.validation_report import (
    ErrorTaxonomy,
    Stage,
    StageResult,
    Status,
    ValidationError,
    ValidationReport,
)


def _meta(trajectory_id: str = "REQ-0001") -> TraceMeta:
    return TraceMeta(request_id="REQ-0001", trajectory_id=trajectory_id, produced_by="test-c9")


def _ir(**overrides) -> ScenarioIR:
    """A minimal but valid ScenarioIR; override behaviors/constraints/actors per test."""
    base: dict = dict(
        meta=_meta(),
        header=IRHeader(request_id="REQ-0001", intent_spec_hash="x", esmini_pin="p1"),
        map=IRMap(map_asset_id="m1", sha256="0" * 64),
        actors=[],
        behaviors=[],
        constraints=[],
        objectives=[],
        suggestions=[],
        feature_keys=[],
    )
    base.update(overrides)
    return ScenarioIR(**base)


def _actor(name: str) -> object:
    from scenariochef.contracts.scenario_ir import IRActor

    return IRActor(
        name=name,
        kind="vehicle",
        bbox_ref="bbox-a",
        spawn=Position(frame=FrameTag.CARTESIAN, x_m=0.0, y_m=0.0),
        initial_speed_mps=10.0,
    )


def _behavior(actor: str, params=None) -> IRBehavior:
    from scenariochef.contracts.intent_spec import ActionType

    return IRBehavior(actor=actor, action=ActionType.SPEED_CHANGE, params=params or {})


def _validation(
    code: ErrorTaxonomy, *, severity: Severity = Severity.ERROR,
    hint: str | None = None,
) -> ValidationReport:
    return ValidationReport(
        meta=_meta(),
        outcome=Status.FAIL,
        stages=[
            StageResult(
                stage=Stage.S1,
                status=Status.FAIL if severity == Severity.ERROR else Status.WARN,
                errors=[ValidationError(
                    code=code, severity=severity, message="boom", repair_hint=hint
                )],
            )
        ],
    )


def _speed_constraint() -> IRConstraint:
    return IRConstraint(
        name="initial_speed:ego",
        value=Range(min=10.0, max=20.0, unit=Unit.MPS),
        unit="mps",
    )


# --- 1. MAP_TOPOLOGY → escalate, no rewrite ---------------------------------

def test_map_topology_escalates_without_rewrite():
    report = _validation(ErrorTaxonomy.MAP_TOPOLOGY, hint="lane L2 not found on road 1")
    action = plan_repair(report, _ir(), iteration=0)
    assert action.escalate_to_user is True
    assert action.stop is True
    assert action.revised_ir is None
    assert action.escalation_reason == "lane L2 not found on road 1"
    assert action.type == "repair"


# --- 2. SEMANTIC_REF → drop dangling behavior, actors byte-identical --------

def test_semantic_ref_drops_dangling_behavior():
    ir = _ir(
        actors=[_actor("ego"), _actor("target")],
        behaviors=[_behavior("ego"), _behavior("ghost", {"v": 5.0})],
    )
    report = _validation(ErrorTaxonomy.SEMANTIC_REF)
    action = plan_repair(report, ir, iteration=0)
    assert action.revised_ir is not None
    assert [b.actor for b in action.revised_ir.behaviors] == ["ego"]
    # Original IR unchanged (no in-place mutation) and actors byte-identical.
    assert [b.actor for b in ir.behaviors] == ["ego", "ghost"]
    assert action.revised_ir.actors == ir.actors


# --- 3. PHYSICAL_BOUNDS non-user-explicit 90 → clamp 70.0 in a copy ---------

def test_physical_bounds_clamps_to_70_in_new_object():
    ir = _ir(actors=[_actor("ego")], behaviors=[_behavior("ego", {"speed": 90.0})])
    report = _validation(ErrorTaxonomy.PHYSICAL_BOUNDS)
    action = plan_repair(report, ir, iteration=0)
    assert action.revised_ir is not None
    assert action.revised_ir.behaviors[0].params["speed"] == 70.0
    # Original IR untouched.
    assert ir.behaviors[0].params["speed"] == 90.0
    assert action.revised_ir is not ir


def test_physical_bounds_user_explicit_escalates_no_rewrite():
    ir = _ir(actors=[_actor("ego")], behaviors=[_behavior("ego", {"speed": 90.0})])
    # Mark the behavior param as user_explicit via the provenance key shape.
    ir.behaviors[0].params["provenance"] = "user_explicit"
    report = _validation(ErrorTaxonomy.PHYSICAL_BOUNDS)
    action = plan_repair(report, ir, iteration=0)
    assert action.escalate_to_user is True
    assert action.stop is True
    assert action.revised_ir is None


# --- 4. XSD_INVALID → stop False, revised_ir None ---------------------------

def test_xsd_invalid_no_ir_level_repair():
    report = _validation(ErrorTaxonomy.XSD_INVALID)
    action = plan_repair(report, _ir(), iteration=0)
    assert action.stop is False
    assert action.revised_ir is None
    assert "regenerate upstream" in action.rationale


# --- 5. E09 WARN tolerated --------------------------------------------------

def test_warn_tolerated():
    report = _validation(ErrorTaxonomy.UNREACHABLE_TRIGGER, severity=Severity.WARN)
    action = plan_repair(report, _ir(), iteration=0)
    assert action.stop is False
    assert action.revised_ir is None


# --- 6. iteration >= 5 → max_iterations (both subsystems) -------------------

def test_max_iterations_repair():
    report = _validation(ErrorTaxonomy.XSD_INVALID)
    action = plan_repair(report, _ir(), iteration=5)
    assert action.stop is True
    assert action.stop_reason == "max_iterations"


def test_max_iterations_explore():
    ir = _ir(constraints=[_speed_constraint()])
    ev = _eval()
    action = plan_explore(ev, ir, iteration=5)
    assert action.stop is True
    assert action.stop_reason == "max_iterations"


# --- 7. Range sweep by iteration --------------------------------------------

def _eval() -> EvaluationReport:
    return EvaluationReport(
        meta=_meta(),
        metrics=[],
        objective_results=[],
        rulebook_version="r1",
        data_source=DataSource.CSV,
    )


def test_range_sweep_candidates():
    c = _speed_constraint()

    for iteration, expected in ((0, 10.0), (1, 15.0), (2, 20.0)):
        ir = _ir(constraints=[c])
        action = plan_explore(_eval(), ir, iteration=iteration)
        assert action.param_sweep[0].param == "initial_speed:ego"
        assert action.param_sweep[0].value == expected
        assert action.param_sweep[0].source_range == c.value
        assert action.revised_ir is not None
        assert action.revised_ir is not ir
        assert action.revised_ir.constraints[0].value == expected


def _lane_offset_constraint() -> IRConstraint:
    return IRConstraint(
        name="lateral_offset:ego",
        value=Range(min=-2.0, max=2.0, unit=Unit.M),
        unit="m",
    )


# --- 7b. constraint rotation across iterations (EXPM-0001) -------------------


def test_range_sweep_rotates_constraints():
    """Multi-constraint IRs round-robin the sweep; single-constraint IRs are unchanged."""
    ir = _ir(constraints=[_speed_constraint(), _lane_offset_constraint()])
    a0 = plan_explore(_eval(), ir, iteration=0)
    a1 = plan_explore(_eval(), ir, iteration=1)
    a2 = plan_explore(_eval(), ir, iteration=2)
    a3 = plan_explore(_eval(), ir, iteration=3)
    assert a0.param_sweep[0].param == "initial_speed:ego"
    assert a0.param_sweep[0].value == 10.0  # min (pinned schedule)
    assert a1.param_sweep[0].param == "lateral_offset:ego"
    assert a1.param_sweep[0].value == 0.0  # mid of [-2, 2]
    assert a2.param_sweep[0].param == "initial_speed:ego"
    assert a2.param_sweep[0].value == 20.0  # max
    assert a3.param_sweep[0].param == "lateral_offset:ego"
    # pinned schedule step 4 = min(min * 1.1, max) = min(-2.2, 2.0)
    assert a3.param_sweep[0].value == -2.2


# --- 8. no_metric_gain ------------------------------------------------------

def test_no_metric_gain_stops():
    ir = _ir(constraints=[_speed_constraint()])
    prev = [Metric(name="ttc", value=0.05, unit=Unit.S, actor_pair=("ego", "target"))]
    action = plan_explore(_eval(), ir, iteration=1, last_metrics=prev)
    assert action.stop is True
    assert action.stop_reason == "no_metric_gain"


def test_plateau_stop_relative_gain():
    """A <1 percent relative improvement over the previous iteration stops (EXPM-0002)."""
    ir = _ir(constraints=[_speed_constraint()])
    prev = [Metric(name="ttc", value=4.000, unit=Unit.S, actor_pair=("ego", "target"))]
    curr = [Metric(name="ttc", value=3.995, unit=Unit.S, actor_pair=("ego", "target"))]
    action = plan_explore(_eval(), ir, iteration=2, last_metrics=curr, prev_metrics=prev)
    assert action.stop is True
    assert action.stop_reason == "no_metric_gain"


def test_meaningful_gain_keeps_exploring():
    """A >=1 percent relative improvement continues (never stops on progress)."""
    ir = _ir(constraints=[_speed_constraint()])
    prev = [Metric(name="ttc", value=4.000, unit=Unit.S, actor_pair=("ego", "target"))]
    curr = [Metric(name="ttc", value=3.900, unit=Unit.S, actor_pair=("ego", "target"))]
    action = plan_explore(_eval(), ir, iteration=2, last_metrics=curr, prev_metrics=prev)
    assert action.stop is False


def test_metric_improved_keeps_exploring():
    ir = _ir(constraints=[_speed_constraint()])
    prev = [Metric(name="ttc", value=5.0, unit=Unit.S, actor_pair=("ego", "target"))]
    action = plan_explore(_eval(), ir, iteration=0, last_metrics=prev)
    assert action.stop is False


# --- 9. run_c9 dispatch by type ---------------------------------------------

def test_run_c9_dispatches_by_report_type():
    v = _validation(ErrorTaxonomy.MAP_TOPOLOGY)
    a = run_c9(v, trajectory_id="REQ-0001", scenario_ir=_ir(), iteration=0)
    assert a.type == "repair"
    assert a.escalate_to_user is True

    ir = _ir(constraints=[_speed_constraint()])
    e = _eval()
    a2 = run_c9(e, trajectory_id="REQ-0001", scenario_ir=ir, iteration=0)
    assert a2.type == "explore"
    assert a2.param_sweep[0].value == 10.0