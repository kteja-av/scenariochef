#!/usr/bin/env python3
"""Append a machine-readable trajectory record for a work session/subagent run.

Usage:
  .harness/record.py --loop L1 --task "implement C4 IR" \
      --agent deepseek-singularity-paid --commit-before <sha> --commit-after <sha> \
      --outcome green|red|hitl --tests "12 passed" [--notes "..."]

Writes one JSON line to .harness/trajectories/LOOP-<date>-<n>.jsonl (append per session).
Trajectories are the raw material the experience compiler distills.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

TRAJ_DIR = Path(__file__).resolve().parent / "trajectories"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", required=True, help="loop id, e.g. L1 or WAVE-B2")
    ap.add_argument("--task", required=True)
    ap.add_argument("--agent", required=True)
    ap.add_argument("--commit-before")
    ap.add_argument("--commit-after")
    ap.add_argument("--outcome", required=True, choices=["green", "red", "hitl"])
    ap.add_argument("--tests", default="")
    ap.add_argument("--verification", default="")
    ap.add_argument("--human-corrections", default="")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    rec = {
        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "loop": args.loop,
        "task": args.task,
        "agent": args.agent,
        "commit_before": args.commit_before,
        "commit_after": args.commit_after,
        "outcome": args.outcome,
        "test_results": args.tests,
        "verification": args.verification,
        "human_corrections": args.human_corrections,
        "notes": args.notes,
    }
    TRAJ_DIR.mkdir(parents=True, exist_ok=True)
    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    # one file per day, one line per session/agent-run
    out = TRAJ_DIR / f"LOOP-{today}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=False) + "\n")
    print(f"recorded → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
