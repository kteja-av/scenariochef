# Elicit Research CSV → ScenarioChef Mapping

**Source:** `Elicit - Deep research paper collection automated scenario generation for ADASAD testing.csv` (45 papers, 2017–2025)
**Purpose:** Identify what already exists in the market (GitHub repos / published methods) that can be added to ScenarioChef to make it more robust, and define the next steps.
**Constraint honored:** ARCH-0001 — C2 stays the only LLM agent; C1–C10 + CX remain deterministic. Every suggestion below respects the frozen architecture unless explicitly flagged as an ADR-level decision.

---

## 1. What the CSV contains (complete inventory)

Method families represented across the 45 papers:

| Family | Papers (row #) | Count |
| --- | --- | --- |
| Surveys / taxonomy / systematic reviews | 0, 1, 2, 3, 4, 39, 40, 41, 42, 43, 44 | 11 |
| Evolutionary / search-based / fuzzing | 8, 9, 10, 11, 12, 13, 14, 15, 16, 19, 20, 21 | 12 |
| Reinforcement-learning generation | 35, 36, 37, 38 | 4 |
| Data-driven / learned generation (traffic, diffusion) | 22, 23, 24, 25, 26, 27 | 6 |
| Corner-case / rare-event synthesis | 28, 29, 30, 31, 32, 33, 34 | 7 |
| Traffic-rule → test (LLM/DSL) | 5 | 1 |
| Constrained randomization / foundations | 17, 18 | 2 |
| RL scenario editing | 35 | (counted above) |

High-relevance rows: 40 of 45. Medium: rows 17, 43, 44.

Key public artifacts (GitHub/code where named in the papers):

| Work | What is public | ScenarioChef relevance |
| --- | --- | --- |
| TARGET (row 5) | Traffic-rule → DSL → executable tests framework | Direct precedent for C2's NL→IntentSpec slot-filling; validates the "schema is the gate" design |
| AdvSce (row 6) | Tool: dynamic parameter-range selection + perturbing participants | C9 explore currently uses a fixed schedule; AdvSce-style feedback-driven range widening is the upgrade path |
| scenoRITA (row 10) | Evolutionary obstacle mutation + multiple safety oracles + duplicate elimination | C8 oracle set + C9 diversity archive |
| AS-Fuzzer (row 8) | Road-structure-based scenario slicing + parallel co-evolution | Road-aware search space for C9 (map-structure-guided mutation) |
| Neural-guided evolutionary fuzzing (row 9, TreeSearchBench-style) | Grammar-valid scenario mutation + learned guidance | C9 mutation validity via C6 preflight; guidance later |
| Matrix-Fuzzer / behavior trees (row 15) | log2BT: abstract logged road users into behavior trees | C1 crash-narrative ingestion + C4 IR behaviors |
| LEADE (row 13) | LLM seeds initial scenarios for an otherwise deterministic multi-objective search | **Compatible with ARCH-0001**: LLM only at C2 boundary; the search stays deterministic in C9 |
| EvoScenario (row 14) | Road-structure-aware criticality search | Same insertion point as AS-Fuzzer (C9) |
| TrafficGen (row 23) / DeepMF (row 24) / CaDRE (row 25) | Learned realistic agent behavior models | Out of scope Phase 1 (CTG/diffusion excluded by checkpoint); revisit at ADR level |
| Scenario Dreamer (row 27) / Latent diffusion (row 26) | Vectorized latent diffusion scene generation | Out of scope Phase 1; matches the C5 ADR exclusion of diffusion |
| AutoScenario multimodal LLM (row 28) | Corner-case generation from multimodal data | Would violate single-LLM boundary if placed outside C2; note for Phase 2 |
| CC-SGG (row 30) | Scene-graph → corner-case transformation | Conceptually close to C3 knowledge graph + C9 mutation; the *learned* part is Phase 2 |
| Surveys (rows 0–4, 39–44) | Terminology (logical/scenario/concrete scenes), abstraction levels, SOTIF/ISO 21448 framing | Use to keep C3 `DomainRule` definitions aligned with PEGASUS/ASAM terms |

---

## 2. ScenarioChef coverage vs the market (gap analysis)

What ScenarioChef already has (validated, tested):

- NL + structured input → IntentSpec (C1/C2, schema-gated LLM) — matches TARGET's pattern.
- Knowledge/evidence service with provenance (C3) — matches "knowledge-based generation" family; deliberately static.
- Deterministic IR → OpenSCENARIO compiler (C4/C5) — matches the "template/rule-based" family of the taxonomy in row 0.
- Validation funnel with dry-run (C6), esmini execution (C7) — the "executable simulation scenario" output all surveyed works target.
- Metrics: TTC (paired PET), collision, completion (C8) — core safety oracles.
- Feedback loop: validation repair + parameter exploration with budget (C9) — a deterministic skeleton of the explore loop every search-based paper builds on.
- Orchestration + management (CX/C10).

Gaps vs the market, ranked by robustness value per unit of risk:

| # | Gap (market evidence) | ScenarioChef insertion point | Architecture risk |
| --- | --- | --- | --- |
| G1 | **Diversity / coverage of parameter space** — every search paper (scenoRITA, LEADE, AS-Fuzzer, AdvSce) sweeps more than one parameter and archives results to avoid duplicates. C9's `plan_explore` sweeps only the FIRST Range constraint (`_next_range_constraint` ignores `iteration`), and there is no archive of visited scenarios. | `c9_feedback/runtime.py` (round-robin/metric-guided constraint selection) + `c10_management` (visited-scenario archive keyed by semantic hash) | None — deterministic, inside C9/C10 contracts |
| G2 | **Minimum-distance oracle** — corner-case literature (rows 29–33) treats minimum inter-actor distance as a first-class criticality metric next to TTC/PET. C8 computes collision only at threshold 0.5 m. | `c8_evaluation/runtime.py` compute_metrics + `rulebook.yaml` + `MetricName` enum | Low — MetricName extension is backward compatible; rulebook gains a constant |
| G3 | **Duplicate elimination / scenario diversity archive** — scenoRITA explicitly removes duplicate tests; AS-Fuzzer maximizes diversity. C10 persists scenarios but nothing deduplicates semantically identical ones. | `c10_management/store.py` + `semantic_hash` (already exists in contracts) | None |
| G4 | **Criticality-aware stopping** — LEADE/AdvSce stop on criticality plateau; C9 already has `no_metric_gain` but it only checks a 0.1 s floor on TTC/PET, not relative improvement across iterations. | `c9_feedback/runtime.py` `_no_metric_gain` | Low |
| G5 | **Constrained randomization baseline** (row 18) — validity-constrained random sampling inside IR ranges is the cheapest diversity baseline and is fully deterministic with a seed. | C9 explore candidate function (seeded, uniform) as an alternative schedule | None |
| G6 | **Road-structure-aware mutation** (AS-Fuzzer, EvoScenario) — mutate within map-consistent structures (junctions, merges). Requires C3 lane topology, which is excluded by ARCH-0003. | Future ADR: read-only map topology source; do NOT write back to C3 | Needs ADR — defer |
| G7 | **LLM-seeded search (LEADE)** — LLM proposes diverse initial IRs, deterministic search refines. Compatible: C2 already is the LLM boundary. | C2 diversity prompts (multiple proposals per request) | Low, but touches LLM behavior — needs eval set first |
| G8 | **Behavior-tree scenario abstraction** (rows 15/16) — richer behavior composition for multi-agent interactions. | C4 IR behaviors | Phase 2 — IR schema change |
| G9 | **Learned traffic realism** (TrafficGen, DeepMF, CaDRE, diffusion rows) | Explicitly out of scope (checkpoint: CTG/TRACE/diffusion excluded) | Phase 2+ ADR |
| G10 | **Terminology/SOTIF alignment** (rows 39–44) — C3 `DomainRule` definitions vs PEGASUS/ISO 21448 terms. | C3 data files (pure data change) | None |

Deliberate non-goals (stay excluded, per frozen architecture): diffusion/learned scene generation (rows 26–27), multimodal LLM corner-case generation outside C2 (row 28), GAN corner synthesis (row 29), CARLA-specific work, lane-topology answers from C3.

---

## 3. Suggested approach (next steps, in order)

Wave R1 — deterministic robustness, no ADR needed (this session):
1. **G1 multi-parameter exploration** in C9: cycle Range constraints across iterations (round-robin keeps the existing single-constraint candidate schedule intact for iterations 0–2 of one constraint). Research: scenoRITA §mutation, LEADE §search space, AdvSce.
2. **G2 min-distance metric** in C8: new `MetricName.MIN_DIST`, computed from the same aligned frames as TTC/PET; rulebook constant `min_distance_warning_m` (default 2.0 m, SOTIF-style proximity warning) — reported, NOT auto-fail (thresholds come from the rulebook only).
3. **G4 plateau stop** in C9: `no_metric_gain` also triggers when relative improvement < 1% across an iteration (configurable constant), matching criticality-plateau stopping in the search literature.
4. Harness updates first: invariants/experiences recorded BEFORE the code lands (per the new harness-first policy), gate green after.

Wave R2 — persistence & dedupe (next session):
5. **G3/G5**: C10 visited-scenario archive keyed by `semantic_hash(ScenarioIR)`; C9 checks the archive before proposing a revised IR (skip duplicates). Seeded constrained-random candidate schedule as an explore option.

Wave R3 — ADR-level decisions (discuss, do not implement ad hoc):
6. **G6** map-topology-aware mutation source (read-only, separate from C3 static knowledge).
7. **G7** C2 multi-proposal diversity with a golden eval set before changing LLM behavior.
8. **G8** behavior-tree IR extension (schema version bump).

Wave R4 — data alignment (background):
9. **G10**: align C3 `DomainRule` definitions with the terminology survey (row 40) and SOTIF framing (row 44).

---

## 4. Per-paper one-line verdicts (complete CSV)

- R0 1001 Ways (survey): use as the taxonomy backbone for C3 `DomainRule` coverage audit.
- R1 Critical-scenario SLR (2021): problem/generation/assessment triad — C6/C8/C9 already cover assessment; generation diversity is G1.
- R2 Data-driven survey (2022): confirms C3-knowledge + deterministic core is the "knowledge-based" family; data-driven paths are Phase 2.
- R3 Review (2024): challenges list maps to G1–G4.
- R4 Automatic Scenario Generation for AD/ADAS (2023): Euro NCAP/JAMA test catalogs → candidate C3 catalog expansion (data, not code).
- R5 TARGET: strongest precedent for C2's schema-gated NL pipeline; keep as benchmark reference.
- R6 AdvSce: dynamic parameter-range challenge — inspires G1/G4.
- R7 DeepScenario: city-scale naturalistic+adversarial — Phase 2, needs naturalistic data.
- R8 AS-Fuzzer: slicing + parallel evolution → G6 (map slicing), R2 archive diversity.
- R9 NNEvoFuzz: grammar-valid mutation → C9 mutations must stay C6-valid (already enforced by pipeline order).
- R10 scenoRITA: multi-oracle + dedupe → G2/G3.
- R11 Closed-loop ADAS fuzzing: ADAS-specific oracle focus → G2 warning threshold fits ADAS proximity semantics.
- R12 ScenarioFuzz (Dance of the ADS): seed corpus from OpenDRIVE + history-informed mutation → R2 archive doubles as seed corpus.
- R13 LEADE: LLM seeds + deterministic multi-objective search → G7, architecture-compatible.
- R14 EvoScenario: road-structure integration → G6.
- R15 Matrix-Fuzzer: log2BT behavior abstraction → G8, also relevant to C1 crash narratives.
- R16 Evolutionary behavior trees: same as R15.
- R17 Event-based multi-event scenarios (2019, medium): sensor/device event composition — low priority.
- R18 Constrained randomization (2017): G5 baseline, cite when implementing.
- R19/R20 Diverse & challenging / adaptive generation (2017/2018): critical-transitions framing → supports G4 plateau stop.
- R21 Apollo/SVL pedestrian SBST: perception-focused; ScenarioChef is behavior-level — keep as reference only.
- R22 Edge cases from real-world data: data-to-parametric pipeline → Phase 2 with trajectory input (C1 already accepts trajectory data).
- R23 TrafficGen: learned traffic — Phase 2 exclusion stands.
- R24 DeepMF: closed-loop motion factorization — Phase 2.
- R25 CaDRE: controllable/diverse safety-critical from real trajectories — Phase 2, but its controllability knob idea supports G1.
- R26 Latent diffusion scenarios: excluded (checkpoint).
- R27 Scenario Dreamer: excluded (checkpoint).
- R28 AutoScenario (multimodal LLM): would break ARCH-0001 if added outside C2 — Phase 2 ADR.
- R29 Cycle-GAN corner synthesis: excluded (vision-level).
- R30 CC-SGG scene graphs: conceptual alignment with C3 graph; learned transform is Phase 2.
- R31 CornerSim perception virtualization: out of scope (perception-level).
- R32 Bounded-rationality rare events: interesting rare-behavior model for C9 candidate schedules later.
- R33 Corner case generation & analysis: decision-making-level corner cases → G2/G1 align.
- R34 Rare-event failure in LECs: retraining-loop idea → C9/C10 feedback data collection, Phase 2.
- R35 RL scenario editing: editing>generating fits C9 mutation model; RL itself excluded (deterministic C9).
- R36 (Re)2H2O: hybrid RL — excluded same reason.
- R37 BADRL critical boundary: bi-level adaptive RL — excluded; the "critical boundary" framing supports G4.
- R38 RL adversarial trajectories vs motion planners: excluded (RL); adversary-actor pattern could become a C4 behavior template later.
- R39 SBAF survey (2020): assessment framing — C8 rulebook provenance.
- R40 Fundamental considerations (2020): terminology/abstraction levels → G10.
- R41 Systematic mapping (2023): evidence map; use for future method selection.
- R42 Critical scenario techniques review (2023): cross-check of G1–G4.
- R43 Validation via OSC 2.0 + CARLA/IDM (2025, medium): OSC 2.0 note — Phase 1 is OSC 1.x via scenariogeneration; revisit at Phase 2.
- R44 Challenges & advances (2025, medium): standards framing (ISO 26262/21448/PEGASAS/OpenODC) → C3 DomainRule data enrichment.
