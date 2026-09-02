"""CX orchestration types: HITL gates, loop budget, and pipeline result.

CX is a hardcoded DAG (not an agent — DERIVED-8) that enforces the fixed step sequence,
HITL on gaps/acks only (CX-Q3), and the N≤5 / 5-minute loop budget (CX-Q4). C4, C6 and
C7 are non-skippable (CX-Q5). Tools exposed to CX are the C1–C10 APIs only (CX-Q2).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class HitlKind(StrEnum):  # CX-Q3 kinds only
    MISSING_PARAM = "missing_param"
    CONTRADICTION = "contradiction"
    LOW_CONFIDENCE = "low_confidence"
    ASSUMPTION_ACK = "assumption_ack"


class HitlRequest(BaseModel):
    """A human-in-the-loop question CX raises."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: HitlKind
    field_paths: list[str] = Field(default_factory=list)
    question: str
    options: list[str] | None = None


class LoopBudget(BaseModel):
    """CX loop budget — frozen (CX-Q4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_iterations: int = 5
    wall_clock_s: float = 300


class PipelineOutcome(StrEnum):
    COMPLETED = "completed"
    HITL_BLOCKED = "hitl_blocked"
    FAILED = "failed"


class PipelineResult(BaseModel):
    """The CX pipeline result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    request_id: str
    outcome: PipelineOutcome
    iterations: int = 0
    validation_outcome: str | None = None
    evaluation_summary: str | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)