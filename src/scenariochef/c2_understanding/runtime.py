"""C2 — Scenario Understanding: slot-filling LLM with schema validation.

C2 is the ONLY package allowed to import an LLM client (ARCH-0001), but top-level
imports must stay offline-safe, so ``openai`` is imported inside ``SpaceXAIProposer``
only. The offline path is the deterministic ``null_proposer``.

Slot provenance rules:
- User-explicit ``RequestSpec.params`` (keys in ``USER_EXPLICIT_KEYS``) are FORCED into
  slots with ``source="user_explicit"`` and never overridden by the proposal (C2-Q3).
  If the proposal disagrees, the conflict is recorded in ``unknowns``.
- Other proposal values carry ``source="llm_proposed"``.
- C3 assumption defaults (``fact_or_assumption == "assumption"``) bind as
  ``c3_default`` only when BOTH acks are present (C1 via
  ``request_spec.acknowledged_assumptions``, C2 via ``evidence item accepted_by_c2``)
  — DERIVED-3, else a ``ValueError``.
- Low confidence / non-empty ``unknowns`` are carried unchanged: CX decides on HITL.
"""

from __future__ import annotations

import ast
import json
import os
from collections.abc import Callable
from typing import Any

from scenariochef import trace
from scenariochef.contracts import (
    ActionType,
    ActorIntent,
    ActorRole,
    ConstraintIntent,
    EvidenceBundle,
    FrameTag,
    IntentSpec,
    ManeuverIntent,
    ObjectiveKind,
    ObjectiveStub,
    Position,
    Range,
    RequestSpec,
    SlotProvenance,
    TraceMeta,
    TriggerIntent,
    TriggerKind,
    Unit,
    semantic_hash,
)

# The only user params that C2 may slot-fill with user_explicit provenance (C2-Q3).
USER_EXPLICIT_KEYS = ("speed", "ego_speed", "lane", "target_lane", "gap", "headway")

DEFAULT_SPEED = 15.0
DEFAULT_LANE = -1
DEFAULT_LEAD_GAP_M = 50.0
# The default map the offline proposer targets is `straight_2lane` (seed xodr), whose
# single road is id 1. Hardcoding 0 here produced an .xosc referencing a non-existent
# road — an E08-class binding bug that only surfaces at esmini runtime (CX-0004).
DEFAULT_ROAD_ID = 1

# ``run_c2`` records {trajectory_id: proposal} here for C10 action logging.
last_proposals: dict[str, dict[str, Any]] = {}


def build_prompt(request_spec: RequestSpec, evidence: EvidenceBundle | None) -> str:
    """Compose the JSON-only prompt: raw text, user params, evidence, instructions."""
    lines: list[str] = []
    lines.append("You slot-fill an OpenSCENARIO scenario intent.")
    lines.append("Output JSON only, no prose. The shape:")
    lines.append(
        '{actors:[{name,kind,role,initial_speed_mps,position:{frame,lane_id,s_m}}],'
        'maneuvers:[{actor,action,params}],triggers:[{kind,params}],'
        'constraints:[{name,value,unit}],objectives:[{id,kind,description,params}],'
        "confidence,unknowns:[]}"
    )
    lines.append(f"raw request: {request_spec.raw}")
    for key, value in request_spec.params.items():
        marker = "USER-EXPLICIT" if key in USER_EXPLICIT_KEYS else "param"
        lines.append(f"[{marker}] {key} = {value!r}")
    # Machine-readable params block for the offline null_proposer.
    lines.append(f"USER_PARAMS: {json.dumps(request_spec.params, sort_keys=True)}")
    if evidence is not None:
        lines.append("evidence definitions (id: claim); do not restate as invented facts:")
        for item in (*evidence.definitions, *evidence.constraints):
            lines.append(f"  {item.id}: {item.claim}")
    lines.append("Never invent facts. Keep USER-EXPLICIT values verbatim.")
    return "\n".join(lines)


def _params_from_prompt(prompt: str) -> dict[str, Any]:
    """Deterministically recover the USER_PARAMS block emitted by build_prompt."""
    for line in prompt.splitlines():
        line = line.strip()
        if line.startswith("USER_PARAMS:"):
            try:
                parsed: Any = ast.literal_eval(line[len("USER_PARAMS:"):].strip())
                if isinstance(parsed, dict):
                    return dict(parsed)
            except (ValueError, SyntaxError):
                return {}
    return {}


def null_proposer(prompt: str) -> dict[str, Any]:
    """Offline deterministic fallback: 2 actors (ego+lead), follow maneuver.

    Speed and lane come from the parsed user params when present, else defaults.
    Returns a dict in the prompt-contract shape.
    """
    params = _params_from_prompt(prompt)
    speed = float(params.get("speed", params.get("ego_speed", DEFAULT_SPEED)))
    lane = int(params.get("lane", DEFAULT_LANE))
    return {
        "actors": [
            {
                "name": "ego",
                "kind": "vehicle",
                "role": "ego",
                "initial_speed_mps": speed,
                "position": {
                    "frame": "lane_relative",
                    "road_id": DEFAULT_ROAD_ID,
                    "lane_id": lane,
                    "s_m": 0.0,
                },
            },
            {
                "name": "lead",
                "kind": "vehicle",
                "role": "target",
                "initial_speed_mps": speed,
                "position": {
                    "frame": "lane_relative",
                    "road_id": DEFAULT_ROAD_ID,
                    "lane_id": lane,
                    "s_m": DEFAULT_LEAD_GAP_M,
                },
            },
        ],
        "maneuvers": [{"actor": "ego", "action": "follow", "params": {"leader": "lead"}}],
        "triggers": [{"kind": "time", "params": {"t": 0.0}}],
        "constraints": [],
        "objectives": [],
        "confidence": 0.95,
        "unknowns": [],
    }


def _proposal_ego(proposal: dict[str, Any]) -> dict[str, Any]:
    for actor in proposal.get("actors", []):
        if isinstance(actor, dict) and (
            actor.get("role") == "ego" or actor.get("name") == "ego"
        ):
            return actor
    return {}


def _proposal_value(proposal: dict[str, Any], user_key: str) -> object:
    """The proposal's value for a user key, if expressed, else None."""
    if user_key in ("speed", "ego_speed"):
        return _proposal_ego(proposal).get("initial_speed_mps")
    if user_key == "lane":
        return (_proposal_ego(proposal).get("position") or {}).get("lane_id")
    if user_key in ("target_lane", "gap", "headway"):
        for move in proposal.get("maneuvers", []):
            if not isinstance(move, dict):
                continue
            params = move.get("params") or {}
            if user_key in params:
                return params[user_key]
    return None


def _record_conflicts(
    proposal: dict[str, Any], params: dict[str, Any], unknowns: list[str]
) -> None:
    for key in USER_EXPLICIT_KEYS:
        if key not in params:
            continue
        user_val = params[key]
        prop_val = _proposal_value(proposal, key)
        if prop_val is not None and prop_val != user_val:
            unknowns.append(f"conflict: {key} user={user_val} proposal={prop_val}")


def _c3_default_triggers(
    request_spec: RequestSpec, evidence: EvidenceBundle | None
) -> tuple[list[TriggerIntent], list[str]]:
    """Bind assumption-class evidence as c3_default triggers (DERIVED-3).

    Each assumption item needs BOTH the C1 ack (id in acknowledged_assumptions) and the
    C2 ack (evidence item ``accepted_by_c2``); missing either raises ValueError.
    """
    triggers: list[TriggerIntent] = []
    refs: list[str] = []
    if evidence is None:
        return triggers, refs
    items = [*evidence.definitions, *evidence.constraints]
    for item in items:
        if item.fact_or_assumption != "assumption":
            continue
        c1_ack = item.id in request_spec.acknowledged_assumptions
        c2_ack = item.accepted_by_c2
        if not (c1_ack and c2_ack):
            raise ValueError(
                f"c3_default '{item.id}' requires accepted_by_c1=True (C1 ack) "
                f"AND accepted_by_c2=True (C2 ack) before binding (DERIVED-3)"
            )
        triggers.append(
            TriggerIntent(
                kind=TriggerKind.TIME,
                params={"evidence": item.id},
                slot=SlotProvenance(
                    source="c3_default", accepted_by_c1=True, accepted_by_c2=True
                ),
            )
        )
        refs.append(item.id)
    return triggers, refs


def _coerce_scalar(value: object) -> float | Range:
    """Coerce a proposal constraint value to float or Range (C4-Q4 intervals only)."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict) and "min" in value and "max" in value:
        unit = Unit(str(value.get("unit", "none")))
        return Range(min=float(value["min"]), max=float(value["max"]), unit=unit)
    raise ValueError(f"constraint value must be a number or a Range dict, got {value!r}")


def gate(
    proposal: dict[str, Any], request_spec: RequestSpec, evidence: EvidenceBundle | None = None
) -> IntentSpec:
    """Validate a proposal dict into a frozen IntentSpec under slot-provenance rules."""
    params = request_spec.params
    unknowns = list(proposal.get("unknowns", []))
    _record_conflicts(proposal, params, unknowns)

    # --- ego actor: user_explicit speed wins over proposal/llm ---
    speed_key = "ego_speed" if "ego_speed" in params else ("speed" if "speed" in params else None)
    if speed_key is not None:
        ego_speed: float = float(params[speed_key])
        ego_speed_slot = SlotProvenance(source="user_explicit")
    else:
        ego_speed = float(_proposal_ego(proposal).get("initial_speed_mps", DEFAULT_SPEED))
        ego_speed_slot = SlotProvenance(source="llm_proposed")

    # --- ego spawn lane: user_explicit lane wins ---
    if "lane" in params:
        ego_lane: int = int(params["lane"])
    else:
        ego_lane = int(_proposal_ego(proposal).get("position", {}).get("lane_id", DEFAULT_LANE))

    # --- lead actor: llm_proposed (or a stable default) ---
    lead_actor = None
    for actor in proposal.get("actors", []):
        name = actor.get("name") or "_"
        if actor.get("role") != "ego" and name != "ego":
            lead_actor = actor
            break
    lead_pos = ((lead_actor or {}).get("position") or {}) if lead_actor else {}
    lead_speed = float((lead_actor or {}).get("initial_speed_mps", ego_speed))

    actors = [
        ActorIntent(
            name="ego",
            kind="vehicle",
            role=ActorRole.EGO,
            initial_position=Position(
                frame=FrameTag.LANE_RELATIVE, road_id=DEFAULT_ROAD_ID, lane_id=ego_lane, s_m=0.0
            ),
            initial_speed_mps=ego_speed,
            slot=ego_speed_slot,
        ),
        ActorIntent(
            name=lead_actor.get("name", "lead") if lead_actor else "lead",
            kind="vehicle",
            role=ActorRole.TARGET,
            initial_position=Position(
                frame=FrameTag.LANE_RELATIVE,
                road_id=DEFAULT_ROAD_ID,
                lane_id=int(lead_pos.get("lane_id", ego_lane)),
                s_m=float(lead_pos.get("s_m", DEFAULT_LEAD_GAP_M)),
            ),
            initial_speed_mps=lead_speed,
            slot=SlotProvenance(source="llm_proposed"),
        ),
    ]

    # --- maneuvers: follow (required) + user gap/headway + optional lane_change ---
    follow_params: dict[str, float | int | str] = {"leader": "lead"}
    any_user_param = False
    for key in ("gap", "headway"):
        if key in params:
            follow_params[key] = params[key]
            any_user_param = True
    maneuvers = [
        ManeuverIntent(
            actor="ego",
            action=ActionType.FOLLOW,
            params=follow_params,
            slot=SlotProvenance(source="user_explicit" if any_user_param else "llm_proposed"),
        )
    ]
    if "target_lane" in params:
        maneuvers.append(
            ManeuverIntent(
                actor="ego",
                action=ActionType.LANE_CHANGE,
                params={"target_lane": params["target_lane"]},
                slot=SlotProvenance(source="user_explicit"),
            )
        )

    # --- constraints / objectives from the proposal (llm_proposed) ---
    constraints: list[ConstraintIntent] = []
    for c in proposal.get("constraints", []):
        constraints.append(
            ConstraintIntent(
                name=str(c["name"]),
                value=_coerce_scalar(c["value"]),
                unit=str(c["unit"]),
            )
        )
    objectives: list[ObjectiveStub] = []
    for obj in proposal.get("objectives", []):
        objectives.append(
            ObjectiveStub(
                id=str(obj.get("id", "")),
                kind=ObjectiveKind(obj.get("kind", "custom")),
                description=str(obj.get("description", "")),
                params=dict(obj.get("params", {})),
            )
        )

    c3_triggers, c3_refs = _c3_default_triggers(request_spec, evidence)
    triggers = c3_triggers

    confidence = float(proposal.get("confidence", 1.0))

    spec = IntentSpec(
        meta=TraceMeta(
            request_id=request_spec.meta.request_id,
            trajectory_id=request_spec.meta.trajectory_id,
            produced_by="C2",
        ),
        actors=actors,
        maneuvers=maneuvers,
        triggers=triggers,
        constraints=constraints,
        objectives=objectives,
        confidence=confidence,
        unknowns=unknowns,
        c3_evidence_refs=c3_refs,
    )
    return spec


def run_c2(
    request_spec: RequestSpec,
    trajectory_id: str = "REQ-0001",
    evidence: EvidenceBundle | None = None,
    proposer: Callable[[str], dict[str, Any]] | None = None,
) -> IntentSpec:
    """Propose and gate an IntentSpec for a request (offline-safe by default)."""
    _proposer = proposer if proposer is not None else null_proposer
    prompt = build_prompt(request_spec, evidence)
    proposal = _proposer(prompt)
    last_proposals[trajectory_id] = proposal

    in_token = f"<RequestSpec:{semantic_hash(request_spec)[:8]}>"
    trace.emit(3, "C2", "IN", in_token, trajectory_id)

    spec = gate(proposal, request_spec, evidence)

    out_token = f"<IntentSpec:{semantic_hash(spec)[:8]}>"
    trace.emit(3, "C2", "OUT", out_token, trajectory_id)
    return spec


class SpaceXAIProposer:
    """Optional real LLM proposer. ``openai`` is imported lazily (ARCH-0001).

    Requires ``XAI_API_KEY`` in the environment; model is ``XAI_MODEL`` or ``grok-4.5``.
    """

    _model: str
    _client: Any

    def __init__(self) -> None:
        import openai as _openai  # type: ignore[import-not-found]  # guarded import (ARCH-0001)

        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            raise RuntimeError("XAI_API_KEY environment variable is not set")
        self._model = os.environ.get("XAI_MODEL", "grok-4.5")
        self._client: Any = _openai.OpenAI(
            api_key=api_key, base_url="https://api.x.ai/v1"
        )

    def __call__(self, prompt: str) -> dict[str, Any]:
        response = self._client.responses.create(
            model=self._model,
            instructions="Return JSON only, matching the documented shape.",
            input=prompt,
        )
        text = response.output_text
        return dict(json.loads(text))