from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class StoreResolutionResult:
    store_root: Path | None
    status: Literal["ok", "not_found", "empty", "path_error", "legacy"]
    detail: str = ""


class ProjectIdentity:
    ID_FILE = ".the-door/project.id"

    @staticmethod
    def _central_store() -> Path:
        return Path.home() / ".the-door" / "store"

    @staticmethod
    def get_or_create(codebase_path: Path) -> str:
        id_file = codebase_path / ProjectIdentity.ID_FILE
        id_file.parent.mkdir(parents=True, exist_ok=True)
        if id_file.exists():
            return id_file.read_text(encoding="utf-8").strip()
        new_id = str(uuid.uuid4())
        id_file.write_text(new_id, encoding="utf-8")
        return new_id

    @staticmethod
    def resolve_store_root(codebase_path: Path) -> StoreResolutionResult:
        id_file = codebase_path / ProjectIdentity.ID_FILE
        legacy_snapshots = codebase_path / ".the-door" / "snapshots"

        if not id_file.exists():
            if legacy_snapshots.exists():
                return StoreResolutionResult(
                    store_root=codebase_path / ".the-door",
                    status="legacy",
                    detail="舊版 store（無 project.id）",
                )
            return StoreResolutionResult(store_root=None, status="not_found", detail="新專案")

        raw = id_file.read_text(encoding="utf-8").strip()
        try:
            uuid.UUID(raw)
        except ValueError:
            return StoreResolutionResult(
                store_root=None,
                status="path_error",
                detail=f"project.id 內容非合法 UUID：{raw!r}",
            )

        store_root = ProjectIdentity._central_store() / raw
        snapshots_dir = store_root / "snapshots"

        if not store_root.exists():
            return StoreResolutionResult(
                store_root=store_root,
                status="path_error",
                detail=f"store 目錄不存在：{store_root}",
            )
        if not snapshots_dir.exists() or not any(snapshots_dir.glob("*.json")):
            return StoreResolutionResult(store_root=store_root, status="empty", detail="")
        return StoreResolutionResult(store_root=store_root, status="ok", detail="")
