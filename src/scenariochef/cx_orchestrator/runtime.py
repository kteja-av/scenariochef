"""CX — Orchestration: DAG coordinator for C1–C10."""

from pathlib import Path

from scenariochef import trace
from scenariochef.c1_input.runtime import run_c1
from scenariochef.c2_understanding.runtime import run_c2
from scenariochef.c3_knowledge.runtime import run_c3
from scenariochef.c4_ir.runtime import run_c4
from scenariochef.c5_generation.runtime import run_c5
from scenariochef.c6_validation.runtime import run_c6
from scenariochef.c7_esmini.runtime import run_c7
from scenariochef.c8_evaluation.runtime import run_c8
from scenariochef.c9_feedback.runtime import run_c9
from scenariochef.c10_management.runtime import run_c10
from scenariochef.scenario_labels import scenario_label_for

LOG_PATH = Path("artifacts") / "trace_run.log"


def _run_one_trajectory(trajectory_id: str) -> None:
    label = scenario_label_for(trajectory_id)
    trace.emit(1, "CX", "IN", f"<raw_request:{label}>", trajectory_id)
    request_spec = run_c1(f"<raw_request:{label}>", trajectory_id)
    intent_spec = run_c2(request_spec, trajectory_id)
    run_c3("<query>", trajectory_id)
    scenario_ir = run_c4(intent_spec, trajectory_id)
    generated_scenario = run_c5(scenario_ir, trajectory_id)
    run_c6(generated_scenario, trajectory_id)  # type: ignore[arg-type]
    run_record = run_c7(generated_scenario, trajectory_id)  # type: ignore[arg-type]
    evaluation_report = run_c8(run_record, trajectory_id)
    feedback_action = run_c9(evaluation_report, trajectory_id)
    run_c10(feedback_action, trajectory_id)
    trace.emit(12, "CX", "OUT", f"<done:{label}>", trajectory_id)


def run_pipeline(trajectory_count: int = 20) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(LOG_PATH, "w", encoding="utf-8")
    trace.set_log(log_file)
    for n in range(1, trajectory_count + 1):
        _run_one_trajectory(f"REQ-{n:04d}")
    log_file.close()
    print(
        f"Wrote {trajectory_count} trajectories (REQ-0001..REQ-{trajectory_count:04d}) "
        f"to {LOG_PATH}"
    )