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
    # The offline proposer must target the real default-map road id (1), not a
    # hardcoded 0 that would produce a non-existent-road .xosc (CX-0004).
    assert ego.initial_position.road_id == 1
    assert out.actors[1].initial_position.road_id == 1


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


# --- deep-tests report F8: real-LLM proposer path (retry/repair/parse) ----------


class _FakeCompletions:
    """Scriptable chat.completions stand-in; records calls, replays replies."""

    def __init__(self, replies: list[str | Exception]):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item

        class _Msg:
            content = item

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()


def _proposer_with(monkeypatch, replies: list[str | Exception]):
    import scenariochef.c2_understanding.runtime as c2mod

    fake = _FakeCompletions(replies)

    class _FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.chat = type("C", (), {})()
            self.chat.completions = fake

    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)
    monkeypatch.setenv("C2_LLM_API_KEY", "test-key")
    proposer = c2mod.CommandCodeProposer()
    return proposer, fake


def test_proposer_retries_transient_errors_then_succeeds(monkeypatch):
    pytest.importorskip("openai")  # the real-LLM path needs the optional client pkg
    import scenariochef.c2_understanding.runtime as c2mod

    sleeps: list[float] = []
    monkeypatch.setattr(c2mod.time, "sleep", sleeps.append)
    proposer, fake = _proposer_with(
        monkeypatch, [RuntimeError("503 bad gateway"), '{"actors": []}']
    )
    out = proposer("prompt")
    assert out == {"actors": []}
    assert len(fake.calls) == 2  # one retry after the transient failure
    assert sleeps == [2.0]  # bounded backoff (2s, then 4s would follow a 2nd retry)


def test_proposer_repairs_malformed_json(monkeypatch):
    pytest.importorskip("openai")
    import scenariochef.c2_understanding.runtime as c2mod

    sleeps: list[float] = []
    monkeypatch.setattr(c2mod.time, "sleep", sleeps.append)
    proposer, fake = _proposer_with(
        monkeypatch,
        ["oops ```not json", '{"confidence": 0.9}'],
    )
    out = proposer("prompt")
    assert out == {"confidence": 0.9}
    # The repair re-ask embeds the offending output and the original prompt.
    assert "not valid JSON" in fake.calls[1]["messages"][1]["content"]
    assert "oops" in fake.calls[1]["messages"][1]["content"]


def test_proposer_raises_runtime_error_after_bounded_attempts(monkeypatch):
    pytest.importorskip("openai")
    import scenariochef.c2_understanding.runtime as c2mod

    sleeps: list[float] = []
    monkeypatch.setattr(c2mod.time, "sleep", sleeps.append)
    proposer, fake = _proposer_with(
        monkeypatch, [RuntimeError("503")] * 5
    )
    with pytest.raises(RuntimeError, match="failed after 3 attempts"):
        proposer("prompt")
    assert len(fake.calls) == 3  # bounded: exactly _MAX_ATTEMPTS
    assert sleeps == [2.0, 4.0]  # total sleep <= 6 s


def test_proposer_requires_api_key(monkeypatch):
    pytest.importorskip("openai")
    import scenariochef.c2_understanding.runtime as c2mod

    monkeypatch.delenv("C2_LLM_API_KEY", raising=False)
    monkeypatch.delenv("COMMAND_CODE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="C2_LLM_API_KEY"):
        c2mod.CommandCodeProposer()


def test_extract_json_tolerates_fences_and_prose():
    from scenariochef.c2_understanding.runtime import _extract_json

    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('Sure!\n{"a": {"b": 2}} hope that helps') == {"a": {"b": 2}}
    assert _extract_json('{"a": 1}') == {"a": 1}
    with pytest.raises(ValueError):
        _extract_json("no json here at all")
    with pytest.raises(ValueError):
        _extract_json("[1, 2, 3]")  # JSON but not an object


# --- F1: cross-actor spawn sanity (deep-tests report) -------------------------


def _proposal_with_lead(lead: dict) -> dict:
    return {
        "actors": [
            {"name": "ego", "role": "ego", "initial_speed_mps": 15.0,
             "position": {"frame": "lane_relative", "road_id": 1, "lane_id": -1, "s_m": 0.0}},
            lead,
        ],
        "maneuvers": [{"actor": "ego", "action": "follow", "params": {"leader": "lead"}}],
        "confidence": 0.9,
        "unknowns": [],
    }


def test_gate_rejects_spawn_overlapping_target():
    """A target spawned at ego's exact point is clamped and recorded (F1).

    L1 witness: the LLM named the lead "Ego" with s_m=0.0; both entities spawned at
    identical coordinates and the run still reported objectives 1/1.
    """
    spec = ingest_nl_params("ego follows lead", {})
    proposal = _proposal_with_lead(
        {"name": "Ego", "role": "target", "initial_speed_mps": 20.0,
         "position": {"frame": "lane_relative", "road_id": 1, "lane_id": -1, "s_m": 0.0}}
    )
    out = gate(proposal, spec)
    target = out.actors[1]
    assert target.initial_position.s_m == 50.0  # clamped to the stable default gap
    assert any("overlaps ego spawn" in u for u in out.unknowns)


def test_gate_clamps_sub_collision_gap_on_same_lane():
    """A 0.2 m lane-matched spawn gap is inside collision distance -> clamped."""
    spec = ingest_nl_params("ego follows lead", {})
    proposal = _proposal_with_lead(
        {"name": "lead", "role": "target", "initial_speed_mps": 20.0,
         "position": {"frame": "lane_relative", "road_id": 1, "lane_id": -1, "s_m": 0.2}}
    )
    out = gate(proposal, spec)
    assert out.actors[1].initial_position.s_m == 50.0
    assert any("overlaps ego spawn" in u for u in out.unknowns)


def test_gate_allows_explicit_gap_on_different_lane():
    """A sub-threshold s on a DIFFERENT lane is a valid crossing/merge setup: kept."""
    spec = ingest_nl_params("pedestrian crosses", {})
    proposal = _proposal_with_lead(
        {"name": "walker", "role": "target", "kind": "pedestrian", "initial_speed_mps": 1.4,
         "position": {"frame": "lane_relative", "road_id": 1, "lane_id": 1, "s_m": 0.2}}
    )
    out = gate(proposal, spec)
    assert out.actors[1].initial_position.s_m == 0.2
    assert not any("overlaps" in u for u in out.unknowns)


def test_gate_renames_duplicate_ego_target():
    """A target literally named 'ego' is renamed so entity refs stay unambiguous (F1)."""
    spec = ingest_nl_params("ego follows lead", {})
    proposal = _proposal_with_lead(
        {"name": "ego", "role": "target", "initial_speed_mps": 20.0,
         "position": {"frame": "lane_relative", "road_id": 1, "lane_id": -1, "s_m": 30.0}}
    )
    out = gate(proposal, spec)
    assert out.actors[1].name == "lead"
    assert any("duplicate actor name" in u for u in out.unknowns)


def test_gate_keeps_explicit_healthy_gap():
    """A proposal-carried healthy gap passes through unchanged (no false clamp)."""
    spec = ingest_nl_params("ego follows lead", {})
    proposal = _proposal_with_lead(
        {"name": "lead", "role": "target", "initial_speed_mps": 20.0,
         "position": {"frame": "lane_relative", "road_id": 1, "lane_id": -1, "s_m": 0.0 + 30.0}}
    )
    out = gate(proposal, spec)
    assert out.actors[1].initial_position.s_m == 30.0
    assert not any("overlaps" in u for u in out.unknowns)


def test_module_imports_without_openai():
    import importlib

    mod = importlib.import_module("scenariochef.c2_understanding.runtime")
    assert hasattr(mod, "null_proposer")
    assert hasattr(mod, "SpaceXAIProposer")