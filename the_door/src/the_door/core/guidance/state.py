import json
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Literal

from the_door.core.diff.snapshot_store import SnapshotEntry

ApiProvider = Literal["anthropic", "openai", "ollama"]

__all__ = ["SnapshotEntry", "StateWarning", "SystemState", "ApiProvider", "to_json_dict", "StateInspector"]


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


class StateInspector:
    def __init__(self, project_path: Path) -> None:
        self._project_path = Path(project_path)

    def inspect(self) -> SystemState:
        dot = self._project_path / ".the-door"
        if not dot.is_dir():
            provider, has_key = self._detect_api_key()
            return SystemState(
                project_path=self._project_path,
                has_dot_the_door=False,
                has_structure_json=False,
                snapshots=(),
                l2_features_analyzed=frozenset(),
                has_api_key=has_key,
                api_provider=provider,
                warnings=(),
            )
        return self._inspect_full(dot)

    def _detect_api_key(self) -> tuple[ApiProvider | None, bool]:
        import os
        if os.environ.get("ANTHROPIC_API_KEY"):
            return ("anthropic", True)
        if os.environ.get("OPENAI_API_KEY"):
            return ("openai", True)
        config_path = Path.home() / ".the-door" / "config.toml"
        if config_path.is_file():
            try:
                import tomllib  # py311+
            except ImportError:
                import tomli as tomllib
            data = tomllib.loads(config_path.read_text(encoding="utf-8"))
            provider = data.get("default_provider")
            if provider in ("anthropic", "openai", "ollama"):
                key_field = f"{provider}_api_key"
                if data.get(key_field):
                    return (provider, True)
        return (None, False)

    def _inspect_full(self, dot: Path) -> SystemState:
        warnings_acc: list[StateWarning] = []

        has_structure_json = (dot / "structure.json").is_file()

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

        provider, has_key = self._detect_api_key()

        return SystemState(
            project_path=self._project_path,
            has_dot_the_door=True,
            has_structure_json=has_structure_json,
            snapshots=tuple(entries),
            l2_features_analyzed=frozenset(l2_ids),
            has_api_key=has_key,
            api_provider=provider,
            warnings=tuple(warnings_acc),
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
