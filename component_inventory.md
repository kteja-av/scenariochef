# Component Inventory — ScenarioChef Phase 1

**Project:** ScenarioChef  
**Phase:** 1 — Automated OpenSCENARIO + esmini  
**Language:** Python 3.11+ (`src/scenariochef/`)  
**Architecture status:** Frozen (see [`docs/checkpoint.md`](docs/checkpoint.md), 2026-08-22)  
**ADR index:** [`docs/adr/README.md`](docs/adr/README.md)

---

## Overview

ScenarioChef decomposes automated scenario generation into **eleven capability components (C1–C10)** plus a **cross-cutting orchestrator (CX)**. Each component has a single primary responsibility, a defined nature (agent vs deterministic), and explicit input/output contracts.

| ID | Name | Package | Type | ADR |
| --- | --- | --- | --- | --- |
| C1 | Scenario Input | `c1_input` | Deterministic service | [0002](docs/adr/0002-c1-scenario-input.md) |
| C2 | Scenario Understanding | `c2_understanding` | LLM agent (propose + schema gate) | [0003](docs/adr/0003-c2-scenario-understanding.md) |
| C3 | Scenario Knowledge | `c3_knowledge` | Deterministic retrieval service | [0004](docs/adr/0004-c3-scenario-knowledge.md) |
| C4 | Scenario IR | `c4_ir` | Deterministic semantic model | [0005](docs/adr/0005-c4-scenario-ir.md) |
| C5 | Scenario Generation | `c5_generation` | Deterministic compiler | [0006](docs/adr/0006-c5-scenario-generation.md) |
| C6 | Scenario Validation | `c6_validation` | Deterministic validator | [0007](docs/adr/0007-c6-scenario-validation.md) |
| C7 | esmini Simulation | `c7_esmini` | Deterministic execution engine | [0008](docs/adr/0008-c7-esmini-simulation.md) |
| C8 | Observation & Evaluation | `c8_evaluation` | Deterministic metrics + rulebook | [0009](docs/adr/0009-c8-observation-evaluation.md) |
| C9 | Feedback & Improvement | `c9_feedback` | Deterministic repair + search service | [0010](docs/adr/0010-c9-feedback-improvement.md) |
| C10 | Scenario Management | `c10_management` | Deterministic persistence | [0011](docs/adr/0011-c10-scenario-management.md) |
| CX | Orchestration | `cx_orchestrator` | Hardcoded DAG | [0012](docs/adr/0012-cx-orchestration.md) |

---

## Abstraction layers

| Layer | Label | Contents |
| --- | --- | --- |
| L0 | Orchestration | CX — routes requests, enforces pipeline order, HITL, loop budgets |
| L1 | Capabilities | C1–C10 |
| L2 | Sub-capabilities | Per-component atomic functions (see `docs/trajectories.md`) |
| L3 | Intelligence | C2 (LLM); C9 (rules + search, not LLM) |
| L4 | Data stores | C10 + artifact files: IR, `.xosc`/`.xodr`, runs, metrics, logs |

---

## Component details

### C1 — Scenario Input

**Role:** Ingest and normalize user requirements across modalities.

**Inputs:** Natural language, structured params, `.xosc`/`.xodr`, crash narratives, multimodal artifacts.

**Outputs:** `RequestSpec` — schema-validated, unit-normalized request with unresolved-field markers.

**Key behaviors:**

- Deterministic adapters per modality; not an agent
- Missing parameters → HITL (ask user)
- Contradictions → HITL
- Must co-acknowledge C3 defaults with C2 before IR binding

**Sub-capabilities:** ingestion, normalization, ambiguity/missing detection, unit conversion, enum validation.

---

### C2 — Scenario Understanding

**Role:** Convert `RequestSpec` into structured scenario intent.

**Inputs:** `RequestSpec`, optional `EvidenceBundle` from C3.

**Outputs:** `IntentSpec` — slot-filled JSON validated by deterministic schema; `unknowns[]` for HITL.

**Key behaviors:**

- **Only LLM agent in Phase 1**
- Slot-filling proposer; schema is the gate
- Never rewrite user-explicit slots (e.g. requested lane id)
- Low confidence → ask user

**Sub-capabilities:** actor/interaction/temporal/spatial/behavior extraction, intent classification, constraint extraction.

---

### C3 — Scenario Knowledge

**Role:** Provide domain, standard, and simulator capability evidence without deciding the scenario.

**Inputs:** Feature queries, map id lookups, catalog lookups.

**Outputs:** `EvidenceBundle` — `{definitions, constraints, examples, compatibility, provenance}`.

**Key behaviors:**

- Typed graph + esmini K3 capability matrix (not vector-DB-as-truth)
- OSC-valid + esmini silent → `unknown` (dry-run decides)
- Map identity/version only — no lane topology
- Static matrix — no runtime write-back
- Phase-1 subset = pinned esmini build support
- CARLA / ScenarioRunner knowledge excluded

**Store nodes:** `Feature`, `StandardVersion`, `SimulatorBuild`, `SupportEdge`, `Catalog`, `MapAsset`, `DomainRule`.

---

### C4 — Scenario IR

**Role:** Canonical machine-readable scenario **meaning**, independent of OpenSCENARIO XML.

**Inputs:** `IntentSpec`, acked `EvidenceBundle` items.

**Outputs:** `ScenarioIR` — Scenic-like DSL shape; optional `suggestions[]`; objective stubs.

**Key behaviors:**

- Positions require explicit frame tags (road-relative and cartesian allowed)
- Ranges (min/max) allowed; no full distributions in Phase 1
- Objective meaning in IR; scoring thresholds in C8 rulebook
- Suggestions are diagnostics — C9 applies mutations

---

### C5 — Scenario Generation

**Role:** Compile IR to executable OpenSCENARIO artifacts.

**Inputs:** `ScenarioIR` only.

**Outputs:** `GeneratedScenario` — `.xosc`, optional `.xodr`, K3 flags, parameter bindings.

**Key behaviors:**

- Deterministic `scenariogeneration` compiler — no LLM
- Compile-time range expansion (concrete instances)
- Emit K3=unknown markers for C6 S6
- CTG/TRACE/diffusion out of scope
- Pass through IR `suggestions[]` untouched

---

### C6 — Scenario Validation

**Role:** Prove scenario structural/semantic executability before full simulation.

**Inputs:** `GeneratedScenario`, map assets, C3 compatibility hints, acked assumptions.

**Outputs:** `ValidationReport` — per-stage status, taxonomy, repair hints.

**Funnel (Phase 1):**

| Stage | Check |
| --- | --- |
| S1 | XSD / structural |
| S2 | OSC semantic |
| S3 | Map references / topology (E08) |
| S4 | Catalog + physical bounds |
| S5 | Static reachability — **skipped** |
| S6 | esmini dry-run — **only if K3=unknown** |

Short-circuit on FAIL. E09 unreachable trigger: WARN-and-pass at C6.

---

### C7 — esmini Simulation

**Role:** Execute validated scenarios in esmini.

**Inputs:** `GeneratedScenario`, OpenDRIVE map, `RunConfig`.

**Outputs:** `RunRecord` — logs, CSV trajectories, optional OSI, hang/timeout metadata.

**Key behaviors:**

- Modes: `preflight` (C6 S6) | `full` (experiments)
- Mandatory RunConfig: `esmini_build`, `dt`, `seed`, `max_time`
- Default controller only
- Hang: wall-clock OR step cap
- Batch headless; GUI for debug

---

### C8 — Observation & Evaluation

**Role:** Extract simulation state and score against scenario objectives.

**Inputs:** `RunRecord`, IR objective stubs, C8 rulebook.

**Outputs:** `EvaluationReport` — TTC, PET, collision, completion, pass/fail per objective.

**Key behaviors:**

- No LLM/VLM interpretation in Phase 1
- TTC always paired with PET
- Evaluate from CSV/states when OSI absent
- Does not invent objectives absent from IR

---

### C9 — Feedback & Improvement

**Role:** Repair failures and explore parameter space after successful validation/evaluation.

**Inputs:** `ValidationReport`, `EvaluationReport`, `ScenarioIR`, C10 history (E10 queries).

**Outputs:** `FeedbackAction` → `RevisedIR` for re-entry at C4.

**Subsystems:**

| Subsystem | When | Method |
| --- | --- | --- |
| Repair | C6 FAIL (structural) | Deterministic rules; no user-explicit slot edits |
| Explore | C6 PASS + post-C8 | Parameter search on IR ranges |

Stop: N=5 iterations OR no metric gain. Diversity constraints deferred.

---

### C10 — Scenario Management

**Role:** Persist artifacts, runs, provenance, and agent action logs.

**Inputs:** All component outputs (via CX).

**Outputs:** Stable record IDs, artifact paths, lineage queries.

**Key behaviors:**

- SQLite/Postgres + object files
- Hashes + human names/tags
- Keep all Phase-1 runs; no dedup
- Log C2 and C9 actions
- E10 runtime facts stored here (not written back to C3)

---

### CX — Orchestration

**Role:** Coordinate the end-to-end request lifecycle.

**Inputs:** User request, HITL responses.

**Outputs:** Final scenario artifacts, evaluation summary, or escalated HITL.

**Key behaviors:**

- Hardcoded DAG; tools = C1–C10 APIs only
- HITL for gaps, contradictions, low confidence, assumption acks
- Loop budget: 5 iterations OR no metric gain; 5-minute wall-clock per request
- Cannot skip/reorder C4, C6, C7
- C9 remains a separate called service

---

## Shared data contracts

| Contract | Producer | Primary consumers |
| --- | --- | --- |
| `RequestSpec` | C1 | C2, CX, C10 |
| `IntentSpec` | C2 | C4, CX, C10 |
| `EvidenceBundle` | C3 | C2, C4, C5, C6 |
| `ScenarioIR` | C4 | C5, C6, C8, C9, C10 |
| `GeneratedScenario` | C5 | C6, C7, C10 |
| `ValidationReport` | C6 | C9, CX, C10 |
| `RunRecord` | C7 | C8, C10 |
| `EvaluationReport` | C8 | C9, CX, C10 |
| `FeedbackAction` / `RevisedIR` | C9 | C4, CX, C10 |

---

## Phase-1 experiment coverage (E01–E10)

Discovery suite defined in `docs/trajectories.md` exercises components systematically (following, braking, lane change, cut-in, E08 invalid lane, E09 unreachable trigger, E10 esmini compatibility).

| Experiment | Primary stress |
| --- | --- |
| E01 | C1–C5 happy path + C7–C8 |
| E02–E07 | Triggers, multi-actor, evaluation |
| E08 | C6 map topology (intentional FAIL) |
| E09 | C6/C7 trigger reachability |
| E10 | C3 unknown + C6 S6 + C7 + C10 logging |

---

## Explicitly out of Phase 1

- CARLA, ScenarioRunner, OSC 2.x backends
- ROS2/FMI controllers in C7
- LLM evaluation in C8
- CTG/TRACE/diffusion generation in C5
- C3 runtime matrix updates from dry-runs
- Scenario deduplication in C10
- C9 diversity constraints

---

## Implementation status

| Component | Code status |
| --- | --- |
| All | Package stub only (`__init__.py`); contracts and ADRs defined |

Next implementation target (per checkpoint SEQ-1): **C3 Scenario Knowledge**.
