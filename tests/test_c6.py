"""C6 — Scenario Validation tests.

Covers the frozen S1→S6 funnel: XSD structural validity (S1), semantic checks (S2),
map/topology (S3, E08), physical bounds (S4), always-skipped S5, and the K3=unknown
dry-run (S6). IRs are hand-built the same way test_c5 does and compiled via
``compile_ir``; the happy path uses a reach-position trigger so the compiled output is
genuinely valid against the OSC 1.0 XSD (SC100 + XSC-0001).
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Callable

from scenariochef.c5_generation.runtime import compile_ir
from scenariochef.c6_validation.runtime import run_c6, validate_scenario
from scenariochef.contracts.common import (
    FrameTag,
    Position,
    SupportLevel,
    TraceMeta,
)
from scenariochef.contracts.generated_scenario import GeneratedScenario, XoscArtifact
from scenariochef.contracts.intent_spec import ActionType, TriggerIntent, TriggerKind
from scenariochef.contracts.run_record import RunConfig, RunRecord, RunStatus
from scenariochef.contracts.scenario_ir import (
    IRActor,
    IRBehavior,
    IRHeader,
    IRMap,
    ScenarioIR,
)
from scenariochef.contracts.validation_report import ErrorTaxonomy, Stage, Status

SHA256_PLACEHOLDER = "0" * 64


def _meta(request_id: str = "REQ-0001") -> TraceMeta:
    return TraceMeta(request_id=request_id, trajectory_id=request_id, produced_by="test-c6")


def _header(request_id: str = "REQ-0001") -> IRHeader:
    return IRHeader(request_id=request_id, intent_spec_hash="abc", esmini_pin="esmini-0.10")


def _map() -> IRMap:
    return IRMap(map_asset_id="straight_2lane", sha256=SHA256_PLACEHOLDER)


def _spawn(lane: int, s: float) -> Position:
    return Position(frame=FrameTag.LANE_RELATIVE, road_id=1, lane_id=lane, s_m=s)


def _actor(name: str, lane: int, s: float, speed: float) -> IRActor:
    return IRActor.model_construct(
        name=name,
        kind="vehicle",
        bbox_ref="car_mid",
        spawn=_spawn(lane, s),
        initial_speed_mps=speed,
    )


def _reach() -> TriggerIntent:
    # A reach-position trigger keeps the compiled xosc OSC 1.0-XSD-valid.
    return TriggerIntent(
        kind=TriggerKind.REACH_POSITION, params={"s_m": 50.0, "lane_id": -1, "road_id": 1}
    )


def _follow_ir(**kwargs) -> ScenarioIR:
    """A 2-actor follow IR (Ego follows Lead), reach-position triggered."""
    ego = kwargs.get("ego", _actor("Ego", -1, 0.0, 15.0))
    lead = kwargs.get("lead", _actor("Lead", -1, 20.0, 15.0))
    behaviors = kwargs.get("behaviors")
    if behaviors is None:
        behaviors = [
            IRBehavior(
                actor="Ego",
                action=ActionType.FOLLOW,
                params={"target_speed": 15.0},
                trigger=_reach(),
            )
        ]
    return ScenarioIR(
        meta=_meta(),
        header=_header(),
        map=_map(),
        actors=[ego, lead],
        behaviors=behaviors,
        feature_keys=["osc.action.SpeedChange"],
    )


def _solo_ir(behavior: IRBehavior, actors: list[IRActor], keys=None) -> ScenarioIR:
    return ScenarioIR(
        meta=_meta(),
        header=_header(),
        map=_map(),
        actors=actors,
        behaviors=[behavior],
        feature_keys=keys or ["osc.action.SpeedChange"],
    )


def _wrap(content: str) -> GeneratedScenario:
    """Wrap raw xosc content into a GeneratedScenario (fresh hash)."""
    return GeneratedScenario.model_construct(
        meta=_meta(),
        scenario_name="REQ-0001-v0",
        xosc=XoscArtifact(
            content=content,
            path=None,
            sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        ),
        xodr=None,
        parameter_bindings=[],
        variation_index=0,
        variation_count=1,
        k3_flags=[],
        suggestions=[],
    )


def _pretend(status: RunStatus) -> Callable[[GeneratedScenario], RunRecord]:
    config = RunConfig(
        esmini_build="esmini-0.10", dt_s=0.05, seed=42, max_time_s=30.0, headless=True
    )

    def _call(_gs: GeneratedScenario) -> RunRecord:
        return RunRecord.model_construct(
            meta=_meta(),
            config=config,
            mode="preflight",
            status=status,
        )

    return _call


# --- S1: XSD ---------------------------------------------------------------


def test_happy_follow_passes_and_s5_s6_skipped():
    gs = compile_ir(_follow_ir())[0]
    report = validate_scenario(gs)
    assert report.outcome is Status.PASS
    by_stage = {r.stage: r for r in report.stages}
    assert by_stage[Stage.S1].status is Status.PASS
    assert by_stage[Stage.S2].status is Status.PASS
    assert by_stage[Stage.S5].status is Status.SKIPPED
    assert by_stage[Stage.S6].status is Status.SKIPPED


def test_broken_xml_fails_s1_and_short_circuits():
    good = compile_ir(_follow_ir())[0]
    broken = good.xosc.content.replace("<Storyboard>", "<Storyboard").replace("/>", "bogus")
    gs = good.model_copy(update={"xosc": XoscArtifact(
        content=broken,
        sha256=hashlib.sha256(broken.encode("utf-8")).hexdigest(),
    )})
    report = validate_scenario(gs)
    assert report.outcome is Status.FAIL
    by_stage = {r.stage: r for r in report.stages}
    s1 = by_stage[Stage.S1]
    assert s1.status is Status.FAIL
    assert s1.errors[0].code is ErrorTaxonomy.XSD_INVALID
    assert len(s1.errors[0].message) <= 200
    # S2..S6 all SKIPPED after the S1 FAIL (short-circuit).
    for after in (Stage.S2, Stage.S3, Stage.S4, Stage.S5, Stage.S6):
        assert by_stage[after].status is Status.SKIPPED


# --- S3: map / topology (E08) -----------------------------------------------


def test_target_lane_missing_from_map_fails_s3_with_repair_hint():
    lc = IRBehavior(
        actor="Ego", action=ActionType.LANE_CHANGE, params={"target_lane": 3}, trigger=_reach()
    )
    ir = _solo_ir(lc, [_actor("Ego", -1, 0.0, 15.0)], keys=["osc.action.LaneChange"])
    gs = compile_ir(ir)[0]
    report = validate_scenario(gs, scenario_ir=ir)
    assert report.outcome is Status.FAIL
    s3 = next(r for r in report.stages if r.stage is Stage.S3)
    assert s3.status is Status.FAIL
    err = s3.errors[0]
    assert err.code is ErrorTaxonomy.MAP_TOPOLOGY
    assert err.repair_hint
    assert "lane 3 does not exist on road 1" in err.repair_hint


def test_spawn_beyond_road_length_fails_s3():
    ego = _actor("Ego", -1, 250.0, 15.0)
    lead = _actor("Lead", -1, 260.0, 15.0)
    ir = _follow_ir(ego=ego, lead=lead)
    gs = compile_ir(ir)[0]
    report = validate_scenario(gs, scenario_ir=ir)
    assert report.outcome is Status.FAIL
    s3 = next(r for r in report.stages if r.stage is Stage.S3)
    assert s3.status is Status.FAIL
    assert any(e.code is ErrorTaxonomy.MAP_TOPOLOGY for e in s3.errors)


# --- S2 / S4: physical bounds -------------------------------------------------


def test_negative_speed_fails_physical_bounds():
    ego = _actor("Ego", -1, 0.0, -5.0)
    brake = IRBehavior(
        actor="Ego",
        action=ActionType.BRAKE,
        params={"target_speed": -5.0},
        trigger=_reach(),
    )
    ir = _solo_ir(brake, [ego])
    gs = compile_ir(ir)[0]
    report = validate_scenario(gs, scenario_ir=ir)
    assert report.outcome is Status.FAIL
    codes = [
        e.code
        for r in report.stages
        for e in r.errors
        if e.severity.value == "error"
    ]
    assert ErrorTaxonomy.PHYSICAL_BOUNDS in codes


# --- S6: dry-run ---------------------------------------------------------------


def _teleport_gs() -> GeneratedScenario:
    tel = IRBehavior(
        actor="Ego",
        action=ActionType.TELEPORT,
        params={"s_m": 50.0, "lane_id": -1, "road_id": 1},
        trigger=_reach(),
    )
    ir = _solo_ir(
        tel,
        [_actor("Ego", -1, 0.0, 15.0)],
        keys=["osc.action.Teleport", "osc.action.SpeedChange"],
    )
    gs = compile_ir(ir)[0]
    assert any(f.support is SupportLevel.UNKNOWN for f in gs.k3_flags)
    return gs


def test_dry_run_completed_passes():
    report = validate_scenario(_teleport_gs(), preflight=_pretend(RunStatus.COMPLETED))
    s6 = next(r for r in report.stages if r.stage is Stage.S6)
    assert s6.status is Status.RUNS
    assert report.outcome is Status.PASS


def test_dry_run_crashed_fails_runtime_compat():
    report = validate_scenario(_teleport_gs(), preflight=_pretend(RunStatus.CRASHED))
    s6 = next(r for r in report.stages if r.stage is Stage.S6)
    assert s6.status is Status.FAIL
    assert any(
        e.code is ErrorTaxonomy.RUNTIME_COMPAT and e.severity.value == "error"
        for e in s6.errors
    )
    assert report.outcome is Status.FAIL


def test_dry_run_hung_fails_runtime_compat():
    report = validate_scenario(_teleport_gs(), preflight=_pretend(RunStatus.HUNG))
    s6 = next(r for r in report.stages if r.stage is Stage.S6)
    assert s6.status is Status.FAIL
    assert report.outcome is Status.FAIL


def test_dry_run_no_preflight_skipped():
    report = validate_scenario(_teleport_gs(), preflight=None)
    s6 = next(r for r in report.stages if r.stage is Stage.S6)
    assert s6.status is Status.SKIPPED
    assert report.outcome is Status.PASS


def test_dry_run_no_binary_warns_but_passes():
    report = validate_scenario(_teleport_gs(), preflight=_pretend(RunStatus.SKIPPED_NO_BINARY))
    s6 = next(r for r in report.stages if r.stage is Stage.S6)
    assert s6.status is Status.WARN
    assert any(e.code is ErrorTaxonomy.RUNTIME_COMPAT for e in s6.errors)
    assert report.outcome is Status.PASS


# --- S2: unreachable trigger (WARN-and-pass, C6-Q3) -----------------------------


def test_unreachable_speed_headway_trigger_warns_and_passes():
    """A SpeedCondition threshold above reachable bound surfaces a WARN, not a FAIL."""
    gs = _inject_speed_condition(80.0)
    report = validate_scenario(gs)
    assert report.outcome is Status.PASS
    s2 = next(r for r in report.stages if r.stage is Stage.S2)
    assert s2.status is Status.PASS
    assert any(e.code is ErrorTaxonomy.UNREACHABLE_TRIGGER for e in s2.errors)


def _inject_speed_condition(value: float) -> GeneratedScenario:
    """Embed an OSC 1.0-valid SpeedCondition into a compiled follow scenario."""
    base = compile_ir(_follow_ir())[0].xosc.content
    root = ET.fromstring(base)
    econd = root.find(".//StartTrigger/.//EntityCondition")
    assert econd is not None
    for child in list(econd):
        econd.remove(child)
    sc = ET.SubElement(econd, "SpeedCondition")
    sc.set("value", f"{value}")
    sc.set("rule", "greaterThan")
    return _wrap(ET.tostring(root, encoding="unicode"))


# --- S3 reads lane ids from the actual xodr -------------------------------------


def test_lane_ids_read_from_actual_xodr_lane_2_fails():
    """straight_2lane.xodr has lanes {1, 0, -1}; lane 2 must be rejected."""
    lc = IRBehavior(
        actor="Ego", action=ActionType.LANE_CHANGE, params={"target_lane": 2}, trigger=_reach()
    )
    ir = _solo_ir(lc, [_actor("Ego", -1, 0.0, 15.0)], keys=["osc.action.LaneChange"])
    gs = compile_ir(ir)[0]
    report = validate_scenario(gs, scenario_ir=ir)
    s3 = next(r for r in report.stages if r.stage is Stage.S3)
    assert s3.status is Status.FAIL
    assert any(e.code is ErrorTaxonomy.MAP_TOPOLOGY for e in s3.errors)
    assert "lane 2" in s3.errors[0].repair_hint or "lane 2" in s3.errors[0].message


# --- run_c6 orchestration (trace + per-scenario reports) -------------------------


def test_run_c6_validates_each_scenario():
    gs = compile_ir(_follow_ir())[0]
    reports = run_c6([gs], trajectory_id="REQ-0001")
    assert len(reports) == 1
    assert reports[0].outcome is Status.PASS