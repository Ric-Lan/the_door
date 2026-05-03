"""Report Renderer — render PipelineResult into update reports.

Supports three output formats:
1. Interactive Markdown (HTML details/summary)
2. Structured JSON (conforms to update-report.schema.json)
3. Mermaid diagram (reuses existing DiffRenderer/ScopeRenderer)

Design principles:
- Use functional language ("功能" not "節點" or "模組")
- Risk-first ordering (out_of_scope → vulnerability → semantic_drift → changes)
- Reuse existing renderer shared utilities (escape_mermaid_label etc.)

All file I/O uses encoding="utf-8" for Windows compatibility.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from the_door.core.diff.diff_renderer import DiffRenderer
from the_door.core.rendering.mermaid_utils import escape_mermaid_label
from the_door.core.scope.scope_renderer import ScopeRenderer
from the_door.core.vulnerability.vulnerability_renderer import VulnerabilityRenderer
from the_door.models import (
    DiffResult,
    L1ChangeEntry,
    L2DetailEntry,
    L3Appendix,
    NodeDiff,
    PipelineResult,
    PipelineStep,
    PipelineSummary,
    ScopeResult,
    UpdateReport,
)


# Risk-first ordering priority for change_type (lower = higher priority)
_CHANGE_TYPE_ORDER = {
    "added": 0,
    "attribute_changed": 1,
    "dependency_changed": 2,
    "removed": 3,
}

# Risk flag priority (lower = higher priority)
_RISK_FLAG_PRIORITY = {
    "out_of_scope": 0,
    "vulnerability": 1,
    "semantic_drift": 2,
}

# Change type display icons
_CHANGE_ICONS = {
    "added": "\U0001f7e2",       # 🟢
    "attribute_changed": "\U0001f7e0",  # 🟠
    "dependency_changed": "\U0001f7e0",  # 🟠
    "removed": "\U0001f534",     # 🔴
}

# Change type display labels
_CHANGE_LABELS = {
    "added": "新增",
    "attribute_changed": "修改",
    "dependency_changed": "修改",
    "removed": "移除",
}


def _risk_sort_key(entry: L1ChangeEntry) -> tuple:
    """Sort key for risk-first ordering.

    Priority:
    1. out_of_scope flag (entries with it come first)
    2. vulnerability flag
    3. semantic_drift flag
    4. change_type: added → attribute_changed/dependency_changed → removed
    """
    has_oos = 1 if "out_of_scope" not in entry.risk_flags else 0
    has_vuln = 1 if "vulnerability" not in entry.risk_flags else 0
    has_drift = 1 if "semantic_drift" not in entry.risk_flags else 0
    ct_order = _CHANGE_TYPE_ORDER.get(entry.change_type, 9)
    return (has_oos, has_vuln, has_drift, ct_order, entry.feature_id)


class ReportRenderer:
    """將 PipelineResult 渲染為版本更新報告。

    支援三種輸出格式：
    1. 互動式 Markdown（HTML details/summary）
    2. 結構化 JSON（符合 update-report.schema.json）
    3. Mermaid 圖形（複用既有 DiffRenderer/ScopeRenderer）
    """

    def render_markdown(self, result: PipelineResult) -> str:
        """渲染互動式 Markdown 報告。

        Structure:
        1. Table of Contents
        2. L0 summary (<details open>)
        3. L1 changes overview (<details open>)
        4. L2 detail expansion (<details>)
        5. L3 technical appendix (<details>)
        """
        lines: list[str] = []
        lines.append("# 版本更新報告")
        lines.append("")

        # Interruption notice
        if result.interrupted:
            lines.append("> ⚠ 管線已被使用者中斷，以下為部分結果")
            lines.append("")

        l1_changes = self._build_l1_changes(result)
        l0_summary = self._build_l0_summary(result)
        l2_details = self._build_l2_details(result, l1_changes)

        # Table of Contents
        lines.append("## 目錄")
        lines.append("")
        lines.append("- [L0 摘要](#l0-摘要)")
        lines.append("- [L1 變更總覽](#l1-變更總覽)")
        lines.append("- [L2 細節展開](#l2-細節展開)")
        lines.append("- [L3 技術附錄](#l3-技術附錄)")
        lines.append("")

        # L0 Summary (<details open>)
        lines.append('<details open id="l0-摘要">')
        lines.append("<summary><strong>L0 摘要</strong>（點擊收合）</summary>")
        lines.append("")
        lines.append(l0_summary)
        lines.append("")
        lines.append("</details>")
        lines.append("")

        # L1 Changes Overview (<details open>)
        lines.append('<details open id="l1-變更總覽">')
        change_count = len(l1_changes)
        lines.append(
            f"<summary><strong>L1 變更總覽</strong>"
            f"（{change_count} 個功能變更，點擊收合）</summary>"
        )
        lines.append("")
        lines.extend(self._render_l1_markdown(l1_changes, result))
        lines.append("")
        lines.append("</details>")
        lines.append("")

        # L2 Detail Expansion (<details>)
        lines.append('<details id="l2-細節展開">')
        lines.append(
            f"<summary><strong>L2 細節展開</strong>"
            f"（點擊展開 {len(l2_details)} 個功能的變更細節）</summary>"
        )
        lines.append("")
        lines.extend(self._render_l2_markdown(l2_details))
        lines.append("")
        lines.append("</details>")
        lines.append("")

        # L3 Technical Appendix (<details>)
        lines.append('<details id="l3-技術附錄">')
        lines.append(
            "<summary><strong>L3 技術附錄</strong>"
            "（點擊查看完整 JSON 資料）</summary>"
        )
        lines.append("")
        lines.extend(self._render_l3_markdown(result))
        lines.append("")
        lines.append("</details>")

        return "\n".join(lines)

    def render_json(self, result: PipelineResult) -> dict:
        """渲染結構化 JSON 報告（符合 update-report.schema.json）。"""
        l1_changes = self._build_l1_changes(result)
        l0_summary = self._build_l0_summary(result)
        l2_details = self._build_l2_details(result, l1_changes)
        l3_appendix = self._build_l3_appendix(result)
        pipeline_summary = self._build_pipeline_summary(result)

        report = {
            "report_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pipeline_summary": {
                "old_path": str(result.config.old_path),
                "new_path": str(result.config.new_path),
                "total_duration_ms": result.total_duration_ms,
                "steps": [
                    self._step_to_dict(s) for s in result.steps
                ],
            },
            "l0_summary": l0_summary,
            "l1_changes": [
                {
                    "feature_id": e.feature_id,
                    "change_type": e.change_type,
                    "risk_flags": list(e.risk_flags),
                    "current_label": e.current_label,
                    "baseline_label": e.baseline_label,
                }
                for e in l1_changes
            ],
            "l2_details": [
                {
                    "feature_id": d.feature_id,
                    "change_type": d.change_type,
                    "current_label": d.current_label,
                    "current_description": d.current_description,
                    "baseline_label": d.baseline_label,
                    "baseline_description": d.baseline_description,
                    "scope_state": d.scope_state,
                    "related_vulnerabilities": list(d.related_vulnerabilities),
                    "affected_relations": list(d.affected_relations),
                }
                for d in l2_details
            ],
            "l3_appendix": {
                "diff_result_json": l3_appendix.diff_result_json,
                "scope_result_json": l3_appendix.scope_result_json,
                "timeline_result_json": l3_appendix.timeline_result_json,
                "pipeline_summary": (
                    {
                        "old_path": pipeline_summary.old_path,
                        "new_path": pipeline_summary.new_path,
                        "total_duration_ms": pipeline_summary.total_duration_ms,
                        "steps": [
                            self._step_to_dict(s)
                            for s in pipeline_summary.steps
                        ],
                    }
                    if pipeline_summary
                    else None
                ),
            },
            "interrupted": result.interrupted,
        }
        return report

    def render_mermaid(self, result: PipelineResult) -> str:
        """渲染 Mermaid 圖形報告。

        Reuses:
        - DiffRenderer.render_l1_diff() for diff diagram
        - ScopeRenderer.render_l1_diff_with_scope() for scope overlay
        - VulnerabilityRenderer.format_summary_header() for vuln text summary
        """
        lines: list[str] = []

        # Top merged summary panel (Mermaid comments %%)
        summary_panel = self._build_merged_summary_panel(result)
        lines.extend(summary_panel)

        # Generate the diagram
        if result.diff_result is None:
            # No diff available — show error
            diff_step = self._find_step(result, "diff")
            error_msg = "版本比對步驟失敗"
            if diff_step and diff_step.error_message:
                error_msg += f"：{diff_step.error_message}"
            lines.append(f"%% {error_msg}")
            lines.append("flowchart TD")
            label = escape_mermaid_label(error_msg)
            lines.append(f'    error_node["{label}"]')
            return "\n".join(lines)

        # Use ScopeRenderer if scope result is available
        if result.scope_result is not None:
            scope_renderer = ScopeRenderer()
            diagram = scope_renderer.render_l1_diff_with_scope(
                result.diff_result,
                result.scope_result,
            )
        else:
            diff_renderer = DiffRenderer()
            diagram = diff_renderer.render_l1_diff(result.diff_result)

        lines.append(diagram)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Core builders
    # ------------------------------------------------------------------

    def _build_l0_summary(self, result: PipelineResult) -> str:
        """Build L0 one-sentence conclusion.

        Format: "本次更新：新增 N 個功能、修改 M 個功能、移除 K 個功能"
        + risk notice if applicable.
        No anomalies: "本次更新在預期範圍內，未發現異常"
        """
        l1_changes = self._build_l1_changes(result)

        if not l1_changes:
            # No diff result or no changes
            if result.diff_result is None:
                diff_step = self._find_step(result, "diff")
                if diff_step and diff_step.status == "failed":
                    return f"版本比對步驟失敗：{diff_step.error_message or '未知錯誤'}"
            return "本次更新在預期範圍內，未發現異常"

        # Count by change type
        added = sum(1 for e in l1_changes if e.change_type == "added")
        modified = sum(
            1 for e in l1_changes
            if e.change_type in ("attribute_changed", "dependency_changed")
        )
        removed = sum(1 for e in l1_changes if e.change_type == "removed")

        parts: list[str] = []
        if added > 0:
            parts.append(f"新增 {added} 個功能")
        if modified > 0:
            parts.append(f"修改 {modified} 個功能")
        if removed > 0:
            parts.append(f"移除 {removed} 個功能")

        if not parts:
            return "本次更新在預期範圍內，未發現異常"

        summary = "本次更新：" + "、".join(parts)

        # Check for risk items
        has_risk = any(len(e.risk_flags) > 0 for e in l1_changes)
        if not has_risk:
            return summary

        # Build risk notices
        risk_parts: list[str] = []
        oos_count = sum(
            1 for e in l1_changes if "out_of_scope" in e.risk_flags
        )
        vuln_count = sum(
            1 for e in l1_changes if "vulnerability" in e.risk_flags
        )
        drift_count = sum(
            1 for e in l1_changes if "semantic_drift" in e.risk_flags
        )

        if oos_count > 0:
            risk_parts.append(f"⚠ {oos_count} 個功能超出範圍")
        if vuln_count > 0:
            risk_parts.append(f"🔴⚑ {vuln_count} 個功能有漏洞風險")
        if drift_count > 0:
            risk_parts.append(f"🔵 {drift_count} 個功能有語意漂移")

        if risk_parts:
            summary += "（" + "、".join(risk_parts) + "）"

        return summary

    def _build_l1_changes(self, result: PipelineResult) -> list[L1ChangeEntry]:
        """Build L1 change list with risk-first ordering.

        Ordering:
        1. out_of_scope (⚠)
        2. vulnerability (🔴⚑)
        3. semantic_drift (🔵)
        4. added (🟢)
        5. attribute_changed / dependency_changed (🟠)
        6. removed (🔴)
        """
        if result.diff_result is None:
            return []

        # Build scope lookup
        scope_map: dict[str, str] = {}
        if result.scope_result is not None:
            for entry in result.scope_result.entries:
                scope_map[entry.feature_id] = entry.scope_state

        # Build vulnerability lookup (from new scan result)
        vuln_features: set[str] = set()
        if result.scan_result_new is not None and result.new_snapshot is not None:
            # Check if any vulnerability has high/critical severity
            has_high_vuln = any(
                v.severity in ("critical", "high")
                for v in result.scan_result_new.entries
            )
            if has_high_vuln:
                # Mark all changed features as having vulnerability risk
                # (Phase 5 doesn't do L2 analysis to map vulns to features)
                for nd in result.diff_result.node_diffs:
                    if nd.diff_state != "unchanged":
                        vuln_features.add(nd.node_id)

        # Build semantic drift lookup (from timeline result)
        drift_features: set[str] = set()
        if result.timeline_result is not None:
            for ft in result.timeline_result.feature_timelines:
                if ft.drift_events:
                    drift_features.add(ft.feature_id)

        entries: list[L1ChangeEntry] = []
        for nd in result.diff_result.node_diffs:
            if nd.diff_state == "unchanged":
                continue

            risk_flags: list[str] = []

            # Check out_of_scope
            if nd.node_id in scope_map:
                if scope_map[nd.node_id] == "out_of_scope":
                    risk_flags.append("out_of_scope")

            # Check vulnerability
            if nd.node_id in vuln_features:
                risk_flags.append("vulnerability")

            # Check semantic drift
            if nd.node_id in drift_features:
                risk_flags.append("semantic_drift")

            entries.append(L1ChangeEntry(
                feature_id=nd.node_id,
                change_type=nd.diff_state,
                risk_flags=risk_flags,
                current_label=nd.current_label or "",
                baseline_label=nd.baseline_label,
            ))

        # Sort by risk-first ordering
        entries.sort(key=_risk_sort_key)

        return entries

    def _build_merged_summary_panel(
        self,
        result: PipelineResult,
    ) -> list[str]:
        """Build merged summary panel (Mermaid comment lines).

        Integrates diff summary + scope summary + vulnerability summary.
        """
        lines: list[str] = []
        lines.append("%% 📊 版本更新摘要")

        # Diff summary
        if result.diff_result is not None:
            s = result.diff_result.summary
            diff_parts: list[str] = []
            if s.added_count > 0:
                diff_parts.append(f"{s.added_count} 新增")
            if s.attribute_changed_count + s.dependency_changed_count > 0:
                mod = s.attribute_changed_count + s.dependency_changed_count
                diff_parts.append(f"{mod} 修改")
            if s.removed_count > 0:
                diff_parts.append(f"{s.removed_count} 移除")
            if diff_parts:
                lines.append(f"%%    變更：{'、'.join(diff_parts)}")
            else:
                lines.append("%%    變更：無")
        else:
            diff_step = self._find_step(result, "diff")
            if diff_step and diff_step.status == "failed":
                lines.append(
                    f"%%    變更：版本比對失敗（{diff_step.error_message or '未知錯誤'}）"
                )

        # Scope summary
        if result.scope_result is not None:
            sc = result.scope_result.counts
            lines.append(
                f"%%    範圍驗核：✓ {sc.in_scope_complete} 範圍內"
                f"、⚠ {sc.out_of_scope} 範圍外"
                f"、○ {sc.in_scope_incomplete} 缺失"
            )

        # Vulnerability summary
        if result.scan_result_new is not None:
            vuln_renderer = VulnerabilityRenderer()
            vuln_summary = vuln_renderer.build_vulnerability_summary(
                result.scan_result_new.entries,
                result.scan_result_new.db_freshness,
            )
            header = vuln_renderer.format_summary_header(vuln_summary)
            lines.append(f"%%    漏洞：{header}")

        return lines

    # ------------------------------------------------------------------
    # Markdown rendering helpers
    # ------------------------------------------------------------------

    def _render_l1_markdown(
        self,
        l1_changes: list[L1ChangeEntry],
        result: PipelineResult,
    ) -> list[str]:
        """Render L1 changes as Markdown list."""
        lines: list[str] = []

        if not l1_changes:
            diff_step = self._find_step(result, "diff")
            if diff_step and diff_step.status == "failed":
                lines.append(
                    f"**版本比對步驟失敗：**{diff_step.error_message or '未知錯誤'}"
                )
            else:
                lines.append("無功能變更。")
            return lines

        for entry in l1_changes:
            icon = _CHANGE_ICONS.get(entry.change_type, "")
            change_label = _CHANGE_LABELS.get(entry.change_type, entry.change_type)
            label = entry.current_label or entry.baseline_label or entry.feature_id

            # Risk flag indicators
            risk_indicators: list[str] = []
            if "out_of_scope" in entry.risk_flags:
                risk_indicators.append("⚠ 超出範圍")
            if "vulnerability" in entry.risk_flags:
                risk_indicators.append("🔴⚑ 漏洞風險")
            if "semantic_drift" in entry.risk_flags:
                risk_indicators.append("🔵 功能說明已更新，請重新確認")

            risk_text = ""
            if risk_indicators:
                risk_text = " — " + "、".join(risk_indicators)

            lines.append(
                f"- {icon} **{label}**（{change_label}）{risk_text}"
            )

        # Vulnerability summary at the end
        if result.scan_result_new is not None:
            vuln_renderer = VulnerabilityRenderer()
            vuln_summary = vuln_renderer.build_vulnerability_summary(
                result.scan_result_new.entries,
                result.scan_result_new.db_freshness,
            )
            header = vuln_renderer.format_summary_header(vuln_summary)
            lines.append("")
            lines.append(f"**漏洞摘要：**{header}")

        return lines

    def _render_l2_markdown(
        self,
        l2_details: list[L2DetailEntry],
    ) -> list[str]:
        """Render L2 detail entries as Markdown."""
        lines: list[str] = []

        if not l2_details:
            lines.append("無細節資料。")
            return lines

        for detail in l2_details:
            label = detail.current_label or detail.feature_id
            change_label = _CHANGE_LABELS.get(detail.change_type, detail.change_type)
            lines.append(f"### {label}（{change_label}）")
            lines.append("")

            # Before/after comparison
            if detail.change_type == "added":
                lines.append(f"- **新增功能：**{detail.current_label}")
                if detail.current_description:
                    lines.append(f"- **說明：**{detail.current_description}")
            elif detail.change_type == "removed":
                lines.append(f"- **移除功能：**{detail.baseline_label or detail.feature_id}")
                if detail.baseline_description:
                    lines.append(f"- **原說明：**{detail.baseline_description}")
            else:
                # attribute_changed or dependency_changed
                if detail.baseline_label:
                    lines.append(f"- **變更前：**{detail.baseline_label}")
                if detail.baseline_description:
                    lines.append(f"- **原說明：**{detail.baseline_description}")
                if detail.current_label:
                    lines.append(f"- **變更後：**{detail.current_label}")
                if detail.current_description:
                    lines.append(f"- **新說明：**{detail.current_description}")

            # Scope state
            if detail.scope_state:
                scope_labels = {
                    "in_scope_complete": "✓ 範圍內",
                    "out_of_scope": "⚠ 超出範圍",
                    "in_scope_incomplete": "○ 範圍內但不完整",
                }
                lines.append(
                    f"- **範圍狀態：**{scope_labels.get(detail.scope_state, detail.scope_state)}"
                )

            # Vulnerabilities
            if detail.related_vulnerabilities:
                lines.append(
                    f"- **相關漏洞：**{', '.join(detail.related_vulnerabilities)}"
                )

            # Affected relations
            if detail.affected_relations:
                lines.append("- **受影響的依賴關係：**")
                for rel in detail.affected_relations:
                    lines.append(f"  - {rel}")

            lines.append("")

        return lines

    def _render_l3_markdown(self, result: PipelineResult) -> list[str]:
        """Render L3 technical appendix as Markdown."""
        lines: list[str] = []

        # Pipeline statistics
        lines.append("### 管線執行統計")
        lines.append("")
        lines.append(f"- **總耗時：**{result.total_duration_ms}ms")
        lines.append("")

        lines.append("| 步驟 | 狀態 | 耗時 | 錯誤 |")
        lines.append("|---|---|---|---|")
        for step in result.steps:
            duration = f"{step.duration_ms}ms" if step.duration_ms is not None else "-"
            error = step.error_message or "-"
            lines.append(f"| {step.step_name} | {step.status} | {duration} | {error} |")
        lines.append("")

        # Failed steps — show error messages prominently
        failed_steps = [s for s in result.steps if s.status == "failed"]
        if failed_steps:
            lines.append("### 失敗步驟")
            lines.append("")
            for step in failed_steps:
                lines.append(
                    f"- **{step.step_name}：**{step.error_message or '未知錯誤'}"
                )
            lines.append("")

        # Complete JSON data
        lines.append("### 完整 JSON 資料")
        lines.append("")

        if result.diff_result is not None:
            lines.append("<details>")
            lines.append("<summary>DiffResult JSON</summary>")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(
                self._diff_result_to_dict(result.diff_result),
                indent=2,
                ensure_ascii=False,
            ))
            lines.append("```")
            lines.append("")
            lines.append("</details>")
            lines.append("")

        if result.scope_result is not None:
            lines.append("<details>")
            lines.append("<summary>ScopeResult JSON</summary>")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(
                self._scope_result_to_dict(result.scope_result),
                indent=2,
                ensure_ascii=False,
            ))
            lines.append("```")
            lines.append("")
            lines.append("</details>")
            lines.append("")

        if result.timeline_result is not None:
            lines.append("<details>")
            lines.append("<summary>TimelineResult JSON</summary>")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(
                self._timeline_result_to_dict(result.timeline_result),
                indent=2,
                ensure_ascii=False,
            ))
            lines.append("```")
            lines.append("")
            lines.append("</details>")

        return lines

    # ------------------------------------------------------------------
    # Data builders
    # ------------------------------------------------------------------

    def _build_l2_details(
        self,
        result: PipelineResult,
        l1_changes: list[L1ChangeEntry],
    ) -> list[L2DetailEntry]:
        """Build L2 detail entries from PipelineResult and L1 changes."""
        if result.diff_result is None:
            return []

        # Build node diff lookup
        node_map: dict[str, NodeDiff] = {
            nd.node_id: nd for nd in result.diff_result.node_diffs
        }

        # Build scope lookup
        scope_map: dict[str, str] = {}
        if result.scope_result is not None:
            for entry in result.scope_result.entries:
                scope_map[entry.feature_id] = entry.scope_state

        # Build vulnerability lookup
        vuln_cves: list[str] = []
        if result.scan_result_new is not None:
            vuln_cves = [v.cve_id for v in result.scan_result_new.entries]

        # Build edge diff lookup for affected relations
        affected_relations_map: dict[str, list[str]] = {}
        for ed in result.diff_result.edge_diffs:
            rel_desc = f"{ed.from_node} → {ed.to_node}（{ed.diff_state}）"
            affected_relations_map.setdefault(ed.from_node, []).append(rel_desc)
            affected_relations_map.setdefault(ed.to_node, []).append(rel_desc)

        details: list[L2DetailEntry] = []
        for entry in l1_changes:
            nd = node_map.get(entry.feature_id)
            if nd is None:
                continue

            # Related vulnerabilities for this feature
            related_vulns: list[str] = []
            if "vulnerability" in entry.risk_flags:
                related_vulns = vuln_cves

            details.append(L2DetailEntry(
                feature_id=entry.feature_id,
                change_type=entry.change_type,
                current_label=nd.current_label or "",
                current_description=nd.current_description or "",
                baseline_label=nd.baseline_label,
                baseline_description=nd.baseline_description,
                scope_state=scope_map.get(entry.feature_id),
                related_vulnerabilities=related_vulns,
                affected_relations=affected_relations_map.get(entry.feature_id, []),
            ))

        return details

    def _build_l3_appendix(self, result: PipelineResult) -> L3Appendix:
        """Build L3 technical appendix."""
        pipeline_summary = self._build_pipeline_summary(result)

        return L3Appendix(
            diff_result_json=(
                self._diff_result_to_dict(result.diff_result)
                if result.diff_result is not None
                else None
            ),
            scope_result_json=(
                self._scope_result_to_dict(result.scope_result)
                if result.scope_result is not None
                else None
            ),
            timeline_result_json=(
                self._timeline_result_to_dict(result.timeline_result)
                if result.timeline_result is not None
                else None
            ),
            pipeline_summary=pipeline_summary,
        )

    def _build_pipeline_summary(self, result: PipelineResult) -> PipelineSummary:
        """Build pipeline summary from result."""
        return PipelineSummary(
            old_path=str(result.config.old_path),
            new_path=str(result.config.new_path),
            total_duration_ms=result.total_duration_ms,
            steps=list(result.steps),
        )

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def _step_to_dict(self, step: PipelineStep) -> dict:
        """Convert PipelineStep to dict for JSON output."""
        d: dict = {
            "step_name": step.step_name,
            "status": step.status,
        }
        if step.duration_ms is not None:
            d["duration_ms"] = step.duration_ms
        else:
            d["duration_ms"] = None
        if step.error_message is not None:
            d["error_message"] = step.error_message
        else:
            d["error_message"] = None
        return d

    def _diff_result_to_dict(self, diff_result: DiffResult) -> dict:
        """Convert DiffResult to serializable dict."""
        return {
            "baseline_info": {
                "version_id": diff_result.baseline_info.version_id,
                "timestamp": diff_result.baseline_info.timestamp,
                "trigger": diff_result.baseline_info.trigger,
            },
            "current_info": {
                "version_id": diff_result.current_info.version_id,
                "timestamp": diff_result.current_info.timestamp,
                "trigger": diff_result.current_info.trigger,
            },
            "summary": {
                "added_count": diff_result.summary.added_count,
                "removed_count": diff_result.summary.removed_count,
                "attribute_changed_count": diff_result.summary.attribute_changed_count,
                "dependency_changed_count": diff_result.summary.dependency_changed_count,
                "total_changed_count": diff_result.summary.total_changed_count,
            },
            "node_diffs": [
                {
                    "node_id": nd.node_id,
                    "diff_state": nd.diff_state,
                    "current_label": nd.current_label,
                    "baseline_label": nd.baseline_label,
                }
                for nd in diff_result.node_diffs
            ],
            "edge_diffs": [
                {
                    "from_node": ed.from_node,
                    "to_node": ed.to_node,
                    "diff_state": ed.diff_state,
                }
                for ed in diff_result.edge_diffs
            ],
            "layer": diff_result.layer,
        }

    def _scope_result_to_dict(self, scope_result: ScopeResult) -> dict:
        """Convert ScopeResult to serializable dict."""
        return {
            "scope_name": scope_result.scope_name,
            "entries": [
                {
                    "feature_id": e.feature_id,
                    "scope_state": e.scope_state,
                    "feature_label": e.feature_label,
                    "expected_label": e.expected_label,
                }
                for e in scope_result.entries
            ],
            "counts": {
                "in_scope_complete": scope_result.counts.in_scope_complete,
                "out_of_scope": scope_result.counts.out_of_scope,
                "in_scope_incomplete": scope_result.counts.in_scope_incomplete,
            },
        }

    def _timeline_result_to_dict(self, timeline_result) -> dict:
        """Convert TimelineResult to serializable dict."""
        return {
            "snapshot_count": timeline_result.snapshot_count,
            "time_range_start": timeline_result.time_range_start,
            "time_range_end": timeline_result.time_range_end,
            "summary": {
                "active_count": timeline_result.summary.active_count,
                "removed_count": timeline_result.summary.removed_count,
                "total_drift_events": timeline_result.summary.total_drift_events,
            },
            "feature_timelines": [
                {
                    "feature_id": ft.feature_id,
                    "first_seen_timestamp": ft.first_seen_timestamp,
                    "last_seen_timestamp": ft.last_seen_timestamp,
                    "change_count": ft.change_count,
                    "current_state": ft.current_state,
                    "current_label": ft.current_label,
                    "drift_events": [
                        {
                            "snapshot_version_id": de.snapshot_version_id,
                            "previous_description": de.previous_description,
                            "new_description": de.new_description,
                            "timestamp": de.timestamp,
                        }
                        for de in ft.drift_events
                    ],
                }
                for ft in timeline_result.feature_timelines
            ],
        }

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _find_step(
        self,
        result: PipelineResult,
        step_name: str,
    ) -> PipelineStep | None:
        """Find a step by name in the pipeline result."""
        for step in result.steps:
            if step.step_name == step_name:
                return step
        return None
