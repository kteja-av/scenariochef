"""C8 — Observation & Evaluation: metrics and rulebook evaluation.

C8 scores a run against the IR objective stubs using the C8 rulebook thresholds
(``rulebook.yaml``) — never invented (C8-Q1). It is a **deterministic scoring module,
not an agent** (ARCH-0001): no LLM. TTC is ALWAYS paired with its PET for the same
actor pair (C8-Q4). The CSV of per-frame states is the data source (C8-Q5); everything
is stdlib-only, deterministic, and ordering-stable.

If no state data is available (no ``simulation_csv_path`` / missing CSV), metrics are
empty and every IR objective fails with detail ``"no state data"``.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel

from scenariochef import trace
from scenariochef.contracts.common import TraceMeta, Unit
from scenariochef.contracts.evaluation_report import (
    DataSource,
    EvaluationReport,
    Metric,
    MetricName,
    ObjectiveResult,
)

if TYPE_CHECKING:
    from scenariochef.contracts.run_record import RunRecord
    from scenariochef.contracts.scenario_ir import ScenarioIR

_PRODUCER = "C8"
_RULEBOOK_PATH = Path(__file__).with_name("rulebook.yaml")
_DETERMINISTIC_CREATED_AT = "2000-01-01T00:00:00+00:00"

# Bucket width for frame alignment (C8-Q5 CSV is a fixed-step state log).
_BUCKET_S = 0.05
# Rulebook constants (mirror rulebook.yaml; loaded values take precedence).
_COLLISION_THRESHOLD_M = 0.5
_CONFLICT_RADIUS_M = 0.5
_COMPLETION_FRACTION = 0.95

# Failed/detail sentinels (deterministic strings).
_DETAIL_NO_STATE_DATA = "no state data"
_THRESHOLD_NONE = "none"


# A min-TTC frame's geometry: (t, ax, ay, bx, by).
_ConflictFrame = tuple[float, float, float, float, float]


def _load_rulebook() -> dict[str, Any]:
    """Load the rulebook once (module-level cache); return its parsed YAML."""
    if _RULEBOOK not in _CACHE:
        _CACHE[_RULEBOOK] = yaml.safe_load(_RULEBOOK_PATH.read_text(encoding="utf-8"))
    return _CACHE[_RULEBOOK]


_RULEBOOK = "c8_rulebook"
_CACHE: dict[str, dict[str, Any]] = {}


def run_c8(
    run_record: RunRecord,
    trajectory_id: str = "REQ-0001",
    scenario_ir: ScenarioIR | None = None,
) -> EvaluationReport:
    """Pipeline C8 entry: trace step 9 IN/OUT around deterministic evaluation."""
    trace.emit(9, "C8", "IN", f"<RunRecord:{_h8(run_record)}>", trajectory_id)
    report = evaluate(run_record, scenario_ir)
    trace.emit(9, "C8", "OUT", f"<EvaluationReport:{_h8(report)}>", trajectory_id)
    return report


def evaluate(
    run_record: RunRecord,
    scenario_ir: ScenarioIR | None = None,
) -> EvaluationReport:
    """Score one run deterministically against the IR objective stubs."""
    csv_path = run_record.simulation_csv_path
    rulebook = _load_rulebook()

    if csv_path and Path(csv_path).is_file():
        metrics = compute_metrics(Path(csv_path))
        if run_record.sim_time_s is not None:
            metrics.append(_completion_metric(run_record, rulebook))
        data_source = DataSource.CSV
        has_state_data = True
    else:
        metrics = []
        data_source = DataSource.CSV
        has_state_data = False

    objective_results = _evaluate_objectives(scenario_ir, metrics, rulebook, has_state_data)

    if not has_state_data:
        failure_class = "no_state_data"
    elif any(not r.passed for r in objective_results):
        failure_class = "objective_failure"
    else:
        failure_class = None

    meta = TraceMeta(
        request_id=run_record.meta.request_id,
        trajectory_id=run_record.meta.trajectory_id,
        created_at=_DETERMINISTIC_CREATED_AT,
        produced_by=_PRODUCER,
    )
    return EvaluationReport(
        meta=meta,
        metrics=metrics,
        objective_results=objective_results,
        rulebook_version=str(rulebook.get("version", "")),
        data_source=data_source,
        failure_class=failure_class,
    )


def compute_metrics(csv_path: Path) -> list[Metric]:
    """Compute TTC/PET/collision metrics from a CSV state log (C8-Q5).

    Columns: ``t, actor, x, y``. Frames are grouped per actor and aligned between
    each sorted actor pair by nearest bucketed time.

    Returns:
        ``ttc`` + ``pet`` metrics for each pair with a meaningful approach, and
        ``collision`` metrics where any frame gap falls below the threshold. Ordering
        is deterministic: pairs sorted, then ttc/pet/collision per pair.
    """
    rulebook = _load_rulebook()
    collision_threshold = float(
        rulebook.get("constants", {}).get("collision_threshold_m", _COLLISION_THRESHOLD_M)
    )
    conflict_radius = float(
        rulebook.get("constants", {}).get("conflict_radius_m", _CONFLICT_RADIUS_M)
    )
    by_actor = _read_states(csv_path)
    actors = sorted(by_actor)
    metrics: list[Metric] = []
    for i, a in enumerate(actors):
        for b in actors[i + 1 :]:
            pair = (a, b)
            gap_series, min_ttc, min_ttc_frame = _pair_gaps(by_actor[a], by_actor[b])
            if min_ttc is not None and math.isfinite(min_ttc):
                metrics.append(
                    Metric(name=MetricName.TTC, value=min_ttc, unit=Unit.S, actor_pair=pair)
                )
            metrics.append(
                Metric(
                    name=MetricName.PET,
                    value=_pet(by_actor[a], by_actor[b], min_ttc_frame, conflict_radius),
                    unit=Unit.S,
                    actor_pair=pair,
                )
            )
            if min(gap for gap, _ in gap_series) < collision_threshold:
                metrics.append(
                    Metric(name=MetricName.COLLISION, value=1.0, unit=Unit.NONE, actor_pair=pair)
                )
    return metrics


def _bucket(t: float) -> int:
    """Bucket a timestamp to the fixed alignment width (deterministic)."""
    return round(t / _BUCKET_S)


def _read_states(csv_path: Path) -> dict[str, list[tuple[float, float, float]]]:
    """Group per-frame states (t, x, y) per actor, sorted deterministically by t.

    Accepts two schemas:

    - Simple: ``actor,t,x,y`` header (historical/test format).
    - esmini ``--csv_logger``: comment preamble lines (``esmini ...`` / ``Scenario`` /
      ``Number of ...``), a wide ``#<i> <Field> [unit]`` header, one units row, and one
      row per frame with all vehicles side by side. Entities are discovered from the
      ``#<i> Entity_Name`` columns.
    """
    with csv_path.open(newline="", encoding="utf-8") as fh:
        lines = fh.readlines()

    if not lines:
        return {}

    header = next(csv.reader([lines[0]]))
    if "actor" in header and "t" in header:
        return _read_states_simple(csv_path)

    # esmini --csv_logger format: a plain-text preamble (no # prefix: "esmini GIT REV:",
    # "Scenario File Name:", "Number of Vehicles: N"), then the header line starting with
    # "Index", then one row per frame. Locate the header by that leading cell.
    header_idx = next(
        (i for i, line in enumerate(lines) if line.split(",")[0].strip().startswith("Index")),
        None,
    )
    if header_idx is None:
        return {}
    header = next(csv.reader([lines[header_idx]]))
    body = lines[header_idx + 1 :]
    return _read_states_esmini(header, body)


def _read_states_simple(csv_path: Path) -> dict[str, list[tuple[float, float, float]]]:
    """Parse the simple ``actor,t,x,y`` schema (historical format)."""
    by_actor: dict[str, list[tuple[float, float, float]]] = {}
    with csv_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            actor = row["actor"]
            by_actor.setdefault(actor, []).append(
                (float(row["t"]), float(row["x"]), float(row["y"]))
            )
    for frames in by_actor.values():
        frames.sort(key=lambda f: (f[0], f[1], f[2]))
    return by_actor


def _read_states_esmini(
    header: list[str], body: list[str]
) -> dict[str, list[tuple[float, float, float]]]:
    """Parse the esmini ``--csv_logger`` wide-format schema.

    Layout: col 1 = TimeStamp; per entity ``#<i>``: ``Entity_Name``, ``World_Position_X``,
    ``World_Position_Y``. The second body line is the units row and is skipped. Rows are
    emitted in file order per actor and then time-sorted.
    """
    by_actor: dict[str, list[tuple[float, float, float]]] = {}
    # Header cells look like "Index [-]", "TimeStamp [s]", "#1 Entity_Name [-]",
    # "#1 World_Position_X [m]", "#2 Entity_Name [-]", ... Normalize each to
    # "<group> <field>" (group "" for the index/time columns).
    norm = [_norm_esmini_header_cell(h) for h in header]
    time_idx = next(
        (i for i, h in enumerate(norm) if h.lower().startswith("timestamp")), 1
    )

    # One (name, x, y) column triple per entity group, keyed by that group's prefix.
    entity_cols: list[tuple[int, int, int]] = []
    for i, h in enumerate(norm):
        parts = h.split(None, 1)
        if len(parts) != 2 or not parts[1].lower().startswith("entity_name"):
            continue
        group = parts[0]
        x_col = _group_field_col(norm, group, "World_Position_X")
        y_col = _group_field_col(norm, group, "World_Position_Y")
        if x_col is not None and y_col is not None:
            entity_cols.append((i, x_col, y_col))
    if not entity_cols:
        return {}
    max_col = max(time_idx, *(max(c) for c in entity_cols))

    for row in csv.reader(body):
        # esmini can emit a trailing partial row on close; skip malformed/short rows.
        if len(row) <= max_col:
            continue
        t_raw = row[time_idx].strip()
        if not t_raw:
            continue
        try:
            t = float(t_raw)
        except ValueError:
            continue
        for name_col, x_col, y_col in entity_cols:
            entity = row[name_col].strip()
            if not entity:
                continue
            try:
                x = float(row[x_col])
                y = float(row[y_col])
            except ValueError:
                continue
            by_actor.setdefault(entity, []).append((t, x, y))

    for frames in by_actor.values():
        frames.sort(key=lambda f: (f[0], f[1], f[2]))
    return by_actor


def _norm_esmini_header_cell(cell: str) -> str:
    """``#1 World_Position_X [m]`` -> ``1 World_Position_X`` (units dropped)."""
    text = cell.strip().lstrip("#").strip()
    if text.endswith("]") and " [" in text:
        text = text.rsplit(" [", 1)[0].strip()
    return text


def _group_field_col(norm_header: list[str], group: str, field: str) -> int | None:
    """Column index of ``<group> <field>`` in the normalized esmini header, else None."""
    target = f"{group} {field}".lower()
    for i, h in enumerate(norm_header):
        if h.lower() == target:
            return i
    return None


def _pair_gaps(
    a_frames: list[tuple[float, float, float]],
    b_frames: list[tuple[float, float, float]],
) -> tuple[list[tuple[float, float]], float | None, _ConflictFrame | None]:
    """Aligned gap series between two actors plus min-TTC frame info.

    Aligns by A's frames, finding B's nearest frame in bucketed time. Tracks the
    minimum instantaneous TTC (gap / positive closing speed) and the frame's positions.

    Returns:
        ``(gap_series, min_ttc, min_ttc_frame)`` where ``gap_series`` is a list of
        ``(t, gap)`` and ``min_ttc_frame`` is ``(t, ax, ay, bx, by)`` at the min-TTC
        frame, or ``None`` if no closing (hence no finite TTC) was observed.
    """
    b_buckets = {_bucket(f[0]): f for f in b_frames}
    b_sorted = sorted(b_frames, key=lambda f: f[0])
    gap_series: list[tuple[float, float]] = []
    min_ttc: float | None = None
    min_ttc_frame: _ConflictFrame | None = None
    prev_gap: float | None = None
    prev_t: float | None = None
    for t, ax, ay in a_frames:
        b_frame = _nearest(b_sorted, b_buckets, t)
        if b_frame is None:
            continue
        bx, by = b_frame[1], b_frame[2]
        gap = math.hypot(ax - bx, ay - by)
        gap_series.append((t, gap))
        if prev_gap is not None and prev_t is not None and t > prev_t:
            dt = t - prev_t
            closing = (prev_gap - gap) / dt if dt > 0 else 0.0
            if closing > 1e-9:
                ttc_inst = gap / closing
                if min_ttc is None or ttc_inst < min_ttc:
                    min_ttc = ttc_inst
                    min_ttc_frame = (t, ax, ay, bx, by)
        prev_gap, prev_t = gap, t
    return gap_series, min_ttc, min_ttc_frame


def _nearest(
    b_sorted: list[tuple[float, float, float]],
    b_buckets: dict[int, tuple[float, float, float]],
    t: float,
) -> tuple[float, float, float] | None:
    """Nearest B frame to time ``t`` using bucketed lookup, then linear fallback."""
    bucket = b_buckets.get(_bucket(t))
    if bucket is not None:
        return bucket
    if not b_sorted:
        return None
    return min(b_sorted, key=lambda f: abs(f[0] - t))


def _pet(
    a_frames: list[tuple[float, float, float]],
    b_frames: list[tuple[float, float, float]],
    min_ttc_frame: _ConflictFrame | None,
    conflict_radius_m: float,
) -> float:
    """PET: |t_A - t_B| at the conflict point (midpoint at the min-TTC frame).

    Returns ``-1.0`` if the conflict point is unknown or either actor never enters the
    conflict radius.
    """
    if min_ttc_frame is None:
        return -1.0
    _t, ax, ay, bx, by = min_ttc_frame
    cx, cy = (ax + bx) / 2.0, (ay + by) / 2.0
    t_a = _first_entry(a_frames, cx, cy, conflict_radius_m)
    t_b = _first_entry(b_frames, cx, cy, conflict_radius_m)
    if t_a is None or t_b is None:
        return -1.0
    return abs(t_a - t_b)


def _first_entry(
    frames: list[tuple[float, float, float]], cx: float, cy: float, radius_m: float
) -> float | None:
    """First timestamp at which the actor is within ``radius_m`` of the point (linear scan)."""
    for t, x, y in frames:
        if math.hypot(x - cx, y - cy) <= radius_m:
            return t
    return None


def _completion_metric(run_record: RunRecord, rulebook: dict[str, Any]) -> Metric:
    """Completion metric: 1.0 if ``sim_time_s`` met the planned duration, else 0.0."""
    fraction = float(
        rulebook.get("constants", {}).get("completion_time_fraction", _COMPLETION_FRACTION)
    )
    sim_time = run_record.sim_time_s if run_record.sim_time_s is not None else 0.0
    target = fraction * run_record.config.max_time_s
    return Metric(
        name=MetricName.COMPLETION,
        value=1.0 if sim_time >= target else 0.0,
        unit=Unit.NONE,
        actor_pair=None,
    )


def _evaluate_objectives(
    scenario_ir: ScenarioIR | None,
    metrics: list[Metric],
    rulebook: dict[str, Any],
    has_state_data: bool,
) -> list[ObjectiveResult]:
    """Grade each IR objective stub against the rulebook threshold for its kind.

    Thresholds are matched by ``objective_kind`` (C8-Q1); a stub with no matching
    rulebook entry (e.g. ``custom``) fails with ``threshold_source="none"``.
    """
    if scenario_ir is None:
        return []
    thresholds = rulebook.get("thresholds", [])
    results: list[ObjectiveResult] = []
    for stub in scenario_ir.objectives:
        rule = next((r for r in thresholds if r["objective_kind"] == stub.kind), None)
        if rule is None:
            results.append(
                ObjectiveResult(
                    stub_id=stub.id,
                    objective_kind=str(stub.kind),
                    passed=False,
                    threshold_source=_THRESHOLD_NONE,
                    detail="no rulebook threshold for objective_kind",
                )
            )
            continue
        observed = _observed_value(str(stub.kind), metrics)
        if not has_state_data:
            passed, detail = False, _DETAIL_NO_STATE_DATA
        else:
            threshold = float(rule["value"])
            le = rule.get("comparator") == "<="
            passed = observed <= threshold if le else observed == threshold
            detail = f"observed={observed:g} threshold={threshold:g} ({rule['id']})"
        results.append(
            ObjectiveResult(
                stub_id=stub.id,
                objective_kind=str(stub.kind),
                passed=passed,
                threshold_source=rule["id"],
                detail=detail,
            )
        )
    return results


def _observed_value(kind: str, metrics: list[Metric]) -> float:
    """Aggregate observed value for a metric kind (min for ttc/pet, else 0/1 sentinels)."""
    if kind in (MetricName.TTC, MetricName.PET):
        values = [m.value for m in metrics if str(m.name) == kind]
        return float(min(values)) if values else math.inf
    if kind == MetricName.COLLISION:
        return 1.0 if any(m.name is MetricName.COLLISION for m in metrics) else 0.0
    if kind == MetricName.COMPLETION:
        comp = [m for m in metrics if m.name is MetricName.COMPLETION]
        return comp[0].value if comp else 0.0
    return math.inf


def _h8(model: BaseModel) -> str:
    """8-char hash token for the trace boundary (``<Kind:hash8>``)."""
    from scenariochef.contracts.common import semantic_hash

    return semantic_hash(model)[:8]