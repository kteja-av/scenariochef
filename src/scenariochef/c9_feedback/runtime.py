"""C9 → Feedback & Improvement: deterministic repair and parameter exploration.

Not an LLM agent (DERIVED-8, ARCH-0001): every branch is a fixed rule over the
validation/evaluation report and the IR. ``revised_ir`` is always a NEW object
produced via ``model_copy(deep=True)`` — never in-place mutation (C9-Q5) — and
user-explicit slots stay byte-identical (ARCH-0002 / C9-Q6). E08-class MAP_TOPOLOGY
FAILs escalate to the user instead of lane-snapping (DERIVED-16). ``stop`` honors the
loop budget (C9-Q4: N=5 or no metric gain).

Provenance choice: ``IRBehavior.params`` is a plain ``dict`` with no schema-level
provenance field, so we look it up defensively (see ``_is_user_explicit``): if the
object carries a ``slot`` (SlotProvenance) or a param key ``provenance`` equal to
``"user_explicit"`` it is treated as user-explicit and never rewritten; otherwise the
param is treated as range-derived and eligible for clamping.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from scenariochef import trace
from scenariochef.contracts.common import Range, SlotProvenance
from scenariochef.contracts.evaluation_report import EvaluationReport, Metric
from scenariochef.contracts.feedback_action import FeedbackAction
from scenariochef.contracts.generated_scenario import ParameterBinding
from scenariochef.contracts.run_record import RunRecord
from scenariochef.contracts.scenario_ir import IRBehavior, IRConstraint, ScenarioIR
from scenariochef.contracts.validation_report import (
    ErrorTaxonomy,
    ValidationError,
    ValidationReport,
)

CLAMP_LIMIT = 70.0
MAX_ITERATIONS = 5

# Determinism (deep-tests report, LOW finding): FeedbackAction hashes must be
# reproducible, so created_at is pinned like C7/C8 do.
_DETERMINISTIC_CREATED_AT = "2000-01-01T00:00:00+00:00"


def _is_user_explicit(obj: Any) -> bool:
    """True when a slot/param object carries user_explicit provenance.

    ``IRBehavior.params`` is untyped on the schema, so provenance may live either on an
    attached ``SlotProvenance`` (``obj.slot``) or inline as a ``provenance`` key. Absent
    either, the value is treated as range-derived (safe default: editable).
    """
    slot = getattr(obj, "slot", None)
    if isinstance(slot, SlotProvenance):
        return slot.source == "user_explicit"
    if isinstance(slot, dict) and slot.get("source") == "user_explicit":
        return True
    source = getattr(obj, "provenance", None)
    if isinstance(source, str):
        return source == "user_explicit"
    params = getattr(obj, "params", None)
    if isinstance(params, dict) and params.get("provenance") == "user_explicit":
        return True
    return False


def run_c9(
    report: ValidationReport | EvaluationReport | RunRecord,
    trajectory_id: str = "REQ-0001",
    scenario_ir: ScenarioIR | None = None,
    iteration: int = 0,
    last_metrics: list[Metric] | None = None,
    prev_metrics: list[Metric] | None = None,
) -> FeedbackAction:
    """Dispatch to repair/explore/simulator-repair by report type (C9-Q1 split)."""
    if isinstance(report, ValidationReport):
        if scenario_ir is None:
            raise ValueError("run_c9: scenario_ir required for repair")
        return plan_repair(report, scenario_ir, iteration)
    if isinstance(report, EvaluationReport):
        if scenario_ir is None:
            raise ValueError("run_c9: scenario_ir required for explore")
        return plan_explore(report, scenario_ir, iteration, last_metrics, prev_metrics)
    # Simulator feedback (C7 RunRecord): the esmini execution feeds the loop too.
    if isinstance(report, RunRecord):
        if scenario_ir is None:
            raise ValueError("run_c9: scenario_ir required for simulator repair")
        return plan_simulator_repair(report, scenario_ir, iteration)
    raise TypeError(f"run_c9: unsupported report type {type(report)!r}")


def plan_repair(
    validation_report: ValidationReport,
    scenario_ir: ScenarioIR,
    iteration: int = 0,
) -> FeedbackAction:
    """Deterministically repair the first FAIL stage's errors (or escalate)."""
    trace.emit(10, "C9", "IN", f"<ValidationReport:{_h(validation_report)}>",
               _tid(validation_report))

    if iteration >= MAX_ITERATIONS:
        return _build(validation_report, "repair", stop=True,
                      stop_reason="max_iterations", iteration=iteration)

    first: ValidationError | None = None
    for stage in validation_report.stages:
        if stage.status.value == "fail" and stage.errors:
            first = stage.errors[0]
            break
    if first is None:
        # Nothing to repair (only WARN) — leave the IR untouched.
        return _build(validation_report, "repair", iteration=iteration,
                      rationale="no FAIL errors to repair")

    code = first.code
    if code is ErrorTaxonomy.MAP_TOPOLOGY:
        # E08 / DERIVED-16 — escalate, no lane rewrite.
        return _build(
            validation_report, "repair", iteration=iteration,
            rationale="map/topology failure; escalate to user (DERIVED-16)",
            escalate_to_user=True, escalation_reason=first.repair_hint, stop=True,
        )

    if code is ErrorTaxonomy.SEMANTIC_REF:
        valid = {a.name for a in scenario_ir.actors}
        dropped = [b.actor for b in scenario_ir.behaviors if b.actor not in valid]
        if not dropped:
            return _build(validation_report, "repair", iteration=iteration,
                          rationale="no dangling behaviors to drop")
        revised = scenario_ir.model_copy(
            deep=True, update={"behaviors": [b for b in scenario_ir.behaviors if b.actor in valid]}
        )
        return _build(
            validation_report, "repair", iteration=iteration,
            revised_ir=revised, stop=False,
            rationale=(
                "dropped behaviors referencing unknown actors: "
                + ", ".join(sorted(set(dropped)))
            ),
        )

    if code is ErrorTaxonomy.PHYSICAL_BOUNDS:
        offending = _find_out_of_bounds_behavior(scenario_ir)
        if offending is not None and _is_user_explicit(offending):
            return _build(
                validation_report, "repair", iteration=iteration,
                rationale="physical-bounds param is user_explicit; escalate, no rewrite (C9-Q6)",
                escalate_to_user=True, escalation_reason=first.repair_hint, stop=True,
            )
        if offending is not None:
            Params = dict[str, float | int | str]

            def _clamped_params(params: Params) -> Params:
                return {
                    k: (CLAMP_LIMIT if isinstance(v, (int, float)) and v > CLAMP_LIMIT else v)
                    for k, v in params.items()
                }

            new_behaviors = [
                b.model_copy(update={"params": _clamped_params(b.params)})
                if b.actor == offending.actor
                else b
                for b in scenario_ir.behaviors
            ]
            revised = scenario_ir.model_copy(deep=True, update={"behaviors": new_behaviors})
            return _build(
                validation_report, "repair", iteration=iteration,
                revised_ir=revised, stop=False,
                rationale=f"clamped physical-bounds param to {CLAMP_LIMIT}",
            )
        return _build(validation_report, "repair", iteration=iteration,
                      rationale="physical-bounds error but no offending behavior located")

    if code is ErrorTaxonomy.RUNTIME_COMPAT:
        # E10 — no substitution, escalate.
        return _build(
            validation_report, "repair", iteration=iteration,
            rationale="runtime-compat issue; no safe substitution (E10)",
            escalate_to_user=True, escalation_reason=first.repair_hint, stop=True,
        )

    if code is ErrorTaxonomy.XSD_INVALID:
        return _build(
            validation_report, "repair", iteration=iteration, stop=False,
            rationale="structural failure exceeds IR-level repair; regenerate upstream",
        )

    if code is ErrorTaxonomy.UNREACHABLE_TRIGGER:
        # E09 WARN-and-pass — tolerated, no action needed.
        return _build(validation_report, "repair", iteration=iteration, stop=False,
                      rationale="WARN only; tolerated (E09)")

    # INTERNAL / unknown — do not guess.
    return _build(validation_report, "repair", iteration=iteration,
                  rationale=f"unhandled taxonomy {code}; escalate", escalate_to_user=True,
                  escalation_reason=first.repair_hint, stop=True)


# esmini runtime-error signatures from stdout/stderr (verified against esmini v3.7.2).
# Map/catalog/locating failures are configuration problems C9 must not paper over —
# they escalate (DERIVED-16 spirit: don't silently rewrite what the user asked for).
# Transient physics errors (zero-width lane while moving) also escalate since they
# indicate a map/scenario mismatch, not a parameter issue.
_SIMULATOR_ERROR_RULES: tuple[tuple[str, str, str], ...] = (
    # (stdout/stderr substring, classification, rationale)
    ("Failed to locate OpenDRIVE file", "map_missing",
     "esmini could not locate the map file"),
    ("Couldn't locate OpenSCENARIO file", "catalog_missing",
     "esmini could not resolve a catalog"),
    ("is or became zero width", "map_topology_runtime",
     "vehicle left the drivable surface (lane width/topology mismatch)"),
)
# Soft findings: 3D model/texture misses are visual-only - esmini continues with a
# bounding box - so they are recorded as rationale, not escalated.
_SIMULATOR_SOFT_RULES: tuple[str, ...] = (
    "3D model ",  # e.g. '3D model ../models/car_white.osgb not located'
)


def plan_simulator_repair(
    run_record: Any,
    scenario_ir: ScenarioIR,
    iteration: int = 0,
) -> FeedbackAction:
    """Classify esmini runtime failures and plan repair from the RunRecord (S-REPAIR).

    The simulator is execution authority (C3-Q2/DERIVED-2): a non-COMPLETED run or a
    hard load/runtime error in the process output feeds back into C9 here. Rules:
    - CRASHED/HUNG → stop (a parameter tweak will not fix a simulator-level fault; the
      loop budget (C9-Q4) should not burn retries on it).
    - Missing map/catalog/asset or runtime topology errors → escalate to the user.
    - COMPLETED with no hard errors → no action (rationale only).
    """
    trace.emit(10, "C9", "IN", f"<RunRecord:{_h(run_record)}>",
               getattr(getattr(run_record, "meta", None), "trajectory_id", "REQ-0001"))

    status = getattr(run_record, "status", None)
    status_value = getattr(status, "value", str(status))
    output = " ".join(
        part or "" for part in (
            getattr(run_record, "stdout_tail", ""),
            getattr(run_record, "stderr_tail", ""),
        )
    )

    if iteration >= MAX_ITERATIONS:
        return _build(run_record, "repair", iteration=iteration, stop=True,
                      stop_reason="max_iterations")

    if status_value in ("crashed", "hung"):
        return _build(
            run_record, "repair", iteration=iteration,
            rationale=(
                f"esmini run {status_value}; simulator-level fault, "
                "not repairable by parameter change"
            ),
            stop=True, stop_reason="none",
        )

    for signature, classification, rationale in _SIMULATOR_ERROR_RULES:
        if signature in output:
            return _build(
                run_record, "repair", iteration=iteration,
                rationale=f"{classification}: {rationale}",
                escalate_to_user=True,
                escalation_reason=f"esmini {classification}: {rationale}",
                stop=True,
            )

    if any(sig in output for sig in _SIMULATOR_SOFT_RULES):
        return _build(
            run_record, "repair", iteration=iteration,
            rationale="visual asset(s) missing (esmini renders bounding boxes); run usable",
        )

    return _build(
        run_record, "repair", iteration=iteration,
        rationale="esmini run clean; no simulator feedback to apply",
    )


def plan_explore(
    evaluation_report: EvaluationReport,
    scenario_ir: ScenarioIR,
    iteration: int = 0,
    last_metrics: list[Metric] | None = None,
    prev_metrics: list[Metric] | None = None,
) -> FeedbackAction:
    """Propose a parameter sweep over a Range-valued IRConstraint (C6 PASS).

    Constraint selection round-robins across ALL eligible Range constraints
    (EXPM-0001, research wave R1): each iteration mutates the next constraint so the
    loop covers the parameter space; a single-constraint IR keeps the pinned
    per-constraint candidate schedule.
    """
    trace.emit(10, "C9", "IN", f"<EvaluationReport:{_h(evaluation_report)}>",
               _tid(evaluation_report))

    if iteration >= MAX_ITERATIONS:
        return _build(evaluation_report, "explore", stop=True,
                      stop_reason="max_iterations", iteration=iteration)

    constraint = _next_range_constraint(scenario_ir, iteration)
    if constraint is None:
        return _build(evaluation_report, "explore", iteration=iteration,
                      rationale="no Range-valued constraints left to explore")

    if _is_user_explicit(constraint):
        return _build(evaluation_report, "explore", iteration=iteration, stop=True,
                      stop_reason="none",
                      rationale="range constraint is user_explicit; not swept (C9-Q6)")

    rng = constraint.value
    if not isinstance(rng, Range):
        return _build(evaluation_report, "explore", iteration=iteration,
                      rationale="constraint is not range-valued; skip")

    value = _candidate(rng.min, rng.max, iteration)
    sweep = [
        ParameterBinding(
            param=constraint.name,
            value=value,
            source_range=rng,
            ir_path=f"constraints/{constraint.name}",
        )
    ]
    if _no_metric_gain(last_metrics, prev_metrics):
        return _build(evaluation_report, "explore", iteration=iteration,
                      revised_ir=None, stop=True, stop_reason="no_metric_gain",
                      rationale=constraint.name)

    new_constraints = [
        constraint.model_copy(update={"value": value})
        if c.name == constraint.name and isinstance(c.value, Range)
        else c
        for c in scenario_ir.constraints
    ]
    revised = scenario_ir.model_copy(deep=True, update={"constraints": new_constraints})
    return _build(
        evaluation_report, "explore", iteration=iteration,
        revised_ir=revised, param_sweep=sweep, stop=False,
        rationale=f"sweep {constraint.name} -> {value}",
    )


# --- helpers ---------------------------------------------------------------


def _no_metric_gain(
    last_metrics: list[Metric] | None, prev_metrics: list[Metric] | None = None
) -> bool:
    """True when exploration can no longer improve the best min ttc/pet.

    Two stop conditions (C9-Q4 budget discipline; EXPM-0002, research wave R1):
    the absolute floor — best metric already <= 0.1 s (collision imminent) — or a
    criticality plateau — relative improvement over the previous iteration's best
    below 1 percent. Plateau stopping mirrors the adaptive search literature
    (LEADE/AdvSce): stop when sweeps stop paying for themselves.
    """
    if not last_metrics:
        return False
    relevant = [m for m in last_metrics if m.name.value in ("ttc", "pet")]
    if not relevant:
        return False
    best = min(m.value for m in relevant)
    if best <= 0.1:
        return True
    if prev_metrics:
        prev_relevant = [m for m in prev_metrics if m.name.value in ("ttc", "pet")]
        if prev_relevant:
            prev_best = min(m.value for m in prev_relevant)
            if prev_best > 0 and (prev_best - best) / prev_best < 0.01:
                return True
    return False


def _next_range_constraint(scenario_ir: ScenarioIR, iteration: int) -> IRConstraint | None:
    """Round-robin the sweep across Range-valued constraints (EXPM-0001).

    ``iteration`` selects which eligible constraint is swept this pass, cycling
    through the full list; user-explicit ranges are still rejected by the caller
    (C9-Q6) and never rewritten.
    """
    eligible = [c for c in scenario_ir.constraints if isinstance(c.value, Range)]
    if not eligible:
        return None
    return eligible[iteration % len(eligible)]


def _candidate(min_v: float, max_v: float, iteration: int) -> float:
    if iteration == 0:
        return min_v
    if iteration == 1:
        return (min_v + max_v) / 2.0
    if iteration == 2:
        return max_v
    return min(min_v * 1.1, max_v)


def _find_out_of_bounds_behavior(scenario_ir: ScenarioIR) -> IRBehavior | None:
    for b in scenario_ir.behaviors:
        if any(isinstance(v, (int, float)) and v > CLAMP_LIMIT for v in b.params.values()):
            return b
    return None


ReportLike = ValidationReport | EvaluationReport


def _tid(report: ReportLike) -> str:
    return getattr(getattr(report, "meta", None), "trajectory_id", "REQ-0001")


def _h(model: BaseModel) -> str:
    """Short stable hash token for the trace line.

    Hash failures are programming errors and must surface: swallowing them used to
    corrupt every C9 trace boundary with the meaningless "00000000" token
    (deep-tests report, LOW finding).
    """
    from scenariochef.contracts.common import semantic_hash
    return semantic_hash(model)[:8]


def _build(report: ReportLike, kind: str, *, iteration: int,
           revised_ir: ScenarioIR | None = None,
           rationale: str = "",
           escalate_to_user: bool = False,
           escalation_reason: str | None = None,
           stop: bool = False,
           stop_reason: str = "none",
           param_sweep: list[ParameterBinding] | None = None) -> FeedbackAction:
    from scenariochef.contracts.common import TraceMeta

    meta = TraceMeta(
        request_id=getattr(getattr(report, "meta", None), "request_id", "REQ-0001"),
        trajectory_id=_tid(report),
        created_at=_DETERMINISTIC_CREATED_AT,
        produced_by="c9",
    )
    action = FeedbackAction(
        meta=meta,
        type=kind,  # type: ignore[arg-type]
        revised_ir=revised_ir,
        rationale=rationale,
        iteration=iteration,
        escalate_to_user=escalate_to_user,
        escalation_reason=escalation_reason,
        stop=stop,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        param_sweep=param_sweep or [],
    )
    trace.emit(10, "C9", "OUT", f"<FeedbackAction:{_h(action)}>", _tid(report))
    return action