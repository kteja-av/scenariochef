"""C6 — Scenario Validation: frozen S1→S6 validation funnel (ADR-0007).

C6 distinguishes structural validity (S1 XSD), semantic consistency (S2), map
compatibility (S3, E08), and physical bounds (S4). The funnel short-circuits on the
first FAIL stage; later stages are SKIPPED (C6-Q4, ARCH-0004). S5 is always SKIPPED
(C6-Q1). S6 dry-run runs only when any k3_flag support is ``unknown`` (C6-Q2) and, in
Phase 1, delegates to the C7 ``preflight`` mode via a callable — never an LLM (ARCH-0001).

WARN-and-pass decisions: UNREACHABLE_TRIGGER (E09) surfaces as a WARN but does not fail
the stage, detection shifting to C7/C8 while S5 is skipped (C6-Q3). RUNTIME_COMPAT (E10)
records a failed dry-run for C10 history.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import xmlschema

from scenariochef import trace
from scenariochef.contracts.common import Severity, TraceMeta, semantic_hash
from scenariochef.contracts.generated_scenario import GeneratedScenario
from scenariochef.contracts.run_record import RunRecord, RunStatus
from scenariochef.contracts.scenario_ir import ScenarioIR
from scenariochef.contracts.validation_report import (
    ErrorTaxonomy,
    Stage,
    StageResult,
    Status,
    ValidationError,
    ValidationReport,
)

if TYPE_CHECKING:
    from xmlschema import XMLSchema

_PRODUCER = "C6"

# Determinism (deep-tests report, LOW finding): the ValidationReport hash must be
# reproducible for identical inputs, so created_at is pinned like C7/C8 do.
_DETERMINISTIC_CREATED_AT = "2000-01-01T00:00:00+00:00"

# XSC-0001: the OSC 1.0 XSD is a real, authoritative schema; an XSD failure is a real
# C6 error, not a warning. The schema is loaded once at module import and cached for the
# process lifetime.
_XSD_PATH = Path(__file__).resolve().parents[3] / "assets" / "xsd" / "OpenSCENARIO_1_0.xsd"
_XSD_SCHEMA: XMLSchema = xmlschema.XMLSchema(str(_XSD_PATH))

_MAX_MSG_CHARS = 200  # truncate XSD error messages to avoid unbounded reports.
_NO_BINARY_PROMPT = "no preflight hook"
_DRY_RUN_SKIPPED = "no unknown k3 flags to dry-run"

# Physical bound for a speed in Phase 1 (m/s). Speeds above this fail physical-bounds.
_SPEED_BOUND_MPS = 70.0

# Sanity threshold for a speed_headway trigger (> bound is flagged unreachable).
_TRIGGER_SPEED_THRESHOLD = 70.0

# Fallback map path when the IR map id is not in the C3 store (mirrors C5), resolved
# against the repo root so S3 works regardless of the invoking CWD.
_FALLBACK_MAP = Path(__file__).resolve().parents[3] / "assets" / "maps" / "straight_2lane.xodr"
_REPO_ROOT_C6 = Path(__file__).resolve().parents[3]


def run_c6(
    generated_scenarios: list[GeneratedScenario],
    trajectory_id: str = "REQ-0001",
    scenario_ir: ScenarioIR | None = None,
    preflight: Callable[[GeneratedScenario], RunRecord] | None = None,
) -> list[ValidationReport]:
    """CX-facing orchestration: run the funnel per scenario and emit trace per scenario.

    ``scenario_ir`` provides IR facts for S3 (map/topology) and S4 (physical bounds);
    when absent, S3 is SKIPPED and S4 falls back to the emitted xosc only. ``preflight``
    is the C7 preflight callable; when None, an S6 dry-run degrades to SKIPPED.
    """
    reports: list[ValidationReport] = []
    for gs in generated_scenarios:
        token_in = f"<GeneratedScenario:{semantic_hash(gs)[:8]}>"
        trace.emit(7, "C6", "IN", token_in, trajectory_id)
        report = validate_scenario(gs, scenario_ir=scenario_ir, preflight=preflight)
        trace.emit(
            7, "C6", "OUT", f"<ValidationReport:{semantic_hash(report)[:8]}>", trajectory_id
        )
        reports.append(report)
    return reports


def validate_scenario(
    gs: GeneratedScenario,
    scenario_ir: ScenarioIR | None = None,
    preflight: Callable[[GeneratedScenario], RunRecord] | None = None,
) -> ValidationReport:
    """Run the frozen S1→S6 funnel on one generated scenario and return its report.

    Stages run in order; the first stage that FAILs causes every later stage to be
    SKIPPED (C6-Q4). S5 is always SKIPPED (C6-Q1).
    """
    meta = TraceMeta(
        request_id=gs.meta.request_id,
        trajectory_id=gs.meta.trajectory_id,
        created_at=_DETERMINISTIC_CREATED_AT,
        produced_by=_PRODUCER,
    )
    # S1→S6 run in order; the first FAIL short-circuits, so later stages never execute
    # (C6-Q4). Stages are invoked lazily so a broken xosc never reaches S2's parser.
    stage_workers: list[Callable[[], StageResult]] = [
        lambda: _stage_s1(gs),
        lambda: _stage_s2(gs),
        lambda: _stage_s3(gs, scenario_ir),
        lambda: _stage_s4(gs, scenario_ir),
        _stage_s5,
        lambda: _stage_s6(gs, preflight),
    ]
    results: list[StageResult] = []
    failed = False
    for i, worker in enumerate(stage_workers):
        if failed:
            results.append(_skip(Stage(f"S{i + 1}")))
            continue
        result = worker()
        results.append(result)
        if result.status is Status.FAIL:
            failed = True
    outcome = Status.FAIL if failed else Status.PASS
    return ValidationReport(
        meta=meta,
        stages=results,
        outcome=outcome,  # type: ignore[arg-type]
    )


# --- S1: structural / XSD ---------------------------------------------------


def _stage_s1(gs: GeneratedScenario) -> StageResult:
    """Validate the emitted xosc against the OSC 1.0 XSD (XSC-0001)."""
    errors: list[ValidationError] = []
    # Broken XML or an XSD failure are both real errors (S1 FAIL -> short-circuit).
    try:
        _XSD_SCHEMA.validate(gs.xosc.content)
    except Exception as exc:  # noqa: BLE001 - any schema/parse failure is a real error
        msg = str(exc).strip().replace("\r", " ").replace("\n", " ")
        errors.append(
            ValidationError(
                code=ErrorTaxonomy.XSD_INVALID,
                severity=Severity.ERROR,
                message=msg[:_MAX_MSG_CHARS],
                location="/",
            )
        )
        return StageResult(stage=Stage.S1, status=Status.FAIL, errors=errors)
    return StageResult(stage=Stage.S1, status=Status.PASS, errors=errors)


# --- S2: semantic -----------------------------------------------------------


def _stage_s2(gs: GeneratedScenario) -> StageResult:
    """Semantic checks over the (well-formed) xosc.

    - Every ``entityRef``/actor reference in the storyboard must be declared as a
      ``ScenarioObject`` in ``Entities`` (SEMANTIC_REF).
    - A negative ``AbsoluteTargetSpeed`` violates physical bounds (PHYSICAL_BOUNDS).
    - A ``SpeedCondition`` threshold above the reachable bound is WARN-and-pass
      (UNREACHABLE_TRIGGER, C6-Q3).
    """
    errors: list[ValidationError] = []
    root = ET.fromstring(gs.xosc.content)

    entities = {o.get("name") for o in root.iter("ScenarioObject") if o.get("name")}
    referenced: set[str] = set()
    for el in root.iter():
        for key, value in el.attrib.items():
            # entityRef on Private/EntityRef; entity on EntityConditions (e.g. headway).
            if key.lower() in ("entityref", "entity") and value:
                referenced.add(value)
    for ref in sorted(referenced - entities):
        errors.append(
            ValidationError(
                code=ErrorTaxonomy.SEMANTIC_REF,
                severity=Severity.ERROR,
                message=f"storyboard references entity '{ref}' not declared in Entities",
                location=f"//*[@entityRef='{ref}']|//*[@entity='{ref}']",
            )
        )

    for el in root.iter("AbsoluteTargetSpeed"):
        speed = _attr_float(el, "value")
        if speed is not None and speed < 0:
            errors.append(
                ValidationError(
                    code=ErrorTaxonomy.PHYSICAL_BOUNDS,
                    severity=Severity.ERROR,
                    message=f"AbsoluteTargetSpeed {speed} is negative",
                    location="/Storyboard",
                )
            )

    for el in root.iter("SpeedCondition"):
        speed = _attr_float(el, "value")
        if speed is not None and speed > _TRIGGER_SPEED_THRESHOLD:
            # E09 unreachable trigger: WARN-and-pass while S5 is skipped (C6-Q3).
            errors.append(
                ValidationError(
                    code=ErrorTaxonomy.UNREACHABLE_TRIGGER,
                    severity=Severity.WARN,
                    message=(
                        f"speed_headway trigger threshold {speed} exceeds the reachable "
                        f"bound {_TRIGGER_SPEED_THRESHOLD} m/s"
                    ),
                    location="/Storyboard",
                )
            )

    any_error = any(e.severity is Severity.ERROR for e in errors)
    status = Status.FAIL if any_error else Status.PASS
    return StageResult(stage=Stage.S2, status=status, errors=errors)


# --- S3: map / topology (E08 lives here) -------------------------------------


def _stage_s3(gs: GeneratedScenario, scenario_ir: ScenarioIR | None) -> StageResult:
    """Check lane existence / spawn distance against the map (only from the IR)."""
    if scenario_ir is None:
        return StageResult(stage=Stage.S3, status=Status.SKIPPED)
    errors: list[ValidationError] = []
    topology = _parse_map(_read_xodr(gs, scenario_ir))

    for behavior in scenario_ir.behaviors:
        lane_value = behavior.params.get("target_lane", behavior.params.get("lane"))
        if lane_value is None:
            continue
        lane = int(lane_value)
        road = int(behavior.params.get("road_id", 1))
        lanes = topology.lanes.get(road)
        if lanes is not None and lane not in lanes:
            errors.append(_lane_missing(lane, road, lanes))
            continue
        if lanes is None:
            errors.append(
                ValidationError(
                    code=ErrorTaxonomy.MAP_TOPOLOGY,
                    severity=Severity.ERROR,
                    message=f"road {road} does not exist in the map",
                    location=f"//behavior[{behavior.actor}]",
                    repair_hint=f"select an existing road; available: {sorted(topology.lanes)}",
                )
            )

    for actor in scenario_ir.actors:
        spawn = actor.spawn
        if spawn.road_id is None or spawn.lane_id is None or spawn.s_m is None:
            continue
        road = int(spawn.road_id)
        lanes = topology.lanes.get(road)
        length = topology.lengths.get(road)
        if lanes is None:
            errors.append(
                ValidationError(
                    code=ErrorTaxonomy.MAP_TOPOLOGY,
                    severity=Severity.ERROR,
                    message=(
                        f"actor '{actor.name}' spawns on road {road}, which does not "
                        "exist in the map"
                    ),
                    location=f"//actors[{actor.name}].spawn",
                    repair_hint=(
                        f"select an existing road; available: {sorted(topology.lanes)}"
                    ),
                )
            )
            continue
        if spawn.lane_id not in lanes:
            errors.append(
                ValidationError(
                    code=ErrorTaxonomy.MAP_TOPOLOGY,
                    severity=Severity.ERROR,
                    message=(
                        f"actor '{actor.name}' spawns on absent lane {spawn.lane_id} "
                        f"of road {road}"
                    ),
                    location=f"//actors[{actor.name}].spawn",
                    repair_hint=f"lane {spawn.lane_id} does not exist on road {road}; "
                    f"nearest valid: {_nearest(spawn.lane_id, lanes)}",
                )
            )
        if length is not None and spawn.s_m > length:
            errors.append(
                ValidationError(
                    code=ErrorTaxonomy.MAP_TOPOLOGY,
                    severity=Severity.ERROR,
                    message=(
                        f"actor '{actor.name}' spawns at s={spawn.s_m} beyond road "
                        f"{road} length {length}"
                    ),
                    location=f"//actors[{actor.name}].spawn",
                    repair_hint=f"clamp spawn s to at most {length}",
                )
            )

    status = Status.FAIL if errors else Status.PASS
    return StageResult(stage=Stage.S3, status=status, errors=errors)


def _lane_missing(lane: int, road: int, lanes: set[int]) -> ValidationError:
    return ValidationError(
        code=ErrorTaxonomy.MAP_TOPOLOGY,
        severity=Severity.ERROR,
        message=f"lane {lane} does not exist on road {road}",
        location=f"//behavior[target_lane={lane}]",
        repair_hint=(
            f"lane {lane} does not exist on road {road}; nearest valid: {_nearest(lane, lanes)}"
        ),
    )


def _nearest(lane: int, lanes: set[int]) -> int:
    """Closest existing lane id to ``lane`` (ties favor the lower value)."""
    if lane in lanes:
        return lane
    return min(lanes, key=lambda cand: (abs(cand - lane), cand))


# --- S4: catalog / physical bounds -------------------------------------------


def _stage_s4(gs: GeneratedScenario, scenario_ir: ScenarioIR | None) -> StageResult:
    """Catalog facts + acknowledged assumptions: speeds must respect physical bounds."""
    errors: list[ValidationError] = []
    if scenario_ir is not None:
        for actor in scenario_ir.actors:
            speed = actor.initial_speed_mps
            if isinstance(speed, (int, float)) and speed > _SPEED_BOUND_MPS:
                errors.append(_speed_error(f"actor '{actor.name}' speed", speed))
        for behavior in scenario_ir.behaviors:
            target = behavior.params.get("target_speed")
            if isinstance(target, (int, float)) and target > _SPEED_BOUND_MPS:
                errors.append(
                    _speed_error(f"behavior '{behavior.actor}' target_speed", float(target))
                )

    status = Status.FAIL if errors else Status.PASS
    return StageResult(stage=Stage.S4, status=status, errors=errors)


def _speed_error(where: str, speed: float) -> ValidationError:
    return ValidationError(
        code=ErrorTaxonomy.PHYSICAL_BOUNDS,
        severity=Severity.ERROR,
        message=f"{where} {speed} m/s exceeds physical bound {_SPEED_BOUND_MPS} m/s",
        location="/",
    )


# --- S5: always skipped --------------------------------------------------------


def _stage_s5() -> StageResult:
    return StageResult(stage=Stage.S5, status=Status.SKIPPED)


# --- S6: dry-run ---------------------------------------------------------------


def _stage_s6(
    gs: GeneratedScenario, preflight: Callable[[GeneratedScenario], RunRecord] | None
) -> StageResult:
    """esmini dry-run — only when any k3_flag support is ``unknown`` (C6-Q2)."""
    unknown = [f for f in gs.k3_flags if f.support.value == "unknown"]
    if not unknown:
        return StageResult(
            stage=Stage.S6,
            status=Status.SKIPPED,
            errors=[
                ValidationError(
                    code=ErrorTaxonomy.INTERNAL,
                    severity=Severity.INFO,
                    message=_DRY_RUN_SKIPPED,
                    location="/",
                )
            ],
        )
    if preflight is None:
        skip_errors = [
            ValidationError(
                code=ErrorTaxonomy.INTERNAL,
                severity=Severity.INFO,
                message=_NO_BINARY_PROMPT,
                location="/",
            )
        ]
        return StageResult(
            stage=Stage.S6,
            status=Status.SKIPPED,
            errors=skip_errors,
        )
    record = preflight(gs)
    status: Status
    errors: list[ValidationError] = []
    if record.status is RunStatus.COMPLETED:
        status = Status.RUNS  # dry-run succeeded -> PASS contribution.
    elif record.status is RunStatus.SKIPPED_NO_BINARY:
        # WARN, outcome unaffected (C6: binary absent is not a scenario fault).
        errors.append(
            ValidationError(
                code=ErrorTaxonomy.RUNTIME_COMPAT,
                severity=Severity.WARN,
                message="esmini binary unavailable; preflight skipped",
                location="/",
            )
        )
        status = Status.WARN
    else:  # HUNG / CRASHED -> FAIL RUNTIME_COMPAT (E10).
        errors.append(
            ValidationError(
                code=ErrorTaxonomy.RUNTIME_COMPAT,
                severity=Severity.ERROR,
                message=f"esmini preflight ended in {record.status}",
                location="/",
            )
        )
        status = Status.FAIL
    return StageResult(stage=Stage.S6, status=status, errors=errors)


# --- helpers ------------------------------------------------------------------


def _skip(stage: Stage) -> StageResult:
    return StageResult(stage=stage, status=Status.SKIPPED)


def _attr_float(el: ET.Element, key: str) -> float | None:
    raw = el.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _read_xodr(gs: GeneratedScenario, scenario_ir: ScenarioIR) -> str:
    """Return the OpenDRIVE content for S3.

    Resolution order: an in-memory .xodr artifact attached to the scenario, then the
    LogicFile path declared inside the emitted .xosc (resolved against the repo root,
    mirroring C7's esmini ``--path``), then the Phase-1 fallback map. Validating against
    the declared map (not the fallback) is what makes the E08/S3 spawn and lane checks
    meaningful for auto-selected maps.
    """
    if gs.xodr is not None:
        return gs.xodr.content
    declared = _declared_logic_file(gs.xosc.content)
    if declared is not None:
        candidate = (_REPO_ROOT_C6 / declared).resolve()
        # Path-traversal guard: the declared path must stay inside the repo.
        if candidate.is_relative_to(_REPO_ROOT_C6) and candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return _FALLBACK_MAP.read_text(encoding="utf-8")


def _declared_logic_file(xosc_content: str) -> str | None:
    """The LogicFile filepath from the emitted .xosc, or None."""
    try:
        root = ET.fromstring(xosc_content)
    except ET.ParseError:
        return None
    logic = root.find("./RoadNetwork/LogicFile")
    if logic is None:
        return None
    path = (logic.get("filepath") or "").strip()
    return path or None


def _parse_map(content: str) -> _MapTopology:
    """Parse an .xodr into road->lane-ids and road->length for C6 S3 (E08)."""
    root = ET.fromstring(content)
    lanes: dict[int, set[int]] = {}
    lengths: dict[int, float] = {}
    for road in root.iter("road"):
        road_id = _attr_float(road, "id")
        if road_id is None:
            continue
        road_id_int = int(road_id)
        length = _attr_float(road, "length")
        if length is not None:
            lengths[road_id_int] = length
        ids = lanes.setdefault(road_id_int, set())
        for lane in road.iter("lane"):
            lane_id = _attr_float(lane, "id")
            if lane_id is not None:
                ids.add(int(lane_id))
    return _MapTopology(lanes=lanes, lengths=lengths)


class _MapTopology:
    """Road id -> lane id set, and road id -> length, parsed from a .xodr."""

    __slots__ = ("lanes", "lengths")

    def __init__(self, lanes: dict[int, set[int]], lengths: dict[int, float]) -> None:
        self.lanes = lanes
        self.lengths = lengths