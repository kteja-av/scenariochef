"""C4 — Scenario IR: deterministic compile of IntentSpec -> ScenarioIR.

Covers: happy-path compile with feature_keys/map identity/catalog refs (C4-Q1,
C3-Q5/Q3, catalog refs), initial-speed range preservation (C4-Q4), E08 suggestions
that never touch canonical fields (C4-Q5, DERIVED-10, ARCH-0002), teleport feature
key, esmini pin from the C3 store, the DERIVED-3 ack gate at IntentSpec construction
(and C4's trust in the validated contract), and byte-identical objective passthrough
(C4-Q3).
"""

from __future__ import annotations

import io

import pytest
from pydantic import ValidationError

from scenariochef import trace as trace_module
from scenariochef.c3_knowledge import ESMINI_BUILD_PIN
from scenariochef.c3_knowledge.store import MAP_SHA256_PLACEHOLDER
from scenariochef.c4_ir.runtime import build_ir, run_c4
from scenariochef.contracts import (
    ActionType,
    ActorIntent,
    ActorRole,
    ConstraintIntent,
    FrameTag,
    IntentSpec,
    ManeuverIntent,
    ObjectiveKind,
    ObjectiveStub,
    Position,
    Range,
    SlotProvenance,
    TraceMeta,
    TriggerIntent,
    TriggerKind,
    Unit,
    semantic_hash,
)
from scenariochef.trace import set_log


def _meta(
    request_id: str = "REQ-0001", trajectory_id: str = "t-1"
) -> TraceMeta:
    return TraceMeta(
        request_id=request_id,
        trajectory_id=trajectory_id,
        produced_by="test",
    )


def _intent(
    *,
    actors: list[ActorIntent] | None = None,
    maneuvers: list[ManeuverIntent] | None = None,
    triggers: list[TriggerIntent] | None = None,
    constraints: list[ConstraintIntent] | None = None,
    objectives: list[ObjectiveStub] | None = None,
    meta: TraceMeta | None = None,
    confidence: float = 0.9,
) -> IntentSpec:
    return IntentSpec(
        meta=(meta or _meta()).model_dump(),
        actors=actors or [],
        maneuvers=maneuvers or [],
        triggers=triggers or [],
        constraints=constraints or [],
        objectives=objectives or [],
        confidence=confidence,
    )


def _actor(
    name: str,
    speed: float | Range,
    *,
    kind: str = "vehicle",
    role: ActorRole = ActorRole.TARGET,
    x: float = 0.0,
    y: float = 0.0,
) -> ActorIntent:
    return ActorIntent(
        name=name,
        kind=kind,
        role=role,
        initial_position=Position(frame=FrameTag.CARTESIAN, x_m=x, y_m=y),
        initial_speed_mps=speed,
    )


# --- happy path ------------------------------------------------------------


def test_happy_path_compile_with_follow_and_trigger():
    """2 actors, a follow maneuver plus a trigger -> IR with feature_keys, map identity,
    catalog refs, esmini pin, and request id."""
    spec = _intent(
        actors=[
            _actor("ego", 10.0, role=ActorRole.EGO),
            _actor("target", 5.0, x=30.0),
        ],
        maneuvers=[
            ManeuverIntent(
                actor="ego",
                action=ActionType.FOLLOW,
                params={"target": "target", "headway_s": 2.0},
            )
        ],
        triggers=[
            TriggerIntent(kind=TriggerKind.TIME, params={"sim_time_s": 1.0}),
        ],
        meta=_meta(request_id="REQ-0042"),
    )

    ir = build_ir(spec)

    # Header: request id from intent meta, semantic hash of the intent, C3 esmini pin.
    assert ir.header.request_id == "REQ-0042"
    assert ir.header.intent_spec_hash == semantic_hash(spec)
    assert ir.header.esmini_pin == ESMINI_BUILD_PIN

    # Feature keys: the follow action + the time trigger.
    assert ir.feature_keys == ["osc.action.Following", "osc.trigger.SimulationTime"]

    # Map identity from the C3 store (default map).
    assert ir.map.map_asset_id == "straight_2lane"
    assert ir.map.sha256 == MAP_SHA256_PLACEHOLDER

    # Catalog refs by kind.
    assert ir.actors[0].bbox_ref == "car_mid"
    assert ir.actors[1].bbox_ref == "car_mid"

    # Behavior carries its trigger.
    behavior = ir.behaviors[0]
    assert behavior.actor == "ego"
    assert behavior.action is ActionType.FOLLOW
    assert behavior.trigger is not None
    assert behavior.trigger.kind is TriggerKind.TIME

    # Positions pass through frame-tagged.
    assert ir.actors[0].spawn.frame is FrameTag.CARTESIAN


def test_catalog_refs_pedestrian_and_truck():
    spec = _intent(
        actors=[
            _actor("walker", 1.0, kind="pedestrian"),
            _actor("freight_truck", 5.0, role=ActorRole.EGO),
        ]
    )
    ir = build_ir(spec)
    refs = {a.name: a.bbox_ref for a in ir.actors}
    assert refs["walker"] == "pedestrian"
    assert refs["freight_truck"] == "truck"


# --- range preservation (C4-Q4) -------------------------------------------


def test_range_initial_speed_preserved_as_constraint():
    """A Range actor speed keeps [min,max] in an IR constraint and a representative
    speed on the actor."""
    spec = _intent(actors=[_actor("ego", Range(min=5.0, max=10.0, unit=Unit.MPS))])
    ir = build_ir(spec)

    assert ir.actors[0].initial_speed_mps == 7.5  # midpoint representative

    constraint = next(c for c in ir.constraints if c.name == "ego_initial_speed")
    assert isinstance(constraint.value, Range)
    assert constraint.value.min == 5.0
    assert constraint.value.max == 10.0
    assert constraint.value.unit is Unit.MPS


def test_float_initial_speed_concrete():
    spec = _intent(actors=[_actor("ego", 10.0)])
    ir = build_ir(spec)
    assert ir.actors[0].initial_speed_mps == 10.0
    assert "ego_initial_speed" not in {c.name for c in ir.constraints}


# --- E08 suggestions never touch canonical fields (DERIVED-10) -------------


def test_e08_suggestion_for_out_of_range_lane_keeps_canonical_target():
    spec = _intent(
        maneuvers=[
            ManeuverIntent(
                actor="ego",
                action=ActionType.LANE_CHANGE,
                params={"target_lane": 3},
            )
        ]
    )
    ir = build_ir(spec)

    suggestions = [s for s in ir.suggestions if s.code == "E08_LANE_OUT_OF_RANGE"]
    assert len(suggestions) == 1
    assert suggestions[0].proposed_value == 1
    assert "lane 3 does not exist" in suggestions[0].message

    # Canonical field is untouched (ARCH-0002 / C2-Q3 / DERIVED-10).
    assert ir.behaviors[0].params["target_lane"] == 3


def test_e08_suggestion_negative_lane_sign_matched():
    spec = _intent(
        maneuvers=[
            ManeuverIntent(
                actor="ego",
                action=ActionType.LANE_CHANGE,
                params={"target_lane": -2},
            )
        ]
    )
    ir = build_ir(spec)
    suggestions = [s for s in ir.suggestions if s.code == "E08_LANE_OUT_OF_RANGE"]
    assert len(suggestions) == 1
    assert suggestions[0].proposed_value == -1


def test_in_range_lane_no_e08_suggestion():
    spec = _intent(
        maneuvers=[
            ManeuverIntent(
                actor="ego",
                action=ActionType.LANE_CHANGE,
                params={"target_lane": 1},
            )
        ]
    )
    ir = build_ir(spec)
    assert all(s.code != "E08_LANE_OUT_OF_RANGE" for s in ir.suggestions)


# --- teleport feature key --------------------------------------------------


def test_teleport_maneuver_feature_key():
    spec = _intent(
        maneuvers=[
            ManeuverIntent(
                actor="target",
                action=ActionType.TELEPORT,
                params={"target_x_m": 50.0, "target_y_m": 0.0},
            )
        ]
    )
    ir = build_ir(spec)
    assert "osc.action.Teleport" in ir.feature_keys


def test_cut_in_produces_two_feature_keys():
    spec = _intent(
        maneuvers=[
            ManeuverIntent(
                actor="target",
                action=ActionType.CUT_IN,
                params={"target_lane": -1},
            )
        ]
    )
    ir = build_ir(spec)
    assert "osc.action.LaneChange" in ir.feature_keys
    assert "osc.action.SpeedChange" in ir.feature_keys


# --- DERIVED-3 ack gate (ARCH-0004) ---------------------------------------


def test_c3_default_without_both_acks_rejected_at_construction():
    """The gate lives at IntentSpec construction; an unacked c3_default slot raises a
    ValidationError before C4 ever runs."""
    with pytest.raises(ValidationError):
        ActorIntent(
            name="ego",
            kind="vehicle",
            role=ActorRole.EGO,
            initial_position=Position(frame=FrameTag.CARTESIAN, x_m=0.0, y_m=0.0),
            initial_speed_mps=Range(min=5.0, max=10.0, unit=Unit.MPS),
            slot=SlotProvenance(
                source="c3_default", accepted_by_c1=True, accepted_by_c2=False
            ),
        )
    # build_ir trusts the validated contract: unacked c3_default cannot be constructed,
    # so there is nothing for C4 to reject. The defensive re-check in C4 (ARCH-0004)
    # exists but is unreachable through public API.


def test_c3_default_with_both_acks_binds_range():
    """The positive path: an acked c3_default range still binds into the IR."""
    actor = ActorIntent(
        name="ego",
        kind="vehicle",
        role=ActorRole.EGO,
        initial_position=Position(frame=FrameTag.CARTESIAN, x_m=0.0, y_m=0.0),
        initial_speed_mps=Range(min=5.0, max=10.0, unit=Unit.MPS),
        slot=SlotProvenance(
            source="c3_default", accepted_by_c1=True, accepted_by_c2=True
        ),
    )
    ir = build_ir(_intent(actors=[actor]))
    assert "ego_initial_speed" in {c.name for c in ir.constraints}


# --- objectives pass through byte-identical (C4-Q3) ------------------------


def test_objectives_pass_through_byte_identical():
    objectives = [
        ObjectiveStub(
            id="o1", kind=ObjectiveKind.TTC, description="ttc>2", params={"min_ttc_s": 2.0}
        ),
        ObjectiveStub(id="o2", kind=ObjectiveKind.COMPLETION, description="reach end"),
    ]
    a = _intent(objectives=objectives, meta=_meta(request_id="REQ-1"))
    b = _intent(objectives=objectives, meta=_meta(request_id="REQ-2"))

    ira = build_ir(a)
    irb = build_ir(b)

    # Byte-identical semantic content of the stub lists across two different intents
    # (each stub hashed semantically — meta is dropped, so identity is not time-bound).
    assert semantic_hash(ira) != semantic_hash(irb)  # different header/request
    assert [semantic_hash(o) for o in ira.objectives] == [
        semantic_hash(o) for o in irb.objectives
    ]
    assert [o.id for o in ira.objectives] == ["o1", "o2"]
    assert ira.objectives[0].kind is ObjectiveKind.TTC


# --- run_c4 entry point + trace -------------------------------------------


def test_run_c4_returns_ir_and_emits_trace():
    spec = _intent()
    original_stream = trace_module._stream
    try:
        buf = io.StringIO()
        set_log(buf)
        ir = run_c4(spec, trajectory_id="REQ-0001")
        out = buf.getvalue()
    finally:
        set_log(original_stream)

    assert ir.header.request_id == "REQ-0001"
    assert "<IntentSpec:" in out
    assert "<ScenarioIR:" in out
    assert "C4  OUT" in out or "C4 OUT" in out