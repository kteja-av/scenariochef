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