"""Tests for C2 — Scenario Understanding (offline: null_proposer or fakes).

Covers: user_explicit slot forcing + conflict recording (C2-Q3, ARCH-0002), DERIVED-3
c3_default double-ack, low-confidence carry (C2-Q2/HITL), null_proposer determinism,
prompt contents, extra-key handling, run_c2 recording, and offline import (ARCH-0001).
"""

from __future__ import annotations

import pytest

from scenariochef.c1_input.runtime import acknowledge_assumption, ingest_nl_params
from scenariochef.c2_understanding.runtime import (
    build_prompt,
    gate,
    last_proposals,
    null_proposer,
    run_c2,
)
from scenariochef.contracts import EvidenceBundle, EvidenceItem, SupportLevel, TraceMeta
from scenariochef.contracts.intent_spec import ActionType


def _evidence_with(item: EvidenceItem) -> EvidenceBundle:
    return EvidenceBundle(
        meta=TraceMeta(request_id="REQ-0001", trajectory_id="REQ-0001", produced_by="C3"),
        definitions=[item],
        constraints=[],
    )


def _assumption_item(**kwargs) -> EvidenceItem:
    defaults = dict(
        id="assumption.gap_20m",
        feature_key="osc.property.gap",
        claim="typical gap is 20 m",
        source_ref="catalog.car_mid",
        authority="domain",
        fact_or_assumption="assumption",
        accepted_by_c1=False,
        accepted_by_c2=False,
        support=SupportLevel.UNKNOWN,
        simulator_build="esmini-2.55",
        excerpt="gap 20 m",
    )
    defaults.update(kwargs)
    return EvidenceItem(**defaults)


def test_user_explicit_params_force_slots_and_conflict():
    spec = ingest_nl_params("", {"speed": 20, "lane": 3})
    proposal = {
        "actors": [
            {"name": "ego", "role": "ego", "initial_speed_mps": 20,
             "position": {"frame": "lane_relative", "road_id": 0, "lane_id": -1, "s_m": 0}},
            {"name": "lead", "role": "target", "initial_speed_mps": 20,
             "position": {"frame": "lane_relative", "road_id": 0, "lane_id": -1, "s_m": 50}},
        ],
        "confidence": 0.9,
        "unknowns": [],
    }
    out = gate(proposal, spec)
    ego = out.actors[0]
    assert ego.initial_speed_mps == 20
    assert ego.slot.source == "user_explicit"
    assert ego.initial_position.lane_id == 3
    assert any(u == "conflict: lane user=3 proposal=-1" for u in out.unknowns)


def test_c3_default_requires_both_acks():
    spec = ingest_nl_params("", {"speed": 20})
    item = _assumption_item()
    # Neither ack -> ValueError.
    with pytest.raises(ValueError):
        gate(null_proposer(""), spec, _evidence_with(item))
    # C1 ack only -> still ValueError.
    c1_only = acknowledge_assumption(spec, item.id)
    with pytest.raises(ValueError):
        gate(null_proposer(""), c1_only, _evidence_with(item))
    # Both acks -> binds c3_default.
    acked = _assumption_item(accepted_by_c2=True)
    both = acknowledge_assumption(spec, acked.id)
    out = gate(null_proposer(""), both, _evidence_with(acked))
    c3 = [t for t in out.triggers if t.slot.source == "c3_default"]
    assert c3
    assert c3[0].slot.accepted_by_c1 is True
    assert c3[0].slot.accepted_by_c2 is True
    assert acked.id in out.c3_evidence_refs


def test_low_confidence_carried_with_unknowns():
    spec = ingest_nl_params("", {"speed": 20})
    proposal = {
        "confidence": 0.4,
        "unknowns": ["lane topology not confirmed"],
        "actors": [],
    }
    out = gate(proposal, spec)
    assert out.confidence == 0.4
    assert "lane topology not confirmed" in out.unknowns


def test_null_proposer_deterministic_and_user_explicit_speed():
    spec = ingest_nl_params("ego follows lead", {"speed": 20})
    out = run_c2(spec)
    assert len(out.actors) == 2
    assert {a.role for a in out.actors} == {"ego", "target"}
    ego = out.actors[0]
    assert ego.initial_speed_mps == 20
    assert ego.slot.source == "user_explicit"
    assert any(m.action is ActionType.FOLLOW for m in out.maneuvers)


def test_build_prompt_contains_user_values_and_evidence():
    spec = ingest_nl_params("ego follows lead at 20", {"speed": 20})
    item = _assumption_item(excerpt="gap 20 m")
    prompt = build_prompt(spec, _evidence_with(item))
    assert "20" in prompt
    assert "USER-EXPLICIT" in prompt
    assert "Never invent facts" in prompt
    assert "typical gap is 20 m" in prompt
    assert item.id in prompt


def test_extra_proposal_key_never_reaches_intent_spec():
    spec = ingest_nl_params("", {"speed": 20})
    proposal = {
        "bogus_top_level": {"x": 1},
        "actors": [],
        "confidence": 0.9,
    }
    out = gate(proposal, spec)
    dump = out.model_dump()
    assert "bogus_top_level" not in dump
    # And the canonical serialized payload carries nothing by that name.
    assert "bogus_top_level" not in out.model_dump_json()


def test_run_c2_records_last_proposals():
    spec = ingest_nl_params("ego follows lead", {"speed": 10})
    run_c2(spec, trajectory_id="REQ-0042")
    assert "REQ-0042" in last_proposals
    assert "actors" in last_proposals["REQ-0042"]


def test_module_imports_without_openai():
    import importlib

    mod = importlib.import_module("scenariochef.c2_understanding.runtime")
    assert hasattr(mod, "null_proposer")
    assert hasattr(mod, "SpaceXAIProposer")