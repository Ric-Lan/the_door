"""Extraction-layer data models (AST extraction output + topology)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileInfo:
    """A source file discovered in the codebase."""

    path: str
    language: str


@dataclass(frozen=True)
class ASTNode:
    """An extracted AST node (function, class, or method)."""

    node_id: str
    type: str  # "function" | "class" | "method"
    name: str
    file: str
    language: str
    start_line: int | None = None   # 1-indexed, inclusive; None = not available
    end_line: int | None = None     # 1-indexed, inclusive; None = not available
    decorators: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    return_type: str | None = None
    docstring: str | None = None
    comments: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Edge:
    """A relationship between two AST nodes."""

    from_node: str  # node_id
    to_node: str  # node_id
    type: str  # "calls" | "imports" | "extends" | "implements"
    resolution: str = "name_match"  # "scope_rule" | "import_alias" | "name_match" | "name_match_ambiguous" | "skipped_dynamic"


@dataclass(frozen=True)
class TopologyEntry:
    """Topology analysis result for a single node."""

    node_id: str
    in_degree: int
    out_degree: int
    topology_rank: int
    is_entry_point: bool
    batch_assignment: int


@dataclass
class ExtractionError:
    """A file that failed to parse during extraction."""

    file_path: str
    reason: str


@dataclass
class ExtractionResult:
    """Complete result of AST extraction from a codebase."""

    files: list[FileInfo] = field(default_factory=list)
    nodes: list[ASTNode] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    errors: list[ExtractionError] = field(default_factory=list)
    warnings: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass
class TopologyResult:
    """Complete topology analysis for all nodes."""

    entries: list[TopologyEntry] = field(default_factory=list)


@dataclass
class StructureJSON:
    """The complete Structure JSON output (extraction + topology)."""

    files: list[FileInfo] = field(default_factory=list)
    nodes: list[ASTNode] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    topology: list[TopologyEntry] = field(default_factory=list)


# === L1 Output models (LLM output, validated by Output Validator) ===
