"""C7 — esmini Simulation tests.

Covers the ADR-0008 / run_record contract behaviors: make_config defaults +
env override, offline SKIPPED_NO_BINARY without esmini, preflight-vs-full argv
differences, hang detection (wall_clock), success, JSON round-trip, and
determinism. Everything runs offline (esmini is not installed).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scenariochef.c7_esmini.runtime import make_config, run_c7, run_c7_sweep
from scenariochef.contracts.common import TraceMeta
from scenariochef.contracts.generated_scenario import GeneratedScenario, XoscArtifact
from scenariochef.contracts.run_record import RunStatus

SHA256_PLACEHOLDER = "0" * 64


def _scenario(name: str = "REQ-0001-v0") -> GeneratedScenario:
    return GeneratedScenario(
        meta=TraceMeta(
            request_id="REQ-0001",
            trajectory_id="REQ-0001",
            produced_by="test-c7",
        ),
        scenario_name=name,
        xosc=XoscArtifact(
            content="<OpenSCENARIO/>",
            path=None,
            sha256=SHA256_PLACEHOLDER,
        ),
    )


def test_make_config_defaults_match_mandatory_fields():
    cfg = make_config()
    assert cfg.esmini_build == "esmini-0.10"
    assert cfg.dt_s == 0.05
    assert cfg.seed == 42
    assert cfg.max_time_s == 30.0
    # Batch default is headless (C7-Q5), OSI off (C7-Q2).
    assert cfg.headless is True
    assert cfg.osi is False


def test_make_config_env_override_esmini_build(monkeypatch):
    monkeypatch.setenv("ESMINI_BUILD", "esmini-0.12")
    cfg = make_config()
    assert cfg.esmini_build == "esmini-0.12"
    # Explicit arg beats env.
    assert make_config(esmini_build="custom").esmini_build == "custom"


def test_run_c7_without_binary_skipped_no_binary(monkeypatch, tmp_path):
    monkeypatch.delenv("ESMINI_BIN", raising=False)
    monkeypatch.setattr(
        "scenariochef.c7_esmini.runtime.shutil.which", lambda _name: None
    )
    record = run_c7(_scenario(), trajectory_id="REQ-0001", workdir=tmp_path)
    assert record.status is RunStatus.SKIPPED_NO_BINARY
    assert record.exit_code is None
    assert record.duration_s == 0.0
    assert "ESMINI_BIN" in record.stderr_tail
    # No exception, no subprocess attempted.


# --- deep-tests report F8: run_c7_sweep machinery + temp-dir hygiene ------------


def test_run_c7_sweep_happy_path(monkeypatch, tmp_path):
    """A fake esmini reporting 3 permutations yields 3 full-mode records in order."""

    script = (
        "#!/bin/sh\n"
        'case "$*" in\n'
        "  *--return_nr_permutations*) echo \"Nr permutations: 3\"; exit 0;;\n"
        "  *) echo \"sweep run\"; exit 0;;\n"
        "esac\n"
    )
    fake = tmp_path / "fake-esmini"
    fake.write_text(script)
    fake.chmod(0o755)
    monkeypatch.setenv("ESMINI_BIN", str(fake))

    records = run_c7_sweep(_scenario(), "egoSpeed", [10.0, 20.0, 30.0], workdir=tmp_path)
    assert len(records) == 3
    assert all(r.mode == "full" for r in records)
    assert all(r.status is RunStatus.COMPLETED for r in records)


def test_run_c7_sweep_zero_permutations_cleans_dir(monkeypatch, tmp_path):
    """Probe reporting 0 permutations -> clean [] result and no leftover scratch."""
    fake = tmp_path / "fake-esmini-zero"
    fake.write_text("#!/bin/sh\necho \"nothing here\"\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("ESMINI_BIN", str(fake))

    scratch = Path(tempfile.gettempdir())
    before = set(scratch.glob("c7_sweep_*"))
    records = run_c7_sweep(_scenario(), "egoSpeed", [10.0], workdir=None)
    assert records == []
    after = set(scratch.glob("c7_sweep_*"))
    assert before == after, "sweep scratch dir leaked"


def test_run_c7_sweep_empty_values_returns_empty():
    assert run_c7_sweep(_scenario(), "egoSpeed", []) == []


def test_run_c7_sweep_without_binary_skipped(monkeypatch):
    monkeypatch.delenv("ESMINI_BIN", raising=False)
    monkeypatch.setattr(
        "scenariochef.c7_esmini.runtime.shutil.which", lambda _name: None
    )
    records = run_c7_sweep(_scenario(), "egoSpeed", [10.0, 20.0])
    # No binary: a single clean-skip marker (permutations cannot be probed).
    assert len(records) == 1
    assert records[0].status is RunStatus.SKIPPED_NO_BINARY
    assert "ESMINI_BIN" in records[0].stderr_tail


def test_run_c7_cleans_own_tempdir(monkeypatch, tmp_path):
    """run_c7 with no explicit workdir removes its c7_* scratch dir (hygiene)."""
    fake = tmp_path / "fake-esmini"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("ESMINI_BIN", str(fake))

    scratch = Path(tempfile.gettempdir())
    before = set(scratch.glob("c7_*"))
    run_c7(_scenario(), trajectory_id="REQ-0001", workdir=None)
    after = set(scratch.glob("c7_*"))
    assert before == after, "run_c7 leaked a temp dir"


def test_run_record_json_round_trip(monkeypatch, tmp_path):
    monkeypatch.delenv("ESMINI_BIN", raising=False)
    monkeypatch.setattr(
        "scenariochef.c7_esmini.runtime.shutil.which", lambda _name: None
    )
    record = run_c7(_scenario(), trajectory_id="REQ-0001", workdir=tmp_path)
    dumped = record.model_dump_json()
    json.loads(dumped)  # must be valid JSON
    restored = type(record).model_validate_json(dumped)
    assert restored == record


class _FakeEsmini:
    """A scriptable stand-in for the esmini binary capturing argv and exit behavior.

    The fake records its argv to a file so the test can assert the exact CLI that C7
    would have invoked against the real binary.
    """

    def __init__(self, path: Path, exit_code: int, stderr: str = "", stdout: str = ""):
        self.path = path
        self.exit_code = exit_code
        self.stderr = stderr
        self.stdout = stdout
        # The script records its argv to a side file and emits the configured
        # stdout/stderr on the real descriptors so subprocess captures them.
        path.write_text(
            "#!/bin/sh\n"
            f'echo "$@" > "{path}.argv"\n'
            f'printf "%s" {json.dumps(self.stdout)}\n'
            f'printf "%s" {json.dumps(self.stderr)} >&2\n'
            f'exit {self.exit_code}\n'
        )
        path.chmod(0o755)


def _fake_run(monkeypatch, tmp_path, exit_code: int, stderr: str = "", stdout: str = "") -> Path:
    """Install a fake esmini binary and return its argv capture path."""
    fake = _FakeEsmini(tmp_path / "fake-esmini", exit_code, stderr, stdout)
    monkeypatch.setenv("ESMINI_BIN", str(fake.path))
    return fake.path


def _read_argv(bin_path: Path) -> list[str]:
    capture = Path(f"{bin_path}.argv")
    return capture.read_text().strip().split(" ") if capture.exists() else []


def test_preflight_vs_full_produce_distinct_argv(monkeypatch, tmp_path):
    bin1 = _fake_run(monkeypatch, tmp_path, exit_code=0)
    run_c7(_scenario(), trajectory_id="REQ-0001", workdir=tmp_path)
    default_argv = _read_argv(bin1)
    assert "--headless" in default_argv
    assert "--terminate_on_end" not in default_argv

    bin2 = _fake_run(monkeypatch, tmp_path, exit_code=0)
    run_c7(_scenario(), trajectory_id="REQ-0001", mode="preflight", workdir=tmp_path)
    preflight_argv = _read_argv(bin2)
    assert "--headless" in preflight_argv
    assert "--terminate_on_end" in preflight_argv
    # Preflight clamps --timeout to at most 10.
    t_idx = preflight_argv.index("--timeout")
    assert float(preflight_argv[t_idx + 1]) <= 10.0

    bin3 = _fake_run(monkeypatch, tmp_path, exit_code=0)
    run_c7(
        _scenario(),
        trajectory_id="REQ-0001",
        config=make_config(headless=False),
        workdir=tmp_path,
    )
    gui_argv = _read_argv(bin3)
    assert "--headless" not in gui_argv
    assert "--window" in gui_argv


def test_hang_wall_clock_on_stderr(monkeypatch, tmp_path):
    _fake_run(monkeypatch, tmp_path, exit_code=9, stderr="simulation hang detected")
    record = run_c7(_scenario(), trajectory_id="REQ-0001", workdir=tmp_path)
    assert record.status is RunStatus.HUNG
    assert record.hang is not None
    assert record.hang.reason == "wall_clock"
    assert record.exit_code == 9


def test_success_completed(monkeypatch, tmp_path):
    _fake_run(monkeypatch, tmp_path, exit_code=0, stdout="all good")
    record = run_c7(_scenario(), trajectory_id="REQ-0001", workdir=tmp_path)
    assert record.status is RunStatus.COMPLETED
    assert record.hang is None
    assert record.exit_code == 0
    assert "all good" in record.stdout_tail


def test_csv_trace_attached(monkeypatch, tmp_path):
    _fake_run(monkeypatch, tmp_path, exit_code=0)
    name = "REQ-0001-v0"
    csv = tmp_path / f"{name}.csv"
    csv.write_text("t,x\n0.0,1.0\n", encoding="utf-8")
    record = run_c7(_scenario(name), trajectory_id="REQ-0001", workdir=tmp_path)
    assert record.status is RunStatus.COMPLETED
    assert record.simulation_csv_path is not None
    assert Path(record.simulation_csv_path).name == f"{name}.csv"


def test_deterministic_records(monkeypatch, tmp_path):
    _fake_run(monkeypatch, tmp_path, exit_code=0)
    first = run_c7(_scenario(), trajectory_id="REQ-0001", workdir=tmp_path)
    second = run_c7(_scenario(), trajectory_id="REQ-0001", workdir=tmp_path)
    a = first.model_dump()
    b = second.model_dump()
    for key in ("meta", "duration_s"):
        a.pop(key)
        b.pop(key)
    assert a == b