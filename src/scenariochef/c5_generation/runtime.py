"""C5 — Scenario Generation: deterministic scenariogeneration compiler."""

from scenariochef import trace


def run_c5(scenario_ir) -> str:
    trace.emit(6, "C5", "IN", scenario_ir)
    trace.emit(6, "C5", "OUT", "<GeneratedScenario>")
    return "<GeneratedScenario>"
