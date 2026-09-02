# CX Orchestrator Implementation Notes (Wave D brief)

The DAG rewiring is the riskiest change: it touches every component seam at once. Design
decisions frozen here so the implementer does not have to re-derive them.

## Run flow (single request)

```
run_pipeline(request, run_id) -> PipelineResult
  1. C1  request_spec = run_c1(request, trajectory_id)
     - unresolved_fields/contradictions non-empty → return hitl_blocked with HitlRequests (CX-Q3)
  2. C3  evidence = run_c3(EvidenceQuery(feature_keys=DEFAULT_QUERY_KEYS), trajectory_id)
  3. C2  intent = run_c2(request_spec, trajectory_id, evidence=evidence)
     - intent.confidence < 0.7 or unknowns → hitl_blocked with HitlRequest(kind=low_confidence)
  4. LOOP (iteration n = 0..4, wall clock <= 300 s):
     a. C4 ir = run_c4(intent, trajectory_id, evidence)
        - if ir is a revised IR from C9, use it (C9-Q5)
     b. C5 instances = run_c5(ir)
     c. C6 reports = run_c6(instances, trajectory_id, scenario_ir=ir, preflight=...)
        - preflight = lambda gs: run_c7(gs, mode="preflight") ONLY invoked by C6 S6 (K3 unknown)
     d. any report FAIL → C9 repair = run_c9(report, trajectory_id, ir, iteration=n)
        - escalate_to_user → hitl_blocked (E08 path)
        - revised_ir → loop continues with it (iteration+1)
        - stop or no revised_ir → failed outcome (record everything in C10 first)
     e. all PASS → C7 full = run_c7(instance, mode="full") for each instance (or first, cap 3)
     f. C8 evaluation = run_c8(run_record, trajectory_id, scenario_ir=ir)
     g. C9 explore = run_c9(evaluation, trajectory_id, ir, iteration=n, last_metrics=...)
        - revised_ir → loop (explore iteration)
        - stop (max_iterations/no gain) → completed
  5. C10 persist every artifact with lineage map; log C2 proposal + C9 actions (C10-Q4).
```

## Enforcement notes

- C4, C6, C7 always execute in that order, every iteration, no skip (CX-Q5) — the
  architecture test greps for the canonical call order.
- LoopBudget literal: max_iterations=5, wall_clock_s=300 (CX-Q4). Wall clock measured
  per request with time.monotonic; a timeout mid-loop → persist what exists, outcome
  failed with stop reason recorded.
- HITL gates ONLY the four CX-Q3 kinds. The pipeline never blocks on WARN.
- Provenance: lineage map accumulates semantic hashes as the run proceeds
  (request→intent→ir→instance→validation→run→evaluation→feedback).
- The 20-trajectory demo stays as `run_demo()` (old behavior) so the CLI trace contract
  still demonstrates the skeleton path; new `main()` runs the real pipeline on a demo
  request when no args given, or on a file/arg when provided.

## CLI

```
scenariochef                      # demo request through the real pipeline
scenariochef --demo               # 20-trajectory skeleton-style demo (labels pool)
scenariochef run <file.xosc|xodr> # ingest a file
scenariochef run --text "..." [--param k=v ...]
```

Exit codes: 0 completed/hitl (HITL is a valid outcome, not an error), 1 failed gate
(tests/lint), 2 pipeline failure.

## Integration test (tests/test_integration_pipeline.py)

- happy path: NL+params request → PipelineResult outcome=completed; artifacts persisted
  under tmp artifacts dir; lineage contains all 8 kinds; trace log written.
- E08: request with lane=3 → hitl_blocked (escalation), lane unchanged in the IR that
  C6 rejected; artifacts persisted including the failed validation.
- esmini absent → pipeline still completes (RunRecord SKIPPED_NO_BINARY; evaluation
  objectives fail visibly with "no state data"; C9 explore stops).
- determinism: same request twice → identical semantic hashes at every stage (except
  run ids/timestamps).
