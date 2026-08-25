# ADR-0010: C9 Feedback & Improvement

## Status

Accepted (source: C9-Q*, checkpoint 2026-08-19 / 2026-08-22)

## Context

Failures from validation, simulation, or evaluation must drive repair or exploration without collapsing into a single opaque "LLM fixes everything" step.

## Decision

C9 splits into two **deterministic subsystems** (rules + search), invoked as a **service on the CX DAG** — not a second LLM agent.

| Subsystem | Responsibility |
| --- | --- |
| **Repair** | Structural patches: schema, catalog, link fixes — **never user-explicit slots** (C9-Q6) |
| **Explore** | Parameter search on IR ranges **after C6 PASS** (C9-Q1, C9-Q2) |

| Topic | Decision |
| --- | --- |
| Diversity constraints | Deferred — not Phase 1 (C9-Q3) |
| Stop condition | N=**5** iterations OR no metric gain (C9-Q4) |
| Mutation target | **RevisedIR** — not rollback to IntentSpec/RequestSpec (C9-Q5) |
| E08 | Classify topology FAIL; escalate to user HITL — do not snap lanes (DERIVED-16) |

### Output contract

`FeedbackAction`: `{type: repair|explore, revised_ir?, rationale, iteration}`

## Consequences

### Positive

- Clear separation from C2 (no rewriting user intent)
- Exploration decoupled from compile-time C5 expansion

### Negative

- Structural repairs limited for map-topology failures
- Parameter search needs C8 metric signal

### Follow-ups

- Log all C9 actions to C10 (C10-Q4)
- Wire stop condition to CX loop budget (ADR-0012)
