from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from the_door.core.diff.snapshot_store import SnapshotEntry

ApiProvider = Literal["anthropic", "openai", "ollama"]

__all__ = ["SnapshotEntry", "StateWarning", "SystemState", "ApiProvider"]


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
