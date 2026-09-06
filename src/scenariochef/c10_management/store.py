"""C10 → SQLite-backed persistence store.

Every artifact is content-addressed: a sha256 hash of the full canonical JSON
dump (including ``meta``/created_at) selects the file path, so the same logical
object produced at different times gets distinct hashes but identical files when
identical (C10-Q2). No dedup (C10-Q5): all objects are always written and every
record row is kept (C10-Q3), enabling full-lineage queries (C10-Q4).

Determinism (ARCH-0001): the schema is created idempotently with CREATE IF NOT
EXISTS; record_id sequence numbers come from COUNT(*) so identical run orderings
yield identical ids; created_at is pinned to the fixed sentinel (BLD-0001).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..contracts.common import TraceMeta
from ..contracts.persistence_record import ActionLog, LineageMap, PersistenceRecord

# BLD-0001: fixed sentinel keeps artifacts/DB/reproducible builds deterministic.
_CREATED_AT = "2000-01-01T00:00:00+00:00"

# Bounded retries for record-id allocation under concurrent writers.
_MAX_RECORD_ID_ATTEMPTS = 5
_SENTINEL_META = TraceMeta(
    request_id="",
    trajectory_id="",
    created_at=_CREATED_AT,
    produced_by="C10",
)


class Store:
    """Content-addressed artifact store backed by SQLite lineage records."""

    def __init__(
        self,
        db_path: Path = Path("artifacts/scenariochef.db"),
        artifacts_dir: Path = Path("artifacts"),
    ) -> None:
        self.db_path = db_path
        self.artifacts_dir = artifacts_dir
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables and indexes idempotently (ARCH-0001 deterministic)."""
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    record_id      TEXT PRIMARY KEY,
                    run_id         TEXT NOT NULL,
                    object_kind    TEXT NOT NULL,
                    object_hash    TEXT NOT NULL,
                    path           TEXT NOT NULL,
                    created_at     TEXT NOT NULL,
                    lineage_json   TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id          TEXT NOT NULL,
                    actor_component TEXT NOT NULL,
                    action_kind     TEXT NOT NULL,
                    payload_hash    TEXT NOT NULL,
                    ts              TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_run_id ON records(run_id)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_object_kind ON records(object_kind)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_records_object_hash ON records(object_hash)"
            )

    def persist(
        self,
        run_id: str,
        obj: BaseModel,
        kind: str,
        lineage: LineageMap | None = None,
    ) -> PersistenceRecord:
        """Write ``obj`` as a content-addressed JSON artifact and record its lineage."""
        obj_json = obj.model_dump_json(indent=2)
        obj_hash = hashlib.sha256(obj_json.encode()).hexdigest()
        h8 = obj_hash[:8]

        subdir = self.artifacts_dir / run_id
        subdir.mkdir(parents=True, exist_ok=True)
        path = subdir / f"{kind}-{h8}.json"
        path.write_text(obj_json)

        lineage = lineage if lineage is not None else LineageMap()
        lineage_json = json.dumps(lineage.model_dump(), sort_keys=True)

        rec = PersistenceRecord(
            meta=_SENTINEL_META,
            record_id="",
            run_id=run_id,
            object_kind=kind,
            object_hash=obj_hash,
            path=str(path),
            lineage=lineage,
        )
        # record_id: sequence per run. COUNT(*) is not multi-writer safe (two writers
        # can observe the same count); instead derive the next id from the current MAX
        # sequence and retry the INSERT on a PRIMARY KEY collision, so concurrent
        # writers serialize instead of failing.
        for _attempt in range(_MAX_RECORD_ID_ATTEMPTS):
            with self.conn:
                row = self.conn.execute(
                    "SELECT MAX(CAST(SUBSTR(record_id, ?) AS INTEGER)) FROM records "
                    "WHERE run_id = ? AND record_id LIKE ?",
                    (len(f"SC-{run_id}-") + 1, run_id, f"SC-{run_id}-%"),
                ).fetchone()
                n = int(row[0] or 0) + 1
                record_id = f"SC-{run_id}-{n}"
                try:
                    self.conn.execute(
                        """
                        INSERT INTO records
                            (record_id, run_id, object_kind, object_hash, path,
                             created_at, lineage_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record_id,
                            run_id,
                            kind,
                            obj_hash,
                            str(path),
                            _CREATED_AT,
                            lineage_json,
                        ),
                    )
                except sqlite3.IntegrityError:
                    continue  # concurrent writer took this id; recompute and retry
                rec = rec.model_copy(update={"record_id": record_id})
                return rec
        raise RuntimeError(
            f"could not allocate a record_id for run {run_id!r} "
            f"after {_MAX_RECORD_ID_ATTEMPTS} attempts"
        )

    def log_action(self, run_id: str, action: ActionLog) -> None:
        """Insert one C2/C9 action-log row."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO actions
                    (run_id, actor_component, action_kind, payload_hash, ts)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    action.actor_component,
                    action.action_kind,
                    action.payload_hash,
                    action.ts,
                ),
            )

    def query_lineage(self, run_id: str) -> list[PersistenceRecord]:
        """All persisted artifacts for a run, in insertion order."""
        rows = self.conn.execute(
            """
            SELECT record_id, run_id, object_kind, object_hash, path, created_at,
                   lineage_json
            FROM records
            WHERE run_id = ?
            ORDER BY rowid
            """,
            (run_id,),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def query_by_feature(self, feature_key: str) -> list[PersistenceRecord]:
        """Validation reports whose lineage references ``feature_key``.

        Phase-1 LIKE substring scan against the serialized lineage JSON
        (C10-Q4). Because lineage only holds sha256 hashes, the key must
        itself be a hash prefix; a later phase should upgrade this to a
        materialized keyed index once hashes become resolvable to features.
        """
        rows = self.conn.execute(
            """
            SELECT record_id, run_id, object_kind, object_hash, path, created_at,
                   lineage_json
            FROM records
            WHERE object_kind = 'ValidationReport'
              AND lineage_json LIKE '%' || ? || '%'
            ORDER BY rowid
            """,
            (feature_key,),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    @staticmethod
    def _row_to_record(row: tuple[Any, ...]) -> PersistenceRecord:
        (
            record_id,
            run_id,
            object_kind,
            object_hash,
            path,
            _created_at,
            lineage_json,
        ) = (str(c) for c in row)
        lineage = LineageMap.model_validate(json.loads(lineage_json))
        return PersistenceRecord(
            meta=_SENTINEL_META,
            record_id=record_id,
            run_id=run_id,
            object_kind=object_kind,
            object_hash=object_hash,
            path=path,
            lineage=lineage,
        )

    def close(self) -> None:
        """Close the underlying connection."""
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()