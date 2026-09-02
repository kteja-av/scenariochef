"""C2 — Scenario Understanding: slot-filling LLM with schema validation."""

from scenariochef import trace
from scenariochef.scenario_labels import scenario_label_for


def run_c2(request_spec, trajectory_id: str) -> str:
    label = scenario_label_for(trajectory_id)
    out = f"<{label}:IntentSpec>"
    trace.emit(3, "C2", "IN", request_spec, trajectory_id)
    trace.emit(3, "C2", "OUT", out, trajectory_id)
    return out
