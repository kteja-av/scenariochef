"""Shared trace emitter: writes one aligned line per pipeline step to the active log stream."""

import sys
from typing import TextIO

# Traces all go to one module-level stream that CX points at a log file; stdout is
# only the fallback sink so a lone emit outside the pipeline still has a target.
_stream: TextIO = sys.stdout


def set_log(stream: TextIO) -> None:
    global _stream
    _stream = stream


def emit(step: int, component: str, direction: str, token: str, trajectory_id: str) -> None:
    print(
        f"{trajectory_id} [step:{step:02d}] {component:<3} {direction:<3} {token}",
        file=_stream,
    )
