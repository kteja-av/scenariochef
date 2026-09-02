"""C6 → ValidationReport: the frozen S1–S6 validation funnel result.

Stages run in order; the outcome short-circuits on the first FAIL stage and later stages
are SKIPPED (C6-Q4). S5 is always SKIPPED (C6-Q1). S6 dry-run is RUNS only when any
k3_flag is unknown (C6-Q2). MAP_TOPOLOGY errors are E08-class and escalate to the user in
C9 (DERIVED-16); UNREACHABLE_TRIGGER (E09) is WARN-and-pass (C6-Q3); RUNTIME_COMPAT
(E10) is recorded here for C10 history.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import Severity, TraceMeta


class Stage(StrEnum):
    S1 = "S1"  # structural — XSD validation
    S2 = "S2"  # semantic — entityRef/catalog refs, speed signs, trigger sanity
    S3 = "S3"  # map/topology — lane existence against xodr (E08 lives here)
    S4 = "S4"  # catalog + physical bounds
    S5 = "S5"  # always SKIPPED (C6-Q1)
    S6 = "S6"  # dry-run — RUNS only when any k3_flag is unknown (C6-Q2)


class Status(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIPPED = "skipped"
    RUNS = "runs"


class ErrorTaxonomy(StrEnum):
    XSD_INVALID = "xsd_invalid"
    SEMANTIC_REF = "semantic_ref"
    MAP_TOPOLOGY = "map_topology"  # E08 — escalate to user (DERIVED-16)
    PHYSICAL_BOUNDS = "physical_bounds"
    UNREACHABLE_TRIGGER = "unreachable_trigger"  # E09 — WARN-and-pass (C6-Q3)
    RUNTIME_COMPAT = "runtime_compat"  # E10 — recorded for C10
    INTERNAL = "internal"


class ValidationError(BaseModel):
    """A single validation error."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ErrorTaxonomy
    severity: Severity
    message: str
    location: str = ""  # xpath or field path
    repair_hint: str | None = None


class StageResult(BaseModel):
    """One stage's result within the funnel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: Stage
    status: Status
    errors: list[ValidationError] = Field(default_factory=list)


class ValidationReport(BaseModel):
    """The C6 output: ordered S1..S6 results plus a short-circuit outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: TraceMeta
    stages: list[StageResult] = Field(default_factory=list)
    outcome: Literal[Status.PASS, Status.FAIL]  # short-circuit on first FAIL stage