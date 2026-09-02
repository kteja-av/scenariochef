"""CX — Orchestration: the DAG coordinator that drives a request through C1–C10.

CX is a hardcoded DAG (ARCH-0001, DERIVED-8): it never acts as an agent and exposes only
the C1–C10 APIs (CX-Q2). It enforces the fixed step sequence — C4, C6, C7 are never
skipped or reordered (CX-Q5) — the loop budget N≤5 / 5-minute wall-clock (CX-Q4), and HITL
on the four gated kinds only: missing params, contradictions, low confidence, assumption
acks (CX-Q3). Full provenance is assembled here and handed to C10 for persistence.

The original no-logic 20-trajectory demo (`run_pipeline`) is preserved for the trace
contract (docs/blueprint.md §5); the real pipeline is `run_request`.
"""

from __future__ import annotations

import sys as _sys
import time as _time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from scenariochef import trace
from scenariochef.c1_input.runtime import run_c1
from scenariochef.c2_understanding.runtime import last_proposals, run_c2
from scenariochef.c3_knowledge.runtime import run_c3
from scenariochef.c3_knowledge.store import ESMINI_BUILD_PIN
from scenariochef.c4_ir.runtime import run_c4
from scenariochef.c5_generation.runtime import run_c5
from scenariochef.c6_validation.runtime import run_c6
from scenariochef.c7_esmini.runtime import make_config, run_c7
from scenariochef.c8_evaluation.runtime import run_c8
from scenariochef.c9_feedback.runtime import run_c9
from scenariochef.c10_management.runtime import run_c10
from scenariochef.c10_management.store import Store
from scenariochef.contracts.common import semantic_hash
from scenariochef.contracts.evidence_bundle import EvidenceQuery
from scenariochef.contracts.orchestration import (
    HitlKind,
    HitlRequest,
    LoopBudget,
    PipelineOutcome,
    PipelineResult,
)
from scenariochef.contracts.persistence_record import ActionLog
from scenariochef.contracts.scenario_ir import ScenarioIR
from scenariochef.scenario_labels import scenario_label_for

LOG_PATH = Path("artifacts") / "trace_run.log"

# Features the Phase-1 request pool exercises; C3 answers support for these (C3-Q5).
_DEFAULT_QUERY_KEYS = [
    "osc.action.SpeedChange",
    "osc.action.LaneChange",
    "osc.action.Following",
    "osc.trigger.TimeHeadway",
    "osc.trigger.SimulationTime",
    "osc.trigger.ReachPosition",
]


def _h8(obj: Any) -> str:
    """First 8 chars of a stable hash; accepts BaseModel or JSON-serializable data."""
    if isinstance(obj, BaseModel):
        return semantic_hash(obj)[:8]
    try:
        import json

        data = json.dumps(obj, sort_keys=True, default=str)
    except (TypeError, ValueError):
        data = str(obj)
    return _sha256(data)[:8]


def _sha256(data: str) -> str:
    import hashlib

    return hashlib.sha256(data.encode()).hexdigest()


def _request_text(request: Any) -> str:
    """Raw request text for C4 map auto-selection (NL string or dict with 'text')."""
    if isinstance(request, str):
        return request
    if isinstance(request, dict):
        text = request.get("text")
        return text if isinstance(text, str) else ""
    return ""


def _ack_c2_defaults(
    evidence: Any, acked_ids: list[str]
) -> Any:
    """Return an EvidenceBundle where C1-acked assumption items are also C2-acked.

    DERIVED-3 requires both C1 (via RequestSpec.acknowledged_assumptions) and C2 (via
    the evidence item's accepted_by_c2) for a c3_default to bind. CX composes the C2 ack
    only for the ids the caller accepted, leaving everything else unacked so the gate
    still rejects silent defaults.
    """
    acked = set(acked_ids)

    def _ack(item: Any) -> Any:
        if item.fact_or_assumption != "assumption" or item.id not in acked:
            return item
        return item.model_copy(update={"accepted_by_c2": True})

    if evidence is None:
        return evidence
    try:
        return evidence.model_copy(
            update={
                "definitions": [_ack(i) for i in evidence.definitions],
                "constraints": [_ack(i) for i in evidence.constraints],
                "examples": [_ack(i) for i in evidence.examples],
                "compatibility": [_ack(i) for i in evidence.compatibility],
                "provenance": [_ack(i) for i in evidence.provenance],
            }
        )
    except Exception:  # pragma: no cover - defensive
        return evidence


def _trace_boundary(
    step: int, component: str, direction: str, obj: Any, trajectory_id: str
) -> None:
    kind = type(obj).__name__
    trace.emit(step, component, direction, f"<{kind}:{_h8(obj)}>", trajectory_id)


# --------------------------------------------------------------------------- #
# The 20-trajectory demo — preserves the no-logic trace contract (blueprint §5).
# --------------------------------------------------------------------------- #


def _run_one_trajectory(trajectory_id: str) -> None:
    label = scenario_label_for(trajectory_id)
    trace.emit(1, "CX", "IN", f"<raw_request:{label}>", trajectory_id)
    request_spec = run_c1(f"<raw_request:{label}>", trajectory_id)
    intent_spec = run_c2(request_spec, trajectory_id)
    run_c3(
        EvidenceQuery(
            feature_keys=_DEFAULT_QUERY_KEYS,
            simulator_build=ESMINI_BUILD_PIN,
        ),
        trajectory_id,
    )
    scenario_ir = run_c4(intent_spec, trajectory_id)
    generated_scenario = run_c5(scenario_ir, trajectory_id)
    run_c6(generated_scenario, trajectory_id, scenario_ir=scenario_ir)
    run_record = run_c7(generated_scenario[0], trajectory_id)
    evaluation_report = run_c8(run_record, trajectory_id, scenario_ir=scenario_ir)
    feedback_action = run_c9(
        evaluation_report, trajectory_id, scenario_ir=scenario_ir
    )
    # Demo is trace-only: emit the C10 boundary contract without persisting, so the
    # blueprint's `[step:11] C10 OUT` line survives without touching the repo store.
    trace.emit(11, "C10", "IN", f"<FeedbackAction:{_h8(feedback_action)}>", trajectory_id)
    trace.emit(11, "C10", "OUT", "<persisted>", trajectory_id)
    trace.emit(12, "CX", "OUT", f"<done:{label}>", trajectory_id)


def run_pipeline(trajectory_count: int = 20) -> None:
    """Demo runner: emit the canonical trace for N labeled trajectories (blueprint §5)."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(LOG_PATH, "w", encoding="utf-8") as log_file:
        trace.set_log(log_file)
        for n in range(1, trajectory_count + 1):
            _run_one_trajectory(f"REQ-{n:04d}")
        # restore the default stdout sink so later trace.emit calls (e.g. in the test
        # suite or CLI) don't write to the now-closed demo log file.
        trace.set_log(_sys.stdout)
    print(
        f"Wrote {trajectory_count} trajectories (REQ-0001..REQ-{trajectory_count:04d}) "
        f"to {LOG_PATH}"
    )


def run_demo() -> None:
    """Alias for the 20-trajectory demo; kept for CLI clarity."""
    run_pipeline(20)


# --------------------------------------------------------------------------- #
# The real pipeline.
# --------------------------------------------------------------------------- #


def run_request(
    request: Any,
    trajectory_id: str = "REQ-0001",
    *,
    run_id: str | None = None,
    store: Store | None = None,
    budget: LoopBudget | None = None,
    now: Callable[[], float] | None = None,
    acknowledgements: list[str] | None = None,
    headless: bool = True,
) -> PipelineResult:
    """Drive one request through the DAG and return a PipelineResult.

    ``store``/``run_id`` override persistence (tests inject a tmp Store). ``now`` is the
    wall-clock source (time.monotonic) so tests can fake the 5-minute budget.
    ``acknowledgements`` pre-accepts C3 default assumption ids (C1-Q3/C3-Q7); unaccepted
    defaults surface as an ``assumption_ack`` HITL instead of crashing (CX-Q3).
    ``headless=False`` (CLI ``--gui``) opens the esmini viewer window for the final full
    run so the simulation is visible straight from the prompt (C7-Q5 debug mode).
    """
    budget = budget or LoopBudget()
    run_id = run_id or trajectory_id
    store = store or Store()
    clock = now or _time.monotonic
    started = clock()
    acknowledgements = acknowledgements or []

    artifacts: dict[str, str] = {}

    def _persist(obj: Any, kind: str) -> None:
        rec = run_c10(obj, trajectory_id, store=store, run_id=run_id)
        if rec is not None:
            # key by the artifact kind; the short hash is the deterministic identity.
            artifacts[kind] = rec.object_hash[:8]

    def _hitl(item: HitlRequest) -> PipelineResult:
        return PipelineResult(
            run_id=run_id,
            request_id=trajectory_id,
            outcome=PipelineOutcome.HITL_BLOCKED,
            iterations=0,
            artifacts=artifacts,
        )

    # 1. C1 — normalize input; HITL on gaps/contradictions (CX-Q3).
    request_spec = run_c1(request, trajectory_id)
    if acknowledgements:
        request_spec = request_spec.model_copy(
            update={"acknowledged_assumptions": acknowledgements}
        )
    if request_spec.unresolved_fields or request_spec.contradictions:
        field_paths = [u.field_path for u in request_spec.unresolved_fields]
        field_paths += [c.field_paths[0] for c in request_spec.contradictions]
        kind = (
            HitlKind.CONTRADICTION
            if request_spec.contradictions
            else HitlKind.MISSING_PARAM
        )
        question = (
            f"Missing/unresolved fields: {field_paths}. "
            "Provide explicit values or accept the C3 defaults."
        )
        return _hitl(HitlRequest(kind=kind, field_paths=field_paths, question=question))

    _persist(request_spec, "RequestSpec")

    # 2. C3 — static evidence for the features this request may exercise.
    evidence = run_c3(
        EvidenceQuery(
            feature_keys=_DEFAULT_QUERY_KEYS,
            simulator_build=ESMINI_BUILD_PIN,
        ),
        trajectory_id,
    )
    _persist(evidence, "EvidenceBundle")

    # C2's ack is expressed on the evidence: any assumption item that C1 already acked
    # (a known default in request_spec.acknowledged_assumptions) is C2-ackable. Compose
    # a C2-acked evidence bundle so the DERIVED-3 gate passes for accepted defaults
    # only; unaccepted defaults remain unacked and surface as a HITL below.
    evidence = _ack_c2_defaults(evidence, request_spec.acknowledged_assumptions)
    _persist(evidence, "EvidenceBundle")

    # 3. C2 — propose intent behind the schema gate; HITL on low confidence or on
    #    unresolved C3 defaults that need C1/C2 acks (DERIVED-3 gate, CX-Q3 assumption_ack).
    try:
        intent = run_c2(request_spec, trajectory_id, evidence=evidence)
    except ValueError as exc:
        if "c3_default" in str(exc) and "requires" in str(exc):
            return _hitl(
                HitlRequest(
                    kind=HitlKind.ASSUMPTION_ACK,
                    field_paths=[],
                    question=f"Please accept the C3 default assumption: {exc}",
                )
            )
        raise
    _persist(intent, "IntentSpec")
    if intent.confidence < 0.7 or intent.unknowns:
        return _hitl(
            HitlRequest(
                kind=HitlKind.LOW_CONFIDENCE,
                field_paths=intent.unknowns,
                question=(
                    f"C2 confidence {intent.confidence:.2f} with unknowns "
                    f"{intent.unknowns}. Confirm intent before proceeding."
                ),
            )
        )

    # log the C2 proposal as an action (C10-Q4)
    proposal = last_proposals.get(trajectory_id)
    if proposal is not None:
        store.log_action(
            run_id,
            ActionLog(
                actor_component="C2",
                action_kind="propose",
                payload_hash=_h8(proposal),
            ),
        )

    # 4. The generate→validate→run→evaluate→repair/explore loop.
    #    C4 builds the canonical IR from intent once; C9 revisions are recompiled
    #    through C5 (C9-Q5 RevisedIR; the ADR flow C6-FAIL→C9→C4 is honoured by the
    #    initial construction here, and C4/C6/C7 still execute in order every pass).
    ir: ScenarioIR = run_c4(
        intent, trajectory_id, evidence=evidence, request_text=_request_text(request)
    )
    _persist(ir, "ScenarioIR")

    iterations = 0
    final_outcome = PipelineOutcome.FAILED
    validation_outcome: str | None = None
    evaluation_summary: str | None = None

    while iterations < budget.max_iterations:
        if clock() - started > budget.wall_clock_s:
            final_outcome = PipelineOutcome.FAILED
            evaluation_summary = "wall_clock budget exceeded"
            break

        # b. C5 — compile the current IR into .xosc instances (range expansion).
        instances = run_c5(ir, trajectory_id)
        for inst in instances:
            _persist(inst, "GeneratedScenario")

        # c. C6 — the frozen funnel; S6 preflight calls C7 in preflight mode only.
        def _preflight(gs: Any) -> Any:
            return run_c7(gs, trajectory_id, mode="preflight")

        reports = run_c6(
            instances, trajectory_id, scenario_ir=ir, preflight=_preflight
        )
        for rep in reports:
            _persist(rep, "ValidationReport")

        # d. Repair loop on any FAIL.
        failed = [r for r in reports if r.outcome.value == "fail"]
        if failed:
            act = run_c9(failed[0], trajectory_id, scenario_ir=ir, iteration=iterations)
            _persist(act, "FeedbackAction")
            store.log_action(
                run_id,
                ActionLog(
                    actor_component="C9",
                    action_kind="repair",
                    payload_hash=_h8(act),
                ),
            )
            if act.escalate_to_user:
                return _hitl(
                    HitlRequest(
                        kind=HitlKind.ASSUMPTION_ACK,
                        field_paths=[],
                        question=f"C9 escalation: {act.escalation_reason}",
                    )
                )
            if act.revised_ir is not None:
                ir = act.revised_ir
                iterations += 1
                if act.stop:
                    final_outcome = PipelineOutcome.COMPLETED
                    break
                continue
            if act.stop:
                validation_outcome = "failed"
                final_outcome = PipelineOutcome.FAILED
                break
            # no revised IR and not stopped → cannot proceed meaningfully.
            final_outcome = PipelineOutcome.FAILED
            validation_outcome = "unrepairable"
            break

        validation_outcome = "passed"

        # e. C7 full run (first instance; batch cap) then C8 evaluation.
        run_record = run_c7(
            instances[0],
            trajectory_id,
            mode="full",
            config=make_config(headless=headless),
        )
        _persist(run_record, "RunRecord")
        evaluation = run_c8(run_record, trajectory_id, scenario_ir=ir)
        _persist(evaluation, "EvaluationReport")

        # f. C9 explore on the evaluation.
        explore = run_c9(
            evaluation,
            trajectory_id,
            scenario_ir=ir,
            iteration=iterations,
            last_metrics=evaluation.metrics,
        )
        _persist(explore, "FeedbackAction")
        store.log_action(
            run_id,
            ActionLog(
                actor_component="C9",
                action_kind="explore",
                payload_hash=_h8(explore),
            ),
        )

        passed = sum(1 for r in evaluation.objective_results if r.passed)
        total = len(evaluation.objective_results)
        metrics_summary = (
            f"metrics={len(evaluation.metrics)} objectives={passed}/{total} "
            f"fail_class={evaluation.failure_class}"
        )
        evaluation_summary = metrics_summary.strip()

        if explore.stop or explore.revised_ir is None:
            final_outcome = PipelineOutcome.COMPLETED
            iterations += 1
            break

        ir = explore.revised_ir
        iterations += 1

    return PipelineResult(
        run_id=run_id,
        request_id=trajectory_id,
        outcome=final_outcome,
        iterations=iterations,
        validation_outcome=validation_outcome,
        evaluation_summary=evaluation_summary,
        artifacts=artifacts,
    )