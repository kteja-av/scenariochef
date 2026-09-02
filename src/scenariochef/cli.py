"""ScenarioChef CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scenariochef.cx_orchestrator.runtime import run_demo, run_request

_DEMO_REQUEST = "ego follows lead in lane -1 at 20 m/s"

# C3 default assumption ids the offline null_proposer binds (DERIVED-3 ack gate). The
# CLI pre-accepts them so the demo request runs through the pipeline; a finer caller can
# omit them and let C1/C2 raise an assumption_ack HITL instead.
KNOWN_DEFAULTS = [
    "gap:osc.trigger.SimulationTime",
    "constraint:typical_gap_20m",
    "constraint:ego_speed_range",
]


def _parse_params(pairs: list[str]) -> dict[str, object]:
    params: dict[str, object] = {}
    for pair in pairs:
        key, _, val = pair.partition("=")
        key = key.strip()
        if not key:
            raise SystemExit(f"invalid --param (expected key=value): {pair!r}")
        try:
            params[key] = int(val)
        except ValueError:
            try:
                params[key] = float(val)
            except ValueError:
                params[key] = val
    return params


def _run_text(text: str, params: dict[str, object]) -> int:
    # A single dict + text request is dispatched by C1 to the NL_PARAMS adapter.
    request = {"text": text, **params} if params else text
    result = run_request(request, acknowledgements=KNOWN_DEFAULTS)
    print(
        f"[run] outcome={result.outcome.value} iterations={result.iterations} "
        f"validation={result.validation_outcome or '-'} "
        f"eval={result.evaluation_summary or '-'}"
    )
    print(f"[run] persisted {len(result.artifacts)} artifacts for run {result.run_id}")
    return 0


def _run_file(path: Path) -> int:
    if not path.exists():
        print(f"[run] file not found: {path}", file=sys.stderr)
        return 2
    result = run_request(path)
    print(
        f"[run] from {path} outcome={result.outcome.value} iterations={result.iterations}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="scenariochef", description="ScenarioChef pipeline")
    ap.add_argument("--demo", action="store_true", help="run the 20-trajectory demo")
    sub = ap.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="run the real pipeline on a request")
    p_run.add_argument("target", nargs="?", help="a .xosc/.xodr file or --text")
    p_run.add_argument("--text", dest="text", help="natural-language request")
    p_run.add_argument("--param", action="append", default=[], metavar="K=V",
                       help="explicit parameter (repeatable)")
    p_run.add_argument("--demo-count", type=int, default=20)

    args = ap.parse_args(argv)

    if args.demo:
        run_demo()
        return 0

    if args.cmd == "run":
        if args.text:
            return _run_text(args.text, _parse_params(args.param))
        if args.target:
            return _run_file(Path(args.target))
        # no target or --text → run the default demo request through the real pipeline
        return _run_text(_DEMO_REQUEST, {})

    # no subcommand → default demo request through the real pipeline
    return _run_text(_DEMO_REQUEST, {})


if __name__ == "__main__":
    sys.exit(main())