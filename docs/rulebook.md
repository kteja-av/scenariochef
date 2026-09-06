# C8 Evaluation Rulebook — v1 (Phase 1)

Deterministic scoring of IR objective stubs. C8 NEVER invents objectives (C8-Q1) or
thresholds; both come from the IR and this file. Version bumped on any threshold change.

## Metrics

| Metric | Definition (Phase-1, CSV states) | Unit |
| --- | --- | --- |
| ttc | TTC(t) = euclidean gap / closing speed, computed when closing speed > 0; reported value = minimum over the run | s |
| pet | PET = |t_A - t_B| at the conflict point (closest approach position); computed for every pair where TTC is reported | s |
| collision | any frame where euclidean gap < collision_threshold | bool (1/0) |
| min_dist | minimum euclidean gap between the pair over the run; reported-only (no threshold → never graded, never auto-fails) | m |
| completion | storyboard completion: simulation time reached >= completion_time_fraction * planned duration | bool (1/0) |

Pairing rule (C8-Q4): every TTC metric row for a pair is accompanied by a PET row for the
same pair. A TTC without its PET pair is a rulebook violation → evaluation error.

## Thresholds

| Objective kind | Comparator | Threshold | Rule id |
| --- | --- | --- | --- |
| ttc | minimum observed TTC <= | 3.0 | RB-TTC-01 |
| pet | minimum observed PET <= | 5.0 | RB-PET-01 |
| collision | == | 1 (any collision frame) | RB-COL-01 |
| completion | == | 1 (must complete) | RB-CMP-01 |

A custom stub with no rulebook entry → objective_result passed=False with
threshold_source="none" and detail "no rulebook entry for custom objective" (visible,
never silently passed).

## Data source

CSV states (C8-Q5): rows of per-timestamp actor states; columns must include at minimum
`t`, `actor`, `x`, `y`. OSI absent → CSV is authoritative. Missing CSV → metrics list is
empty and every objective fails with detail "no state data" (fail-visible, not crash).

## Conflict-point approximation (Phase 1)

PET conflict point = midpoint of the positions at the minimum-TTC frame for the pair.
Entry times = linear interpolation of when each actor first comes within
conflict_radius (0.5 m) of that point; if an actor never enters, PET = None and the pair
reports PET value -1.0 with detail "no conflict point entry" (visible absence).
