"""C3 — Scenario Knowledge: retrieval + rules over the typed graph / K3 capability matrix.

C3 is a pure read service over static curated knowledge (``store.py``). It never writes
at runtime (C3-Q4/ARCH-0003), never answers map topology (C3-Q3), never uses an LLM
(ARCH-0001), and never coerces an esmini-silent feature to ``supports``/``partial``
(C3-Q2). OSC-yes-but-esmini-silent ⇒ ``SupportLevel.UNKNOWN``; execution authority is the
C6/C7 dry-run, not retrieval (DERIVED-1/DERIVED-2).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from scenariochef import trace

from ..contracts.common import SupportLevel, TraceMeta, semantic_hash
from ..contracts.evidence_bundle import (
    Authority,
    EvidenceBundle,
    EvidenceItem,
    EvidenceQuery,
    MapAsset,
)
from ..contracts.generated_scenario import K3Flag
from .store import (
    ESMINI_BUILD_PIN,
    definitions_ordering_key,
    get_store,
)

if TYPE_CHECKING:
    pass

_PRODUCER = "C3"
_GAP_CLAIM = "no evidence"
# Authority is a closed contract Literal ("xsd"|"esmini_docs"|"catalog"|"domain"); there is
# no "none" value. A total gap (unknown feature key) therefore cites the lowest-priority
# category, ``domain``, as a knowledge-note rather than a factual claim (C3-Q8). C3 cannot
# extend the contract (it is frozen in contracts/evidence_bundle.py).
_GAP_AUTHORITY: Authority = "domain"

# TraceMeta.created_at is part of the contract (defaults to the current wall-clock instant,
# common.py). C3 must be deterministic (no wall-clock reads in logic), so every C3 bundle
# ties created_at to this fixed sentinel; repeated calls are byte-identical and reproducible.
_DETERMINISTIC_CREATED_AT = "2000-01-01T00:00:00+00:00"

# A string query asking about lane existence is topology (E08/C6 territory), never
# answered inside C3 (C3-Q3). Pattern: "lane" + a digit + "exist".
_TOPOLOGY_LANE_EXIST = re.compile(r"lane\s*\d+\s*exist", re.IGNORECASE)


def _request_id(trajectory_id: str) -> str:
    """Stable, deterministic request id for the bundle's trace header."""
    return f"{trajectory_id}:C3"


def _trace_meta(trajectory_id: str) -> TraceMeta:
    return TraceMeta(
        request_id=_request_id(trajectory_id),
        trajectory_id=trajectory_id,
        created_at=_DETERMINISTIC_CREATED_AT,
        produced_by=_PRODUCER,
    )


def _bag_from_string(raw: str) -> list[str]:
    """Whitespace-split bag of feature keys, tolerating dotted keys (no dots stripped)."""
    return [tok for tok in raw.split() if tok]


def _looks_like_topology_query(raw: str) -> bool:
    """True when a text query is a C6-owned topology question (lane existence)."""
    return bool(_TOPOLOGY_LANE_EXIST.search(raw))


def _definition_item(feature_key: str, standard_version: str, claim: str) -> EvidenceItem:
    """Syntax/definition claim — such claims are OSC XSD authority (DERIVED-1)."""
    return EvidenceItem(
        id=f"def:{feature_key}",
        feature_key=feature_key,
        claim=claim,
        source_ref=f"OSC {standard_version} XSD",
        authority="xsd",
        fact_or_assumption="fact",
        support=SupportLevel.UNKNOWN,  # definition bucket does not assert execution
        simulator_build=ESMINI_BUILD_PIN,
        excerpt="Defined in the OpenSCENARIO standard schema (syntax/definition claim).",
    )


def _docs_item(
    feature_key: str, source_ref: str, authority: Authority, excerpt: str
) -> EvidenceItem:
    """esmini-docs/domain evidence hanging off a feature node."""
    return EvidenceItem(
        id=f"docs:{feature_key}:{authority}",
        feature_key=feature_key,
        claim="Support/evidence note from curated source.",
        source_ref=source_ref,
        authority=authority,
        fact_or_assumption="fact",
        support=SupportLevel.UNKNOWN,
        simulator_build=ESMINI_BUILD_PIN,
        excerpt=excerpt,
    )


def _compat_item(
    feature_key: str, level: SupportLevel, source_ref: str, authority: Authority
) -> EvidenceItem:
    """K3 capability-matrix decision for one feature under the pinned build."""
    return EvidenceItem(
        id=f"support:{feature_key}",
        feature_key=feature_key,
        claim=f"esmini {ESMINI_BUILD_PIN} support for {feature_key} is {level.value}.",
        source_ref=source_ref,
        authority=authority,
        fact_or_assumption="fact",
        support=level,
        simulator_build=ESMINI_BUILD_PIN,
        excerpt=(source_ref or ""),
    )


def _gap_item(feature_key: str) -> EvidenceItem:
    """Unknown feature key ⇒ knowledge gap: support=unknown, no evidence, assumption."""
    return EvidenceItem(
        id=f"gap:{feature_key}",
        feature_key=feature_key,
        claim=_GAP_CLAIM,
        source_ref="domain note — no curated evidence",
        authority=_GAP_AUTHORITY,
        fact_or_assumption="assumption",
        support=SupportLevel.UNKNOWN,
        simulator_build=ESMINI_BUILD_PIN,
        excerpt="No curated evidence for this feature key in the ACL knowledge store.",
    )


def _domain_rule_item(rule_id: str, claim: str, source_ref: str, excerpt: str = "") -> EvidenceItem:
    """Assumption-class default/typical (Q7/DERIVED-3): C1 and C2 must ack before use."""
    return EvidenceItem(
        id=f"constraint:{rule_id}",
        feature_key=rule_id,
        claim=claim,
        source_ref=source_ref,
        authority="domain",
        fact_or_assumption="assumption",
        accepted_by_c1=False,
        accepted_by_c2=False,
        support=SupportLevel.UNKNOWN,
        simulator_build=ESMINI_BUILD_PIN,
        excerpt=excerpt,
    )


def _map_provenance_item(asset: MapAsset) -> EvidenceItem:
    """Provenance note: map identity only — topology questions are out of scope (C3-Q3)."""
    return EvidenceItem(
        id=f"map:{asset.id}",
        feature_key=f"map:{asset.id}",
        claim=f"Map asset {asset.id} identified (identity only; topology owned by C6/E08).",
        source_ref="C3 knowledge store — RODR map index",
        authority="catalog",
        fact_or_assumption="fact",
        support=SupportLevel.UNKNOWN,
        simulator_build=ESMINI_BUILD_PIN,
        excerpt=(
            f"id={asset.id} path={asset.path} sha256={asset.sha256} version={asset.version}"
        ),
    )


def query_support(
    feature_keys: list[str], build: str = ESMINI_BUILD_PIN
) -> list[K3Flag]:
    """K3 support flags for the requested features under ``build`` (C5-Q3 input)."""
    store = get_store()
    flags: list[K3Flag] = []
    for key in feature_keys:
        level = store.get_support(key, build)
        if level is None:
            # Not found or not edge => unknown, never coerced to supports/partial (C3-Q2).
            level = SupportLevel.UNKNOWN
        flags.append(K3Flag(feature_key=key, support=level))
    return flags


def query_map(map_id: str) -> MapAsset | None:
    """Return map identity only (id/path/sha256/version) — never topology (C3-Q3)."""
    return get_store().get_map(map_id)


def query_definitions(keys: list[str]) -> list[EvidenceItem]:
    """Definition/evidence items for the requested feature keys.

    Ordering (documented rule): definitions bucket sorts by authority rank ascending —
    ``xsd`` outranks ``esmini_docs`` (C3-Q8); ties keep data/YAML order. Unknown keys
    yield a gap item (support=unknown, claim "no evidence").
    """
    store = get_store()
    items: list[EvidenceItem] = []
    for key in keys:
        feature = store.get_feature(key)
        if feature is None:
            items.append(_gap_item(key))
            continue
        items.append(
            _definition_item(
                key,
                feature.standard_version,
                f"{key} is an OpenSCENARIO element: {feature.description}",
            )
        )
        for edge in feature.support_edges:
            items.append(
                _docs_item(key, edge.source_ref, edge.authority, edge.excerpt)
            )
    items.sort(key=lambda i: definitions_ordering_key(i.authority))
    return items


def _assemble_bundle(
    feature_keys: list[str],
    simulator_build: str,
    map_id: str | None,
    trajectory_id: str,
) -> EvidenceBundle:
    store = get_store()

    definitions: list[EvidenceItem] = []
    compatibility: list[EvidenceItem] = []
    for key in feature_keys:
        feature = store.get_feature(key)
        if feature is None:
            definitions.append(_gap_item(key))
            compatibility.append(_gap_item(key))
            continue
        definitions.append(
            _definition_item(
                key,
                feature.standard_version,
                f"{key} is an OpenSCENARIO element: {feature.description}",
            )
        )
        edge = store.get_support_edge(key, simulator_build)
        if edge is None:
            # OSC-valid but esmini silent => unknown, never coerced (C3-Q2).
            compatibility.append(
                _compat_item(key, SupportLevel.UNKNOWN, "no curated edge", "esmini_docs")
            )
        else:
            definitions.append(_docs_item(key, edge.source_ref, edge.authority, edge.excerpt))
            compatibility.append(
                _compat_item(key, edge.level, edge.source_ref, edge.authority)
            )
    definitions.sort(key=lambda i: definitions_ordering_key(i.authority))

    # Domain rules are assumption-class constraints (Q7/DERIVED-3); acks are never set here.
    constraints: list[EvidenceItem] = []
    for rule in store.domain_rules:
        constraints.append(
            _domain_rule_item(
                rule.id,
                rule.claim,
                rule.source_ref,
                excerpt=f"{rule.claim} (domain assumption)",
            )
        )

    provenance: list[EvidenceItem] = []
    map_assets: list[MapAsset] = []
    if map_id is not None:
        asset = store.get_map(map_id)
        if asset is not None:
            map_assets.append(asset)
            provenance.append(_map_provenance_item(asset))

    return EvidenceBundle(
        meta=_trace_meta(trajectory_id),
        definitions=definitions,
        constraints=constraints,
        examples=[],
        compatibility=compatibility,
        provenance=provenance,
        map_assets=map_assets,
    )


def run_c3(query: EvidenceQuery | str, trajectory_id: str = "REQ-0001") -> EvidenceBundle:
    """Entry point: resolve a query to an EvidenceBundle (deterministic, read-only).

    A ``str`` query is accepted for backward compatibility with the skeleton: it is
    treated as a whitespace-split bag of feature keys, tolerating dotted keys such as
    ``osc.action.LaneChange``. A topology-style string ("does lane 3 exist") returns
    provenance-only evidence — C3 never answers topology (C3-Q3).
    """
    feature_keys: list[str]
    map_id: str | None
    if isinstance(query, EvidenceQuery):
        feature_keys = list(query.feature_keys)
        simulator_build = query.simulator_build
        map_id = query.map_id
    else:
        simulator_build = ESMINI_BUILD_PIN
        map_id = None
        if _looks_like_topology_query(query):
            # C6 owns topology (C3-Q3/DERIVED-5): answer with map identity provenance only.
            bundle = EvidenceBundle(
                meta=_trace_meta(trajectory_id),
                definitions=[],
                constraints=[],
                examples=[],
                compatibility=[],
                provenance=[
                    EvidenceItem(
                        id="map:topology-declined",
                        feature_key="map:topology",
                        claim="Topology questions (e.g. lane existence) are owned by C6/E08; "
                        "C3 returns map identity only (C3-Q3/DERIVED-5).",
                        source_ref="C3 knowledge store — RODR Q-MAP policy",
                        authority="domain",
                        fact_or_assumption="fact",
                        support=SupportLevel.UNKNOWN,
                        simulator_build=ESMINI_BUILD_PIN,
                        excerpt="No lane connectivity information lives in C3.",
                    )
                ],
                map_assets=[],
            )
            _emit_trace(bundle, query, trajectory_id)
            return bundle
        feature_keys = _bag_from_string(query)

    bundle = _assemble_bundle(feature_keys, simulator_build, map_id, trajectory_id)
    _emit_trace(bundle, query, trajectory_id)
    return bundle


def _emit_trace(bundle: EvidenceBundle, query: EvidenceQuery | str, trajectory_id: str) -> None:
    token_in = (
        query if isinstance(query, str) else f"EvidenceQuery:<{', '.join(query.feature_keys)}>"
    )
    # semantic_hash drops meta, so this token is stable for equal bundles.
    bundle_digest = semantic_hash(bundle)[:8]
    trace.emit(4, "C3", "IN", token_in, trajectory_id)
    trace.emit(4, "C3", "OUT", f"<EvidenceBundle:{bundle_digest}>", trajectory_id)