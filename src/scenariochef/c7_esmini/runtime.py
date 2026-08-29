"""C7 — esmini Simulation: preflight and full execution modes."""

from scenariochef import trace
from scenariochef.scenario_labels import scenario_label_for


def run_c7(generated_scenario, trajectory_id) -> str:
    label = scenario_label_for(trajectory_id)
    out = f"<{label}:RunRecord>"
    trace.emit(8, "C7", "IN", generated_scenario, trajectory_id)
    trace.emit(8, "C7", "OUT", out, trajectory_id)
    return out
