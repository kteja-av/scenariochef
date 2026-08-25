# Checkpoint — Phase 1 low-level design decisions

Temporary working file. Intended to be ingested later by Genesis.
Rule: do **not** record an architectural choice here unless the user confirmed it.

Last updated: 2026-08-22

---

## Status of this file

| Kind | How it is recorded |
| --- | --- |
| Confirmed decision | `DECIDED` + owner + reason + date |
| Sequencing / process move (not an architecture freeze) | `PROPOSED` until confirmed |
| Open choice the literature does not settle | `OPEN` + options + trade-offs |
| Logical consequence of a DECIDED row (not a new choice) | `DERIVED` |

---

## Why the first detailed page is C3 (Scenario Knowledge)

**Status:** `DECIDED` (SEQ-1, 2026-08-19)

C3 is the first detailed LLD page. Agent runtime is not the first page.

**Reason this was drawn first (not a claim that it is the most important component):**

1. The Phase-1 literature review actually supports a knowledge layer (HASCO RAG over XSD / esmini docs / `scenariogeneration`; the explicit gap is standard-valid vs esmini-executable).
2. The named agent-literature topics map onto *later* components. Doing those first would require freezing agent-vs-service boundaries that the thesis does not yet prove.
3. C2, C4, C5, C6, C9, and any future agent runtime all *query* knowledge. An unset knowledge contract will leak into every later LLD.
4. User constraint: one component first; knowledge was called out as large; cap of three later.
5. User confirmed SEQ-1: keep C3 as the first detailed page.

**Next:** freeze remaining pages via their question lists. Suggested: C1-Q5 / C2 split, then C4-Q1, then C5-Q1, then CX-Q1.

---

## Literature topic → component map

| Literature topic | Candidate component | Status |
| --- | --- | --- |
| Context engineering | C3 Scenario Knowledge | **DECIDED** — typed graph + esmini matrix |
| Agent planning | C9 Feedback & CX | **DECIDED** — C9 rules+search split; CX is a DAG |
| Agent evaluation + reliability | C8 Observation | **DECIDED** — rulebook vs IR stubs; no LLM layer-4 |
| Tool use + execution | CX (not C7) | **DECIDED** — DAG; C1–C10 APIs; C7 is the simulator |
| Save agent actions | C10 Scenario Management | **DECIDED** — SQL+files; log C2/C9 actions now |

---

## C3 contract (working, from existing LLD + review)

These were already on the C1–C10 LLD page. Still in force.

- C3 is a **retrieval / rules service**. It does not decide the scenario.
- Output envelope is **EvidenceBundle** `{definitions, constraints, examples, compatibility, provenance}`.
- Intelligence-heavy interpretation stays in C2; construction/serialization stays in C5; pass/fail stays in C6; esmini execution stays in C7.
- Standard capability ≠ esmini capability. That split is a research gap (E10), not an implementation detail.

---

## C3 decisions (user-confirmed 2026-08-19)

| ID | Status | Decision | Reason (as given / implied by the option) |
| --- | --- | --- | --- |
| SEQ-1 | DECIDED | Draw C3 detailed LLD first; keep that page | User confirmed keep-C3 sequencing |
| C3-Q1 | DECIDED | **B — Typed graph + esmini capability matrix** | Does not reproduce HASCO’s passive RAG as the store. Nodes: Feature, Version, Simulator, Map, Rule. Edges: supports / partial / unsupported / unknown. Docs may hang off nodes as *evidence*, not as the store |
| C3-Q2 | DECIDED | OSC=yes and esmini docs silent → C3 returns **`unknown`**. Execution authority is **C6/C7 dry-run** | C3 does not invent support. E10 is classified at preflight/runtime, not guessed in retrieval |
| C3-Q3 | DECIDED | **C3 stores and versions the map; C6 owns topology checks** | “Does lane 3 exist?” is validation (E08), not knowledge retrieval. C3 answers map identity, path, hash, version — not connectivity |
| C3-Q4 | DECIDED | **Static docs only** — runtime / E10 / dry-run **never write** the matrix | C3 stays a library, not an evolving world model. Rediscovery of the same `unknown` across runs is accepted |
| C3-Q5 | DECIDED | Phase-1 OSC subset = **whatever the pinned esmini build actually executes** | Version is not a marketing number (1.0/1.2/1.3). The pin is an esmini build id; K3 is keyed by that build |
| C3-Q6 | DECIDED | **CARLA / ScenarioRunner knowledge is out of Phase 1** | Matches existing Phase-1 notes. Do not ingest those sources into the graph |
| C3-Q7 | DECIDED | **Emit defaults, but C1/C2 must accept before use** | Assumptions are allowed in the bundle, never as silent facts. Unaccepted assumptions are not usable by C4/C5 |
| C3-Q8 | DECIDED | Authority ranking: **OSC XSD > esmini docs > catalogs > domain notes** | Standard text outranks simulator prose for *definition/syntax* conflicts. See DERIVED-1 for how this coexists with Q2/Q5 |

---

## Derived consequences (not new choices)

These follow from the table above. Overturn a DECIDED row if you do not want the consequence.

### DERIVED-1 — Q8 does not override Q2 / Q5

OSC XSD ranking is for **the same kind of claim** (what the construct *is*). It does **not** let C3 assert that esmini will *run* an OSC-valid feature.

| Claim kind | Winner | Status if missing |
| --- | --- | --- |
| Syntax / definition (“is this an OSC element?”) | OSC XSD (Q8) | `gap` |
| Catalog numeric fact (bbox, vehicle class) | catalog, then domain | `gap` or labeled assumption (Q7) |
| Will this esmini **build** execute it? | K3 matrix keyed by pinned build (Q5). If silent → `unknown` (Q2). Dry-run in C6/C7 is execution authority | `unknown`, never coerced to yes |
| Does this map have lane 3? | **not C3** (Q3). C6 topology | C3 may only return map identity |

### DERIVED-2 — Q4 + Q2: dry-run does not enrich C3

C6/C7 may discover that an `unknown` feature loads, hangs, or crashes. That fact is recorded in C10 (run/validation reports). It does **not** become a K3 edge. The matrix stays as curated from static sources.

Implication: C9 repair cannot ask C3 “prior E10 hits for this feature” unless that query reads **C10**, not C3.

### DERIVED-3 — Q7 requires an ack field on assumption items

EvidenceItem for defaults/patterns must carry:

- `fact_or_assumption = assumption`
- `accepted_by` must include **both C1 and C2** before C4 may bind (C1-Q3)
- C4/C5/C6 must refuse to consume assumptions missing either ack

Hidden unit conversions and unlabeled “typical 20 m gap” are contract violations.

### DERIVED-4 — Q1-B store shape (implementation sketch, still not code)

Graph (not a vector DB as source of truth):

- `Feature` (canonical key e.g. `osc.action.LaneChange`)
- `StandardVersion` (OSC/ODR version as metadata, not the Phase-1 subset pin)
- `SimulatorBuild` (the Q5 pin)
- `SupportEdge` (supports | partial | unsupported | unknown) + source_ref + doc excerpt as evidence blob
- `Catalog` / `CatalogEntry`
- `MapAsset` (id, path, hash, version) — **no lane graph inside C3** (Q3)
- `DomainRule` (always assumption-class unless it is a catalog number)

No CARLA/ScenarioRunner nodes (Q6).

### DERIVED-5 — Q-MAP on the tldraw page is reclassified

The board originally listed Q-MAP as a C3 query. Under Q3 it is a **C6** query. C3’s remaining map query is Q-MAP-ID: “which map asset, which hash, which version.”

---

## C1 / C2 decisions (user-confirmed 2026-08-19)

| ID | Status | Decision | Reason |
| --- | --- | --- | --- |
| C1-Q5 / C2-Q5 | DECIDED | **Keep the C1 / C2 split** | Normalize vs interpret stay separate. Review merge challenge rejected |
| C1-Q1 | DECIDED | **All listed modalities**: NL+params, .xosc/.xodr ingest, crash narratives, multimodal | User chose all of A–D. See DERIVED-6 |
| C1-Q2 | DECIDED | **Ask the user** when a parameter is missing | Do not reject, block-silently, or auto-ack a C3 default |
| C1-Q3 | DECIDED | **Both C1 and C2 must ack** C3 defaults | Tightens C3-Q7 |
| C1-Q4 | DECIDED | **Ask the user** on contradictory constraints | Same HITL policy as missing params (user-supplied option) |
| C1-Q6 | DECIDED | C1 is a **deterministic adapter + schema**, not an agent | |
| C2-Q1 | DECIDED | **Slot-filling LLM + JSON schema** | Chat2Scenario-like extraction |
| C2-Q4 | DECIDED | LLM **proposes**; **deterministic schema validates** | Resolves the Q1/Q4 clash: “no LLM” is withdrawn; schema is the gate |
| C2-Q2 | DECIDED | Low confidence / unknowns[] → **ask the user** | Same HITL as C1-Q2 |
| C2-Q3 | DECIDED | **Never rewrite user-explicit slots** | E08: keep lane 3; C6 rejects |

### DERIVED-6 — C1-Q1 all modalities is a Phase-1 scope expansion

The review placed dashcam/sketch multimodal in Phase 2 and treated crash-narrative trees as Txt2Sce-scale work. You explicitly put **A+B+C+D** in Phase 1. That does not freeze *how* each adapter is built, only that C1 must accept those inputs. Overturn C1-Q1 if you meant “eventually,” not “in the first runnable spec.”

### DERIVED-7 — HITL at C1/C2

Missing params, contradictions, and low-confidence understanding all **ask the user**. CX-Q3 is DECIDED (HITL on those gaps/acks only). A “HITL never” option would conflict.

### DERIVED-8 — Who is an agent so far

C1 is not an agent. C2 is an LLM proposer behind a schema gate (not unconstrained generation). C7 is not an agent. CX is a DAG; C2 is the only LLM agent.

---

## C4 decisions (user-confirmed 2026-08-19)

| ID | Status | Decision | Reason |
| --- | --- | --- | --- |
| C4-Q1 | DECIDED | **Scenic-like probabilistic DSL as the IR language** — language only; CARLA still out (C3-Q6) | Simulator-independent spatial/temporal semantics (Scenic). Not OSC-JSON. C5 must compile this language → OpenSCENARIO XML |
| C4-Q2 | DECIDED | **Both road-relative and cartesian allowed; every position carries a frame tag** | Frame is mandatory; untagged XYZ is a contract violation |
| C4-Q3 | DECIDED | **IR holds objective stubs; C8 owns thresholds/rulebook** | Meaning of “what to evaluate” is in IR; how to score is C8. Partially constrains C8-Q1 (C8 is the evaluator, not a second objective author) |
| C4-Q4 | DECIDED | **Ranges (min/max) allowed** — not full distributions in Phase 1 | Phase-1 subset of Scenic: spatial language + interval uncertainty, not probabilistic sampling yet. See DERIVED-9 |
| C4-Q5 | DECIDED | **C4 may emit repair suggestions; C9 still applies them** | C4 does not mutate the canonical IR on its own. Suggestions are diagnostics, not silent edits (E08 must remain visible) |

### DERIVED-9 — Scenic-like ≠ Scenic-full, and ≠ CARLA

Q1 is the *language shape* (relative geometry, declarative constraints, behaviors). Q4 forbids Phase-1 distributions/sampling, so this is **not** shipping the Scenic compiler or CARLA backend. C5 still serializes to `.xosc` for esmini. If you later want Scenic sampling, that reopens C4-Q4.

### DERIVED-10 — C4 suggestions vs E08/E09

A suggestion such as “lane 3 does not exist; nearest is 2” may appear on the IR as `suggestions[]`. The canonical `target_lane=3` stays: C2-Q3 and C9-Q6 both forbid rewriting user-explicit slots.

### DERIVED-11 — C8-Q1 is partly constrained

C8 evaluates IR objective stubs against a C8 rulebook. C8 should not invent a new objective that is absent from the IR stub. C8-Q1…Q5 are DECIDED.

---

## C5 decisions (user-confirmed 2026-08-19)

| ID | Status | Decision | Reason |
| --- | --- | --- | --- |
| C5-Q1 | DECIDED | **Deterministic scenariogeneration compiler only** — no LLM in C5 | Scenic-like IR → API → XML |
| C5-Q2 | DECIDED | **C5 owns variation** as compile-time range expansion | Not DriveFuzz. Canonical IR not rewritten |
| C5-Q3 | DECIDED | **Emit K3=unknown** for C6 S6 dry-run | Must not substitute a supported action. Fits C6-Q2 unknown-only |
| C5-Q4 | DECIDED | **CTG/TRACE diffusion out of Phase 1** | Review Phase-2. Fits C4-Q4 (no distributions) and C5-Q1 (compiler-only) |
| C5-Q5 | DECIDED | **C5 consumes IR only** | C9 applies C4 suggestions |

### DERIVED-12 — C5 variation ≠ IR mutation

C5 binds C4 ranges into concrete `.xosc` instances. Search-based criticality is C9 (DECIDED: param search after PASS).

### DERIVED-13 — C4-Q5 + C5-Q5

`suggestions[]` pass through C5 untouched.

---

### C5 Generation — frozen

### C6 Validation

| ID | Status | Decision | Notes |
| --- | --- | --- | --- |
| C6-Q1 | DECIDED | **Skip static reachability in Phase 1** | Gap 1 deferred. E09 not caught in C6 S5 |
| C6-Q2 | DECIDED | **Dry-run only when K3=unknown** | Conflict resolved: C3-Q2 and C5-Q3 stand. User changed C6-Q2 from “never” to unknown-only |
| C6-Q3 | DECIDED | E09 = **WARN-and-pass** | With Q1=skip, C6 will not emit this; detection shifts to C7/C8 unless Q1 is reopened |
| C6-Q4 | DECIDED | **Freeze S1→S6; short-circuit on FAIL** | If S5/S6 are skipped/no-op, order is S1–S4 in Phase 1 |
| C6-Q5 | DECIDED | Physical bounds = **catalog facts + C1/C2-acked assumptions** | Fits C3-Q7 / C1-Q3 |

**C6-Q2 resolved:** dry-run **only when K3=unknown**. C3-Q2 and C5-Q3 stand. Phase-1 funnel is S1–S4 always; S5 is a no-op (Q1 skip); S6 runs only on unknown features.

### C7 esmini

| ID | Status | Decision | Reason |
| --- | --- | --- | --- |
| C7-Q1 | DECIDED | **One runner, two modes**: `preflight` \| `full` | C6 S6 calls `preflight` when K3=unknown. Not a second binary |
| C7-Q2 | DECIDED | Mandatory RunConfig: **esmini_build, dt, seed, max_time**. OSI and headless optional | Repro minimum. See DERIVED-14 |
| C7-Q3 | DECIDED | **Internal Default controller only** | ROS2/FMI out of Phase 1 |
| C7-Q4 | DECIDED | Hang policy = **wall-clock timeout AND step cap** | Either trip → terminate, record in RunRecord |
| C7-Q5 | DECIDED | **GUI allowed for debug; batch is headless** | Headless default for E01–E10 batch |

### DERIVED-14 — Batch vs debug RunConfig

Batch: `headless=true`. Debug may set `headless=false`. OSI remains optional; if off, C8-Q5 is DECIDED: evaluate from CSV/states.

### C7 esmini — frozen

### C8 Evaluation

| ID | Status | Decision | Reason |
| --- | --- | --- | --- |
| C8-Q1 | DECIDED | **C8 rulebook pass/fail against IR objective stubs** | Fits C4-Q3. C8 does not invent new objectives |
| C8-Q2 | DECIDED | **No layer-4 LLM/VLM** in Phase 1 | Measurement + rulebook only |
| C8-Q3 | DECIDED | Core set: **TTC, collision, completion** | See DERIVED-15 with Q4 |
| C8-Q4 | DECIDED | **Always pair TTC with PET** | TTC false-positive mitigation |
| C8-Q5 | DECIDED | **Evaluate from CSV/states if OSI missing** | Matches C7 OSI-optional |

### DERIVED-15 — Phase-1 metric set

Effective set: **TTC, PET, collision, completion**. PET is required whenever TTC is reported (Q4), so Q3’s “TTC-only” is expanded by pairing, not replaced.

### C8 Evaluation — frozen

### C9 Feedback

| ID | Status | Decision | Reason |
| --- | --- | --- | --- |
| C9-Q1 | DECIDED | **Hard split**: structural repair vs exploration | Matches review Gap 3 framing |
| C9-Q2 | DECIDED | **Rules on structure; search/fuzz on parameters** | Not SERA-in-C9. Not unified CX agent |
| C9-Q3 | DECIDED | **Diversity constraint later**, not Phase 1 | Gap 3 deferred |
| C9-Q4 | DECIDED | Stop on **N=5 iterations OR no metric gain** | N frozen 2026-08-22 |
| C9-Q5 | DECIDED | **Mutate IR** → RevisedIR | Not rollback to IntentSpec/RequestSpec |
| C9-Q6 | DECIDED | **Never change user-explicit slots** | Aligns with C2-Q3. E08 cannot be “fixed” by snapping lanes |

### DERIVED-16 — E08 repair under C9-Q6

C9 may classify map-topology FAIL and stop or escalate to the user (C1 HITL). It may **not** rewrite `lane 3` to `lane 2`. `suggestions[]` from C4 stay suggestions.

### DERIVED-17 — Two C9 subsystems

- **Repair:** deterministic patches that do not touch user-explicit slots (schema/catalog/link fixes).
- **Explore:** parameter search on IR ranges after C6 PASS (Q1 split). C5 range expansion is compile-time; C9 search is post-eval.

### C9 Feedback — frozen

### C10 Management

| ID | Status | Decision | Reason |
| --- | --- | --- | --- |
| C10-Q1 | DECIDED | **SQLite/Postgres + object files** | Queryable E10-by-feature; files for artifacts |
| C10-Q2 | DECIDED | **Hashes and human names/tags** | Identity + usability |
| C10-Q3 | DECIDED | **Keep all Phase-1 runs** | Discovery suite is small enough |
| C10-Q4 | DECIDED | **Log C2/C9 proposals as actions now** | Save-actions without waiting on CX |
| C10-Q5 | DECIDED | **No dedup in Phase 1** | Do not drop near-duplicates while discovering failures |

### C10 Management — frozen

### CX Orchestration / agent runtime

| ID | Status | Decision | Reason |
| --- | --- | --- | --- |
| CX-Q1 | DECIDED | **DAG orchestrator + C2 as the LLM agent; C9 on the DAG as repair/explore service** | Option C topology. C9 stays rules+search (C9-Q2), not a second LLM. See DERIVED-18 |
| CX-Q2 | DECIDED | **Tools = C1–C10 APIs only** | No shell, no raw file edits |
| CX-Q3 | DECIDED | **HITL** for missing params, contradictions, low confidence, and assumption acks | Already required by C1/C2. Not every repair, not every run |
| CX-Q4 | DECIDED | Loop budget = **N=5 or no metric gain, plus 5-minute wall-clock per request** | N and wall frozen 2026-08-22 |
| CX-Q5 | DECIDED | **May not skip or reorder C4/C6/C7** | Compiler pipeline stays intact |
| CX-Q6 | DECIDED | **Keep C9 as a service the DAG calls** | Do not collapse C9 into CX |

### DERIVED-18 — “Two agents” vs C9-Q2

CX-Q1 option C is the **control topology** from trajectories.md, not a claim that C9 is an LLM. Frozen C9 is rule-based structural repair + parameter search. The only LLM agent in Phase 1 is **C2** (propose slots, schema gate). CX itself is a **hardcoded DAG** and cannot skip C4/C6/C7.

### CX — frozen

---

## Still `OPEN` — leftovers only

None. C5-Q4, C9-Q4 **N**, and CX-Q4 wall-clock were closed 2026-08-22.

---

## Decisions log

| Date | ID | Status | Decision | Reason | Source |
| --- | --- | --- | --- | --- | --- |
| 2026-08-19 | SEQ-1 | DECIDED | C3 detailed LLD first | Knowledge contract gates later agent pages | User confirm (keep C3) |
| 2026-08-19 | C3-Q1 | DECIDED | Typed graph + capability matrix | Research gap 2, not HASCO reproduction | User |
| 2026-08-19 | C3-Q2 | DECIDED | `unknown` + defer execution to C6/C7 dry-run | C3 must not guess esmini support | User |
| 2026-08-19 | C3-Q3 | DECIDED | C3 versions maps; C6 checks topology | E08 is validation | User |
| 2026-08-19 | C3-Q4 | DECIDED | Static matrix; no runtime write-back | Keep C3 a library | User |
| 2026-08-19 | C3-Q5 | DECIDED | Subset = pinned esmini build’s actual support | Standard version ≠ executable subset | User |
| 2026-08-19 | C3-Q6 | DECIDED | No CARLA/ScenarioRunner knowledge in Phase 1 | Phase-1 esmini-only | User |
| 2026-08-19 | C3-Q7 | DECIDED | Defaults allowed; C1/C2 must ack before use | Kill hidden Unknown Knowns | User |
| 2026-08-19 | C3-Q8 | DECIDED | OSC XSD > esmini docs > catalogs > domain | Definition authority ≠ execution authority | User |
| 2026-08-19 | SEQ-2 | DECIDED | Draw detailed LLD pages for all remaining components (options OPEN) | User: “do this for all the components” | User |
| 2026-08-19 | C1-Q5 | DECIDED | Keep C1/C2 split | User |
| 2026-08-19 | C1-Q1 | DECIDED | All modalities A–D | User “all of the above” |
| 2026-08-19 | C1-Q2 | DECIDED | Ask user on missing params | User |
| 2026-08-19 | C1-Q3 | DECIDED | Both C1 and C2 must ack defaults | User |
| 2026-08-19 | C1-Q4 | DECIDED | Ask user on contradictions | User (custom) |
| 2026-08-19 | C1-Q6 | DECIDED | C1 not an agent | User |
| 2026-08-19 | C2-Q1 | DECIDED | Slot-filling LLM + JSON schema | User |
| 2026-08-19 | C2-Q4 | DECIDED | LLM proposes; schema validates | User resolved Q1/Q4 clash |
| 2026-08-19 | C2-Q2 | DECIDED | Ask user on low confidence | User |
| 2026-08-19 | C2-Q3 | DECIDED | Never rewrite user-explicit slots | User |
| 2026-08-19 | C4-Q1 | DECIDED | Scenic-like IR language (not CARLA) | User |
| 2026-08-19 | C4-Q2 | DECIDED | Positions both allowed; frame tag required | User |
| 2026-08-19 | C4-Q3 | DECIDED | IR objective stubs; C8 owns rulebook | User |
| 2026-08-19 | C4-Q4 | DECIDED | Ranges, not full distributions | User |
| 2026-08-19 | C4-Q5 | DECIDED | C4 may suggest; C9 applies | User |

| 2026-08-19 | C5-Q1 | DECIDED | Compiler-only scenariogeneration | User |
| 2026-08-19 | C5-Q2 | DECIDED | C5 owns compile-time range expansion | User |
| 2026-08-19 | C5-Q3 | DECIDED | Emit K3=unknown; dry-run in C6/C7 | User |
| 2026-08-22 | C5-Q4 | DECIDED | Diffusion / CTG / TRACE out of Phase 1 | User |
| 2026-08-19 | C5-Q5 | DECIDED | C5 consumes IR; no mutation | User |

| 2026-08-19 | C6-Q1 | DECIDED | Skip static reachability Phase 1 | User |
| 2026-08-19 | C6-Q2 | DECIDED | Dry-run only when K3=unknown | User resolved vs C3-Q2 |
| 2026-08-19 | C6-Q3 | DECIDED | E09 WARN-and-pass | User |
| 2026-08-19 | C6-Q4 | DECIDED | S1→S6 frozen; short-circuit FAIL | User |
| 2026-08-19 | C6-Q5 | DECIDED | Bounds = catalog + acked assumptions | User |
| 2026-08-19 | C7-Q1 | DECIDED | One runner, preflight \| full | User |
| 2026-08-19 | C7-Q2 | DECIDED | Mandatory: build, dt, seed, max_time | User |
| 2026-08-19 | C7-Q3 | DECIDED | Default controller only | User |
| 2026-08-19 | C7-Q4 | DECIDED | Hang = wall clock + step cap | User |
| 2026-08-19 | C7-Q5 | DECIDED | Batch headless; GUI debug OK | User |
| 2026-08-19 | C8-Q1 | DECIDED | C8 rulebook vs IR stubs | User |
| 2026-08-19 | C8-Q2 | DECIDED | No LLM interpretation Phase 1 | User |
| 2026-08-19 | C8-Q3 | DECIDED | TTC + collision + completion | User |
| 2026-08-19 | C8-Q4 | DECIDED | Pair TTC with PET | User |
| 2026-08-19 | C8-Q5 | DECIDED | CSV-only eval allowed | User |
| 2026-08-19 | C9-Q1 | DECIDED | Hard split repair vs explore | User |
| 2026-08-19 | C9-Q2 | DECIDED | Rules on structure; search on params | User |
| 2026-08-19 | C9-Q3 | DECIDED | Diversity later, not Phase 1 | User |
| 2026-08-22 | C9-Q4 | DECIDED | Stop: N=5 OR no metric gain | User |
| 2026-08-19 | C9-Q5 | DECIDED | Mutate IR (RevisedIR) | User |
| 2026-08-19 | C9-Q6 | DECIDED | Never change user-explicit slots | User |
| 2026-08-19 | C10-Q1 | DECIDED | SQL + object files | User |
| 2026-08-19 | C10-Q2 | DECIDED | Hashes and names/tags | User |
| 2026-08-19 | C10-Q3 | DECIDED | Keep all Phase-1 runs | User |
| 2026-08-19 | C10-Q4 | DECIDED | Log C2/C9 actions now | User |
| 2026-08-19 | C10-Q5 | DECIDED | No dedup in Phase 1 | User |
| 2026-08-19 | CX-Q1 | DECIDED | DAG + C2 LLM agent; C9 as DAG service | User option C + DERIVED-18 |
| 2026-08-19 | CX-Q2 | DECIDED | C1–C10 APIs only | User |
| 2026-08-19 | CX-Q3 | DECIDED | HITL on gaps/acks only | User |
| 2026-08-22 | CX-Q4 | DECIDED | N=5 or no gain + 5 min wall-clock / request | User |
| 2026-08-19 | CX-Q5 | DECIDED | No skip/reorder C4/C6/C7 | User |
| 2026-08-19 | CX-Q6 | DECIDED | Keep C9 as a called service | User |

---

## Next

All C1–C10 + CX architecture options are frozen. No OPEN rows remain. Genesis can ingest this file. Overturn any row explicitly if you change your mind.
