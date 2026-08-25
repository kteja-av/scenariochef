# ADR-0005: C4 Scenario IR

## Status

Accepted (source: C4-Q*, checkpoint 2026-08-19)

## Context

The IR is the most important architectural layer: it represents **scenario meaning** independent of OpenSCENARIO XML. Direct JSON-mirror of XOSC would forfeit portability and repair semantics.

## Decision

Use a **Scenic-like probabilistic DSL shape** as the IR **language** (not the Scenic compiler or CARLA backend).

| Topic | Decision |
| --- | --- |
| Language | Scenic-like spatial/temporal semantics (C4-Q1) |
| Positions | Road-relative and cartesian **both allowed**; every position **must** carry a frame tag (C4-Q2) |
| Objectives | IR holds **objective stubs**; C8 owns thresholds/rulebook (C4-Q3) |
| Uncertainty | **Ranges (min/max)** in Phase 1 — not full distributions (C4-Q4) |
| Repair hints | C4 may emit `suggestions[]`; **C9 applies** — C4 does not mutate canonical IR (C4-Q5) |

### Output contract

`ScenarioIR` — canonical semantic model + optional `suggestions[]` + provenance links.

## Consequences

### Positive

- Simulator-independent meaning layer
- C5 can compile to `.xosc` without touching LLM
- User-explicit slots preserved for E08 visibility

### Negative

- Custom IR parser/validator must be built (Scenic toolchain not shipped)
- Range semantics need clear binding rules in C5

### Follow-ups

- Define IR grammar (Python dataclasses / Pydantic + optional surface syntax)
- Frame tag enum: `road_relative`, `lane_relative`, `cartesian`, etc.
