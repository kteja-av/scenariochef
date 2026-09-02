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

# esmini catalog locations (C3-Q5: the pinned esmini build's actual catalogs). C5 declares
# a <CatalogLocations> pointing at these on-disk assets so generated .xosc resolve against
# the real esmini Vehicle/Pedestrian catalogs, not a synthetic entry id.
_CATALOG_DIR = "assets/catalogs"
VEHICLE_CATALOG_NAME = "VehicleCatalog"
PEDESTRIAN_CATALOG_NAME = "PedestrianCatalog"
# esmini resolves <Directory path="X"/> + catalogName -> X/<catalogName>.xosc, so the
# declared directory is the folder holding the catalog file, not the catalog name.
_CATALOG_DIRECTORY_OF: dict[str, str] = {
    VEHICLE_CATALOG_NAME: f"{_CATALOG_DIR}/Vehicles",
    PEDESTRIAN_CATALOG_NAME: f"{_CATALOG_DIR}/Pedestrians",
}

# Map ScenarioChef's logical entry ids (C4/C3 inventory) to concrete esmini catalog
# entries that actually exist in the bundled VehicleCatalog/PedestrianCatalog assets.
_ESMINI_ENTRY_MAP: dict[str, str] = {
    "car_mid": "car_white",
    "truck": "truck_yellow",
    "pedestrian": "pedestrian_adult",
    # passthrough: already-real esmini entry ids are used as-is
}
_ESMINI_CATALOG_OF: dict[str, str] = {  # logical id -> esmini catalog name
    "pedestrian": PEDESTRIAN_CATALOG_NAME,
}


def _esmini_entry(bbox_ref: str) -> str:
    return _ESMINI_ENTRY_MAP.get(bbox_ref, bbox_ref)


def _esmini_catalog(bbox_ref: str) -> str:
    return _ESMINI_CATALOG_OF.get(bbox_ref, VEHICLE_CATALOG_NAME)


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
        trajectory_id=scenario_ir.meta.trajectory_id,
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
        catalog=_catalog_locations(scenario_ir),
        # OSC 1.1 (revMinor 1): the intersection where all Phase-1 features coexist.
        # Rule.greaterOrEqual needs >=1.1; ReachPositionCondition is removed in 1.2.
        osc_minor_version=1,
        creation_date=_SCENARIO_CREATION_DATE,
    )
    root = scenario.get_element()
    ET.indent(root)
    return ET.tostring(root, encoding="unicode")


def _catalog_locations(scenario_ir: ScenarioIR) -> xosc.Catalog:
    """Emit <CatalogLocations> for every catalog referenced by the scenario's actors.

    Declares the on-disk directory for each distinct esmini catalog used so the generated
    .xosc's CatalogReferences resolve at runtime (esmini locates the catalog file by the
    declared Directory). Only catalogs actually referenced are declared, keeping the
    document minimal and matching esmini's own scenario style.
    """
    catalog = xosc.Catalog()
    used: list[tuple[str, str]] = []
    for actor in scenario_ir.actors:
        entry = _esmini_entry(actor.bbox_ref)
        cat = _esmini_catalog(actor.bbox_ref)
        pair = (cat, entry)
        if pair not in used:
            used.append(pair)
            catalog.add_catalog(cat, _CATALOG_DIRECTORY_OF[cat])
    return catalog


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
    # OSC 1.0 XSD only allows equalTo|greaterThan|lessThan; greaterOrEqual is 1.1+
    # (see .harness experience XSC-0001). A >= semantic maps to greaterThan.
    rule = str(params.get("rule", "greaterOrEqual")).strip().lower()
    if rule in ("ge", ">=", "greater", "greaterorequal"):
        return xosc.Rule.greaterThan
    return xosc.Rule.equalTo


# --- Entities / Init / Storyboard -------------------------------------------


def _entity_ref(kind: str, bbox_ref: str) -> xosc.CatalogReference:
    """Catalog entry for an IRActor, mapped onto the real esmini catalogs.

    ``bbox_ref`` is the logical entry id (C4/C3): vehicles resolve to the bundled esmini
    VehicleCatalog and pedestrians to the PedestrianCatalog, translating the logical id
    to a concrete entry that exists in the esmini catalog assets (C3-Q5).
    """
    return xosc.CatalogReference(_esmini_catalog(bbox_ref), _esmini_entry(bbox_ref))


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
            xosc.SimulationTimeCondition(-0.05, xosc.Rule.greaterThan),
        )
    params = trigger.params
    if trigger.kind.value == "time":
        value = float(params.get("value", 0))
        return xosc.ValueTrigger(
            name, 0, xosc.ConditionEdge.none,
            xosc.SimulationTimeCondition(value - 0.05, xosc.Rule.greaterThan),
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
                entity=other, value=value, rule=xosc.Rule.greaterThan,
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
    if not scenario_ir.behaviors:
        # No behaviors: init-only scenario. An empty Act would fail serialization,
        # so we skip the act when there is nothing to schedule. The storyboard-level
        # stop trigger still bounds the run in real esmini.
        return xosc.StoryBoard(init=init, stoptrigger=_storyboard_stop_trigger())
    act = xosc.Act(
        name=f"act_{scenario_ir.header.request_id}",
        stoptrigger=_storyboard_stop_trigger("act_stop"),
    )
    for index, behavior in enumerate(scenario_ir.behaviors):
        act.add_maneuver_group(_build_maneuver_group(behavior, scenario_ir, overrides, index))
    story = xosc.StoryBoard(init=init, stoptrigger=_storyboard_stop_trigger())
    story.add_act(act)
    return story


# Storyboard/Act stop-triggers: an empty <StopTrigger/> is serialized when no trigger is
# set, and real esmini treats an empty StopTrigger as true-at-t=0, ending the simulation
# immediately (verified against esmini v3.7.2). Both levels therefore always declare an
# explicit SimulationTimeCondition stop so the scenario runs its full duration.
_STOP_TRIGGER_S = 30.0
_STOP_CONDITION = None  # built lazily; xosc condition objects are single-use in pyoscx


def _sim_time_stop_condition(value: float) -> xosc.SimulationTimeCondition:
    return xosc.SimulationTimeCondition(value, xosc.Rule.greaterThan)


def _storyboard_stop_trigger(name: str = "storyboard_stop") -> xosc.ValueTrigger:
    # triggeringpoint="stop" is required by pyoscx for StoryBoard/Act stop triggers.
    # An empty <StopTrigger/> is treated as true-at-t=0 by real esmini, so both levels
    # always declare an explicit simulation-time stop.
    return xosc.ValueTrigger(
        name,
        0,
        xosc.ConditionEdge.none,
        _sim_time_stop_condition(_STOP_TRIGGER_S),
        triggeringpoint="stop",
    )