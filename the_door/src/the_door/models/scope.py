"""Scope verification data models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScopeFeatureEntry:
    """Scope definition 中的單一預期功能。"""

    feature_id: str
    expected_label: str | None = None


@dataclass(frozen=True)
class ScopeDefinition:
    """PM/SPM 定義的 Sprint/Release 範圍。"""

    scope_name: str
    features: list[ScopeFeatureEntry] = field(default_factory=list)
    description: str | None = None


# === Scope Result models ===


@dataclass(frozen=True)
class ScopeEntry:
    """單一功能的範圍驗核結果。"""

    feature_id: str
    scope_state: str  # "in_scope_complete" | "out_of_scope" | "in_scope_incomplete"
    feature_label: str | None = None  # 來自 L1Output（若存在）
    expected_label: str | None = None  # 來自 ScopeDefinition（若存在）


@dataclass(frozen=True)
class ScopeCounts:
    """範圍驗核聚合計數。"""

    in_scope_complete: int = 0
    out_of_scope: int = 0
    in_scope_incomplete: int = 0


@dataclass(frozen=True)
class ScopeResult:
    """完整的範圍驗核結果。"""

    scope_name: str
    entries: list[ScopeEntry] = field(default_factory=list)
    counts: ScopeCounts = field(default_factory=ScopeCounts)


# === Doubt Path models ===
