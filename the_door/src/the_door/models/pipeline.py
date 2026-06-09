"""Update-report data models (the persisted diff-report structure).

T5-A: the analyze/update execution models (AnalyzeConfig, AnalyzeResult,
StepTimeouts, PipelineConfig, PipelineResult, PipelineError, AnalyzeError,
CostConfirmationRequired) were removed with the key-bound analyze pipeline.
What remains is the *report* data cluster — the structure of the persisted
update-report JSON that the viewer's diff/report display path reads.
PipelineStep/PipelineSummary remain only as the nested shape of L3Appendix /
UpdateReport (no execution engine produces them anymore; they describe
already-persisted reports).
"""
from __future__ import annotations

from dataclasses import dataclass, field


# === Pipeline summary (nested report shape) ===


@dataclass(frozen=True)
class PipelineStep:
    """管線中的單一執行步驟狀態（僅記錄終態；報告結構用）。"""

    step_name: str
    status: str  # "completed" | "failed" | "skipped"
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class PipelineSummary:
    """管線執行摘要（報告結構用）。"""

    old_path: str
    new_path: str
    total_duration_ms: int
    steps: list[PipelineStep] = field(default_factory=list)


# === Report Data ===


@dataclass(frozen=True)
class L1ChangeEntry:
    """L1 變更總覽中的單一項目。"""

    feature_id: str
    change_type: str  # "added" | "removed" | "attribute_changed" | "dependency_changed"
    risk_flags: list[str] = field(default_factory=list)
    current_label: str = ""
    baseline_label: str | None = None


@dataclass(frozen=True)
class L2DetailEntry:
    """L2 細節展開中的單一項目。"""

    feature_id: str
    change_type: str
    current_label: str = ""
    current_description: str = ""
    baseline_label: str | None = None
    baseline_description: str | None = None
    scope_state: str | None = None
    related_vulnerabilities: list[str] = field(default_factory=list)
    affected_relations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class L3Appendix:
    """L3 技術附錄。"""

    diff_result_json: dict | None = None
    scope_result_json: dict | None = None
    timeline_result_json: dict | None = None
    pipeline_summary: PipelineSummary | None = None


@dataclass(frozen=True)
class DiffChangeExplanation:
    """自然語言差異推論結果。

    confidence: "high" | "medium" | "low"
    generated_at: ISO 8601 UTC string
    """

    feature_id: str
    change_type: str
    impact_summary: str
    possible_purpose: str
    linked_resources: list[str] = field(default_factory=list)
    caution: str = ""
    confidence: str = "low"
    language: str = "zh-Hant"
    generated_at: str = ""
    baseline_version_id: str = ""
    current_version_id: str = ""


@dataclass(frozen=True)
class UpdateReport:
    """版本更新報告的完整結構化資料（持久化於 .the-door，viewer 顯示用）。"""

    report_version: str = "1.0.0"
    generated_at: str = ""
    pipeline_summary: PipelineSummary | None = None
    l0_summary: str = ""
    l1_changes: list[L1ChangeEntry] = field(default_factory=list)
    l2_details: list[L2DetailEntry] = field(default_factory=list)
    l3_appendix: L3Appendix = field(default_factory=L3Appendix)
    interrupted: bool = False
    output_language: str = "zh-Hant"
    diff_change_explanations: list[DiffChangeExplanation] = field(default_factory=list)
