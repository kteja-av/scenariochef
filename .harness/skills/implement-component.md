# Skill: Implementing a ScenarioChef component runtime

Standard procedure when implementing any C1–C10 component in `src/scenariochef/<pkg>/runtime.py`.

1. Read the component's ADR in `docs/adr/` and its decision rows in `docs/checkpoint.md`.
   The ADR is the contract; do not invent behavior the ADR forbids.
2. Check the contracts package first: `src/scenariochef/contracts/`. If your component's
   input/output model exists there, use it. If you need a new field, extend the contract
   — never invent a private dict format.
3. Keep the public surface: `run_cN(...)` with typed signature. CX calls only these APIs.
4. Deterministic only (except C2). No LLM, no random without seed, no wall-clock reads
   in logic. Reproducibility: same input → same output.
5. Trace: call `trace.emit(step, "CN", "IN"|"OUT", token, trajectory_id)` at boundaries
   exactly like the skeleton does. The trace contract is in `docs/blueprint.md` §5.
6. Tests: add `tests/test_<component>.py` with at least one happy path and one failure
   path per ADR-listed behavior. Run `.harness/gate.sh` before committing.
7. Never rewrite user-explicit slots (invariant ARCH-0002). Never write runtime facts
   into C3 (ARCH-0003). Never skip/reorder C4/C6/C7 (ARCH-0004).
8. Commit: single-line message, no co-author trailers naming Cursor.
