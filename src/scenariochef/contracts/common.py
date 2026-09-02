"""Shared enums, value objects, and hashing helpers for the ScenarioChef contracts.

Every cross-boundary object in the pipeline is a Pydantic model defined in this package.
This module provides the shared vocabulary (modalities, frame tags, support levels,
severities, units) plus small value objects that are reused across contracts:

- ``Position``: a frame-tagged spatial reference (C4-Q2 style: frame is mandatory).
- ``Range``: a closed interval with an explicit unit (C4-Q4 — intervals only).
- ``SlotProvenance``: provenance of a slot value so user-explicit values are never
  rewritten by C2/C9 (C2-Q3, C9-Q6, DERIVED-3).
- ``TraceMeta``: the trace header every cross-boundary object carries (request_id,
  trajectory_id, created_at in ISO-8601 UTC, producing component).

Hashing:
- ``content_hash`` / ``content_hash_eq``: sha256 of the canonical JSON dump (sorted keys).
  This includes the ``meta`` field, so two logically-equal objects produced at different
  times hash differently.
- ``semantic_hash`` / ``semantic_hash_eq``: sha256 of the canonical JSON dump **without**
  the ``meta`` field, used for cross-stage identity comparisons (e.g. verifying an intent
  reached IR unchanged, or that a RevisedIR kept user-explicit slots byte-identical).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    pass


class Modality(StrEnum):  # C1-Q1 — all four Phase-1 modalities
    NL_PARAMS = "nl_params"  # natural language + parameter dict
    XOSC_XODR = "xosc_xodr"  # existing file ingest
    CRASH_NARRATIVE = "crash_narrative"
    MULTIMODAL = "multimodal"


class FrameTag(StrEnum):  # C4-Q2 — mandatory on every position
    ROAD_RELATIVE = "road_relative"  # s/t/h coordinates on a road
    LANE_RELATIVE = "lane_relative"  # road_id + lane_id + s-offset
    CARTESIAN = "cartesian"  # x/y/z world


class SupportLevel(StrEnum):  # C3-Q1/K3 matrix edge values
    SUPPORTS = "supports"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"


class Unit(StrEnum):
    M = "m"
    MPS = "mps"
    MPS2 = "mps2"
    S = "s"
    NONE = "none"


def _utc_now_iso() -> str:
    """Current time as an ISO-8601 UTC string (zero-padded, naive-converted to UTC)."""
    return datetime.now(UTC).isoformat()


class TraceMeta(BaseModel):
    """Trace header attached to every cross-boundary object.

    ``created_at`` defaults to the instant the model is built and is serialized in
    ISO-8601 UTC. ``produced_by`` names the component that emitted the object.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    trajectory_id: str
    created_at: str = Field(default_factory=_utc_now_iso)
    produced_by: str


class Position(BaseModel):
    """A frame-tagged spatial reference (value object, frozen).

    Exactly which fields are meaningful is determined by ``frame`` (C4-Q2):
    - ``lane_relative``  requires ``road_id`` + ``lane_id`` + ``s_m``.
    - ``cartesian``      requires ``x_m`` and ``y_m`` (``z_m`` optional).
    - ``road_relative``  requires ``road_id`` + ``s_m``.

    Untagged (missing frame) or internally-inconsistent positions raise a
    ``ValidationError``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    frame: FrameTag
    road_id: int | None = None
    lane_id: int | None = None
    s_m: float | None = None
    t_m: float | None = None
    x_m: float | None = None
    y_m: float | None = None
    z_m: float | None = None

    @model_validator(mode="after")
    def _check_frame_consistency(self) -> Position:
        frame = self.frame
        required: dict[FrameTag, tuple[str, ...]] = {
            FrameTag.LANE_RELATIVE: ("road_id", "lane_id", "s_m"),
            FrameTag.CARTESIAN: ("x_m", "y_m"),
            FrameTag.ROAD_RELATIVE: ("road_id", "s_m"),
        }
        names = required[frame]
        missing = [n for n in names if getattr(self, n) is None]
        if missing:
            raise ValueError(f"{frame} position requires {', '.join(missing)}")
        return self


class Range(BaseModel):
    """A closed interval ``[min, max]`` with an explicit unit (C4-Q4).

    Only intervals are allowed in Phase 1 — no distributions. Rejects ``min > max``
    and `None` bounds (a bound must always be a float).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    min: float
    max: float
    unit: Unit

    @model_validator(mode="after")
    def _check_min_max(self) -> Range:
        if self.min > self.max:
            raise ValueError(f"Range min {self.min} > max {self.max}")
        return self


SlotSource = Literal["user_explicit", "llm_proposed", "c3_default", "c9_mutation"]


class SlotProvenance(BaseModel):
    """Provenance of a slot value.

    ``user_explicit`` values are never rewritten (C2-Q3, C9-Q6). ```c3_default`` values
    require BOTH ``accepted_by_c1`` and ``accepted_by_c2`` before C4 may bind them
    (DERIVED-3); the ``IntentSpec`` validator enforces this.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: SlotSource
    accepted_by_c1: bool = False
    accepted_by_c2: bool = False


def _canonical_payload(model: BaseModel, *, drop_meta: bool) -> dict[str, Any]:
    """Canonical JSON-able dict for hashing with sorted keys.

    When ``drop_meta`` is set, the ``meta`` TraceMeta field is removed so that two
    logically-equal objects produced at different times hash identically.
    """
    data = model.model_dump()
    if drop_meta:
        data.pop("meta", None)
    return data


def content_hash(model: BaseModel) -> str:
    """sha256 of the model's canonical JSON dump (sorted keys), **including** ``meta``.

    Used for artifact addresses (C10 object_hash) where production time is part of the
    identity. Two equal objects built at different instants hash differently because
    ``meta.created_at`` differs.
    """
    payload = _canonical_payload(model, drop_meta=False)
    return hashlib.sha256(_dump_sorted(payload).encode()).hexdigest()


def semantic_hash(model: BaseModel) -> str:
    """sha256 of the canonical JSON dump **without** the ``meta`` field.

    Used for cross-stage identity comparisons — e.g. verifying an IntentSpec reached IR
    unchanged, or that a C9 RevisedIR kept user-explicit slots byte-identical (C9-Q5/Q6).
    """
    payload = _canonical_payload(model, drop_meta=True)
    return hashlib.sha256(_dump_sorted(payload).encode()).hexdigest()


def content_hash_eq(a: BaseModel, b: BaseModel) -> bool:
    """True when two models hash identically including ``meta``."""
    return content_hash(a) == content_hash(b)


def semantic_hash_eq(a: BaseModel, b: BaseModel) -> bool:
    """True when two models are semantically identical, ignoring ``meta``."""
    return semantic_hash(a) == semantic_hash(b)


def _dump_sorted(payload: dict[str, Any]) -> str:
    """JSON dump with sorted keys (recursively) — deterministic canonical form."""
    import json

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)