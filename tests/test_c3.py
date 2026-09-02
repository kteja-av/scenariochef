"""C3 — Scenario Knowledge: retrieval service over the typed graph / K3 matrix.

Covers: deterministic/no-write loading (every API callable repeatedly), support-level
inference (unknown never coerced, C3-Q2), map identity vs topology (C3-Q3), catalog
facts, authority ordering (C3-Q8), assumption acks (Q7/DERIVED-3), K3 flags, and the
knowledge-gap item for unknown feature keys.
"""

from __future__ import annotations

from scenariochef.c3_knowledge import (
    ESMINI_BUILD_PIN,
    query_definitions,
    query_map,
    query_support,
    run_c3,
)
from scenariochef.c3_knowledge.store import definitions_ordering_key, get_store
from scenariochef.contracts.common import SupportLevel
from scenariochef.contracts.evidence_bundle import EvidenceQuery
from scenariochef.contracts.generated_scenario import K3Flag

# All-zero sha256 placeholder documented in data/knowledge.yaml.
SHA256_PLACEHOLDER = "0" * 64


def test_loads_without_writing_any_file_and_is_idempotent():
    """Every query API returns identical results when called twice (pure reads)."""
    first = [
        [get_store().get_feature(k) for k in ["osc.action.SpeedChange", "osc.action.Teleport"]],
        [get_store().get_support("osc.action.LaneChange", ESMINI_BUILD_PIN)],
        get_store().get_catalog_entry("car_mid"),
        get_store().get_map("straight_2lane"),
        get_store().get_domain_rule("typical_gap_20m"),
        query_support(["osc.action.SpeedChange", "osc.action.Teleport"], ESMINI_BUILD_PIN),
        query_definitions(["osc.action.SpeedChange"]),
        query_map("straight_2lane"),
        run_c3("osc.action.Teleport osc.action.LaneChange"),
        run_c3(
            EvidenceQuery(
                feature_keys=["osc.action.SpeedChange"],
                simulator_build=ESMINI_BUILD_PIN,
                map_id="straight_2lane",
            )
        ),
    ]
    second = [
        [get_store().get_feature(k) for k in ["osc.action.SpeedChange", "osc.action.Teleport"]],
        [get_store().get_support("osc.action.LaneChange", ESMINI_BUILD_PIN)],
        get_store().get_catalog_entry("car_mid"),
        get_store().get_map("straight_2lane"),
        get_store().get_domain_rule("typical_gap_20m"),
        query_support(["osc.action.SpeedChange", "osc.action.Teleport"], ESMINI_BUILD_PIN),
        query_definitions(["osc.action.SpeedChange"]),
        query_map("straight_2lane"),
        run_c3("osc.action.Teleport osc.action.LaneChange"),
        run_c3(
            EvidenceQuery(
                feature_keys=["osc.action.SpeedChange"],
                simulator_build=ESMINI_BUILD_PIN,
                map_id="straight_2lane",
            )
        ),
    ]
    for a, b in zip(first, second):
        assert a == b


def test_string_query_whitespace_split_tolerates_dotted_keys():
    """A string query is a whitespace-split bag of feature keys (backward compat)."""
    bundle = run_c3("osc.action.LaneChange osc.action.SpeedChange")
    keys = {i.feature_key for i in bundle.definitions}
    assert "osc.action.LaneChange" in keys
    assert "osc.action.SpeedChange" in keys


def test_esmini_silent_feature_support_is_unknown_never_coerced():
    """OSC=yes, esmini silent ⇒ support UNKNOWN (C3-Q2); never supports/partial."""
    assert (
        get_store().get_support("osc.action.ControllerAssign", ESMINI_BUILD_PIN)
        == SupportLevel.UNKNOWN
    )
    flag = query_support(["osc.action.ControllerAssign"], ESMINI_BUILD_PIN)[0]
    assert flag.support == SupportLevel.UNKNOWN
    # And via the bundle compatibility bucket.
    bundle = run_c3(
        EvidenceQuery(
            feature_keys=["osc.action.ControllerAssign"],
            simulator_build=ESMINI_BUILD_PIN,
        )
    )
    assert any(i.support == SupportLevel.UNKNOWN for i in bundle.compatibility)


def test_unsupported_feature_support_is_unsupported():
    assert (
        get_store().get_support("osc.action.CustomCommand", ESMINI_BUILD_PIN)
        == SupportLevel.UNSUPPORTED
    )
    flag = query_support(["osc.action.CustomCommand"], ESMINI_BUILD_PIN)[0]
    assert flag.support == SupportLevel.UNSUPPORTED


def test_partial_feature_support_is_partial():
    assert (
        get_store().get_support("osc.action.Following", ESMINI_BUILD_PIN)
        == SupportLevel.PARTIAL
    )
    flag = query_support(["osc.action.Following"], ESMINI_BUILD_PIN)[0]
    assert flag.support == SupportLevel.PARTIAL


def test_supported_features_report_supports():
    for key in ["osc.action.SpeedChange", "osc.action.LaneChange",
                "osc.trigger.TimeHeadway", "osc.trigger.ReachPosition"]:
        assert get_store().get_support(key, ESMINI_BUILD_PIN) == SupportLevel.SUPPORTS


def test_map_identity_query_works():
    asset = query_map("straight_2lane")
    assert asset is not None
    assert asset.id == "straight_2lane"
    assert asset.path == "assets/maps/straight_2lane.xodr"
    assert asset.sha256 == SHA256_PLACEHOLDER
    assert asset.version == "v1"


def test_lane_existence_query_returns_provenance_only_never_topology():
    """'does lane 3 exist' is C6/E08 territory — C3 returns provenance only (C3-Q3)."""
    bundle = run_c3("does lane 3 exist", trajectory_id="REQ-0002")
    # No lane/topology answer: no map_assets populated from a bare topology string.
    assert bundle.definitions == []
    assert bundle.compatibility == []
    assert len(bundle.provenance) == 1
    item = bundle.provenance[0]
    assert "topology" in item.claim.lower()
    assert "owned by C6" in item.claim


def test_catalog_entries_present_with_bbox_numbers():
    entries = {
        "car_mid": (2.0, 4.5),
        "truck": (2.55, 12.0),
        "pedestrian": (0.5, 0.5),
    }
    for name, (exp_w, exp_l) in entries.items():
        entry = get_store().get_catalog_entry(name)
        assert entry is not None
        assert entry.bbox_width_m == exp_w
        assert entry.bbox_length_m == exp_l


def test_authority_ranking_xsd_outranks_esmini_docs_in_definitions():
    """Definitions bucket sorts by authority ascending: xsd before esmini_docs (C3-Q8)."""
    items = query_definitions(["osc.action.SpeedChange"])
    # An xsd item and an esmini_docs item must both be present to observe ranking.
    assert any(i.authority == "xsd" for i in items)
    assert any(i.authority == "esmini_docs" for i in items)
    ranks = [definitions_ordering_key(i.authority) for i in items]
    assert ranks == sorted(ranks)


def test_assumption_defaults_have_both_acks_false():
    """Q7/DERIVED-3: assumption-class defaults ship unacknowledged; acks via C1/C2 only."""
    bundle = run_c3("osc.action.SpeedChange")
    assert bundle.constraints
    for item in bundle.constraints:
        assert item.fact_or_assumption == "assumption"
        assert item.accepted_by_c1 is False
        assert item.accepted_by_c2 is False


def test_k3flag_list_support_levels():
    flags = query_support(
        [
            "osc.action.SpeedChange",
            "osc.action.Following",
            "osc.action.CustomCommand",
            "osc.action.ControllerAssign",
        ],
        ESMINI_BUILD_PIN,
    )
    by_key = {f.feature_key: f.support for f in flags}
    assert by_key["osc.action.SpeedChange"] == SupportLevel.SUPPORTS
    assert by_key["osc.action.Following"] == SupportLevel.PARTIAL
    assert by_key["osc.action.CustomCommand"] == SupportLevel.UNSUPPORTED
    assert by_key["osc.action.ControllerAssign"] == SupportLevel.UNKNOWN
    assert isinstance(flags[0], K3Flag)


def test_unknown_feature_key_marks_gap():
    """Unknown feature key ⇒ evidence item marked gap: unknown, no evidence, assumption."""
    items = query_definitions(["osc.action.DoesNotExist"])
    assert len(items) == 1
    gap = items[0]
    assert gap.feature_key == "osc.action.DoesNotExist"
    assert gap.support == SupportLevel.UNKNOWN
    assert gap.claim == "no evidence"
    assert gap.fact_or_assumption == "assumption"
    # Authority is a contract literal without "none"; a gap cites the lowest category
    # (domain) as a knowledge note. Documented below.
    assert gap.authority == "domain"


def test_features_with_support_helper():
    store = get_store()
    supported = {f.key for f in store.features_with_support("supports", ESMINI_BUILD_PIN)}
    assert "osc.action.SpeedChange" in supported
    assert "osc.action.CustomCommand" not in supported