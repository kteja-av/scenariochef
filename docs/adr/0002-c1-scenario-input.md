# ADR-0002: C1 Scenario Input

## Status

Accepted (source: C1-Q*, checkpoint 2026-08-19)

## Context

Users arrive with heterogeneous inputs: natural language, parameterized requests, existing `.xosc`/`.xodr`, crash narratives, and multimodal artifacts. C1 must normalize these into a consistent **RequestSpec** without interpreting scenario semantics (that is C2's job).

## Decision

C1 is a **deterministic adapter layer**, not an LLM agent.

| Topic | Decision |
| --- | --- |
| Modalities | All Phase-1 modalities: NL+params, `.xosc`/`.xodr` ingest, crash narratives, multimodal (C1-Q1) |
| Missing parameters | **Ask the user** — no silent defaults, no hard reject (C1-Q2) |
| C3 defaults | Both C1 and C2 must acknowledge before C4 may consume (C1-Q3, ties C3-Q7) |
| Contradictions | **Ask the user** (C1-Q4) |
| C1 / C2 split | **Keep separate** — normalize vs interpret (C1-Q5) |
| Agent? | **No** (C1-Q6) |

### Output contract

`RequestSpec` — normalized, schema-validated request with explicit units, modality tag, and unresolved-field markers for HITL.

## Consequences

### Positive

- Clear boundary: adapters vs understanding
- HITL policy is consistent across C1 and C2

### Negative

- Multimodal ingest (Phase-1 scope) increases C1 adapter surface area early

### Follow-ups

- Define Pydantic models for `RequestSpec` and per-modality adapters
- HITL channel owned by CX (ADR-0012)
