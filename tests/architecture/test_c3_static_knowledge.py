"""ARCH-0003 — C3 is static knowledge only.

Structural tests: no runtime write-back into the C3 store, and the C3 runtime
exposes retrieval-only APIs. Origin: C3-Q2, C3-Q3, C3-Q4, DERIVED-2.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "scenariochef"
C3 = SRC / "c3_knowledge"

FORBIDDEN_WRITE_FUNCS = ("write", "append", "update", "insert", "save", "commit", "executemany")


def test_c3_runtime_defines_no_write_api():
    runtime = C3 / "runtime.py"
    assert runtime.exists(), "C3 runtime must exist"
    tree = ast.parse(runtime.read_text())
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name.lower()
            assert not any(w in name for w in FORBIDDEN_WRITE_FUNCS), (
                f"C3 runtime function '{node.name}' looks like a write API — "
                "C3 is retrieval-only (C3-Q4)"
            )


def test_c3_no_runtime_import_of_c6_c7_c10():
    """C3 must not depend on runtime components (no dry-run enrichment, DERIVED-2)."""
    forbidden = ("c6_validation", "c7_esmini", "c8_evaluation", "c10_management")
    for p in C3.rglob("*.py"):
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not any(f in node.module for f in forbidden), (
                    f"{p.relative_to(SRC)} imports {node.module} — C3 must not read "
                    "runtime results (DERIVED-2)"
                )


def test_no_component_writes_c3_store():
    """Nothing outside C3 may open the C3 knowledge store for writing."""
    store_names = ("knowledge_store", "k3_matrix", "c3_graph")
    for p in SRC.rglob("*.py"):
        if p.is_relative_to(C3):
            continue
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Attribute) and child.attr in ("write", "append", "update"):
                    # only flag when the target references a c3 store object
                    target = getattr(child, "value", None)
                    if isinstance(target, ast.Name) and any(
                        s in target.id.lower() for s in store_names
                    ):
                        raise AssertionError(
                            f"{p.relative_to(SRC)} writes a C3 store — runtime write-back "
                            "is forbidden (C3-Q4)"
                        )
