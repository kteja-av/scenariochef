#!/usr/bin/env python3
"""Promotion ladder: advance/demote experience lifecycle states.

Usage:
  .harness/promote.py observe   <ID>        # same class seen again → bump counters
  .harness/promote.py verify    <ID>        # mark last_verified=today, +times_prevented
  .harness/promote.py supersede <ID> <NEW>  # link and retire old rule
  .harness/promote.py disprove  <ID>        # rule no longer holds
  .harness/promote.py promote   <ID>        # ACTIVE rule → executable invariant:
                                           #   requires evals/regression test node id
  .harness/promote.py status                 # summary table

Promotion criteria (from the harness design):
  - episode → rule: automatic when times_prevented >= 1 (observed again)
  - rule → invariant: requires the entry to carry required_check referencing a
    pytest node id under evals/regression/, else promotion is refused.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent
EXP_DIR = HARNESS / "experiences"
INV_DIR = HARNESS / "invariants"
EVAL_CATALOG = HARNESS / "evals" / "regression" / "catalog.json"

# re-exec under the project venv (has pyyaml) when invoked with system python3
_VENV_PY = HARNESS.parent / ".venv" / "bin" / "python"
if _VENV_PY.exists() and Path(sys.executable).resolve() != _VENV_PY.resolve():
    os.execv(str(_VENV_PY), [str(_VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]])


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")


def _load(path: Path) -> dict:
    import yaml

    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return data


def _save(path: Path, data: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _find(exp_id: str) -> Path:
    p = EXP_DIR / f"{exp_id}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"no experience {p}")
    return p


def _load_catalog() -> dict:
    import json

    if EVAL_CATALOG.exists():
        return json.loads(EVAL_CATALOG.read_text())
    return {"invariants": []}


def _save_catalog(cat: dict) -> None:
    import json

    EVAL_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    EVAL_CATALOG.write_text(json.dumps(cat, indent=2, sort_keys=False) + "\n")


def observe(exp_id: str) -> str:
    p = _find(exp_id)
    d = _load(p)
    d["last_observed"] = _now()
    d["failure_count"] = int(d.get("failure_count", 0)) + 1
    # episode → rule promotion is automatic on re-observation
    level = d.get("level", "episode")
    if level == "episode" and int(d["failure_count"]) >= 2:
        d["level"] = "rule"
        _save(p, d)
        return f"{exp_id}: observed again, promoted episode → rule"
    _save(p, d)
    return f"{exp_id}: last_observed={d['last_observed']} failure_count={d['failure_count']}"


def verify(exp_id: str) -> str:
    p = _find(exp_id)
    d = _load(p)
    d["last_verified"] = _now()
    d["times_prevented"] = int(d.get("times_prevented", 0)) + 1
    _save(p, d)
    return f"{exp_id}: verified today, times_prevented={d['times_prevented']}"


def supersede(exp_id: str, new_id: str) -> str:
    p = _find(exp_id)
    d = _load(p)
    d["status"] = "SUPERSEDED"
    d["superseded_by"] = new_id
    _save(p, d)
    return f"{exp_id}: SUPERSEDED by {new_id}"


def disprove(exp_id: str) -> str:
    p = _find(exp_id)
    d = _load(p)
    d["status"] = "DISPROVEN"
    _save(p, d)
    deleg = f" (delegate invariants: {d.get('required_check', 'none')})" if d.get("required_check") else ""
    return f"{exp_id}: DISPROVEN{deleg}"


def promote(exp_id: str) -> str:
    p = _find(exp_id)
    d = _load(p)
    if d.get("status") != "ACTIVE":
        return f"{exp_id}: refuse — status is {d.get('status')}, only ACTIVE entries promote"
    check = d.get("required_check")
    if not check or "evals/regression" not in str(check):
        return (
            f"{exp_id}: refuse — required_check must reference a pytest node under "
            "evals/regression/ (write the regression test first; the gate owns enforcement)"
        )
    # copy the rule to invariants/ and register in the eval catalog
    INV_DIR.mkdir(exist_ok=True)
    inv = {
        "id": d["id"],
        "rule": d.get("correct_rule"),
        "trigger": d.get("trigger"),
        "scope": d.get("scope"),
        "severity": d.get("severity", "HIGH"),
        "required_check": check,
        "origin_experience": str(d.get("source", "")),
        "created_at": _now(),
        "last_verified": _now(),
    }
    _save(INV_DIR / f"{d['id']}.yaml", inv)
    d["level"] = "invariant"
    d["last_verified"] = _now()
    _save(p, d)
    cat = _load_catalog()
    cat.setdefault("invariants", []).append(
        {"id": d["id"], "rule": inv["rule"], "test": check}
    )
    _save_catalog(cat)
    return f"{exp_id}: promoted to invariant; gate now enforces {check}"


def status() -> str:
    rows = []
    for p in sorted(EXP_DIR.glob("*.yaml")):
        try:
            d = _load(p)
        except Exception as e:  # noqa: BLE001
            rows.append((p.stem, "?", "?", f"unreadable: {e}"))
            continue
        rows.append(
            (
                str(d.get("id", p.stem)),
                str(d.get("status", "?")),
                str(d.get("level", "episode")),
                f"prevented={d.get('times_prevented', 0)} failed={d.get('failure_count', 0)}",
            )
        )
    if not rows:
        return "no experiences yet"
    w = max(len(r[0]) for r in rows) + 2
    head = f"{'ID'.ljust(w)}{'STATUS'.ljust(12)}{'LEVEL'.ljust(12)}COUNTERS"
    return "\n".join([head] + [f"{r[0].ljust(w)}{r[1].ljust(12)}{r[2].ljust(12)}{r[3]}" for r in rows])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["observe", "verify", "supersede", "disprove", "promote", "status"])
    ap.add_argument("id", nargs="?", default=None)
    ap.add_argument("new_id", nargs="?", default=None)
    args = ap.parse_args()
    try:
        if args.cmd == "status":
            print(status())
            return 0
        if not args.id:
            ap.error(f"{args.cmd} needs an experience id")
        if args.cmd == "observe":
            msg = observe(args.id)
        elif args.cmd == "verify":
            msg = verify(args.id)
        elif args.cmd == "supersede":
            if not args.new_id:
                ap.error("supersede needs <ID> <NEW_ID>")
            msg = supersede(args.id, args.new_id)
        elif args.cmd == "disprove":
            msg = disprove(args.id)
        else:
            msg = promote(args.id)
        print(msg)
        return 0
    except Exception as e:  # noqa: BLE001 - CLI boundary
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
