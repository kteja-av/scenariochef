"""C4 — Scenario Representation: Scenic-like intermediate representation (IR).

Deterministic compiler from a validated ``IntentSpec`` to the canonical ``ScenarioIR``
(frozen). No LLM (ARCH-0001). Positions are passed through frame-tagged (C4-Q2);
objectives pass through unchanged (C4-Q3); initial-speed intervals are preserved as
range constraints (C4-Q4); repair hints ride along on ``suggestions`` and never mutate
the canonical fields (C4-Q5, DERIVED-10, ARCH-0002). The esmini pin comes from the C3
K3 matrix (C3-Q5), and map identity only from the C3 store (never topology — C3-Q3).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from scenariochef import trace

from ..c3_knowledge.store import (
    ESMINI_BUILD_PIN,
    MAP_SHA256_PLACEHOLDER,
    get_store,
)
from ..contracts.common import Range, SlotProvenance, TraceMeta, semantic_hash
from ..contracts.intent_spec import (
    ActionType,
    ActorIntent,
    IntentSpec,
    ManeuverIntent,
    TriggerIntent,
    TriggerKind,
)
from ..contracts.scenario_ir import (
    IRActor,
    IRBehavior,
    IRConstraint,
    IRHeader,
    IRMap,
    IRSuggestion,
    ScenarioIR,
)

if TYPE_CHECKING:
    from ..contracts.evidence_bundle import EvidenceBundle

_PRODUCER = "C4"
_DEFAULT_MAP = "straight_2lane"

# Keyword rules for automatic map selection when the request names no map explicitly
# (C1-Q2: an explicit map_id always wins). Each rule maps a keyword in the request text
# to a C3-registered map id (assets/scenario_db/esmini-maps/, see knowledge.yaml).
# First matching rule in declaration order wins; deterministic.
_MAP_SELECTION_RULES: tuple[tuple[str, str], ...] = (
    ("intersection", "esmini_crossing_8"),
    ("crossing", "esmini_crossing_8"),
    ("junction", "esmini_crossing_8"),
    ("merge", "esmini_highway_merge"),
    ("highway", "esmini_highway_merge"),
    ("motorway", "esmini_highway_merge"),
    ("parking", "esmini_parking_lot"),
    ("overtake", "esmini_two_plus_one"),
    ("curve", "esmini_curve"),
    ("bend", "esmini_curve"),
)
# Lane span of the default map (lanes -1..1); the E08 lane-existence check is a
# topology claim and so only valid for the known default map (C3-Q3 stays intact:
# C3 never answers topology; C4 emits the suggestion only for its known default map).
_DEFAULT_MAP_LANE_MIN = -1
_DEFAULT_MAP_LANE_MAX = 1

# TraceMeta.created_at is part of the contract (defaults to the wall-clock instant,
# common.py). C4 must be deterministic (no wall-clock reads in logic), so the IR's
# created_at is bound to this fixed sentinel, matching C3; repeated calls are
# byte-identical and reproducible.
_DETERMINISTIC_CREATED_AT = "2000-01-01T00:00:00+00:00"

# ActionType -> OSC feature keys the behavior relies on (drives C3 K3 lookup + C6 S6).
_ACTION_FEATURES: dict[ActionType, tuple[str, ...]] = {
    ActionType.SPEED_CHANGE: ("osc.action.SpeedChange",),
    ActionType.LANE_CHANGE: ("osc.action.LaneChange",),
    ActionType.FOLLOW: ("osc.action.Following",),
    ActionType.BRAKE: ("osc.action.SpeedChange",),
    ActionType.CUT_IN: ("osc.action.LaneChange", "osc.action.SpeedChange"),
    ActionType.CROSS_PATH: ("osc.action.SpeedChange",),
    ActionType.TELEPORT: ("osc.action.Teleport",),
}

# TriggerKind -> OSC trigger key the behavior's trigger relies on.
_TRIGGER_FEATURES: dict[TriggerKind, str] = {
    TriggerKind.TIME: "osc.trigger.SimulationTime",
    TriggerKind.SPEED_HEADWAY: "osc.trigger.SpeedCondition",
    TriggerKind.REACH_POSITION: "osc.trigger.ReachPosition",
    TriggerKind.TIME_HEADWAY: "osc.trigger.TimeHeadway",
}

_E08_CODE = "E08_LANE_OUT_OF_RANGE"


def _trace_meta(intent_spec: IntentSpec) -> TraceMeta:
    """Deterministic trace header; request id from the intent (fallback handled by caller)."""
    return TraceMeta(
        request_id=intent_spec.meta.request_id,
        trajectory_id=intent_spec.meta.trajectory_id,
        created_at=_DETERMINISTIC_CREATED_AT,
        produced_by=_PRODUCER,
    )


def _require_acked(provenance: SlotProvenance, context: str) -> None:
    """DERIVED-3 / ARCH-0004: refuse a c3_default-derived value missing either C1/C2 ack.

    The IntentSpec validator already rejects unacked c3_default slots at construction;
    this is defense in depth for when C4 binds a c3_default-derived range into an
    IRConstraint (the range's origin is the actor/maneuver slot).
    """
    if provenance.source == "c3_default" and not (
        provenance.accepted_by_c1 and provenance.accepted_by_c2
    ):
        raise ValueError(
            f"{context}: c3_default requires accepted_by_c1=True and accepted_by_c2=True"
        )


def _map_topology_for(map_id: str) -> dict[int, float] | None:
    """Road lengths for the selected map (id -> length in meters), or None.

    Reads the C3-registered map asset path. This is generation input (binding a
    concrete spawn s), not a topology judgment — C6 S3 remains the validator that
    FAILs out-of-range spawns (C3-Q3 boundary).
    """
    asset = get_store().get_map(map_id)
    if asset is None or not asset.path:
        return None
    path = (Path(__file__).resolve().parents[3] / asset.path).resolve()
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    lengths: dict[int, float] = {}
    for road in root.iter("road"):
        try:
            rid = int(road.get("id", ""))
            max_s = float(road.get("length", ""))
        except ValueError:
            continue
        lengths[rid] = max_s
    return lengths or None


def _default_road_for(map_id: str) -> int | None:
    """A sensible default driving road on the selected map: its longest road.

    Auto-selected multi-road maps (urban junction networks) usually have no road 1;
    binding the default spawn to the longest road keeps keyword-selected environments
    runnable without the request naming a road explicitly.
    """
    lengths = _map_topology_for(map_id)
    if not lengths:
        return None
    return max(lengths, key=lambda rid: lengths[rid])


def _explicit_map_id(intent_spec: IntentSpec) -> str | None:
    """Map id named explicitly by the request, or None (C1-Q2: explicit wins)."""
    for constraint in intent_spec.constraints:
        if constraint.name.lower() == "map" and isinstance(constraint.value, str):
            return constraint.value
    for maneuver in intent_spec.maneuvers:
        for key, value in maneuver.params.items():
            if key.lower() == "map_id" and isinstance(value, str):
                return value
    for trigger in intent_spec.triggers:
        for key, value in trigger.params.items():
            if key.lower() == "map_id" and isinstance(value, str):
                return value
    return None


def _auto_select_map(request_text: str) -> str | None:
    """First keyword-rule match against C3-registered maps, or None."""
    text = (request_text or "").lower()
    for keyword, map_id in _MAP_SELECTION_RULES:
        if keyword in text and get_store().get_map(map_id) is not None:
            return map_id
    return None


def _resolve_map_id(intent_spec: IntentSpec, request_text: str = "") -> str:
    """Explicit map id, else keyword auto-selection, else the Phase-1 default map."""
    explicit = _explicit_map_id(intent_spec)
    if explicit is not None:
        return explicit
    auto = _auto_select_map(request_text)
    if auto is not None:
        return auto
    return _DEFAULT_MAP


def _map_identity(map_id: str) -> IRMap:
    """Embed C3 map identity only (id/sha256) — never topology (C3-Q3)."""
    asset = get_store().get_map(map_id)
    if asset is not None:
        return IRMap(map_asset_id=asset.id, sha256=asset.sha256)
    # Unknown map: still reference the requested id with the documented placeholder,
    # keeping the IR well-formed; C6/E08 owns topology checks for it.
    return IRMap(map_asset_id=map_id, sha256=MAP_SHA256_PLACEHOLDER)


def _catalog_ref(actor: ActorIntent) -> str:
    """Catalog entry name by actor kind (vehicle -> car_mid, pedestrian -> pedestrian,
    truck by name hint); static actors have no catalog entry, default to car_mid."""
    name = actor.name.lower()
    if "truck" in name:
        return "truck"
    if actor.kind == "pedestrian":
        return "pedestrian"
    return "car_mid"  # vehicle and static


def _initial_speed_constraint(actor_intent: ActorIntent) -> IRConstraint | None:
    """Preserve an initial-speed interval as a range constraint (C4-Q4).

    Defensively gates a c3_default origin (the IntentSpec validator already double-acks;
    this is ARCH-0004 defense in depth). The concrete representative speed lives on the
    IRActor; the full interval rides in the IR constraint.
    """
    speed = actor_intent.initial_speed_mps
    if not isinstance(speed, Range):
        return None
    _require_acked(actor_intent.slot, f"actor '{actor_intent.name}' initial speed")
    return IRConstraint(
        name=f"{actor_intent.name}_initial_speed",
        value=Range(min=speed.min, max=speed.max, unit=speed.unit),
        unit="mps",
    )


def _lane_target(params: dict[str, float | int | str]) -> int | None:
    """First integer lane target in a maneuver/trigger param bag (key mentions 'lane')."""
    for key, value in params.items():
        if "lane" not in key.lower():
            continue
        parsed = _as_int(value)
        if parsed is not None:
            return parsed
    return None


def _as_int(value: object) -> int | None:
    """Parse a float/int/str numeric value as an integer lane id when integral."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        try:
            number = Decimal(value)
        except ArithmeticError:
            return None
        return int(number) if number == number.to_integral_value() else None
    return None


def _e08_suggestions(
    behaviors: list[IRBehavior], map_id: str
) -> list[IRSuggestion]:
    """E08 (DERIVED-10): a lane target outside the default map's lanes is a diagnostic.

    The canonical ``params`` are left untouched (C2-Q3 / C9-Q6 / ARCH-0002): C4 only
    appends a suggestion with a sign-matched nearest in-range lane.
    """
    if map_id != _DEFAULT_MAP:
        # Unknown map topology is not C4's to judge (C3-Q3); only the known default
        # map has a lane span C4 may reason about.
        return []
    suggestions: list[IRSuggestion] = []
    for index, behavior in enumerate(behaviors):
        if behavior.action is not ActionType.LANE_CHANGE:
            continue
        target = _lane_target(behavior.params)
        if target is None:
            continue
        if _DEFAULT_MAP_LANE_MIN <= target <= _DEFAULT_MAP_LANE_MAX:
            continue
        nearest = _DEFAULT_MAP_LANE_MAX if target > 0 else _DEFAULT_MAP_LANE_MIN
        suggestions.append(
            IRSuggestion(
                code=_E08_CODE,
                message=(
                    f"lane {target} does not exist on straight_2lane; nearest is {nearest}"
                ),
                field_path=f"behaviors[{index}].params",
                proposed_value=nearest,
            )
        )
    return suggestions


def _to_ir_behavior(
    maneuver: ManeuverIntent, trigger: TriggerIntent | None
) -> tuple[IRBehavior, list[str]]:
    """One declarative behavior with passthrough params/trigger + its OSC feature keys."""
    _require_acked(maneuver.slot, f"maneuver '{maneuver.action}' for '{maneuver.actor}'")
    behavior = IRBehavior(
        actor=maneuver.actor,
        action=maneuver.action,
        params=dict(maneuver.params),
        trigger=trigger,
    )
    keys = list(_ACTION_FEATURES[maneuver.action])
    if trigger is not None:
        keys.append(_TRIGGER_FEATURES[trigger.kind])
    return behavior, keys


def build_ir(
    intent_spec: IntentSpec,
    evidence: EvidenceBundle | None = None,
    request_text: str = "",
) -> ScenarioIR:
    """Compile a validated IntentSpec to a frozen ScenarioIR (core, no trace emitted).

    ``evidence`` is accepted for interface compatibility (C3 bundle provenance); map
    identity resolution still queries the C3 store directly, since C3 is static
    knowledge (C3-Q4). ``request_text`` drives keyword map auto-selection when the
    request names no map explicitly. Deterministic: same intent -> same IR.
    """
    del evidence  # map identity comes from the C3 store; evidence is provenance only.

    # Header.
    request_id = intent_spec.meta.request_id or "REQ-0001"
    header = IRHeader(
        request_id=request_id,
        intent_spec_hash=semantic_hash(intent_spec),
        esmini_pin=ESMINI_BUILD_PIN,
    )

    # Map identity (via C3 store — identity only, C3-Q3).
    map_id = _resolve_map_id(intent_spec, request_text)
    ir_map = _map_identity(map_id)

    # Actors. Lane-relative spawns are clamped to the selected map's road length
    # (topology data comes from the C6-owned parse; C4 only clamps, it does not
    # re-route — C3-Q3 boundary) so auto-selected short-segment urban maps don't get
    # out-of-range s values that esmini would silently truncate.
    map_topology = _map_topology_for(map_id)
    default_road = _default_road_for(map_id)
    actors: list[IRActor] = []
    actor_constraints: list[IRConstraint] = []
    for actor_intent in intent_spec.actors:
        speed = actor_intent.initial_speed_mps
        representative = (
            speed if isinstance(speed, float) else (speed.min + speed.max) / 2.0
        )
        spawn = actor_intent.initial_position
        if map_topology is not None:
            spawn_road = int(spawn.road_id or 1)
            if spawn_road not in map_topology and default_road is not None:
                # The spawn's road does not exist on the selected map; bind to the
                # map's longest road (keeps keyword-selected junction networks
                # runnable without the request naming a road).
                spawn = spawn.model_copy(update={"road_id": default_road})
                spawn_road = default_road
            max_s = map_topology.get(spawn_road)
            if max_s is not None and spawn.s_m is not None and spawn.s_m > max_s:
                spawn = spawn.model_copy(update={"s_m": max_s * 0.9})
        actor = IRActor(
            name=actor_intent.name,
            kind=actor_intent.kind,
            bbox_ref=_catalog_ref(actor_intent),
            spawn=spawn,
            initial_speed_mps=representative,
        )
        speed_constraint = _initial_speed_constraint(actor_intent)
        if speed_constraint is not None:
            actor_constraints.append(speed_constraint)
        actors.append(actor)

    # Behaviors: triggers attach positionally to maneuvers (no explicit join key in the
    # contract — both lists run in parallel, so behavior i takes trigger i when present).
    triggers = intent_spec.triggers
    behaviors: list[IRBehavior] = []
    feature_keys: list[str] = []
    seen: set[str] = set()
    for index, maneuver in enumerate(intent_spec.maneuvers):
        trigger = triggers[index] if index < len(triggers) else None
        behavior, keys = _to_ir_behavior(maneuver, trigger)
        behaviors.append(behavior)
        for key in keys:
            if key not in seen:
                seen.add(key)
                feature_keys.append(key)

    # E08 suggestions — diagnostics only; canonical params untouched (DERIVED-10).
    suggestions = _e08_suggestions(behaviors, map_id)

    # Constraints: intent constraints pass through; actor-speed ranges added above.
    constraints = [
        IRConstraint(name=c.name, value=c.value, unit=c.unit)
        for c in intent_spec.constraints
    ] + actor_constraints

    ir = ScenarioIR(
        meta=_trace_meta(intent_spec),
        header=header,
        map=ir_map,
        actors=actors,
        behaviors=behaviors,
        constraints=constraints,
        objectives=list(intent_spec.objectives),
        suggestions=suggestions,
        feature_keys=feature_keys,
    )
    return ir


def run_c4(
    intent_spec: IntentSpec,
    trajectory_id: str = "REQ-0001",
    evidence: EvidenceBundle | None = None,
    request_text: str = "",
) -> ScenarioIR:
    """Pipeline entry point: build the IR and emit the trace at step 5.

    ``request_text`` is the raw user request (C1 ``RequestSpec.raw``), used only for
    keyword map auto-selection; explicit map fields on the IntentSpec always win.
    """
    ir = build_ir(intent_spec, evidence, request_text=request_text)
    intent_digest = semantic_hash(intent_spec)[:8]
    ir_digest = semantic_hash(ir)[:8]
    trace.emit(5, "C4", "IN", f"<IntentSpec:{intent_digest}>", trajectory_id)
    trace.emit(5, "C4", "OUT", f"<ScenarioIR:{ir_digest}>", trajectory_id)
    return ir