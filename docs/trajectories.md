Your current decomposition is **directionally correct**, but I would not freeze it yet.

The biggest issue is that the diagram currently mixes **capabilities, artifacts, execution stages, and control-loop functions** at the same level. For example, `Scenario Knowledge`, `Scenario Representation (IR)`, and `Scenario Management` are capability domains, while `esmini Simulation` is an execution capability and `Scenario / Map / Results / Logs` is primarily an artifact/data domain.

That distinction matters because otherwise you will eventually end up designing the architecture around boxes rather than around responsibilities.

Also, I don't see a separate dry-run output in what you provided—the image is the system abstraction itself. So I can identify gaps visible from this decomposition, but I cannot honestly claim that a particular gap was discovered from runtime evidence yet. The 10 experiments below should be used to generate that evidence.

---

# **1\. First: corrected Phase-1 capability model**

I would keep your **10 major areas**, but refine their internal meaning like this:

| \# | Component | Primary role | Nature |
| ----- | ----- | ----- | ----- |
| 1 | User Request / Requirements | Define intended scenario | Input / specification |
| 2 | Scenario Understanding | Convert natural-language intent into structured intent | Reasoning-heavy |
| 3 | Scenario Knowledge | Provide domain/standard/simulation knowledge | Knowledge |
| 4 | Scenario Representation / IR | Create canonical machine-readable scenario meaning | Deterministic \+ semantic |
| 5 | Scenario Generation | Construct candidate scenario | Mixed |
| 6 | Scenario Validation | Prove scenario is structurally/semantically executable | Mostly deterministic |
| 7 | esmini Simulation | Execute scenario | Deterministic execution |
| 8 | Observation & Evaluation | Extract and judge simulation behaviour | Mixed |
| 9 | Feedback & Improvement | Modify/search/retry based on evidence | Reasoning/optimization-heavy |
| 10 | Scenario Management | Persist, version, reproduce and organize artifacts | Mostly deterministic |

### **But there are two cross-cutting capabilities missing from the diagram:**

**A. Experiment / Execution Orchestration**

Something needs to coordinate:

> generate → validate → run → observe → evaluate → modify → rerun

This is currently implicit in your arrows.

**B. Provenance / Traceability**

You need to know:

> User request → interpretation → knowledge used → IR → generated `.xosc` → validation → esmini configuration → run → output → evaluation → feedback → next version.

Without this, debugging an automated generator becomes painful very quickly.

I would **not necessarily make either of these top-level boxes yet**. Treat them as cross-cutting capabilities during discovery.

---

# **2\. Component 1 — User Request / Scenario Requirements**

This is more than a text input box.

## **Sub-components**

### **1.1 Requirement ingestion**

Accept:

* natural language  
* structured scenario specification  
* parameterized scenario request  
* possibly an existing scenario to modify

### **1.2 Requirement normalization**

Convert:

> "Create a scenario where the ego follows another car and the car suddenly brakes."

into something conceptually like:

Scenario intent:  
  interaction \= following  
  lead\_vehicle \= vehicle  
  ego\_vehicle \= vehicle  
  event \= sudden\_braking  
  expected\_response \= ego\_reacts

### **1.3 Requirement constraints**

Capture:

* road type  
* number of actors  
* speed  
* relative distance  
* maneuver  
* trigger  
* duration  
* desired outcome  
* constraints  
* pass/fail criteria

### **1.4 Ambiguity detection**

Example:

> "Vehicle suddenly changes lane."

Questions:

* Which vehicle?  
* Which direction?  
* At what speed?  
* To which lane?  
* When?  
* Relative to ego?  
* Is collision expected or avoided?

This should not silently become arbitrary values.

---

## **Capabilities**

* requirement extraction  
* requirement normalization  
* ambiguity detection  
* missing-parameter detection  
* constraint extraction  
* intent classification  
* scenario objective extraction  
* acceptance-criteria extraction

### **Deterministic**

* schema validation  
* required-field checking  
* datatype checking  
* unit normalization  
* enum validation

### **Reasoning/intelligence**

* natural-language interpretation  
* ambiguity detection  
* intent extraction  
* inferred relationships

### **Agent potential**

**Medium.**

A requirement-understanding agent could be useful, but you don't need an "agent" just because LLM reasoning exists.

A good conceptual boundary is:

> **LLM/agent proposes structured intent → deterministic schema validates it.**

---

# **3\. Component 2 — Scenario Understanding**

This should be more sophisticated than simply parsing the request.

## **Sub-components**

### **2.1 Actor understanding**

Identify:

* ego  
* target vehicles  
* pedestrians  
* static objects  
* environment

### **2.2 Interaction understanding**

Examples:

* following  
* overtaking  
* merging  
* cut-in  
* crossing  
* collision  
* yielding  
* braking interaction

### **2.3 Temporal understanding**

Understand:

> "After the ego reaches 50 km/h, the lead vehicle brakes."

This becomes:

condition:  
    ego.speed \>= 50 km/h

then:  
    lead\_vehicle.brake

### **2.4 Spatial understanding**

Examples:

* same lane  
* adjacent lane  
* opposite direction  
* ahead  
* behind  
* intersection  
* crossing path

### **2.5 Behaviour understanding**

Convert:

> "lead car suddenly brakes"

into a semantic maneuver.

---

## **Important output**

Do **not** immediately generate OpenSCENARIO XML here.

Output a semantic scenario description:

Actors  
Relationships  
Initial conditions  
Road context  
Maneuvers  
Triggers  
Constraints  
Objective  
Evaluation criteria

That becomes the input to the IR.

---

# **4\. Component 3 — Scenario Knowledge**

This is one of the most important components in your whole system.

I would split it conceptually into **four knowledge domains**.

## **3.1 OpenSCENARIO knowledge**

Knowledge of:

* entities  
* vehicles  
* pedestrians  
* controllers  
* positions  
* trajectories  
* routes  
* actions  
* events  
* maneuvers  
* stories  
* triggers  
* conditions  
* parameters  
* catalogs

OpenSCENARIO catalogs are specifically designed for reuse of objects such as vehicles, controllers, pedestrians, trajectories, routes, environments and maneuvers. [Asam](https://www.asam.net/fileadmin/Standards/OpenSCENARIO/ASAM_OpenSCENARIO_BS-1-2_User-Guide_V1-2-0.html?utm_source=chatgpt.com)

## **3.2 OpenDRIVE knowledge**

Knowledge of:

* roads  
* lanes  
* lane sections  
* lane types  
* junctions  
* road geometry  
* lane connectivity  
* road coordinates  
* elevation  
* road markings

## **3.3 esmini capability knowledge**

This is particularly important.

Don't assume:

> "OpenSCENARIO supports X → esmini supports X."

Those are different questions.

esmini currently supports OpenSCENARIO XML 1.0–1.3, but explicitly notes that feature coverage is limited. [GitHub](https://github.com/esmini/esmini?utm_source=chatgpt.com)

esmini's ScenarioEngine parses the scenario, creates its internal representation of entities/triggers/actions and executes the scenario logic. Its RoadManager handles OpenDRIVE data. [Esmini](https://esmini.github.io/inner-workings.html?utm_source=chatgpt.com)

Therefore your knowledge base needs something like:

OpenSCENARIO capability  
        ↓  
esmini support status  
        ↓  
supported version  
        ↓  
known limitations  
        ↓  
workaround / alternative representation

That is a major implicit requirement.

## **3.4 Scenario-domain knowledge**

Examples:

* reasonable vehicle dimensions  
* acceleration ranges  
* braking ranges  
* lane-change duration  
* following distance  
* TTC  
* relative velocity  
* road geometry constraints

Some of these are facts; others are assumptions and should be explicitly marked as such.

---

# **5\. Component 4 — Scenario Representation / IR**

I strongly recommend keeping this component.

It is probably the **most important architectural decision in Phase 1**.

Do not make your IR simply:

> OpenSCENARIO XML represented as JSON.

That would give you very little benefit.

The IR should represent **scenario meaning**, independent of the final serialization.

For example:

Scenario  
 ├── Actors  
 ├── RoadContext  
 ├── InitialState  
 ├── Relationships  
 ├── Maneuvers  
 ├── Triggers  
 ├── Constraints  
 ├── EvaluationCriteria  
 └── Metadata

Then:

Natural language  
       ↓  
Semantic IR  
       ↓  
OpenSCENARIO generator  
       ↓  
.xosc

This gives you room later for another simulator without changing the understanding layer.

---

## **IR sub-capabilities**

* actor representation  
* road representation  
* initial-state representation  
* maneuver representation  
* trigger representation  
* parameter representation  
* temporal relationships  
* spatial relationships  
* evaluation criteria  
* provenance  
* scenario metadata

### **Deterministic**

Mostly.

### **Intelligence**

Mostly in **creating/updating** the IR, not in the IR itself.

### **Agent potential**

Low.

The IR should be deterministic and strongly typed.

---

# **6\. Component 5 — Scenario Generation**

This is where the semantic IR becomes an executable scenario.

## **Sub-components**

### **5.1 Actor generation**

* entity declarations  
* vehicle types  
* dimensions  
* controllers

### **5.2 Position generation**

Potential representations include:

* LanePosition  
* RoadPosition  
* WorldPosition  
* relative positioning

This is an important design choice. esmini explicitly supports OpenSCENARIO positioning mechanisms and provides road-relative positioning/interpolation behaviour. [Esmini](https://esmini.github.io/positioning.html?utm_source=chatgpt.com)

### **5.3 Maneuver generation**

Examples:

* accelerate  
* decelerate  
* follow  
* lane change  
* lateral movement  
* speed change  
* trajectory following

### **5.4 Trigger generation**

* simulation-time  
* distance  
* relative distance  
* speed  
* parameter conditions  
* entity conditions

### **5.5 Parameterization**

For example:

ego\_speed \= 15–25 m/s  
lead\_speed \= 10–20 m/s  
brake\_start \= 30–50 m

OpenSCENARIO parameters are particularly useful here because parameters can appear throughout the scenario and catalog references can override catalog defaults. [Asam](https://www.asam.net/fileadmin/Standards/OpenSCENARIO/QUICK_READ_ASAM_OpenSCENARIO_BS-1-2_User-Guide_V1-0-0.html?utm_source=chatgpt.com)

### **5.6 Catalog selection**

Rather than generating every object from scratch.

### **5.7 XML serialization**

Final conversion:

IR → OpenSCENARIO XML  
---

## **Agent potential**

**High, but only partially.**

A generation agent could:

* choose maneuver strategies  
* select candidate structures  
* propose parameters  
* repair generation failures

But XML construction itself should be deterministic.

---

# **7\. Component 6 — Scenario Validation**

I think your current box is **too broad**.

Split its capability conceptually into:

### **6.1 Structural validation**

* XML well-formedness  
* XSD/schema validation  
* required elements  
* datatype correctness

### **6.2 OpenSCENARIO semantic validation**

Examples:

* invalid references  
* invalid parameter usage  
* inconsistent entity references  
* invalid trigger/action relationships

This matters because XML validation alone does not catch everything. For example, ASAM notes that parameter type inference checking is not ensured by the XML validator and needs simulator-side handling. [Asam](https://www.asam.net/fileadmin/Standards/OpenSCENARIO/QUICK_READ_ASAM_OpenSCENARIO_BS-1-2_User-Guide_V1-0-0.html?utm_source=chatgpt.com)

### **6.3 OpenDRIVE compatibility validation**

Check:

* road exists  
* lane exists  
* lane direction valid  
* lane connection valid  
* position lies on road  
* junction reference valid

### **6.4 esmini compatibility validation**

This is crucial.

Example:

Scenario valid according to OpenSCENARIO  
                ↓  
        esmini-compatible?

Those are different validations.

### **6.5 Scenario sanity validation**

Examples:

* vehicle starts outside road  
* impossible speed  
* impossible maneuver  
* trigger can never activate  
* actors spawn on top of each other  
* lane change target doesn't exist

### **6.6 Runtime preflight**

Try loading the scenario before running the full experiment.

---

## **Validation should produce**

Not just:

PASS / FAIL

but:

VALID  
WARNING  
UNSUPPORTED  
SEMANTIC\_ERROR  
RUNTIME\_ERROR

with:

error  
location  
cause  
severity  
possible repair

This will become extremely important for your feedback loop.

---

# **8\. Component 7 — esmini Simulation**

This should be treated as the **execution engine**, not the intelligence layer.

Conceptually:

Validated .xosc  
      \+  
OpenDRIVE  
      \+  
runtime configuration  
      ↓  
    esmini  
      ↓  
simulation state  
      ↓  
ground truth / logs / traces / artifacts

esmini exposes ground-truth information through APIs and can save OSI traces or send OSI data over IP/UDP. [Esmini](https://esmini.github.io/inner-workings.html?utm_source=chatgpt.com)

## **Sub-capabilities**

* scenario loading  
* map loading  
* simulation initialization  
* stepping  
* execution control  
* runtime parameter handling  
* controller execution  
* state extraction  
* logging  
* OSI output  
* failure capture  
* termination detection

### **Deterministic**

Very high.

Given:

same scenario  
same map  
same configuration  
same simulator version  
same seed/settings

you want reproducible results.

### **Agent potential**

**No.**

Don't turn the simulator into an agent.

---

# **9\. Component 8 — Observation & Evaluation**

This is another component that needs to be split.

## **Observation**

Collect:

* actor positions  
* velocity  
* acceleration  
* heading  
* lane  
* relative distance  
* simulation time  
* trigger states  
* collisions  
* scenario termination state  
* runtime errors

## **Evaluation**

Convert observations into metrics.

Examples:

### **Safety**

* collision  
* TTC  
* minimum distance  
* time gap

### **Behaviour**

* lane-change completed  
* braking occurred  
* acceleration occurred  
* target reached  
* route followed

### **Scenario objective**

For:

> "lead vehicle brakes and ego responds"

evaluation might be:

lead\_brake\_detected \= true  
ego\_brake\_detected \= true  
collision \= false  
minimum\_distance \> threshold

### **Runtime evaluation**

* scenario completed  
* trigger activated  
* action executed  
* simulator crashed  
* entity disappeared  
* invalid state occurred

---

## **Agent potential**

Evaluation has two layers.

### **Deterministic evaluator**

Use this for measurable things.

collision \= false  
TTC \> 2 sec  
lane\_change\_completed \= true

### **Reasoning evaluator**

Potentially useful for:

> "Did the scenario behave according to the intended interaction?"

But I would **not make an LLM the primary evaluator** for Phase 1\.

---

# **10\. Component 9 — Feedback & Improvement**

This is where your architecture starts becoming genuinely interesting.

This shouldn't simply mean:

> "LLM looks at failure and generates another scenario."

There are several different improvement mechanisms.

## **9.1 Error-driven repair**

Example:

Validation:  
Target lane 3 does not exist.

        ↓

Repair:

Change target lane 3 → lane 2

This can be deterministic.

## **9.2 Parameter optimization**

Example:

minimum distance \= 12 m

target \= 5 m

modify:  
initial\_distance 30 → 20 m

Could use optimization/search.

## **9.3 Structural repair**

Example:

Trigger never fires

        ↓

change:  
simulationTime \> 10

to:

relativeDistance \< 20

This may require reasoning.

## **9.4 Scenario exploration**

Generate variations intentionally:

speed ∈ \[10, 15, 20\]  
distance ∈ \[10, 20, 30\]  
braking ∈ \[2, 4, 6\] m/s²

This is closer to experiment design/search than agentic repair.

---

## **Agent potential**

**Very high.**

This is one of the strongest candidates for an agent because it involves:

> observe → diagnose → propose modification → validate → execute → evaluate.

But don't make the agent responsible for everything.

---

# **11\. Component 10 — Scenario Management**

Your current name:

> Scenario / map / results / logs

is actually hiding several different responsibilities.

## **Scenario artifact management**

* scenario ID  
* versions  
* source  
* generated scenario  
* parent scenario  
* status

## **Map management**

* OpenDRIVE file  
* map version  
* compatibility  
* road metadata

## **Run management**

Each execution should record:

scenario version  
map version  
esmini version  
configuration  
parameters  
timestamp  
seed  
result

## **Result management**

* trajectories  
* metrics  
* evaluation  
* logs  
* OSI trace  
* errors

## **Provenance**

This is particularly important:

User request \#001  
       ↓  
Interpretation \#001  
       ↓  
IR \#001  
       ↓  
Generated scenario \#001  
       ↓  
Validation \#001  
       ↓  
Run \#001  
       ↓  
Evaluation \#001  
       ↓  
Repair \#001  
       ↓  
Scenario \#002

Without this lineage, your feedback loop will eventually become impossible to debug.

---

# **12\. Deterministic vs intelligence boundary**

This is the boundary I would use for Phase 1:

| Capability | Deterministic | Intelligence |
| ----- | ----- | ----- |
| XML parsing | ✓ |  |
| Schema validation | ✓ |  |
| Unit conversion | ✓ |  |
| IR schema | ✓ |  |
| XML generation | ✓ |  |
| Map lookup | ✓ |  |
| Trigger execution | ✓ |  |
| Simulation | ✓ |  |
| Metric calculation | ✓ |  |
| Artifact management | ✓ |  |
| Requirement interpretation |  | ✓ |
| Ambiguity resolution |  | ✓ |
| Scenario intent extraction |  | ✓ |
| Maneuver strategy selection |  | ✓ |
| Scenario repair |  | ✓ |
| Parameter exploration |  | ✓ |
| Open-ended scenario generation |  | ✓ |
| Behaviour explanation |  | ✓ |

This prevents the classic mistake:

> "We are building an agentic system, therefore every component should be an agent."

No.

Most of your system should be deterministic infrastructure. **Agents should sit around the deterministic machinery where decisions, interpretation, exploration, and repair are actually needed.**

---

# **13\. Agent candidates**

I would investigate these four first:

### **Agent 1 — Scenario Understanding Agent**

User request  
     ↓  
interpret  
     ↓  
structured intent

### **Agent 2 — Scenario Generation Agent**

Intent \+ knowledge  
       ↓  
candidate scenario

### **Agent 3 — Diagnosis / Repair Agent**

validation/runtime/evaluation failure  
              ↓  
          diagnose  
              ↓  
        repair proposal

### **Agent 4 — Exploration Agent**

previous experiments  
        ↓  
identify unexplored region  
        ↓  
generate next scenario

I would **not** create:

* Validation Agent  
* Simulation Agent  
* XML Writer Agent  
* Logging Agent

Those should remain deterministic services/capabilities.

---

# **14\. Known Knowns**

These are things you can reasonably put into your Phase-1 knowledge today.

### **Standards**

* OpenSCENARIO is the scenario description format.  
* OpenDRIVE provides road-network representation.  
* esmini is the simulation engine.  
* OpenSCENARIO has entities, actions, events, triggers, parameters, catalogs, trajectories, etc.  
* OpenSCENARIO supports reusable catalogs. [Asam](https://www.asam.net/fileadmin/Standards/OpenSCENARIO/ASAM_OpenSCENARIO_BS-1-2_User-Guide_V1-2-0.html?utm_source=chatgpt.com)  
* Parameters can be used across scenario elements and catalog references. [Asam](https://www.asam.net/fileadmin/Standards/OpenSCENARIO/QUICK_READ_ASAM_OpenSCENARIO_BS-1-2_User-Guide_V1-0-0.html?utm_source=chatgpt.com)  
* esmini has ScenarioEngine \+ RoadManager \+ controller mechanisms. [Esmini](https://esmini.github.io/inner-workings.html?utm_source=chatgpt.com)  
* esmini can expose ground truth and OSI traces. [Esmini](https://esmini.github.io/esmini-lib-programming.html?utm_source=chatgpt.com)

### **System**

You know you need:

requirement  
→ understanding  
→ representation  
→ generation  
→ validation  
→ simulation  
→ observation  
→ evaluation  
→ improvement

### **Experimentation**

You know you need to test:

* longitudinal interaction  
* following  
* braking  
* acceleration  
* lateral movement  
* crossing  
* triggers  
* runtime failures

---

# **15\. Known Unknowns**

These should become explicit research questions.

### **OpenSCENARIO**

1. Which OpenSCENARIO version will Phase 1 target?  
2. Which subset of OpenSCENARIO do you actually need?  
3. Are trajectories required or can most behaviours be expressed with actions?  
4. Which catalog types will be supported?  
5. Which trigger conditions will be supported initially?

### **esmini**

6. Which OpenSCENARIO features are actually supported by your chosen esmini version?  
7. Which supported features behave differently from the standard?  
8. What are known runtime limitations?  
9. What output format should become your canonical observation format?  
10. What constitutes a simulation failure?

### **IR**

11. How simulator-independent should the IR be?  
12. Should evaluation criteria exist inside the IR?  
13. Should uncertainty/confidence be represented?  
14. Should provenance be part of the IR or external metadata?

### **Generation**

15. Rule-based generation vs LLM generation?  
16. How much freedom does the generator get?  
17. How are invalid generated scenarios repaired?  
18. How are parameter ranges selected?

### **Evaluation**

19. Which metrics define success?  
20. Which metrics are generic vs scenario-specific?  
21. How do you determine that an intended maneuver actually occurred?

---

# **16\. Unknown Knowns**

This is where I think your current decomposition has the most hidden requirements.

These are things you probably **implicitly need because of the standards/simulation domain**, even though they aren't explicit boxes.

## **Unknown Known \#1 — Coordinate/position semantics**

A scenario generator cannot simply think:

> x \= 50, y \= 2\.

It needs to understand road-relative positioning.

esmini explicitly recommends road-relative positioning such as LanePosition/RoadPosition where appropriate because it makes scenarios more adaptable to road geometry. [Esmini](https://esmini.github.io/scenario-construction-tips.html?utm_source=chatgpt.com)

---

## **Unknown Known \#2 — Scenario validity ≠ simulator compatibility**

This is critical.

OpenSCENARIO-valid  
        ≠  
esmini-executable  
        ≠  
behaviourally-correct

You need three different notions of correctness.

---

## **Unknown Known \#3 — Trigger reachability**

A syntactically correct trigger can be logically unreachable.

Example:

Trigger:  
ego speed \> 100 m/s

Scenario:  
ego maximum speed \= 30 m/s

XML is valid.

Scenario is logically useless.

You need **trigger reachability analysis**.

---

## **Unknown Known \#4 — Actor initialization consistency**

You need to reason about:

position  
speed  
heading  
lane  
road  
dimensions  
controller

collectively.

---

## **Unknown Known \#5 — Temporal consistency**

Scenario generation isn't just spatial.

You need:

t0 → action → condition → action → termination

The system needs to understand temporal causality.

---

## **Unknown Known \#6 — Reproducibility**

A generated scenario isn't enough.

You need:

scenario  
\+ map  
\+ simulator version  
\+ parameters  
\+ configuration  
\+ seed

to reproduce an experiment.

---

## **Unknown Known \#7 — Failure taxonomy**

"Simulation failed" isn't enough.

You need to distinguish:

generation failure  
validation failure  
map compatibility failure  
load failure  
runtime failure  
trigger failure  
behaviour failure  
evaluation failure  
infrastructure failure

This will dramatically improve your feedback loop.

---

# **17\. Unknown Unknowns**

Don't try to invent these.

Instead, create experiments that expose them.

For example:

### **Question**

> What happens when a lane-change target disappears because the road geometry doesn't contain the requested lane?

Experiment.

### **Question**

> What does esmini do when a theoretically valid scenario uses a feature that isn't fully supported?

Experiment.

### **Question**

> What happens when a trigger is technically valid but never reachable?

Experiment.

### **Question**

> What happens when two actors are initialized in an invalid physical relationship?

Experiment.

### **Question**

> Does trajectory interpolation produce the behaviour we expected?

Experiment.

This is exactly where your **10 scenario dry runs** become valuable.

---

# **18\. The most important missing relationship in your diagram**

Your diagram currently looks approximately like:

Generation  
    ↓  
Validation  
    ↓  
Simulation  
    ↓  
Observation  
    ↓  
Feedback  
    ↘  
      Generation

That's good.

But you need to conceptually add:

                 ┌──────────────┐  
                  │ Knowledge    │  
                  └──────┬───────┘  
                         ↓  
Requirements → Understanding → IR → Generation  
                              ↑       ↓  
                              │   Validation  
                              │       ↓  
                              │   Simulation  
                              │       ↓  
                              │ Observation  
                              │       ↓  
                              └─ Feedback

And underneath everything:

             Experiment / Provenance  
                     ↓  
       scenarios \+ runs \+ results \+ logs

That is the part I would investigate next.

---

# **19\. Ten representative Phase-1 experiments**

These are intentionally **not ten variations of following**.

They cover different semantic, generation, trigger, validation and runtime behaviours.

---

## **Experiment 1 — Stable Following**

### **Scenario name**

**E01 — Constant-Speed Following**

### **Objective**

Test basic longitudinal interaction.

### **Actors**

* Ego vehicle  
* Lead vehicle

### **Initial conditions**

Ego: 15 m/s  
Lead: 15 m/s  
Initial gap: 30 m  
Same lane

### **Road/map assumptions**

Straight two-lane road, ego and lead in same lane.

### **Trajectory/maneuver**

Lead maintains constant speed.

Ego maintains following behaviour.

### **Trigger conditions**

No complex trigger initially.

Scenario starts immediately.

### **Parameters**

* ego speed \= 15 m/s  
* lead speed \= 15 m/s  
* gap \= 30 m  
* simulation duration \= 20 s

### **Expected behaviour**

Gap remains approximately stable.

### **Expected esmini output**

* both vehicles move along same lane  
* no collision  
* stable relative distance  
* continuous trajectory/log output

### **Tests**

**Scenario Understanding \+ IR \+ basic generation \+ simulation \+ observation**

### **Expected result**

**PASS**

---

# **20\. Experiment 2 — Lead Vehicle Braking**

### **Scenario name**

**E02 — Sudden Lead Braking**

### **Objective**

Test longitudinal interaction and triggered braking.

### **Actors**

* Ego  
* Lead vehicle

### **Initial conditions**

Ego \= 20 m/s  
Lead \= 20 m/s  
Gap \= 40 m

### **Road**

Straight road.

### **Maneuver**

Lead cruises initially.

Then performs strong deceleration.

Ego should encounter the resulting reduced headway.

### **Trigger**

simulation time \> 5 s

### **Parameters**

* lead braking \= \-5 m/s²  
* braking duration \= 3 s

### **Expected behaviour**

Lead slows rapidly.

Ego detects changing longitudinal relationship.

### **Expected output**

* lead velocity decreases  
* relative distance decreases  
* ego response observable  
* no unintended teleportation or trajectory discontinuity

### **Tests**

**Trigger generation \+ longitudinal action \+ evaluation**

### **Expected result**

**PASS**

---

# **21\. Experiment 3 — Ego Acceleration**

### **Scenario name**

**E03 — Ego Acceleration to Target Speed**

### **Objective**

Test speed-change generation.

### **Actors**

* Ego  
* Lead vehicle far ahead

### **Initial conditions**

Ego \= 5 m/s  
Lead \= 20 m/s  
Gap \= 100 m

### **Road**

Straight road.

### **Maneuver**

Ego accelerates from 5 → 20 m/s.

### **Trigger**

simulation time \> 2 s

### **Parameters**

* target speed \= 20 m/s  
* acceleration \= 2 m/s²

### **Expected behaviour**

Ego velocity increases smoothly.

### **Expected output**

Velocity curve should show acceleration toward target.

### **Tests**

**Parameterization \+ speed action \+ observation**

### **Expected result**

**PASS**

---

# **22\. Experiment 4 — Planned Lane Change**

### **Scenario name**

**E04 — Ego Lane Change**

### **Objective**

Test lateral maneuver generation.

### **Actors**

* Ego

### **Initial conditions**

Ego in lane 1  
Speed \= 15 m/s

### **Road**

Two-lane straight road.

### **Maneuver**

Lane 1 → Lane 2\.

### **Trigger**

simulation time \> 3 s

### **Parameters**

* target lane \= 2  
* lane-change duration \= 4 s

### **Expected behaviour**

Ego moves smoothly from lane 1 to lane 2\.

### **Expected output**

* lateral movement  
* final lane \= 2  
* no road departure

### **Tests**

**Lane semantics \+ lateral action \+ OpenDRIVE compatibility**

### **Expected result**

**PASS**

---

# **23\. Experiment 5 — Cut-In**

### **Scenario name**

**E05 — Target Vehicle Cut-In**

### **Objective**

Test multi-actor interaction.

### **Actors**

* Ego  
* Cut-in vehicle

### **Initial conditions**

Ego: lane 1, 20 m/s  
Target: lane 2, 20 m/s  
Target initially ahead

### **Road**

Two lanes, same direction.

### **Maneuver**

Target moves from lane 2 → lane 1 in front of ego.

### **Trigger**

relative distance \< 30 m

### **Parameters**

* cut-in distance  
* lateral transition duration  
* target speed

### **Expected behaviour**

Target enters ego's lane.

### **Expected output**

* target changes lane  
* relative distance decreases  
* ego/target interaction becomes measurable

### **Tests**

**Spatial relationship \+ trigger \+ multi-agent interaction**

### **Expected result**

**PASS**

---

# **24\. Experiment 6 — Crossing Interaction**

### **Scenario name**

**E06 — Pedestrian Crossing**

### **Objective**

Test non-vehicle actor and crossing interaction.

### **Actors**

* Ego vehicle  
* Pedestrian

### **Initial conditions**

Vehicle approaches crossing.

Pedestrian begins outside vehicle path.

### **Road**

Intersection/crossing environment.

### **Maneuver**

Pedestrian crosses the vehicle's path.

### **Trigger**

ego reaches defined distance from crossing

### **Parameters**

* pedestrian speed  
* crossing location  
* ego speed

### **Expected behaviour**

Pedestrian trajectory intersects the vehicle's projected path.

### **Expected output**

* pedestrian crosses  
* interaction becomes observable  
* collision metric can be evaluated

### **Tests**

**Actor diversity \+ crossing \+ evaluation**

### **Expected result**

**PASS**

---

# **25\. Experiment 7 — Trigger Chain**

### **Scenario name**

**E07 — Multi-Stage Triggered Behaviour**

### **Objective**

Test temporal dependency.

### **Actors**

* Ego  
* Lead

### **Road**

Straight road.

### **Behaviour**

t \> 3s  
    ↓  
Lead accelerates

then

relative distance \< 20m  
    ↓  
Ego accelerates

then

ego speed \> 20m/s  
    ↓  
Lead changes lane

### **Parameters**

Multiple thresholds.

### **Expected behaviour**

Events occur in the correct sequence.

### **Expected output**

The event timeline should be reconstructable from logs.

### **Tests**

**Trigger semantics \+ temporal reasoning \+ observation**

### **Expected result**

**PASS**

This is much more valuable than another simple trajectory because it tests your scenario **logic model**, not just motion.

---

# **26\. Experiment 8 — Boundary / Edge Condition**

### **Scenario name**

**E08 — Lane Boundary Request**

### **Objective**

Discover how the system behaves when generation requests a boundary condition.

### **Actors**

* Ego

### **Road**

Two-lane road.

### **Requested manoeuvre**

lane 2 → lane 3

when lane 3 does not exist.

### **Expected behaviour**

The generator/validator should reject the scenario **before normal simulation**.

### **Expected output**

Something like:

VALIDATION\_FAILURE

Reason:  
Target lane does not exist.

Category:  
OpenDRIVE compatibility

Severity:  
ERROR

### **Tests**

**IR validation \+ map reasoning \+ error classification**

### **Expected result**

**INTENTIONAL FAILURE**

This experiment is extremely important.

---

# **27\. Experiment 9 — Unreachable Trigger**

### **Scenario name**

**E09 — Impossible Trigger Condition**

### **Objective**

Test semantic validation rather than XML validity.

### **Actors**

* Ego

### **Initial condition**

ego maximum speed \= 20 m/s

### **Trigger**

ego speed \> 50 m/s

### **Maneuver**

Brake after trigger.

### **Expected behaviour**

The trigger should never activate.

### **What you want to discover**

Does your system identify:

valid XML  
\+  
valid OpenSCENARIO structure  
\+  
unreachable behaviour

?

### **Tests**

**Trigger reachability analysis**

### **Expected result**

**INTENTIONAL FAILURE / WARNING**

This is a very important missing capability if your validator currently only checks XML/schema.

---

# **28\. Experiment 10 — Runtime / Feature Compatibility Failure**

### **Scenario name**

**E10 — Unsupported or Runtime-Incompatible Scenario**

### **Objective**

Expose the difference between:

standards-valid

and:

esmini-executable

### **Scenario**

Construct a scenario using a carefully selected OpenSCENARIO feature that your target esmini version does not fully support or handles differently.

Do **not** randomly invent an unsupported feature. Select it from the actual esmini version/support matrix during the experiment.

esmini itself explicitly warns that although it supports OpenSCENARIO XML versions 1.0–1.3, feature coverage is limited. [GitHub](https://github.com/esmini/esmini?utm_source=chatgpt.com)

### **Expected behaviour**

One of:

load failure  
runtime error  
unsupported feature  
unexpected behaviour

### **Expected output**

Your system should capture:

scenario  
feature involved  
esmini version  
failure phase  
error/log

### **Tests**

**esmini compatibility layer \+ runtime failure classification**

### **Expected result**

**INTENTIONAL FAILURE**

This experiment should probably be one of the first ones you run after establishing the basic happy path.

---

# **29\. The 10 experiments form a capability matrix**

Don't just run them and look at the result.

Use them as a discovery matrix:

| Experiment | Understanding | IR | Generation | Validation | Trigger | Simulation | Observation | Feedback |
| ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- |
| E01 Following | ✓ | ✓ | ✓ | ✓ |  | ✓ | ✓ |  |
| E02 Braking | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| E03 Acceleration | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |
| E04 Lane Change | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |
| E05 Cut-in | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| E06 Crossing | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |
| E07 Trigger Chain | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| E08 Invalid Lane |  | ✓ | ✓ | **✓** |  |  |  | ✓ |
| E09 Unreachable Trigger |  | ✓ | ✓ | **✓** | **✓** |  |  | ✓ |
| E10 Runtime Failure |  | ✓ | ✓ | **✓** | ✓ | **✓** | **✓** | **✓** |

This gives you something much more useful than ten demos.

You are effectively building a **capability discovery test suite**.

---

# **30\. What I would change in your current diagram**

I would **not add ten more boxes**.

Instead, keep your current high-level flow and make these conceptual corrections:

### **Current**

Scenario Knowledge

### **Refine internally into**

Standard Knowledge  
Domain Knowledge  
Map Knowledge  
Simulator Capability Knowledge  
Scenario Pattern Knowledge  
---

### **Current**

Scenario Validation

### **Refine into**

Structural Validation  
Semantic Validation  
Map Validation  
esmini Compatibility Validation  
Reachability / Sanity Validation  
Runtime Preflight  
---

### **Current**

Observation & Evaluation

### **Refine into**

Observation  
   ↓  
State Extraction  
   ↓  
Metric Calculation  
   ↓  
Objective Evaluation  
   ↓  
Failure Classification  
---

### **Current**

Feedback & Improvement

### **Refine into**

Diagnosis  
Repair  
Parameter Search  
Scenario Mutation  
Exploration  
---

### **Current**

Scenario / Map / Results / Logs

### **Refine into**

Scenario Artifacts  
Map Artifacts  
Run Artifacts  
Results  
Logs  
Metrics  
Provenance  
Versioning  
---

# **31\. The most important conceptual separation**

I would establish this before writing any architecture:

                   INTELLIGENCE  
                         │  
       ┌─────────────────┼──────────────────┐  
       ↓                 ↓                  ↓  
 Understanding       Generation         Improvement  
       │                 │                  │  
       └─────────────────┼──────────────────┘  
                         ↓  
                    Semantic IR  
                         │  
                         ↓  
                 Deterministic Layer  
                         │  
              ┌──────────┼───────────┐  
              ↓          ↓           ↓  
         Validation   Serialization  Execution  
              │          │           │  
              └──────────┼───────────┘  
                         ↓  
                      esmini  
                         ↓  
                   Observations  
                         ↓  
                  Deterministic  
                    Evaluation  
                         ↓  
                    Intelligence

That is much cleaner than making every box an agent.

---

# **32\. One major architectural principle for Phase 1**

Your real research question shouldn't be:

> **"How do I build an AI agent that generates OpenSCENARIO?"**

That's too narrow and will lead you toward an LLM wrapper around XML generation.

The more valuable question is:

> **"How can an intelligent system reliably transform scenario intent into executable, validated, observable and iteratively improvable simulation scenarios?"**

That changes what you measure.

Your success criteria then become:

1. Can it understand intent?  
2. Can it represent intent independently of XML?  
3. Can it generate executable scenarios?  
4. Can it detect invalid scenarios before execution?  
5. Can it distinguish standard validity from simulator compatibility?  
6. Can it observe what actually happened?  
7. Can it determine whether the intended behaviour occurred?  
8. Can it diagnose failures?  
9. Can it improve the scenario?  
10. Can it reproduce every experiment?

That is a much stronger Phase-1 research boundary.

And importantly, **don't bring CARLA into this yet**. The IR and capability boundaries should be designed with future simulator portability in mind, but the experiments and implementation should remain strictly **OpenSCENARIO \+ OpenDRIVE \+ esmini** for Phase 1\.

The next useful step is therefore **not coding**. It is to take these 10 experiments and, for each one, record:

Requirement  
→ Interpretation  
→ IR  
→ Generated OSC  
→ Validation result  
→ esmini execution  
→ Observations  
→ Evaluation  
→ Failure/repair  
→ Final scenario

That will expose the actual **Known Unknowns and Unknown Knowns** far better than trying to predict them from the architecture diagram alone.

