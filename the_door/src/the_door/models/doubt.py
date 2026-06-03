"""Doubt-path data models (and doubt exceptions)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StateTransition:
    """疑義狀態轉換記錄。"""

    from_state: str
    to_state: str
    timestamp: str  # ISO8601 UTC
    actor: str
    reason: str | None = None


@dataclass(frozen=True)
class Resolution:
    """疑義解決記錄。"""

    type: str  # "explained" | "fixed" | "accepted_risk"
    description: str
    resolved_by: str
    resolved_at: str  # ISO8601 UTC


@dataclass
class DoubtRecord:
    """疑義追蹤記錄。非 frozen — 狀態轉換需要修改。"""

    doubt_id: str  # UUID v4
    source_node: str  # feature_id
    doubt_type: str  # "out_of_scope" | "in_scope_incomplete" | "anomaly" | "low_confidence"
    current_state: str  # "discovered" | "investigating" | "explained" | "fixed" | "escalated" | "accepted_risk"
    created_by: str
    created_at: str  # ISO8601 UTC
    updated_at: str  # ISO8601 UTC
    assigned_to: str | None = None
    state_history: list[StateTransition] = field(default_factory=list)
    resolution: Resolution | None = None


@dataclass(frozen=True)
class DoubtSummary:
    """疑義聚合統計。"""

    total_active: int = 0
    by_state: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)


# === Phase 3: Custom exceptions ===


class ScopeDefinitionError(Exception):
    """Scope definition 解析或驗證錯誤。"""

    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        super().__init__(f"Scope definition error in '{file_path}': {message}")


class DoubtNotFoundError(Exception):
    """找不到指定的疑義記錄。"""

    def __init__(self, doubt_id: str):
        self.doubt_id = doubt_id
        super().__init__(f"Doubt not found: '{doubt_id}'")


class InvalidTransitionError(Exception):
    """不合法的狀態轉換。"""

    def __init__(self, current_state: str, target_state: str):
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(
            f"Invalid transition: '{current_state}' \u2192 '{target_state}'"
        )


class DoubtTerminalError(Exception):
    """疑義已在終態，不允許進一步轉換。"""

    def __init__(self, doubt_id: str, current_state: str):
        self.doubt_id = doubt_id
        self.current_state = current_state
        super().__init__(
            f"Doubt '{doubt_id}' is in terminal state '{current_state}'"
        )


# ============================================================================
# Phase 4: History Timeline models
# ============================================================================
