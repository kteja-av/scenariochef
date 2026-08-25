# ADR-0009: C8 Observation & Evaluation

## Status

Accepted (source: C8-Q*, checkpoint 2026-08-19)

## Context

Simulation output must become objective pass/fail against scenario intent. LLM-as-evaluator is deferred to avoid non-reproducible scoring.

## Decision

C8 is **measurement + rulebook** — no layer-4 LLM/VLM in Phase 1.

| Topic | Decision |
| --- | --- |
| Objectives | Evaluate IR objective stubs against C8 **rulebook** — do not invent new objectives (C8-Q1) |
| LLM | **None** in Phase 1 (C8-Q2) |
| Core metrics | TTC, collision, completion (C8-Q3) |
| TTC | **Always pair with PET** (C8-Q4) |
| Data source | CSV/states if OSI missing (C8-Q5) |

### Output contract

`EvaluationReport`: metric values, pass/fail per objective stub, failure classification.

## Consequences

### Positive

- Deterministic, auditable scoring
- Aligns with IR objective stubs from C4

### Negative

- Cannot score subjective "did it feel like a cut-in?" without future LLM layer
- PET computation must be implemented for all TTC reports

### Follow-ups

- Version rulebook YAML alongside IR schema
- Map E01–E10 expected outcomes to rulebook entries
