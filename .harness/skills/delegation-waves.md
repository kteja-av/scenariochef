# Skill: Delegation waves for ScenarioChef implementation

How the orchestrator (GLM 5.3) delegates implementation to deepseek singularity paid subagents.

1. Before each wave, run `.harness/retrieve.py --files <predicted files> --modules <concepts>`
   and paste the lesson block into the subagent prompt.
2. One component (or one tightly-coupled pair) per subagent. Components depend on the
   contracts package — contracts land before any component wave.
3. Each subagent must: read ADR + contracts, implement, write tests, run
   `.harness/gate.sh --quick` (ruff + pytest), and report exit status. The orchestrator
   re-runs the full gate (with mypy) before committing.
4. Orchestrator commits per wave, single-line messages, no Cursor co-author trailers.
5. After each wave, record trajectory: `.harness/record.py --loop <wave> --task ... --agent
   deepseek-singularity-paid --outcome green|red|hitl`.
6. Wave order (dependency-sorted): contracts → (C1, C3) → (C4, C5) → (C6, C7) → (C8, C9)
   → (C10, C2) → CX + CLI + integration.
7. Checkpoint rule: the checkpoint writer subagent must be independent from the wave
   implementers — it reads git log + diff, not the wave transcripts.
