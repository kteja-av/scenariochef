"""C3 — static knowledge store: typed graph + esmini capability matrix (K3).

The store is loaded once from ``data/knowledge.yaml`` (functools-cached) into typed
graph nodes. It is a pure retrieval layer: every accessor is deterministic and
side-effect-free — the store is never written at runtime (C3-Q4, ARCH-0003).

Map nodes carry identity only (id/path/sha256/version); no lane graph and no topology
queries live here (C3-Q3). The capability matrix (K3) is keyed by the pinned esmini
build id (C3-Q5).
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import TYPE_CHECKING

# PyYAML ships no type stubs and mypy's strict mode flags the untyped import; type
# stubs are not part of the project dev deps (pyproject.toml is out of scope here).
import yaml  # type: ignore[import-untyped]

from ..contracts.common import SupportLevel
from ..contracts.evidence_bundle import Authority, MapAsset

if TYPE_CHECKING:
    pass

ESMINI_BUILD_PIN = "esmini-0.10"

_DATA_DIR = Path(__file__).parent / "data"
_KNOWLEDGE_YAML = _DATA_DIR / "knowledge.yaml"

# sha256 placeholder: all-zero hex, documented (never a real digest).
MAP_SHA256_PLACEHOLDER = "0" * 64

# Authority ranking (C3-Q8 / DERIVED-1), lowest number = highest priority.
_AUTHORITY_ORDER = ("xsd", "esmini_docs", "catalog", "domain")


class SimulatorBuild:
    """A pinned simulator build (C3-Q5). K3 edges are keyed by the build id."""

    __slots__ = ("id", "standard_version", "note")

    def __init__(self, id_: str, standard_version: str, note: str = "") -> None:
        self.id = id_
        self.standard_version = standard_version
        self.note = note


class SupportEdge:
    """A K3 edge: build + support level + evidence blob (source_ref/authority/excerpt)."""

    __slots__ = ("build", "level", "source_ref", "authority", "excerpt")

    def __init__(
        self,
        build: str,
        level: SupportLevel,
        source_ref: str,
        authority: Authority,
        excerpt: str,
    ) -> None:
        self.build = build
        self.level = level
        self.source_ref = source_ref
        self.authority = authority
        self.excerpt = excerpt


class Feature:
    """A knowledge node for one OSC feature key (e.g. ``osc.action.LaneChange``)."""

    __slots__ = ("key", "description", "standard_version", "support_edges")

    def __init__(self, key: str, description: str, standard_version: str) -> None:
        self.key = key
        self.description = description
        self.standard_version = standard_version
        self.support_edges: list[SupportEdge] = []


class CatalogEntry:
    """A cataloged actor: name + bbox + vehicle class + authority."""

    __slots__ = (
        "name",
        "bbox_width_m",
        "bbox_length_m",
        "bbox_height_m",
        "vehicle_class",
        "authority",
    )

    def __init__(
        self,
        name: str,
        bbox_width_m: float,
        bbox_length_m: float,
        bbox_height_m: float,
        vehicle_class: str,
        authority: Authority,
    ) -> None:
        self.name = name
        self.bbox_width_m = bbox_width_m
        self.bbox_length_m = bbox_length_m
        self.bbox_height_m = bbox_height_m
        self.vehicle_class = vehicle_class
        self.authority = authority


class Catalog:
    """A catalog (e.g. ``catalogs/vehicles.xml``) holding CatalogEntries."""

    __slots__ = ("id", "standard_version", "entries")

    def __init__(self, id_: str, standard_version: str) -> None:
        self.id = id_
        self.standard_version = standard_version
        self.entries: dict[str, CatalogEntry] = {}


class DomainRule:
    """An assumption-class rule or typical (Q7/DERIVED-3). Always an assumption unless
    catalog-backed."""

    __slots__ = (
        "id",
        "claim",
        "source_ref",
        "authority",
        "fact_or_assumption",
        "value",
        "value_min",
        "value_max",
        "unit",
    )

    def __init__(
        self,
        id_: str,
        claim: str,
        source_ref: str,
        authority: Authority,
        fact_or_assumption: str,
        value: float | None = None,
        value_min: float | None = None,
        value_max: float | None = None,
        unit: str = "",
    ) -> None:
        self.id = id_
        self.claim = claim
        self.source_ref = source_ref
        self.authority = authority
        self.fact_or_assumption = fact_or_assumption
        self.value = value
        self.value_min = value_min
        self.value_max = value_max
        self.unit = unit


class KnowledgeStore:
    """In-memory typed graph loaded once from the curated YAML (static, read-only)."""

    def __init__(
        self,
        builds: list[SimulatorBuild],
        maps: list[MapAsset],
        features: list[Feature],
        catalogs: list[Catalog],
        domain_rules: list[DomainRule],
    ) -> None:
        self.builds = builds
        self.maps = maps
        self.features = features
        self.catalogs = catalogs
        self.domain_rules = domain_rules

        self._build_by_id = {b.id: b for b in builds}
        self._map_by_id = {m.id: m for m in maps}
        self._feature_by_key = {f.key: f for f in features}
        self._catalog_by_id = {c.id: c for c in catalogs}
        # Flatten all catalog entries across catalogs by entry name.
        self._entry_by_name: dict[str, CatalogEntry] = {}
        for cat in catalogs:
            self._entry_by_name.update(cat.entries)
        self._rule_by_id = {r.id: r for r in domain_rules}

    # ---- pure read APIs ---------------------------------------------------

    def get_feature(self, key: str) -> Feature | None:
        return self._feature_by_key.get(key)

    def get_support(self, feature_key: str, build: str) -> SupportLevel | None:
        """Support level for a feature under a build, or None if the feature is absent."""
        feature = self._feature_by_key.get(feature_key)
        if feature is None:
            return None
        for edge in feature.support_edges:
            if edge.build == build:
                return edge.level
        return None

    def get_catalog_entry(self, name: str) -> CatalogEntry | None:
        return self._entry_by_name.get(name)

    def get_map(self, map_id: str) -> MapAsset | None:
        return self._map_by_id.get(map_id)

    def get_domain_rule(self, rule_id: str) -> DomainRule | None:
        return self._rule_by_id.get(rule_id)

    def get_support_edge(self, feature_key: str, build: str) -> SupportEdge | None:
        """Return the support edge (support + evidence blob) for a feature under a build."""
        feature = self._feature_by_key.get(feature_key)
        if feature is None:
            return None
        for edge in feature.support_edges:
            if edge.build == build:
                return edge
        return None

    def features_with_support(self, level: str, build: str = ESMINI_BUILD_PIN) -> list[Feature]:
        """All features whose K3 edge for ``build`` equals ``level`` (canonical support name)."""
        out = []
        for feature in self.features:
            for edge in feature.support_edges:
                if edge.build == build and edge.level.value == level:
                    out.append(feature)
                    break
        return out


@functools.lru_cache(maxsize=1)
def _load_store() -> KnowledgeStore:
    """Build the store once from ``data/knowledge.yaml``. Deterministic, no file writes."""
    with _KNOWLEDGE_YAML.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    builds = [
        SimulatorBuild(b["id"], b.get("standard_version", ""), b.get("note", ""))
        for b in data.get("simulator_builds", [])
    ]

    maps = [
        MapAsset(
            id=m["id"],
            path=m["path"],
            sha256=m["sha256"],
            version=m["version"],
        )
        for m in data.get("map_assets", [])
    ]

    features = []
    for f in data.get("features", []):
        feature = Feature(f["key"], f.get("description", ""), f.get("standard_version", ""))
        for e in f.get("support_edges", []):
            feature.support_edges.append(
                SupportEdge(
                    build=e["build"],
                    level=SupportLevel(e["level"]),
                    source_ref=e["source_ref"],
                    authority=e["authority"],
                    excerpt=e.get("excerpt", ""),
                )
            )
        features.append(feature)

    catalogs = []
    for cat in data.get("catalogs", []):
        catalog = Catalog(cat["id"], cat.get("standard_version", ""))
        for ent in cat.get("entries", []):
            entry = CatalogEntry(
                name=ent["name"],
                bbox_width_m=float(ent["bbox_width_m"]),
                bbox_length_m=float(ent["bbox_length_m"]),
                bbox_height_m=float(ent["bbox_height_m"]),
                vehicle_class=ent["vehicle_class"],
                authority=ent["authority"],
            )
            catalog.entries[entry.name] = entry
        catalogs.append(catalog)

    domain_rules = []
    for r in data.get("domain_rules", []):
        domain_rules.append(
            DomainRule(
                id_=r["id"],
                claim=r["claim"],
                source_ref=r["source_ref"],
                authority=r["authority"],
                fact_or_assumption=r.get("fact_or_assumption", "assumption"),
                value=r.get("value"),
                value_min=r.get("value_min"),
                value_max=r.get("value_max"),
                unit=r.get("unit", ""),
            )
        )

    return KnowledgeStore(builds, maps, features, catalogs, domain_rules)


def get_store() -> KnowledgeStore:
    """Return the singleton store (cached; load happens at most once)."""
    return _load_store()


def definitions_ordering_key(authority: Authority) -> int:
    """Ranking key so lower numbers sort first — highest authority (xsd) first (C3-Q8)."""
    try:
        return _AUTHORITY_ORDER.index(authority)
    except ValueError:
        # Unknown authority placed last deterministically.
        return len(_AUTHORITY_ORDER)