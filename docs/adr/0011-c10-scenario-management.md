# ADR-0011: C10 Scenario Management

## Status

Accepted (source: C10-Q*, checkpoint 2026-08-19)

## Context

Without provenance, automated generation is undebuggable. E10 runtime discoveries must be queryable even though C3 does not accept runtime write-back.

## Decision

C10 persists **SQL metadata + object files** for all Phase-1 artifacts.

| Topic | Decision |
| --- | --- |
| Storage | SQLite (dev) / Postgres (prod) + object store for `.xosc`, maps, logs (C10-Q1) |
| Identity | Content hashes **and** human names/tags (C10-Q2) |
| Retention | **Keep all Phase-1 runs** (C10-Q3) |
| Action log | Log C2 and C9 proposals as actions now (C10-Q4) |
| Dedup | **None** in Phase 1 (C10-Q5) |

### Stored entities

Request → Intent → IR → GeneratedScenario → ValidationReport → RunRecord → EvaluationReport → FeedbackAction (full lineage).

## Consequences

### Positive

- C9 can query prior E10 hits by feature via C10, not C3
- Reproducibility: esmini build, seed, map hash on every run

### Negative

- Storage growth without dedup
- Requires migration strategy before production scale

### Follow-ups

- Define SQL schema and artifact directory layout under `artifacts/`
- Cross-link ADR provenance fields to C10 record ids
