"""C1 — Scenario Input: ingest and normalize user requirements."""

from scenariochef import trace
from scenariochef.scenario_labels import scenario_label_for


def run_c1(raw_input, trajectory_id) -> str:
    label = scenario_label_for(trajectory_id)
    trace.emit(2, "C1", "IN", raw_input, trajectory_id)
    trace.emit(2, "C1", "OUT", f"<{label}:RequestSpec>", trajectory_id)
    return f"<{label}:RequestSpec>"
