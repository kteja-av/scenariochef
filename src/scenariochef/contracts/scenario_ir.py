"""C4 → ScenarioIR: the canonical, simulator-independent intermediate representation.

Scenic-like shape (C4-Q1): frame-tagged spawn positions, declarative behaviors,
constraints and objective stubs. Frozen — the canonical fields must never be mutated;
diagnostics ride along on ``suggestions`` which never touch canonical fields
(C4-Q5, DERIVED-10). ``esmini_pin`` comes from the C3 K3 matrix (C3-Q5).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import Position, Range, TraceMeta
from .intent_spec import ActionType, ObjectiveStub, TriggerIntent


class IRHeader(BaseModel):
    """Identity header: which request, which intent revision, which esmini pin."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    intent_spec_hash: str
    esmini_pin: str


class IRMap(BaseModel):
    """Identity-only map reference (C3 provides identity only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    map_asset_id: str
    sha256: str


class IRActor(BaseModel):
    """An actor in the IR. ``spawn`` is a frame-tagged Position (C4-Q2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: str
    bbox_ref: str  # catalog entry id
    spawn: Position
    initial_speed_mps: float


class IRBehavior(BaseModel):
    """A Scenic-like declarative behavior for one actor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor: str
    action: ActionType
    params: dict[str, float | int | str] = Field(default_factory=dict)
    trigger: TriggerIntent | None = None
    start_condition: str = ""


class IRConstraint(BaseModel):
    """A named scalar-or-range constraint with explicit unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    value: float | Range
    unit: str


class IRSuggestion(BaseModel):
    """Diagnostic only — never mutates canonical IR fields (C4-Q5, DERIVED-10)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    field_path: str
    proposed_value: object | None = None


class ScenarioIR(BaseModel):
    """The canonical IR. Frozen; ``suggestions`` ride along without mutating it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: TraceMeta
    header: IRHeader
    map: IRMap
    actors: list[IRActor] = Field(default_factory=list)
    behaviors: list[IRBehavior] = Field(default_factory=list)
    constraints: list[IRConstraint] = Field(default_factory=list)
    objectives: list[ObjectiveStub] = Field(default_factory=list)
    suggestions: list[IRSuggestion] = Field(default_factory=list)
    feature_keys: list[str] = Field(default_factory=list)  # drives C3 K3 + C6 S6