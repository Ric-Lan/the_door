"""Manage version snapshot creation, persistence, and retrieval.

All file I/O uses encoding="utf-8" for Windows compatibility.
Snapshots stored as individual JSON files in .the-door/snapshots/.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path

from the_door.models import (
    BaselineInfo,
    BlockSummary,
    DatabaseFreshness,
    FeatureSummary,
    RelationSummary,
    SnapshotError,
    SnapshotNotFoundError,
    VersionSnapshot,
    VulnerabilityEntry,
)

logger = logging.getLogger(__name__)


class SnapshotStore:
    """Manage version snapshot creation, persistence, and retrieval."""

    def __init__(self, project_root: Path):
        self._snapshots_dir = project_root / ".the-door" / "snapshots"

    def create_snapshot(
        self,
        *,
        l1_snapshot: dict[str, FeatureSummary],
        feature_relations: list[RelationSummary],
        analyzed_files: list[str],
        commit_hash: str | None = None,
        git_tags: list[str] | None = None,
        trigger: str = "commit",
        label: str | None = None,
        l1_5_snapshot: dict[str, BlockSummary] | None = None,
        vulnerabilities: list[VulnerabilityEntry] | None = None,
        db_freshness: DatabaseFreshness | None = None,
    ) -> VersionSnapshot:
        """Create and persist a new snapshot. Returns the created VersionSnapshot.

        Generates a UUID v4 version_id and ISO8601 timestamp (UTC).
        Creates .the-door/snapshots/ directory if it doesn't exist.
        If trigger is "manual" and no label provided, auto-generates one.
        """
        version_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()

        if trigger == "manual" and label is None:
            label = f"Auto-snapshot {now.strftime('%Y-%m-%d %H:%M:%S')}"

        snapshot = VersionSnapshot(
            version_id=version_id,
            timestamp=timestamp,
            trigger=trigger,
            l1_snapshot=l1_snapshot,
            analyzed_files=analyzed_files,
            commit_hash=commit_hash,
            git_tags=git_tags if git_tags is not None else [],
            label=label,
            l1_5_snapshot=l1_5_snapshot if l1_5_snapshot is not None else {},
            feature_relations_snapshot=feature_relations,
            vulnerabilities_snapshot=vulnerabilities if vulnerabilities is not None else [],
            vulnerability_db_freshness=db_freshness,
        )

        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._snapshots_dir / f"{version_id}.json"
        data = self._serialize_snapshot(snapshot)
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        return snapshot

    def get_snapshot(self, version_id: str) -> VersionSnapshot | None:
        """Load a snapshot by version_id. Returns None if not found."""
        file_path = self._snapshots_dir / f"{version_id}.json"
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return self._deserialize_snapshot(data)
        except json.JSONDecodeError:
            logger.warning("Corrupted snapshot file: %s", file_path)
            return None

    def get_latest(self) -> VersionSnapshot | None:
        """Return the most recently created snapshot by timestamp, or None if empty."""
        snapshots = self._load_all_snapshots()
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.timestamp)

    def resolve_baseline(self, reference: str) -> VersionSnapshot:
        """Resolve a baseline reference to a snapshot.

        Resolution priority:
        1. Try ISO 8601 date format (YYYY-MM-DD) → find most recent snapshot on or before that date
        2. Try git tag match or commit SHA match (full or abbreviated ≥7 chars)
        3. Fall back to manual label exact match

        Raises SnapshotNotFoundError with available snapshots if no match.
        """
        snapshots = self._load_all_snapshots()

        # 1. Try ISO 8601 date format
        if re.match(r"^\d{4}-\d{2}-\d{2}$", reference):
            return self._resolve_by_date(reference, snapshots)

        # 2. Try git tag or commit SHA
        result = self._resolve_by_git_ref(reference, snapshots)
        if result is not None:
            return result

        # 3. Fall back to manual label exact match
        result = self._resolve_by_label(reference, snapshots)
        if result is not None:
            return result

        # Nothing matched
        available = self._build_available_list(snapshots)
        raise SnapshotNotFoundError(reference, available)

    def list_snapshots(self) -> list[VersionSnapshot]:
        """Return all snapshots sorted by timestamp descending (most recent first)."""
        snapshots = self._load_all_snapshots()
        return sorted(snapshots, key=lambda s: s.timestamp, reverse=True)

    def delete_snapshot(self, version_id: str) -> None:
        """Delete a snapshot JSON file by version_id.

        Silently ignores if the file does not exist (idempotent operation).
        """
        file_path = self._snapshots_dir / f"{version_id}.json"
        if file_path.exists():
            file_path.unlink()

    def _load_all_snapshots(self) -> list[VersionSnapshot]:
        """Load all snapshot files from disk. Skip corrupted files with warning."""
        if not self._snapshots_dir.exists():
            return []

        snapshots: list[VersionSnapshot] = []
        for file_path in self._snapshots_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                snapshots.append(self._deserialize_snapshot(data))
            except json.JSONDecodeError:
                logger.warning("Skipping corrupted snapshot file: %s", file_path)
        return snapshots

    def _serialize_snapshot(self, snapshot: VersionSnapshot) -> dict:
        """Convert VersionSnapshot to JSON-serializable dict."""
        l1_data = {}
        for fid, fs in snapshot.l1_snapshot.items():
            entry = {
                "label": fs.label,
                "description": fs.description,
                "source_node_count": len(fs.source_nodes),
                "confidence": fs.confidence,
            }
            if fs.trigger_description is not None:
                entry["trigger_description"] = fs.trigger_description
            if fs.source_nodes:
                entry["source_nodes"] = list(fs.source_nodes)
            l1_data[fid] = entry

        l1_5_data = {}
        for bid, bs in snapshot.l1_5_snapshot.items():
            l1_5_data[bid] = {
                "label": bs.label,
                "responsibility": bs.responsibility,
                "confidence": bs.confidence,
            }

        relations_data = [
            {
                "from_feature": r.from_feature,
                "to_feature": r.to_feature,
                "relation": r.relation,
            }
            for r in snapshot.feature_relations_snapshot
        ]

        return {
            "version_id": snapshot.version_id,
            "timestamp": snapshot.timestamp,
            "trigger": snapshot.trigger,
            "commit_hash": snapshot.commit_hash,
            "git_tags": snapshot.git_tags,
            "label": snapshot.label,
            "l1_snapshot": l1_data,
            "analyzed_files": snapshot.analyzed_files,
            "l1_5_snapshot": l1_5_data,
            "feature_relations_snapshot": relations_data,
            "vulnerabilities_snapshot": [
                {
                    "cve_id": v.cve_id,
                    "package": v.package,
                    "version": v.version,
                    "severity": v.severity,
                    "cvss": v.cvss,
                    "source": v.source,
                }
                for v in snapshot.vulnerabilities_snapshot
            ],
            "vulnerability_db_freshness": (
                {
                    "timestamp": snapshot.vulnerability_db_freshness.timestamp,
                    "mode": snapshot.vulnerability_db_freshness.mode,
                    "stale_warning": snapshot.vulnerability_db_freshness.stale_warning,
                }
                if snapshot.vulnerability_db_freshness
                else None
            ),
        }

    def _deserialize_snapshot(self, data: dict) -> VersionSnapshot:
        """Convert JSON dict back to VersionSnapshot."""
        version_id = data.get("version_id", "unknown")
        l1_snapshot = {}
        for fid, fdata in data.get("l1_snapshot", {}).items():
            declared_count = fdata.get("source_node_count", 0)
            source_nodes = tuple(fdata.get("source_nodes", ()) or ())
            if declared_count > 0 and not source_nodes:
                warnings.warn(
                    f"source_nodes_drift in snapshot {version_id} feature {fid}: "
                    f"declared count={declared_count} but source_nodes empty; normalized to 0/()",
                    UserWarning,
                    stacklevel=2,
                )
                declared_count = 0
            l1_snapshot[fid] = FeatureSummary(
                feature_id=fid,
                label=fdata["label"],
                description=fdata["description"],
                source_node_count=declared_count,
                confidence=fdata["confidence"],
                trigger_description=fdata.get("trigger_description"),
                source_nodes=source_nodes,
            )

        l1_5_snapshot = {}
        for bid, bdata in data.get("l1_5_snapshot", {}).items():
            l1_5_snapshot[bid] = BlockSummary(
                block_id=bid,
                label=bdata["label"],
                responsibility=bdata["responsibility"],
                confidence=bdata.get("confidence", "medium"),
            )

        relations = [
            RelationSummary(
                from_feature=r["from_feature"],
                to_feature=r["to_feature"],
                relation=r["relation"],
            )
            for r in data.get("feature_relations_snapshot", [])
        ]

        # Vulnerability data (backward-compatible: defaults to empty for pre-Phase-2.5 snapshots)
        vulnerabilities = [
            VulnerabilityEntry(
                cve_id=v["cve_id"],
                package=v["package"],
                version=v["version"],
                severity=v["severity"],
                cvss=v["cvss"],
                source=v.get("source", "osv-scanner"),
            )
            for v in data.get("vulnerabilities_snapshot", [])
        ]

        db_freshness_data = data.get("vulnerability_db_freshness")
        db_freshness = None
        if db_freshness_data:
            db_freshness = DatabaseFreshness(
                timestamp=db_freshness_data["timestamp"],
                mode=db_freshness_data["mode"],
                stale_warning=db_freshness_data.get("stale_warning"),
            )

        return VersionSnapshot(
            version_id=data["version_id"],
            timestamp=data["timestamp"],
            trigger=data["trigger"],
            l1_snapshot=l1_snapshot,
            analyzed_files=data.get("analyzed_files", []),
            commit_hash=data.get("commit_hash"),
            git_tags=data.get("git_tags", []),
            label=data.get("label"),
            l1_5_snapshot=l1_5_snapshot,
            feature_relations_snapshot=relations,
            vulnerabilities_snapshot=vulnerabilities,
            vulnerability_db_freshness=db_freshness,
        )

    # --- Private resolution helpers ---

    def _resolve_by_date(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot:
        """Find the most recent snapshot on or before the given date."""
        try:
            query_date = datetime.strptime(reference, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError:
            available = self._build_available_list(snapshots)
            raise SnapshotNotFoundError(reference, available)

        candidates = []
        for s in snapshots:
            try:
                ts = datetime.fromisoformat(s.timestamp)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts <= query_date:
                    candidates.append((ts, s))
            except ValueError:
                continue

        if not candidates:
            available = self._build_available_list(snapshots)
            raise SnapshotNotFoundError(reference, available)

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _resolve_by_git_ref(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot | None:
        """Find snapshot by git tag or commit SHA match."""
        candidates: list[VersionSnapshot] = []
        for s in snapshots:
            # Check git tags
            if reference in (s.git_tags or []):
                candidates.append(s)
                continue
            # Check commit SHA (full or abbreviated ≥7 chars)
            if (
                s.commit_hash is not None
                and len(reference) >= 7
                and s.commit_hash.startswith(reference)
            ):
                candidates.append(s)

        if not candidates:
            return None

        return max(candidates, key=lambda s: s.timestamp)

    def _resolve_by_label(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot | None:
        """Find snapshot by exact label match."""
        candidates = [s for s in snapshots if s.label == reference]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.timestamp)

    def _build_available_list(self, snapshots: list[VersionSnapshot]) -> list[dict]:
        """Build a list of available snapshot summaries for error messages."""
        available = []
        for s in sorted(snapshots, key=lambda x: x.timestamp, reverse=True):
            entry: dict = {
                "version_id": s.version_id,
                "timestamp": s.timestamp,
                "trigger": s.trigger,
            }
            if s.commit_hash:
                entry["commit_hash"] = s.commit_hash
            if s.git_tags:
                entry["git_tags"] = s.git_tags
            if s.label:
                entry["label"] = s.label
            available.append(entry)
        return available
