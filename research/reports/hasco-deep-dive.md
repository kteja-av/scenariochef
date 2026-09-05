# HASCO deep dive — "HASCO: A Hybrid AI Simulation Compiler for Semantic Accident Reconstruction"

Researched 2026-09-05. Method: web_search + `curl -sL` verification of every cited URL
(HTTP status recorded per link); the full paper was downloaded and read end-to-end
(DROPS PDF, 22 pp., OASIcs vol. 143, AEiC 2026). No existing project files were modified.

---

## 0. Identity resolution — read this first

**The task brief attributed HASCO to JHU authors ("Baek-Hyun Cho, Seongjin Choi, Sohee
Lee"). That attribution is wrong, verified against the paper itself and three
bibliographic databases:**

- The actual paper: **Edin Jelačić, Rong Gu, Cristina Seceleanu, Ning Xiong, Peter
  Backeman, Tiberiu Seceleanu (Mälardalen University, Sweden + Prover Technology AB),
  Zhennan Fei, Ali Nouri (Volvo Cars + Chalmers), "HASCO: A Hybrid AI Simulation Compiler
  for Semantic Accident Reconstruction", OASIcs vol. 143, 30th Ada-Europe International
  Conference on Reliable Software Technologies (AEiC 2026), Article 4, pp. 4:1–4:22,
  DOI 10.4230/OASIcs.AEiC.2026.4** — authors' affiliations printed on page 1 of the PDF.
- **HASCO expands to "Hybrid AI Simulation COmpiler"** (paper abstract), not any
  hierarchical/adaptive acronym.
- Author verification via OpenAlex author search: a "Baek-Hyun Cho" exists but publishes
  automatic-transmission solenoid-valve papers (SAE, 1997–2002) and one 2006 nursing
  paper — no scenario-generation work. No arXiv author record at all
  (`au:"Baek Hyun Cho"` → 0 results). No Cho+Choi+Lee co-authored scenario paper exists
  on arXiv/Crossref/OpenAlex.
- ScenarioChef's own prior research note
  (`tmp/stale_docs/Automated Scenario Generation Research.md`) cited the same DROPS URL
  but hallucinated its title ("Driving Scene Synthesis", "JHU", "OASIcs 2026 vol 143"
  with wrong authors); the venue/volume were right, the title/authors were invented.
  This report corrects that record.

The paper is **not on arXiv** (DROPS + OpenAlex only; OpenAlex's record contains a
mislinked `oa_url` pointing at arXiv 2305.06018, which is actually the TARGET paper —
do not cite that arXiv ID for HASCO).

**Primary sources (all `curl -sL`-verified 2026-09-05):**

| Source | URL | Status |
| --- | --- | --- |
| Paper PDF (full text used) | https://drops.dagstuhl.de/storage/01oasics/oasics-vol143-aeic2026/OASIcs.AEiC.2026.4/OASIcs.AEiC.2026.4.pdf | 200 |
| Paper landing page (HTML abstract + links) | https://drops.dagstuhl.de/entities/document/10.4230/OASIcs.AEiC.2026.4 | 200 |
| Full-text HTML | https://drops.dagstuhl.de/storage/01oasics/oasics-vol143-aeic2026/html/OASIcs.AEiC.2026.4/OASIcs.AEiC.2026.4.html | 200 |
| DOI | https://doi.org/10.4230/OASIcs.AEiC.2026.4 | 200 (redirects to DROPS) |
| Volume TOC (OASIcs vol. 143) | https://drops.dagstuhl.de/entities/volume/OASIcs-volume-143 | 200 |

### Is any HASCO code public?

**No — status: not public as of 2026-09-05.** Searches performed (all negative):

- GitHub repository search: `HASCO scenario` (0), `HASCO OpenSCENARIO` (0),
  `HASCO in:name driving` (0), `"simulation compiler" openscenario` (0); the generic
  `HASCO` result set (197 repos) is all unrelated (ontology API, soundboard, hardware
  firm). Zenodo: no record. DiVA portal: unreachable from this machine (000).
- First author's GitHub (`github.com/jelacicedin`, 30 repos) — closest artifact is
  `jelacicedin/osi-ontology-observer` ("simulator-agnostic event detection and scoring
  toolkit for OpenSCENARIO"), Python, last pushed 2025-10-19 — related tooling but
  **not** HASCO itself; no repo is named or described as HASCO.
- The paper contains **no code/artifact-availability statement** — only funding
  acknowledgements (Swedish Knowledge Foundation "PerFlex", TSS-INSID) and tool credits.
- Author's publications page (`https://jelacicedin.github.io/publications/`, 200)
  lists the paper with note **"In preparation"** in the BibTeX and carries no code link.

Treat HASCO as **ideas-only adoptable** (same status already assumed in
`research/reports/competitor-comparison.md`). A partial-but-verified public codebase for
the *same problem class* (accident report → executable scenario) that surfaced during the
code hunt: `Francis-Shao/SCRIBE` ("From Accident Reports to Executable Scenarios:
Scenario-Level Consistent Reconstruction via Multi-Level Abstraction"), repo live
(200) — candidate for a future sibling report.

---

## 1. Pipeline stages and data flow

HASCO is a CLI toolchain that translates **unstructured forensic accident reports**
(police records, news articles, legal blogs; 8 languages) into executable
**esmini/OpenSCENARIO** artifacts (`.xosc` + `.xodr` + vehicle catalog). Framing: a
*semantic compiler* — "the LLM acts as a parser that extracts high-level logic, while the
deterministic pipeline handles the 'assembly code' generation of the XML." It is a
Human-in-the-Loop *co-generation* tool (code co-generation paradigm, Nouri et al.
arXiv:2505.19658), not an autonomous generator. Everything is run with OpenAI
`gpt-5-mini`, claimed model-agnostic.

Four synchronized pipelines (paper §4):

### 1.1 Geospatial pipeline (static world generation)

```
report text ──LLM location extraction──▶ Nominatim query string (exactly one line)
   ──▶ Nominatim API geocoordinates ──▶ OSM download for bounding box
   ──▶ dockerized CARLA conversion script ──▶ .xodr OpenDRIVE map
   ──▶ map "summary" text (for later prompt injection)
```

The location-extraction LLM prompt is published verbatim (Appendix, Listing 5):
"Return EXACTLY one line of text… include the most specific intersection or segment…
No coordinates, no postal codes… If you cannot identify a plausible location, return an
empty string." Geocoding failures account for most Mode-2/3 residual failures.

### 1.2 Vehicle extraction module (actor dimensioning)

Parses vehicle descriptions ("2015 Volvo V60", "small silver hatchback"), queries a
**Wikipedia-based knowledge base** for real physical dimensions (length, width,
wheelbase); vague descriptions fall back to the nearest real-world vehicle class. Output:
an **OpenSCENARIO vehicle catalog** injected into the combined prompt. Purpose: ground
collision physics in realistic bounding boxes; per-scenario dynamic resolution instead of
a static lookup table.

### 1.3 Semantic pipeline (dynamic scenario synthesis) — the RAG module

A hybrid RAG module grounds LLM output. **Corpus composition (exactly three sources,
paper §4.3):**

1. The **ASAM OpenSCENARIO standard (v1.x) schema definitions**;
2. The **esmini documentation and validator rules**;
3. The **complete `scenariogeneration` Python library repository** (the same
   pyoscx/scenariogeneration package C5 is built on).

**Retrieval mechanics:** a **re-ranking mechanism** filters retrieved snippets to
prioritize pertinent API calls (example given: specific `ManeuverGroup` classes); the
filtered snippets are injected into the system prompt inside a delimited
`### Reference docs … ### End docs` section, and prompts declare those snippets
**authoritative** ("treat those snippets as authoritative and prefer those APIs"). So the
retrieval key is essentially *task/feature-relevant API documentation* — not retrieval of
prior scenarios. The published system prompts (all three modes) are reproduced in full in
Appendix A of the paper (Listings 1–5).

### 1.4 Multi-strategy synthesis — three compilation paths (§4.4)

A unified prompt routes into one of three strategies; all paths converge at the Judge.

**Mode 1 — Direct XOSC synthesis.** LLM emits raw `.xosc` XML → immediately run in
esmini headless → parse/runtime errors fed back to the LLM for self-correction.
Published prompt (Listing 2) demands: exactly one XML document, catalog paths used
verbatim, full Storyboard (Init → Story → Act → ManeuverGroup → Event with
StartTrigger/StopTrigger), deterministic actions (`SpeedAction`, `LaneChangeAction`,
`CollisionCondition`), coordinates grounded in the provided map, "never invent roadId=0",
traffic-side lane polarity, every actor stopped at the end, simulation-wide StopTrigger.
**Result: catastrophic — 5% executability** (§5.1); rare Mode-1 survivors render as
static environments with no dynamic content, so the paper discards the entire Mode-1
corpus (Bin 0).

**Mode 2 — Python-programmatic synthesis.** LLM emits a Python script against the
`scenariogeneration` library — the script *is* the IR — executed in a **sandboxed
environment**; interpreter tracebacks (`AttributeError` etc.) are returned to the LLM to
repair API usage. The published prompt (Listing 3) is rich with project-relevant
micro-rules: load the map path from the prompt (`xosc.RoadNetwork(roadfile=...)`), never
build a road graph; register the catalog directory verbatim
(`scenario.add_catalog("VehicleCatalog", ...)`); every actor modeled (3+ if stated);
**"If the report indicates a crash/collision/impact, YOU MUST choreograph a deterministic
impact"** — approach → impact (RelativeDistance trigger ≤ 0.5 m or CollisionCondition) →
aftermath (stop/park both entities) — geometry matched to crash type (head-on = opposing
headings, rear-end = faster follower same lane, side = perpendicular approaches);
Position objects, never tuples/strings; `xosc.Rule` enums not strings; no subclassing
`ScenarioGenerator`; API markers in comments. **Result: 80% → 90% executability with the
Judge** (§5.1).

**Mode 3 — Ontology-driven synthesis (the best one).** A semantic intermediate layer
adapted from Bogdoll et al.'s AD ontology (arXiv:2209.00342 — verified 200), distilled
into a **lightweight JSON-LD profile** with core classes `Actor`, `Event`, `StartPose`.
Generation → **SHACL validation** → compilation:

```
report + map summary ──LLM──▶ JSON-LD instance (actors, assets, start poses, events)
   ──▶ SHACL validation against shapes.ttl (logical consistency:
        every actor referenced in an Event exists in the actor list, etc.)
        ├─ violations ──▶ injected verbatim into next prompt ──▶ regenerate
        └─ pass ──▶ deterministic "heuristic translation layer" ──▶ .xosc
```

The system prompt (Listing 1) shows the JSON-LD contract: every actor gets a unique
`hasco:` identifier, a concrete ontology class (Vehicle/Pedestrian/Bicycle…), a catalog
asset, and a `startPose` with `headingDeg`/`speedMps`; every Event carries
`subject, target, timeSec, xodrRoadId/laneId/s` and a prose `eventSummary`; "Never invent
roadId=0 or omit lane polarity"; "if uncertain, pick the most defensible option and
explain the assumption briefly in eventSummary" — i.e., **imputation with recorded
assumptions**. **Result: 92.5% → 95% executability** (§5.1).

**The heuristic translation layer (deterministic JSON-LD → XOSC compiler, §4.5)** — the
heart of the paper and the most adoptable mechanic:

- Parses each actor's sequence of `Event` nodes; reconstructs a **continuous polyline
  trajectory from sparse keyframes** (`StartPose` at t₀ + event timestamps tₙ) — the LLM
  never outputs frame-by-frame coordinates.
- **Lane-change inference**: regex-matches `laneId` tokens in event summaries; the
  compiler **automatically injects intermediate waypoints** to smooth the lateral
  transition (kinematic feasibility without LLM vector math).
- **Keyword-based trigger classifier**: "stop"/"stationary"/"halt" → `SpeedAction`
  target 0.0; "collision"/"impact"/"rear-end" (minus disqualifiers like "near-miss") →
  treated as stop triggers.
- Emits the synchronized `ConditionGroup`/`SimulationTimeCondition` blocks itself —
  "effectively functioning as a 'type system' for physical interactions."

### 1.5 The forensic Judge (validation loop, §4.6) — esmini execution feedback

Two stages, explicitly ordered ("unlike fire-and-forget generators"):

1. **Syntax and runtime repair first**: attempt to compile the artifact (Python or
   ontology) into `.xosc`; on runtime exception or static-guardrail violation (invalid
   enums), feed the **error trace** back to the synthesis model for repair — recover from
   brittle syntax errors before they cascade.
2. **Semantic and functional alignment second**: parse the valid `.xosc` into a
   **structured event log** (e.g., "Actor A: ChangeLane at t = 5s"); a **Judge LLM**
   compares the log against the original police report. Crucially it targets **silent
   failures**: code that runs but is inert (actors spawn and never move; "scenario
   duration is 0s"). The Judge returns a natural-language critique ("The simulation is
   inert; the report describes a collision, but no trigger was activated") that acts as a
   semantic constraint for the next synthesis iteration. The Judge prompt (Listing 4)
   constrains it to: compare report + map context to candidate scene; reply "OK",
   critique text, corrected JSON-LD, or revised XML per instructions; **never emit Python
   code**; concise, factual, actionable feedback.

A worked German-language cyclist–truck end-to-end example (Appendix B, Table 3, Fig. 10)
shows all six configurations side by side, including the Ontology+Judge Bin-3
reconstruction and the generated OpenDRIVE map.

---

## 2. Handling invalid LLM output

No constrained decoding in the shipped system (it is named only as a possible future fix,
§5.2 Bin-0 discussion: "This may be potentially fixed by enforcing constrained decoding
(grammar-based sampling)"). Instead: **architecture + feedback loops**:

| Mechanism | Where | Detail |
| --- | --- | --- |
| Don't let the LLM produce XML at all | Modes 2/3 | LLM emits Python or a JSON-LD graph; the deterministic layer owns XML. This is *the* fix: 5% → 90–95% executability. |
| Sandbox + traceback repair | Mode 2 | Script executed sandboxed; Python exceptions returned to LLM to fix API usage. |
| esmini headless + error-log repair | Mode 1 | esmini parse errors (e.g., missing parameter definitions) fed back verbatim. |
| **SHACL schema-validation loop** | Mode 3 | JSON-LD validated against `shapes.ttl`; **specific violations injected into the next prompt**; compilation only on pass. Deterministic pre-XML gate — prevents actor-hallucination that slipped through in Mode 2 (Appendix B: Python mode invented a delivery van absent from the report; SHACL constrained the admissible actor set and prevented it). |
| Judge, stage 1 | all modes | Compile/run first; error traces fed back before semantic review. |
| Judge, stage 2 | all modes | Event-log vs report comparison; catches *silent failures* (valid-but-inert runs); critique injected as semantic constraint on next iteration. |
| Catalog grounding | prompts | Hallucinated catalog paths are prevented by injecting available asset paths and catalog entry names into the prompt context (proposed fix §5.2; already implemented in Listings 1–3: "Reference catalog entries exactly; do not fabricate new vehicle definitions"). |

The paper's own **failure-mode catalogue** (§5.2, Bin 0) is directly reusable as a
taxonomy: (a) *structural malformation* — truncated/broken XML from context limits
("Couldn't find OpenSCENARIO element"); (b) *asset hallucination* — fabricated catalog
paths ("Couldn't locate catalog file: VehicleCatalog"); (c) *simulator incompatibility* —
standard-valid but unsupported by the target simulator ("Exception: Unsupported
condition: SimulationTimeCondition" — i.e., the standard-vs-esmini support gap
ScenarioChef encodes as E10/K3=unknown); (d) *convergence failure* — retry budget
exhausted; proposed remedy: decompose into smaller modular generation steps.

Cost note (§5.3): the Judge costs ≈2.5× tokens and ≈3× latency (avg 180 s vs 60 s per
run) for modest executability gains — their recommendation: run the cheap path by
default and **reserve the Judge for scenarios that execute but stay semantically inert**.

---

## 3. Evaluation methodology

- **Dataset**: N = 40 unstructured accident reports scraped from open-web sources (news,
  legal blogs, public police logs) — deliberately not curated corpora like NMVCCS —
  curated to maximize entropy: **8 languages** (English, German, Swedish, Dutch, French,
  Japanese, Spanish, Bosnian) and **information sparsity** from "hyper-detailed legal
  texts" down to "a car hit a pedestrian near the station", forcing imputation.
- **Metric 1 — Executability** (binary pass/fail at esmini): Direct 5% → 7.5% with
  Judge (+2.5); Python 80% → 90% (+10); Ontology 92.5% → 95% (+2.5). Residual 5%
  Ontology failures were geocoding-infrastructure, not generation logic. Judge impact
  largest on Python (+10 pts) because it catches silent failures/empty outputs.
- **Metric 2 — Semantic fidelity, a 4-bin rubric (0–3)** graded by intervention
  required: **Bin 0** syntax failure (split: infrastructure vs generative failures — the
  failure-mode catalogue above); **Bin 1** semantic failure (executes but the causal
  event is missing/wrong — "T-bone at intersection" simulated as two cars passing);
  **Bin 2** draft quality (correct core event, kinematic artifacts or asset mismatches —
  "teleports"/jerky movement, wrong vehicle class; needs human polishing); **Bin 3**
  production quality (semantically faithful, kinematically smooth, one-shot usable).
  Aggregate quality score `S_avg = Σ wᵢnᵢ` with weights {0,1,2,3}. With Judge, Python
  mode: 62.5% acceptable (Draft+Production), a 300% relative increase in Production;
  Ontology+Judge: 57.5% acceptable, semantic failures −36.3%.
- **Metric 3 — Cost-benefit**: token consumption vs quality/executability per mode;
  conclusion: Mode-3-no-Judge is the most cost-effective default, Judge reserved for hard
  cases.
- **Honest threats-to-validity section (§6)**: rubric + Judge subjectivity; Judge can
  hallucinate "OK" or miss kinematic errors; single model (`gpt-5-mini`), temperature not
  configurable, single-run; imputation vs accuracy trade-off — outputs are "representative
  edge cases rather than exact digital twins"; external-dependency fragility (Nominatim
  timeouts, OSM lane-level gaps) — most Mode-2/3 errors are external failures.
- **Explicitly out**: TTC/PET-style deterministic safety metrics (named as future work
  together with constraint-based motion planning). Two cross-cutting eval insights: high
  executability ≠ forensic accuracy (RQ2), and their own worked example shows the Judge
  missing an actor hallucination that was "internally consistent".

---

## 4. What an open implementation (ScenarioChef) should adopt — mapped to C1–C10

ScenarioChef equivalents (from `component_inventory.md`, `docs/checkpoint.md`, and
source): C2 = slot-filling LLM proposer behind a pydantic schema gate
(`c2_understanding/runtime.py`, `build_prompt`/`SpaceXAIProposer`/`null_proposer`); C3 =
typed knowledge graph + esmini K3 capability matrix (`c3_knowledge`), deliberately not
passive-RAG-as-truth (C3-Q1); C4 = ScenarioIR (Scenic-like DSL, ranges, frame tags); C5 =
deterministic `scenariogeneration` compiler (`c5_generation`); C6 = S1–S6 validation
funnel with XSD/semantic/map/bounds stages + esmini dry-run on K3=unknown
(`c6_validation/runtime.py`); C7 = esmini runner with `--csv_logger`, `--path`,
hang detection, `stderr_tail` on `RunRecord` (`c7_esmini/runtime.py`); C9 = deterministic
repair + explore + simulator-repair with `MAX_ITERATIONS=5` and an esmini
stdout/stderr signature table (`c9_feedback/runtime.py`); C8 = TTC/PET/collision from CSV.

Priorities marked ★ are the highest leverage per unit of work.

| # | HASCO mechanic (concrete) | ScenarioChef mapping | Action + status |
| --- | --- | --- | --- |
| 1 ★ | **SHACL-style deterministic semantic gate on the LLM's structured output, with specific violations injected into the next prompt** (not generic "invalid JSON, retry") | **C2** schema gate + **C9** repair | ScenarioChef already rejects invalid proposals at the pydantic gate; adopt HASCO's loop shape: return the *specific* violated constraints (which actor, which slot, which rule) into the retry prompt instead of re-sending the schema. Cheap, high convergence value. **Open.** |
| 2 ★ | **Compile-time guardrails embedded in the proposer prompt**: catalog paths + enumerated valid entry names injected verbatim; "reference entries exactly; do not fabricate"; "never invent roadId=0"; lane polarity per traffic side; "omit the slot if unknown — do not guess" | **C2 `build_prompt`** | C2's prompt already constrains lanes/speeds/actions but does **not inject the actual catalog entry names or map ids/road ids available** — the exact defect HASCO catalogs as "asset hallucination". Inject the real `VehicleCatalog.xosc`/`PedestrianCatalog.xosc` entry names + C3 map ids into the prompt. **Open.** |
| 3 ★ | **Deterministic keyframe→trajectory + keyword→trigger translation layer**: LLM supplies sparse events (subject, target, timeSec, roadId/laneId/s, speedMps, eventSummary); deterministic code builds polyline trajectories, injects lane-change waypoints, maps "stop/halt/stationary" → SpeedAction 0.0 and "collision/impact/rear-end" (minus "near-miss") → stop triggers; LLM never does vector math | **C4→C5** (extends the existing deterministic compiler) | This is HASCO's 95% executability source. ScenarioChef's C5 already compiles IR deterministically; adopt the *sparse event + imputed keyframes* input shape and the trigger keyword classifier as an offline fallback/intent normalizer. **Open.** |
| 4 ★ | **"Silent failure" detection: a run that executes but is inert (0 s duration, actors never move, no trigger fires) is a FAIL class** | **C8** + **C9** | ScenarioChef's C8 scores TTC/PET/collision but has no explicit "functionally void" classification (e.g., pet=∞ + no completion + zero movement ⇒ `SIMULATION_INERT`), and C9's simulator-repair currently treats clean-but-inert runs as "no feedback to apply" (`plan_simulator_repair` returns stop on "clean"). Add the inert signature → repair action. **Open.** |
| 5 | **Two-stage repair ordering: syntax/runtime repair before semantic review** | **C9** dispatch order | C9 already short-circuits on C6 FAIL before C8 metrics, so the ordering holds; document and enforce that no semantic critique is generated from an artifact that failed S1–S6. **Mostly done** — make it an explicit invariant/test. |
| 6 | **Event-log-vs-intent semantic comparison** ("Judge lite"): parse the executed scenario into a structured event log and diff against the IntentSpec's maneuvers/triggers, before any LLM judge | **C7→C8** (esmini CSV/state log) + **C4 IntentSpec** | A deterministic diff (which maneuvers fired, when, which triggers fired) would catch silent failures without an LLM; if a diff is inconclusive, route to HITL (CX already has the channel) rather than a Judge LLM — consistent with ARCH-0001 ("only C2 may import an LLM"). **Open.** |
| 7 | **Cost-tiered judge policy: run cheap validation by default; escalate expensive semantic review only for "executes but semantically suspect" cases** (their data: Judge ≈ 2.5× tokens, 3× latency, +2.5–10 pts) | **CX** loop budget + **C6 S6** gating | Map to CX's existing 5-iteration / 5-minute budget: LLM-in-the-loop repair attempts only after deterministic repair exhausted, or only when C8 flags inert/suspect. **Open.** |
| 8 | **RAG corpus composition** (validated target for C3's planned retrieval lane): (a) OSC 1.x XSD/schema definitions, (b) esmini docs + validator rules, (c) full `scenariogeneration` repo — re-ranked to the API subset relevant to the request, injected in a fenced "authoritative" docs section | **C3 → C2 evidence** | `checkpoint.md` C3-Q1 already cites this ("HASCO RAG over XSD / esmini docs / scenariogeneration") and decided C3 = typed graph + capability matrix with docs as node evidence — i.e., these three corpora *hanging off C3 nodes* is the sanctioned shape, not a free vector DB. The re-rank-to-relevant-API mechanic is the adoptable bit when the retrieval lane is built. **Partially open (gap 3 in competitor-comparison.md).** |
| 9 | **Failure-mode taxonomy** (structural malformation / asset hallucination / simulator incompatibility / convergence failure) | **C6 `ErrorTaxonomy`** + **C9 signature table** | Direct correspondence: C6's `XSD_INVALID`≈(a), `SEMANTIC_REF`≈(b) partly, `RUNTIME_COMPAT`≈(c) — add *asset hallucination* (catalog/asset reference not resolvable) as a named class if not covered, and *convergence failure* (loop budget exhausted) as a CX-level status. **Partially open.** |
| 10 | **Imputation-with-recorded-assumption prompts**: "if uncertain, pick the most defensible option and explain the assumption in the event summary" + imputation honesty in threats-to-validity | **C2 provenance** (already partially built) | C2's provenance system (`user_explicit`/`llm_proposed`/`c3_default`, `unknowns[]`) already encodes the same discipline more rigorously than HASCO's prose eventSummary — no change needed; use HASCO §6 as citable evidence for why imputed slots must stay marked. **Done by design** — keep it. |
| 11 | **Multi-lingual, sparsity-maximizing eval corpus + intervention-graded rubric** (bins 0–3, `S_avg` weighted score) + threats section | **C8 rulebook** + repo eval harness | Adopt the rubric shape for ScenarioChef's E01–E10 discovery-suite reporting: deterministic metrics (C8) for executability/objectives, human/LLM-lite bins for narrative fidelity if NL inputs grow. The 8-language stress test is cheap insurance for C1/C2 parsing. **Open (eval harness, not component code).** |
| 12 | **Map/context grounding of geospatial claims** (map "summarized" to text for the prompt; roads/lane polarity asserted from the real map, never invented) | **C3 map nodes → C2 prompt → C5** | ScenarioChef already hit this bug class (CX-0004: hardcoded `roadId=0` vs real road id 1; C2 now defaults `DEFAULT_ROAD_ID=1`). HASCO's generalization: derive the *entire* spatial context block (road ids, lane ids, junctions) from the actual map asset summary, never from LLM memory. **Partially closed; generalize.** |

**Not worth adopting:** Mode-1 direct-XML synthesis (empirically dead: 95% failure —
validates ScenarioChef's deterministic-C5 architecture); Wikipedia-based per-scenario
vehicle dimension lookup (nice for forensic bounding-box fidelity, out of Phase-1 scope;
catalogs suffice); Nominatim/OSM geospatial pipeline (Phase-1 pins `straight_2lane` +
mirrored esmini maps; revisit only if crash-report inputs become in-scope — note C1's
"crash narratives" modality makes this a plausible Phase-2 story).

**Framing takeaway (RQ2):** executability ≠ fidelity. ScenarioChef's C6–C8 funnel proves
executability and objective metrics, but a scenario can pass everything and still not be
what the user asked — the deterministic event-log diff (item 6) is the cheapest answer to
the gap HASCO demonstrates with a full Judge.

---

## 5. Public code status — detailed

- **HASCO itself: no public code found** (GitHub/Zenodo/project page all negative; no
  artifact statement in the paper; author's site lists it "In preparation"). Status:
  **not public as of 2026-09-05** — recheck `jelacicedin`'s GitHub periodically.
- Related-but-not-HASCO, verified live: `jelacicedin/osi-ontology-observer` (author's own
  OpenSCENARIO event-detection/scoring toolkit — could serve ScenarioChef's C8-style
  event-log extraction experiments) and `Francis-Shao/SCRIBE` (accident-report →
  executable scenario, same problem class, public demo repo).

## 6. URL verification log (all checked 2026-09-05 with `curl -sL`)

| URL | Status | Note |
| --- | --- | --- |
| DROPS PDF (`…/OASIcs.AEiC.2026.4.pdf`) | 200 | Full text read |
| DROPS landing (`/entities/document/10.4230/OASIcs.AEiC.2026.4`) | 200 | |
| DROPS full-text HTML (`…/html/OASIcs.AEiC.2026.4.html`) | 200 | |
| DOI `10.4230/OASIcs.AEiC.2026.4` | 200 | → DROPS |
| DROPS volume `OASIcs-volume-143` | 200 | |
| `jelacicedin.github.io` (+ `/publications/`) | 200 | "In preparation", no code link |
| `github.com/jelacicedin/osi-ontology-observer` | 200 (API) | not HASCO |
| `github.com/Francis-Shao/SCRIBE` | 200 (API) | related work, public code |
| `arxiv.org/abs/2505.19658` (Nouri, code co-generation) | 200 | |
| `arxiv.org/abs/2209.00342` (Bogdoll et al., ontology) | 200 | |
| `arxiv.org/abs/2305.06018` (TARGET) | 200 | ⚠️ OpenAlex mislinks this as HASCO's OA PDF — it is not |
| `arxiv.org/abs/2405.03709` (ScenicNL) | 200 | |
| `arxiv.org/abs/2509.02150` (Txt2Sce) | 200 | |
| `arxiv.org/abs/2502.02145` (Guo et al., words-to-collisions) | 200 | |
| `arxiv.org/abs/1801.08598` (Menzel et al., scenario levels) | 200 | |
| `github.com/esmini/esmini`, `github.com/pyoscx/scenariogeneration` | 200 | |
| `w3.org/TR/shacl/` | 200 | |
| `dl.acm.org/doi/10.1145/3691620.3695037` (SoVAR) | 403 | bot-blocked; **unverified** |
| `nhtsa.gov/…/national-motor-vehicle-crash-cause-survey` (NMVCCS) | 403 | bot-blocked; **unverified** |
| `drops.dagstuhl.de/volumes/2026/143/` | 403 | superseded by `/entities/volume/OASIcs-volume-143` (200) |
| `github.com/carla-simulator/opendrive-converter` | 404 | dead/never existed; the paper's "dockerized CARLA conversion script" has no citable public URL — **unverified** |
| DiVA portal query | 000 | unreachable from this machine — **unverified** |
| AEiC 2026 programme page | 000 | unreachable from this machine — **unverified** |

Search footprint (negative results): arXiv API (`all:"HASCO"`, `ti:"HASCO"`,
`au:"Baek Hyun Cho"`, co-author pairs → 0 scenario hits); Crossref (no Cho/Choi/Lee
scenario paper); OpenAlex (HASCO → the two unrelated 2021/2023 namesakes; author records
show the JHU attribution is unsupportable); GitHub repo search (0 relevant); Zenodo API
(0); DDG/Mojeek/Brave HTML scrapes (no HASCO-code signal; Brave surfaced only
esmini-ecosystem links and an unrelated hasco.com thermo-simulation page).
