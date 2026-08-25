# Phase 1 — Initial Dry Runs (E01 & E02)

Working document. Captures two conceptual dry runs through the frozen C1–C10 + CX architecture.

**Authority:** `checkpoint.md` (all architecture options frozen as of 2026-08-22).  
**Board:** `Automated Scenario Architecture` tldraw — LLD pages per component.  
**Purpose:** Validate that the workflow is understandable end-to-end before implementation or Genesis ingest.

---

## Shared architecture context

### Pipeline (CX hardcoded DAG)

```
C1 → C2 ⇄ C3 → C4 → C5 → C6 ──PASS──→ C7 → C8 → C9 ──→ C5 (loop)
                              └──FAIL──→ C9 ──→ C5
All components emit provenance → C10
```

### Frozen rules that apply to both dry runs

| Rule | Source |
| --- | --- |
| C1 deterministic; C2 LLM proposes, schema validates | C1-Q6, C2-Q4 |
| Missing params / contradictions / low confidence → **ask user** (HITL) | C1-Q2/Q4, C2-Q2, CX-Q3 |
| C3 typed graph + esmini matrix; `unknown` → C6 S6 dry-run only | C3-Q1/Q2 |
| C3 versions maps; **C6 owns topology** | C3-Q3 |
| IR = Scenic-like language; frame-tagged positions; ranges OK | C4-Q1/Q2/Q4 |
| C5 = compiler-only; consumes IR; emits unknown features | C5-Q1/Q3/Q5 |
| C6 S5 reachability skipped Phase 1; S6 only if K3=unknown | C6-Q1/Q2 |
| C7 one runner, modes `preflight \| full`; mandatory: build, dt, seed, max_time | C7-Q1/Q2 |
| C8 rulebook vs IR stubs; TTC paired with PET; no LLM layer-4 | C8-Q1/Q2/Q4 |
| C9 split repair vs explore; mutate IR; never user-explicit slots | C9-Q1/Q2/Q6 |
| C9 stop: N=5 or no metric gain; CX + 5 min wall-clock | C9-Q4, CX-Q4 |
| C10 SQL + files; log C2/C9 actions; keep all runs | C10-Q1/Q4/Q3 |

### CX budgets (both runs)

- `request_id` assigned per request
- Wall-clock cap: **5 minutes per request**
- C9 loop cap: **N = 5 iterations OR no metric gain**

---

## Dry run 1 — E01 Constant-Speed Following

### Experiment reference

From `trajectories.md`: **E01 — Constant-Speed Following**. Tests basic longitudinal interaction: understanding, IR, generation, simulation, observation. Expected: **PASS**. No C9 loop on happy path.

### User request (C1 input)

> “Create a following scenario: ego and lead both at 15 m/s, 30 m gap, same lane, straight two-lane road, run 20 s.”

`request_id`: `req-001`

### Step 1 — C1 Scenario Input

**Role:** Normalize and validate. No interpretation.

**Output — RequestSpec:**

```yaml
request_id: req-001
intent_text: "following scenario, ego and lead 15 m/s, 30 m gap, same lane, 20 s"
parameters:
  ego_speed:  { value: 15, unit: m/s, source: user-explicit }
  lead_speed: { value: 15, unit: m/s, source: user-explicit }
  gap:        { value: 30, unit: m,  source: user-explicit }
  duration:   { value: 20, unit: s,  source: user-explicit }
missing: []
contradictions: []
assumption_acks: []
```

**HITL:** Not triggered (all parameters explicit).

**C10:** Raw input + RequestSpec.

---

### Step 2 — C2 Understanding (+ C3)

**Role:** LLM slot-filling; schema gate. Queries C3 for definitions and compatibility.

**C3 queries (example):**

- Q-DEF: `SpeedAction`, lane-relative position
- Q-COMPAT: features on pinned build `esmini-2.48.0` → `supported`

**Output — IntentSpec:**

```yaml
actors: [ego, lead]
relations: [following, same_lane]
initial_state:
  ego.speed: 15 m/s
  lead.speed: 15 m/s
  gap: 30 m
maneuvers: [lead_maintain_speed, ego_follow]
triggers: [start_immediately]
objective_stub: stable_following
unknowns: []
confidence: high
```

**C10:** IntentSpec + C2 action log.

---

### Step 3 — C4 Scenario IR

**Role:** Canonical Scenic-like IR; simulator-independent meaning.

```yaml
ScenarioIR:
  map: { id: map_straight_2lane_v1, hash: abc123 }
  actors:
    ego:  { init: { lane: 1, s_offset: 0,   speed: 15 m/s } }
    lead: { init: { lane: 1, s_offset: -30, speed: 15 m/s } }
  behaviors:
    lead: maintain_speed(15 m/s)
    ego:  follow(lead, target_gap: 30 m)
  triggers: [on_start]
  duration: 20 s
  evaluation_stubs: [stable_gap, no_collision]
  suggestions: []
```

**C10:** ScenarioIR v1.

---

### Step 4 — C5 Generation

**Role:** Compiler-only. IR → scenariogeneration → `.xosc`.

```yaml
ScenarioBundle:
  files: [scenario.xosc, map_ref: map_straight_2lane_v1.xodr]
  feature_keys_emitted: [SpeedAction, RelativeDistance, LanePosition, ...]
  manifest: { ir_version: 1, bundle_hash: <hash> }
```

No range expansion (all point values). No IR mutation.

**C10:** Bundle + hash.

---

### Step 5 — C6 Validation

| Stage | E01 result |
| --- | --- |
| S1 XML/XSD | PASS |
| S2 Semantic/refs | PASS |
| S3 Map topology | PASS |
| S4 Physical plausibility | PASS |
| S5 Reachability | Skipped (Phase 1) |
| S6 Preflight | Skipped (no K3=unknown features) |

```yaml
ValidationReport:
  status: PASS
  phase: S4_complete
  diagnostics: []
```

**Branch not taken:** FAIL → C9 → C5.

**C10:** ValidationReport.

---

### Step 6 — C7 esmini Simulation

```yaml
RunConfig:
  esmini_build: esmini-2.48.0
  dt: 0.05
  seed: 42
  max_time: 20 s
  headless: true
  osi: false
```

```yaml
RunRecord:
  run_id: run-001
  termination: time_limit
  runtime_errors: []
```

**Expected behaviour:** Both vehicles same lane; gap ~stable; no collision; continuous logs.

**C10:** RunRecord + RunConfig pins.

---

### Step 7 — C8 Evaluation

```yaml
EvaluationReport:
  metrics:
    min_gap: ~28–32 m
    ttc: large
    pet: n/a
    collision: false
  objective_status: PASS
  completion: true
```

Rulebook checks IR stubs: stable gap, no collision.

**C10:** EvaluationReport.

---

### Step 8 — C9 Feedback

**Not invoked.** E01 PASS with no exploration request → single pass, no loop.

---

### Step 9 — CX / C10 outcome

**CX:** Terminates after one pass.

**Lineage in C10:**

```
req-001 → IntentSpec → ScenarioIR v1 → Bundle → ValidationReport (PASS)
       → RunRecord run-001 → EvaluationReport (PASS)
```

### E01 — What was proven vs not exercised

| Proven | Not exercised |
| --- | --- |
| Full happy-path pipeline | HITL (missing params) |
| C2⇄C3 grounding | K3=unknown → S6 preflight |
| Scenic-like IR → compiler | Range expansion |
| C6 S1–S4 | S5 reachability, E09 |
| C7 + RunConfig pins | C9 repair/explore loop |
| C8 metrics + rulebook | OSI stream (CSV path only if OSI off) |

---

## Dry run 2 — E02 Sudden Lead Braking

### Experiment reference

From `trajectories.md`: **E02 — Sudden Lead Braking**. Tests trigger generation, longitudinal action, evaluation. Expected: **PASS**, then optional C9 exploration.

### User request (C1 input)

> “Ego and lead both at 20 m/s, 40 m gap. After 5 seconds the lead brakes hard for 3 seconds. Straight road. Check ego response.”

`request_id`: `req-002`

### What E02 adds over E01

| Capability | E01 | E02 |
| --- | --- | --- |
| Triggers | `on_start` only | `simulation_time > 5 s` |
| Maneuvers | maintain / follow | cruise → decelerate |
| C3 | basic actions | + time conditions, decel profiles |
| C8 | gap stability | TTC + PET, headway collapse |
| C9 | none | **explore loop** after PASS |

---

### Step 1 — C1 Scenario Input

```yaml
request_id: req-002
parameters:
  ego_speed:      { value: 20, unit: m/s, source: user-explicit }
  lead_speed:     { value: 20, unit: m/s, source: user-explicit }
  gap:            { value: 40, unit: m,  source: user-explicit }
  trigger_time:   { value: 5,  unit: s,  source: user-explicit }
  brake_duration: { value: 3,  unit: s,  source: user-explicit }
missing:
  - lead_deceleration_rate   # "hard" is not numeric
contradictions: []
```

**HITL (C1-Q2):** System asks user for deceleration rate.  
**User answers:** `−5 m/s²` → recorded as user-explicit (not C3 assumption).

**C10:** RequestSpec + HITL exchange.

---

### Step 2 — C2 Understanding (+ C3)

**C3 queries:**

| Query | Result |
| --- | --- |
| Q-DEF: SimulationTimeCondition | OSC definition |
| Q-DEF: AbsoluteSpeedAction / decel profile | definition + catalog example |
| Q-COMPAT: time trigger + speed action chain | `supported` |

**Output — IntentSpec:**

```yaml
actors: [ego, lead]
relations: [following, same_lane]
initial_state:
  ego.speed: 20 m/s
  lead.speed: 20 m/s
  gap: 40 m
phases:
  - name: cruise
    until: simulation_time > 5 s
  - name: lead_brake
    trigger: simulation_time > 5 s
    lead.action: decelerate at -5 m/s² for 3 s
objective_stub: ego_survives_braking_event
unknowns: []
```

**C10:** IntentSpec + C2 action log.

---

### Step 3 — C4 Scenario IR

```yaml
ScenarioIR:
  map: { id: map_straight_2lane_v1, hash: abc123 }
  actors:
    ego:  { init: { lane: 1, s: 0,  speed: 20 m/s } }
    lead: { init: { lane: 1, s: -40, speed: 20 m/s } }
  storyboard:
    - phase: cruise
      until: t > 5 s
      lead: maintain_speed(20 m/s)
      ego:  follow(lead, gap: 40 m)
    - phase: lead_brake
      trigger: simulation_time > 5 s
      lead: absolute_speed_profile(decel: -5 m/s², duration: 3 s)
      ego:  follow(lead)   # observe response; no scripted ego brake
  evaluation_stubs:
    - min_ttc_during_event
    - no_collision
    - lead_speed_decreases_after_t5
  suggestions: []
```

**C10:** ScenarioIR v1.

---

### Step 4 — C5 Generation

Compiler emits:

- Init: both 20 m/s, 40 m gap
- Event 1: cruise from t=0
- Event 2: `SimulationTimeCondition > 5` → lead `AbsoluteSpeedAction` (−5 m/s², 3 s)
- Ego: Default controller (lane follow)

```yaml
ScenarioBundle:
  feature_keys_emitted:
    - SimulationTimeCondition
    - AbsoluteSpeedAction
    - LanePosition
```

**C10:** Bundle.

---

### Step 5 — C6 Validation

All stages S1–S4 PASS. S5 skipped. S6 skipped (known-supported features).

```yaml
ValidationReport: { status: PASS, phase: S4_complete }
```

**C7 allowed.**

---

### Step 6 — C7 esmini Simulation

```yaml
RunConfig:
  esmini_build: esmini-2.48.0
  dt: 0.05
  seed: 42
  max_time: 25 s
  headless: true
```

| Time | Behaviour |
| --- | --- |
| 0–5 s | Both ~20 m/s, gap ~40 m |
| t = 5 s | Trigger fires; lead decelerates |
| 5–8 s | Gap shrinks; TTC drops |
| 8+ s | Lead at lower speed |

```yaml
RunRecord:
  run_id: run-002
  trigger_log:
    - { name: lead_brake, fired_at: 5.0 s, ok: true }
  runtime_errors: []
```

**C10:** RunRecord.

---

### Step 7 — C8 Evaluation

```yaml
EvaluationReport (nominal, run-002):
  metrics:
    lead_speed_at_t5: 20 m/s
    lead_speed_at_t8: ~5 m/s
    min_gap: ~15–25 m
    min_ttc: 2.8 s
    min_pet: 1.1 s
    collision: false
    trigger_fired: { lead_brake: true }
  objective_status: PASS
  completion: true
```

TTC always reported with PET (C8-Q4). Rulebook checks IR stubs.

**C10:** EvaluationReport.

---

### Step 8 — C9 Feedback (exploration loop)

**Path:** Explore (C6 PASS; no structural repair).

**Mechanism:** Parameter search on IR (C9-Q2). Structure unchanged (C9-Q6).

| Iter | Mutation | Notes |
| --- | --- | --- |
| 1 | baseline | gap=40, decel=−5, t_trigger=5 |
| 2 | gap 40→25 m | smaller headway |
| 3 | decel −5→−7 m/s² | harder brake |
| 4 | trigger 5→3 s | earlier brake |
| 5 | gap 25 + decel −7 | combined stress → collision |

Each iteration: `RevisedIR → C5 → C6 → C7 → C8 → C10`.

**Example iter 3 (PASS, more critical):**

```yaml
EvaluationReport (iter 3):
  min_ttc: 0.9 s
  min_pet: 0.4 s
  collision: false
  objective_status: PASS
```

**Example iter 5 (FAIL):**

```yaml
EvaluationReport (iter 5):
  min_ttc: 0.3 s
  collision: true
  objective_status: FAIL
```

**Stop:** N=5 reached (or no metric gain / wall-clock).

```yaml
FeedbackRecord:
  class: explore
  best_candidate: iter-3
  RevisedIR_ref: ir-req-002-v4
  iterations_used: 5
```

**Repair path not used** (no C6 FAIL).

---

### Step 9 — CX / C10 outcome

**CX returns:**

- Nominal E02 PASS (`run-002`)
- Most critical safe variant: iter-3 (TTC ≈ 0.9 s, no collision)
- Full multi-iteration lineage in C10

**Lineage (abbreviated):**

```
req-002 → IR v1 → bundle v1 → run-002 → eval-002 (PASS)
         → IR v2 → … → eval-003
         → IR v3 → … → eval-004 (best safe)
         → …
         → IR v5 → … → eval-006 (collision)
```

### E02 — Branches not hit

| Case | Would happen at |
| --- | --- |
| Absurd decel (−50 m/s²) | C6 S4 FAIL → C9 **repair** (rules), not explore |
| K3=unknown feature | C6 S6 preflight FAIL → C9 repair; C10 records E10 class |
| User-explicit lane change | C2/C9 must not rewrite (C2-Q3, C9-Q6) |

---

## Comparison summary

| Aspect | E01 | E02 |
| --- | --- | --- |
| CX passes | 1 | 1 nominal + up to 5 explore |
| HITL | No | Yes (decel rate) |
| C6 S6 preflight | No | No |
| C7 runs | 1 | 1 + up to 5 |
| C9 | Idle | Explore (param search) |
| Primary C8 metrics | Gap stability | TTC + PET, trigger fired |
| C10 records | Single lineage chain | Branching lineage tree |

---

## Suggested next dry runs

| ID | Purpose |
| --- | --- |
| E08 | C6 S3 FAIL (invalid lane) → C9 repair, no C7 |
| E09 | Unreachable trigger (S5 skipped; detect at C7/C8) |
| E10 | K3=unknown → C6 S6 preflight → E10 classification |

---

## Document history

| Date | Change |
| --- | --- |
| 2026-08-22 | Initial capture of E01 and E02 conceptual dry runs from architecture walkthrough |
