"""C3 — Scenario Knowledge: typed graph and esmini capability matrix."""

from scenariochef import trace
from scenariochef.scenario_labels import scenario_label_for


def run_c3(query, trajectory_id: str) -> str:
    label = scenario_label_for(trajectory_id)
    out = f"<{label}:EvidenceBundle>"
    trace.emit(4, "C3", "IN", query, trajectory_id)
    trace.emit(4, "C3", "OUT", out, trajectory_id)
    return out
