"""Batch reader — orchestrate topology-guided batch LLM calls with pruning."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from the_door.core.llm.prompts import L1_SYSTEM_PROMPT
from the_door.core.llm.response_parser import ResponseParser
from the_door.core.reading.pruning_engine import PruningEngine
from the_door.models import (
    ASTNode,
    Edge,
    Feature,
    FeatureRelation,
    L1Output,
    StructureJSON,
    TopologyEntry,
)

_VALID_CONTEXT_MODES = ("detail", "minimal")


MAX_BATCHES = 5


@dataclass
class BatchReadResult:
    """Result of the complete batch reading process."""

    l1_output: L1Output = field(default_factory=L1Output)
    total_batches: int = 0
    total_tokens_used: int = 0
    pruned_node_count: int = 0


@dataclass
class RegenerateResult:
    """Result of a regeneration request."""

    previous_result: Feature | None = None
    new_result: Feature | None = None
    differs: bool = False


class BatchReader:
    """Orchestrate topology-guided batch reading with pruning."""

    def __init__(
        self,
        llm_provider,
        structure: StructureJSON,
        *,
        max_context_tokens: int | None = None,
        context_mode: Literal["detail", "minimal"] = "detail",
    ) -> None:
        if context_mode not in _VALID_CONTEXT_MODES:
            raise ValueError(
                f"context_mode must be one of {_VALID_CONTEXT_MODES}, got {context_mode!r}"
            )
        self._provider = llm_provider
        self._structure = structure
        self._parser = ResponseParser()
        self._pruning = PruningEngine(structure.edges)
        self._max_context_tokens = max_context_tokens
        self._context_mode = context_mode
        self._node_lookup: dict[str, ASTNode] = {n.node_id: n for n in structure.nodes}

    async def read(
        self,
        affected_nodes: list[str] | None = None,
    ) -> BatchReadResult:
        """Execute full batch reading pipeline."""
        if not self._structure.topology:
            return BatchReadResult()

        # Group nodes by batch_assignment
        batch_groups = self._group_by_batch()

        # If affected_nodes specified, filter to only those + dependents
        if affected_nodes is not None:
            batch_groups = self._filter_affected(batch_groups, affected_nodes)

        # Sort batches in ascending order
        sorted_batches = sorted(batch_groups.keys())

        # Enforce max batch limit
        overflow_nodes: list[str] = []
        if len(sorted_batches) > MAX_BATCHES:
            for batch_num in sorted_batches[MAX_BATCHES:]:
                overflow_nodes.extend(batch_groups[batch_num])
            sorted_batches = sorted_batches[:MAX_BATCHES]

        # Process each batch
        all_features: list[Feature] = []
        all_relations: list[FeatureRelation] = []
        all_unclassified: list[str] = []
        all_infrastructure: list[str] = []
        total_tokens = 0

        for batch_num in sorted_batches:
            node_ids = batch_groups[batch_num]

            # Filter out pruned nodes
            active_nodes = [nid for nid in node_ids if not self._pruning.should_prune(nid)]
            if not active_nodes:
                continue

            # Check if payload exceeds context window → auto-split
            sub_batches = self._maybe_split(active_nodes)

            for sub_nodes in sub_batches:
                features, relations, unclassified, infrastructure, prompt_str = await self._process_batch(
                    sub_nodes, batch_num
                )
                all_features.extend(features)
                all_relations.extend(relations)
                all_unclassified.extend(unclassified)
                all_infrastructure.extend(infrastructure)

                # Record confidence for pruning
                for feat in features:
                    for src_node in feat.source_nodes:
                        self._pruning.record_confidence(src_node, feat.confidence, batch_num)

                total_tokens += self._provider.estimate_tokens(prompt_str)

        # Add overflow nodes as unclassified
        all_unclassified.extend(overflow_nodes)

        l1_output = L1Output(
            summary="",
            features=all_features,
            feature_relations=all_relations,
            unclassified_nodes=all_unclassified,
            infrastructure_nodes=all_infrastructure,
        )

        return BatchReadResult(
            l1_output=l1_output,
            total_batches=len(sorted_batches),
            total_tokens_used=total_tokens,
            pruned_node_count=len(self._pruning.get_pruned_nodes()),
        )

    async def regenerate(
        self,
        feature_id: str,
        previous_result: Feature,
    ) -> RegenerateResult:
        """Re-analyze a specific feature node."""
        source_nodes = list(previous_result.source_nodes)
        prompt = self._serialize_regenerate_payload(source_nodes, feature_id)

        response = await self._provider.complete(prompt, system_prompt=L1_SYSTEM_PROMPT)
        parse_result = self._parser.parse(response)

        if not parse_result.success or not parse_result.data:
            return RegenerateResult(
                previous_result=previous_result,
                new_result=None,
                differs=False,
            )

        # Extract the regenerated feature
        features_data = parse_result.data.get("features", [])
        if not features_data:
            return RegenerateResult(
                previous_result=previous_result,
                new_result=None,
                differs=False,
            )

        feat_data = features_data[0]
        new_feature = Feature(
            feature_id=feat_data.get("feature_id", feature_id),
            label=feat_data.get("label", ""),
            description=feat_data.get("description", ""),
            trigger=feat_data.get("trigger", "user_action"),
            trigger_description=feat_data.get("trigger_description", ""),
            confidence=feat_data.get("confidence", "medium"),
            confidence_reason=feat_data.get("confidence_reason", ""),
            source_nodes=feat_data.get("source_nodes", []),
            needs_source_review=feat_data.get("needs_source_review", False),
            review_reason=feat_data.get("review_reason"),
        )

        # Check if results differ
        differs = (
            new_feature.label != previous_result.label
            or new_feature.description != previous_result.description
            or list(new_feature.source_nodes) != list(previous_result.source_nodes)
        )

        return RegenerateResult(
            previous_result=previous_result,
            new_result=new_feature,
            differs=differs,
        )

    # === Private helpers ===

    def _group_by_batch(self) -> dict[int, list[str]]:
        """Group topology entries by batch_assignment."""
        groups: dict[int, list[str]] = {}
        for entry in self._structure.topology:
            groups.setdefault(entry.batch_assignment, []).append(entry.node_id)
        return groups

    def _filter_affected(
        self,
        batch_groups: dict[int, list[str]],
        affected_nodes: list[str],
    ) -> dict[int, list[str]]:
        """Filter batch groups to only include affected nodes + direct dependents."""
        affected_set = set(affected_nodes)

        # Add direct dependents (nodes that affected nodes point to)
        for edge in self._structure.edges:
            if edge.from_node in affected_set:
                affected_set.add(edge.to_node)

        # Filter batch groups
        filtered: dict[int, list[str]] = {}
        for batch_num, node_ids in batch_groups.items():
            filtered_nodes = [nid for nid in node_ids if nid in affected_set]
            if filtered_nodes:
                filtered[batch_num] = filtered_nodes

        return filtered

    def _maybe_split(self, node_ids: list[str]) -> list[list[str]]:
        """Split node list if payload would exceed context window."""
        if self._max_context_tokens is None:
            return [node_ids]

        # Estimate payload size using the actual serialization path (batch_num=0 is a size-estimation placeholder)
        payload_text = self._serialize_payload(node_ids, batch_num=0)
        estimated_tokens = self._provider.estimate_tokens(payload_text)

        if estimated_tokens <= self._max_context_tokens:
            return [node_ids]

        # Recursively halve
        mid = len(node_ids) // 2
        if mid == 0:
            return [node_ids]

        left = self._maybe_split(node_ids[:mid])
        right = self._maybe_split(node_ids[mid:])
        return left + right

    def _build_payload(self, node_ids: list[str], batch_num: int) -> dict:
        """Build the prompt payload dict (pre-serialization form)."""
        if self._context_mode == "minimal":
            return {
                "batch": batch_num,
                "context_mode": "minimal",
                "nodes": list(node_ids),
            }
        # "detail"
        node_dicts: list[dict] = []
        for nid in node_ids:
            node = self._node_lookup.get(nid)
            if node is None:
                continue
            node_dicts.append({
                "node_id": node.node_id,
                "type": node.type,
                "name": node.name,
                "file": node.file,
                "language": node.language,
                "parameters": list(node.parameters),
                "return_type": node.return_type,
                "decorators": list(node.decorators),
                "docstring": node.docstring,
                "comments": list(node.comments),
            })
        # Filter edges to those fully within this batch to bound payload size.
        batch_node_set = set(node_ids)
        edge_dicts = [
            {
                "from": e.from_node,
                "to": e.to_node,
                "type": e.type,
                "resolution": e.resolution,
            }
            for e in self._structure.edges
            if e.from_node in batch_node_set and e.to_node in batch_node_set
        ]
        return {
            "batch": batch_num,
            "context_mode": "detail",
            "nodes": node_dicts,
            "edges": edge_dicts,
        }

    def _serialize_payload(self, node_ids: list[str], batch_num: int) -> str:
        """Serialize the batch payload for LLM consumption."""
        return json.dumps(self._build_payload(node_ids, batch_num), ensure_ascii=False)

    def _serialize_regenerate_payload(
        self, source_nodes: list[str], feature_id: str
    ) -> str:
        """Serialize regenerate-task payload, respecting context_mode."""
        payload = self._build_payload(source_nodes, batch_num=0)
        payload.pop("batch", None)
        payload["task"] = "regenerate"
        payload["feature_id"] = feature_id
        return json.dumps(payload, ensure_ascii=False)

    async def _process_batch(
        self,
        node_ids: list[str],
        batch_num: int,
    ) -> tuple[list[Feature], list[FeatureRelation], list[str], list[str], str]:
        """Process a single batch of nodes via LLM call."""
        prompt = self._serialize_payload(node_ids, batch_num)

        response = await self._provider.complete(prompt, system_prompt=L1_SYSTEM_PROMPT)
        parse_result = self._parser.parse(response)

        if not parse_result.success or not parse_result.data:
            # All nodes in this batch become unclassified
            return [], [], list(node_ids), [], prompt

        data = parse_result.data
        features: list[Feature] = []
        relations: list[FeatureRelation] = []

        # Parse features
        for feat_data in data.get("features", []):
            features.append(Feature(
                feature_id=feat_data.get("feature_id", ""),
                label=feat_data.get("label", ""),
                description=feat_data.get("description", ""),
                trigger=feat_data.get("trigger", "user_action"),
                trigger_description=feat_data.get("trigger_description", ""),
                confidence=feat_data.get("confidence", "medium"),
                confidence_reason=feat_data.get("confidence_reason", ""),
                source_nodes=feat_data.get("source_nodes", []),
                needs_source_review=feat_data.get("needs_source_review", False),
                review_reason=feat_data.get("review_reason"),
            ))

        # Parse relations
        for rel_data in data.get("feature_relations", []):
            relations.append(FeatureRelation(
                from_feature=rel_data.get("from", ""),
                to_feature=rel_data.get("to", ""),
                relation=rel_data.get("relation", ""),
                relation_type=rel_data.get("relation_type", "inferred"),
                inferred_reason=rel_data.get("inferred_reason"),
            ))

        unclassified = data.get("unclassified_nodes", [])
        infrastructure = data.get("infrastructure_nodes", [])

        return features, relations, unclassified, infrastructure, prompt
