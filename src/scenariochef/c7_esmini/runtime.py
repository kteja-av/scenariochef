"""C7 — esmini Simulation: deterministic subprocess runner (preflight | full).

C7 executes one concrete ``GeneratedScenario`` with the esmini binary and returns a
``RunRecord``. It is a **deterministic subprocess runner, not an agent** (ARCH-0001):
no LLM, no randomness, and the output logic never reads the wall clock — the only
wall-clock read is the measured ``duration_s`` (the framework explicitly allows it
there). The esmini binary is discovered via the ``ESMINI_BIN`` env var or PATH; when
absent the pipeline must stay runnable, so C7 returns ``SKIPPED_NO_BINARY`` with a
stderr note — never a Python exception.

One runner, two modes (C7-Q1, ARCH-0004): ``preflight`` truncates the run to at most 10
sim seconds and terminates at end-of-scenario; ``full`` runs to ``max_time_s``. Hang
policy (C7-Q4): either the subprocess wall-clock timeout **or** an esmini step-cap
signature trips termination. Batch runs default to headless (C7-Q5).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from scenariochef import trace
from scenariochef.contracts.common import TraceMeta
from scenariochef.contracts.generated_scenario import GeneratedScenario
from scenariochef.contracts.run_record import HangInfo, RunConfig, RunRecord, RunStatus

_PRODUCER = "C7"

# Pinned esmini build (C7-Q2 / the C4 header ``esmini_pin``). Overridable via the
# ``ESMINI_BUILD`` env var or explicitly in ``make_config``.
_DEFAULT_BUILD = "esmini-0.10"

_TAIL_CHARS = 8192  # last 8 KB of stdout/stderr captured on the record.
_WALL_CLOCK_SLACK_S = 10.0  # subprocess wall-clock timeout = max_time + slack (C7-Q4).
_PREFLIGHT_TIMEOUT_S = 10.0  # preflight runs truncated to at most 10 sim seconds.
_STEP_CAP_MARKER = "steps exceeded"  # esmini step-cap termination signature (C7-Q4).
_HANG_MARKER = "hang"  # stderr signature for generic hang detection (C7-Q4).

# Deterministic created-at sentinel, mirroring C5's policy: the produced RunRecord must
# be reproducible (same inputs -> same fields) apart from the measured ``duration_s``.
_DETERMINISTIC_CREATED_AT = "2000-01-01T00:00:00+00:00"


def make_config(
    seed: int = 42,
    dt_s: float = 0.05,
    max_time_s: float = 30.0,
    headless: bool = True,
    osi: bool = False,
    esmini_build: str | None = None,
) -> RunConfig:
    """Build a reproducible ``RunConfig`` (C7-Q2).

    ``esmini_build`` resolves to the ``ESMINI_BUILD`` env var when not given, else the
    pinned ``esmini-0.10`` default. Batch runs default to ``headless`` (C7-Q5).
    """
    build = esmini_build or os.environ.get("ESMINI_BUILD", _DEFAULT_BUILD)
    return RunConfig(
        esmini_build=build,
        dt_s=dt_s,
        seed=seed,
        max_time_s=max_time_s,
        headless=headless,
        osi=osi,
    )


def run_c7(
    generated_scenario: GeneratedScenario,
    trajectory_id: str = "REQ-0001",
    config: RunConfig | None = None,
    mode: Literal["preflight", "full"] = "full",
    workdir: Path | None = None,
) -> RunRecord:
    """Execute one esmini run and return the ``RunRecord`` (preflight or full).

    Deterministic: same inputs yield the same record fields except the measured
    ``duration_s``. The esmini binary is discovered via ``ESMINI_BIN`` then PATH; when
    absent C7 returns ``SKIPPED_NO_BINARY`` — it never raises.
    """
    meta = TraceMeta(
        request_id=generated_scenario.meta.request_id,
        trajectory_id=trajectory_id,
        created_at=_DETERMINISTIC_CREATED_AT,
        produced_by=_PRODUCER,
    )
    trace.emit(8, "C7", "IN", f"<GeneratedScenario:{_h8(generated_scenario)}>", trajectory_id)

    run_config = config if config is not None else make_config()

    binary = _find_binary()
    if binary is None:
        stderr_note = "esmini binary not found (set ESMINI_BIN)"
        record = RunRecord(
            meta=meta,
            config=run_config,
            mode=mode,
            exit_code=None,
            stderr_tail=stderr_note,
            duration_s=0.0,
            status=RunStatus.SKIPPED_NO_BINARY,
        )
        trace.emit(8, "C7", "OUT", f"<RunRecord:{_h8(record)}>", trajectory_id)
        return record

    dir_ = workdir if workdir is not None else Path(tempfile.mkdtemp(prefix="c7_"))
    dir_.mkdir(parents=True, exist_ok=True)
    xosc_path = dir_ / f"{generated_scenario.scenario_name}.xosc"
    xosc_path.write_text(generated_scenario.xosc.content, encoding="utf-8")

    argv = _build_argv(binary, xosc_path, run_config, mode)
    wall_clock_timeout = run_config.max_time_s + _WALL_CLOCK_SLACK_S

    start = time.monotonic()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=wall_clock_timeout)
        returncode: int | None = proc.returncode
        stdout_all = proc.stdout or ""
        stderr_all = proc.stderr or ""
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        returncode = None
        stdout_all = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr_all = exc.stderr if isinstance(exc.stderr, str) else ""
        timed_out = True
    duration_s = time.monotonic() - start

    status, hang = _classify(
        returncode, stdout_all, stderr_all, timed_out, run_config, wall_clock_timeout
    )

    csv_path = dir_ / f"{xosc_path.stem}.csv"
    simulation_csv_path = str(csv_path) if csv_path.exists() else None

    record = RunRecord(
        meta=meta,
        config=run_config,
        mode=mode,
        exit_code=returncode,
        stdout_tail=stdout_all[-_TAIL_CHARS:],
        stderr_tail=stderr_all[-_TAIL_CHARS:],
        simulation_csv_path=simulation_csv_path,
        osi_trace_path=None,
        hang=hang,
        duration_s=duration_s,
        sim_time_s=None,
        status=status,
    )
    trace.emit(8, "C7", "OUT", f"<RunRecord:{_h8(record)}>", trajectory_id)
    return record


def _find_binary() -> str | None:
    """Resolve the esmini executable via ``ESMINI_BIN`` then PATH, else ``None``."""
    env_bin = os.environ.get("ESMINI_BIN")
    if env_bin:
        p = Path(env_bin)
        # a set-but-nonexistent ESMINI_BIN must not crash subprocess later — treat it
        # as absent so C7 returns SKIPPED_NO_BINARY (never raises).
        if p.is_file():
            return env_bin
        return None
    return shutil.which("esmini")


def _build_argv(
    binary: str, xosc_path: Path, config: RunConfig, mode: Literal["preflight", "full"]
) -> list[str]:
    """Assemble the deterministic esmini argv for a run.

    ``preflight`` adds ``--terminate_on_end`` and clamps ``--timeout`` to at most 10 sim
    seconds (C7-Q1); ``full`` runs to ``max_time_s``. ``headless`` selects the window
    geometry vs ``--headless`` (C7-Q5).
    """
    display = ["--window", "60,60,800,400"] if not config.headless else ["--headless"]
    if mode == "preflight":
        timeout_s = min(config.max_time_s, _PREFLIGHT_TIMEOUT_S)
    else:
        timeout_s = config.max_time_s
    argv = [
        binary,
        *display,
        "--osc",
        str(xosc_path),
        "--fixed_timestep",
        str(config.dt_s),
        "--seed",
        str(config.seed),
        "--timeout",
        str(timeout_s),
    ]
    if mode == "preflight":
        argv.append("--terminate_on_end")
    return argv


def _classify(
    returncode: int | None,
    stdout: str,
    stderr: str,
    timed_out: bool,
    config: RunConfig,
    wall_clock_timeout: float,
) -> tuple[RunStatus, HangInfo | None]:
    """Map a finished process into status + optional hang info (C7-Q4).

    Step-cap signature takes precedence over the generic hang; both force ``HUNG``. A
    nonzero exit without any hang signature is a crash.
    """
    if _STEP_CAP_MARKER in stdout:
        return RunStatus.HUNG, HangInfo(reason="step_cap", limit_value=config.max_time_s)
    if timed_out or (returncode not in (None, 0) and _HANG_MARKER in stderr.lower()):
        return RunStatus.HUNG, HangInfo(reason="wall_clock", limit_value=wall_clock_timeout)
    if returncode == 0:
        return RunStatus.COMPLETED, None
    return RunStatus.CRASHED, None


def _h8(model: BaseModel) -> str:
    """8-char hash token for the trace boundary (``<Kind:hash8>``)."""
    from scenariochef.contracts.common import content_hash

    return content_hash(model)[:8]