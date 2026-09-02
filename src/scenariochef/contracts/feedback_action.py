"""C9 → FeedbackAction: deterministic repair or explore (service on the CX DAG).

Not a second LLM agent (DERIVED-8). ``revised_ir`` is always a NEW object — never
in-place mutation — and user-explicit slots must stay byte-identical (C9-Q5/Q6).
E08-class map-topology FAILs set ``escalate_to_user`` instead of repairing
(DERIVED-16). ``stop`` honors the loop budget (C9-Q4).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import TraceMeta
from .generated_scenario import ParameterBinding
from .scenario_ir import ScenarioIR


class FeedbackAction(BaseModel):
    """The C9 output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: TraceMeta
    type: Literal["repair", "explore"]  # C9-Q1 hard split
    revised_ir: ScenarioIR | None = None  # a NEW object, user_explicit slots byte-identical
    rationale: str = ""
    iteration: int = 0  # 0-based
    escalate_to_user: bool = False
    escalation_reason: str | None = None
    stop: bool = False
    stop_reason: Literal["max_iterations", "no_metric_gain", "repaired", "none"] = "none"
    param_sweep: list[ParameterBinding] = Field(default_factory=list)  # explore candidates