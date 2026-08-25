# ADR-0012: CX Orchestration

## Status

Accepted (source: CX-Q*, checkpoint 2026-08-19 / 2026-08-22)

## Context

Something must coordinate generate → validate → run → evaluate → repair without making every box an agent. Cross-cutting experiment orchestration and provenance were identified in `docs/trajectories.md`.

## Decision

CX is a **hardcoded DAG orchestrator** with **C2 as the only LLM agent** and **C9 as a called service**.

| Topic | Decision |
| --- | --- |
| Topology | DAG + C2 LLM; C9 repair/explore on DAG (CX-Q1) |
| Tools | **C1–C10 APIs only** — no shell, no raw file edits (CX-Q2) |
| HITL | Missing params, contradictions, low confidence, assumption acks (CX-Q3) |
| Loop budget | N=5 or no metric gain, plus **5-minute wall-clock per request** (CX-Q4) |
| Pipeline integrity | **May not skip or reorder C4, C6, C7** (CX-Q5) |
| C9 placement | Keep C9 as separate service — do not collapse into CX (CX-Q6) |

### Canonical request flow

```
User → C1 → C2 ⇄ C3 → C4 → C5 → C6 ──FAIL──→ C9 ──→ C4…
                              │ PASS
                              ▼
                             C7 → C8 ──→ C9 (explore) ──→ …
                              │
                              └── all steps ──→ C10
```

## Consequences

### Positive

- Deterministic control plane; intelligence only where needed
- HITL gates centralized

### Negative

- DAG changes require code edits, not prompt changes
- 5-minute wall-clock may abort long esmini runs

### Follow-ups

- Implement CX as explicit state machine in `cx_orchestrator/`
- Expose component APIs as typed Python functions first, HTTP later if needed
