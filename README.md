# ScenarioChef

**Automated driving-scenario generation, validation, and simulation — in one compiler-style pipeline.**

ScenarioChef transforms human intent into validated, executable [OpenSCENARIO](https://www.asam.net/standards/detail/openscenario/) scenarios that run in the [esmini](https://github.com/esmini/esmini) OpenSCENARIO/OpenDRIVE player. Describe a situation in plain English (or hand over a spec, a crash narrative, trajectory data, or existing `.xosc`/`.xodr` files) and the pipeline compiles it into simulation-ready artifacts, proves they are executable, simulates them, scores the outcome, and repairs failures automatically.

- **Status:** Pre-Alpha (`v0.1.0`) — Phase 1 scope
- **Language:** Python 3.11+
- **Target simulator:** esmini (verified with v3.7.2; CARLA / ScenarioRunner deferred to later phases)
- **License:** MIT

---

## Table of contents

1. [What is ScenarioChef?](#what-is-scenariochef)
2. [Where it is used](#where-it-is-used)
3. [How it works](#how-it-works)
4. [Key features](#key-features)
5. [Getting started](#getting-started)
6. [Usage](#usage)
7. [Project layout](#project-layout)
8. [Development](#development)
9. [Git hooks & Cursor integration](#git-hooks--cursor-integration)
10. [Self-improving harness (`.harness/`)](#self-improving-harness-harness)
11. [Documentation map](#documentation-map)
12. [License](#license)

---

## What is ScenarioChef?

Scenario-based testing is the backbone of ADAS and autonomous-driving (AD) validation, but writing OpenSCENARIO files by hand is slow, error-prone, and requires deep knowledge of the standard *and* the simulator. ScenarioChef treats scenario creation like a compiler problem:

> **human intent → validated, executable simulation scenario**

Instead of one monolithic LLM "generator," ScenarioChef is a deterministic pipeline with a **single, narrow LLM touchpoint**. Each stage has one responsibility, an explicit input/output contract, and a frozen architecture (see [ADRs 0001–0012](docs/adr/README.md)). The result is reproducible: the same request produces the same artifacts (hash-verified in the test suite).

Phase 1 accepts:

- Natural-language requests ("ego follows lead in lane -1 at 20 m/s")
- Structured parameter specs
- Crash narratives
- Trajectory data
- Existing `.xosc` / `.xodr` files

## Where it is used

- **ADAS / AD simulation teams** — generate regression scenario corpora for esmini without hand-authoring XML.
- **Safety validation** — turn crash narratives and parameterized hazard descriptions into executable test cases.
- **Simulation research** — a reference implementation of LLM-assisted scenario generation where the LLM proposes but deterministic gates (schema, XSD, map topology, dry-run) decide.
- **Scenario engineering education** — a small, readable codebase (one package per pipeline stage) that shows how OpenSCENARIO, OpenDRIVE, and esmini fit together.

Out of scope for Phase 1: CTG/TRACE/diffusion-style trajectory generation, CARLA and ScenarioRunner backends, and full probabilistic scenario distributions.

## How it works

Eleven capability components (**C1–C10**) plus a hardcoded-DAG orchestrator (**CX**). Only C2 uses an LLM — everything else is deterministic.

```
                    ┌────────────────────────────── CX orchestrator (DAG) ─────────────────────────────┐
                    │                                                                                   │
 user request ──▶ C1 ──▶ C2 ──▶ C4 ──▶ C5 ──▶ C6 ──▶ C7 ──▶ C8 ──▶ C9 ──▶ C10                          │
 (text/spec/      │      │  ▲          │       │      │      │      │        │                           │
  .xosc/…)        │      ▼  │          ▼       ▼      ▼      ▼      ▼        ▼                           │
                  └─▶ C3 ◀──┘        repair loop ◀────── failed reports (loop budget + HITL) ────────────┘
                  (knowledge)
```

| ID | Component | What it does | Nature |
| --- | --- | --- | --- |
| C1 | Scenario Input | Ingest & normalize heterogeneous input into a validated `RequestSpec`; surface missing/contradictory fields as human-in-the-loop (HITL) questions | Deterministic |
| C2 | Scenario Understanding | Convert the request into structured `IntentSpec` (slot-filling); the **only LLM agent**, gated by a strict schema; falls back to an offline null proposer without an API key | LLM |
| C3 | Scenario Knowledge | Typed graph + esmini capability matrix answering "does the standard/simulator support this?" — provides evidence, never decisions | Deterministic |
| C4 | Scenario IR | Canonical machine-readable scenario *meaning*, independent of OpenSCENARIO XML | Deterministic |
| C5 | Scenario Generation | Compile the IR to executable `.xosc` (+ optional `.xodr`) via `scenariogeneration` | Deterministic |
| C6 | Scenario Validation | Executability funnel: XSD → OSC semantics → map topology (E08) → catalog bounds → esmini dry-run | Deterministic |
| C7 | esmini Simulation | Execute the scenario in esmini (headless or GUI) and capture states | Deterministic |
| C8 | Observation & Evaluation | Metrics (TTC, min distance, collision auto-fail, …) scored against a rulebook | Deterministic |
| C9 | Feedback & Improvement | Repair loop: rule-based fixes + parameter sweeps + constraint rotation; escalates to HITL when stuck | Deterministic |
| C10 | Scenario Management | Persist runs, artifacts, IR, metrics, and logs | Deterministic |
| CX | Orchestration | Fixed-order DAG, repair-loop budgets, HITL surfacing, run bookkeeping | DAG |

Full component contracts: [`component_inventory.md`](component_inventory.md) · data flow: [`component_connection_map.md`](component_connection_map.md).

## Key features

- **Compiler-style determinism** — one LLM proposer (C2), schema-gated; the pipeline never lets the LLM rewrite user-explicit values.
- **Executable-output guarantee** — a scenario is only "done" after it passes the C6 funnel *and* runs in real esmini (v3.7.2 verified).
- **Intent-driven map auto-selection** — picks the best-matching OpenDRIVE map from `assets/maps/` and the curated corpus in `assets/scenario_db/` (69 proven `.xosc` golden scenarios + 20 maps from the esmini ecosystem).
- **Automatic repair loop** — failed validations/evaluations feed C9, which applies rule-based mutations and parameter sweeps within a bounded budget before escalating to a human.
- **HITL by design** — missing parameters, contradictions, low LLM confidence, and unacked assumptions surface as explicit human questions instead of silent guesses.
- **Reproducible runs** — same request ⇒ same artifact hashes (regression-tested); artifacts persisted by C10 per run.

## Getting started

### Prerequisites

- **Python 3.11+**
- **esmini** (v3.7.2 verified) — a macOS build is bundled under `tools/` (`tools/esmini-bin_macOS.zip`, extracted to `tools/esmini-3.7.2/`); otherwise grab a release from the [esmini GitHub releases](https://github.com/esmini/esmini/releases).
- *(Optional)* `jq` — only needed if you enable the optional Cursor shell hook (see [below](#git-hooks--cursor-integration)).

### Install

```bash
git clone <this-repo> && cd scenariochef
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest   # 200+ tests should pass out of the box (esmini absent ⇒ C7 skips gracefully)
```

### Configure the environment

```bash
cp .env.example .env   # .env is git-ignored — never commit real keys
```

| Variable | Purpose |
| --- | --- |
| `C2_LLM_API_KEY` | Enables the real-LLM C2 path (OpenAI-compatible endpoint). Unset ⇒ offline null proposer. |
| `C2_LLM_MODEL` | Model id for C2 (default shown in `.env.example`). |
| `C2_LLM_BASE_URL` | OpenAI-compatible base URL for C2. |
| `ESMINI_BIN` | Absolute path to the esmini executable. Without it C7 reports `skipped_no_binary`. |
| `ESMINI_BUILD` | esmini build id recorded in `RunConfig` (e.g. `esmini-3.7.2`). |
| `ESMINI_ASSET_PATH` | Optional repo-root override for asset resolution. |

## Usage

The CLI ships as `scenariochef` (or `python -m scenariochef.cli`):

```bash
# Run the built-in demo request through the real pipeline
# (default: "ego follows lead in lane -1 at 20 m/s")
scenariochef

# Natural-language request with explicit parameters
scenariochef run --text "ego follows lead in lane -1 at 20 m/s" --param gap=15

# Show the esmini viewer window for the final simulation (default is headless)
scenariochef run --text "..." --gui

# Run the pipeline on an existing .xosc/.xodr file
scenariochef run path/to/scenario.xosc

# 20-trajectory demo sweep
scenariochef --demo
```

Each run prints the outcome, iteration count, validation/evaluation summaries, and the persisted artifact list (run id, IR, `.xosc`, metrics, logs).

### Dry-run driver (real LLM C2 end-to-end)

```bash
python scripts/dry_run.py --out-dir artifacts/dryrun   # loads .env, runs one full pass, writes summary.json + trace.log
DRY_RUN_OFFLINE=1 python scripts/dry_run.py            # force the offline null proposer
```

## Project layout

```
src/scenariochef/     Python package — one module per component (c1_input … c10_management, cx_orchestrator)
assets/maps/          OpenDRIVE maps available for auto-selection
assets/scenario_db/   Curated external scenario corpus (see INDEX.md / SOURCES.md for licenses)
assets/xsd/           OpenSCENARIO 1.0 XSD used by the S1 validation stage
docs/                 Blueprint, checkpoint (frozen decisions), contracts, research notes
docs/adr/             Architecture Decision Records 0001–0012
tests/                Unit, architecture, and integration tests (200+ cases)
scripts/              dry_run.py, git-hook installer, Cursor co-author blocker
.harness/             Self-improving development harness (see below)
tools/                Bundled esmini build
```

## Development

```bash
# Quality gate — lint + types + tests (mirrors .harness/gate.sh)
.venv/bin/ruff check src tests
.venv/bin/mypy
.venv/bin/python -m pytest -q
```

Run these (or `.harness/gate.sh`) before every commit — the gate must be green.

## Git hooks & Cursor integration

This repo is worked on with AI coding agents (including Cursor). Two mechanisms keep Cursor from inserting itself as a commit co-author — a recurring annoyance when agents append `Co-authored-by: Cursor` trailers. Set up **both** after cloning:

### 1. Git `commit-msg` hook (always active once installed)

`.githooks/commit-msg` strips any `Co-authored-by: … Cursor` trailer from commit messages before the commit is created. It is *not* installed automatically:

```bash
sh scripts/install-git-hooks.sh
# → installed commit-msg
# → Git hooks installed. Co-authored-by Cursor lines will be stripped on commit.
```

The script copies `.githooks/commit-msg` into `.git/hooks/` and marks it executable. It does not change git config, and it removes nothing except Cursor co-author lines — your own trailers are untouched.

### 2. Cursor rule (`.cursor/rules/git-commits.mdc`)

An always-apply Cursor rule tells the agent itself never to add Cursor co-author trailers or `--trailer "Co-authored-by: Cursor …"` flags. If you use Cursor with this repo, this rule is picked up automatically from `.cursor/rules/`; no setup needed.

### 3. Optional: Cursor shell hook (hard block)

For defense in depth you can make Cursor **deny** any `git commit` command that would add a Cursor co-author trailer, using the Cursor hooks feature:

1. Create `.cursor/hooks.json` in the repo root (or add to it) with:

   ```json
   {
     "hooks": {
       "beforeShellExecution": [
         {
           "command": "scripts/block-cursor-coauthor.sh",
           "matcher": "git\\s+commit"
         }
       ]
     }
   }
   ```

2. Ensure `jq` is on your `PATH` (the script parses the hook input JSON with it).

When Cursor then attempts a `git commit` containing `Co-authored-by: Cursor` (including `--trailer` forms), the script returns a `deny` permission with a message telling the agent to strip the trailers and retry. Everything else is allowed through unchanged.

### Commit-authorship policy

Only human authors the user explicitly requests may appear in commit messages. If a hook rejects your message, rewrite it without the Cursor co-author lines and commit again.

## Self-improving harness (`.harness/`)

ScenarioChef is developed inside a **learned harness** wrapped around the deterministic gate (ruff + mypy + pytest). The harness decides which historical lessons matter for a specific change, and compiles every work session into persistent memory so the same mistakes are not made twice.

> **Harness-first is mandatory:** new changes update `.harness/` (experiences/invariants) *before* the code — see `.harness/skills/harness-first-policy.md`.

### The loop

Run this in every work session and every subagent delegation:

```
1. BEFORE coding   →  .harness/retrieve.py --files <changed> --modules <touched>
                      paste the returned lesson block into the (sub)agent prompt
2. DURING coding   →  .harness/gate.sh        (ruff + mypy + pytest; --quick skips mypy)
                      never commit on red
3. AFTER coding    →  .harness/record.py --loop <id> --task "..." --agent <name>                          --outcome green|red|hitl --tests "N passed"
                      draft experience YAML → .harness/compile_experience.py
4. PERIODICALLY    →  .harness/promote.py observe|verify|supersede|disprove
                      recurring failures harden into executable tests (evals/regression/)
```

### Memory stores

| Store | Path | Holds | Strength |
| --- | --- | --- | --- |
| Invariants | `.harness/invariants/*.yaml` | Rules that must hold; each maps to a grep check or a pytest node id | Hard |
| Experiences | `.harness/experiences/*.yaml` | One file per learned mistake/success, with lifecycle fields | Soft → hard |
| Skills | `.harness/skills/*.md` | Repeatable procedures for recurring jobs (e.g. `implement-component.md`, `scenariogeneration-recipe.md`) | Medium |
| Repo model | `.harness/repo-model/components.json` | What exists: components, packages, dependencies | Fact |
| Trajectories | `.harness/trajectories/*.jsonl` | Raw per-session records the experience compiler distills | Raw material |
| Evals | `.harness/evals/regression/` | Executable proof: invariant → pytest node id (created when the first invariant hardens) | Hard |

### Experience lifecycle

Every experience carries `created_at`, `last_observed`, `last_verified`, `confidence`, `times_prevented`, `failure_count`, and a `status` of `ACTIVE | STALE | SUPERSEDED | DISPROVEN`. Mistakes harden along a promotion ladder:

```
episode (one occurrence)
  → rule (same class seen again)
  → executable invariant (recurring/high-risk: a pytest regression test owns it)
```

Only `evals/regression/` entries are enforced by the gate; everything else is retrieval context. **The gate, not the memory, is the authority.**

### Ground rules

- Retrieval is keyed on the *proposed change* (predicted files/modules/failure classes), not on the user prompt alone.
- `compile_experience.py` refuses duplicates and schema-invalid entries — no learned slop.
- Nothing under `.harness/` is executed at runtime: the product (`src/scenariochef`) never imports harness code.
- Checkpoints (`.harness/checkpoints.md`) are written by an independent subagent with its own memory — never by the orchestrator that did the work.

## Documentation map

| Document | Contents |
| --- | --- |
| [`docs/checkpoint.md`](docs/checkpoint.md) | Frozen low-level design decisions (decision registry) |
| [`docs/adr/`](docs/adr/README.md) | ADRs 0001–0012 — one per architectural decision (stack, C1–C10, CX) |
| [`component_inventory.md`](component_inventory.md) | Component roles, types, and contracts |
| [`component_connection_map.md`](component_connection_map.md) | Data flow and dependencies |
| [`docs/contracts.md`](docs/contracts.md) | Cross-component data contracts |
| [`docs/rulebook.md`](docs/rulebook.md) | C8 evaluation rulebook |
| [`docs/blueprint.md`](docs/blueprint.md) | Phase-1 blueprint and trace contract |
| [`docs/cx-implementation-notes.md`](docs/cx-implementation-notes.md) | Orchestrator implementation notes |
| [`research/`](research/reports/) | HASCO deep dive, LLM-scenario systems survey, competitor comparison |
| [`assets/scenario_db/INDEX.md`](assets/scenario_db/INDEX.md) | Curated scenario corpus index and licenses |

## License

MIT — see [LICENSE](LICENSE).
