"""C5 — Scenario Generation: deterministic scenariogeneration compiler.

Turns a canonical ``ScenarioIR`` into one-or-more concrete OpenSCENARIO instances.
Explicitly **no LLM** (ARCH-0001) and consumes **IR only** (C5-Q5 / ARCH-0004):
C9 applies C4 suggestions, never C5.

Two entry points:

- ``compile_ir(scenario_ir)`` — pure, deterministic core. No tracing. Same input,
  byte-identical ``.xosc`` content (C5 is deterministic).
- ``run_c5(scenario_ir, trajectory_id)`` — CX-facing thin wrapper that emits trace
  calls at the boundaries and delegates to ``compile_ir``.

Compile-time range expansion (C5-Q2): any ``Range`` appearing in an actor's initial
speed or a behavior's ``params`` is expanded into concrete instances (min / midpoint /
max). Concrete (non-range) IR yields exactly one instance. Variation enumerates the
cross-product in a deterministic ordering, capped at ``_TOTAL_INSTANCE_CAP`` instances.

K3 flags (C5-Q3) are looked up from C3 and attached to every instance; C5 never
substitutes an unknown feature. ``suggestions`` pass through untouched (DERIVED-13).
"""

from __future__ import annotations

import hashlib
import itertools
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

from scenariogeneration import xosc  # type: ignore[import-untyped]

from scenariochef import trace
from scenariochef.c3_knowledge.runtime import query_map, query_support
from scenariochef.contracts.common import FrameTag, Position, Range, TraceMeta
from scenariochef.contracts.generated_scenario import (
    GeneratedScenario,
    ParameterBinding,
    XoscArtifact,
)
from scenariochef.contracts.scenario_ir import IRBehavior, ScenarioIR

# No wall-clock in C5 output (determinism). Both the ``TraceMeta.created_at`` carried
# on every ``GeneratedScenario`` and the OpenSCENARIO ``FileHeader`` date are bound to
# this fixed sentinel, mirroring C3's deterministic-created-at policy.
_DETERMINISTIC_CREATED_AT = "2000-01-01T00:00:00+00:00"
_SCENARIO_CREATION_DATE = datetime(2000, 1, 1, tzinfo=UTC)

_PRODUCER = "C5"
_AUTHOR = "ScenarioChef C5"

# Range expansion knobs (ADR-0006 / C5-Q2 cap). A range yields at most ``_RANGE_CAP``
# concrete values per axis; the total cross-product of instances is capped at
# ``_TOTAL_INSTANCE_CAP`` instances with deterministic truncation.
_RANGE_CAP = 4
_TOTAL_INSTANCE_CAP = 8

# ``IRMap`` carries identity only (C3-Q3); the asset path lives in C3's store, so C5
# resolves it through ``query_map``. Fallback when the id is unknown.
_FALLBACK_MAP = "assets/maps/straight_2lane.xodr"

_PEDESTRIAN_WALK_MPS = 1.4  # Phase-1 cross_path walk speed (approximation reuse)


def run_c5(scenario_ir: ScenarioIR, trajectory_id: str = "REQ-0001") -> list[GeneratedScenario]:
    """CX-facing orchestration entry: trace + deterministic core compile.

    ``scenario_ir`` is a canonical, validated ``ScenarioIR`` (C4 output). Returns the
    list of concrete generated instances.
    """
    trace.emit(6, "C5", "IN", f"<ScenarioIR:{scenario_ir.header.request_id}>", trajectory_id)
    instances = compile_ir(scenario_ir)
    out_token = ",".join(inst.scenario_name for inst in instances)
    trace.emit(6, "C5", "OUT", f"<GeneratedScenario:{out_token}>", trajectory_id)
    return instances


def compile_ir(scenario_ir: ScenarioIR) -> list[GeneratedScenario]:
    """Deterministic core compile. No tracing, no wall-clock reads.

    - Entities: one ScenarioObject per IRActor via a CatalogReference.
    - Init: TeleportAction to the spawn position + AbsoluteSpeedAction for the initial
      speed.
    - Behaviors -> storyboard: one Act; per IRBehavior an Event (Priority.parallel).
    - Range expansion into concrete instances (C5-Q2).
    - K3 flags from C3 on every instance (C5-Q3); suggestions pass through untouched.
    """
    variants = _expand_ranges(scenario_ir)
    k3_flags = query_support(list(scenario_ir.feature_keys))
    instances: list[GeneratedScenario] = []
    for index, variant in enumerate(variants):
        scenario_name = f"{scenario_ir.header.request_id}-v{index}"
        content = _serialize(scenario_ir, variant["overrides"])
        instances.append(
            GeneratedScenario(
                meta=_trace_meta(scenario_ir),
                scenario_name=scenario_name,
                xosc=XoscArtifact(
                    content=content,
                    path=None,  # CX/C10 decide where to persist.
                    sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                ),
                xodr=None,
                parameter_bindings=variant["bindings"],
                variation_index=index,
                variation_count=len(variants),
                k3_flags=k3_flags,
                suggestions=list(scenario_ir.suggestions),
            )
        )
    return instances


def _trace_meta(scenario_ir: ScenarioIR) -> TraceMeta:
    return TraceMeta(
        request_id=scenario_ir.header.request_id,
        trajectory_id="REQ-0001",
        created_at=_DETERMINISTIC_CREATED_AT,
        produced_by=_PRODUCER,
    )


def _serialize(scenario_ir: ScenarioIR, overrides: dict[str, float]) -> str:
    """Assemble and serialize one OpenSCENARIO document to a deterministic string."""
    entities = _build_entities(scenario_ir)
    init = _build_init(scenario_ir, overrides)
    story = _build_storyboard(scenario_ir, overrides, init)
    scenario = xosc.Scenario(
        name=f"{scenario_ir.header.request_id}",
        author=_AUTHOR,
        parameters=xosc.ParameterDeclarations(),
        entities=entities,
        storyboard=story,
        roadnetwork=xosc.RoadNetwork(roadfile=_resolve_map_path(scenario_ir)),
        catalog=xosc.Catalog(),
        # OSC 1.1 (revMinor 1): the intersection where all Phase-1 features coexist.
        # Rule.greaterOrEqual needs >=1.1; ReachPositionCondition is removed in 1.2.
        osc_minor_version=1,
        creation_date=_SCENARIO_CREATION_DATE,
    )
    root = scenario.get_element()
    ET.indent(root)
    return ET.tostring(root, encoding="unicode")


# --- Variation / range expansion (C5-Q2) -----------------------------------


def _collect_ranges(scenario_ir: ScenarioIR) -> list[dict[str, Any]]:
    """Ranges anywhere C5 must synthesize concrete values.

    Detected at the object level: ``IRActor.initial_speed_mps`` is typed ``float`` and
    behavior ``params`` are typed ``float|int|str`` by the frozen contract, so C5 looks
    for ``Range`` instances via ``isinstance`` rather than the declared type — this
    matches the richer ``ActorIntent.initial_speed_mps: float | Range`` intent C4 is
    expected to preserve and is forward-compatible.
    """
    found: list[dict[str, Any]] = []
    for i, actor in enumerate(scenario_ir.actors):
        if isinstance(actor.initial_speed_mps, Range):
            found.append(
                {
                    "ir_path": f"actors[{i}].initial_speed_mps",
                    "param": f"{actor.name}.initial_speed_mps",
                    "range": actor.initial_speed_mps,
                    "kind": "actor_speed",
                    "actor_index": i,
                }
            )
    for i, behavior in enumerate(scenario_ir.behaviors):
        for key, value in behavior.params.items():
            if isinstance(value, Range):
                found.append(
                    {
                        "ir_path": f"behaviors[{i}].params.{key}",
                        "param": f"{behavior.actor}.{behavior.action.value}.{key}",
                        "range": value,
                        "kind": "behavior_param",
                        "behavior_index": i,
                        "param_key": key,
                    }
                )
    return found


def _range_values(value: Range) -> list[float]:
    """Concrete deterministic values for one range: min, midpoint, max.

    Always includes both bounds plus the midpoint, keeping the count (3) at or below the
    ``_RANGE_CAP`` (4) upper bound while yielding clean, useful samples.
    """
    lo, hi = value.min, value.max
    if lo == hi:
        return [lo]
    return [lo, (lo + hi) / 2.0, hi]


def _expand_ranges(scenario_ir: ScenarioIR) -> list[dict[str, Any]]:
    """Generate concrete variants in a deterministic product order.

    Each variant carries ``overrides`` (ir_path -> concrete value) and the list of
    ``ParameterBinding`` records describing that choice. Concrete IR -> exactly one
    variant. The product is truncated deterministically to ``_TOTAL_INSTANCE_CAP``.
    """
    ranges = _collect_ranges(scenario_ir)
    if not ranges:
        return [{"overrides": {}, "bindings": []}]
    choices = [_range_values(r["range"]) for r in ranges]
    variants: list[dict[str, Any]] = []
    for combination in itertools.product(*choices):
        overrides: dict[str, float] = {}
        bindings: list[ParameterBinding] = []
        for spec, concrete in zip(ranges, combination):
            path = spec["ir_path"]
            overrides[path] = concrete
            bindings.append(
                ParameterBinding(
                    param=spec["param"],
                    value=concrete,
                    source_range=spec["range"],
                    ir_path=path,
                )
            )
        variants.append({"overrides": overrides, "bindings": bindings})
        if len(variants) >= _TOTAL_INSTANCE_CAP:
            break
    return variants


# --- OpenSCENARIO assembly -------------------------------------------------


def _resolve_map_path(scenario_ir: ScenarioIR) -> str:
    """Resolve the .xodr path from the IR map identity (C3 query), else fallback."""
    asset = query_map(scenario_ir.map.map_asset_id)
    if asset is not None and asset.path:
        return asset.path
    return _FALLBACK_MAP


def _lane_position(
    road_id: int | None, lane_id: int | None, s: float, t: float | None
) -> xosc.LanePosition:
    return xosc.LanePosition(
        s=float(s),
        offset=float(t) if t is not None else 0.0,
        lane_id=str(lane_id),
        road_id=str(road_id),
    )


def _spawn_position(spawn: Position) -> xosc.LanePosition | xosc.WorldPosition:
    if spawn.frame is FrameTag.LANE_RELATIVE:
        return _lane_position(spawn.road_id, spawn.lane_id, spawn.s_m or 0.0, spawn.t_m)
    if spawn.frame is FrameTag.CARTESIAN:
        return xosc.WorldPosition(x=spawn.x_m or 0.0, y=spawn.y_m or 0.0, z=spawn.z_m)
    raise ValueError(f"Unsupported spawn frame for C5: {spawn.frame!r}")


def _public_lane_position(params: dict[str, Any]) -> xosc.LanePosition:
    """A LanePosition built from a maneuver/trigger ``params`` dict (lane ids as strings)."""
    return xosc.LanePosition(
        s=float(params.get("s_m", params.get("s", 0.0))),
        offset=float(params.get("t_m", params.get("t", 0.0))),
        lane_id=str(params.get("lane_id", params.get("target_lane", 0))),
        road_id=str(params.get("road_id", 1)),
    )


def _rule(params: dict[str, Any]) -> xosc.Rule:
    rule = str(params.get("rule", "greaterOrEqual")).strip().lower()
    if rule in ("ge", ">=", "greater", "greaterorequal"):
        return xosc.Rule.greaterOrEqual
    return xosc.Rule.equalTo


# --- Entities / Init / Storyboard -------------------------------------------


def _entity_ref(kind: str, bbox_ref: str) -> xosc.CatalogReference:
    """Catalog entry for an IRActor: vehicles vs pedestrians catalog mapping."""
    if kind.lower() == "pedestrian":
        return xosc.CatalogReference("Catalogs/Pedestrians", "pedestrian")
    return xosc.CatalogReference("Catalogs/Vehicles", bbox_ref)


def _build_entities(scenario_ir: ScenarioIR) -> xosc.Entities:
    entities = xosc.Entities()
    for actor in scenario_ir.actors:
        entities.add_scenario_object(
            actor.name, _entity_ref(actor.kind, actor.bbox_ref)
        )
    return entities


def _actor_initial_speed(
    scenario_ir: ScenarioIR, actor_name: str, overrides: dict[str, float]
) -> float:
    for i, actor in enumerate(scenario_ir.actors):
        if actor.name == actor_name:
            path = f"actors[{i}].initial_speed_mps"
            value = overrides.get(path, actor.initial_speed_mps)
            return float(value if not isinstance(value, Range) else value.min)
    return 0.0


def _build_init(scenario_ir: ScenarioIR, overrides: dict[str, float]) -> xosc.Init:
    init = xosc.Init()
    for i, actor in enumerate(scenario_ir.actors):
        path = f"actors[{i}].initial_speed_mps"
        speed = overrides.get(path, actor.initial_speed_mps)
        if isinstance(speed, Range):
            # Un-resolved Range that somehow escaped expansion: pin to the minimum
            # rather than emitting a non-numeric speed into the action.
            speed = speed.min
        init.add_init_action(actor.name, xosc.TeleportAction(_spawn_position(actor.spawn)))
        init.add_init_action(
            actor.name,
            xosc.AbsoluteSpeedAction(
                float(speed),
                xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0),
            ),
        )
    return init


def _trigger_for(
    behavior: IRBehavior,
) -> xosc.ValueTrigger | xosc.EntityTrigger:
    trigger = behavior.trigger
    name = f"start_{behavior.actor}_{behavior.action.value}"
    if trigger is None:
        return xosc.ValueTrigger(
            name, 0, xosc.ConditionEdge.none,
            xosc.SimulationTimeCondition(0, xosc.Rule.greaterOrEqual),
        )
    params = trigger.params
    if trigger.kind.value == "time":
        value = float(params.get("value", 0))
        return xosc.ValueTrigger(
            name, 0, xosc.ConditionEdge.none,
            xosc.SimulationTimeCondition(value, xosc.Rule.greaterOrEqual),
        )
    if trigger.kind.value == "speed_headway":
        value = float(params.get("value", 0))
        return xosc.ValueTrigger(
            name, 0, xosc.ConditionEdge.none, xosc.SpeedCondition(value, _rule(params))
        )
    if trigger.kind.value == "reach_position":
        return xosc.EntityTrigger(
            name, 0, xosc.ConditionEdge.none,
            xosc.ReachPositionCondition(_public_lane_position(params), 1.0),
            triggerentity=behavior.actor,
        )
    if trigger.kind.value == "time_headway":
        other = str(params.get("other", params.get("reference_entity", "")))
        value = float(params.get("value", 0))
        return xosc.EntityTrigger(
            name, 0, xosc.ConditionEdge.none,
            xosc.TimeHeadwayCondition(
                entity=other, value=value, rule=xosc.Rule.greaterOrEqual,
                alongroute=True, freespace=True,
            ),
            triggerentity=behavior.actor,
        )
    raise ValueError(f"Unsupported trigger kind for C5: {trigger.kind!r}")


def _action_for(
    behavior: IRBehavior,
    scenario_ir: ScenarioIR,
    overrides: dict[str, float],
    scoped_params: dict[str, Any] | None = None,
) -> xosc.AbsoluteSpeedAction | xosc.AbsoluteLaneChangeAction | xosc.TeleportAction:
    params = scoped_params if scoped_params is not None else behavior.params
    actor_speed = _actor_initial_speed(scenario_ir, behavior.actor, overrides)

    def _speed(target: float) -> xosc.AbsoluteSpeedAction:
        return xosc.AbsoluteSpeedAction(
            target,
            xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 1),
        )

    if behavior.action.value in ("speed_change", "brake"):
        return _speed(float(params.get("target_speed", actor_speed)))
    if behavior.action.value in ("lane_change", "cut_in"):
        lane = int(params.get("target_lane", params.get("lane", 0)))
        return xosc.AbsoluteLaneChangeAction(
            lane,
            xosc.TransitionDynamics(
                xosc.DynamicsShapes.sinusoidal, xosc.DynamicsDimension.time, 2
            ),
        )
    if behavior.action.value == "follow":
        # Phase-1 approximation: drive the follower toward the target speed. A true
        # FollowingController is out of Phase-1 scope (C5-Q4).
        return _speed(float(params.get("target_speed", actor_speed)))
    if behavior.action.value == "cross_path":
        # Pedestrian walk-speed approximation for crossing (Phase-1).
        return _speed(float(params.get("target_speed", _PEDESTRIAN_WALK_MPS)))
    if behavior.action.value == "teleport":
        return xosc.TeleportAction(_public_lane_position(params))
    raise ValueError(f"Unsupported action type for C5: {behavior.action!r}")


def _behavior_param_overrides(overrides: dict[str, float], behavior_index: int) -> dict[str, Any]:
    """Concrete values for a single behavior's ranged params, keyed by param name."""
    prefix = f"behaviors[{behavior_index}].params."
    return {
        path[len(prefix):]: value
        for path, value in overrides.items()
        if path.startswith(prefix)
    }


def _build_maneuver_group(
    behavior: IRBehavior,
    scenario_ir: ScenarioIR,
    overrides: dict[str, float],
    behavior_index: int,
) -> xosc.ManeuverGroup:
    scoped = dict(behavior.params)
    scoped.update(_behavior_param_overrides(overrides, behavior_index))
    action = _action_for(behavior, scenario_ir, overrides, scoped)
    event = xosc.Event(
        name=f"event_{behavior.actor}_{behavior.action.value}", priority=xosc.Priority.parallel
    )
    event.add_action(f"act_{behavior.actor}_{behavior.action.value}", action)
    event.add_trigger(_trigger_for(behavior))
    maneuver = xosc.Maneuver(name=f"maneuver_{behavior.actor}_{behavior.action.value}")
    maneuver.add_event(event)
    group = xosc.ManeuverGroup(name=f"mg_{behavior.actor}_{behavior.action.value}")
    group.add_actor(behavior.actor)
    group.add_maneuver(maneuver)
    return group


def _build_storyboard(
    scenario_ir: ScenarioIR, overrides: dict[str, float], init: xosc.Init
) -> xosc.StoryBoard:
    story = xosc.StoryBoard(init=init)
    if not scenario_ir.behaviors:
        # No behaviors: init-only scenario. An empty Act would fail serialization,
        # so we skip the act when there is nothing to schedule.
        return story
    act = xosc.Act(name=f"act_{scenario_ir.header.request_id}")
    for index, behavior in enumerate(scenario_ir.behaviors):
        act.add_maneuver_group(_build_maneuver_group(behavior, scenario_ir, overrides, index))
    story.add_act(act)
    return story