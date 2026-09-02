"""ScenarioChef typed contracts.

Single source of truth for the Pydantic models exchanged across every component boundary
(see ``docs/contracts.md``). Each component consumes/produces ONLY these types plus
primitives. Import public models from here, or from their defining submodule.
"""

from . import (
    common,
    evaluation_report,
    evidence_bundle,
    feedback_action,
    generated_scenario,
    intent_spec,
    orchestration,
    persistence_record,
    request_spec,
    run_record,
    scenario_ir,
    validation_report,
)
from .common import (
    FrameTag,
    Modality,
    Position,
    Range,
    Severity,
    SlotProvenance,
    SupportLevel,
    TraceMeta,
    Unit,
    content_hash,
    content_hash_eq,
    semantic_hash,
    semantic_hash_eq,
)
from .evaluation_report import (
    DataSource,
    EvaluationReport,
    Metric,
    MetricName,
    ObjectiveResult,
)
from .evidence_bundle import (
    Authority,
    EvidenceBundle,
    EvidenceItem,
    EvidenceQuery,
    MapAsset,
)
from .feedback_action import FeedbackAction
from .generated_scenario import (
    GeneratedScenario,
    K3Flag,
    ParameterBinding,
    XodrArtifact,
    XoscArtifact,
)
from .intent_spec import (
    ActionType,
    ActorIntent,
    ActorRole,
    ConstraintIntent,
    IntentSpec,
    ManeuverIntent,
    ObjectiveKind,
    ObjectiveStub,
    TriggerIntent,
    TriggerKind,
)
from .orchestration import (
    HitlKind,
    HitlRequest,
    LoopBudget,
    PipelineOutcome,
    PipelineResult,
)
from .persistence_record import ActionLog, LineageMap, PersistenceRecord
from .request_spec import (
    Contradiction,
    InputFile,
    RequestSpec,
    UnresolvedField,
)
from .run_record import HangInfo, RunConfig, RunRecord, RunStatus
from .scenario_ir import (
    IRActor,
    IRBehavior,
    IRConstraint,
    IRHeader,
    IRMap,
    IRSuggestion,
    ScenarioIR,
)
from .validation_report import (
    ErrorTaxonomy,
    Stage,
    StageResult,
    Status,
    ValidationError,
    ValidationReport,
)

__all__ = [
    # modules
    "common",
    "request_spec",
    "intent_spec",
    "evidence_bundle",
    "scenario_ir",
    "generated_scenario",
    "validation_report",
    "run_record",
    "evaluation_report",
    "feedback_action",
    "persistence_record",
    "orchestration",
    # common
    "Modality",
    "FrameTag",
    "SupportLevel",
    "Severity",
    "Unit",
    "Position",
    "Range",
    "SlotProvenance",
    "TraceMeta",
    "content_hash",
    "content_hash_eq",
    "semantic_hash",
    "semantic_hash_eq",
    # request_spec
    "RequestSpec",
    "InputFile",
    "UnresolvedField",
    "Contradiction",
    # intent_spec
    "IntentSpec",
    "ActorIntent",
    "ActorRole",
    "ManeuverIntent",
    "TriggerIntent",
    "ConstraintIntent",
    "ObjectiveStub",
    "ActionType",
    "TriggerKind",
    "ObjectiveKind",
    # evidence_bundle
    "EvidenceBundle",
    "EvidenceItem",
    "MapAsset",
    "EvidenceQuery",
    "Authority",
    # scenario_ir
    "ScenarioIR",
    "IRActor",
    "IRBehavior",
    "IRConstraint",
    "IRSuggestion",
    "IRHeader",
    "IRMap",
    # generated_scenario
    "GeneratedScenario",
    "XoscArtifact",
    "XodrArtifact",
    "ParameterBinding",
    "K3Flag",
    # validation_report
    "ValidationReport",
    "StageResult",
    "ValidationError",
    "Stage",
    "Status",
    "ErrorTaxonomy",
    # run_record
    "RunRecord",
    "RunConfig",
    "HangInfo",
    "RunStatus",
    # evaluation_report
    "EvaluationReport",
    "Metric",
    "ObjectiveResult",
    "MetricName",
    "DataSource",
    # feedback_action
    "FeedbackAction",
    # persistence_record
    "PersistenceRecord",
    "LineageMap",
    "ActionLog",
    # orchestration
    "HitlRequest",
    "HitlKind",
    "LoopBudget",
    "PipelineResult",
    "PipelineOutcome",
]