"""Fixed deterministic pool of scenario-type labels.

Keeps the skeleton explicitly "no-logic": a label is assigned to a trajectory by
indexing into a small fixed pool with the trajectory number only. No randomness,
no domain logic, no LLM, no files or DB.
"""

POOL = [
    "cut-in",
    "follow-brake",
    "merge",
    "crossing",
    "lane-change",
    "yield",
]


def scenario_label_for(trajectory_id: str) -> str:
    """Return the deterministic scenario label for a `REQ-NNNN` id."""
    n = int(trajectory_id.split("-")[1])
    return POOL[(n - 1) % len(POOL)]