"""C9 — Feedback & Improvement: structural repair and parameter exploration."""

from scenariochef import trace
from scenariochef.scenario_labels import scenario_label_for


def run_c9(report, trajectory_id) -> str:
    label = scenario_label_for(trajectory_id)
    out = f"<{label}:FeedbackAction>"
    trace.emit(10, "C9", "IN", report, trajectory_id)
    trace.emit(10, "C9", "OUT", out, trajectory_id)
    return out
