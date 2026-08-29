"""C4 — Scenario Representation: Scenic-like intermediate representation (IR)."""

from scenariochef import trace


def run_c4(intent_spec) -> str:
    trace.emit(5, "C4", "IN", intent_spec)
    trace.emit(5, "C4", "OUT", "<ScenarioIR>")
    return "<ScenarioIR>"
