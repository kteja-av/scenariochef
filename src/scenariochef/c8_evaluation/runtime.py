"""C8 — Observation & Evaluation: metrics and rulebook evaluation."""

from scenariochef import trace


def run_c8(run_record) -> str:
    trace.emit(9, "C8", "IN", run_record)
    trace.emit(9, "C8", "OUT", "<EvaluationReport>")
    return "<EvaluationReport>"
