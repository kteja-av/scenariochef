# ADR-0001: Python Implementation Stack

## Status

Accepted (2026-08-25)

## Context

ScenarioChef is a multi-component pipeline spanning NLP, knowledge retrieval, IR compilation, validation, external simulator invocation, and persistent artifact management. The project is greenfield with frozen Phase-1 architecture decisions in `docs/checkpoint.md` but no implementation yet.

We need a language and tooling baseline that:

- Integrates with `scenariogeneration` (Python) for OpenSCENARIO compilation
- Supports structured schemas (IR, intent slots, validation reports)
- Can orchestrate subprocess calls to esmini and external validators
- Is familiar to the research/simulation community

## Decision

Implement ScenarioChef in **Python 3.11+** with:

| Layer | Choice |
| --- | --- |
| Packaging | `hatchling` via `pyproject.toml` |
| Schemas / contracts | `pydantic` v2 |
| Config / static data | YAML where human-edited |
| Lint / format | `ruff` |
| Types | `mypy` (strict) |
| Tests | `pytest` |
| Package layout | `src/scenariochef/` with one subpackage per component (C1–C10, CX) |

External dependencies pinned at integration time: esmini binary, OpenSCENARIO XSD, pinned esmini build id (see ADR-0004, ADR-0008).

## Consequences

### Positive

- Direct use of `scenariogeneration` without FFI
- Rapid iteration on IR and validation logic
- Strong typing via Pydantic models shared across components

### Negative

- Simulator and heavy numerics remain out-of-process (esmini subprocess)
- GIL limits pure-Python parallelism for batch runs (mitigate with process pools later)

### Follow-ups

- Add `requirements-esmini.txt` or env docs when esmini pin is chosen
- Wire CI (lint, typecheck, pytest) once first component lands
