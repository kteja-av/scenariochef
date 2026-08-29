"""CX — Orchestration: DAG coordinator for C1–C10."""

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


def run_pipeline() -> None:
    trace.emit(1, "CX", "IN", "<raw_request>")
    request_spec = run_c1("<raw_request>")
    intent_spec = run_c2(request_spec)
    run_c3("<query>")
    scenario_ir = run_c4(intent_spec)
    generated_scenario = run_c5(scenario_ir)
    run_c6(generated_scenario)
    run_record = run_c7(generated_scenario)
    evaluation_report = run_c8(run_record)
    feedback_action = run_c9(evaluation_report)
    run_c10(feedback_action)
    trace.emit(12, "CX", "OUT", "<done>")
