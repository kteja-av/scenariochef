"""C5 → GeneratedScenario: a concrete OpenSCENARIO artifact instance.

C5 expands IR ranges into a deterministic list of N concrete instances (cap 8 per range
axis, 32 total, deterministic order). ``k3_flags`` surface features that K3 marks
unknown/unsupported so C6 can dry-run them (C5-Q3 — never substitute). ``suggestions``
pass through untouched from the IR (DERIVED-13).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import Range, SupportLevel, TraceMeta
from .scenario_ir import IRSuggestion


class XoscArtifact(BaseModel):
    """The generated OpenSCENARIO file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str
    path: str | None = None  # Path str for JSON-serializability
    sha256: str


class XodrArtifact(BaseModel):
    """An optional emitted OpenDRIVE map."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str
    path: str | None = None
    sha256: str


class ParameterBinding(BaseModel):
    """A concrete value chosen for range expansion (C5-Q2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    param: str
    value: float | int | str
    source_range: Range | None = None
    ir_path: str = ""


class K3Flag(BaseModel):
    """A feature whose K3 support is unknown/unsupported (C5-Q3 — never substituted)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_key: str
    support: SupportLevel


class GeneratedScenario(BaseModel):
    """One concrete, executable scenario instance produced by C5."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: TraceMeta
    scenario_name: str
    xosc: XoscArtifact
    xodr: XodrArtifact | None = None
    parameter_bindings: list[ParameterBinding] = Field(default_factory=list)
    variation_index: int = 0
    variation_count: int = 1
    k3_flags: list[K3Flag] = Field(default_factory=list)
    suggestions: list[IRSuggestion] = Field(default_factory=list)