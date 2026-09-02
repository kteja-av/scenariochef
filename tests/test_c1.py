"""Tests for C1 — Scenario Input adapter.

Covers the four Phase-1 modalities plus the deterministic normalizations and HITL
markers (C1-Q2, C1-Q4), frozen RequestSpec, and acknowledge_assumption immutability.
"""

import hashlib
import io
from pathlib import Path

import pytest
from pydantic import ValidationError

from scenariochef import trace
from scenariochef.c1_input.runtime import (
    acknowledge_assumption,
    ingest_crash_narrative,
    ingest_file,
    ingest_multimodal,
    ingest_nl_params,
    run_c1,
)
from scenariochef.contracts import Modality

_TINY_XOSC = """<?xml version="1.0" encoding="UTF-8"?>
<OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="0"/>
</OpenSCENARIO>
"""


def test_nl_params_happy_path():
    spec = ingest_nl_params("  ego    brakes at 40 m   ", {"speed": 20, "unit": "mps"})
    assert spec.modality is Modality.NL_PARAMS
    assert spec.raw == "ego brakes at 40 m"
    assert spec.params["speed"] == 20
    assert spec.params["unit"] == "mps"
    assert spec.unresolved_fields == []
    assert spec.contradictions == []


def test_file_ingest_xosc_happy_path(tmp_path: Path):
    p = tmp_path / "scenario.xosc"
    p.write_text(_TINY_XOSC, encoding="utf-8")
    spec = ingest_file(p)
    assert spec.modality is Modality.XOSC_XODR
    assert len(spec.input_files) == 1
    f = spec.input_files[0]
    assert f.path == str(p)
    assert f.kind == "xosc"
    assert len(f.sha256) == 64
    assert f.sha256 == hashlib.sha256(_TINY_XOSC.encode()).hexdigest()
    assert spec.unresolved_fields == []


def test_file_ingest_malformed_xml_unresolved(tmp_path: Path):
    p = tmp_path / "broken.xosc"
    p.write_text("<OpenSCENARIO><unclosed>", encoding="utf-8")
    spec = ingest_file(p)
    assert spec.unresolved_fields
    u = spec.unresolved_fields[0]
    assert u.field_path == "input_files[0].xml"
    assert u.reason == "not well-formed XML"


def test_contradiction_detection():
    spec = ingest_nl_params("ego", {"speed": [20, 25]})
    assert len(spec.contradictions) == 1
    c = spec.contradictions[0]
    assert c.field_paths == ["speed", "speed"]
    assert "speed" in c.description


def test_unknown_param_unresolved():
    spec = ingest_nl_params("ego", {"gizmo": 5})
    assert spec.unresolved_fields
    u = spec.unresolved_fields[0]
    assert u.field_path == "gizmo"
    assert u.reason == "unknown parameter — needs HITL"
    # C1 still records the value; it just asks (no silent default).
    assert spec.params["gizmo"] == 5


def test_acknowledge_assumption_immutability():
    spec = ingest_nl_params("ego", {"speed": 10})
    assert spec.acknowledged_assumptions == []
    updated = acknowledge_assumption(spec, "assumption.ev-1")
    assert updated.acknowledged_assumptions == ["assumption.ev-1"]
    # Original must be unchanged.
    assert spec.acknowledged_assumptions == []
    assert spec is not updated


def test_multimodal_two_files_hashes(tmp_path: Path):
    a = tmp_path / "clip.xosc"
    b = tmp_path / "sketch.png"
    a.write_text("x", encoding="utf-8")
    b.write_bytes(b"png")
    spec = ingest_multimodal("dashcam behind van", [a, b])
    assert spec.modality is Modality.MULTIMODAL
    assert spec.raw == "dashcam behind van"
    assert len(spec.input_files) == 2
    assert all(len(f.sha256) == 64 for f in spec.input_files)
    assert {f.kind for f in spec.input_files} == {"xosc", "other"}


def test_all_four_modalities_enum(tmp_path: Path):
    p = tmp_path / "m.xosc"
    p.write_text(_TINY_XOSC, encoding="utf-8")
    mods = {
        ingest_nl_params("x", {}).modality,
        ingest_file(p).modality,
        ingest_crash_narrative("x").modality,
        ingest_multimodal("x", []).modality,
    }
    assert mods == {
        Modality.NL_PARAMS,
        Modality.XOSC_XODR,
        Modality.CRASH_NARRATIVE,
        Modality.MULTIMODAL,
    }


def test_run_c1_dispatch_shapes(tmp_path: Path):
    # file path (xosc) dispatches to file ingest
    p = tmp_path / "a.xosc"
    p.write_text(_TINY_XOSC, encoding="utf-8")
    assert run_c1(p).modality is Modality.XOSC_XODR
    assert run_c1(str(p)).modality is Modality.XOSC_XODR
    # dict -> nl_params
    assert run_c1({"speed": 10}).modality is Modality.NL_PARAMS
    # bare string -> nl text
    assert run_c1("ego brakes").modality is Modality.NL_PARAMS


def test_request_spec_frozen():
    spec = ingest_nl_params("ego", {"speed": 10})
    with pytest.raises(ValidationError):
        spec.raw = "changed"


def test_trace_out_token_is_request_spec():
    sink = io.StringIO()
    trace.set_log(sink)
    ingest_nl_params("ego", {})
    out = sink.getvalue()
    assert "[step:02] C1" in out
    assert "OUT <RequestSpec:" in out