# ADR-0003: C2 Scenario Understanding

## Status

Accepted (source: C2-Q*, checkpoint 2026-08-19)

## Context

C2 converts normalized requests into structured scenario intent suitable for IR construction. This is the primary **intelligence** step in Phase 1. The thesis recommends LLM-as-intent-parser, not LLM-as-XML-writer.

## Decision

C2 is a **slot-filling LLM proposer** behind a **deterministic JSON schema gate**. It is the **only LLM agent** in Phase 1.

| Topic | Decision |
| --- | --- |
| Mechanism | Slot-filling LLM + JSON schema (C2-Q1) |
| Validation | LLM proposes; schema validates (C2-Q4) |
| Low confidence | `unknowns[]` → ask user (C2-Q2) |
| User-explicit slots | **Never rewrite** — e.g. keep `lane=3` even if invalid (C2-Q3) |
| Knowledge | Queries C3 `EvidenceBundle`; does not invent OSC facts |

### Output contract

`IntentSpec` — validated slots: actors, maneuvers, triggers, constraints, objectives, confidence/unknowns.

## Consequences

### Positive

- Prevents unconstrained LLM output from reaching IR
- E08 (invalid lane) remains visible for C6/C9 rather than silently "fixed"

### Negative

- Schema maintenance cost as scenario vocabulary grows
- LLM latency on every request

### Follow-ups

- Version `IntentSpec` schema alongside IR schema
- Log all C2 proposals to C10 (C10-Q4)
