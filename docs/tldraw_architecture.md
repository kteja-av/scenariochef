# TL Draw Architecture — Phase 1 Automated Scenario Generation
## Abstraction & Capability Layer | Data Flow for One User Request

---

## LAYER 0: ABSTRACTION MAP

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ABSTRACTION LAYERS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Abstraction  │  Label              │  Description                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  L0         │  Orchestration      │  Coordinates all components; │
│             │                     │  routes data between them    │
├─────────────────────────────────────────────────────────────────────────────┤
│  L1         │  Capabilities       │  11 named capability groups  │
│             │                     │  (see LAYER 2)               │
├─────────────────────────────────────────────────────────────────────────────┤
│  L2         │  Sub-Capabilities   │  60+ atomic sub-functions    │
│             │                     │  (see LAYER 2 detail)        │
├─────────────────────────────────────────────────────────────────────────────┤
│  L3         │  Intelligence       │  Agent candidates vs.          │
│             │                     │  deterministic functions     │
├─────────────────────────────────────────────────────────────────────────────┤
│  L4         │  Data Stores        │  Persistent state:             │
│             │                     │  IR, .xosc/.xodr, runs,        │
│             │                     │  metrics, logs                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

(LAYER 1 and LAYER 4 continue on next page — this diagram uses layered notation
where each horizontal band is a capability, vertical arrows are data flow.)

---

## LAYER 1: CAPABILITY LAYER (11 CAPABILITIES)

```
  C1  Scenario Input
  C2  Scenario Understanding
  C3  Scenario Knowledge
  C4  Scenario Representation
  C5  Scenario Generation
  C6  Scenario Exploration
  C7  Scenario Validation
  C8  esmini Simulation
  C9  Observation & Evaluation
  C10 Feedback & Improvement
  C11 Scenario Management
```

(LAYER 2: Sub-capability detail continues below)
