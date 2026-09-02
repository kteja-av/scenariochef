#!/bin/sh
# Deterministic gate: lint + types + tests. Exit nonzero blocks the commit.
# Usage: .harness/gate.sh [--quick]   (--quick skips mypy for inner loops)
set -e
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "gate: missing $PY — run: uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -e \".[dev]\" scenariogeneration" >&2
  exit 1
fi

echo "== ruff =="
.venv/bin/ruff check src tests
echo "== mypy =="
if [ "$1" = "--quick" ]; then
  echo "skipped (--quick)"
else
  .venv/bin/mypy
fi
echo "== pytest =="
.venv/bin/python -m pytest -q
echo "== gate: GREEN =="
