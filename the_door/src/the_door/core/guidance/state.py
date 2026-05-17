from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Literal

from the_door.core.diff.snapshot_store import SnapshotEntry

ApiProvider = Literal["anthropic", "openai", "ollama"]

__all__ = ["SnapshotEntry", "StateWarning", "SystemState", "ApiProvider", "to_json_dict"]


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
    has_api_key: bool
    api_provider: ApiProvider | None
    warnings: tuple[StateWarning, ...]

    @property
    def has_snapshots(self) -> bool:
        return bool(self.snapshots)

    @property
    def latest_snapshot(self) -> SnapshotEntry | None:
        return self.snapshots[0] if self.snapshots else None


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
