"""Core data models for The Door — package façade.

Re-exports every model from the per-domain submodules so that existing
`from the_door.models import X` imports continue to work unchanged.
Filing axis = domain (PMEST citation order: domain > lifecycle > role).
When adding a new model: file it by domain first; summaries/errors follow
their domain (no role-based files); never reorder within a submodule
(default_factory forward refs are evaluated at class-definition time).
"""
from __future__ import annotations

from .extraction import (
    FileInfo, ASTNode, Edge, TopologyEntry,
    ExtractionError, ExtractionResult, TopologyResult, StructureJSON,
)
from .analysis import (
    Feature, FeatureRelation, L1Output,
    CheckResult, ValidationResult,
    L1_5Block, BlockRelation, InfrastructureBlock, L1_5Output,
    L2Module, ModuleInteraction, Anomaly, L2Output,
    NarrativeNodeRead, NarrativeRecord,
)
from .vulnerability import (
    VulnerabilityEntry, DatabaseFreshness, ScanResult,
    VulnerabilitySummaryEntry, VulnerabilitySummary, VulnerabilityDiffSummary,
)
from .snapshot import (
    FeatureSummary, BlockSummary, RelationSummary, BaselineInfo, VersionSnapshot,
    SnapshotError, SnapshotNotFoundError,
)
from .diff import NodeDiff, EdgeDiff, DiffSummary, DiffResult, DiffError
from .scope import (
    ScopeFeatureEntry, ScopeDefinition, ScopeEntry, ScopeCounts, ScopeResult,
)
from .doubt import (
    StateTransition, Resolution, DoubtRecord, DoubtSummary,
    ScopeDefinitionError, DoubtNotFoundError, InvalidTransitionError, DoubtTerminalError,
)
from .timeline import (
    SemanticDriftEvent, FeatureTimeline, TimelineSummary, TimelineResult,
    RetentionDecision, TimelineError, RetentionConfigError,
)
from .pipeline import (
    PipelineStep, PipelineSummary,
    L1ChangeEntry, L2DetailEntry, L3Appendix,
    DiffChangeExplanation, UpdateReport,
)

__all__ = [
    "FileInfo", "ASTNode", "Edge", "TopologyEntry",
    "ExtractionError", "ExtractionResult", "TopologyResult", "StructureJSON",
    "Feature", "FeatureRelation", "L1Output",
    "CheckResult", "ValidationResult",
    "L1_5Block", "BlockRelation", "InfrastructureBlock", "L1_5Output",
    "L2Module", "ModuleInteraction", "Anomaly", "L2Output",
    "NarrativeNodeRead", "NarrativeRecord",
    "VulnerabilityEntry", "DatabaseFreshness", "ScanResult",
    "VulnerabilitySummaryEntry", "VulnerabilitySummary", "VulnerabilityDiffSummary",
    "FeatureSummary", "BlockSummary", "RelationSummary", "BaselineInfo", "VersionSnapshot",
    "SnapshotError", "SnapshotNotFoundError",
    "NodeDiff", "EdgeDiff", "DiffSummary", "DiffResult", "DiffError",
    "ScopeFeatureEntry", "ScopeDefinition", "ScopeEntry", "ScopeCounts", "ScopeResult",
    "StateTransition", "Resolution", "DoubtRecord", "DoubtSummary",
    "ScopeDefinitionError", "DoubtNotFoundError", "InvalidTransitionError", "DoubtTerminalError",
    "SemanticDriftEvent", "FeatureTimeline", "TimelineSummary", "TimelineResult",
    "RetentionDecision", "TimelineError", "RetentionConfigError",
    "PipelineStep", "PipelineSummary",
    "L1ChangeEntry", "L2DetailEntry", "L3Appendix",
    "DiffChangeExplanation", "UpdateReport",
]
