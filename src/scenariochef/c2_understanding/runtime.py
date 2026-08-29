"""C2 — Scenario Understanding: slot-filling LLM with schema validation."""

from scenariochef import trace


def run_c2(request_spec) -> str:
    trace.emit(3, "C2", "IN", request_spec)
    trace.emit(3, "C2", "OUT", "<IntentSpec>")
    return "<IntentSpec>"
