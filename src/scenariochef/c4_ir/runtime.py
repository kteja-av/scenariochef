"""C4 — Scenario Representation: Scenic-like intermediate representation (IR)."""

from scenariochef import trace
from scenariochef.scenario_labels import scenario_label_for


def run_c4(intent_spec: str, trajectory_id: str) -> str:
    label = scenario_label_for(trajectory_id)
    out = f"<{label}:ScenarioIR>"
    trace.emit(5, "C4", "IN", intent_spec, trajectory_id)
    trace.emit(5, "C4", "OUT", out, trajectory_id)
    return out
