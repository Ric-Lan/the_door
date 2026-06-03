"""Realtime pipeline + report data models (and pipeline exceptions)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .analysis import L1Output
from .diff import DiffResult
from .scope import ScopeResult
from .snapshot import VersionSnapshot
from .timeline import TimelineResult
from .vulnerability import ScanResult


@dataclass(frozen=True)
class AnalyzeConfig:
    """分析管線的配置參數。"""

    provider: str | None = None
    model: str | None = None
    skip_cost_confirm: bool = False
    offline_vuln: bool = False
    timeout_seconds: int = 300
    extra_ignore: list[str] | None = None
    snapshot_label: str | None = None
    context_mode: str = "detail"


@dataclass(frozen=True)
class AnalyzeResult:
    """分析管線的完整結果。"""

    snapshot: VersionSnapshot
    l1_output: L1Output
    l1_output_data: dict
    scan_result: ScanResult
    file_fingerprint: dict[str, tuple[int, float]]
    total_batches: int
    total_tokens: int


# === Pipeline Configuration ===


@dataclass(frozen=True)
class StepTimeouts:
    """各管線步驟的超時秒數（immutable）。"""

    analyze_old: int = 300
    analyze_new: int = 300
    diff: int = 30
    scope_verify: int = 30
    timeline: int = 30
    report: int = 30


@dataclass(frozen=True)
class PipelineConfig:
    """版本更新管線的完整配置。"""

    old_path: Path
    new_path: Path
    analyze_config: AnalyzeConfig = field(default_factory=AnalyzeConfig)
    scope_name: str | None = None
    skip_timeline: bool = False
    force_reanalyze: bool = False
    step_timeouts: StepTimeouts = field(default_factory=StepTimeouts)
    output_language: str = "zh-Hant"


# === Pipeline Execution State ===


@dataclass(frozen=True)
class PipelineStep:
    """管線中的單一執行步驟狀態（僅記錄終態）。"""

    step_name: str
    status: str  # "completed" | "failed" | "skipped"
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class PipelineSummary:
    """管線執行摘要。"""

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
    """版本更新報告的完整結構化資料。"""

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


# === Pipeline Result ===


@dataclass(frozen=True)
class PipelineResult:
    """管線執行的完整結果。"""

    config: PipelineConfig
    steps: list[PipelineStep] = field(default_factory=list)
    old_snapshot: VersionSnapshot | None = None
    new_snapshot: VersionSnapshot | None = None
    diff_result: DiffResult | None = None
    scope_result: ScopeResult | None = None
    timeline_result: TimelineResult | None = None
    scan_result_old: ScanResult | None = None
    scan_result_new: ScanResult | None = None
    total_duration_ms: int = 0
    interrupted: bool = False


# === Phase 5: Custom exceptions ===


class PipelineError(Exception):
    """管線執行錯誤（不可恢復）。"""

    def __init__(self, step_name: str, message: str):
        self.step_name = step_name
        super().__init__(f"Pipeline error at '{step_name}': {message}")


class AnalyzeError(Exception):
    """分析管線錯誤。"""

    pass


class CostConfirmationRequired(Exception):
    """需要使用者確認 LLM 呼叫成本。"""

    def __init__(self, estimated_cost: float, total_tokens: int):
        self.estimated_cost = estimated_cost
        self.total_tokens = total_tokens
        super().__init__(
            f"Estimated cost: ${estimated_cost:.4f} ({total_tokens} tokens). "
            "Confirmation required."
        )
