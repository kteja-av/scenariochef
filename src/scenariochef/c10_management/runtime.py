"""C10 — Scenario Management: persistence, provenance, and artifact storage."""

from scenariochef import trace
from scenariochef.scenario_labels import scenario_label_for


def run_c10(record, trajectory_id) -> str:
    label = scenario_label_for(trajectory_id)
    out = f"<{label}:persisted>"
    trace.emit(11, "C10", "IN", record, trajectory_id)
    trace.emit(11, "C10", "OUT", out, trajectory_id)
    return out
