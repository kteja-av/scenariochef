"""C6 — Scenario Validation: XSD, semantic, and dry-run funnel."""

from scenariochef import trace
from scenariochef.scenario_labels import scenario_label_for


def run_c6(generated_scenario, trajectory_id: str) -> str:
    label = scenario_label_for(trajectory_id)
    out = f"<{label}:ValidationReport>"
    trace.emit(7, "C6", "IN", generated_scenario, trajectory_id)
    trace.emit(7, "C6", "OUT", out, trajectory_id)
    return out
