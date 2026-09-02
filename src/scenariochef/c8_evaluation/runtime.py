"""C8 — Observation & Evaluation: metrics and rulebook evaluation."""

from scenariochef import trace
from scenariochef.scenario_labels import scenario_label_for


def run_c8(run_record, trajectory_id: str) -> str:
    label = scenario_label_for(trajectory_id)
    out = f"<{label}:EvaluationReport>"
    trace.emit(9, "C8", "IN", run_record, trajectory_id)
    trace.emit(9, "C8", "OUT", out, trajectory_id)
    return out
