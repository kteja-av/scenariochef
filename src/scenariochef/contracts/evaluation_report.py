"""C8 → EvaluationReport: deterministic scoring of a run against IR objective stubs.

Thresholds come from the rulebook (`c8_evaluation/rulebook.yaml`), never invented
(C8-Q1). TTC is ALWAYS paired with PET per actor pair (C8-Q4). `data_source` says whether
metrics were computed from OSI or CSV states (C8-Q5).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from .common import TraceMeta, Unit


class MetricName(StrEnum):
    TTC = "ttc"
    PET = "pet"
    COLLISION = "collision"
    COMPLETION = "completion"


class DataSource(StrEnum):
    OSI = "osi"
    CSV = "csv"


class Metric(BaseModel):
    """One computed metric."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: MetricName
    value: float
    unit: Unit
    actor_pair: tuple[str, str] | None = None  # TTC always paired with PET per pair


class ObjectiveResult(BaseModel):
    """Outcome of one IR objective stub against the rulebook."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stub_id: str
    objective_kind: str
    passed: bool
    threshold_source: str  # rulebook entry id
    detail: str = ""


class EvaluationReport(BaseModel):
    """The C8 output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: TraceMeta
    metrics: list[Metric] = []
    objective_results: list[ObjectiveResult] = []
    rulebook_version: str = ""
    data_source: DataSource
    failure_class: str | None = None  # E-taxonomy classification when objectives fail