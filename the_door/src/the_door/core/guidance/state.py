import json
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotEntry

__all__ = ["SnapshotEntry", "StateWarning", "SystemState", "to_json_dict", "StateInspector"]


@dataclass(frozen=True)
class StateWarning:
    code: str
    location: str
    message: str
    remediation_code: str | None = None


@dataclass(frozen=True)
class SystemState:
    project_path: Path
    has_dot_the_door: bool
    has_structure_json: bool
    snapshots: tuple[SnapshotEntry, ...]
    l2_features_analyzed: frozenset[str]
    warnings: tuple[StateWarning, ...]
    # C5: has the edge_residue stage been stamped in the execution checklist?
    # Lets the guidance authority surface edge_residue as snapshot_write's
    # prerequisite (matching the C3 gate). Last field + default → existing
    # constructors are unchanged.
    edge_residue_stamped: bool = False

    @property
    def has_snapshots(self) -> bool:
        return bool(self.snapshots)

    @property
    def latest_snapshot(self) -> SnapshotEntry | None:
        return self.snapshots[0] if self.snapshots else None


class StateInspector:
    def __init__(self, project_path: Path) -> None:
        self._project_path = Path(project_path)

    def inspect(self) -> SystemState:
        dot = self._project_path / ".the-door"
        if not dot.is_dir():
            return SystemState(
                project_path=self._project_path,
                has_dot_the_door=False,
                has_structure_json=False,
                snapshots=(),
                l2_features_analyzed=frozenset(),
                warnings=(),
            )
        return self._inspect_full(dot)

    def _inspect_full(self, dot: Path) -> SystemState:
        from the_door.core.checklist import (
            FIELD_STAGES,
            STAGE_EDGE_RESIDUE,
            read_checklist,
        )

        warnings_acc: list[StateWarning] = []

        has_structure_json = (dot / "structure.json").is_file()

        checklist = read_checklist(self._project_path)
        edge_residue_stamped = isinstance(checklist, dict) and isinstance(
            (checklist.get(FIELD_STAGES) or {}).get(STAGE_EDGE_RESIDUE), dict
        )

        snap_dir = dot / "snapshots"
        struct_dir = dot / "structures"
        entries: list[SnapshotEntry] = []
        if snap_dir.is_dir():
            for snap_path in snap_dir.glob("*.json"):
                try:
                    data = json.loads(snap_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
                    warnings_acc.append(StateWarning(
                        code="snapshot_corrupted",
                        location=f"snapshot/{snap_path.stem}",
                        message=f"failed to parse: {e}",
                        remediation_code="snapshot_corrupted",
                    ))
                    continue
                vid = data["version_id"]
                for feat_id, feat in (data.get("l1_snapshot") or {}).items():
                    if feat.get("source_node_count", 0) > 0 and not feat.get("source_nodes"):
                        warnings_acc.append(StateWarning(
                            code="source_nodes_drift",
                            location=f"snapshot/{vid}/{feat_id}",
                            message=f"declared count={feat['source_node_count']} but source_nodes empty",
                            remediation_code="source_nodes_drift",
                        ))
                entries.append(SnapshotEntry(
                    version_id=vid,
                    label=data.get("label"),
                    git_tags=tuple(data.get("git_tags", [])),
                    commit_hash=data.get("commit_hash"),
                    timestamp=data["timestamp"],
                    has_persisted_structure=(struct_dir / f"{vid}.json.gz").is_file(),
                ))
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        l2_dir = dot / "l2-outputs"
        l2_ids: set[str] = set()
        if l2_dir.is_dir():
            for p in l2_dir.iterdir():
                if p.suffix == ".json":
                    l2_ids.add(p.stem)

        return SystemState(
            project_path=self._project_path,
            has_dot_the_door=True,
            has_structure_json=has_structure_json,
            snapshots=tuple(entries),
            l2_features_analyzed=frozenset(l2_ids),
            warnings=tuple(warnings_acc),
            edge_residue_stamped=edge_residue_stamped,
        )


def _value_to_json(value):
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, frozenset):
        return sorted(value)
    if isinstance(value, tuple):
        return [_value_to_json(v) for v in value]
    if is_dataclass(value):
        return {f.name: _value_to_json(getattr(value, f.name)) for f in fields(value)}
    return value


def to_json_dict(state: SystemState) -> dict:
    out = {f.name: _value_to_json(getattr(state, f.name)) for f in fields(state)}
    out["has_snapshots"] = state.has_snapshots
    out["latest_snapshot"] = _value_to_json(state.latest_snapshot)
    return out
