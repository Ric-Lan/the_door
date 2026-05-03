"""Narrative chain — append-only JSONL persistence for cross-session continuity."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from the_door.models import NarrativeRecord, NarrativeNodeRead, StructureJSON

logger = logging.getLogger(__name__)


class NarrativeChain:
    """Append-only JSONL narrative chain with cross-session resume."""

    def __init__(self, chain_path: Path) -> None:
        self._path = chain_path

    def append(self, record: NarrativeRecord) -> None:
        """Append a record to the JSONL file."""
        data = self._record_to_dict(record)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def read_all(self) -> list[NarrativeRecord]:
        """Read all records from the chain. Skips corrupted lines."""
        if not self._path.exists():
            return []

        records: list[NarrativeRecord] = []
        content = self._path.read_text(encoding="utf-8")
        if not content.strip():
            return []

        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                record = self._dict_to_record(data)
                records.append(record)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"Skipping corrupted line {line_num} in narrative chain: {e}")
                continue

        return records

    def get_last_state(self) -> NarrativeRecord | None:
        """Get the last batch record for resume detection."""
        records = self.read_all()
        # Find the last batch record
        for record in reversed(records):
            if record.record_type == "batch":
                return record
        return None

    def detect_structural_change(
        self, before: StructureJSON, after: StructureJSON
    ) -> NarrativeRecord | None:
        """Compare two structures. Returns a structural_change record or None if identical."""
        before_ids = {n.node_id for n in before.nodes}
        after_ids = {n.node_id for n in after.nodes}

        added = after_ids - before_ids
        removed = before_ids - after_ids

        if not added and not removed:
            return None

        from datetime import datetime, timezone

        return NarrativeRecord(
            record_type="structural_change",
            timestamp=datetime.now(timezone.utc).isoformat(),
            added_nodes=sorted(added),
            removed_nodes=sorted(removed),
            modified_nodes=[],  # TODO: detect modifications via hash comparison
        )

    def format_human_readable(self) -> str:
        """Pretty-print the narrative chain for CLI display."""
        records = self.read_all()
        if not records:
            return "No narrative chain records found."

        lines: list[str] = []
        lines.append("=== Narrative Chain ===\n")

        for record in records:
            if record.record_type == "batch":
                lines.append(f"[Batch {record.batch}] {record.timestamp}")
                lines.append(f"  Strategy: {record.strategy}")
                lines.append(f"  Nodes read: {len(record.nodes_read)}")
                lines.append(f"  LLM judgment: {record.llm_judgment}")
                if record.pruned_nodes:
                    lines.append(f"  Pruned: {', '.join(record.pruned_nodes)}")
                if record.pending_low_confidence:
                    lines.append(f"  Pending low confidence: {', '.join(record.pending_low_confidence)}")
                lines.append("")

            elif record.record_type == "regeneration":
                lines.append(f"[Regeneration] {record.timestamp}")
                lines.append(f"  Feature: {record.feature_id}")
                lines.append(f"  Previous: {record.previous_summary}")
                lines.append(f"  New: {record.new_summary}")
                lines.append("")

            elif record.record_type == "structural_change":
                lines.append(f"[Structural Change] {record.timestamp}")
                if record.added_nodes:
                    lines.append(f"  Added: {', '.join(record.added_nodes)}")
                if record.removed_nodes:
                    lines.append(f"  Removed: {', '.join(record.removed_nodes)}")
                if record.modified_nodes:
                    lines.append(f"  Modified: {', '.join(record.modified_nodes)}")
                lines.append("")

        return "\n".join(lines)

    # === Private helpers ===

    def _record_to_dict(self, record: NarrativeRecord) -> dict:
        """Convert NarrativeRecord to a JSON-serializable dict."""
        data: dict = {
            "record_type": record.record_type,
            "timestamp": record.timestamp,
        }

        if record.record_type == "batch":
            data["batch"] = record.batch
            data["strategy"] = record.strategy
            data["nodes_read"] = [
                {
                    "node_id": nr.node_id,
                    "topology_rank": nr.topology_rank,
                    "in_degree": nr.in_degree,
                    "is_entry_point": nr.is_entry_point,
                }
                for nr in record.nodes_read
            ]
            data["llm_judgment"] = record.llm_judgment
            data["pruned_nodes"] = record.pruned_nodes
            data["pending_low_confidence"] = record.pending_low_confidence

        elif record.record_type == "regeneration":
            data["feature_id"] = record.feature_id
            data["previous_summary"] = record.previous_summary
            data["new_summary"] = record.new_summary

        elif record.record_type == "structural_change":
            data["added_nodes"] = record.added_nodes
            data["removed_nodes"] = record.removed_nodes
            data["modified_nodes"] = record.modified_nodes

        return data

    def _dict_to_record(self, data: dict) -> NarrativeRecord:
        """Convert a dict from JSONL back to NarrativeRecord."""
        record = NarrativeRecord(
            record_type=data["record_type"],
            timestamp=data["timestamp"],
        )

        if record.record_type == "batch":
            record.batch = data.get("batch")
            record.strategy = data.get("strategy", "topology_guided")
            record.nodes_read = [
                NarrativeNodeRead(
                    node_id=nr["node_id"],
                    topology_rank=nr["topology_rank"],
                    in_degree=nr["in_degree"],
                    is_entry_point=nr["is_entry_point"],
                )
                for nr in data.get("nodes_read", [])
            ]
            record.llm_judgment = data.get("llm_judgment", "")
            record.pruned_nodes = data.get("pruned_nodes", [])
            record.pending_low_confidence = data.get("pending_low_confidence", [])

        elif record.record_type == "regeneration":
            record.feature_id = data.get("feature_id")
            record.previous_summary = data.get("previous_summary")
            record.new_summary = data.get("new_summary")

        elif record.record_type == "structural_change":
            record.added_nodes = data.get("added_nodes")
            record.removed_nodes = data.get("removed_nodes")
            record.modified_nodes = data.get("modified_nodes")

        return record
