"""C1 — Scenario Input: ingest and normalize user requirements.

Deterministic adapter layer (ARCH-0001): C1 never calls an LLM and never rewrites
user-explicit slots (ARCH-0002). It normalizes one of the four Phase-1 modalities into
a validated ``RequestSpec`` and emits HITL markers (unresolved fields / contradictions)
for CX to resolve (C1-Q2, C1-Q4).
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from scenariochef import trace
from scenariochef.contracts import (
    Contradiction,
    InputFile,
    Modality,
    RequestSpec,
    TraceMeta,
    UnresolvedField,
    semantic_hash,
)
from scenariochef.contracts.request_spec import FileKind

# Keys C1 recognizes without needing HITL. Any other param key is flagged unresolved
# (C1-Q2 — C1 asks, never silently defaults).
ALLOWED_PARAMS = frozenset(
    {
        "ego_speed",
        "speed",
        "target_lane",
        "lane",
        "gap",
        "dt",
        "seed",
        "max_time",
        "headway",
    }
)

# Standalone unit modifier key. Recorded in params as given by the user (unit is part
# of the param vocabulary, not an unknown parameter to be resolved).
UNIT_KEY = "unit"

UNRESOLVED_REASON = "unknown parameter — needs HITL"

_WELLKNOWN_UNITS = frozenset({"m", "mps", "mps2", "s", "none"})

# Determinism (deep-tests report, LOW finding): C1/C2/C6/C9 pin created_at to the same
# fixed sentinel the other components use, so identical requests produce identical
# artifact hashes. Wall-clock metadata is not part of any contract payload.
_DETERMINISTIC_CREATED_AT = "2000-01-01T00:00:00+00:00"

# An empty NL payload carries no scenario intent; C2 cannot infer one and silently
# fabricating defaults is wrong (deep-tests report F4) — C1 asks (C1-Q2).
_EMPTY_TEXT_REASON = "empty request text — describe the scenario to simulate"


def _normalize(text: str) -> str:
    """Strip and collapse internal whitespace (no semantic interpretation — C2's job)."""
    return " ".join(text.split())


def _hash_file(path: Path) -> str:
    """sha256 of the raw file bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_kind(path: Path) -> FileKind:
    suffix = path.suffix.lower()
    if suffix == ".xosc":
        return "xosc"
    if suffix == ".xodr":
        return "xodr"
    return "other"


def _is_scene_file_path(value: str) -> bool:
    """Whether a string names an existing .xosc/.xodr file path."""
    return value.lower().endswith((".xosc", ".xodr"))


def _well_formed(path: Path) -> bool:
    """Well-formedness check only — C1 never interprets the XML content."""
    try:
        ET.parse(path)
    except ET.ParseError:
        return False
    return True


def _candidate_values(value: Any) -> list[Any]:
    """Represent the possible values for one param key.

    A scalar holds one candidate; a list holds several (a dict cannot repeat a key, so
    multiple values for the same key are passed as a list of candidates). Returning
    more than one distinct candidate is a contradiction (C1-Q4).
    """
    if isinstance(value, list):
        seen: list[Any] = []
        for v in value:
            if v not in seen:
                seen.append(v)
        return seen
    return [value]


def _analyze_params(
    params: dict[str, Any],
) -> tuple[dict[str, float | int | str], list[Contradiction], list[UnresolvedField]]:
    """Split params into resolved values, contradictions, and unresolved fields."""
    resolved: dict[str, float | int | str] = {}
    contradictions: list[Contradiction] = []
    unresolved: list[UnresolvedField] = []

    for key, value in params.items():
        if key == UNIT_KEY:
            if isinstance(value, str) and value.lower() in _WELLKNOWN_UNITS:
                resolved[key] = value
            else:
                # Unknown units are asked about, never silently dropped
                # (deep-tests report F5 — same ask-the-user contract as unknown keys).
                unresolved.append(
                    UnresolvedField(
                        field_path=UNIT_KEY,
                        reason=f"unknown unit {value!r} — expected one of "
                        f"{sorted(_WELLKNOWN_UNITS)}",
                    )
                )
            continue
        candidates = _candidate_values(value)
        if len(candidates) > 1:
            shown = ", ".join(repr(c) for c in candidates)
            contradictions.append(
                Contradiction(
                    field_paths=[key, key],
                    description=f"conflicting values for '{key}': {shown}",
                )
            )
            # Ambiguous — C1 cannot pick a value, so the key is left out of params.
            continue
        resolved[key] = candidates[0]
        if key not in ALLOWED_PARAMS:
            unresolved.append(UnresolvedField(field_path=key, reason=UNRESOLVED_REASON))

    return resolved, contradictions, unresolved


def _emit_and_build(
    modality: Modality,
    raw: str,
    params: dict[str, float | int | str],
    input_files: list[InputFile],
    unresolved: list[UnresolvedField],
    contradictions: list[Contradiction],
    trajectory_id: str,
) -> RequestSpec:
    """Build the validated RequestSpec and emit the step-2 trace lines."""
    spec = RequestSpec(
        meta=TraceMeta(
            request_id=trajectory_id,
            trajectory_id=trajectory_id,
            created_at=_DETERMINISTIC_CREATED_AT,
            produced_by="C1",
        ),
        modality=modality,
        raw=raw,
        params=params,
        input_files=input_files,
        unresolved_fields=unresolved,
        contradictions=contradictions,
    )
    hash8 = semantic_hash(spec)[:8]
    trace.emit(2, "C1", "IN", raw, trajectory_id)
    trace.emit(2, "C1", "OUT", f"<RequestSpec:{hash8}>", trajectory_id)
    return spec


def run_c1(raw_input: Any, trajectory_id: str = "REQ-0001", **kwargs: Any) -> RequestSpec:
    """Dispatch on input shape into the matching modality adapter."""
    if isinstance(raw_input, Path):
        return ingest_file(raw_input, trajectory_id)
    if isinstance(raw_input, str) and _is_scene_file_path(raw_input):
        return ingest_file(Path(raw_input), trajectory_id)
    if isinstance(raw_input, dict):
        # Dict requests may carry a natural-language payload under `text`/`request`;
        # the remaining keys are explicit params (C1-Q1 NL+params modality).
        params = dict(raw_input)
        nl = params.pop("text", None) or params.pop("request", "").strip()
        return ingest_nl_params(str(nl), params, trajectory_id)
    text = raw_input if isinstance(raw_input, str) else str(raw_input)
    return ingest_nl_params(text, {}, trajectory_id)


def ingest_file(path: Path, trajectory_id: str = "REQ-0001") -> RequestSpec:
    """Modality XOSC_XODR — record the file reference; XML is only well-formedness checked.

    A nonexistent path is a HITL marker (unresolved ``input_files[0].path``), not a raw
    ``FileNotFoundError``: API callers get the same ask-the-user gate the CLI's
    exit-2 guard provides (deep-tests report F6).
    """
    raw = str(path)
    unresolved: list[UnresolvedField] = []
    if not path.is_file():
        unresolved.append(
            UnresolvedField(
                field_path="input_files[0].path",
                reason="file not found",
            )
        )
        return _emit_and_build(
            Modality.XOSC_XODR,
            raw,
            {},
            [],
            unresolved,
            [],
            trajectory_id,
        )
    input_file = InputFile(path=raw, kind=_file_kind(path), sha256=_hash_file(path))
    if not _well_formed(path):
        unresolved.append(
            UnresolvedField(field_path="input_files[0].xml", reason="not well-formed XML")
        )
    return _emit_and_build(
        Modality.XOSC_XODR,
        raw,
        {},
        [input_file],
        unresolved,
        [],
        trajectory_id,
    )


def ingest_nl_params(
    text: str, params: dict[str, Any], trajectory_id: str = "REQ-0001"
) -> RequestSpec:
    """Modality NL_PARAMS — normalized text plus validated param vocabulary.

    An empty NL payload (no text, no params) cannot express an intent: it is flagged
    as an unresolved field so CX routes it to HITL instead of letting C2 fabricate a
    full default scenario (deep-tests report F4).
    """
    raw = _normalize(text)
    resolved, contradictions, unresolved = _analyze_params(params)
    if not raw and not resolved and not unresolved and not contradictions:
        unresolved.append(
            UnresolvedField(field_path="text", reason=_EMPTY_TEXT_REASON)
        )
    return _emit_and_build(
        Modality.NL_PARAMS,
        raw,
        resolved,
        [],
        unresolved,
        contradictions,
        trajectory_id,
    )


def ingest_crash_narrative(text: str, trajectory_id: str = "REQ-0001") -> RequestSpec:
    """Modality CRASH_NARRATIVE — normalized text; interpretation is C2's job."""
    raw = _normalize(text)
    return _emit_and_build(
        Modality.CRASH_NARRATIVE, raw, {}, [], [], [], trajectory_id
    )


def ingest_multimodal(
    text: str, files: list[Path], trajectory_id: str = "REQ-0001"
) -> RequestSpec:
    """Modality MULTIMODAL — normalized text plus referenced artifacts (hashed)."""
    raw = _normalize(text)
    input_files = [
        InputFile(path=str(f), kind=_file_kind(f), sha256=_hash_file(f)) for f in files
    ]
    return _emit_and_build(
        Modality.MULTIMODAL, raw, {}, input_files, [], [], trajectory_id
    )


def acknowledge_assumption(request_spec: RequestSpec, evidence_id: str) -> RequestSpec:
    """Return a new frozen RequestSpec with the C3 default id acknowledged (C1-Q3)."""
    return request_spec.model_copy(
        update={
            "acknowledged_assumptions": [
                *request_spec.acknowledged_assumptions,
                evidence_id,
            ]
        }
    )