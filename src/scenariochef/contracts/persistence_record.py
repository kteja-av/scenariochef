"""C10 → PersistenceRecord: content-addressed artifact + full-lineage bookkeeping.

Every artifact, run, and C2/C9 action is logged under a hash and record id for
full-lineage queries (request→intent→ir→generated→validation→run→evaluation→feedback,
C10-Q4). No dedup (C10-Q5) — all runs are kept (C10-Q3).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import TraceMeta


class ActionLog(BaseModel):
    """A logged C2 proposal or C9 repair/explore action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_component: Literal["C2", "C9"]
    action_kind: Literal["propose", "repair", "explore", "sim_repair"]
    payload_hash: str
    ts: str = ""  # ISO-8601 UTC


class LineageMap(BaseModel):
    """Hashes of every upstream artifact in this run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_hash: str = ""
    intent_hash: str = ""
    ir_hash: str = ""
    generated_hash: str = ""
    validation_hash: str = ""
    run_hash: str = ""
    evaluation_hash: str = ""
    feedback_hash: str = ""


class PersistenceRecord(BaseModel):
    """One content-addressed persisted artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: TraceMeta
    record_id: str  # SC-<run>-<seq>
    run_id: str
    object_kind: str
    object_hash: str
    path: str  # Path as str for JSON round-trip (artifacts/<run_id>/...)
    lineage: LineageMap = Field(default_factory=LineageMap)
    actions: list[ActionLog] = Field(default_factory=list)