# ADR-0006: C5 Scenario Generation

## Status

Accepted (source: C5-Q*, checkpoint 2026-08-19 / 2026-08-22)

## Context

C5 turns semantic IR into executable OpenSCENARIO artifacts. Raw LLM XML generation is explicitly rejected by the thesis and checkpoint.

## Decision

C5 is a **deterministic scenariogeneration compiler only** — no LLM.

| Topic | Decision |
| --- | --- |
| Compiler | Scenic-like IR → scenariogeneration API → `.xosc` / `.xodr` (C5-Q1) |
| Variation | C5 owns **compile-time range expansion** into concrete scenario instances (C5-Q2) |
| K3 unknown | Emit features marked unknown for C6 S6 dry-run (C5-Q3) |
| Diffusion / CTG / TRACE | **Out of Phase 1** (C5-Q4) |
| Input | **IR only** — C9 applies C4 suggestions, not C5 (C5-Q5) |

### Output contract

`GeneratedScenario`: `.xosc`, optional `.xodr`, catalog refs, parameter bindings, K3 flags per feature used.

## Consequences

### Positive

- Reproducible XML generation
- Variation at compile time keeps canonical IR immutable

### Negative

- Compile-time combinatorics if ranges are large (cap expansion in implementation)
- Tight coupling to scenariogeneration API version

### Follow-ups

- Pin scenariogeneration version in pyproject optional deps
- Pass through `suggestions[]` untouched to C9/C10
