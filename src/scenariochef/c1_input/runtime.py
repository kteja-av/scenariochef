"""C1 — Scenario Input: ingest and normalize user requirements."""

from scenariochef import trace


def run_c1(raw_input) -> str:
    trace.emit(2, "C1", "IN", raw_input)
    trace.emit(2, "C1", "OUT", "<RequestSpec>")
    return "<RequestSpec>"
