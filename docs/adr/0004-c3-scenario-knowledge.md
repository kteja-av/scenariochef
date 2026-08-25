# ADR-0004: C3 Scenario Knowledge

## Status

Accepted (source: C3-Q*, checkpoint 2026-08-19)

## Context

OpenSCENARIO-valid does not imply esmini-executable. HASCO-style passive RAG alone cannot answer "will this build run it?" C3 must supply evidence without deciding the scenario.

## Decision

C3 is a **retrieval and rules service** backed by a **typed graph + esmini capability matrix (K3)**, not a vector DB as source of truth.

### Store shape

- `Feature` (e.g. `osc.action.LaneChange`)
- `StandardVersion`, `SimulatorBuild` (pinned esmini build id)
- `SupportEdge`: supports | partial | unsupported | **unknown**
- `Catalog` / `CatalogEntry`, `MapAsset` (id, path, hash — **no lane graph**)
- `DomainRule` (assumption-class unless catalog-backed)

### Key rules

| Topic | Decision |
| --- | --- |
| OSC yes, esmini silent | Return **`unknown`**; execution authority is C6/C7 dry-run (C3-Q2) |
| Map topology | C3 versions maps; **C6 owns** "does lane 3 exist?" (C3-Q3) |
| Runtime write-back | **Never** — static docs only (C3-Q4) |
| Phase-1 OSC subset | Whatever the **pinned esmini build** executes (C3-Q5) |
| CARLA / ScenarioRunner | **Out of Phase 1** (C3-Q6) |
| Defaults in bundle | Allowed as assumptions; C1+C2 must ack before use (C3-Q7) |
| Authority | OSC XSD > esmini docs > catalogs > domain notes (C3-Q8) |

### Output contract

`EvidenceBundle`: `{definitions, constraints, examples, compatibility, provenance}`

## Consequences

### Positive

- Separates definition authority from execution authority
- K3 matrix is curated and reproducible

### Negative

- `unknown` features require dry-run cost (C6 S6 / C7 preflight)
- No learning from repeated E10 failures inside C3 (record in C10 instead)

### Follow-ups

- Implement graph store (SQLite or JSON + loader) keyed by esmini build id
- Ingest XSD, esmini docs, catalogs as evidence blobs on nodes
