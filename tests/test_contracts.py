"""Tests for the ScenarioChef typed contracts package.

Covers the invariants a downstream component relies on:
- Position frame-consistency (C4-Q2) and Range min<=max (C4-Q4).
- IntentSpec DERIVED-3 (c3_default requires both acks) vs user_explicit (no acks needed).
- Frozen models reject mutation (RequestSpec, IntentSpec, ScenarioIR...).
- content_hash vs semantic_hash: equal content + different meta must hash differently
  on content_hash but identically on semantic_hash.
- JSON round-trip for every public model.
- RunConfig mandatory fields, RunRecord SKIPPED_NO_BINARY constructibility.
- FeedbackAction escalate path fields.
"""

import json

import pytest
from pydantic import ValidationError

from scenariochef.contracts import (
    ActionType,
    ActorIntent,
    ActorRole,
    ErrorTaxonomy,
    EvidenceBundle,
    EvidenceItem,
    FeedbackAction,
    FrameTag,
    GeneratedScenario,
    HitlKind,
    HitlRequest,
    IntentSpec,
    IRActor,
    IRBehavior,
    IRConstraint,
    IRHeader,
    IRMap,
    IRSuggestion,
    K3Flag,
    LineageMap,
    LoopBudget,
    ManeuverIntent,
    Metric,
    Modality,
    ObjectiveKind,
    ObjectiveResult,
    ObjectiveStub,
    PersistenceRecord,
    PipelineResult,
    Position,
    Range,
    RequestSpec,
    RunConfig,
    RunRecord,
    RunStatus,
    ScenarioIR,
    Severity,
    SlotProvenance,
    Stage,
    StageResult,
    Status,
    SupportLevel,
    TraceMeta,
    Unit,
    ValidationReport,
    XoscArtifact,
    content_hash,
    semantic_hash,
)
from scenariochef.contracts import (
    ValidationError as ModelValidationError,
)


def _meta(request_id: str = "req-1") -> TraceMeta:
    return TraceMeta(
        request_id=request_id,
        trajectory_id="t-1",
        produced_by="test",
    )


# --- 1. Position frame consistency ----------------------------------------


def test_position_lane_relative_missing_lane_id():
    with pytest.raises(ValidationError):
        Position(frame=FrameTag.LANE_RELATIVE, road_id=1, s_m=10.0)


def test_position_lane_relative_ok():
    p = Position(frame=FrameTag.LANE_RELATIVE, road_id=1, lane_id=2, s_m=10.0)
    assert p.frame is FrameTag.LANE_RELATIVE


def test_position_cartesian_ok():
    p = Position(frame=FrameTag.CARTESIAN, x_m=1.0, y_m=2.0)
    assert p.x_m == 1.0 and p.y_m == 2.0


def test_position_road_relative_ok():
    p = Position(frame=FrameTag.ROAD_RELATIVE, road_id=1, s_m=5.0)
    assert p.frame is FrameTag.ROAD_RELATIVE


def test_position_frame_required():
    with pytest.raises(ValidationError):
        Position(x_m=1.0, y_m=2.0)


# --- 2. IntentSpec DERIVED-3 ----------------------------------------------


def _base_intent() -> dict:
    return {"meta": _meta().model_dump(), "confidence": 0.9}


def test_c3_default_without_acks_rejected():
    with pytest.raises(ValidationError):
        ActorIntent(
            name="ego",
            kind="vehicle",
            role=ActorRole.EGO,
            initial_position=Position(frame=FrameTag.CARTESIAN, x_m=0.0, y_m=0.0),
            initial_speed_mps=10.0,
            slot=SlotProvenance(source="c3_default", accepted_by_c1=True, accepted_by_c2=False),
        )


def test_c3_default_with_both_acks_ok():
    actor = ActorIntent(
        name="ego",
        kind="vehicle",
        role=ActorRole.EGO,
        initial_position=Position(frame=FrameTag.CARTESIAN, x_m=0.0, y_m=0.0),
        initial_speed_mps=10.0,
        slot=SlotProvenance(source="c3_default", accepted_by_c1=True, accepted_by_c2=True),
    )
    spec = IntentSpec(**_base_intent(), actors=[actor])
    assert spec.actors[0].name == "ego"


def test_user_explicit_without_acks_ok():
    slot = SlotProvenance(source="user_explicit", accepted_by_c1=False, accepted_by_c2=False)
    spec = IntentSpec(
        **_base_intent(),
        maneuvers=[ManeuverIntent(actor="ego", action=ActionType.BRAKE, params={}, slot=slot)],
    )
    assert spec.maneuvers[0].action is ActionType.BRAKE


def test_llm_proposed_default_ok_without_acks():
    spec = IntentSpec(**_base_intent())
    assert spec.actors == []


# --- 3. Range min<=max ----------------------------------------------------


def test_range_min_gt_max_rejected():
    with pytest.raises(ValidationError):
        Range(min=20.0, max=10.0, unit=Unit.M)


def test_range_ok():
    r = Range(min=5.0, max=20.0, unit=Unit.M)
    assert r.unit is Unit.M


# --- 4. Frozen models ------------------------------------------------------


def test_request_spec_frozen():
    spec = RequestSpec(
        meta=_meta().model_dump(),
        modality=Modality.NL_PARAMS,
        raw="car brakes at 40 m",
        params={},
    )
    with pytest.raises(ValidationError):
        spec.raw = "changed"


def test_scenario_ir_frozen():
    ir = _make_ir()
    with pytest.raises(ValidationError):
        ir.actors = []


# --- 5. content_hash vs semantic_hash -------------------------------------


def test_content_semantic_hash_differ_on_meta():
    a = RequestSpec(meta=_meta("req-a"), modality=Modality.NL_PARAMS, raw="x", params={})
    b = RequestSpec(meta=_meta("req-b"), modality=Modality.NL_PARAMS, raw="x", params={})
    # Different meta => different content_hash, identical semantic_hash.
    assert content_hash(a) != content_hash(b)
    assert semantic_hash(a) == semantic_hash(b)


def test_content_hash_deterministic():
    m = TraceMeta(
        request_id="req-1",
        trajectory_id="t-1",
        created_at="2026-01-01T00:00:00+00:00",
        produced_by="test",
    )
    a = RequestSpec(meta=m, modality=Modality.NL_PARAMS, raw="x", params={"gap_m": 10})
    b = RequestSpec(meta=m, modality=Modality.NL_PARAMS, raw="x", params={"gap_m": 10})
    assert content_hash(a) == content_hash(b)


# --- 6. JSON round-trip for all public models -----------------------------


def _make_ir() -> ScenarioIR:
    actor = IRActor(
        name="ego",
        kind="vehicle",
        bbox_ref="catalog.ev.1",
        spawn=Position(frame=FrameTag.CARTESIAN, x_m=0.0, y_m=0.0),
        initial_speed_mps=10.0,
    )
    return ScenarioIR(
        meta=_meta().model_dump(),
        header=IRHeader(request_id="req-1", intent_spec_hash="abc", esmini_pin="1.0"),
        map=IRMap(map_asset_id="map-a", sha256="deadbeef"),
        actors=[actor],
        behaviors=[
            IRBehavior(
                actor="ego",
                action=ActionType.SPEED_CHANGE,
                params={"target_speed_mps": 5.0},
            )
        ],
        constraints=[
            IRConstraint(
                name="max_speed",
                value=Range(min=0.0, max=30.0, unit=Unit.MPS),
                unit="mps",
            )
        ],
        objectives=[ObjectiveStub(id="o1", kind=ObjectiveKind.TTC, description="ttc>2")],
        suggestions=[IRSuggestion(code="E09", message="trigger far", field_path="triggers[0]")],
        feature_keys=["osc.act.SpeedChange"],
    )


@pytest.mark.parametrize(
    "model",
    [
        lambda: RequestSpec(
            meta=_meta().model_dump(), modality=Modality.NL_PARAMS, raw="x", params={"gap_m": 10}
        ),
        lambda: IntentSpec(**_base_intent()),
        lambda: EvidenceBundle(
            meta=_meta().model_dump(),
            definitions=[EvidenceItem(
                id="e1",
                feature_key="osc.action.LaneChange",
                claim="lane change",
                source_ref="xsd",
                authority="xsd",
                fact_or_assumption="fact",
                support=SupportLevel.SUPPORTS,
                simulator_build="1.0",
            )],
        ),
        _make_ir,
        lambda: GeneratedScenario(
            meta=_meta().model_dump(),
            scenario_name="s",
            xosc=XoscArtifact(content="<xosc/>", sha256="h"),
            k3_flags=[K3Flag(feature_key="f", support=SupportLevel.UNKNOWN)],
        ),
        lambda: ValidationReport(
            meta=_meta().model_dump(),
            stages=[
                StageResult(
                    stage=Stage.S1,
                    status=Status.PASS,
                    errors=[ModelValidationError(
                        code=ErrorTaxonomy.XSD_INVALID,
                        severity=Severity.ERROR,
                        message="bad",
                        location="/xosc",
                    )],
                )
            ],
            outcome=Status.PASS.value,
        ),
        lambda: RunRecord(
            meta=_meta().model_dump(),
            config=RunConfig(esmini_build="1.7", dt_s=0.1, seed=1, max_time_s=30.0),
            mode="preflight",
            status=RunStatus.COMPLETED,
        ),
        lambda: ObjectiveResult(
            stub_id="o1", objective_kind="ttc", passed=True, threshold_source="rulebook.1"
        ),
        lambda: Metric(name="ttc", value=2.5, unit=Unit.S, actor_pair=("ego", "target")),
        lambda: FeedbackAction(meta=_meta().model_dump(), type="repair"),
        lambda: PersistenceRecord(
            meta=_meta().model_dump(),
            record_id="SC-1-0",
            run_id="run-1",
            object_kind="RequestSpec",
            object_hash="h",
            path="artifacts/run-1/x.json",
            lineage=LineageMap(),
        ),
        lambda: HitlRequest(kind=HitlKind.MISSING_PARAM, field_paths=["x"], question="what?"),
        lambda: LoopBudget(),
        lambda: PipelineResult(run_id="run-1", request_id="req-1", outcome="completed"),
    ],
)
def test_models_round_trip_json(model):
    obj = model()
    dumped = obj.model_dump_json()
    json.loads(dumped)  # must be valid JSON
    restored = type(obj).model_validate_json(dumped)
    assert restored == obj


# --- 7. RunConfig mandatory fields / RunRecord SKIPPED_NO_BINARY ----------


def test_run_config_mandatory_fields():
    with pytest.raises(ValidationError):
        RunConfig(dt_s=0.1)  # missing esmini_build, seed, max_time_s


def test_run_record_skipped_no_binary_constructible():
    rec = RunRecord(
        meta=_meta().model_dump(),
        config=RunConfig(esmini_build="1.7", dt_s=0.1, seed=1, max_time_s=30.0),
        mode="full",
        status=RunStatus.SKIPPED_NO_BINARY,
        stderr_tail="esmini not found on PATH",
    )
    assert rec.status is RunStatus.SKIPPED_NO_BINARY
    assert "esmini" in rec.stderr_tail


# --- 8. FeedbackAction escalate path --------------------------------------


def test_feedback_action_escalate():
    fa = FeedbackAction(
        meta=_meta().model_dump(),
        type="repair",
        escalate_to_user=True,
        escalation_reason="E08 map-topology: lane 3 not present",
        stop=False,
    )
    assert fa.escalate_to_user is True
    assert "lane 3" in fa.escalation_reason


def test_feedback_action_stop_max_iterations():
    fa = FeedbackAction(
        meta=_meta().model_dump(),
        type="explore",
        iteration=5,
        stop=True,
        stop_reason="max_iterations",
    )
    assert fa.stop is True
    assert fa.stop_reason == "max_iterations"