"""C1 → RequestSpec: normalized, schema-validated user request (frozen).

Ingests heterogeneous input (all four Phase-1 modalities) into one validated shape.
Non-empty ``unresolved_fields`` or ``contradictions`` force a HITL gate before C2 runs
(C1-Q2, C1-Q4); ``acknowledged_assumptions`` records which C3 default ids C1 accepted
(C1-Q3).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .common import Modality, TraceMeta

FileKind = Literal["xosc", "xodr", "other"]


class InputFile(BaseModel):
    """A user-supplied file reference ingested by C1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    kind: FileKind
    sha256: str


class UnresolvedField(BaseModel):
    """A parameter that C1 could not resolve (C1-Q2 — ask the user)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_path: str
    reason: str
    options: list[str] | None = None


class Contradiction(BaseModel):
    """A contradictory set of constraints that must be asked about (C1-Q4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_paths: list[str]
    description: str


class RequestSpec(BaseModel):
    """The single validated C1 output. Frozen: downstream components must not mutate it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: TraceMeta
    modality: Modality
    raw: str
    params: dict[str, float | int | str]
    input_files: list[InputFile] = []
    unresolved_fields: list[UnresolvedField] = []
    contradictions: list[Contradiction] = []
    acknowledged_assumptions: list[str] = []