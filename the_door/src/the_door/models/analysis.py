"""Analysis-pipeline data models (L1, validation, L1.5, L2, narrative chain)."""
from __future__ import annotations

from dataclasses import dataclass, field


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
