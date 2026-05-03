"""Timeline Engine — multi-version timeline analysis.

Pure functions, no I/O, no side effects. Analyzes a sequence of
VersionSnapshots and produces FeatureTimeline records for every feature
that has ever appeared in any snapshot.
"""
from __future__ import annotations

from the_door.models import (
    FeatureSummary,
    FeatureTimeline,
    SemanticDriftEvent,
    TimelineResult,
    TimelineSummary,
    VersionSnapshot,
)


class TimelineEngine:
    """多版本時間軸分析引擎。Pure function — 無 I/O。"""

    def analyze(
        self,
        snapshots: list[VersionSnapshot],
    ) -> TimelineResult:
        """分析 snapshot 序列，產生完整的時間軸結果。

        Algorithm:
        1. Sort snapshots by timestamp
        2. Collect all distinct feature_ids (union of all l1_snapshot keys)
        3. For each feature_id build a FeatureTimeline
        4. Compute TimelineSummary
        5. Return TimelineResult

        Edge cases:
        - Empty list → empty result with snapshot_count=0
        - Single snapshot → all change_count=0, drift_events empty
        """
        if not snapshots:
            return TimelineResult(
                snapshot_count=0,
                time_range_start=None,
                time_range_end=None,
                feature_timelines=[],
                summary=TimelineSummary(),
            )

        sorted_snapshots = sorted(snapshots, key=lambda s: s.timestamp)

        # Collect all distinct feature_ids across all snapshots
        all_feature_ids: set[str] = set()
        for snap in sorted_snapshots:
            all_feature_ids.update(snap.l1_snapshot.keys())

        # Build a FeatureTimeline for each feature_id
        feature_timelines: list[FeatureTimeline] = []
        for fid in sorted(all_feature_ids):
            ft = self._build_feature_timeline(sorted_snapshots, fid)
            feature_timelines.append(ft)

        summary = self._compute_summary(feature_timelines)

        return TimelineResult(
            snapshot_count=len(sorted_snapshots),
            time_range_start=sorted_snapshots[0].timestamp,
            time_range_end=sorted_snapshots[-1].timestamp,
            feature_timelines=feature_timelines,
            summary=summary,
        )

    def analyze_feature(
        self,
        snapshots: list[VersionSnapshot],
        feature_id: str,
    ) -> FeatureTimeline | None:
        """Analyze single feature. Returns None if feature_id not in any snapshot."""
        if not snapshots:
            return None

        sorted_snapshots = sorted(snapshots, key=lambda s: s.timestamp)

        # Check if feature_id exists in any snapshot
        found = any(
            feature_id in snap.l1_snapshot for snap in sorted_snapshots
        )
        if not found:
            return None

        return self._build_feature_timeline(sorted_snapshots, feature_id)

    def _build_feature_timeline(
        self,
        sorted_snapshots: list[VersionSnapshot],
        feature_id: str,
    ) -> FeatureTimeline:
        """Build a FeatureTimeline for a single feature across sorted snapshots."""
        first_seen_ts: str | None = None
        last_seen_ts: str | None = None
        last_known_label: str = ""
        change_count = 0
        drift_events: list[SemanticDriftEvent] = []
        prev_feature: FeatureSummary | None = None

        for snap in sorted_snapshots:
            curr_feature = snap.l1_snapshot.get(feature_id)

            if curr_feature is not None:
                # Track first/last seen
                if first_seen_ts is None:
                    first_seen_ts = snap.timestamp
                last_seen_ts = snap.timestamp
                last_known_label = curr_feature.label

                # Compare with previous occurrence
                if prev_feature is not None:
                    label_changed = prev_feature.label != curr_feature.label
                    desc_changed = (
                        prev_feature.description != curr_feature.description
                    )

                    # change_count: label or description changed
                    # (confidence changes are EXCLUDED)
                    if label_changed or desc_changed:
                        change_count += 1

                    # Semantic drift: label unchanged + description changed
                    drift = self._detect_drift(
                        prev_feature, curr_feature, snap
                    )
                    if drift is not None:
                        drift_events.append(drift)

                prev_feature = curr_feature
            # If feature not in this snapshot, prev_feature stays as-is
            # so we can detect changes when it reappears

        # Determine current_state: active if in latest snapshot, removed if not
        latest_snapshot = sorted_snapshots[-1]
        current_state = (
            "active"
            if feature_id in latest_snapshot.l1_snapshot
            else "removed"
        )

        return FeatureTimeline(
            feature_id=feature_id,
            first_seen_timestamp=first_seen_ts or "",
            last_seen_timestamp=last_seen_ts or "",
            change_count=change_count,
            current_state=current_state,
            current_label=last_known_label,
            drift_events=drift_events,
        )

    def _detect_drift(
        self,
        prev_feature: FeatureSummary,
        curr_feature: FeatureSummary,
        snapshot: VersionSnapshot,
    ) -> SemanticDriftEvent | None:
        """Detect semantic drift between consecutive snapshots for same feature.

        Drift = label unchanged + description changed.
        If both label AND description changed → normal attribute change, no drift.
        If neither changed → no drift.
        """
        label_changed = prev_feature.label != curr_feature.label
        desc_changed = prev_feature.description != curr_feature.description

        if not label_changed and desc_changed:
            return SemanticDriftEvent(
                snapshot_version_id=snapshot.version_id,
                previous_description=prev_feature.description,
                new_description=curr_feature.description,
                timestamp=snapshot.timestamp,
            )
        return None

    def _compute_summary(
        self,
        feature_timelines: list[FeatureTimeline],
    ) -> TimelineSummary:
        """Compute aggregate stats."""
        active_count = sum(
            1 for ft in feature_timelines if ft.current_state == "active"
        )
        removed_count = sum(
            1 for ft in feature_timelines if ft.current_state == "removed"
        )
        total_drift_events = sum(
            len(ft.drift_events) for ft in feature_timelines
        )
        return TimelineSummary(
            active_count=active_count,
            removed_count=removed_count,
            total_drift_events=total_drift_events,
        )
