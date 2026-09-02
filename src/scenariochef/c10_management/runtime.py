"""C10 — Scenario Management: persistence, provenance, and artifact storage."""

from __future__ import annotations

from pydantic import BaseModel

from .. import trace
from ..contracts.common import semantic_hash
from ..contracts.persistence_record import ActionLog, PersistenceRecord
from .store import Store


def run_c10(
    record: object,
    trajectory_id: str = "REQ-0001",
    store: Store | None = None,
    run_id: str | None = None,
) -> PersistenceRecord | None:
    """Persist ``record`` to the deterministic store, tracing step 11.

    - An ``ActionLog`` is logged to the actions table and returns ``None``.
    - Any non-``BaseModel`` payload is a log-free skip (returns ``None``).
    - A ``BaseModel`` artifact is content-addressed and returns its record.
    """
    if not isinstance(record, BaseModel):
        return None

    active_store = store if store is not None else Store()
    active_run = run_id if run_id is not None else trajectory_id

    if isinstance(record, ActionLog):
        active_store.log_action(active_run, record)
        return None

    kind = type(record).__name__
    h8 = semantic_hash(record)[:8]
    trace.emit(11, "C10", "IN", f"<{kind}:{h8}>", trajectory_id)
    rec = active_store.persist(active_run, record, kind)
    trace.emit(11, "C10", "OUT", f"<persisted:{rec.record_id}>", trajectory_id)
    return rec