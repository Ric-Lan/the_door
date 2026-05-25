"""The Door — LLM constraint pipeline for code structure extraction and validation."""

from importlib.metadata import version as _version, PackageNotFoundError as _PackageNotFoundError

try:
    __version__ = _version("the-door")
except _PackageNotFoundError:
    __version__ = "0.0.0+dev"

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
