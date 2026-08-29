"""C5 — Scenario Generation: deterministic scenariogeneration compiler."""

from scenariochef import trace
from scenariochef.scenario_labels import scenario_label_for


def run_c5(scenario_ir, trajectory_id) -> str:
    label = scenario_label_for(trajectory_id)
    out = f"<{label}:GeneratedScenario>"
    trace.emit(6, "C5", "IN", scenario_ir, trajectory_id)
    trace.emit(6, "C5", "OUT", out, trajectory_id)
    return out
