"""Diff Engine — compute structural diffs between two version snapshots.

Pure functions, no I/O, no side effects. Supports both L1 (feature-level)
and L1.5 (block-level) diffs.
"""
from __future__ import annotations

from the_door.models import (
    BaselineInfo,
    BlockSummary,
    DiffError,
    DiffResult,
    DiffSummary,
    EdgeDiff,
    FeatureSummary,
    NodeDiff,
    RelationSummary,
    VersionSnapshot,
    VulnerabilityDiffSummary,
    VulnerabilityEntry,
)


class DiffEngine:
    """Compute structural diffs between two version snapshots.

    Pure functions — no I/O, no side effects. All inputs are dicts/dataclasses.
    Supports both L1 (feature-level) and L1.5 (block-level) diffs.
    """

    def compute_l1_diff(
        self,
        baseline: VersionSnapshot,
        current: VersionSnapshot,
    ) -> DiffResult:
        """Compute L1 feature-level diff.

        1. Match features by feature_id
        2. Classify each as added/removed/attribute_changed/unchanged
        3. Compare feature_relations (edges) for edge-level diffs
        4. Upgrade unchanged→dependency_changed when edges change
        5. Apply priority rules (added > removed > dep_changed > attr_changed)
        6. Compute summary counts
        """
        if not baseline.l1_snapshot and not current.l1_snapshot:
            # Both empty is valid — produces empty diff
            pass
        # Validate that snapshots have L1 data when they have other content
        if not baseline.l1_snapshot and (
            baseline.l1_5_snapshot or baseline.analyzed_files
        ):
            raise DiffError("Baseline snapshot is missing L1 data")
        if not current.l1_snapshot and (
            current.l1_5_snapshot or current.analyzed_files
        ):
            raise DiffError("Current snapshot is missing L1 data")

        baseline_map = baseline.l1_snapshot
        current_map = current.l1_snapshot

        # Step 1 & 2: Match features and classify nodes
        node_diffs_by_id: dict[str, NodeDiff] = {}

        # Added: in current but not in baseline
        for fid, feat in current_map.items():
            if fid not in baseline_map:
                node_diffs_by_id[fid] = NodeDiff(
                    node_id=fid,
                    diff_state="added",
                    current_label=feat.label,
                    current_description=feat.description,
                    current_confidence=feat.confidence,
                    baseline_label=None,
                    baseline_description=None,
                )

        # Removed: in baseline but not in current
        for fid, feat in baseline_map.items():
            if fid not in current_map:
                node_diffs_by_id[fid] = NodeDiff(
                    node_id=fid,
                    diff_state="removed",
                    baseline_label=feat.label,
                    baseline_description=feat.description,
                    current_label=None,
                    current_description=None,
                    current_confidence=None,
                )

        # Matched: in both — compare label and description
        for fid in baseline_map:
            if fid in current_map:
                b_feat = baseline_map[fid]
                c_feat = current_map[fid]
                if b_feat.label == c_feat.label and b_feat.description == c_feat.description:
                    state = "unchanged"
                else:
                    state = "attribute_changed"
                node_diffs_by_id[fid] = NodeDiff(
                    node_id=fid,
                    diff_state=state,
                    current_label=c_feat.label,
                    current_description=c_feat.description,
                    current_confidence=c_feat.confidence,
                    baseline_label=b_feat.label,
                    baseline_description=b_feat.description,
                )

        # Step 3: Compare edges (feature_relations_snapshot)
        edge_diffs = self._compute_edge_diffs(
            baseline.feature_relations_snapshot,
            current.feature_relations_snapshot,
        )

        # Step 4: Upgrade unchanged/attribute_changed → dependency_changed
        changed_edge_nodes = self._get_edge_affected_nodes(edge_diffs)
        node_diffs_by_id = self._upgrade_dependency_changed(
            node_diffs_by_id, changed_edge_nodes
        )

        # Step 6: Build result
        node_diffs = list(node_diffs_by_id.values())
        summary = self._compute_summary(node_diffs)
        baseline_info = self._build_baseline_info(baseline)
        current_info = self._build_baseline_info(current)

        return DiffResult(
            baseline_info=baseline_info,
            current_info=current_info,
            node_diffs=node_diffs,
            edge_diffs=edge_diffs,
            summary=summary,
            layer="l1",
        )

    def compute_l1_5_diff(
        self,
        baseline: VersionSnapshot,
        current: VersionSnapshot,
    ) -> DiffResult:
        """Compute L1.5 block-level diff. Same algorithm as L1 but on blocks.

        Uses block_id for matching, compares label and responsibility.
        """
        if not baseline.l1_5_snapshot:
            raise DiffError("Baseline snapshot is missing L1.5 data")
        if not current.l1_5_snapshot:
            raise DiffError("Current snapshot is missing L1.5 data")

        baseline_map = baseline.l1_5_snapshot
        current_map = current.l1_5_snapshot

        # Step 1 & 2: Match blocks and classify nodes
        node_diffs_by_id: dict[str, NodeDiff] = {}

        # Added: in current but not in baseline
        for bid, block in current_map.items():
            if bid not in baseline_map:
                node_diffs_by_id[bid] = NodeDiff(
                    node_id=bid,
                    diff_state="added",
                    current_label=block.label,
                    current_description=block.responsibility,
                    current_confidence=block.confidence,
                    baseline_label=None,
                    baseline_description=None,
                )

        # Removed: in baseline but not in current
        for bid, block in baseline_map.items():
            if bid not in current_map:
                node_diffs_by_id[bid] = NodeDiff(
                    node_id=bid,
                    diff_state="removed",
                    baseline_label=block.label,
                    baseline_description=block.responsibility,
                    current_label=None,
                    current_description=None,
                    current_confidence=None,
                )

        # Matched: in both — compare label and responsibility
        for bid in baseline_map:
            if bid in current_map:
                b_block = baseline_map[bid]
                c_block = current_map[bid]
                if (
                    b_block.label == c_block.label
                    and b_block.responsibility == c_block.responsibility
                ):
                    state = "unchanged"
                else:
                    state = "attribute_changed"
                node_diffs_by_id[bid] = NodeDiff(
                    node_id=bid,
                    diff_state=state,
                    current_label=c_block.label,
                    current_description=c_block.responsibility,
                    current_confidence=c_block.confidence,
                    baseline_label=b_block.label,
                    baseline_description=b_block.responsibility,
                )

        # L1.5 doesn't have feature_relations — no edge diff
        edge_diffs: list[EdgeDiff] = []

        # Build result
        node_diffs = list(node_diffs_by_id.values())
        summary = self._compute_summary(node_diffs)
        baseline_info = self._build_baseline_info(baseline)
        current_info = self._build_baseline_info(current)

        return DiffResult(
            baseline_info=baseline_info,
            current_info=current_info,
            node_diffs=node_diffs,
            edge_diffs=edge_diffs,
            summary=summary,
            layer="l1.5",
        )

    # ── Private helpers ──────────────────────────────────────────────────

    def _compute_edge_diffs(
        self,
        baseline_relations: list[RelationSummary],
        current_relations: list[RelationSummary],
    ) -> list[EdgeDiff]:
        """Compare edges by (from_feature, to_feature) composite key."""
        baseline_edges: dict[tuple[str, str], RelationSummary] = {
            (r.from_feature, r.to_feature): r for r in baseline_relations
        }
        current_edges: dict[tuple[str, str], RelationSummary] = {
            (r.from_feature, r.to_feature): r for r in current_relations
        }

        edge_diffs: list[EdgeDiff] = []

        # Added edges: in current but not in baseline
        for key, rel in current_edges.items():
            if key not in baseline_edges:
                edge_diffs.append(
                    EdgeDiff(
                        from_node=key[0],
                        to_node=key[1],
                        diff_state="added",
                        current_relation=rel.relation,
                        baseline_relation=None,
                    )
                )

        # Removed edges: in baseline but not in current
        for key, rel in baseline_edges.items():
            if key not in current_edges:
                edge_diffs.append(
                    EdgeDiff(
                        from_node=key[0],
                        to_node=key[1],
                        diff_state="removed",
                        current_relation=None,
                        baseline_relation=rel.relation,
                    )
                )

        # Modified edges: same key, different relation text
        for key in baseline_edges:
            if key in current_edges:
                b_rel = baseline_edges[key]
                c_rel = current_edges[key]
                if b_rel.relation != c_rel.relation:
                    edge_diffs.append(
                        EdgeDiff(
                            from_node=key[0],
                            to_node=key[1],
                            diff_state="modified",
                            current_relation=c_rel.relation,
                            baseline_relation=b_rel.relation,
                        )
                    )

        return edge_diffs

    def _get_edge_affected_nodes(
        self, edge_diffs: list[EdgeDiff]
    ) -> set[str]:
        """Get the set of node IDs affected by edge changes."""
        affected: set[str] = set()
        for ed in edge_diffs:
            affected.add(ed.from_node)
            affected.add(ed.to_node)
        return affected

    def _upgrade_dependency_changed(
        self,
        node_diffs_by_id: dict[str, NodeDiff],
        changed_edge_nodes: set[str],
    ) -> dict[str, NodeDiff]:
        """Upgrade unchanged/attribute_changed → dependency_changed for nodes with edge changes.

        Priority rules:
        - added/removed are terminal — never upgraded
        - dependency_changed > attribute_changed
        - If node was attribute_changed, move attribute details to secondary_changes
        """
        result: dict[str, NodeDiff] = {}
        for nid, nd in node_diffs_by_id.items():
            if nid in changed_edge_nodes and nd.diff_state in (
                "unchanged",
                "attribute_changed",
            ):
                secondary = None
                if nd.diff_state == "attribute_changed":
                    secondary = {
                        "attribute_changed": {
                            "old_label": nd.baseline_label,
                            "new_label": nd.current_label,
                            "old_description": nd.baseline_description,
                            "new_description": nd.current_description,
                        }
                    }
                result[nid] = NodeDiff(
                    node_id=nd.node_id,
                    diff_state="dependency_changed",
                    current_label=nd.current_label,
                    current_description=nd.current_description,
                    current_confidence=nd.current_confidence,
                    baseline_label=nd.baseline_label,
                    baseline_description=nd.baseline_description,
                    secondary_changes=secondary,
                )
            else:
                result[nid] = nd
        return result

    def _compute_summary(self, node_diffs: list[NodeDiff]) -> DiffSummary:
        """Compute aggregate counts from node diffs."""
        added = sum(1 for nd in node_diffs if nd.diff_state == "added")
        removed = sum(1 for nd in node_diffs if nd.diff_state == "removed")
        dep_changed = sum(
            1 for nd in node_diffs if nd.diff_state == "dependency_changed"
        )
        attr_changed = sum(
            1 for nd in node_diffs if nd.diff_state == "attribute_changed"
        )
        total = added + removed + dep_changed + attr_changed

        return DiffSummary(
            added_count=added,
            removed_count=removed,
            dependency_changed_count=dep_changed,
            attribute_changed_count=attr_changed,
            total_changed_count=total,
        )

    def _build_baseline_info(self, snapshot: VersionSnapshot) -> BaselineInfo:
        """Build BaselineInfo from a VersionSnapshot."""
        return BaselineInfo(
            version_id=snapshot.version_id,
            timestamp=snapshot.timestamp,
            trigger=snapshot.trigger,
            commit_hash=snapshot.commit_hash,
            git_tags=snapshot.git_tags,
            label=snapshot.label,
        )

    @staticmethod
    def build_vulnerability_diff_summary(
        baseline_vulns: list[VulnerabilityEntry],
        current_vulns: list[VulnerabilityEntry],
    ) -> VulnerabilityDiffSummary:
        """Compute vulnerability changes between two snapshots."""
        baseline_keys = {(v.cve_id, v.package, v.version): v for v in baseline_vulns}
        current_keys = {(v.cve_id, v.package, v.version): v for v in current_vulns}

        new = [v for k, v in current_keys.items() if k not in baseline_keys]
        resolved = [v for k, v in baseline_keys.items() if k not in current_keys]
        unchanged = [v for k, v in current_keys.items() if k in baseline_keys]

        return VulnerabilityDiffSummary(
            new_vulnerabilities=new,
            resolved_vulnerabilities=resolved,
            unchanged_vulnerabilities=unchanged,
        )
