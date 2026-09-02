"""C7 → RunRecord: one esmini execution (preflight or full).

The esmini binary is discovered via the ``ESMINI_BIN`` env var or PATH (C7). When
absent, the pipeline must remain runnable: status is ``SKIPPED_NO_BINARY`` with a
stderr note — never a Python exception. Hang policy (C7-Q4): either a wall-clock timeout
or a step cap trips termination.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .common import TraceMeta


class RunStatus(StrEnum):
    COMPLETED = "completed"
    HUNG = "hung"
    CRASHED = "crashed"
    SKIPPED_NO_BINARY = "skipped_no_binary"


class HangInfo(BaseModel):
    """Why a run was terminated as hung."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: Literal["wall_clock", "step_cap"]
    limit_value: float


class RunConfig(BaseModel):
    """Reproducible simulation configuration (C7-Q2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    esmini_build: str
    dt_s: float
    seed: int
    max_time_s: float
    headless: bool = True
    osi: bool = False
    # ``asset_search_path`` is passed to esmini via ``--path`` so relative OpenDRIVE map
    # and catalog paths inside the .xosc resolve from the repo root (esmini searches the
    # declared path for files it cannot find relative to the scenario file).
    asset_search_path: str | None = None


class RunRecord(BaseModel):
    """The C7 output: stdout/stderr tails, exit code, timing, hang info, status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: TraceMeta
    config: RunConfig
    mode: Literal["preflight", "full"]
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""  # last 8 KB each
    simulation_csv_path: str | None = None  # Path as str for JSON round-trip
    osi_trace_path: str | None = None
    hang: HangInfo | None = None
    duration_s: float = 0.0
    sim_time_s: float | None = None
    status: RunStatus