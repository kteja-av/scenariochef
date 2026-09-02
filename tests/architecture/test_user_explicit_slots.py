"""ARCH-0002 — user-explicit slots are never rewritten.

C2 proposes without rewriting user-explicit values; C9 repair never touches them;
E08 stays visible instead of being silently snapped. Origin: C2-Q3, C9-Q6,
DERIVED-10, DERIVED-16. Behavioral half is enforced in component tests; this
module guards the structural half once C2/C9 land.
"""

from __future__ import annotations

from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "scenariochef"


def test_c9_exposes_no_slot_mutation_api():
    """C9's public API must not offer a generic 'set slot' on canonical IR fields.

    Repair produces a NEW ScenarioIR (RevisedIR), and user-explicit slots must be
    byte-identical. A generic setter would invite violations, so we refuse one.
    """
    c9 = SRC / "c9_feedback" / "runtime.py"
    if not c9.exists():
        return
    src = c9.read_text().lower()
    for name in ("def set_slot", "def rewrite_slot", "def mutate_slot", "def override_user"):
        assert name not in src, f"C9 must not expose '{name}' (C9-Q6)"


def _is_skeleton(p: Path) -> bool:
    """A runtime is still the no-logic skeleton if it returns placeholder tokens."""
    src = p.read_text()
    return ":IntentSpec>" in src or ":FeedbackAction>" in src


def test_c2_c9_reference_user_explicit_contract():
    """Both C2 and C9 must consult SlotProvenance (source=user_explicit) in code."""
    for pkg in ("c2_understanding", "c9_feedback"):
        p = SRC / pkg / "runtime.py"
        if not p.exists():
            continue
        if _is_skeleton(p):
            continue  # enforced once the real runtime replaces the skeleton
        src = p.read_text()
        assert "user_explicit" in src, (
            f"{pkg} must reference the user_explicit slot source (C2-Q3/C9-Q6)"
        )
