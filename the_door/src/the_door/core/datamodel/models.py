"""Value objects for data-model contract verification (side-channel, off translation path)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataModelCandidate:
    """A localized data-model touch point (Tier 0)."""
    node_id: str            # ASTNode.node_id；schema 檔候選此欄為 ""
    file: str               # 候選檔案路徑（交付粒度為「檔」，spec §3 無行範圍）
    kind: str               # "code_site" | "schema_file"
    flagged_reason: str     # 命中哪條啟發式（可讀字串）


@dataclass(frozen=True)
class DataModelLocalization:
    """Tier 0 output: code-site + schema-file candidates."""
    code_candidates: tuple[DataModelCandidate, ...] = ()
    schema_candidates: tuple[DataModelCandidate, ...] = ()


@dataclass(frozen=True)
class DeclaredField:
    """One declared field in a schema entity (agent-normalized)."""
    field: str
    type: str | None = None


@dataclass(frozen=True)
class CodeTouch:
    """One code-side data touch (agent-normalized)."""
    op: str                 # "write" | "read"
    entity: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class ContractEntry:
    """One bidirectional contract-diff result for an entity field."""
    entity: str
    field: str
    status: str             # "write_gap" | "coverage_gap" | "match"
    detail: str


@dataclass(frozen=True)
class ContractDiff:
    """Tier 1 output: the full contract diff."""
    entries: tuple[ContractEntry, ...] = ()
