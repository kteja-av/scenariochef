#!/usr/bin/env python3
"""Retrieve the 5–15 most relevant lessons for a proposed change.

Usage:
  .harness/retrieve.py --files src/scenariochef/c4_ir/runtime.py tests/test_c4.py \
      [--modules c4 ir positions] [--failure-classes map-binding lanes] [--json]

Keyed on the *proposed change* (files/modules/failure classes), not the user prompt.
Prints a block meant to be pasted into an agent prompt before it codes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parent

# re-exec under the project venv (has pyyaml) when invoked with system python3
_VENV_PY = HARNESS.parent / ".venv" / "bin" / "python"
if _VENV_PY.exists() and Path(sys.executable).resolve() != _VENV_PY.resolve():
    os.execv(str(_VENV_PY), [str(_VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]])

# Weighting: rarer tokens (repo, area, files, trigger keywords) score higher than
# generic narrative words. A small stopword list keeps prose from dominating.
STOPWORDS = {
    "the", "a", "an", "and", "or", "not", "no", "yes", "if", "then", "else",
    "for", "to", "of", "in", "on", "at", "by", "with", "is", "are", "was",
    "be", "been", "do", "does", "did", "this", "that", "these", "those",
    "it", "its", "as", "we", "you", "they", "will", "can", "cannot", "must",
    "should", "may", "might", "from", "into", "when", "what", "which", "who",
    "how", "why", "all", "any", "some", "none", "more", "less", "use", "used",
    "using", "make", "made", "add", "added", "run", "runs", "running", "set",
    "get", "new", "old", "one", "two", "per", "via", "etc", "eg", "ie",
}


def _tokens(text: str) -> list[str]:
    return [
        t for t in re.findall(r"[a-z0-9_.\-]+", text.lower())
        if t not in STOPWORDS and len(t) > 2
    ]


def _load_yaml_lessons() -> list[dict]:
    """Minimal YAML subset reader for our experiences/invariants (no pyyaml dep needed
    by the harness itself; falls back to line-oriented parsing)."""
    lessons: list[dict] = []
    for kind, sub in (("experience", "experiences"), ("invariant", "invariants")):
        d = HARNESS / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
            try:
                import yaml  # type: ignore[import-not-found]

                data = yaml.safe_load(f.read_text()) or {}
                data["_kind"] = kind
                data["_path"] = str(f.relative_to(HARNESS))
                lessons.append(data)
            except ImportError:
                # line-oriented fallback: key: value pairs only
                data: dict = {"id": f.stem}
                for line in f.read_text().splitlines():
                    m = re.match(r"^([a-z_]+):\s*(.+)$", line, re.I)
                    if m:
                        data[m.group(1)] = m.group(2).strip()
                data["_kind"] = kind
                data["_path"] = str(f.relative_to(HARNESS))
                lessons.append(data)
    return lessons


def _score(query_tokens: list[str], lesson: dict) -> tuple[int, list[str]]:
    """Token overlap score between query and lesson fields; returns (score, hits)."""
    fields = " ".join(
        str(lesson.get(k, ""))
        for k in ("id", "scope", "area", "files", "modules", "trigger", "when",
                  "mistake", "rule", "correct_rule", "required_check", "severity",
                  "applies_to", "failure_class", "example_fix")
    )
    field_tokens = set(_tokens(fields))
    hits = sorted(set(query_tokens) & field_tokens)
    # kind weighting: invariants outrank episodic memories at equal overlap
    weight = 2 if lesson.get("_kind") == "invariant" else 1
    return weight * len(hits), hits


def retrieve(
    files: list[str], modules: list[str], failure_classes: list[str], limit: int = 15
) -> list[tuple[int, dict]]:
    query = " ".join(files + modules + failure_classes)
    qt = _tokens(query)
    scored: list[tuple[int, dict]] = []
    for lesson in _load_yaml_lessons():
        score, _ = _score(qt, lesson)
        if score > 0:
            scored.append((score, lesson))
    scored.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    return scored[:limit]


def _render(lessons: list[tuple[int, dict]], as_json: bool) -> str:
    if as_json:
        return json.dumps(
            [
                {
                    "id": l.get("id"),
                    "kind": l.get("_kind"),
                    "status": l.get("status", "ACTIVE"),
                    "severity": l.get("severity", "MEDIUM"),
                    "scope": l.get("scope"),
                    "trigger": l.get("trigger"),
                    "rule": l.get("correct_rule") or l.get("rule"),
                    "check": l.get("required_check"),
                }
                for _, l in lessons
            ],
            indent=2,
        )
    if not lessons:
        return "No relevant historical lessons found."
    lines = ["Historical lessons relevant to this task (from .harness memory):", ""]
    for score, l in lessons:
        sev = str(l.get("severity", "MEDIUM")).upper()
        kind = str(l.get("_kind", "?")).upper()
        rule = l.get("correct_rule") or l.get("rule") or l.get("mistake")
        trig = l.get("trigger") or l.get("when") or l.get("applies_to") or ""
        check = l.get("required_check") or ""
        lines.append(f"[{sev}|{kind}] {l.get('id', '?')} (match {score})")
        lines.append(f"  rule: {rule}")
        if trig:
            lines.append(f"  trigger: {trig}")
        if check:
            lines.append(f"  required check: {check}")
        lines.append("")
    lines.append(
        "Before coding: honor the rules above. They are enforced by the deterministic "
        "gate (.harness/gate.sh) where a required_check exists."
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*", default=[])
    ap.add_argument("--modules", nargs="*", default=[])
    ap.add_argument("--failure-classes", nargs="*", default=[])
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    lessons = retrieve(args.files, args.modules, args.failure_classes, args.limit)
    print(_render(lessons, args.json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
