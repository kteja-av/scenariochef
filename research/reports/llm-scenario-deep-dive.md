# LLM scenario-generation deep dive — ChatScene, Txt2Sce, Chat2Scenario

Researched 2026-09-05 for ScenarioChef C2 (slot-filling LLM behind a JSON-schema gate,
OpenAI-compatible endpoint). Every claim below was checked against primary sources:
both papers' arXiv HTML full text, and shallow clones of both public repos read
directly (`/tmp/chatscene_clone`, `/tmp/chat2sce_repo`). All URLs were re-verified
with `curl -sL` on 2026-09-05 (status codes in the Verification log at the end).
Where something could not be verified from source, it is explicitly marked
**UNVERIFIED**.

## Correction to the task brief

- **Txt2Sce is not Tsinghua.** arXiv:2509.02150 is from Nanjing University (State Key
  Laboratory for Novel Software Technology; Pin Ji, Yang Feng, et al.).
  No Tsinghua group publishes a system under that name; arXiv full-text search for
  `"Txt2Sce"` returns exactly one paper. This report covers the real Txt2Sce.
- **Chat2Scenario is TU Graz** (Institute of Automotive Engineering; Yongqi Zhao,
  Wenbo Xiao, et al., IEEE IV 2024), arXiv:2404.16147, **with public code** —
  cloned and read for this report. It is dataset-trajectory→scenario, not chat→video;
  the closest verified "video/chat → scenario" analog. As a supplementary "chat →
  scenario" reference, Text2Scenario (arXiv:2503.02911, Beijing Jiaotong / Beihang
  authors — affiliation from arXiv metadata **UNVERIFIED**) does LLM+DSL-corpus
  text→scenario; its project page exists (see log) but full text was not read for
  this report.

## C2 today (baseline for the mapping)

From `src/scenariochef/c2_understanding/runtime.py` and
`src/scenariochef/contracts/intent_spec.py` (read, not modified):

- Input: `RequestSpec` (raw text + user `params`; `USER_EXPLICIT_KEYS =
  ("speed","ego_speed","lane","target_lane","gap","headway")`) plus optional
  `EvidenceBundle` (C3 definitions/constraints with `fact_or_assumption`).
- `build_prompt()` emits a one-shot template: shape sketch, raw text, `[USER-EXPLICIT]`
  param lines, evidence ids/claims, "Never invent facts" instruction. No few-shot
  examples, no retrieval.
- Proposers: deterministic `null_proposer` (keyword→ActionType table) and
  `SpaceXAIProposer` (OpenAI-compatible, lazy import, `json.loads` with **no
  schema validation or retry** before `gate()`).
- `gate()` rebuilds a fixed ego+lead `IntentSpec` (Phase-1), passes through extra
  known-`ActionType` maneuvers, forces user-explicit values (`SlotProvenance`
  source `user_explicit` / `llm_proposed` / `c3_default`), records
  `unknowns` (incl. user-vs-LLM conflicts) and `confidence`, and validates via the
  frozen pydantic model (`extra="forbid"`).
- Downstream: C4 compiles IR → C5 scenariogeneration → C6 validation → C7 esmini →
  C8 evaluation → C9 feedback.

---

# 1. ChatScene (CVPR 2024; UIUC)

- Paper: arXiv:2405.14062 (Zhang, Xu, Li) — verified.
- Code: https://github.com/javyduck/ChatScene — MIT license, shallow-cloned (394 MB,
  includes vendored Safebench + Scenic forks). The LLM pipeline lives in
  `retrieve/` (`retrieve.py`, `utils.py`, `architecture.py`, `prompts/*.txt`,
  `database_v1.pkl`) — ~220 lines of Python total.

## Pipeline (verified in code)

1. **Decompose (one LLM call).** `prompts/extraction.txt` is a 6-example few-shot
   prompt that forces the free-text scenario into **exactly four labeled fields**
   via a regex-checked format:
   `Adversarial Object: (enum: Car|Pedestrian|Bicycle|Motorcycle)` / `Behavior:` /
   `Geometry:` (road layout incl. signal state) / `Spawn Position:` (relative to ego,
   incl. occluders). `retrieve.py` parses the reply with
   `re.search(r"Adversarial Object:(.*?)Behavior:(.*?)Geometry:(.*?)Spawn Position:(.*)", ..., re.DOTALL)`.
2. **Retrieve (three independent k-NN searches).** `database_v1.pkl` stores, per axis
   (`behavior`/`geometry`/`spawn`), parallel lists of natural-language descriptions and
   **human-written Scenic 2.1 code snippets** (behavior functions, ego geometry,
   spawn logic). Embeddings via `sentence-t5-large`; top-3 cosine retrieval per axis.
3. **Snippitize (per axis).** `utils.generate_code_snippet()` composes a per-axis
   prompt (`behavior.txt` / `geometry.txt` / `spawn.txt`) containing the top-k
   description↔snippet pairs plus the new sub-description, with hard syntax
   constraints (behavior fn must be named `AdvBehavior`; tunables must be
   `param OPT_xxx` read via `globalParameters.OPT_xxx`; blockers restricted to a
   fixed enum of 11 CARLA props). Crucially: `--use_llm` off ⇒ **pure retrieval**
   (return top snippet verbatim); on ⇒ LLM only adapts/extends retrieved snippets.
   Output is fenced-code extracted by regex `` r"```scenic(.*?)```" ``.
4. **Assemble.** Deterministic string concatenation: docstring of the original
   scenario + map param + a fixed Scenic header (map/ego model) + behavior +
   geometry + spawn snippets. Formatting choices (map, Town, ego model) are
   template constants, not LLM decisions.
5. **Validate (compile-only).** `ScenicSimulator(file_path, ...)` is instantiated
   purely to check compilability. Failures do **not** go back to the LLM: the file is
   renamed `.txt` ("quarantined"), the failure logged, and the pipeline moves on.
   A `TODO: use llm for fixing the error` comment shows LLM repair was planned but
   not shipped.
6. **Simulate & mine hard scenes.** Scenic executes in CARLA; `train_scenario` mode
   samples 50 scenes/behavior, optimizes parameter ranges (`OPT_xxx` globals) every
   10 steps by collision statistics, and keeps the 2 most challenging scenes
   (README, verified). Output artifacts: `.scenic` files + a CSV log row per
   scenario (sub-descriptions, snippets, success flag).

## Key properties

| Dimension | What ChatScene does |
| --- | --- |
| Input | free text, one scenario per line |
| NL structure | forced 4-field fixed-vocabulary extraction (one enum + 3 free-text fields), regex-checked |
| Output | Scenic 2.1 code (not XML), assembled from retrieved snippets |
| Validation | regex on extraction; code-extraction regex; compile check; quarantine on failure; no LLM repair |
| Simulator | CARLA 0.9.13 via Scenic/Safebench |

## Adoptable mechanics for C2

1. **Fixed-field decomposition prompt with enum-constrained fields and a
   machine-checkable format** (`prompts/extraction.txt`).
   *Map to C2:* make `build_prompt()` request the JSON shape with enumerated fields
   constrained to `ActionType` / `TriggerKind` / `ActorRole` / `ObjectiveKind` values
   (the enums already in `contracts/intent_spec.py`). The gate already rejects unknown
   actions; publishing the enum values in the prompt raises first-pass validity.
   ChatScene pairs the free-text fields with one hard enum (adversary type) — C2's
   analogue is pinning `action` and `trigger.kind` to the enum lists in the prompt
   while leaving `params` free.
2. **Description↔snippet corpus as few-shot examples, retrieved per axis**
   (`database_v1.pkl` + `retrieve_topk`). *Map to C2:* `assets/scenario_db/`
   (69 esmini demos mirrored, per `research/reports/competitor-comparison.md`) plus
   accumulated (raw-request → accepted IntentSpec) pairs form a retrieval corpus;
   C3's static knowledge lane injects the top-k pairs into `build_prompt()` so the
   LLM sees real, gate-passing slot patterns for similar requests. This is the
   single highest-value mechanic for C2.
3. **"If a retrieved example already matches, reuse it verbatim"** (all three
   snippet prompts contain this instruction, and `--use_llm` off is pure retrieval).
   *Map to C2:* prompt clause + cheap deterministic pre-check: if the top-1 retrieved
   IntentSpec matches the request above a similarity threshold and passes the gate,
   short-circuit the LLM call (deterministic path; the gate cannot tell the
   difference because provenance is recorded per slot either way).
4. **Hyperparameters as named, mutable knobs.** `param OPT_xxx` /
   `globalParameters.OPT_xxx` lets ChatScene sweep and optimize values without
   re-generating code. *Map to C2/C9:* keep numeric slots in `IntentSpec` named and
   unit-tagged (they already are via `ConstraintIntent`/params) so C9 explore mutates
   slot values rather than re-prompting; C5's parameter expansion stays
   downstream of a stable slot schema.
5. **Fail-cheap quarantine instead of silent retry.** On any failure, keep the raw
   output in a quarantine artifact with the failure reason. *Map to C2:* when
   `json.loads` or `gate()` raises, persist `(prompt, raw_text, exception)` via
   C10 logging before any retry, so schema-gate failures are observable rather than
   invisible retries.

---

# 2. Txt2Sce (Nanjing University; arXiv:2509.02150, Sep 2025)

- Paper: "Txt2Sce: Scenario Generation for Autonomous Driving System Testing Based
  on Textual Reports" — verified from arXiv HTML full text.
- Code: referenced as "our public repository" for prompts/parameter tables, but no
  URL appears in the arXiv HTML (**UNVERIFIED / not found**; treat as unavailable).

## Pipeline (from full text)

1. **Element collection (graph DBs, no LLM).** (a) An *entity database* scraped from
   the OpenSCENARIO UML/XSD documentation: nodes `XSDElement`/`XSDAttribute`, edges
   containment/inheritance/has-attribute, encoding "relationships among scenario
   elements, attribute types, and **valid value ranges**" — a schema-level reference.
   (b) A *map database* parsed from OpenDRIVE files: road-segment nodes with
   lane metadata (ids, types, directions, lane-change permissions) and directed
   topology edges annotated with junction/connecting-road/lane-transition info.
2. **Text report → structured sub-scenario (LLM: DeepSeek `deepseek-chat`).**
   Input: California DMV AV accident-report narratives (180 filtered reports → 33
   representative seeds). Multi-turn, dialogue-style prompt progressively extracts,
   per NPC and obstacle: quantity, type, location, behavior. Two deterministic-ish
   scaffolds make the output structured:
   - **Behaviors are compiled to ordered event sequences over 13 fine-grained
     enumerated actions** (turns, accelerate, decelerate, …) — "this standardization
     improves output consistency and ensures logical continuity".
   - **Positions are normalized to seven enumerated relative-position classes
     R1–R7 w.r.t. the AV** (e.g., same-lane front, opposite oncoming lane …),
     decoupling behavior from road layout so the same description reuses across
     junction types.
3. **Position alignment & road matching (deterministic).** Query the map DB with the
   extracted constraints (lane counts, turn connectivity, R1–R7) to filter road
   segments; pick one; assign initial lanes by **rule**: leftmost by default, with
   spelled-out overrides derived from the first lane-constrained action in the NPC's
   event sequence (e.g., sequence `afd` must start further right to allow a later
   left lane change). No LLM in this stage.
4. **Seed OpenSCENARIO generation (hybrid template + LLM).** A template skeleton is
   built deterministically from the selected map (RoadNetwork, signals, computed
   entity positions) "with semantic slots reserved"; then the LLM fills only the
   semantic-level slots (object defs, initial speeds, speed changes, trajectories,
   event sequences) producing **XML fragments inserted into the template**.
5. **Scenario block mutation (deterministic, no LLM).** Disassemble the seed into
   typed XML blocks (weather, traffic signal, obstacles, NPC defs, individual events);
   mutate with four operator families — Dynamics (target speed, TransitionDynamics,
   maxAccel/Decel/Speed), Trajectory (waypoint lateral offsets), Physical (dimension,
   NPC category), Environment (weather+friction, signal states, obstacle insertion) —
   with three value strategies: uniform random in range, Gaussian noise, and
   context-aware computation from map topology.
6. **Assembly + testing.** Re-insert blocks in fixed order (weather → NPCs → signals
   → events → obstacles) into a hierarchical derivation tree; run in CARLA +
   scenario_runner as the OpenSCENARIO engine against **Autoware**; oracles: collision,
   jerk (±300 m/s³ threshold), yaw-rate intervals. Result: 33 seeds → 4,373 valid
   files; all 33 seeds executed; 93.9% judged semantically faithful to the report.

## Key properties

| Dimension | What Txt2Sce does |
| --- | --- |
| Input | accident-report narratives (multi-sentence, implicit facts) |
| NL structure | multi-turn extraction → NPC/obstacle slots (qty, type, R1–R7 position, 13-action event sequence) |
| Output | standards-compliant OpenSCENARIO XML; template + LLM-filled semantic slots |
| Validation | schema-derived graph DB constrains generation; LLM extraction manually audited (accuracy table per slot type: NPC type 97.6%, quantity 96.9%, position 87.8%, events 90.2%); all seeds execute in CARLA |
| Simulator | CARLA + scenario_runner (OSC 1.x engine); tests Autoware |

## Adoptable mechanics for C2

1. **Template-with-reserved-slots generation: the LLM fills semantic slots, the
   skeleton is deterministic.** *Map to C2:* this is exactly C2's contract taken
   further — the gate should treat the LLM reply as slot values only and never as
   structure: already true (`gate()` rebuilds actors/maneuvers), but the *prompt*
   should say so explicitly ("fill the given shape; fields may be omitted, never
   restructured") so the JSON gate sees uniform shapes.
2. **Extract to enumerated vocabularies, not free text, at the NL boundary**
   (13-action behavior alphabet; 7 relative positions). *Map to C2:* extend the
   prompt's shape sketch with enumerated vocabularies for position and behavior —
   e.g., position ∈ {same_lane_front, same_lane_behind, left_adjacent, right_adjacent,
   oncoming, cross_path} and maneuver sequences as ordered lists of `ActionType`.
   The deterministic lane-assignment rules then live in `gate()`/C4, not in the LLM
   (mirroring Txt2Sce's step 3, which computes lanes from the event sequence with
   if/else rules — directly portable into `gate()` for the lead actor's lane).
3. **Schema-derived range knowledge as gate checks.** Txt2Sce's entity DB encodes
   "valid value ranges" from the OpenSCENARIO spec and uses them to reject/repair.
   *Map to C2/C6:* after the JSON gate, run cheap range checks on LLM-proposed numeric
   slots (speeds, gaps, lane ids vs. the map DB C3/C5 already know) and on failure
   demote the slot to `unknowns` instead of aborting — a deterministic repair path
   that needs no LLM.
4. **Per-slot extraction-accuracy auditing.** They measured LLM accuracy *per slot
   type* (positions and event sequences are the weak slots at 87.8/90.2%). *Map to
   C2/C10:* log per-slot provenance + post-hoc hit rate (does C7/C8 agree the slot
   did what the user asked?) so weak slots are identified empirically; this refines
   where `confidence` should be discounted and where few-shot examples help most.
5. **Default-then-complete: unspecified slots get safe defaults rather than LLM
   guesses.** "Default values are assigned to parameters not explicitly specified in
   the accident reports to ensure scenario completeness." *Map to C2:* C2 already has
   `DEFAULT_SPEED/LANE/GAP`; make the prompt instruct the model to **omit** unknown
   slots (or emit them into `unknowns`) instead of inventing values, letting the
   deterministic defaults apply — this keeps the user-explicit precedence rules
   (C2-Q3) clean and shrinks hallucinated numbers.

---

# 3. Chat2Scenario (TU Graz; IEEE IV 2024; arXiv:2404.16147)

- Paper: verified from arXiv HTML full text. Code:
  https://github.com/ftgTUGraz/Chat2Scenario — Python, cloned (166 MB incl. a
  bundled Windows venv; real code in `NLP/`, `scenario_mining/`, `utils/`, `GUI/`).

## Pipeline (verified in code + paper)

Direction: the inverse of C2 — it turns **dataset trajectories (highD) + one natural-
language description** into replayed scenarios. Stages:

1. **Scenario classification model (fixed vocabulary).** A closed taxonomy defines
   everything the LLM may say: ego/target longitudinal activity ∈ {keep velocity,
   acceleration, deceleration}; lateral ∈ {follow lane, lane change left, lane change
   right}; target position ∈ {same lane: front/behind; adjacent lane: left/right;
   lane next to adjacent lane: left/right}. Defined as a plain Python dict in
   `NLP/Scenario_Description_Understand.py` (`classification_framework`) and dumped
   into the prompt via `json.dumps(...)`.
2. **LLM classification call.** One prompt that (a) assigns the LLM a role, (b) shows
   the framework JSON, (c) the user description, (d) the exact expected response
   structure with `#1`/`#2` numbering for multiple targets, (e) a fully worked
   example, (f) a closing reinforcement instruction (five segments; the paper cites
   OpenAI's prompt-engineering guide). `temperature=0`, and `base_url` is a config
   parameter (an OpenAI-compatible endpoint — same integration shape as C2's
   planned LLM). The reply is parsed with `extract_json_from_response` (find the
   first `{`, JSON-decode; permissive, no schema library).
3. **Deterministic scenario search.** The parsed labels are matched against the
   dataset with closed-form rules (their Eq. 1–3): longitudinal class from
   acceleration thresholds, lateral from Δlane-id + direction, relative position
   from ‖Δlane‖ and Δx. This is a filter over mined trajectory segments — no LLM.
4. **Criticality filter.** Threshold-based metrics (TTC / THW / DRAC etc.; a
   `metric_threshold` like "1 - 3" in `config/config.json`) select the critical
   instances.
5. **Simulatable output.** `utils/helper_scenario_function.py` builds ASAM
   OpenSCENARIO **programmatically with the `scenariogeneration` (pyoscx) package**
   — the same library C5 uses: catalog + RoadNetwork(.xodr) + Entities + Init
   (TeleportAction to WorldPosition) + StoryBoard with a SimulationTimeCondition
   stop trigger + per-timestamp Vertex/WorldPosition trajectory events from the
   dataset. IPG CarMaker text format as the second output. The files are stated
   (paper) to run in esmini; esmini is the compatibility target of scenariogeneration.

## Key properties

| Dimension | What Chat2Scenario does |
| --- | --- |
| Input | naturalistic driving trajectories (highD CSV) + NL scenario description |
| NL structure | LLM forced into a **fixed classification JSON** derived from a closed taxonomy dict (temperature 0, worked example, `#n` target numbering) |
| Output | OpenSCENARIO 1.2 XML (via scenariogeneration) + CarMaker CSV; trajectory replay |
| Validation | strict-format prompt + JSON extraction; deterministic label→trajectory matching; criticality thresholds; quantitative precision/recall vs. hand labels (cut-in F1 0.889, cut-out 0.919, following 0.857) |
| Simulator | esmini (via scenariogeneration) and IPG CarMaker |

## Adoptable mechanics for C2

1. **Taxonomy-dict-as-prompt: generate the schema section of the prompt from a
   Python enum/dict, and give one fully worked example.** Their prompt embeds the
   exact `classification_framework` JSON and one input→output example; response
   format is spelled field-for-field. *Map to C2:* derive the shape sketch in
   `build_prompt()` from the pydantic contracts (JSON-schema of `IntentSpec`-eligible
   fields, enums included) rather than the current hand-written one-line shape, and
   add one gold input→JSON example (e.g., the cut-in example from `tests/test_c2.py`).
   Schema-gate pass rate improves without weakening the gate.
2. **Closed-vocabulary slots with deterministic decoding rules.** Every LLM-emitted
   label is one of a fixed set, and the mapping label→executable parameters is a
   deterministic function (their Eq. 1–3). *Map to C2:* LLM slot vocab stays
   closed (`ActionType`, `TriggerKind`, position classes); the LLM never emits
   coordinates — `gate()` computes `road_id/lane_id/s_m` from position class + map
   knowledge (C3), exactly as Chat2Scenario never lets the LLM touch trajectories.
   This is the cleanest fit with the deterministic schema gate.
3. **Per-target numbering convention for multi-actor output** (`Target Vehicle #1`,
   `#2`, …). *Map to C2:* the JSON shape should specify actors as an **array with
   stable `name` keys referenced by maneuvers** (`{"actor": name}`) — C2's shape
   already implies this, but the prompt should state the invariant "every maneuver
   actor must be a declared actor name" so `gate()`'s actor-membership check rarely
   fires; violations go to `unknowns`, not crash.
4. **Threshold-based criticality as an acceptance filter downstream of structure.**
   Structure first (classification), then a numeric criticality window
   (TTC 1–3 s) selects what is worth keeping. *Map to C2/C8:* treat `confidence` and
   C8 metrics (TTC/headway already in the rulebook) as the acceptance gate for
   whether an LLM-proposed scenario enters the regression corpus — structure is the
   LLM's job, interestingness is measured, not asserted.
5. **Endpoint-configurable OpenAI-compatible client with graceful failure modes.**
   Their client takes `base_url` from config and returns `None` per error class
   (auth/rate-limit/bad-request) instead of raising through the pipeline.
   *Map to C2:* `SpaceXAIProposer` should accept `base_url`/model from config
   (env), map API error classes to distinct `unknowns`/retry policies, and let
   `run_c2` fall back to `null_proposer` on transport errors — keeping C2's
   offline-safe guarantee.

---

# Cross-system takeaways for C2 (ranked)

All three systems converge on the same shape, which is ideal for a deterministic
schema gate: **the LLM only ever emits values from small closed vocabularies into a
fixed structure; everything else (layout, lanes, geometry, XML) is deterministic.**

| # | Mechanic (source) | C2 component |
| --- | --- | --- |
| 1 | Few-shot retrieval of (request → gated IntentSpec) pairs from a scenario corpus, "reuse top match verbatim if it fits" (ChatScene) | `build_prompt()` + C3 retrieval lane over `assets/scenario_db/` |
| 2 | Prompt schema generated from the pydantic contracts incl. enum vocab + one gold example (Chat2Scenario) | `build_prompt()` |
| 3 | LLM emits position classes / behavior vocab; `gate()` deterministically computes lanes & geometry; omitted slots fall back to C2 defaults (Txt2Sce, Chat2Scenario) | `gate()` slot decoding + prompt "omit, don't invent" rule |
| 4 | Schema/range checks with slot demotion to `unknowns`, per-failure quarantine artifacts (Txt2Sce, ChatScene) | `gate()` + C10 logging around `SpaceXAIProposer.__call__` |
| 5 | Deterministic keyword/pattern fast path before the LLM (ChatScene's `--use_llm off` = pure retrieval) | `run_c2()` proposer selection |
| 6 | Per-slot provenance + empirical per-slot accuracy tracking; numeric acceptance via C8 criticality metrics (Txt2Sce, Chat2Scenario) | `SlotProvenance` + C10 store + C8 rulebook |

Reinforced but already-adopted in ScenarioChef: `scenariogeneration`-based XML
compilation (both Txt2Sce and Chat2Scenario build OpenSCENARIO through templated or
programmatic structure, never raw LLM XML), explicit stop triggers, and catalogs.

# Verification log (`curl -sL`, 2026-09-05)

| URL | Status |
| --- | --- |
| https://arxiv.org/abs/2405.14062 | 200 |
| https://arxiv.org/html/2405.14062v1 | 200 |
| https://github.com/javyduck/ChatScene | 200 (cloned, MIT) |
| https://arxiv.org/abs/2509.02150 | 200 |
| https://arxiv.org/html/2509.02150v1 | 200 |
| https://arxiv.org/abs/2404.16147 | 200 |
| https://arxiv.org/html/2404.16147v1 | 200 |
| https://github.com/ftgTUGraz/Chat2Scenario | 200 (cloned, IEEE IV 2024) |
| https://github.com/pyoscx/scenariogeneration | 200 |
| https://javyduck.github.io/chatscene | 200 |
| https://caixxuan.github.io/Text2Scenario.GitHub.io | 200 (Text2Scenario project page; full text **not read**) |
| https://platform.openai.com/docs/guides/prompt-engineering | 200 (cited by Chat2Scenario) |

Additional arXiv API verification: full-text search `all:"Txt2Sce"` → 1 result
(2509.02150); `all:"Chat2Scenario"` → 1 result (2404.16147);
`abs:"Txt2Sce" OR ti:"text-to-scenario"` → also surfaced Text2Scenario (2503.02911).

## Unverified / not found

- Txt2Sce public code repository: paper says "prompts and implementation details are
  provided in our public repository" but no URL appears in the arXiv HTML; searches
  did not find it. **Treat Txt2Sce mechanics as paper-level claims only.**
- Text2Scenario (arXiv:2503.02911) author affiliations and DSL-corpus internals:
  only abstract-level verified; details **not verified** (full text not read).
- ChatScene GPT-4o "database v2" (README roadmap): marked beta/in-progress upstream;
  database_v1.pkl was inspected, v2 does not exist in the repo.
- ChatScene paper numbers (15% collision-rate increase, 9% reduction after
  fine-tuning): taken from the verified arXiv abstract; not independently reproduced.
