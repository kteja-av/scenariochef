#!/usr/bin/env python3
"""Dry-run driver: one ScenarioChef pipeline pass with the real LLM-backed C2.

Loads ``./.env`` (quoted values, shlex-parsed) into the process environment,
drives ``cx_orchestrator.run_request`` with a run-scoped Store, copies the
esmini states CSV out of C7's temp dir, and writes ``summary.json`` plus
``trace.log`` under ``--out-dir``. Prints the summary JSON to stdout.

The API key is only ever read into the process environment; it is never
printed, logged, or persisted. Set ``DRY_RUN_OFFLINE=1`` to skip .env loading
and force the offline null proposer (mechanic tests only).
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from scenariochef.c10_management.store import Store  # noqa: E402 (after sys.path setup)


def _load_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env of KEY="quoted value" lines (shlex handles quotes/spaces)."""
    loaded: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        parts = shlex.split(val.strip())
        loaded[key.strip()] = parts[0] if parts else ""
    return loaded


def _latest(store: Store, run_id: str, kind: str) -> Path | None:
    """Newest persisted artifact file of ``kind`` for ``run_id`` (by rowid)."""
    rows = store.conn.execute(
        "SELECT object_hash FROM records WHERE run_id = ? AND object_kind = ? "
        "ORDER BY rowid DESC LIMIT 1",
        (run_id, kind),
    ).fetchall()
    if not rows:
        return None
    h8 = str(rows[0][0])[:8]
    p = store.artifacts_dir / run_id / f"{kind}-{h8}.json"
    return p if p.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser(prog="dry_run.py")
    ap.add_argument("--request", required=True, help="natural-language request text")
    ap.add_argument("--run-id", required=True, help="trajectory id, e.g. DRY-A1")
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--param", action="append", default=[], metavar="K=V")
    args = ap.parse_args()

    env: dict[str, str] = {}
    if not os.environ.get("DRY_RUN_OFFLINE") and (_REPO / ".env").exists():
        env = _load_dotenv(_REPO / ".env")
        os.environ.update(env)

    from scenariochef import trace
    from scenariochef.cli import KNOWN_DEFAULTS, _parse_params
    from scenariochef.cx_orchestrator.runtime import run_request

    # One subdirectory per run id so parallel/sequential runs never overwrite
    # each other's summary.json (a second run used to clobber the first).
    out = args.out_dir / args.run_id
    out.mkdir(parents=True, exist_ok=True)

    params = _parse_params(args.param)
    request = {"text": args.request, **params} if params else args.request

    log_file = open(out / "trace.log", "w", encoding="utf-8")
    trace.set_log(log_file)
    store = Store(db_path=out / f"{args.run_id}.db", artifacts_dir=out / "artifacts")
    try:
        result = run_request(
            request,
            trajectory_id=args.run_id,
            store=store,
            acknowledgements=KNOWN_DEFAULTS,
            headless=True,
        )
    finally:
        log_file.close()
        trace.set_log(sys.stdout)

    summary: dict[str, object] = {
        "run_id": args.run_id,
        "request": args.request,
        "params": params,
        "outcome": result.outcome.value,
        "iterations": result.iterations,
        "validation_outcome": result.validation_outcome,
        "evaluation_summary": result.evaluation_summary,
        "llm_proposer": bool(env.get("C2_LLM_API_KEY")),
        "artifacts": result.artifacts,
    }
    art = store.artifacts_dir / args.run_id

    # C2 IntentSpec — what the Laguna proposer actually extracted.
    intent_path = _latest(store, args.run_id, "IntentSpec")
    if intent_path:
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
        summary["intent"] = {
            "confidence": intent.get("confidence"),
            "unknowns": intent.get("unknowns"),
            "actors": [
                {
                    "name": a.get("name"),
                    "role": str(a.get("role", "")),
                    "speed_mps": a.get("initial_speed_mps"),
                    "lane_id": (a.get("initial_position") or {}).get("lane_id"),
                    "s_m": (a.get("initial_position") or {}).get("s_m"),
                    "slot_source": (a.get("slot") or {}).get("source"),
                }
                for a in intent.get("actors", [])
            ],
            "maneuvers": [
                {"actor": m.get("actor"), "action": str(m.get("action", "")),
                 "params": m.get("params")}
                for m in intent.get("maneuvers", [])
            ],
            "triggers": [
                {"kind": str(t.get("kind", "")), "params": t.get("params")}
                for t in intent.get("triggers", [])
            ],
        }
        shutil.copy(intent_path, out / "intent.json")

    # C6 ValidationReport — the S1..S6 funnel.
    val_path = _latest(store, args.run_id, "ValidationReport")
    if val_path:
        val = json.loads(val_path.read_text(encoding="utf-8"))
        summary["validation"] = {
            "outcome": val.get("outcome"),
            "stages": [
                {
                    "stage": s.get("stage"),
                    "status": s.get("status"),
                    "errors": [
                        {"code": e.get("code"), "severity": str(e.get("severity", "")),
                         "message": e.get("message")}
                        for e in s.get("errors", [])
                    ],
                }
                for s in val.get("stages", [])
            ],
        }

    # C7 RunRecord — final full-run status; copy the states CSV home.
    run_rows = store.conn.execute(
        "SELECT object_hash FROM records WHERE run_id = ? AND object_kind = 'RunRecord' "
        "ORDER BY rowid",
        (args.run_id,),
    ).fetchall()
    run_records = []
    for (h,) in run_rows:
        p = art / f"RunRecord-{str(h)[:8]}.json"
        if p.exists():
            run_records.append(json.loads(p.read_text(encoding="utf-8")))
    full_runs = [r for r in run_records if r.get("mode") == "full"]
    if full_runs:
        final_run = full_runs[-1]
        simulation: dict[str, object] = {
            "status": final_run.get("status"),
            "exit_code": final_run.get("exit_code"),
            "duration_s": final_run.get("duration_s"),
            "esmini_build": (final_run.get("config") or {}).get("esmini_build"),
            "max_time_s": (final_run.get("config") or {}).get("max_time_s"),
            "hang": final_run.get("hang"),
            "total_full_runs": len(full_runs),
        }
        csv_src = final_run.get("simulation_csv_path")
        if csv_src and Path(csv_src).exists():
            shutil.copy(csv_src, out / "states.csv")
            simulation["states_csv"] = str(out / "states.csv")
        stderr_tail = (final_run.get("stderr_tail") or "").strip()
        if stderr_tail:
            simulation["stderr_tail"] = stderr_tail[-300:]
        summary["simulation"] = simulation

    # C8 EvaluationReport — final metrics and objective results.
    eval_path = _latest(store, args.run_id, "EvaluationReport")
    if eval_path:
        ev = json.loads(eval_path.read_text(encoding="utf-8"))
        summary["evaluation"] = {
            "data_source": ev.get("data_source"),
            "failure_class": ev.get("failure_class"),
            "metrics": [
                {
                    "name": m.get("name"),
                    "value": m.get("value"),
                    "unit": m.get("unit"),
                    "actor_pair": m.get("actor_pair"),
                }
                for m in ev.get("metrics", [])
            ],
            "objectives": [
                {
                    "stub_id": o.get("stub_id"),
                    "kind": o.get("objective_kind"),
                    "passed": o.get("passed"),
                    "detail": o.get("detail"),
                }
                for o in ev.get("objective_results", [])
            ],
        }

    # C9 action log — repair/explore/sim_repair sequence from the store.
    actions = store.conn.execute(
        "SELECT actor_component, action_kind, payload_hash FROM actions "
        "WHERE run_id = ? ORDER BY id",
        (args.run_id,),
    ).fetchall()
    if actions:
        summary["c9_actions"] = [
            {"actor": a, "kind": k} for a, k, _ in actions
        ]

    # The generated .xosc for replay/inspection.
    gen_path = _latest(store, args.run_id, "GeneratedScenario")
    if gen_path:
        gen = json.loads(gen_path.read_text(encoding="utf-8"))
        content = (gen.get("xosc") or {}).get("content")
        if content:
            (out / "scenario.xosc").write_text(content, encoding="utf-8")

    (out / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
