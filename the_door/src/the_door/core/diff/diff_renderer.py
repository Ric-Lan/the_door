"""Diff renderer — generate Mermaid diff diagrams from DiffResult."""
from __future__ import annotations

import re

from the_door.core.rendering.mermaid_utils import escape_mermaid_label
from the_door.core.rendering.mermaid_renderer import MARKER_DEFS
from the_door.models import DiffResult, NodeDiff, BaselineInfo, DiffSummary, EdgeDiff


class DiffRenderer:
    """Generate Mermaid diff diagrams from DiffResult.

    Extends the visual patterns from MermaidRenderer but specialized for diff output.
    Uses Phase 0a diff classDefs and edge styles.
    """

    # Diff classDef definitions (from Phase 0a §4.5)
    DIFF_CLASSDEFS = {
        "diff_added": "fill:#d4edda,stroke:#28a745,stroke-width:2",
        "diff_removed": "fill:#f8d7da,stroke:#dc3545,stroke-width:2",
        "diff_dep_changed": "fill:#f5c6a0,stroke:#e67e22,stroke-width:2",
        "diff_attr_changed": "fill:#ffe0cc,stroke:#fd7e14,stroke-width:2",
        "unchanged": "fill:#f8f9fa,stroke:#dee2e6,color:#6c757d,stroke-dasharray:2 2",
    }

    # Diff symbols (from Phase 0a §4.1)
    DIFF_SYMBOLS = {
        "added": "+",
        "removed": "\u2212",  # − (minus sign)
        "dependency_changed": "\u2260",  # ≠
        "attribute_changed": "~",
    }

    # Map diff_state to classDef name
    STATE_TO_CLASSDEF = {
        "added": "diff_added",
        "removed": "diff_removed",
        "dependency_changed": "diff_dep_changed",
        "attribute_changed": "diff_attr_changed",
        "unchanged": "unchanged",
    }

    def render_l1_diff(
        self,
        diff_result: DiffResult,
        *,
        marker_context: dict[str, dict[str, bool]] | None = None,
        vulnerability_markers: dict[str, str] | None = None,
    ) -> str:
        """Render L1 diff as Mermaid flowchart.

        1. Emit summary panel as comment block
        2. Emit diff classDef definitions
        3. Emit node definitions with diff symbol prefix and confidence icon
        4. Assign classDef per node based on diff state
        5. Emit edge definitions with diff edge styles
        """
        lines: list[str] = ["flowchart TD"]

        # Summary panel
        summary_lines = self._render_summary_panel(diff_result)
        lines.extend(summary_lines)

        # ClassDef definitions
        for name, style in self.DIFF_CLASSDEFS.items():
            lines.append(f"    classDef {name} {style}")
        lines.append("")

        # Nodes
        for node_diff in diff_result.node_diffs:
            confidence_icon = self._resolve_confidence_icon(
                node_diff, marker_context
            )
            # Add ⚑ prefix if node has a vulnerability marker
            vuln_symbol = ""
            if vulnerability_markers and node_diff.node_id in vulnerability_markers:
                vuln_symbol = "⚑"
            label = self._build_node_label(node_diff, confidence_icon, vuln_symbol=vuln_symbol)
            classdef_name = self.STATE_TO_CLASSDEF[node_diff.diff_state]
            lines.append(f'    {node_diff.node_id}["{label}"]')
            lines.append(f"    class {node_diff.node_id} {classdef_name}")

        lines.append("")

        # Build set of edge-diff pairs for quick lookup
        edge_diff_pairs = {
            (ed.from_node, ed.to_node) for ed in diff_result.edge_diffs
        }

        # Edge diffs (changed edges)
        edge_index = 0
        edge_styles: list[str] = []

        for edge_diff in diff_result.edge_diffs:
            if edge_diff.diff_state == "added":
                lines.append(
                    f'    {edge_diff.from_node} -.->'
                    f'|"+"|'
                    f" {edge_diff.to_node}"
                )
                edge_styles.append(
                    f"    linkStyle {edge_index} stroke:#28a745,stroke-dasharray:5 5"
                )
            elif edge_diff.diff_state == "removed":
                lines.append(
                    f'    {edge_diff.from_node} -.-x'
                    f'|"\\u2212"|'
                    f" {edge_diff.to_node}"
                )
                edge_styles.append(
                    f"    linkStyle {edge_index} stroke:#dc3545,stroke-dasharray:5 5"
                )
            elif edge_diff.diff_state == "modified":
                lines.append(
                    f'    {edge_diff.from_node} -->'
                    f'|"~"|'
                    f" {edge_diff.to_node}"
                )
                edge_styles.append(
                    f"    linkStyle {edge_index} stroke:#fd7e14"
                )
            edge_index += 1

        # Unchanged edges: edges from current snapshot not in edge_diffs
        # We infer these from node_diffs — nodes that are not removed should
        # have their current edges rendered. But since DiffResult doesn't carry
        # the full current edge list, we render unchanged edges only if the
        # caller provides them. For now, we skip unchanged edges since they
        # aren't in the DiffResult structure.
        # (The DiffEngine only puts changed edges in edge_diffs.)

        # Emit linkStyle directives
        if edge_styles:
            lines.append("")
            lines.extend(edge_styles)

        return "\n".join(lines)

    def render_l1_5_diff(
        self,
        diff_result: DiffResult,
    ) -> str:
        """Render L1.5 diff as Mermaid flowchart. Same pattern as L1 but for blocks.

        No edge diffs for L1.5.
        """
        lines: list[str] = ["flowchart TD"]

        # Summary panel
        summary_lines = self._render_summary_panel(diff_result)
        lines.extend(summary_lines)

        # ClassDef definitions
        for name, style in self.DIFF_CLASSDEFS.items():
            lines.append(f"    classDef {name} {style}")
        lines.append("")

        # Nodes (blocks)
        for node_diff in diff_result.node_diffs:
            confidence_icon = self._resolve_confidence_icon(node_diff, None)
            label = self._build_node_label(node_diff, confidence_icon)
            classdef_name = self.STATE_TO_CLASSDEF[node_diff.diff_state]
            lines.append(f'    {node_diff.node_id}["{label}"]')
            lines.append(f"    class {node_diff.node_id} {classdef_name}")

        return "\n".join(lines)

    def _render_summary_panel(self, diff_result: DiffResult) -> list[str]:
        """Generate summary panel as Mermaid comment lines.

        Format:
        %% 📊 版本比較：[baseline_label] → [current_label]
        %%    新增 N 個功能 | 移除 N 個功能 | 修改 N 個功能（M 個依賴關係變更、K 個屬性變更）
        """
        baseline_label = self._format_baseline_label(diff_result.baseline_info)
        current_label = self._format_baseline_label(diff_result.current_info)

        lines: list[str] = []
        lines.append(f"%% \U0001f4ca 版本比較：{baseline_label} → {current_label}")

        summary = diff_result.summary
        if summary.total_changed_count == 0:
            lines.append("%%    無變更")
            return lines

        parts: list[str] = []
        if summary.added_count > 0:
            parts.append(f"新增 {summary.added_count} 個功能")
        if summary.removed_count > 0:
            parts.append(f"移除 {summary.removed_count} 個功能")

        # Modified = dependency_changed + attribute_changed
        modified_count = (
            summary.dependency_changed_count + summary.attribute_changed_count
        )
        if modified_count > 0:
            detail_parts: list[str] = []
            if summary.dependency_changed_count > 0:
                detail_parts.append(
                    f"{summary.dependency_changed_count} 個依賴關係變更"
                )
            if summary.attribute_changed_count > 0:
                detail_parts.append(
                    f"{summary.attribute_changed_count} 個屬性變更"
                )
            detail_str = "、".join(detail_parts)
            parts.append(f"修改 {modified_count} 個功能（{detail_str}）")

        lines.append("%%    " + " | ".join(parts))
        return lines

    def _format_baseline_label(self, baseline_info: BaselineInfo) -> str:
        """Format baseline label based on available metadata.

        - git ref with tags: "v1.2.0 (abc1234)"
        - git ref without tags: "abc1234" (abbreviated to 7 chars)
        - date-based: "2024-01-15 的快照"
        - manual label: use label directly
        - fallback: version_id
        """
        # Check if resolved_from matches a date pattern
        if baseline_info.resolved_from and re.match(
            r"^\d{4}-\d{2}-\d{2}$", baseline_info.resolved_from
        ):
            return f"{baseline_info.resolved_from} 的快照"

        # Git tags + commit hash
        if baseline_info.git_tags and baseline_info.commit_hash:
            tag = baseline_info.git_tags[0]
            short_hash = baseline_info.commit_hash[:7]
            return f"{tag} ({short_hash})"

        # Commit hash only (no tags)
        if baseline_info.commit_hash and not baseline_info.git_tags:
            return baseline_info.commit_hash[:7]

        # Manual label
        if baseline_info.label:
            return baseline_info.label

        # Fallback
        return baseline_info.version_id

    def _build_node_label(
        self,
        node_diff: NodeDiff,
        confidence_icon: str,
        *,
        vuln_symbol: str = "",
    ) -> str:
        """Build label: "[confidence_icon] [⚑] [diff_symbol] escaped_label".

        Uses current_label for added/unchanged/changed nodes,
        baseline_label for removed nodes.
        """
        diff_symbol = self.DIFF_SYMBOLS.get(node_diff.diff_state, "")

        # Choose the appropriate label
        if node_diff.diff_state == "removed":
            raw_label = node_diff.baseline_label or ""
        else:
            raw_label = node_diff.current_label or ""

        escaped_label = escape_mermaid_label(raw_label)

        # Compose: "{confidence_icon} {vuln_symbol} {diff_symbol} {escaped_label}".strip()
        parts = [confidence_icon, vuln_symbol, diff_symbol, escaped_label]
        return " ".join(p for p in parts if p).strip()

    def _resolve_confidence_icon(
        self,
        node_diff: NodeDiff,
        marker_context: dict[str, dict[str, bool]] | None,
    ) -> str:
        """Resolve the confidence icon for a node.

        - If marker_context has the node_id, use the confidence from there
        - Otherwise use current_confidence from NodeDiff
        - For removed nodes (no current_confidence), return empty string
        - Default for unknown confidence: empty string
        """
        # Removed nodes have no current confidence
        if node_diff.diff_state == "removed":
            return ""

        # Check marker_context first
        if marker_context and node_diff.node_id in marker_context:
            ctx = marker_context[node_diff.node_id]
            # marker_context entries have confidence key
            confidence = ctx.get("confidence", node_diff.current_confidence)
        else:
            confidence = node_diff.current_confidence

        if not confidence:
            return ""

        marker_def = MARKER_DEFS.get(confidence)
        if marker_def:
            return marker_def.icon

        return ""
