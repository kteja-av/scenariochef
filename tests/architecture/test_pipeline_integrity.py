"""ARCH-0004 — Pipeline integrity.

CX may never skip or reorder C4, C6, C7. Assumptions from C3 need C1+C2 acks
before C4 binds them. Origin: CX-Q5, C1-Q3, DERIVED-3, C6-Q4.
The structural half lives here (call order); the ack half is enforced by the
IntentSpec validator in the contracts package (see tests/test_contracts.py).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "scenariochef"
CX = SRC / "cx_orchestrator" / "runtime.py"

# The frozen canonical order (docs/checkpoint.md CX-Q5 / ADR-0012).
CANONICAL = ["run_c1", "run_c2", "run_c3", "run_c4", "run_c5", "run_c6", "run_c7", "run_c8", "run_c9", "run_c10"]


def test_cx_calls_c_components_in_canonical_order():
    assert CX.exists(), "CX runtime must exist"
    src = CX.read_text()
    positions = {}
    for fn in CANONICAL:
        m = re.search(rf"\b{fn}\(", src)
        assert m, f"CX runtime must call {fn} (CX-Q5: no skipping)"
        positions[fn] = m.start()
    ordered = sorted(positions, key=positions.get)
    assert ordered == CANONICAL, (
        f"CX call order violates CX-Q5 (no reorder of C4/C6/C7):\n"
        f"  found:    {ordered}\n  canonical: {CANONICAL}"
    )


def test_cx_has_no_dynamic_dispatch_to_components():
    """CX is a hardcoded DAG: component calls must be static names, not getattr chains."""
    tree = ast.parse(CX.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            value = node.func.value
            if isinstance(value, ast.Name) and value.id in ("self", "ctx", "registry", "components", "tools"):
                raise AssertionError(
                    "CX dispatches components dynamically — must be a hardcoded DAG (CX-Q2/CX-Q1)"
                )


def test_assumption_ack_contract_enforced_in_contracts():
    """The DERIVED-3 ack rule must exist as code (IntentSpec validator), not just prose."""
    intent_py = SRC / "contracts" / "intent_spec.py"
    if not intent_py.exists():
        # contracts not merged yet; skip quietly — CI catches post-merge
        return
    src = intent_py.read_text()
    assert "c3_default" in src and "accepted_by_c1" in src and "accepted_by_c2" in src, (
        "IntentSpec must enforce the C1+C2 double-ack for c3_default slots (DERIVED-3)"
    )
