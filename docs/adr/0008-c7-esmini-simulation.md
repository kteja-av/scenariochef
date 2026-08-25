# ADR-0008: C7 esmini Simulation

## Status

Accepted (source: C7-Q*, checkpoint 2026-08-19)

## Context

C7 is the Phase-1 execution engine. It must support both validation preflight and full experiment runs with reproducible configuration.

## Decision

C7 is a **deterministic subprocess runner** — not an agent.

| Topic | Decision |
| --- | --- |
| Modes | One runner, two modes: `preflight` \| `full` (C7-Q1) |
| RunConfig | Mandatory: `esmini_build`, `dt`, `seed`, `max_time`; OSI and headless optional (C7-Q2) |
| Controllers | **Default controller only** — ROS2/FMI out of Phase 1 (C7-Q3) |
| Hang policy | Wall-clock timeout **and** step cap — either trips termination (C7-Q4) |
| GUI | Allowed for debug; **batch defaults to headless** (C7-Q5) |

### Output contract

`RunRecord`: stdout/stderr, exit code, trajectories (CSV), optional OSI trace, timing, hang reason.

## Consequences

### Positive

- C6 S6 and full experiments share one integration surface
- Reproducibility fields satisfy experiment matrix (E01–E10)

### Negative

- esmini binary path and version are environment dependencies
- OSI-off path requires C8 CSV/state evaluation (C8-Q5)

### Follow-ups

- Document esmini install and pinned build in README
- Capture RunRecord to C10 on every invocation
