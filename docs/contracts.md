# ScenarioChef Contracts Spec — Phase 1 Implementation

Single source of truth for the Pydantic contracts in `src/scenariochef/contracts/`.
Every component exchanges ONLY these types (plus primitives) across boundaries.
Derived from: ADR-0002..0012, docs/checkpoint.md frozen decisions, docs/blueprint.md.

Rules that apply to every contract:

- Pydantic v2, `extra="forbid"` everywhere — unknown fields are contract violations, not
  silent passthrough.
- Every cross-boundary object carries `meta: TraceMeta` (request_id, trajectory_id,
  created_at ISO-8601 UTC, component that produced it).
- Units are explicit in field names (`_m`, `_mps`, `_mps2`, `_s`) — never bare floats.
- `model_config = ConfigDict(frozen=True)` for specs that downstream components must not
  mutate (RequestSpec, IntentSpec, ScenarioIR canonical form). RevisedIR is a new object,
  never in-place mutation (C9-Q5).
- JSON-serializable (`model_dump_json`) for C10 persistence; every model gets a
  `content_hash()` (sha256 of canonical JSON dump, sorted keys).

## Shared enums and value objects (`contracts/common.py`)

```python
class Modality(StrEnum):        # C1-Q1 — all four Phase-1 modalities
    NL_PARAMS = "nl_params"     # natural language + parameter dict
    XOSC_XODR = "xosc_xodr"     # existing file ingest
    CRASH_NARRATIVE = "crash_narrative"
    MULTIMODAL = "multimodal"

class FrameTag(StrEnum):        # C4-Q2 — mandatory on every position
    ROAD_RELATIVE = "road_relative"   # s/t/h coordinates on a road
    LANE_RELATIVE = "lane_relative"   # road_id + lane_id + s-offset
    CARTESIAN = "cartesian"           # x/y/z world

class SupportLevel(StrEnum):    # C3-Q1/K3 matrix edge values
    SUPPORTS = "supports"; PARTIAL = "partial"; UNSUPPORTED = "unsupported"; UNKNOWN = "unknown"

class Severity(StrEnum): ERROR="error"; WARN="warn"; INFO="info"

class Unit(StrEnum): M="m"; MPS="mps"; MPS2="mps2"; S="s"; NONE="none"
```

`Position` (value object): `frame: FrameTag` (required), `road_id: int|None`,
`lane_id: int|None`, `s_m: float|None`, `t_m: float|None`, `x_m/y_m/z_m: float|None`.
Validator: fields must be consistent with the frame (lane_relative ⇒ road_id+lane_id+s_m;
cartesian ⇒ x_m/y_m; road_relative ⇒ road_id+s_m). Untagged or inconsistent ⇒ ValidationError.

`Range`: `min`/`max` floats + `unit: Unit` (C4-Q4 — intervals only, no distributions).

`SlotProvenance`: marks user-explicit values so C2/C9 can never rewrite them (C2-Q3, C9-Q6):
`source: Literal["user_explicit","llm_proposed","c3_default","c9_mutation"]`,
`accepted_by_c1: bool`, `accepted_by_c2: bool`. Defaults from C3 need BOTH acks before
C4 binds (DERIVED-3); validator on IntentSpec enforces this for `c3_default` slots.

## C1 → RequestSpec (`contracts/request_spec.py`)

- `modality: Modality`
- `raw: str` (normalized text or file reference)
- `params: dict[str, float|int|str]` (explicit user parameters, if any)
- `input_files: list[InputFile]` where InputFile = `{path, kind: xosc|xodr|other, sha256}`
- `unresolved_fields: list[UnresolvedField]` — `{field_path, reason, options?}`; non-empty
  ⇒ CX must run HITL before C2 (C1-Q2)
- `contradictions: list[Contradiction]` — `{field_paths, description}`; non-empty ⇒ HITL (C1-Q4)
- `acknowledged_assumptions: list[str]` — C3 default ids C1 has acked (C1-Q3)
- frozen.

## C2 → IntentSpec (`contracts/intent_spec.py`)

- `actors: list[ActorIntent]` — `{name, kind: vehicle|pedestrian|static, role: ego|target,
  initial_position: Position, initial_speed_mps: float|Range, slot: SlotProvenance per field}`
- `maneuvers: list[ManeuverIntent]` — `{actor: str, action: ActionType, params: dict,
  slot: SlotProvenance}`; ActionType enum covers Phase-1 subset: `speed_change, lane_change,
  follow, brake, cut_in, cross_path, teleport`
- `triggers: list[TriggerIntent]` — `{kind: time|speed_headway|reach_position|time_headway,
  params: dict (with units in keys), slot}`
- `constraints: list[ConstraintIntent]` — `{name, value: float|Range, unit}`
- `objectives: list[ObjectiveStub]` — `{id, kind: ttc|pet|collision|completion|custom,
  description, params}` (C4-Q3: stubs only — thresholds live in C8 rulebook)
- `confidence: float` (0..1); `unknowns: list[str]` — low confidence ⇒ HITL (C2-Q2)
- `c3_evidence_refs: list[str]` — evidence item ids used
- validator: any `c3_default` slot with missing ack ⇒ error (DERIVED-3).
- frozen.

## C3 → EvidenceBundle (`contracts/evidence_bundle.py`)

- `definitions: list[EvidenceItem]`
- `constraints: list[EvidenceItem]`
- `examples: list[EvidenceItem]`
- `compatibility: list[EvidenceItem]`
- `provenance: list[EvidenceItem]`
- EvidenceItem = `{id, feature_key (e.g. "osc.action.LaneChange"), claim, source_ref,
  authority: xsd|esmini_docs|catalog|domain (C3-Q8 ranking), fact_or_assumption:
  fact|assumption, accepted_by_c1: bool, accepted_by_c2: bool, support: SupportLevel,
  simulator_build: str, excerpt: str}`
- `map_assets: list[MapAsset]` — `{id, path, sha256, version}` (identity only — Q3).
- Query in: `EvidenceQuery` = `{feature_keys: list[str], simulator_build: str,
  map_id: str|None}`. C3 never answers topology (Q3); never writes at runtime (Q4);
  OSC-silent ⇒ `support=unknown` (Q2).

## C4 → ScenarioIR (`contracts/scenario_ir.py`)

- `header: {request_id, intent_spec_hash, esmini_pin: str}` — pin comes from C3 K3 (C3-Q5)
- `map: {map_asset_id: str, sha256}` — identity only
- `actors: list[IRActor]` — name, kind, bbox ref (catalog entry id), spawn Position (frame-tagged), initial speed
- `behaviors: list[IRBehavior]` — `{actor, action: ActionType, params, trigger: TriggerIntent|None,
  start_condition}` — Scenic-like declarative behaviors
- `constraints: list[IRConstraint]` — named scalar/range constraints with units
- `objectives: list[ObjectiveStub]` — passed through from IntentSpec unchanged
- `suggestions: list[IRSuggestion]` — `{code, message, field_path, proposed_value}` —
  diagnostics ONLY; canonical fields untouched (C4-Q5, DERIVED-10)
- `feature_keys: list[str]` — OSC features used (drives C3 K3 lookup + C6 S6 decision)
- frozen; `suggestions` ride along but never mutate canonical fields.

## C5 → GeneratedScenario (`contracts/generated_scenario.py`)

- `scenario_name: str`
- `xosc: XoscArtifact` — `{content: str, path: Path|None, sha256}`
- `xodr: XodrArtifact|None` (optional map emission)
- `parameter_bindings: list[ParameterBinding]` — `{param, value, source_range: Range|None,
  ir_path}` — concrete values chosen for range expansion (C5-Q2)
- `variation_index: int`, `variation_count: int` — C5 expands ranges into N concrete
  instances (cap: 8 per range axis, 32 total, deterministic order)
- `k3_flags: list[K3Flag]` — `{feature_key, support: SupportLevel}`; features the IR used
  that K3 marks unknown/unsupported flow here (C5-Q3 — never substituted)
- `suggestions: list[IRSuggestion]` — passed through untouched (DERIVED-13)
- list of one-or-more instances comes from `run_c5(ir) -> list[GeneratedScenario]`.

## C6 → ValidationReport (`contracts/validation_report.py`)

- `stages: list[StageResult]` — one per S1..S6 in order:
  - S1 structural (xmlschema/lxml XSD validation against OSC 1.0 XSD)
  - S2 semantic (entityRef/catalog references, speed sign checks, trigger param sanity)
  - S3 map/topology (lane existence against xodr; E08 lives here)
  - S4 catalog + physical bounds (catalog facts + acked assumptions only, C6-Q5)
  - S5 = SKIPPED always (C6-Q1)
  - S6 dry-run = RUNS only when any k3_flag is unknown (C6-Q2); calls C7 preflight
- StageResult = `{stage: S1..S6, status: PASS|FAIL|WARN|SKIPPED|RUNS, errors: list[ValidationError]}`
- ValidationError = `{code: ErrorTaxonomy, severity, message, location (xpath or field path),
  repair_hint: str|None}`
- ErrorTaxonomy enum (C6 report taxonomy): `XSD_INVALID, SEMANTIC_REF, MAP_TOPOLOGY (E08),
  PHYSICAL_BOUNDS, UNREACHABLE_TRIGGER (E09 — WARN-and-pass, C6-Q3), RUNTIME_COMPAT (E10),
  INTERNAL`
- `outcome: PASS|FAIL` — short-circuit on first FAIL stage (C6-Q4); stages after the
  short-circuit are SKIPPED.

## C7 → RunRecord (`contracts/run_record.py`)

- `config: RunConfig` — mandatory `esmini_build: str, dt_s: float, seed: int,
  max_time_s: float`; optional `headless: bool = True, osi: bool = False` (C7-Q2, DERIVED-14)
- `mode: preflight|full` (C7-Q1)
- `exit_code: int|None`, `stdout_tail: str`, `stderr_tail: str` (last 8 KB)
- `simulation_csv_path: Path|None` (parsed states), `osi_trace_path: Path|None`
- `hang: HangInfo|None` — `{reason: wall_clock|step_cap, limit_value}` (C7-Q4 — either trips)
- `duration_s: float`, `sim_time_s: float|None`
- `status: COMPLETED|HUNG|CRASHED|SKIPPED_NO_BINARY`
- esmini binary discovered via env `ESMINI_BIN` or PATH; absent ⇒ SKIPPED_NO_BINARY with
  stderr note (never a Python exception — the pipeline must stay runnable without esmini).

## C8 → EvaluationReport (`contracts/evaluation_report.py`)

- `metrics: list[Metric]` — Metric = `{name: ttc|pet|collision|completion, value: float,
  unit, actor_pair: tuple[str,str]|None}`; TTC ALWAYS paired with PET per pair (C8-Q4)
- `objective_results: list[ObjectiveResult]` — `{stub_id, objective_kind, passed: bool,
  threshold_source: str (rulebook entry id), detail}`
- `rulebook_version: str`, `data_source: osi|csv` (C8-Q5)
- `failure_class: str|None` — E-taxonomy classification when objectives fail
- Thresholds come from `c8_evaluation/rulebook.yaml`, never invented (C8-Q1).
- Deterministic TTC/PET from CSV states: TTC(t) = gap/(closing speed) when closing>0;
  PET = time between actor entries to the conflict point. No numpy requirement — stdlib.

## C9 → FeedbackAction (`contracts/feedback_action.py`)

- `type: repair|explore` (C9-Q1 hard split)
- `revised_ir: ScenarioIR|None` — a NEW object; user_explicit slots byte-identical (C9-Q5/Q6)
- `rationale: str`, `iteration: int` (0-based)
- `escalate_to_user: bool` + `escalation_reason: str|None` — E08-class topology FAILs set
  this instead of repairing (DERIVED-16)
- `stop: bool` + `stop_reason: one_of[max_iterations, no_metric_gain, repaired, none]` (C9-Q4)
- Explore actions carry `param_sweep: list[ParameterBinding]` — next candidate values.

## C10 → PersistenceRecord (`contracts/persistence_record.py`)

- `record_id: str` (SC-<run>-<seq>), `run_id: str`, `object_kind`, `object_hash: str`,
  `path: Path`, `lineage: LineageMap` — hashes of every upstream artifact in the run
  (request→intent→ir→generated→validation→run→evaluation→feedback, C10 full lineage)
- `actions: list[ActionLog]` — C2 proposals and C9 actions logged as actions (C10-Q4):
  `{actor_component: C2|C9, action_kind: propose|repair|explore, payload_hash, ts}`
- SQLite schema in `c10_management/schema.sql`; content-addressed files under
  `artifacts/<run_id>/`; no dedup (C10-Q5), keep all runs (C10-Q3).

## CX orchestration types (`contracts/orchestration.py`)

- `HitlRequest` = `{kind: missing_param|contradiction|low_confidence|assumption_ack,
  field_paths: list[str], question: str, options: list[str]|None}` — CX-Q3 kinds only
- `LoopBudget` = `{max_iterations: 5, wall_clock_s: 300}` — CX-Q4 (frozen)
- `PipelineResult` = `{run_id, request_id, outcome: completed|hitl_blocked|failed,
  iterations: int, validation_outcome, evaluation_summary, artifacts: dict}`
- CX never skips/reorders C4/C6/C7 (CX-Q5); tools are C1–C10 APIs only (CX-Q2).

## Trace contract (unchanged from blueprint §5)

`[step:NN] CC DIR <token>` — components still call `trace.emit`; tokens are now
`<kind:hash8>` (e.g. `<ScenarioIR:1a2b3c4d>`) instead of placeholder strings.
`scenario_labels.py` stays for the deterministic demo pool.
