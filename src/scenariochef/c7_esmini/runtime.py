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

# Default esmini asset search path: the repo root that ships assets/maps and
# assets/catalogs. Resolved from this file so it is independent of the process CWD
# (src/scenariochef/c7_esmini/runtime.py -> parents[2] is the repo root when the
# package lives in <repo>/src; for site-packages installs the env var or explicit
# config must supply it).
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Modern esmini (>= v2) removed --timeout/--terminate_on_end: run duration is governed by
# the scenario StopTrigger (C5 always emits one). Legacy 0.x/1.x builds still need them.
# The probe is cached per binary and fails safe to legacy so unparseable/stand-in binaries
# keep the historical argv.
_MODERN_VERSION_CACHE: dict[str, bool] = {}


def _is_modern_esmini(binary: str) -> bool:
    """True when the binary reports esmini >= v2 (no --timeout/--terminate_on_end)."""
    cached = _MODERN_VERSION_CACHE.get(binary)
    if cached is not None:
        return cached
    modern = False
    try:
        proc = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=5
        )
        import re

        match = re.search(r"v(\d+)\.", proc.stdout or "")
        if match:
            modern = int(match.group(1)) >= 2
    except (OSError, subprocess.TimeoutExpired):
        modern = False
    _MODERN_VERSION_CACHE[binary] = modern
    return modern


def make_config(
    seed: int = 42,
    dt_s: float = 0.05,
    max_time_s: float = 30.0,
    headless: bool = True,
    osi: bool = False,
    esmini_build: str | None = None,
    asset_search_path: str | None = None,
) -> RunConfig:
    """Build a reproducible ``RunConfig`` (C7-Q2).

    ``esmini_build`` resolves to the ``ESMINI_BUILD`` env var when not given, else the
    pinned ``esmini-0.10`` default. Batch runs default to ``headless`` (C7-Q5).
    ``asset_search_path`` is handed to esmini as ``--path`` so relative .xodr map and
    catalog references in the generated .xosc resolve from the repo root.
    """
    build = esmini_build or os.environ.get("ESMINI_BUILD", _DEFAULT_BUILD)
    search = asset_search_path or os.environ.get("ESMINI_ASSET_PATH") or str(_REPO_ROOT)
    return RunConfig(
        esmini_build=build,
        dt_s=dt_s,
        seed=seed,
        max_time_s=max_time_s,
        headless=headless,
        osi=osi,
        asset_search_path=search,
    )


def run_c7(
    generated_scenario: GeneratedScenario,
    trajectory_id: str = "REQ-0001",
    config: RunConfig | None = None,
    mode: Literal["preflight", "full"] = "full",
    workdir: Path | None = None,
    param_dist_path: Path | None = None,
    param_permutation: int | None = None,
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
    if param_dist_path is not None and param_permutation is not None:
        # Parameter-sweep mode: the --osc target is the dist file (which names the
        # scenario via its ScenarioFile element); esmini substitutes permutation i.
        argv += [
            "--param_dist", str(param_dist_path),
            "--param_permutation", str(param_permutation),
        ]
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
    _cleanup_workdir(dir_, workdir)

    # --csv_logger writes <stem>_states.csv; in permutation mode esmini appends
    # "_K_of_N" to the filename. Keep the legacy <stem>.csv check for esmini builds
    # that auto-log next to the scenario file.
    csv_path = dir_ / f"{xosc_path.stem}_states.csv"
    if not csv_path.exists() and param_permutation is not None:
        suffix_matches = sorted(dir_.glob(f"{xosc_path.stem}_states_*_of_*.csv"))
        if suffix_matches:
            csv_path = suffix_matches[0]
    if not csv_path.exists():
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


def _cleanup_workdir(dir_: Path, explicit_workdir: Path | None) -> None:
    """Remove the run's scratch directory when C7 created it (hygiene: no temp leak).

    Explicit ``workdir`` callers (tests, sweeps that need per-permutation files)
    keep ownership; when no CSV was produced a C7-owned temp dir has nothing left
    worth keeping, so it is removed.
    """
    if explicit_workdir is not None:
        return
    try:
        if not any(dir_.glob("*.csv")):
            shutil.rmtree(dir_, ignore_errors=True)
    except OSError:
        pass  # never fail the run record over cleanup


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
    # GUI window geometry is space-separated (esmini --window <x y w h>); headless hides it.
    display = ["--window", "60", "60", "800", "400"] if not config.headless else ["--headless"]
    argv = [
        binary,
        *display,
        "--osc",
        str(xosc_path),
        "--seed",
        str(config.seed),
    ]
    if config.headless:
        # Headless batch runs decouple from realtime for throughput; GUI runs realtime
        # so the viewer window is watchable (C7-Q5 debug mode).
        argv += ["--fixed_timestep", str(config.dt_s)]
    if not _is_modern_esmini(binary):
        # Legacy builds (0.x/1.x): --timeout caps sim seconds; preflight truncates to 10.
        timeout_s = (
            min(config.max_time_s, _PREFLIGHT_TIMEOUT_S)
            if mode == "preflight"
            else config.max_time_s
        )
        argv += ["--timeout", str(timeout_s)]
    # ``--path`` lets esmini resolve relative OpenDRIVE map and catalog references inside
    # the .xosc from the configured asset search path (default: repo root).
    if config.asset_search_path:
        argv += ["--path", config.asset_search_path]
    if mode == "preflight" and not _is_modern_esmini(binary):
        argv.append("--terminate_on_end")
    if mode == "full":
        # Real-run data sources for C8 evaluation: per-vehicle state CSV + collision flag.
        argv += ["--csv_logger", str(xosc_path.parent / f"{xosc_path.stem}_states.csv"),
                 "--collision"]
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

# --- Parameter sweep (esmini --param_dist) ----------------------------------

# esmini ParameterValueDistribution template (verified against esmini v3.7.2 with
# --return_nr_permutations and per-permutation CSV output; element/attribute names
# follow the OSC ParameterValueDistribution standard as parsed by
# OSCParameterDistribution.cpp: attribute-based ParameterAssignment/Element).
_PARAM_DIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="1" date="2000-01-01T00:00:00"
              description="ScenarioChef parameter sweep" author="ScenarioChef"/>
  <ParameterValueDistribution>
    <ScenarioFile filepath="{scenario_filename}"/>
    <Deterministic>
      <DeterministicSingleParameterDistribution parameterName="{param_name}">
        <DistributionSet>
{elements}
        </DistributionSet>
      </DeterministicSingleParameterDistribution>
    </Deterministic>
  </ParameterValueDistribution>
</OpenSCENARIO>
"""

_NR_PERMUTATIONS_MARKER = "Nr permutations: "


def run_c7_sweep(
    generated_scenario: GeneratedScenario,
    param_name: str,
    values: list[float],
    trajectory_id: str = "REQ-0001",
    config: RunConfig | None = None,
    workdir: Path | None = None,
) -> list[RunRecord]:
    """Run an esmini parameter sweep over ``values`` for ``param_name``.

    Writes a ParameterValueDistribution referencing the generated .xosc, asks esmini
    for the permutation count, then executes one run per permutation (the .xosc must
    reference the parameter as ``${param_name}`` — the caller (CX/C9) is responsible
    for emitting ParameterDeclarations and $refs; the sweep skips cleanly when esmini
    reports 0 permutations). Returns one RunRecord per permutation, in order.
    """
    if not values:
        return []
    run_config = config if config is not None else make_config()
    binary = _find_binary()
    if binary is None:
        stderr_note = "esmini binary not found (set ESMINI_BIN)"
        return [
            RunRecord(
                meta=TraceMeta(
                    request_id=generated_scenario.meta.request_id,
                    trajectory_id=trajectory_id,
                    created_at=_DETERMINISTIC_CREATED_AT,
                    produced_by=_PRODUCER,
                ),
                config=run_config,
                mode="full",
                exit_code=None,
                stderr_tail=stderr_note,
                duration_s=0.0,
                status=RunStatus.SKIPPED_NO_BINARY,
            )
        ]

    dir_ = workdir if workdir is not None else Path(tempfile.mkdtemp(prefix="c7_sweep_"))
    dir_.mkdir(parents=True, exist_ok=True)
    xosc_path = dir_ / f"{generated_scenario.scenario_name}.xosc"
    xosc_path.write_text(generated_scenario.xosc.content, encoding="utf-8")
    dist_path = dir_ / f"{generated_scenario.scenario_name}.pvd.xosc"
    elements = "\n".join(f'          <Element value="{v}"/>' for v in values)
    dist_path.write_text(
        _PARAM_DIST_TEMPLATE.format(
            scenario_filename=xosc_path.name,
            param_name=param_name,
            elements=elements,
        ),
        encoding="utf-8",
    )

    # Discover the permutation count (esmini prints "Nr permutations: N"). A probe
    # failure is reported as zero permutations (clean skip), not a raised exception —
    # the sweep dir is removed on those paths so scratch space never leaks.
    try:
        probe = subprocess.run(
            [binary, "--headless", "--osc", str(dist_path), "--return_nr_permutations"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        shutil.rmtree(dir_, ignore_errors=True)
        return []
    probe_out = probe.stdout or ""
    if _NR_PERMUTATIONS_MARKER not in probe_out:
        shutil.rmtree(dir_, ignore_errors=True)
        return []
    try:
        count = int(probe_out.split(_NR_PERMUTATIONS_MARKER, 1)[1].split()[0])
    except (IndexError, ValueError):
        shutil.rmtree(dir_, ignore_errors=True)
        return []
    if count <= 0:
        shutil.rmtree(dir_, ignore_errors=True)
        return []

    records: list[RunRecord] = []
    try:
        for index in range(count):
            records.append(
                run_c7(
                    generated_scenario,
                    trajectory_id=trajectory_id,
                    config=run_config,
                    mode="full",
                    workdir=dir_,
                    param_dist_path=dist_path,
                    param_permutation=index,
                )
            )
    finally:
        # C7-owned sweep dirs are scratch: once the records (incl. CSV paths) are
        # captured, remove the directory unless the caller passed an explicit workdir.
        if workdir is None:
            shutil.rmtree(dir_, ignore_errors=True)
    return records
