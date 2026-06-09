"""Import-equivalence safety net for the_door.models.

Pins the public surface: every one of the 79 model types must be importable
from `the_door.models`. Passes against the CURRENT single-file models.py and
MUST stay green after the package split (proves consumers are unaffected).
"""
from __future__ import annotations

import importlib

# The complete public surface of the_door.models (79 types).
EXPECTED_NAMES = [
    # extraction
    "FileInfo", "ASTNode", "Edge", "TopologyEntry",
    "ExtractionError", "ExtractionResult", "TopologyResult", "StructureJSON",
    # analysis (l1 + validation + l1.5 + l2 + narrative)
    "Feature", "FeatureRelation", "L1Output",
    "CheckResult", "ValidationResult",
    "L1_5Block", "BlockRelation", "InfrastructureBlock", "L1_5Output",
    "L2Module", "ModuleInteraction", "Anomaly", "L2Output",
    "NarrativeNodeRead", "NarrativeRecord",
    # vulnerability
    "VulnerabilityEntry", "DatabaseFreshness", "ScanResult",
    "VulnerabilitySummaryEntry", "VulnerabilitySummary", "VulnerabilityDiffSummary",
    # snapshot
    "FeatureSummary", "BlockSummary", "RelationSummary", "BaselineInfo", "VersionSnapshot",
    "SnapshotError", "SnapshotNotFoundError",
    # diff
    "NodeDiff", "EdgeDiff", "DiffSummary", "DiffResult", "DiffError",
    # scope
    "ScopeFeatureEntry", "ScopeDefinition", "ScopeEntry", "ScopeCounts", "ScopeResult",
    # doubt
    "StateTransition", "Resolution", "DoubtRecord", "DoubtSummary",
    "ScopeDefinitionError", "DoubtNotFoundError", "InvalidTransitionError", "DoubtTerminalError",
    # timeline
    "SemanticDriftEvent", "FeatureTimeline", "TimelineSummary", "TimelineResult",
    "RetentionDecision", "TimelineError", "RetentionConfigError",
    # pipeline (report cluster only — analyze/update execution models removed in T5-A)
    "PipelineStep", "PipelineSummary", "L1ChangeEntry", "L2DetailEntry", "L3Appendix",
    "DiffChangeExplanation", "UpdateReport",
]


def test_expected_names_count_is_68():
    # T5-A removed 8 analyze/pipeline-execution model types (79 → 71), then
    # TheDoorConfig + CostEstimate (provider config, 71 → 69); the follow-up
    # cleanup removed the dead ParseResult (response_parser orphan, 69 → 68).
    assert len(EXPECTED_NAMES) == 68
    assert len(set(EXPECTED_NAMES)) == 68  # no duplicates


def test_all_names_importable_from_the_door_models():
    mod = importlib.import_module("the_door.models")
    missing = [n for n in EXPECTED_NAMES if not hasattr(mod, n)]
    assert not missing, f"the_door.models is missing: {missing}"
    # every name resolves to a class
    non_class = [n for n in EXPECTED_NAMES if not isinstance(getattr(mod, n), type)]
    assert not non_class, f"not classes: {non_class}"


def test_names_match_actual_module_classes():
    """The 79 expected names equal the set of classes the module actually
    defines/exports — guards against the list drifting out of sync."""
    import inspect
    mod = importlib.import_module("the_door.models")
    actual = {
        name for name, obj in inspect.getmembers(mod, inspect.isclass)
        if obj.__module__.startswith("the_door.models")
    }
    assert actual == set(EXPECTED_NAMES), (
        f"drift: only-in-module={sorted(actual - set(EXPECTED_NAMES))}, "
        f"only-in-expected={sorted(set(EXPECTED_NAMES) - actual)}"
    )
