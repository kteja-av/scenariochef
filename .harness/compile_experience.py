#!/usr/bin/env python3
"""Compile a session outcome into a persistent experience entry.

Usage:
  .harness/compile_experience.py --draft path/to/draft.yaml
  .harness/compile_experience.py --inline 'id: X; mistake: ...; correct_rule: ...'

Draft YAML fields:
  id (required, unique), scope (repo/area/files), trigger (when relevant),
  mistake, root_cause, correct_rule, required_check, example_fix,
  severity, failure_class, confidence, source (checkpoint/trajectory id)

Compiler duties (anti-slop):
  - refuse schema-invalid entries
  - refuse duplicate ids
  - refuse near-duplicates of ACTIVE entries (same failure_class + trigger)
  - normalize lifecycle fields (created_at, last_observed, status=ACTIVE)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import os
import re
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
EXP_DIR = HARNESS / "experiences"

# re-exec under the project venv (has pyyaml) when invoked with system python3
_VENV_PY = HARNESS.parent / ".venv" / "bin" / "python"
if _VENV_PY.exists() and Path(sys.executable).resolve() != _VENV_PY.resolve():
    os.execv(str(_VENV_PY), [str(_VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]])

REQUIRED = ("id", "trigger", "correct_rule")
ALLOWED = {
    "id", "scope", "trigger", "when", "mistake", "root_cause", "correct_rule",
    "required_check", "example_fix", "severity", "failure_class", "confidence",
    "source", "status", "created_at", "last_observed", "last_verified",
    "times_prevented", "failure_count", "superseded_by",
}
LIFECYCLE_DEFAULTS = {
    "status": "ACTIVE",
    "times_prevented": 0,
    "failure_count": 0,
}


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")


def _parse_yaml(path: Path) -> dict:
    import yaml

    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return data


def _parse_inline(text: str) -> dict:
    data: dict = {}
    for part in text.split(";"):
        m = re.match(r"^([a-z_]+):\s*(.*)$", part.strip(), re.I)
        if m:
            data[m.group(1)] = m.group(2).strip()
    return data


def _render_yaml(data: dict) -> str:
    import yaml

    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def compile_entry(draft: dict, yes: bool = False) -> tuple[bool, str]:
    missing = [k for k in REQUIRED if not draft.get(k)]
    if missing:
        return False, f"missing required fields: {missing}"

    unknown = set(draft) - ALLOWED
    if unknown:
        return False, f"unknown fields (fix or extend ALLOWED deliberately): {sorted(unknown)}"

    exp_id = str(draft["id"]).strip()
    if not re.fullmatch(r"[A-Z]{2,6}-[0-9]{3,5}", exp_id):
        return False, (
            f"id '{exp_id}' must look like AREA-0000 (2-6 letters, 3-5 digits) "
            "so ids sort and stay greppable"
        )

    dest = EXP_DIR / f"{exp_id}.yaml"
    if dest.exists():
        return False, f"duplicate id: {dest} already exists"

    # near-duplicate guard: same failure_class + similar trigger
    fc = str(draft.get("failure_class", "")).lower()
    trig = str(draft.get("trigger", "")).lower()
    for other in EXP_DIR.glob("*.yaml"):
        try:
            o = _parse_yaml(other)
        except Exception:
            continue
        o_fc = str(o.get("failure_class", "")).lower()
        o_trig = str(o.get("trigger", "")).lower()
        if fc and o_fc == fc and difflib.SequenceMatcher(None, trig, o_trig).ratio() > 0.75:
            return False, (
                f"near-duplicate of {other.name} (failure_class + trigger similarity "
                f">0.75). Extend that entry instead of adding a new one."
            )

    entry = dict(draft)
    entry["id"] = exp_id
    entry["created_at"] = _now()
    entry["last_observed"] = _now()
    entry.update({k: v for k, v in LIFECYCLE_DEFAULTS.items() if k not in entry})

    if not yes:
        print(_render_yaml(entry))
        print(f"--> would write {dest}")
        print("Re-run with --yes to accept.")
        return False, "dry-run"

    EXP_DIR.mkdir(exist_ok=True)
    dest.write_text(_render_yaml(entry))
    return True, f"wrote {dest}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", type=Path)
    ap.add_argument("--inline", type=str)
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    if not args.draft and not args.inline:
        ap.error("need --draft or --inline")
    try:
        draft = _parse_yaml(args.draft) if args.draft else _parse_inline(args.inline)
        ok, msg = compile_entry(draft, yes=args.yes)
        print(msg)
        return 0 if ok else 1
    except Exception as e:  # noqa: BLE001 - CLI boundary
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
