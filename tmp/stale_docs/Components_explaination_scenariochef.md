Yes. These two files are essentially **the blueprint of ScenarioChef Phase 1**. One tells you **what each component is responsible for**, and the other tells you **how those components connect and exchange information**.

For your ScenarioChef project, the easiest way to understand them is:

> **Component Inventory \= “What does each component do?”**  
> **Connection Map \= “How does the whole system work together?”**

The architecture is explicitly frozen for Phase 1, and Phase 1 is focused on **automated OpenSCENARIO \+ esmini**.

---

# **1\. First understand the whole ScenarioChef idea**

Imagine the user says:

> **“Create a scenario where my ego vehicle follows a lead vehicle at 50 km/h, and the lead vehicle suddenly brakes.”**

ScenarioChef should **not** simply send that sentence to an LLM and ask it to generate `.xosc`.

Instead, it creates a controlled pipeline:

User  
  ↓  
C1  → Understand the input  
  ↓  
C2  → Understand what the user actually means  
  ↓  
C3  → Check knowledge / capabilities  
  ↓  
C4  → Create canonical scenario meaning  
  ↓  
C5  → Compile into OpenSCENARIO  
  ↓  
C6  → Validate it  
  ↓  
C7  → Run it in esmini  
  ↓  
C8  → Evaluate what happened  
  ↓  
C9  → Repair / improve if necessary  
  ↓  
C10 → Store everything

And **CX** controls the entire process.

The inventory defines these as C1–C10 plus CX, with each component having a specific responsibility and contract.

---

# **2\. The most important architectural idea**

There is a very important separation here:

### **LLM ≠ entire system**

Only **C2 is an LLM agent in Phase 1**.

Everything else is deliberately deterministic:

| Component | What it is |
| ----- | ----- |
| C1 | Deterministic |
| C2 | **LLM agent** |
| C3 | Deterministic retrieval |
| C4 | Deterministic semantic model |
| C5 | Deterministic compiler |
| C6 | Deterministic validator |
| C7 | Deterministic simulator |
| C8 | Deterministic evaluator |
| C9 | Deterministic repair/search |
| C10 | Deterministic persistence |
| CX | Hardcoded orchestrator |

That is a **very deliberate design choice**.

So ScenarioChef is **not an “LLM generates driving scenarios” system**.

It is closer to:

> **LLM-assisted scenario engineering pipeline with deterministic verification and execution.**

That's a much stronger architecture.

---

# **3\. What CX actually does**

Think of **CX as the manager**.

It doesn't generate scenarios.

It decides:

What should run?  
When should it run?  
Can we continue?  
Do we need the user?  
Did something fail?  
Should we retry?  
When should we stop?

CX enforces this mandatory order:

C1 → C2 → C4 → C5 → C6 → C7 → C8

C3 is consulted when needed.

CX also controls:

* HITL  
* iteration limits  
* timeout  
* component ordering  
* provenance  
* repair/exploration loops

The Phase-1 limits are **maximum 5 iterations** and **5 minutes per request**.

---

# **4\. C1 — Scenario Input**

C1 is basically your **input adapter**.

Suppose user provides:

> “Make a highway scenario where the ego car follows another car at 50 km/h.”

C1 doesn't try to reason deeply about the scenario.

It converts the raw input into a structured:

RequestSpec

C1 handles:

* natural language  
* structured parameters  
* `.xosc`  
* `.xodr`  
* crash narratives  
* multimodal artifacts  
* units  
* missing fields  
* contradictions

Its output is schema-valid and normalized.

### **Example**

Raw:

"ego follows lead at 50 kph"

C1 might normalize:

{  
  "ego\_speed": {  
    "value": 50,  
    "unit": "km/h"  
  },  
  "relationship": "follow",  
  "lead\_vehicle": true  
}

Not necessarily this exact schema—the important point is that **C1 produces RequestSpec**, not ScenarioIR.

---

# **5\. C2 — Scenario Understanding**

This is the **main intelligence component**.

C2 takes:

RequestSpec  
       \+  
EvidenceBundle from C3

and creates:

IntentSpec

Its job is to answer:

> **“What scenario does the user actually want?”**

It extracts:

* actors  
* interactions  
* temporal relationships  
* spatial relationships  
* behavior  
* constraints  
* intent

C2 is explicitly the **only LLM agent in Phase 1**.

### **Example**

User:

> “Lead car brakes suddenly while ego follows at 50 km/h.”

C2 might infer:

Actors:  
    ego  
    lead

Relationship:  
    ego follows lead

Behavior:  
    lead performs sudden braking

Speed:  
    ego \= 50 km/h

Objective:  
    evaluate whether ego responds appropriately

But here's an important rule:

### **C2 cannot override explicit user choices.**

If the user says:

> “Use lane 3.”

C2 cannot decide:

> “Lane 2 makes more sense.”

The architecture explicitly says C2 must not rewrite user-explicit slots.

---

# **6\. C3 — Scenario Knowledge**

This is one of the most important components for **your current implementation work**.

C3 is basically:

> **ScenarioChef's authoritative knowledge layer.**

But it is **not an LLM brain**.

It provides evidence about:

* OpenSCENARIO definitions  
* simulator capabilities  
* feature compatibility  
* catalogs  
* map identity/version  
* domain rules

Its output:

EvidenceBundle

The architecture specifically says C3 uses a:

> **Typed graph \+ esmini K3 capability matrix**

rather than treating a vector DB as truth.

This distinction matters.

### **C3 answers:**

> “What does this OpenSCENARIO construct mean?”

> “Does this pinned esmini build support this feature?”

> “What version of OSC supports this?”

But C3 does **not** answer:

> “Does lane 3 physically exist on this map?”

That's C6's responsibility.

The authority table makes this explicit.

---

# **7\. C4 — Scenario IR**

This is probably the **most important conceptual layer** in the architecture.

C4 converts:

IntentSpec  
     ↓  
ScenarioIR

ScenarioIR represents the **meaning of the scenario**, independent of OpenSCENARIO XML.

Think:

User intent  
     ↓  
IntentSpec  
     ↓  
ScenarioIR  
     ↓  
OpenSCENARIO

The critical idea is:

> **ScenarioIR is not `.xosc`.**

It is your internal semantic representation.

For example:

ScenarioIR

Actors:  
  ego  
  lead

Initial condition:  
  ego speed \= 50 km/h

Behavior:  
  lead brakes

Relationship:  
  ego follows lead

Objective:  
  evaluate response

C4 also supports ranges such as:

speed \= 40–60 km/h

but Phase 1 does not support full probability distributions.

---

# **8\. C5 — Scenario Generation**

C5 is the **compiler**.

This is a crucial distinction.

C5 does not reason about what the user meant.

It receives:

ScenarioIR

and produces:

GeneratedScenario

containing things like:

scenario.xosc  
scenario.xodr  
K3 flags  
parameter bindings

The architecture explicitly makes C5 deterministic and excludes LLM-based generation approaches such as CTG/TRACE/diffusion from Phase 1\.

So:

C2 \= interprets intent

C4 \= represents meaning

C5 \= compiles meaning → executable scenario

That separation is excellent because it prevents the LLM from directly writing arbitrary simulation artifacts.

---

# **9\. C6 — Scenario Validation**

Now ScenarioChef asks:

> **“Is this scenario actually valid and executable?”**

C6 is a validation funnel.

It performs:

S1 → XSD / structural  
S2 → OpenSCENARIO semantic  
S3 → map/topology  
S4 → catalog \+ physical bounds  
S5 → static reachability \[skipped\]  
S6 → esmini dry-run if necessary

This is where a lot of the architecture's real value appears.

A scenario can be:

valid XML  
     ↓  
valid OpenSCENARIO  
     ↓  
BUT invalid map reference

So merely checking the XSD isn't enough.

---

# **10\. C7 — esmini Simulation**

C7 is the actual execution engine.

It takes:

GeneratedScenario  
\+  
OpenDRIVE map  
\+  
RunConfig

and runs it in **esmini**.

It produces:

RunRecord

containing things like:

* logs  
* CSV trajectories  
* optional OSI  
* timeout information  
* hang metadata

Phase 1 is intentionally bounded to:

C5 → C6 → C7(esmini) → C8

There are **no CARLA, ScenarioRunner, or OSC2Runner edges in Phase 1**.

---

# **11\. C8 — Observation & Evaluation**

C7 tells you:

> “Here is what happened.”

C8 tells you:

> **“Did what happened satisfy the scenario objective?”**

For example:

TTC  
PET  
collision  
completion  
objective pass/fail

C8 is deterministic.

No LLM/VLM interpretation in Phase 1\.

This is important.

If the scenario objective is:

> “Ego should avoid collision.”

C8 should calculate objective-related metrics rather than ask an LLM:

> “Do you think this was safe?”

---

# **12\. C9 — Feedback & Improvement**

This is where the system becomes iterative.

Suppose C6 says:

FAIL

Invalid lane reference.

Then:

C6  
 ↓  
ValidationReport  
 ↓  
C9  
 ↓  
repair  
 ↓  
RevisedIR  
 ↓  
C4

C9 then sends the repaired IR back through the pipeline.

The architecture calls this the **repair loop**.

There is also an **exploration loop**:

C6 PASS  
 ↓  
C7  
 ↓  
C8  
 ↓  
C9  
 ↓  
change parameters  
 ↓  
C4

This is for exploring parameter ranges after a successful scenario.

C9 itself is deterministic:

Repair → rules  
Explore → parameter search

No LLM.

---

# **13\. C10 — Scenario Management**

C10 is your **memory/database layer**.

It stores essentially everything:

RequestSpec  
IntentSpec  
ScenarioIR  
GeneratedScenario  
ValidationReport  
RunRecord  
EvaluationReport  
FeedbackAction

The architecture calls this the full **provenance chain**.

This is extremely important for debugging.

Imagine someone asks:

> “Why did ScenarioChef generate this scenario?”

You can trace:

User request  
   ↓  
RequestSpec  
   ↓  
IntentSpec  
   ↓  
ScenarioIR  
   ↓  
GeneratedScenario  
   ↓  
ValidationReport  
   ↓  
RunRecord  
   ↓  
EvaluationReport  
   ↓  
FeedbackAction

C10 maintains those links using record IDs and hashes.

---

# **14\. Now connect the two files together**

The **Component Inventory** says:

C1 \= input  
C2 \= understanding  
C3 \= knowledge  
C4 \= IR  
C5 \= generation  
C6 \= validation  
C7 \= simulation  
C8 \= evaluation  
C9 \= improvement  
C10 \= persistence  
CX \= orchestration

The **Connection Map** tells you how those components communicate:

User  
 ↓  
CX  
 ↓  
C1  
 ↓ RequestSpec  
C2  
 ↓ IntentSpec  
C4  
 ↓ ScenarioIR  
C5  
 ↓ GeneratedScenario  
C6  
 ↓  
C7  
 ↓ RunRecord  
C8  
 ↓ EvaluationReport  
C9  
 ↓ RevisedIR  
 ↺ C4

Everything  
 ↓  
C10  
---

# **15\. The actual data contracts are the key**

You should memorize these:

User  
  ↓  
RequestSpec  
  ↓  
IntentSpec  
  ↓  
ScenarioIR  
  ↓  
GeneratedScenario  
  ↓  
ValidationReport  
  ↓  
RunRecord  
  ↓  
EvaluationReport  
  ↓  
FeedbackAction / RevisedIR

These are the **contracts between components**.

In other words, components should not randomly exchange arbitrary Python objects.

They communicate through defined artifacts.

---

# **16\. A complete example**

Let's run your hypothetical scenario through the architecture.

### **User**

> “Create a highway scenario where the ego follows a lead vehicle at 50 km/h and the lead suddenly brakes.”

### **Step 1 — C1**

Produces:

RequestSpec

Normalized request.

↓

### **Step 2 — C2**

Understands:

ego  
lead vehicle  
following relationship  
50 km/h  
sudden braking

Produces:

IntentSpec

↓

### **Step 3 — C3**

Checks:

What does the required OSC construct mean?  
Does esmini support it?  
What assumptions are necessary?

Returns:

EvidenceBundle

↓

### **Step 4 — C4**

Builds:

ScenarioIR

This is the canonical scenario meaning.

↓

### **Step 5 — C5**

Compiles:

ScenarioIR  
     ↓  
scenario.xosc

↓

### **Step 6 — C6**

Checks:

XSD  
OSC semantics  
map  
catalog  
physical bounds  
esmini compatibility

Suppose it passes.

↓

### **Step 7 — C7**

Runs:

esmini

Produces:

RunRecord

with trajectories.

↓

### **Step 8 — C8**

Calculates:

TTC  
PET  
collision  
completion  
objective pass/fail

Produces:

EvaluationReport

↓

### **Step 9 — C9**

Suppose TTC is too low.

C9 may explore a parameter range:

initial distance:  
20m  
30m  
40m  
50m

Then produces:

RevisedIR

↓

### **Step 10**

Back to:

C4  
 ↓  
C5  
 ↓  
C6  
 ↓  
C7  
 ↓  
C8

until:

metric improves

or:

5 iterations

or:

5-minute request budget

is reached.

---

# **17\. The most important separation to understand**

There are **four different kinds of correctness**.

This is probably the single most important architectural concept in the connection map.

### **1\. Is the OpenSCENARIO construct valid?**

**C3 \+ C6 S1/S2**

Is this legal OSC?

### **2\. Is the scenario valid for this map?**

**C6**

Does lane 3 actually exist?

Not C3.

### **3\. Will esmini actually execute it?**

C3 K3 capability  
\+  
C6 S6 if unknown  
\+  
C7

### **4\. Did the scenario achieve its objective?**

**C8**

Did ego avoid collision?  
Was TTC within desired range?  
Did the scenario complete?

The architecture explicitly separates these authorities.

---

# **18\. Where your current project actually stands**

This is important because you shouldn't assume the architecture is already implemented.

The file says:

> **All components are currently package stubs only (`__init__.py`).**

Contracts and ADRs are defined, but implementation has not yet been completed.

And the **next implementation target is C3 — Scenario Knowledge**. component\_inventory.mdMD

So if you're working on ScenarioChef **right now**, don't start randomly implementing C1 → C10.

The architecture says the recommended build order is:

Layer 0  
    C10  
    C3

Layer 1  
    C1 → C2

Layer 2  
    C4 → C5

Layer 3  
    C6 ↔ C7

Layer 4  
    C8 → C9

Layer 5  
    CX  
component\_connection\_map.mdMD

And specifically:

> **C3 is the first detailed implementation target (SEQ-1).**

---

# **19\. How I would mentally model ScenarioChef**

Don't think of it as:

LLM → xosc → simulator

That's too simplistic.

Think of it as:

                ┌───────────────┐  
                 │      CX       │  
                 │  Orchestrator │  
                 └───────┬───────┘  
                         │  
User → C1 → C2 ←─────── C3  
          │              │  
          ↓              │  
         C4 ←────────────┘  
          │  
          ↓  
         C5  
          │  
          ↓  
         C6  
          │  
          ↓  
         C7  
          │  
          ↓  
         C8  
          │  
          ↓  
         C9 ───────────→ C4  
            
          ↓  
         C10

The **LLM is only one piece**.

The real product is the controlled loop:

> **Understand → Represent → Compile → Validate → Simulate → Evaluate → Improve**

with **knowledge, orchestration, human intervention, and provenance around it**.

That is what these two files are actually specifying.

