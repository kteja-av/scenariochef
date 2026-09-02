"""C3 → EvidenceBundle: static knowledge retrieval (identity and evidence only).

C3 is static knowledge — no runtime write-back (ARDH-0003), never answers topology
(Q3), never coerces ``unknown`` to ``yes`` (Q2). Evidence is split into buckets that the
pipeline consumes separately (definitions/constraints/examples/compatibility/provenance).
``map_assets`` carries identity only (id/path/sha256/version) — no lane graph.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import SupportLevel, TraceMeta

Authority = Literal["xsd", "esmini_docs", "catalog", "domain"]


class EvidenceItem(BaseModel):
    """One piece of static knowledge retrieved for a feature key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    feature_key: str  # e.g. "osc.action.LaneChange"
    claim: str
    source_ref: str
    authority: Authority  # C3-Q8 ranking
    fact_or_assumption: Literal["fact", "assumption"]
    accepted_by_c1: bool = False
    accepted_by_c2: bool = False
    support: SupportLevel
    simulator_build: str
    excerpt: str = ""


class MapAsset(BaseModel):
    """Identity-only map reference (no topology inside C3 — Q3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    path: str
    sha256: str
    version: str


class EvidenceQuery(BaseModel):
    """C3 query input. C3 never answers topology (Q3); OSC-silent ⇒ unknown (Q2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_keys: list[str] = []
    simulator_build: str
    map_id: str | None = None


class EvidenceBundle(BaseModel):
    """The C3 output: evidence grouped by consumption bucket, plus map identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: TraceMeta
    definitions: list[EvidenceItem] = Field(default_factory=list)
    constraints: list[EvidenceItem] = Field(default_factory=list)
    examples: list[EvidenceItem] = Field(default_factory=list)
    compatibility: list[EvidenceItem] = Field(default_factory=list)
    provenance: list[EvidenceItem] = Field(default_factory=list)
    map_assets: list[MapAsset] = Field(default_factory=list)