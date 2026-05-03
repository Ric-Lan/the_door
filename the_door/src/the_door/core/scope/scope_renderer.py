"""Scope renderer — Mermaid scope badges, summary panels, and merged panels.

Compose, not copy: reuses shared utilities from existing rendering modules.
Scope badges are LABEL-EMBEDDED only (symbol<sup>scope</sup>), NEVER classDef.
"""
from __future__ import annotations

from the_door.core.rendering.mermaid_utils import escape_mermaid_label
from the_door.core.rendering.mermaid_renderer import resolve_marker_state, MARKER_DEFS
from the_door.core.diff.diff_renderer import DiffRenderer
from the_door.models import ScopeResult, ScopeEntry, L1Output, DiffResult, NodeDiff


class ScopeRenderer:
    """Mermaid 範圍角標徽章渲染器。

    在節點標籤末端嵌入 scope badge（✓/⚠/○ <sup>scope</sup>），
    不使用 classDef。可與 confidence icon、diff symbol、vuln symbol 共存。

    設計原則：compose 而非 copy。內部複用既有共用工具：
    - escape_mermaid_label()（from mermaid_utils）
    - resolve_marker_state() / MARKER_DEFS（from mermaid_renderer）
    - DiffRenderer.DIFF_SYMBOLS（from diff_renderer）
    不重複實作 label escaping、confidence resolution、diff symbol 邏輯。
    """

    SCOPE_BADGES: dict[str, str] = {
        "in_scope_complete": "✓",
        "out_of_scope": "⚠",
        "in_scope_incomplete": "○",
    }

    def build_scope_badge(self, scope_state: str) -> str:
        """產生 scope badge 字串，例如 ``'✓<sup>scope</sup>'``。

        Returns empty string for unknown states.
        """
        symbol = self.SCOPE_BADGES.get(scope_state, "")
        if not symbol:
            return ""
        return f"{symbol}<sup>scope</sup>"

    # ------------------------------------------------------------------
    # Scope Summary Panel
    # ------------------------------------------------------------------

    def render_scope_summary_panel(
        self,
        scope_result: ScopeResult,
    ) -> list[str]:
        """產生範圍驗核摘要面板（Mermaid 註解行）。

        Format::

            %% 📋 {scope_name} 範圍驗核
            %%    ✓ 範圍內已完成：N 個功能
            %%    ⚠ 超出範圍：N 個功能（需調查）
            %%    ○ 範圍內未完成：N 個功能

        Display rules:
        - ✓ line ALWAYS shown (even if count=0)
        - ⚠ line OMITTED when out_of_scope count=0, includes「（需調查）」suffix when shown
        - ○ line OMITTED when in_scope_incomplete count=0
        """
        lines: list[str] = []
        counts = scope_result.counts

        lines.append(f"%% 📋 {scope_result.scope_name} 範圍驗核")
        # ✓ always shown
        lines.append(f"%%    ✓ 範圍內已完成：{counts.in_scope_complete} 個功能")
        # ⚠ only when > 0
        if counts.out_of_scope > 0:
            lines.append(
                f"%%    ⚠ 超出範圍：{counts.out_of_scope} 個功能（需調查）"
            )
        # ○ only when > 0
        if counts.in_scope_incomplete > 0:
            lines.append(
                f"%%    ○ 範圍內未完成：{counts.in_scope_incomplete} 個功能"
            )

        return lines

    # ------------------------------------------------------------------
    # L1 with Scope
    # ------------------------------------------------------------------

    def render_l1_with_scope(
        self,
        l1_output: L1Output,
        scope_result: ScopeResult,
        *,
        marker_context: dict[str, dict[str, bool]] | None = None,
        vulnerability_border_styles: dict[str, str] | None = None,
    ) -> str:
        """渲染帶有 scope badges 的 L1 Mermaid 圖。

        When scope_result has no entries, output is identical to
        MermaidRenderer.render_l1() (backward compatibility).
        """
        lines: list[str] = []

        # Build scope lookup: feature_id -> ScopeEntry
        scope_map: dict[str, ScopeEntry] = {
            e.feature_id: e for e in scope_result.entries
        }
        has_scope = len(scope_map) > 0

        # Scope summary panel (only when scope entries exist)
        if has_scope:
            lines.extend(self.render_scope_summary_panel(scope_result))

        lines.append("flowchart TD")

        if not l1_output.features and not has_scope:
            lines.append('    empty["No features identified"]')
            return "\n".join(lines)

        # Confidence classDef definitions (reuse MARKER_DEFS)
        lines.append("    %% Confidence-based styling")
        for key, mdef in MARKER_DEFS.items():
            parts = [f"fill:{mdef.fill}", f"stroke:{mdef.stroke}"]
            if mdef.stroke_dasharray:
                parts.append(f"stroke-dasharray:{mdef.stroke_dasharray}")
            if mdef.stroke_width != 2:
                parts.append(f"stroke-width:{mdef.stroke_width}")
            lines.append(f"    classDef {key} {','.join(parts)}")
        lines.append("")

        feature_ids = {f.feature_id for f in l1_output.features}

        # Nodes from L1Output
        for feature in l1_output.features:
            ctx = (marker_context or {}).get(feature.feature_id, {})
            state = resolve_marker_state(
                feature,
                regenerated_differs=ctx.get("regenerated_differs", False),
                incomplete_reading=ctx.get("incomplete_reading", False),
            )
            marker = MARKER_DEFS[state]
            label = escape_mermaid_label(feature.label)
            trigger = escape_mermaid_label(feature.trigger_description)

            # Build scope badge if scope entry exists for this feature
            scope_badge = ""
            if feature.feature_id in scope_map:
                scope_badge = self.build_scope_badge(
                    scope_map[feature.feature_id].scope_state
                )

            # Label format: "{confidence_icon} {feature_label} {scope_badge}"
            # with trigger on second line
            if scope_badge:
                node_label = (
                    f"{marker.icon} {label} {scope_badge}<br/><i>{trigger}</i>"
                )
            else:
                node_label = f"{marker.icon} {label}<br/><i>{trigger}</i>"

            lines.append(f'    {feature.feature_id}["{node_label}"]')
            lines.append(f"    class {feature.feature_id} {state}")

        # Placeholder nodes for in_scope_incomplete features NOT in L1Output
        for entry in scope_result.entries:
            if (
                entry.scope_state == "in_scope_incomplete"
                and entry.feature_id not in feature_ids
            ):
                expected = escape_mermaid_label(
                    entry.expected_label or entry.feature_id
                )
                badge = self.build_scope_badge("in_scope_incomplete")
                placeholder_label = f"{expected} {badge}"
                lines.append(
                    f'    {entry.feature_id}["{placeholder_label}"]'
                )
                lines.append(
                    f"    style {entry.feature_id} stroke-dasharray:5 5"
                )

        lines.append("")

        # Edges
        for rel in l1_output.feature_relations:
            if (
                rel.from_feature in feature_ids
                and rel.to_feature in feature_ids
            ):
                lines.append(f"    {rel.from_feature} --> {rel.to_feature}")

        # Vulnerability classDefs and node overrides
        if vulnerability_border_styles:
            lines.append("")
            lines.append("    %% Vulnerability styling")
            lines.append(
                "    classDef vuln_high "
                "fill:#f8d7da,stroke:#dc3545,stroke-width:3"
            )
            lines.append(
                "    classDef vuln_medium "
                "fill:#ffe0cc,stroke:#fd7e14,stroke-width:3"
            )
            for fid, style in vulnerability_border_styles.items():
                if fid in feature_ids:
                    if "dc3545" in style:
                        lines.append(f"    class {fid} vuln_high")
                    elif "fd7e14" in style:
                        lines.append(f"    class {fid} vuln_medium")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Merged Summary Panel (Diff + Scope)
    # ------------------------------------------------------------------

    def render_merged_summary_panel(
        self,
        scope_result: ScopeResult,
        diff_result: DiffResult,
    ) -> list[str]:
        """產生 Diff+Scope 合併摘要面板。

        Format::

            %% 📊 {scope_name} 變更驗核
            %%    ✓ 範圍內變更：N 個（M 新增、K 修改）
            %%    ⚠ 範圍外變更：N 個（需調查）
            %%    ○ 預期變更缺失：N 個（尚未完成）
        """
        lines: list[str] = []
        lines.append(f"%% 📊 {scope_result.scope_name} 變更驗核")

        # Build scope lookup
        scope_map: dict[str, ScopeEntry] = {
            e.feature_id: e for e in scope_result.entries
        }

        # Categorize diff nodes by scope state
        in_scope_added = 0
        in_scope_modified = 0
        in_scope_total = 0
        out_of_scope_total = 0

        for nd in diff_result.node_diffs:
            if nd.diff_state == "unchanged":
                continue
            entry = scope_map.get(nd.node_id)
            if entry and entry.scope_state == "in_scope_complete":
                in_scope_total += 1
                if nd.diff_state == "added":
                    in_scope_added += 1
                else:
                    # removed, dependency_changed, attribute_changed → "修改"
                    in_scope_modified += 1
            else:
                # out_of_scope or not in scope map → out-of-scope change
                out_of_scope_total += 1

        # Count in_scope_incomplete
        incomplete_count = scope_result.counts.in_scope_incomplete

        # ✓ line — always shown
        detail_parts: list[str] = []
        if in_scope_added > 0:
            detail_parts.append(f"{in_scope_added} 新增")
        if in_scope_modified > 0:
            detail_parts.append(f"{in_scope_modified} 修改")
        if detail_parts:
            detail_str = "、".join(detail_parts)
            lines.append(
                f"%%    ✓ 範圍內變更：{in_scope_total} 個（{detail_str}）"
            )
        else:
            lines.append(f"%%    ✓ 範圍內變更：{in_scope_total} 個")

        # ⚠ line — only when > 0
        if out_of_scope_total > 0:
            lines.append(
                f"%%    ⚠ 範圍外變更：{out_of_scope_total} 個（需調查）"
            )

        # ○ line — only when > 0
        if incomplete_count > 0:
            lines.append(
                f"%%    ○ 預期變更缺失：{incomplete_count} 個（尚未完成）"
            )

        return lines

    # ------------------------------------------------------------------
    # L1 Diff with Scope
    # ------------------------------------------------------------------

    def render_l1_diff_with_scope(
        self,
        diff_result: DiffResult,
        scope_result: ScopeResult,
        *,
        marker_context: dict[str, dict[str, bool]] | None = None,
        vulnerability_markers: dict[str, str] | None = None,
    ) -> str:
        """渲染帶有 scope badges 的 L1 diff Mermaid 圖。

        Label format:
        ``"{confidence_icon} {vuln_symbol} {diff_symbol} {feature_label} {scope_badge}<sup>scope</sup>"``

        Uses merged summary panel (replaces separate diff + scope panels).
        """
        lines: list[str] = []

        scope_map: dict[str, ScopeEntry] = {
            e.feature_id: e for e in scope_result.entries
        }
        has_scope = len(scope_map) > 0

        # Merged summary panel (replaces separate diff + scope panels)
        if has_scope:
            lines.extend(
                self.render_merged_summary_panel(scope_result, diff_result)
            )

        lines.append("flowchart TD")

        # Diff classDef definitions (reuse DiffRenderer constants)
        for name, style in DiffRenderer.DIFF_CLASSDEFS.items():
            lines.append(f"    classDef {name} {style}")
        lines.append("")

        diff_node_ids: set[str] = set()

        # Nodes
        for node_diff in diff_result.node_diffs:
            diff_node_ids.add(node_diff.node_id)

            confidence_icon = self._resolve_confidence_icon(
                node_diff, marker_context
            )

            # Vulnerability symbol
            vuln_symbol = ""
            if (
                vulnerability_markers
                and node_diff.node_id in vulnerability_markers
            ):
                vuln_symbol = "⚑"

            # Diff symbol (reuse DiffRenderer.DIFF_SYMBOLS)
            diff_symbol = DiffRenderer.DIFF_SYMBOLS.get(
                node_diff.diff_state, ""
            )

            # Feature label
            if node_diff.diff_state == "removed":
                raw_label = node_diff.baseline_label or ""
            else:
                raw_label = node_diff.current_label or ""
            escaped_label = escape_mermaid_label(raw_label)

            # Scope badge
            scope_badge = ""
            if node_diff.node_id in scope_map:
                scope_badge = self.build_scope_badge(
                    scope_map[node_diff.node_id].scope_state
                )

            # Compose label: "{confidence_icon} {vuln_symbol} {diff_symbol} {feature_label} {scope_badge}"
            label_parts = [
                confidence_icon,
                vuln_symbol,
                diff_symbol,
                escaped_label,
            ]
            label_core = " ".join(p for p in label_parts if p).strip()
            if scope_badge:
                label = f"{label_core} {scope_badge}"
            else:
                label = label_core

            classdef_name = DiffRenderer.STATE_TO_CLASSDEF[
                node_diff.diff_state
            ]
            lines.append(f'    {node_diff.node_id}["{label}"]')
            lines.append(f"    class {node_diff.node_id} {classdef_name}")

        # Placeholder nodes for in_scope_incomplete features not in diff
        for entry in scope_result.entries:
            if (
                entry.scope_state == "in_scope_incomplete"
                and entry.feature_id not in diff_node_ids
            ):
                expected = escape_mermaid_label(
                    entry.expected_label or entry.feature_id
                )
                badge = self.build_scope_badge("in_scope_incomplete")
                placeholder_label = f"{expected} {badge}"
                lines.append(
                    f'    {entry.feature_id}["{placeholder_label}"]'
                )
                lines.append(
                    f"    style {entry.feature_id} stroke-dasharray:5 5"
                )

        lines.append("")

        # Edge diffs
        edge_index = 0
        edge_styles: list[str] = []

        for edge_diff in diff_result.edge_diffs:
            if edge_diff.diff_state == "added":
                lines.append(
                    f"    {edge_diff.from_node} -.->"
                    f'|"+"|'
                    f" {edge_diff.to_node}"
                )
                edge_styles.append(
                    f"    linkStyle {edge_index} "
                    f"stroke:#28a745,stroke-dasharray:5 5"
                )
            elif edge_diff.diff_state == "removed":
                lines.append(
                    f"    {edge_diff.from_node} -.-x"
                    f'|"\\u2212"|'
                    f" {edge_diff.to_node}"
                )
                edge_styles.append(
                    f"    linkStyle {edge_index} "
                    f"stroke:#dc3545,stroke-dasharray:5 5"
                )
            elif edge_diff.diff_state == "modified":
                lines.append(
                    f"    {edge_diff.from_node} -->"
                    f'|"~"|'
                    f" {edge_diff.to_node}"
                )
                edge_styles.append(
                    f"    linkStyle {edge_index} stroke:#fd7e14"
                )
            edge_index += 1

        # Emit linkStyle directives
        if edge_styles:
            lines.append("")
            lines.extend(edge_styles)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_confidence_icon(
        self,
        node_diff: NodeDiff,
        marker_context: dict[str, dict[str, bool]] | None,
    ) -> str:
        """Resolve the confidence icon for a diff node.

        Reuses the same logic as DiffRenderer._resolve_confidence_icon.
        """
        if node_diff.diff_state == "removed":
            return ""

        if marker_context and node_diff.node_id in marker_context:
            ctx = marker_context[node_diff.node_id]
            confidence = ctx.get("confidence", node_diff.current_confidence)
        else:
            confidence = node_diff.current_confidence

        if not confidence:
            return ""

        marker_def = MARKER_DEFS.get(confidence)
        if marker_def:
            return marker_def.icon

        return ""
