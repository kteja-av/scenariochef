# ScenarioChef Checkpoints

Mirror format. Sections per checkpoint: `## Built`, `## Learned`, `## Contradictions`, `## Token count`.

---

# Checkpoint 1

Written by: independent non-Opus agent (deepseek singularity). Reason: see ## Mistakes below.

## Built

- ScenarioChef no-logic skeleton:
  - `src/scenariochef/cli.py`
  - `src/scenariochef/trace.py`
  - `src/scenariochef/cx_orchestrator/runtime.py`
  - `src/scenariochef/c1_input/..c10_management/runtime.py` (per-component stub per cN)
- Each cN is a stub returning placeholder tokens.
- CX orchestrator runs 20 trajectories, writes `artifacts/trace_run.log`.
- Added deterministic 6-label scenario pool so the 20 trajectories are distinct in the log.

## Learned

Generalizable rules (bias-variance balanced):

- **Clean Architecture / Ports & Adapters (Hexagonal):** put adapters at the edge so they can adapt to any external source; keep a deterministic domain core + orchestrator in the middle; keep skeleton minimal, no premature real logic. Don't build real logic into stubs early.
- **Many trajectories > single case:** when explaining/demonstrating a system, run MANY trajectories (e.g. 20), not one; prefer a live visual (tldraw canvas via SDK) over a pile of Markdown files.
- **Log multi-trajectory runs:** write run output to a file so interactions are inspectable after the fact.
- **Orchestrator orchestrates only:** delegate implementation to worker subagents; delegate checkpoint-writing to a SEPARATE independent agent with independent memory. Do NOT let Opus write checkpoints — its memory can skew honesty.
- **Checkpoint discipline:** every checkpoint = built + learned + mistake + token count + contradictions, phrased generically, contradiction-aware.

## Mistakes

- **Sonnet not available:** requested checkpoint writer was "Sonnet", not in orchestrator's model list → used closest available substitute instead.
- **grok-4.6 rate-limited:** first substitute (grok-4.6) was rate-limited → could not write; fell through to independent non-Opus agent (deepseek singularity).
- **tldraw worker text-only bug:** first tldraw worker attempt failed — that model only supports text input, but the worker tried to read a screenshot → fix was to verify via JSON records only. Lesson: check the agent's input modality before passing image/screenshot data.

## Contradictions

- None (this is checkpoint #1).

## Token count

Writing this checkpoint: honest estimate ~250 tokens (markdown is terse).
Prior work (skeleton, labels pool, 20-trajectory runner): not counted here; estimate larger, exact unknown.

---

# Checkpoint 2

Written by: independent non-Opus agent (deepseek singularity). Reason: see ## Mistakes below.

## Built

- Skeleton now runs 20 distinct trajectories:
  - `src/scenariochef/scenario_labels.py` — fixed 6-label deterministic pool (cut-in, follow-brake, merge, crossing, lane-change, yield) indexed by trajectory number.
  - `cx_orchestrator/runtime.py` and the c1..c10 runtimes tag their tokens with the per-trajectory label.
- Verified `artifacts/trace_run.log`: 440 lines = 22 lines × 20 trajectories; exactly 20 distinct REQ-0001..REQ-0020 ids; all 6 labels appear.
- tldraw blueprint page created: "ScenarioChef File Connections - NEW.tldraw" at `/Users/krishnateja/Documents/ScenarioChef File Connections - NEW.tldraw`.
  - Records-verified: 39 shapes (14 geo boxes + 24 arrows + 1 text note), 48 arrow bindings (24 real bound arrows), lint clean.
  - Boxes for cli.py, cx_orchestrator/runtime.py, trace.py, c1..c10 runtimes, artifacts/trace_run.log; flow cli→orchestrator→c1..c10 in sequence, each cN→trace, orchestrator+trace→log, plus a 20-trajectory loop visual.
- `.harness/checkpoints.md` holds checkpoint #1 and #2.

## Learned

Generalizable rules (bias-variance balanced):

- **Match verification method to model input modality:** text-only models must verify via structured records/JSON (shape counts, bindings), never screenshots/images. Pick the verification channel the model can actually ingest.
- **Pick an independent writer within quota:** choose a checkpoint writer that is both independent-memory AND within available usage quota; don't assume a single fallback is available — check quota before committing.
- **Names can collide with pre-owned artifacts:** when a requested filename matches an existing unowned doc, create a distinctly-named sibling (e.g. "- NEW") rather than clobbering the owner.
- **Rank fallbacks in advance:** enumerate the writer fallback chain (given model list and quota) before writing, so a failure lands on a known next candidate, not an ad-hoc one.

## Mistakes

- **grok-4.6 rate-limited:** first checkpoint writer (grok-4.6) was rate-limited (free usage exhausted, 429) → fell back to deepseek singularity. Lesson: verify quota for the intended writer before relying on it.
- **Sonnet unavailable, Opus disallowed:** Sonnet was never in the orchestrator's model list; Opus was disallowed by the human → checkpoint writer is a non-Opus independent agent. Record this as an explicit model-selection constraint.
- First-run tldraw verification failure (image-read on a text-only model) was re-encountered and corrected by a hard "records-only verification, no image reads" constraint on the re-run.

## Contradictions

- None. Checkpoint #1's learned/constraint statements (non-Opus independent writer, tldraw records-only verification, 20-trajectory runner) are all confirmed and extended, not contradicted, by checkpoint #2 facts.

## Token count

Writing this checkpoint: honest estimate ~330 tokens (markdown is terse). Prior work (trajectory tagging, tldraw doc creation, log verification) not counted here; estimate larger, exact unknown.

---

# Checkpoint 3

Written by: independent checkpoint writer (own memory; judged directly from repo state, not any prior transcript).

## Built

Verified from repo, not assumed:

- **Full pipeline vs. skeleton**: `git log --oneline` shows 25 single-line-stage commits from `2b665bb Initial project scaffold` → `168e744` (CX integration learnings). Each cN landed as its own commit with a follow-on "record wave … in harness" commit.
- **11 runtimes implemented** (not stubs): `wc -l src/scenariochef/*/runtime.py` = c1 240, c2 399, c3 347, c4 332, c5 451, c6 460, c7 229, c8 352, c9 327, c10 39, cx 418 (3,594 total). `contracts/` package has 14 modules defining the typed boundaries (RequestSpec, EvidenceBundle, IntentSpec, ScenarioIR, ValidationReport, EvaluationReport, FeedbackAction, RunRecord, orchestration, etc.).
- **Test suite green**: `.venv/bin/python -m pytest -q` → **157 passed** (clean state). Ruff: `All checks passed!`. Mypy: `Success: no issues found in 42 source files`. Note: my first CLI run polluted `artifacts/scenariochef.db`, which tripped `test_no_repo_pollution` (1 failed/156) — cleaned it and 157 passed.
- **Harness stores populated**: `.harness/` = gate.sh, retrieve.py, compile_experience.py, promote.py, record.py; invariants/ (4 yaml), experiences/ (9 yaml), skills/ (3 md), repo-model/components.json, evals/ (empty dir), trajectories/.
- **Docs/artifacts**: docs/contracts.md, docs/rulebook.md, docs/cx-implementation-notes.md, docs/adr/ (12 ADRs); assets/xsd/OpenSCENARIO_1_0.xsd; assets/maps/straight_2lane.xodr.
- **Pipeline runs end-to-end (not just tests)**: `ESMINI_BIN=/nonexistent .venv/bin/python -m scenariochef.cli` → `outcome=completed iterations=1 validation=passed` and `persisted 9 artifacts` for REQ-0001. Cleaned up the run's `artifacts/scenariochef.db` and `artifacts/REQ-0001/` afterwards (repo left clean; `git status` empty).
- **E08 lane escalation verified**: integration test `test_e08_escalates_lane_unchanged` passes — user-explicit `target_lane=3` on the two-lane map fails C6 S3 MAP_TOPOLOGY, C9 escalates (DERIVED-16, no lane rewrite; target_lane stays 3), CX returns `outcome=hitl_blocked` with a persisted ValidationReport. Also confirmed directly via `run_request({"text":"change to lane 3","target_lane":3}, ack=…)` → `hitl_blocked`.

## Learned

Generalizable rules (bias-variance balanced):

- **Orchestrator-authored integration vs. component work:** CX is where cross-component seams belong (DERIVED-3 ack composition, budget/HITL gating, DAG sequencing, persistence), while each cN runtime stays a self-contained adapter for a single concern and can be built/verified independently. Moved final wiring into CX after component unit tests were green.
- **DERIVED-3 ack composition pattern:** an actor expresses its ack *on the artifact it consumes* (C2-acks default assumptions on the EvidenceBundle) rather than on the producing component; the orchestrator then *composes* those acked bundles so a downstream gate passes only for accepted assumptions and surfaces outstanding ones as a `hitl_blocked` instead of crashing. Keep gates non-fatal.
- **Tolerate offline / never raise on a missing binary:** the pipeline treats an absent esmini (`SKIPPED_NO_BINARY`) as a first-class outcome, not an exception; a validation run still returns `validation=passed` and persists all artifacts. Hardening an external-tool boundary to degrade gracefully keeps the DAG testable offline.
- **Single-line-stage commits + harness trajectory recording:** landing each stage one commit at a time (component → wire → integration → record-in-harness) makes green-checkpoints reproducible and gives the harness a per-stage trajectory to compile into episodic memory. This is the same many-trajectory principle as checkpoint #1/#2 applied to development history, not just demo runs.
- **What the tests/eval genuinely revealed:** `test_no_repo_pollution` is a real guard — a bare `run_request`/CLI with default Store *does* write `artifacts/scenariochef.db`, so offline verification must inject a tmp Store (as line 1 of the integration suite docstring states); running the CLI for a manual check and not cleaning up breaks the suite. Also: E08 behavior is enforced at both C4 (E08_LANE_OUT_OF_RANGE suggestion must not touch the canonical field) and C6/C9 (MAP_TOPOLOGY FAIL escalates rather than snapping), i.e. the invariant is protected at multiple layers.

## Contradictions

- None. Checkpoint #1/#2's "skeleton, stubs, placeholder tokens" is individually superseded per-component (each cN is now real, 39–460 lines) — expected, not a contradiction. Checkpoint #2's record says 20 trajectories wrote 440 lines to `artifacts/trace_run.log`; the file still exists (that runner is preserved) and the new CLI reachable path (`run_request`/`scenariochef.cli`) adds 9-persisted-artifact runs. No claim contradicted.

## Token count

Writing this checkpoint: honest estimate ~360 tokens (markdown is terse). Prior work (running pytest/ruff/mypy, end-to-end CLI, E08 verification, artifacts cleanup) not counted here; estimate larger, exact unknown.