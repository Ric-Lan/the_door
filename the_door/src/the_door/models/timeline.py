"""History-timeline data models (and timeline exceptions)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SemanticDriftEvent:
    """語意漂移事件記錄。

    當功能的 label 未變但 description 實質改變時觸發。
    """

    snapshot_version_id: str
    previous_description: str
    new_description: str
    timestamp: str  # ISO8601


@dataclass(frozen=True)
class FeatureTimeline:
    """單一功能的完整演進記錄。"""

    feature_id: str
    first_seen_timestamp: str  # ISO8601
    last_seen_timestamp: str  # ISO8601
    change_count: int  # label 或 description 變更次數
    current_state: str  # "active" | "removed"
    current_label: str  # 最新 snapshot 中的 label（若已移除則為最後已知 label）
    drift_events: list[SemanticDriftEvent] = field(default_factory=list)


@dataclass(frozen=True)
class TimelineSummary:
    """時間軸聚合統計。"""

    active_count: int = 0
    removed_count: int = 0
    total_drift_events: int = 0


@dataclass(frozen=True)
class TimelineResult:
    """Timeline Engine 的完整輸出。"""

    snapshot_count: int
    time_range_start: str | None  # ISO8601（最早 snapshot 時間戳），空序列時為 None
    time_range_end: str | None  # ISO8601（最新 snapshot 時間戳），空序列時為 None
    feature_timelines: list[FeatureTimeline] = field(default_factory=list)
    summary: TimelineSummary = field(default_factory=TimelineSummary)


@dataclass(frozen=True)
class RetentionDecision:
    """保留策略計算結果。"""

    to_retain: list[str] = field(default_factory=list)  # version_id 列表
    to_remove: list[str] = field(default_factory=list)  # version_id 列表


# === Phase 4: Custom exceptions ===


class TimelineError(Exception):
    """時間軸分析錯誤。"""

    pass


class RetentionConfigError(Exception):
    """保留策略設定錯誤。"""

    pass


# ============================================================================
# Phase 5: Realtime Dynamic Layer (Pipeline + Report) models
# ============================================================================
