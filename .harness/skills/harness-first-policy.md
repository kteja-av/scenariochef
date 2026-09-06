# Skill: Harness-first policy (MANDATORY for all ScenarioChef changes)

Standing instruction from the project owner (2026-09-06): **every new change that goes
into ScenarioChef updates the `.harness/` folder FIRST, then the code.** Harness
maintenance is not optional cleanup after the fact — it is step one of any change.

## The order (violating this is a process failure)

1. **BEFORE coding** — write the harness entries that the change will have to satisfy:
   - New rule the code must follow → draft experience via
     `.venv/bin/python .harness/compile_experience.py --draft <draft.yaml> --yes`
     (it refuses duplicates and schema-invalid entries).
   - New property that must always hold → add `.harness/invariants/<ID>.yaml` with a
     `required_check` pointing at the test that will enforce it.
   - Run `.harness/retrieve.py --files <predicted files> --modules <concepts>` and paste
     the lesson block into the worker prompt.
2. **DURING coding** — implement to the recorded rule; run `.harness/gate.sh --quick`
   (full gate before commit; never commit red).
3. **AFTER coding** — `.harness/record.py --loop <id> --task ... --outcome green|red|hitl`;
   keep invariant `required_check` node ids real (the test must exist and pass).

## Why

- The experience compiler is the anti-slop gate: entries written after coding tend to be
  post-hoc justifications instead of falsifiable rules.
- Retrieval keyed on the proposed change only helps if the lesson for that change class
  already exists when the next agent picks up related work.
- Promotion ladder (`promote.py`) needs lifecycle fields set at creation time.

## Scope

Applies to feature work, research-driven waves, bug fixes, and refactors. Harness-only
commits (this file, checkpoints, trajectories) are exempt from the pre-code step but must
still pass the gate.
