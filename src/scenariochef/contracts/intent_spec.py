"""C2 → IntentSpec: slot-filled scenario intent proposed by the LLM (frozen).

Proposals are validated by a deterministic schema gate (C2-Q1/Q4). Never rewrites
user-explicit slots (C2-Q3). Low confidence or non-empty ``unknowns`` route to HITL
(C2-Q2).

DERIVED-3: any slot whose provenance is ``c3_default`` must carry BOTH
``accepted_by_c1`` and ``accepted_by_c2`` acks before C4 may bind it. The model validator
below enforces this at construction time (including nested slots inside actor fields).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import Position, Range, SlotProvenance, TraceMeta


class ActionType(StrEnum):
    """Phase-1 maneuver action subset."""

    SPEED_CHANGE = "speed_change"
    LANE_CHANGE = "lane_change"
    FOLLOW = "follow"
    BRAKE = "brake"
    CUT_IN = "cut_in"
    CROSS_PATH = "cross_path"
    TELEPORT = "teleport"


class TriggerKind(StrEnum):
    TIME = "time"
    SPEED_HEADWAY = "speed_headway"
    REACH_POSITION = "reach_position"
    TIME_HEADWAY = "time_headway"


class ObjectiveKind(StrEnum):
    TTC = "ttc"
    PET = "pet"
    COLLISION = "collision"
    COMPLETION = "completion"
    CUSTOM = "custom"


class ActorRole(StrEnum):
    EGO = "ego"
    TARGET = "target"


# --- Nested slot-bearing models -------------------------------------------


class ActorIntent(BaseModel):
    """An actor's intent: identity, role, spawn position and initial speed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: Literal["vehicle", "pedestrian", "static"]
    role: ActorRole
    initial_position: Position
    initial_speed_mps: float | Range
    slot: SlotProvenance = SlotProvenance(source="llm_proposed")

    @model_validator(mode="after")
    def _check_d3(self) -> ActorIntent:
        _require_c3_acks([self.slot])
        return self


class ManeuverIntent(BaseModel):
    """A maneuver an actor executes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor: str
    action: ActionType
    params: dict[str, float | int | str]
    slot: SlotProvenance = SlotProvenance(source="llm_proposed")

    @model_validator(mode="after")
    def _check_d3(self) -> ManeuverIntent:
        _require_c3_acks([self.slot])
        return self


class TriggerIntent(BaseModel):
    """A trigger condition (time-, headway-, or position-based)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: TriggerKind
    params: dict[str, float | int | str]
    slot: SlotProvenance = SlotProvenance(source="llm_proposed")

    @model_validator(mode="after")
    def _check_d3(self) -> TriggerIntent:
        _require_c3_acks([self.slot])
        return self


class ConstraintIntent(BaseModel):
    """A named scalar-or-range constraint with explicit unit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    value: float | Range
    unit: str


class ObjectiveStub(BaseModel):
    """An objective stub — thresholds live in the C8 rulebook, not here (C4-Q3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: ObjectiveKind
    description: str
    params: dict[str, float | int | str] = {}


def _require_c3_acks(slots: list[SlotProvenance]) -> None:
    """DERIVED-3: a ``c3_default`` slot without both acks is a validation error."""
    for slot in slots:
        if slot.source == "c3_default" and not (slot.accepted_by_c1 and slot.accepted_by_c2):
            raise ValueError("c3_default slot requires accepted_by_c1=True AND accepted_by_c2=True")


# --- IntentSpec ------------------------------------------------------------


class IntentSpec(BaseModel):
    """The validated C2 output. Frozen — a new spec object is produced, never mutated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: TraceMeta
    actors: list[ActorIntent] = []
    maneuvers: list[ManeuverIntent] = []
    triggers: list[TriggerIntent] = []
    constraints: list[ConstraintIntent] = []
    objectives: list[ObjectiveStub] = []
    confidence: float = Field(ge=0.0, le=1.0)
    unknowns: list[str] = []
    c3_evidence_refs: list[str] = []