# ScenarioChef Self-Improving Harness

A learned harness wrapped around the deterministic gate (tests/lint/types). It makes the
harness decide which 5–15 historical lessons matter for a specific change, and compiles
every session's outcome into persistent memory.

**Harness-first is mandatory:** new changes update `.harness/` (experiences/invariants)
BEFORE the code — see `skills/harness-first-policy.md`.

Loop (every work session, every subagent delegation):

```
1. BEFORE coding     →  .harness/retrieve.py --files ... --modules ...
                        paste the output block into the (sub)agent prompt
2. DURING coding     →  .harness/gate.sh  (ruff + mypy + pytest)
                        never commit on red
3. AFTER coding      →  write .harness/trajectories/<id>.jsonl
                        draft experience YAML → .harness/compile_experience.py
4. PERIODICALLY      →  .harness/promote.py observe|verify|supersede|disprove
                        recurring failures harden into tests under evals/regression/
```

## Memory stores

| Store | Path | Holds | Strength |
| --- | --- | --- | --- |
| Invariants | `invariants/*.yaml` | rules that must hold; each maps to a grep check or pytest node id | hard |
| Experiences | `experiences/*.yaml` | one file per learned mistake/success with lifecycle fields | soft→hard |
| Skills | `skills/*.md` | repeatable procedures for recurring jobs | medium |
| Repo model | `repo-model/components.json` | what exists: components, packages, dependencies | fact |
| Evals | `evals/regression/catalog.json` | executable proof: invariant → pytest node id | hard |

## Experience lifecycle

Every experience carries `created_at`, `last_observed`, `last_verified`, `confidence`,
`times_prevented`, `failure_count`, `status` (`ACTIVE|STALE|SUPERSEDED|DISPROVEN`).

Promotion ladder (a mistake gradually hardens):

```
episode (one occurrence)
  → rule (same class seen again; correct_rule field is trusted)
  → executable invariant (recurring/high-risk: a pytest regression test owns it)
```

Only `evals/regression/` entries are enforced by the gate. Everything else is retrieval
context — the gate, not the memory, is the authority.

## Rules of the loop

- Retrieval is keyed on the *proposed change* (predicted files/modules/failure classes),
  not on the user prompt alone.
- The deterministic gate runs before every commit; a red gate blocks the commit.
- `compile_experience.py` refuses duplicates and schema-invalid entries — no learned slop.
- Nothing in `.harness/experiences|skills|repo-model` is executed at runtime; the product
  (`src/scenariochef`) never imports harness code.
- Checkpoints (`.harness/checkpoints.md`) are written by an independent subagent with its
  own memory, never by the orchestrator that did the work.
