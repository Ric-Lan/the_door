"""The Door — LLM constraint pipeline for code structure extraction and validation."""

__version__ = "1.0.5"

from the_door.models import (
    ASTNode,
    CheckResult,
    Edge,
    ExtractionError,
    ExtractionResult,
    Feature,
    FeatureRelation,
    FileInfo,
    L1Output,
    StructureJSON,
    TopologyEntry,
    TopologyResult,
    ValidationResult,
)
