"""Core data models for The Door Phase 1-min."""
from __future__ import annotations

from dataclasses import dataclass, field


# === Structure JSON models (AST extraction output) ===


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


@dataclass(frozen=True)
class Feature:
    """A single L1 feature identified by the LLM."""

    feature_id: str
    label: str
    description: str
    trigger: str  # "user_action" | "scheduled" | "auto_triggered"
    trigger_description: str
    confidence: str  # "high" | "medium" | "low"
    confidence_reason: str
    source_nodes: list[str] = field(default_factory=list)
    needs_source_review: bool = False
    review_reason: str | None = None
    source_reviewed: bool = False


@dataclass(frozen=True)
class FeatureRelation:
    """A relationship between two L1 features."""

    from_feature: str  # feature_id
    to_feature: str  # feature_id
    relation: str
    relation_type: str  # "static" | "inferred"
    inferred_reason: str | None = None


@dataclass
class L1Output:
    """Complete L1 output from the LLM."""

    summary: str = ""
    features: list[Feature] = field(default_factory=list)
    feature_relations: list[FeatureRelation] = field(default_factory=list)
    unclassified_nodes: list[str] = field(default_factory=list)
    infrastructure_nodes: list[str] = field(default_factory=list)


# === Validation result models ===


@dataclass
class CheckResult:
    """Result of a single validation check."""

    passed: bool
    errors: list[str] = field(default_factory=list)
    details: dict | None = None


@dataclass
class ValidationResult:
    """Aggregated result of all 5 validation checks."""

    passed: bool
    schema_result: CheckResult = field(
        default_factory=lambda: CheckResult(passed=True)
    )
    coverage_result: CheckResult = field(
        default_factory=lambda: CheckResult(passed=True)
    )
    language_result: CheckResult = field(
        default_factory=lambda: CheckResult(passed=True)
    )
    anchor_result: CheckResult = field(
        default_factory=lambda: CheckResult(passed=True)
    )
    relation_result: CheckResult = field(
        default_factory=lambda: CheckResult(passed=True)
    )


# ============================================================================
# Phase 1-full models (L1.5, L2, Narrative Chain, LLM/Config)
# ============================================================================


# === L1.5 Output models ===


@dataclass(frozen=True)
class L1_5Block:
    """A structural block in the L1.5 overview."""

    block_id: str
    label: str  # Module name + functional description
    responsibility: str
    trigger_mechanism: str  # Human-readable trigger description
    related_features: list[str] = field(default_factory=list)  # L1 feature_ids


@dataclass(frozen=True)
class BlockRelation:
    """A relationship between two L1.5 blocks."""

    from_block: str  # block_id
    to_block: str  # block_id
    relation: str
    relation_type: str  # "static" | "inferred"
    inferred_reason: str | None = None


@dataclass(frozen=True)
class InfrastructureBlock:
    """Consolidated infrastructure block in L1.5."""

    label: str  # "System Infrastructure"
    components: list[str] = field(default_factory=list)


@dataclass
class L1_5Output:
    """Complete L1.5 structural overview output."""

    blocks: list[L1_5Block] = field(default_factory=list)
    block_relations: list[BlockRelation] = field(default_factory=list)
    infrastructure_block: InfrastructureBlock | None = None


# === L2 Output models ===


@dataclass(frozen=True)
class L2Module:
    """A module in the L2 interaction view."""

    module_id: str
    label: str
    source_nodes: list[str] = field(default_factory=list)
    confidence: str = "medium"  # "high" | "medium" | "low"
    confidence_reason: str = ""


@dataclass(frozen=True)
class ModuleInteraction:
    """An interaction between two L2 modules."""

    from_module: str  # module_id
    to_module: str  # module_id
    description: str
    relation_type: str  # "static" | "inferred"
    inferred_reason: str | None = None


@dataclass(frozen=True)
class Anomaly:
    """An anomaly detected in L2 analysis."""

    anomaly_type: str  # "dead_code" | "logic_dead_end" | "uncertain_boundary" | "vuln_high" | "vuln_medium"
    affected_node_ids: list[str] = field(default_factory=list)
    explanation: str = ""
    confidence: str = "medium"


@dataclass
class L2Output:
    """Complete L2 module interaction output."""

    modules: list[L2Module] = field(default_factory=list)
    module_interactions: list[ModuleInteraction] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)


# === Narrative Chain models ===


@dataclass
class NarrativeNodeRead:
    """A node read in a batch, recorded in the narrative chain."""

    node_id: str
    topology_rank: int
    in_degree: int
    is_entry_point: bool


@dataclass
class NarrativeRecord:
    """A single record in the narrative chain JSONL."""

    record_type: str  # "batch" | "regeneration" | "structural_change"
    timestamp: str  # ISO8601
    batch: int | None = None
    strategy: str = "topology_guided"
    nodes_read: list[NarrativeNodeRead] = field(default_factory=list)
    llm_judgment: str = ""
    pruned_nodes: list[str] = field(default_factory=list)
    pending_low_confidence: list[str] = field(default_factory=list)
    # Regeneration fields
    feature_id: str | None = None
    previous_summary: str | None = None
    new_summary: str | None = None
    # Structural change fields
    added_nodes: list[str] | None = None
    removed_nodes: list[str] | None = None
    modified_nodes: list[str] | None = None


# === LLM / Config models ===


@dataclass
class TheDoorConfig:
    """Parsed configuration for The Door one-click mode."""

    default_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    max_retries: int = 3
    timeout_seconds: int = 120
    cost_warning_threshold: float = 1.00


@dataclass
class CostEstimate:
    """Estimated API cost for a codebase analysis."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    provider: str = ""
    model: str = ""
    batch_count: int = 0
    is_local: bool = False


@dataclass
class ParseResult:
    """Result of parsing an LLM response."""

    success: bool = False
    data: dict | None = None
    raw_text: str = ""
    error: str | None = None


# ============================================================================
# Phase 2: Diff Engine models
# ============================================================================


@dataclass(frozen=True)
class FeatureSummary:
    """Summarized feature data stored in a version snapshot.

    Projects :class:`Feature` to the minimum needed for diff comparison plus
    the bits the viewer needs to drill down. ``trigger_description`` is the
    user-facing trigger text and ``source_nodes`` is the AST node ids the
    LLM attributed to this feature — without it, L2 generation has no way
    to know which subset of structure.json to cluster. Both default to
    empty/None so legacy snapshots deserialize unchanged.

    ``source_nodes`` is a tuple (not list) so the dataclass stays hashable
    under ``frozen=True``; callers serialize it as a JSON list at boundaries.
    Diff comparison (:mod:`core.diff.diff_engine`) only keys on label and
    description, so adding/removing nodes here does not flip a feature into
    ``attribute_changed``.
    """

    feature_id: str
    label: str
    description: str
    source_node_count: int
    confidence: str  # "high" | "medium" | "low"
    trigger_description: str | None = None
    source_nodes: tuple[str, ...] = ()
    confidence_reason: str | None = None


@dataclass(frozen=True)
class BlockSummary:
    """Summarized block data stored in a version snapshot (L1.5)."""

    block_id: str
    label: str
    responsibility: str
    confidence: str = "medium"


@dataclass(frozen=True)
class RelationSummary:
    """Summarized feature relation stored in a version snapshot."""

    from_feature: str
    to_feature: str
    relation: str


@dataclass(frozen=True)
class BaselineInfo:
    """Metadata about a comparison baseline or current version."""

    version_id: str
    timestamp: str  # ISO8601
    trigger: str  # "commit" | "manual"
    commit_hash: str | None = None
    git_tags: list[str] = field(default_factory=list)
    label: str | None = None
    resolved_from: str | None = None  # Original query string used to resolve this baseline


@dataclass(frozen=True)
class VersionSnapshot:
    """A persisted record of L1/L1.5 output at a specific point in time."""

    version_id: str
    timestamp: str  # ISO8601
    trigger: str  # "commit" | "manual"
    l1_snapshot: dict[str, FeatureSummary] = field(default_factory=dict)
    analyzed_files: list[str] = field(default_factory=list)
    commit_hash: str | None = None
    git_tags: list[str] = field(default_factory=list)
    label: str | None = None
    l1_5_snapshot: dict[str, BlockSummary] = field(default_factory=dict)
    feature_relations_snapshot: list[RelationSummary] = field(default_factory=list)
    vulnerabilities_snapshot: list[VulnerabilityEntry] = field(default_factory=list)
    vulnerability_db_freshness: DatabaseFreshness | None = None
    codebase_path: Path | None = None


@dataclass(frozen=True)
class NodeDiff:
    """A single node's diff classification."""

    node_id: str  # feature_id or block_id
    diff_state: str  # "added" | "removed" | "attribute_changed" | "dependency_changed" | "unchanged"
    current_label: str | None = None
    current_description: str | None = None
    baseline_label: str | None = None
    baseline_description: str | None = None
    current_confidence: str | None = None
    secondary_changes: dict | None = None


@dataclass(frozen=True)
class EdgeDiff:
    """A single edge's diff classification."""

    from_node: str
    to_node: str
    diff_state: str  # "added" | "removed" | "modified"
    current_relation: str | None = None
    baseline_relation: str | None = None


@dataclass(frozen=True)
class DiffSummary:
    """Aggregate counts for a diff result."""

    added_count: int = 0
    removed_count: int = 0
    dependency_changed_count: int = 0
    attribute_changed_count: int = 0
    total_changed_count: int = 0


@dataclass(frozen=True)
class DiffResult:
    """Complete diff output between two snapshots."""

    baseline_info: BaselineInfo
    current_info: BaselineInfo
    node_diffs: list[NodeDiff] = field(default_factory=list)
    edge_diffs: list[EdgeDiff] = field(default_factory=list)
    summary: DiffSummary = field(default_factory=DiffSummary)
    layer: str = "l1"  # "l1" | "l1.5"


# === Phase 2: Custom exceptions ===


class SnapshotError(Exception):
    """Base exception for snapshot operations."""

    pass


class SnapshotNotFoundError(SnapshotError):
    """Raised when a baseline reference cannot be resolved."""

    def __init__(self, reference: str, available: list[dict]):
        self.reference = reference
        self.available = available
        super().__init__(f"No snapshot matches '{reference}'")


class DiffError(Exception):
    """Exception for diff computation errors."""

    pass


# ============================================================================
# Phase 2.5: Vulnerability Layer models
# ============================================================================


# === Phase 2.5: Vulnerability Layer models ===


@dataclass(frozen=True)
class VulnerabilityEntry:
    """A single vulnerability record from osv-scanner."""

    cve_id: str
    package: str
    version: str
    severity: str  # "critical" | "high" | "medium" | "low"
    cvss: float  # 0.0–10.0
    source: str = "osv-scanner"


@dataclass(frozen=True)
class DatabaseFreshness:
    """Metadata about vulnerability database currency."""

    timestamp: str  # ISO8601
    mode: str  # "online" | "offline"
    stale_warning: str | None = None


@dataclass(frozen=True)
class ScanResult:
    """Complete result of a vulnerability scan."""

    entries: list[VulnerabilityEntry] = field(default_factory=list)
    db_freshness: DatabaseFreshness | None = None
    warnings: list[str] = field(default_factory=list)
    scanner_available: bool = True


@dataclass(frozen=True)
class VulnerabilitySummaryEntry:
    """A single entry in the vulnerability summary panel."""

    cve_id: str
    package: str
    version: str
    severity: str
    cvss: float
    action: str  # "立即更新" | "建議更新" | "留意追蹤"
    affected_features: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VulnerabilitySummary:
    """Structured vulnerability summary for side panel display.

    Contains only data — formatting (header text, no-vuln message) is done by the renderer.
    """

    total_critical: int = 0
    total_high: int = 0
    total_medium: int = 0
    total_low: int = 0
    entries: list[VulnerabilitySummaryEntry] = field(default_factory=list)
    db_freshness_display: str = ""


@dataclass(frozen=True)
class VulnerabilityDiffSummary:
    """Vulnerability changes between two snapshots.

    Contains only data — summary text formatting is done by the renderer.
    """

    new_vulnerabilities: list[VulnerabilityEntry] = field(default_factory=list)
    resolved_vulnerabilities: list[VulnerabilityEntry] = field(default_factory=list)
    unchanged_vulnerabilities: list[VulnerabilityEntry] = field(default_factory=list)


# ============================================================================
# Phase 3: Scope Verification + Doubt Path models
# ============================================================================


# === Scope Definition models ===


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

from pathlib import Path


# === Analyze Pipeline Configuration ===


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
