"""C5 — Scenario Generation tests.

Covers the required compile behaviors: deterministic core compile, cross-boundary
range expansion (C5-Q2), K3-flag attachment (C5-Q3), suggestions passthrough
(DERIVED-13), determinism, instance capping, and lane-id-as-string serialization.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from scenariochef.c5_generation.runtime import compile_ir, run_c5
from scenariochef.contracts.common import (
    FrameTag,
    Position,
    Range,
    SupportLevel,
    TraceMeta,
    Unit,
)
from scenariochef.contracts.generated_scenario import K3Flag
from scenariochef.contracts.intent_spec import ActionType, TriggerIntent, TriggerKind
from scenariochef.contracts.scenario_ir import (
    IRActor,
    IRBehavior,
    IRHeader,
    IRMap,
    IRSuggestion,
    ScenarioIR,
)

SHA256_PLACEHOLDER = "0" * 64


def _meta(request_id: str = "REQ-0001") -> TraceMeta:
    return TraceMeta(
        request_id=request_id, trajectory_id=request_id, produced_by="test-c5"
    )


def _header(request_id: str = "REQ-0001") -> IRHeader:
    return IRHeader(request_id=request_id, intent_spec_hash="abc", esmini_pin="esmini-0.10")


def _map() -> IRMap:
    return IRMap(map_asset_id="straight_2lane", sha256=SHA256_PLACEHOLDER)


def _spawn(lane: int, s: float) -> Position:
    return Position(frame=FrameTag.LANE_RELATIVE, road_id=1, lane_id=lane, s_m=s)


def _actor(name: str, lane: int, s: float, speed: float | Range) -> IRActor:
    return IRActor.model_construct(
        name=name,
        kind="vehicle",
        bbox_ref="car_mid",
        spawn=_spawn(lane, s),
        initial_speed_mps=speed,
    )


def _follow_ir(**kwargs) -> ScenarioIR:
    """A 2-actor follow IR: Ego follows Lead at 15 m/s, triggered at 5 s."""
    ego = _actor("Ego", -1, 0.0, 15.0)
    lead = _actor("Lead", -1, 20.0, 15.0)
    trigger = TriggerIntent(kind=TriggerKind.TIME, params={"value": 5})
    follow = IRBehavior(
        actor="Ego",
        action=ActionType.FOLLOW,
        params={"target_speed": 15.0},
        trigger=trigger,
    )
    return ScenarioIR(
        meta=kwargs.get("meta", _meta()),
        header=kwargs.get("header", _header()),
        map=kwargs.get("map", _map()),
        actors=[ego, lead],
        behaviors=[follow],
        feature_keys=["osc.action.SpeedChange"],
        suggestions=kwargs.get("suggestions", []),
    )


def test_compile_follow_ir_single_instance_and_speed_action():
    ir = _follow_ir()
    instances = compile_ir(ir)
    assert len(instances) == 1
    instance = instances[0]
    content = instance.xosc.content
    # XML must be well-formed.
    assert ET.fromstring(content).tag == "OpenSCENARIO"
    # scenariogeneration serializes the AbsoluteSpeedAction for follow as
    # SpeedAction/AbsoluteTargetSpeed.
    assert "AbsoluteTargetSpeed value=\"15.0\"" in content
    # Road network resolved from C3 map identity.
    assert 'filepath="assets/maps/straight_2lane.xodr"' in content
    # Concrete IR -> no parameter bindings.
    assert instance.parameter_bindings == []
    assert instance.variation_index == 0
    assert instance.variation_count == 1
    # K3 support flag attached from C3.
    assert instance.k3_flags == [
        K3Flag(feature_key="osc.action.SpeedChange", support=SupportLevel.SUPPORTS)
    ]


def test_range_expansion_deterministic_values_and_binding_records():
    ir = _follow_ir()
    ir = ScenarioIR(
        meta=ir.meta,
        header=ir.header,
        map=ir.map,
        actors=[_actor("Ego", -1, 0.0, Range(min=10, max=20, unit=Unit.MPS))],
        behaviors=ir.behaviors,
        feature_keys=ir.feature_keys,
    )
    instances = compile_ir(ir)
    assert [inst.variation_index for inst in instances] == [0, 1, 2]
    assert [inst.variation_count for inst in instances] == [3, 3, 3]
    concrete = []
    for inst in instances:
        assert len(inst.parameter_bindings) == 1
        binding = inst.parameter_bindings[0]
        assert binding.source_range is not None
        assert binding.source_range.min == 10.0 and binding.source_range.max == 20.0
        assert binding.ir_path == "actors[0].initial_speed_mps"
        concrete.append(binding.value)
    assert set(concrete) == {10.0, 15.0, 20.0}


def test_teleport_behavior_emits_teleport_action_and_unknown_k3():
    ego = _actor("Ego", -1, 0.0, 15.0)
    teleport = IRBehavior(
        actor="Ego",
        action=ActionType.TELEPORT,
        params={"s_m": 50.0, "lane_id": -1, "road_id": 1},
    )
    ir = ScenarioIR(
        meta=_meta(),
        header=_header(),
        map=_map(),
        actors=[ego],
        behaviors=[teleport],
        feature_keys=["osc.action.Teleport", "osc.action.SpeedChange"],
    )
    instances = compile_ir(ir)
    content = instances[0].xosc.content
    assert "TeleportAction" in content
    flags = {flag.feature_key: flag.support for flag in instances[0].k3_flags}
    assert flags["osc.action.Teleport"] == SupportLevel.UNKNOWN
    assert flags["osc.action.SpeedChange"] == SupportLevel.SUPPORTS


def test_suggestions_pass_through_untouched():
    suggestion = IRSuggestion(code="C", message="note", field_path="actors[0]")
    ir = _follow_ir(suggestions=[suggestion])
    instances = compile_ir(ir)
    assert instances
    for instance in instances:
        assert instance.suggestions == [suggestion]


def test_compile_twice_is_byte_identical_deterministic():
    ir = _follow_ir()
    first = compile_ir(ir)
    second = compile_ir(ir)
    assert [inst.xosc.content for inst in first] == [
        inst.xosc.content for inst in second
    ]
    assert [inst.xosc.sha256 for inst in first] == [
        inst.xosc.sha256 for inst in second
    ]


def test_instance_count_capped_at_eight():
    ego = _actor("Ego", -1, 0.0, Range(min=0, max=100, unit=Unit.MPS))
    lead = _actor("Lead", -1, 20.0, Range(min=0, max=50, unit=Unit.MPS))
    behavior = IRBehavior(
        actor="Ego",
        action=ActionType.FOLLOW,
        params={"target_speed": 10.0},
        trigger=TriggerIntent(kind=TriggerKind.TIME, params={"value": 1}),
    )
    ir = ScenarioIR(
        meta=_meta(),
        header=_header(),
        map=_map(),
        actors=[ego, lead],
        behaviors=[behavior],
    )
    instances = compile_ir(ir)
    # Raw product 3x3=9 would exceed the 8-instance cap.
    assert len(instances) <= 8
    assert [inst.variation_count for inst in instances] == [len(instances)] * len(instances)


def test_lane_ids_serialize_as_strings():
    instances = compile_ir(_follow_ir())
    content = instances[0].xosc.content
    assert 'laneId="-1"' in content
    assert 'roadId="1"' in content


def test_time_headway_and_reach_position_triggers():
    ego = _actor("Ego", -1, 0.0, 15.0)
    lead = _actor("Lead", -1, 20.0, 15.0)
    headway = IRBehavior(
        actor="Ego",
        action=ActionType.BRAKE,
        params={"target_speed": 5.0},
        trigger=TriggerIntent(
            kind=TriggerKind.TIME_HEADWAY, params={"value": 2.0, "other": "Lead"}
        ),
    )
    reach = IRBehavior(
        actor="Ego",
        action=ActionType.LANE_CHANGE,
        params={"target_lane": 1},
        trigger=TriggerIntent(
            kind=TriggerKind.REACH_POSITION, params={"s_m": 50.0, "lane_id": -1, "road_id": 1}
        ),
    )
    ir = ScenarioIR(
        meta=_meta(),
        header=_header(),
        map=_map(),
        actors=[ego, lead],
        behaviors=[headway, reach],
    )
    content = compile_ir(ir)[0].xosc.content
    assert "TimeHeadwayCondition" in content
    assert "ReachPositionCondition" in content
    assert "LaneChangeAction" in content


def test_run_c5_returns_instances_and_emits_trace():
    instances = run_c5(_follow_ir(), trajectory_id="REQ-0001")
    assert isinstance(instances, list)
    assert instances[0].scenario_name == "REQ-0001-v0"