"""C10 → SQLite scenario-management store and runtime persistence tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scenariochef.c10_management.runtime import run_c10
from scenariochef.c10_management.store import Store
from scenariochef.contracts.common import TraceMeta
from scenariochef.contracts.intent_spec import IntentSpec
from scenariochef.contracts.persistence_record import ActionLog, LineageMap


def _meta() -> TraceMeta:
    return TraceMeta(
        request_id="REQ-1",
        trajectory_id="REQ-0001",
        produced_by="C2",
    )


def _intent_spec() -> IntentSpec:
    return IntentSpec(
        meta=_meta(),
        actors=[],
        maneuvers=[],
        triggers=[],
        constraints=[],
        objectives=[],
        confidence=1.0,
        unknowns=[],
        c3_evidence_refs=[],
    )


@pytest.fixture()
def store(tmp_path: Path) -> Store:
    return Store(db_path=tmp_path / "sc.db", artifacts_dir=tmp_path / "artifacts")


def test_persist_writes_file_and_row(store: Store, tmp_path: Path) -> None:
    spec = _intent_spec()
    rec = store.persist("REQ-1", spec, "IntentSpec")

    assert rec.record_id == "SC-REQ-1-1"
    assert Path(rec.path).exists()
    assert Path(rec.path).is_relative_to(tmp_path / "artifacts")
    # content-addressed path under artifacts/<run_id>/
    assert rec.path.startswith(str(tmp_path / "artifacts" / "REQ-1"))

    row = store.conn.execute(
        "SELECT object_kind, object_hash FROM records WHERE record_id = ?",
        (rec.record_id,),
    ).fetchone()
    assert row is not None
    assert row[0] == "IntentSpec"
    assert row[1] == rec.object_hash

    written = json.loads(Path(rec.path).read_text())
    assert written["meta"]["request_id"] == "REQ-1"


def test_no_dedup_second_persist_same_file(store: Store) -> None:
    spec = _intent_spec()
    rec1 = store.persist("REQ-1", spec, "IntentSpec")
    rec2 = store.persist("REQ-1", spec, "IntentSpec")

    assert rec1.record_id == "SC-REQ-1-1"
    assert rec2.record_id == "SC-REQ-1-2"  # distinct id, no dedup (C10-Q5)
    assert rec1.path == rec2.path  # same content, same address
    assert rec1.object_hash == rec2.object_hash


def test_query_lineage_preserves_order(store: Store) -> None:
    store.persist("REQ-1", _intent_spec(), "IntentSpec")
    store.persist("REQ-1", _intent_spec(), "IntentSpec")
    store.persist("REQ-1", _intent_spec(), "IrSpec")

    lineage = store.query_lineage("REQ-1")
    assert [r.record_id for r in lineage] == [
        "SC-REQ-1-1",
        "SC-REQ-1-2",
        "SC-REQ-1-3",
    ]
    assert [r.object_kind for r in lineage] == ["IntentSpec", "IntentSpec", "IrSpec"]
    # other runs excluded
    assert store.query_lineage("OTHER") == []


def test_log_action_rows(store: Store) -> None:
    action = ActionLog(
        actor_component="C2", action_kind="propose", payload_hash="abc123", ts="t1"
    )
    store.log_action("REQ-1", action)

    rows = store.conn.execute(
        "SELECT run_id, actor_component, action_kind, payload_hash, ts FROM actions"
    ).fetchall()
    assert rows == [("REQ-1", "C2", "propose", "abc123", "t1")]


def test_query_by_feature_lineage_contains_key(store: Store) -> None:
    lineage = LineageMap(intent_hash="feat-abcdef0123")
    store.persist("REQ-1", _intent_spec(), "IntentSpec")  # not a ValidationReport
    store.persist("REQ-1", _intent_spec(), "ValidationReport", lineage=lineage)

    found = store.query_by_feature("feat-abcdef0123")
    assert len(found) == 1
    assert found[0].record_id == "SC-REQ-1-2"
    assert found[0].lineage.intent_hash == "feat-abcdef0123"

    # key absent → nothing found
    assert store.query_by_feature("missing") == []


def test_plain_dict_skipped(tmp_path: Path) -> None:
    store = Store(db_path=tmp_path / "sc.db", artifacts_dir=tmp_path / "artifacts")
    out = run_c10({"not": "a model"}, trajectory_id="REQ-1", store=store)
    assert out is None
    assert store.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0


def test_action_via_runtime(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    store = Store(db_path=tmp_path / "sc.db", artifacts_dir=tmp_path / "artifacts")
    action = ActionLog(
        actor_component="C9", action_kind="repair", payload_hash="deadbeef", ts="t"
    )
    out = run_c10(action, trajectory_id="REQ-1", store=store)
    assert out is None
    assert store.conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0] == 1


def test_store_init_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "sc.db"
    arts = tmp_path / "artifacts"
    Store(db_path=db, artifacts_dir=arts)
    # second open of same db — idempotent schema, no error
    s2 = Store(db_path=db, artifacts_dir=arts)
    s2.persist("REQ-1", _intent_spec(), "IntentSpec")
    assert s2.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 1


def test_no_repo_pollution(tmp_path: Path) -> None:
    store = Store(db_path=tmp_path / "sc.db", artifacts_dir=tmp_path / "artifacts")
    store.persist("REQ-1", _intent_spec(), "IntentSpec")
    # everything lives under tmp_path
    assert (tmp_path / "sc.db").exists()
    assert (tmp_path / "artifacts").is_dir()
    # nothing was written to the repo-level default artifact location
    db = Path("artifacts/scenariochef.db")
    assert not db.exists()
    assert not list(Path("artifacts").glob("REQ-1/*.json"))