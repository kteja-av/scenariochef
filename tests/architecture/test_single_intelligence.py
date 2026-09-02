"""ARCH-0001 — C2 is the ONLY LLM agent in Phase 1.

Structural test: no LLM client/library usage anywhere in src/scenariochef except
src/scenariochef/c2_understanding/. Origin: CX-Q1, DERIVED-8, DERIVED-18, C1-Q6,
C8-Q2, C9-Q2 (frozen in docs/checkpoint.md).
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "scenariochef"
LLM_ALLOWED_PACKAGE = SRC / "c2_understanding"

LLM_IMPORT_MARKERS = (
    "openai",
    "anthropic",
    "litellm",
    "langchain",
    "llama_index",
    "google.generativeai",
    "xai",
)

LLM_CALL_MARKERS = (
    "chat.completions",
    "completions.create",
    "responses.create",
    "messages.create",
)


def _iter_py_files():
    for p in SRC.rglob("*.py"):
        yield p


def test_no_llm_imports_outside_c2():
    offenders = []
    for p in _iter_py_files():
        if p.is_relative_to(LLM_ALLOWED_PACKAGE):
            continue
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError as e:  # a broken file is itself a failure
            raise AssertionError(f"{p}: syntax error {e}") from e
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for n in names:
                if any(marker in n for marker in LLM_IMPORT_MARKERS):
                    offenders.append(f"{p.relative_to(SRC)} imports {n}")
    assert not offenders, "LLM usage outside C2 violates ARCH-0001:\n" + "\n".join(offenders)


def test_no_llm_call_expressions_outside_c2():
    offenders = []
    for p in _iter_py_files():
        if p.is_relative_to(LLM_ALLOWED_PACKAGE):
            continue
        src = p.read_text()
        for marker in LLM_CALL_MARKERS:
            if marker in src:
                offenders.append(f"{p.relative_to(SRC)} contains '{marker}'")
    assert not offenders, "LLM call markers outside C2 violate ARCH-0001:\n" + "\n".join(offenders)


def test_c2_llm_isolated_but_present():
    """C2 package exists and is the only package whose files may mention an LLM client.

    We do NOT require an LLM import in C2 (tests must run offline); we require that
    no other component package mentions one in code (docstrings excluded via AST).
    """
    assert (SRC / "c2_understanding").is_dir(), "C2 package must exist"
