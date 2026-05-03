"""Timeline renderer — generate Mermaid gantt charts or plain text from TimelineResult."""
from __future__ import annotations

from the_door.core.rendering.mermaid_utils import escape_mermaid_label
from the_door.models import (
    FeatureTimeline,
    TimelineResult,
    VersionSnapshot,
    FeatureSummary,
)


class TimelineRenderer:
    """將 TimelineResult 渲染為 Mermaid gantt 圖形或純文字。

    複用 escape_mermaid_label() 共用函式。
    摘要面板用 Mermaid comments（%%）。
    """

    # 時間軸視覺標記
    TIMELINE_MARKERS = {
        "first_seen": "\U0001f7e2",       # 🟢 功能首次出現
        "removed": "\U0001f534",           # 🔴 功能被移除
        "attribute_changed": "\U0001f7e0", # 🟠 功能屬性變更
        "semantic_drift": "\U0001f535",    # 🔵 語意漂移
        "unchanged": "\u26aa",             # ⚪ 功能無變化
    }

    def render_mermaid(self, result: TimelineResult) -> str:
        """渲染 Mermaid gantt 圖形。

        1. 輸出摘要面板（Mermaid comments）
        2. 輸出 gantt 圖形宣告
        3. 以功能為 section，版本狀態為 task
        4. 使用視覺標記前綴區分狀態（🟢/🔴/🟠/🔵/⚪）
        5. 語意漂移事件附加提示文字
        """
        lines: list[str] = []

        # Summary panel
        summary_lines = self._render_summary_panel(result)
        lines.extend(summary_lines)

        # Gantt chart declaration
        lines.append("gantt")
        lines.append("    dateFormat YYYY-MM-DD")
        lines.append("    title 功能演進時間軸")
        lines.append("")

        if not result.feature_timelines:
            lines.append("    %% 無功能資料")
            return "\n".join(lines)

        # Build drift event lookup: feature_id -> set of timestamps
        drift_timestamps: dict[str, set[str]] = {}
        for ft in result.feature_timelines:
            if ft.drift_events:
                drift_timestamps[ft.feature_id] = {
                    ev.timestamp for ev in ft.drift_events
                }

        # Sections per feature, sorted by first_seen_timestamp ascending
        sorted_features = sorted(
            result.feature_timelines, key=lambda ft: ft.first_seen_timestamp
        )

        for ft in sorted_features:
            escaped_label = escape_mermaid_label(ft.current_label)
            lines.append(f"    section {escaped_label}")

            # Determine the marker for this feature's overall state
            first_date = ft.first_seen_timestamp[:10]  # YYYY-MM-DD
            last_date = ft.last_seen_timestamp[:10]

            # First seen task
            first_marker = self.TIMELINE_MARKERS["first_seen"]
            escaped_first = escape_mermaid_label(
                f"{first_marker} 首次出現"
            )
            lines.append(
                f"    {escaped_first} :active, {first_date}, {last_date}"
            )

            # Drift events as milestone tasks
            feature_drifts = drift_timestamps.get(ft.feature_id, set())
            for ev in ft.drift_events:
                drift_marker = self.TIMELINE_MARKERS["semantic_drift"]
                drift_date = ev.timestamp[:10]
                hint = "功能說明已更新，請重新確認"
                escaped_drift = escape_mermaid_label(
                    f"{drift_marker} {hint}"
                )
                lines.append(
                    f"    {escaped_drift} :milestone, {drift_date}, 0d"
                )

            # Removed marker if feature is removed
            if ft.current_state == "removed":
                removed_marker = self.TIMELINE_MARKERS["removed"]
                escaped_removed = escape_mermaid_label(
                    f"{removed_marker} 已移除"
                )
                lines.append(
                    f"    {escaped_removed} :done, {last_date}, 0d"
                )

        return "\n".join(lines)

    def render_text(self, result: TimelineResult) -> str:
        """渲染純文字功能演進摘要。

        格式：
        === 功能演進時間軸 ===
        分析版本數：N | 時間範圍：YYYY-MM-DD ~ YYYY-MM-DD
        活躍功能：N | 已移除功能：N | 語意漂移事件：N

        功能名稱          首次出現      變更次數  狀態    漂移次數
        ─────────────────────────────────────────────────────
        使用者認證          2024-01-15    3        active  1
          🔵 2024-02-01: 功能說明已更新
        ...

        按 first_seen_timestamp 排序（最早出現的功能排在前面）。
        使用功能語言（「功能」而非「節點」或「模組」）。
        """
        lines: list[str] = []

        # Header
        lines.append("=== 功能演進時間軸 ===")

        # Stats line
        time_start = result.time_range_start[:10] if result.time_range_start else "N/A"
        time_end = result.time_range_end[:10] if result.time_range_end else "N/A"
        lines.append(
            f"分析版本數：{result.snapshot_count} | "
            f"時間範圍：{time_start} ~ {time_end}"
        )
        lines.append(
            f"活躍功能：{result.summary.active_count} | "
            f"已移除功能：{result.summary.removed_count} | "
            f"語意漂移事件：{result.summary.total_drift_events}"
        )
        lines.append("")

        if not result.feature_timelines:
            lines.append("（無功能資料）")
            return "\n".join(lines)

        # Table header
        lines.append(
            f"{'功能名稱':<18}{'首次出現':<14}{'變更次數':<10}{'狀態':<10}{'漂移次數'}"
        )
        lines.append("─" * 60)

        # Sort by first_seen_timestamp ascending
        sorted_features = sorted(
            result.feature_timelines, key=lambda ft: ft.first_seen_timestamp
        )

        for ft in sorted_features:
            first_date = ft.first_seen_timestamp[:10]
            drift_count = len(ft.drift_events)
            lines.append(
                f"{ft.current_label:<18}{first_date:<14}"
                f"{ft.change_count:<10}{ft.current_state:<10}{drift_count}"
            )

            # Drift detail lines
            drift_marker = self.TIMELINE_MARKERS["semantic_drift"]
            for ev in ft.drift_events:
                drift_date = ev.timestamp[:10]
                lines.append(f"  {drift_marker} {drift_date}: 功能說明已更新")

        return "\n".join(lines)

    def render_feature_detail(
        self,
        feature_timeline: FeatureTimeline,
        snapshots: list[VersionSnapshot],
    ) -> str:
        """渲染單一功能的詳細演進記錄。

        Per-version: commit_hash, git_tags, label, description, confidence,
        source_node_count, state marker.
        Side-by-side description comparison for drift events.
        """
        lines: list[str] = []
        lines.append(f"=== 功能詳細演進：{feature_timeline.feature_id} ===")
        lines.append("")

        # Build drift event lookup: timestamp -> SemanticDriftEvent
        drift_by_timestamp: dict[str, object] = {}
        for ev in feature_timeline.drift_events:
            drift_by_timestamp[ev.timestamp] = ev

        # Sort snapshots by timestamp
        sorted_snapshots = sorted(snapshots, key=lambda s: s.timestamp)

        # Track previous feature for change detection
        prev_feature: FeatureSummary | None = None
        version_num = 0

        for snap in sorted_snapshots:
            feature = snap.l1_snapshot.get(feature_timeline.feature_id)

            # Determine state marker
            if feature is None and prev_feature is not None:
                # Feature was removed in this snapshot
                version_num += 1
                marker = self.TIMELINE_MARKERS["removed"]
                state_label = "已移除"

                # Version header
                tags_str = ", ".join(snap.git_tags) if snap.git_tags else ""
                commit_str = snap.commit_hash or ""
                header_parts = [f"版本 {version_num}:"]
                if commit_str:
                    header_parts.append(commit_str)
                if tags_str:
                    header_parts.append(f"({tags_str})")
                lines.append(" ".join(header_parts))
                lines.append(f"  時間：{snap.timestamp}")
                lines.append(f"  狀態：{state_label} {marker}")
                lines.append("")
                prev_feature = None
                continue

            if feature is None:
                # Feature not present in this snapshot and wasn't before
                continue

            version_num += 1

            # Determine state
            if prev_feature is None:
                marker = self.TIMELINE_MARKERS["first_seen"]
                state_label = "首次出現"
            elif snap.timestamp in drift_by_timestamp:
                marker = self.TIMELINE_MARKERS["semantic_drift"]
                state_label = "語意漂移"
            elif (
                feature.label != prev_feature.label
                or feature.description != prev_feature.description
            ):
                marker = self.TIMELINE_MARKERS["attribute_changed"]
                state_label = "屬性變更"
            else:
                marker = self.TIMELINE_MARKERS["unchanged"]
                state_label = "無變化"

            # Version header
            tags_str = ", ".join(snap.git_tags) if snap.git_tags else ""
            commit_str = snap.commit_hash or ""
            header_parts = [f"版本 {version_num}:"]
            if commit_str:
                header_parts.append(commit_str)
            if tags_str:
                header_parts.append(f"({tags_str})")
            if snap.label:
                header_parts.append(snap.label)
            lines.append(" ".join(header_parts))

            lines.append(f"  時間：{snap.timestamp}")
            lines.append(f"  Label: {feature.label}")
            lines.append(f"  Description: {feature.description}")
            lines.append(f"  Confidence: {feature.confidence}")
            lines.append(f"  Source Nodes: {feature.source_node_count}")
            lines.append(f"  狀態：{state_label} {marker}")

            # Side-by-side description comparison for drift events
            if snap.timestamp in drift_by_timestamp:
                drift_ev = drift_by_timestamp[snap.timestamp]
                lines.append(f"  前版說明：{drift_ev.previous_description}")
                lines.append(f"  新版說明：{drift_ev.new_description}")

            lines.append("")
            prev_feature = feature

        return "\n".join(lines)

    def _render_summary_panel(self, result: TimelineResult) -> list[str]:
        """產生摘要面板（Mermaid 註解行）。

        格式：
        %% 📈 功能演進時間軸
        %%    分析版本數：N | 時間範圍：YYYY-MM-DD ~ YYYY-MM-DD
        %%    活躍功能：N | 已移除功能：N | 語意漂移事件：N
        """
        lines: list[str] = []

        lines.append("%% \U0001f4c8 功能演進時間軸")

        time_start = result.time_range_start[:10] if result.time_range_start else "N/A"
        time_end = result.time_range_end[:10] if result.time_range_end else "N/A"

        lines.append(
            f"%%    分析版本數：{result.snapshot_count} | "
            f"時間範圍：{time_start} ~ {time_end}"
        )
        lines.append(
            f"%%    活躍功能：{result.summary.active_count} | "
            f"已移除功能：{result.summary.removed_count} | "
            f"語意漂移事件：{result.summary.total_drift_events}"
        )

        return lines
