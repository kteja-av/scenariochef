# ADR-0007: C6 Scenario Validation

## Status

Accepted (source: C6-Q*, checkpoint 2026-08-19)

## Context

Validation must distinguish structural validity, semantic consistency, map compatibility, and esmini executability. A single PASS/FAIL bit is insufficient for the repair loop.

## Decision

C6 implements a **frozen funnel S1→S6** with **short-circuit on FAIL**.

| Stage | Phase-1 behavior |
| --- | --- |
| S1 | XSD / structural validation |
| S2 | OpenSCENARIO semantic checks |
| S3 | OpenDRIVE / map reference checks |
| S4 | Catalog and physical bounds (catalog facts + C1/C2-acked assumptions) |
| S5 | Static reachability — **skipped** (C6-Q1) |
| S6 | esmini dry-run — **only when K3=unknown** (C6-Q2) |

| Topic | Decision |
| --- | --- |
| E09 unreachable trigger | WARN-and-pass (detection shifts to C7/C8 while S5 skipped) (C6-Q3) |
| Physical bounds | Catalog facts + acknowledged assumptions (C6-Q5) |

### Output contract

`ValidationReport`: per-stage status, error taxonomy, location, severity, repair hints.

## Consequences

### Positive

- Cheaper checks before simulator invocation
- Unknown-feature path aligned with C3/C5/C7

### Negative

- E09 may not surface until runtime without S5
- Map topology errors (E08) require C6 S3, not C3

### Follow-ups

- Integrate ASAM semantic checker if available as subprocess
- C6 S6 calls C7 `preflight` mode only
