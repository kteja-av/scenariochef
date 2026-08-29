# ScenarioChef — Phase 1 Blueprint (No-Logic Skeleton)

## 1. Purpose and How to Read This Blueprint

This document is a **blueprint**, not an implementation plan with logic. It fixes the file layout, per-component responsibilities, the architectural style and patterns, the exact stdout trace the skeleton emits, and how the same seams scale from one request to a cloud software factory. The Phase-1 deliverable described here is a **no-logic skeleton**: every component (C1–C10, CX) is represented by a single `print(...)` trace line and a placeholder token passed to the next component. No component performs any real work yet.

Frozen architecture facts are sourced from `docs/checkpoint.md`, the ADRs in `docs/adr/0001..0012`, `component_inventory.md`, and `component_connection_map.md`; this blueprint adds nothing that contradicts them.

How to read: §2 shows where everything lives. §3 is the component table (what each box does and the frozen decision IDs it honors). §4 names the style and patterns and the trade-off of each. §5 defines the trace contract — the only observable behavior of the skeleton. §6 shows how the same boundaries grow later, all marked "later — not now."

## 2. File and Folder Structure

The skeleton produces `src/scenariochef/` exactly as below. `(exists)` = already in the repo as a stub, untouched. `(new)` = added by the skeleton. Sibling `tests/` and `docs/` are shown for context; `artifacts/` is the **proposed runtime output dir** (not created by the skeleton — reserved for C10 object files in later stages).

```
scenariochef/
├── src/scenariochef/
│   ├── __init__.py                       # (exists) package marker
│   ├── cli.py                            # (overwritten) entry point; main() -> run_pipeline()
│   ├── trace.py                          # (new) emit(step, component, direction, token) -> None
│   ├── c1_input/
│   │   ├── __init__.py                   # (exists) C1 package marker
│   │   └── runtime.py                    # (new) run_c1(raw_input) -> "<RequestSpec>"
│   ├── c2_understanding/
│   │   ├── __init__.py                   # (exists) C2 package marker
│   │   └── runtime.py                    # (new) run_c2(request_spec) -> "<IntentSpec>"
│   ├── c3_knowledge/
│   │   ├── __init__.py                   # (exists) C3 package marker
│   │   └── runtime.py                    # (new) run_c3(query) -> "<EvidenceBundle>"
│   ├── c4_ir/
│   │   ├── __init__.py                   # (exists) C4 package marker
│   │   └── runtime.py                    # (new) run_c4(intent_spec) -> "<ScenarioIR>"
│   ├── c5_generation/
│   │   ├── __init__.py                   # (exists) C5 package marker
│   │   └── runtime.py                    # (new) run_c5(scenario_ir) -> "<GeneratedScenario>"
│   ├── c6_validation/
│   │   ├── __init__.py                   # (exists) C6 package marker
│   │   └── runtime.py                    # (new) run_c6(generated_scenario) -> "<ValidationReport>"
│   ├── c7_esmini/
│   │   ├── __init__.py                   # (exists) C7 package marker
│   │   └── runtime.py                    # (new) run_c7(generated_scenario) -> "<RunRecord>"
│   ├── c8_evaluation/
│   │   ├── __init__.py                   # (exists) C8 package marker
│   │   └── runtime.py                    # (new) run_c8(run_record) -> "<EvaluationReport>"
│   ├── c9_feedback/
│   │   ├── __init__.py                   # (exists) C9 package marker
│   │   └── runtime.py                    # (new) run_c9(report) -> "<FeedbackAction>"
│   ├── c10_management/
│   │   ├── __init__.py                   # (exists) C10 package marker
│   │   └── runtime.py                    # (new) run_c10(record) -> "<persisted>"
│   └── cx_orchestrator/
│       ├── __init__.py                   # (exists) CX package marker
│       └── runtime.py                    # (new) run_pipeline() -> None; calls C1..C10 in fixed order
├── tests/
│   └── __init__.py                       # (exists) test suite marker
├── docs/
│   └── adr/                              # (exists) frozen ADRs 0001–0012 — untouched by the skeleton
└── artifacts/                            # (proposed) runtime output dir for C10 object files in later stages
```

The skeleton **adds** one `runtime.py` per component (C1–C10), `trace.py`, the CX `runtime.py`, and rewires `cli.py`. It touches no ADR and creates no `artifacts/` content.

## 3. Component Table

Types: **Det** = deterministic service · **LLM** = LLM agent (the only one) · **DAG** = orchestrator. In the skeleton, every component returns a placeholder token and persists nothing — the "persists to C10" behavior is represented by C10's own trace line at the end of the run.

| ID | Package / function | Type | Single responsibility | Input token | Output token | Frozen decisions honored |
| --- | --- | --- | --- | --- | --- | --- |
| C1 Scenario Input | `c1_input/runtime.py` `run_c1` | Det | Ingest and normalize heterogeneous user input into one validated `RequestSpec`. | `<raw_request>` | `<RequestSpec>` | C1-Q1..Q6, DERIVED-6, DERIVED-7 |
| C2 Understanding | `c2_understanding/runtime.py` `run_c2` | **LLM** | Propose slot-filled `IntentSpec` from the request; deterministic schema is the gate; never rewrites user-explicit slots. | `<RequestSpec>` | `<IntentSpec>` | C2-Q1..Q5, DERIVED-7, DERIVED-8 |
| C3 Knowledge | `c3_knowledge/runtime.py` `run_c3` | Det | Retrieve definitions/constraints/examples/compatibility/provenance evidence without deciding the scenario. | `<query>` | `<EvidenceBundle>` | C3-Q1..Q8, DERIVED-1..5 |
| C4 Scenario IR | `c4_ir/runtime.py` `run_c4` | Det | Build the canonical, simulator-independent `ScenarioIR` from validated intent (Scenic-like shape, frame-tagged positions, ranges). | `<IntentSpec>` | `<ScenarioIR>` | C4-Q1..Q5, DERIVED-9, DERIVED-10 |
| C5 Generation | `c5_generation/runtime.py` `run_c5` | Det | Compile `ScenarioIR` into executable OpenSCENARIO artifacts via the deterministic `scenariogeneration` API. | `<ScenarioIR>` | `<GeneratedScenario>` | C5-Q1..Q5, DERIVED-12, DERIVED-13 |
| C6 Validation | `c6_validation/runtime.py` `run_c6` | Det | Prove structural/semantic/map executability through the frozen S1–S6 funnel, short-circuiting on FAIL. | `<GeneratedScenario>` | `<ValidationReport>` | C6-Q1..Q5 |
| C7 esmini | `c7_esmini/runtime.py` `run_c7` | Det | Execute validated scenarios in esmini (`preflight`\|`full`) into a `RunRecord`; hang-guarded, reproducible. | `<GeneratedScenario>` | `<RunRecord>` | C7-Q1..Q5, DERIVED-14 |
| C8 Evaluation | `c8_evaluation/runtime.py` `run_c8` | Det | Score the run against IR objective stubs with a deterministic rulebook (no LLM/VLM). | `<RunRecord>` | `<EvaluationReport>` | C8-Q1..Q5, DERIVED-15 |
| C9 Feedback | `c9_feedback/runtime.py` `run_c9` | Det (called by DAG) | Repair structural failures or explore parameter ranges, stopping at the loop budget; never edits user-explicit slots. | `<EvaluationReport>` | `<FeedbackAction>` | C9-Q1..Q6, DERIVED-16, DERIVED-17, CX-Q6 |
| C10 Management | `c10_management/runtime.py` `run_c10` | Det | Persist every artifact, run, and C2/C9 action under hash + record id for full-lineage queries. | `<FeedbackAction>` | `<persisted>` | C10-Q1..Q5 |
| CX Orchestration | `cx_orchestrator/runtime.py` `run_pipeline` | DAG | Enforce the fixed step sequence, HITL gates, loop budget, and provenance fan-out to C10. | `<raw_request>` | `<done>` | CX-Q1..Q6, DERIVED-18 |

**Single intelligence boundary.** C2 is the *only* LLM agent in Phase 1. CX is a hardcoded DAG. C9 is a deterministic repair/explore service the DAG calls — it is not a second LLM. C1, C3, C4, C5, C6, C7, C8, C10 are deterministic services (DERIVED-8, DERIVED-18).

## 4. Architectural Style and Design Patterns

**Style: layered pipeline DAG with a single intelligence boundary.** The system is an abstraction stack (L0 orchestration → L1 capabilities → L2 sub-capabilities → L3 intelligence → L4 data stores, per `docs/tldraw_architecture.md` and `component_inventory.md`) through which one request flows as an ordered DAG. Intelligence (the LLM) exists on exactly one edge — C2 proposes, everything else is deterministic. CX routes; it never acts as an agent.

| Pattern | Where (component) | What it buys | What it costs |
| --- | --- | --- | --- |
| Adapter | C1 | Each input modality is normalized to one `RequestSpec` contract, so downstream components never see raw input. | All four Phase-1 modalities (NL, `.xosc`/`.xodr`, crash narrative, multimodal) must be adapted up front (DERIVED-6). |
| Compiler | C4 → C5 | IR→`.xosc` is deterministic and reproducible, and meaning stays simulator-independent. | A custom IR grammar/validator and its compile rules must be built and maintained (ADR-0005, ADR-0006). |
| Proposer–validator (schema gate) | C2 | Unconstrained model output can never reach IR — bounded, auditable intelligence on one edge only. | Schema maintenance grows with scenario vocabulary, and the LLM adds latency to every request (ADR-0003). |
| Repository / persistence | C10 | Queryable lineage and E10 history exist without writing runtime facts back to C3 (DERIVED-2). | Storage grows unbounded (no dedup, C10-Q5) and needs a migration path before Postgres (ADR-0011). |
| Service-per-capability | C1–C10 | Each capability is testable and replaceable in isolation, and CX's tool surface is capped at the C1–C10 APIs (CX-Q2). | More modules to wire, and contracts churn while the ADRs stabilize. |
| Orchestration DAG (explicit order) | CX | The control plane is deterministic: non-skippable C4/C6/C7, loop budget and HITL are enforced in one place (CX-Q1/Q3/Q4/Q5). | DAG changes require code edits, not prompt changes; the hardcoded sequence must later generalize to a state machine (ADR-0012). |

No other pattern is introduced: there is no logic engine, no message bus, no event sourcing — each would be speculative in a no-logic skeleton. The provenance-observer pattern is folded into C10: it is currently represented by a single end-of-run persistence line, and is listed here as a follow-up rather than a separate mechanism.

## 5. No-Logic Trace Contract

The skeleton has exactly one observable behavior: a stdout trace, one line per boundary, in this exact format:

```
[step:NN] CC DIR <token>
```

**Fields**

| Field | Meaning | Values |
| --- | --- | --- |
| `step:NN` | Step ordinal, zero-padded 2 digits | `01`, `02`, … |
| `CC` | Component id, left-padded to 3 chars | `CX`, `C1`…`C10` |
| `DIR` | Direction, left-padded to 3 chars | `IN` or `OUT` |
| `<token>` | Placeholder token moved to the next component | `<raw_request>`, `<RequestSpec>`, …, `<done>` |

**Fixed step sequence (CX enforces; C4, C6, C7 non-skippable per CX-Q5).**

```
CX  IN  <raw_request>
C1  IN  <raw_request>      C1  OUT <RequestSpec>
C2  IN  <RequestSpec>      C2  OUT <IntentSpec>
C3  IN  <query>            C3  OUT <EvidenceBundle>
C4  IN  <IntentSpec>       C4  OUT <ScenarioIR>
C5  IN  <ScenarioIR>       C5  OUT <GeneratedScenario>
C6  IN  <GeneratedScenario> C6 OUT <ValidationReport>
C7  IN  <GeneratedScenario> C7 OUT <RunRecord>
C8  IN  <RunRecord>        C8  OUT <EvaluationReport>
C9  IN  <EvaluationReport> C9  OUT <FeedbackAction>
C10 IN  <FeedbackAction>   C10 OUT <persisted>
CX  OUT <done>
```

C3 is queried opportunistically (C3-Q2/Q3): the skeleton shows one pull with `<query>`; later stages call it from C2, C4, C5, and C6. The C6→C9→C4 repair loop and the C8→C9 explore loop are **logic and are deferred** — this skeleton is the straight happy-path DAG only. Loop budget (N≤5 or no metric gain, 5-minute wall clock — CX-Q4/C9-Q4) and HITL gates (CX-Q3) are documented constraints, not implemented here.

**Worked example — one happy-path request.** This is the exact output of `PYTHONPATH=src python -m scenariochef.cli`:

```
[step:01] CX  IN  <raw_request>
[step:02] C1  IN  <raw_request>
[step:02] C1  OUT <RequestSpec>
[step:03] C2  IN  <RequestSpec>
[step:03] C2  OUT <IntentSpec>
[step:04] C3  IN  <query>
[step:04] C3  OUT <EvidenceBundle>
[step:05] C4  IN  <IntentSpec>
[step:05] C4  OUT <ScenarioIR>
[step:06] C5  IN  <ScenarioIR>
[step:06] C5  OUT <GeneratedScenario>
[step:07] C6  IN  <GeneratedScenario>
[step:07] C6  OUT <ValidationReport>
[step:08] C7  IN  <GeneratedScenario>
[step:08] C7  OUT <RunRecord>
[step:09] C8  IN  <RunRecord>
[step:09] C8  OUT <EvaluationReport>
[step:10] C9  IN  <EvaluationReport>
[step:10] C9  OUT <FeedbackAction>
[step:11] C10 IN  <FeedbackAction>
[step:11] C10 OUT <persisted>
[step:12] CX  OUT <done>
```

## 6. Scaling Path

Documentation only — no implementation here. The component/artifact seams and the canonical order never change across stages; scaling replaces *internals*, never the boundaries, which is what service-per-capability (§4) buys.

**(a) Single-flow skeleton — this phase (now).** One hardcoded `cx_orchestrator/runtime.py`, one request, placeholder tokens, trace only. No concurrency, no DB, no LLM. Everything below is **later — not now**.

**(b) One simple agent (C2 becomes a real LLM proposer behind the schema gate).**
- **later — not now**: C2 swaps its placeholder for a real slot-filling LLM call + Pydantic schema gate, logging every proposal to C10 (C10-Q4).
- **later — not now**: C3 becomes the typed graph + K3 capability matrix keyed to the pinned esmini build (per SEQ-1, C3 is the first detailed implementation); C4/C5 get a real IR and `scenariogeneration` compiler; C6/C7/C8 get the real funnel, esmini subprocess, and metrics; C10 activates SQLite + `artifacts/` object files with content hashes.
- CX's `run_pipeline` keeps the same call order — the DAG already exists.

**(c) Many concurrent agents/requests.**
- **later — not now**: CX replaces the hardcoded sequence with an explicit state machine carrying per-request state (ADR-0012 follow-up).
- **later — not now**: C7 batch runs move to process pools (GIL mitigation per ADR-0001).
- **later — not now**: C10 moves SQLite → Postgres and starts emitting per-row lineage instead of one summary record (ADR-0011 migration).
- **later — not now**: a bounded request queue/worker pool isolates the 5-minute wall-clock budget per request; the §5 trace line becomes the structured log every worker emits.

**(d) Hundreds of agents — a software factory in the cloud.**
- **later — not now**: each component becomes a deployable, stateless service with an HTTP boundary (ADR-0012 follow-up: "typed Python functions first, HTTP later if needed"); CX becomes the factory orchestrator submitting per-request DAG jobs to a queue with autoscaling workers.
- **later — not now**: C10 → Postgres cluster + object store; C2 → hosted LLM inference behind the same schema gate (rate limits, retries); C7 → pinned esmini container images on ephemeral batch workers; C3 → a read-only retrieval service; C6/C8 → shared stateless compute.
- **later — not now**: the §5 trace lines are aggregated into metrics/alerting, and config/secrets (esmini pins, DB URLs, model keys) move to centralized management. The blueprint's boundaries remain the scaling units.
