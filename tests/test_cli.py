"""CLI entry-point tests (deep-tests report F8: cli.py had 0% coverage).

Runs ``main()`` offline (no esmini, no LLM keys) against a tmp Store via the
run_request store parameter — the CLI opens its own repo Store, so these tests
monkeypatch Store to a tmp location and assert process outcomes and printed lines.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scenariochef import cli


@pytest.fixture()
def offline_env(monkeypatch, tmp_path: Path):
    """Force the CLI offline and run it from a tmp cwd (its Store writes there)."""
    for var in ("C2_LLM_API_KEY", "COMMAND_CODE_API_KEY", "XAI_API_KEY", "ESMINI_BIN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)


def test_parse_params_types():
    assert cli._parse_params(["speed=20"]) == {"speed": 20}
    assert cli._parse_params(["gap=1.5"]) == {"gap": 1.5}
    assert cli._parse_params(["lane=-1"]) == {"lane": -1}
    assert cli._parse_params(["text=ego"]) == {"text": "ego"}


def test_parse_params_invalid_exits():
    with pytest.raises(SystemExit):
        cli._parse_params(["=value"])


def test_cli_run_text_offline(capsys: pytest.CaptureFixture, offline_env):
    rc = cli.main(["run", "--text", "ego follows lead in lane -1 at 20 m/s"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[run] outcome=completed" in out
    assert "[run] persisted" in out


def test_cli_run_missing_file_exit_2(capsys: pytest.CaptureFixture, offline_env):
    rc = cli.main(["run", "/nonexistent/no_such_file.xosc"])
    assert rc == 2
    assert "file not found" in capsys.readouterr().err


def test_cli_run_existing_xosc_file(tmp_path: Path, capsys: pytest.CaptureFixture, offline_env):
    p = tmp_path / "tiny.xosc"
    p.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<OpenSCENARIO><FileHeader revMajor=\"1\" revMinor=\"0\"/></OpenSCENARIO>",
        encoding="utf-8",
    )
    rc = cli.main(["run", str(p)])
    assert rc == 0
    assert f"from {p}" in capsys.readouterr().out


def test_cli_default_demo_request(capsys: pytest.CaptureFixture, offline_env):
    rc = cli.main([])
    assert rc == 0
    assert "[run] outcome=completed" in capsys.readouterr().out


def test_cli_bad_param_value_hits_gate(capsys: pytest.CaptureFixture, offline_env):
    """A param outside the C1 vocabulary resolves to a HITL-blocked run (rc 0)."""
    rc = cli.main(["run", "--text", "ego follows lead", "--param", "gizmo=5"])
    assert rc == 0
    assert "[run] outcome=hitl_blocked" in capsys.readouterr().out
