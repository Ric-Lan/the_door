# Task 01 — Core Infrastructure: FlowGuard + ProjectIdentity

**依賴：** 無（其他所有 task 依賴本 task）  
**測試覆蓋率目標：** 100%

---

## 產出檔案分類

### 新增
| 檔案 | 說明 |
|---|---|
| `the_door/src/the_door/core/flow_guard.py` | FlowGuard + Decision + CheckpointOption |
| `the_door/src/the_door/core/project_identity.py` | ProjectIdentity + StoreResolutionResult |
| `the_door/tests/unit/core/test_flow_guard.py` | FlowGuard 單元測試 |
| `the_door/tests/unit/core/test_project_identity.py` | ProjectIdentity 單元測試 |

### 不修改
無

---

## 1.1 FlowGuard

### TDD — 先寫測試 `tests/unit/core/test_flow_guard.py`

```python
# 測試清單（全部需通過，覆蓋率 100%）

# choice=None → Decision.is_resolved=False, chosen=None
# choice="A" 合法（options 含 key "A"） → Decision.is_resolved=True, chosen="A"
# choice="Z" 非法（options 不含 key "Z"） → Decision.is_resolved=False, chosen=None
# choice 大小寫不敏感："a" 應等同 "A" → Decision.is_resolved=True, chosen="A"
# options 為空 → raise ValueError("options must not be empty")
# options 含重複 key → raise ValueError("duplicate option key: A")
# Decision.is_resolved property：chosen=None → False；chosen="A" → True
# CheckpointOption.next_call 預設值為 ""（不傳時不報錯）
```

### 實作 `core/flow_guard.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class CheckpointOption:
    key: str
    label: str
    next_call: str = ""

@dataclass
class Decision:
    checkpoint_name: str
    status: str
    options: list[CheckpointOption]
    chosen: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.chosen is not None

class FlowGuard:
    def check(
        self,
        name: str,
        status: str,
        options: list[CheckpointOption],
        choice: str | None = None,
    ) -> Decision:
        if not options:
            raise ValueError("options must not be empty")
        keys = [o.key for o in options]
        if len(keys) != len(set(keys)):
            dupes = [k for k in keys if keys.count(k) > 1]
            raise ValueError(f"duplicate option key: {dupes[0]}")
        
        resolved_choice = None
        if choice is not None:
            normalized = choice.upper()
            if normalized in {o.key.upper() for o in options}:
                resolved_choice = next(
                    o.key for o in options if o.key.upper() == normalized
                )
        
        return Decision(
            checkpoint_name=name,
            status=status,
            options=options,
            chosen=resolved_choice,
        )
```

---

## 1.2 ProjectIdentity

### TDD — 先寫測試 `tests/unit/core/test_project_identity.py`

```python
# 測試清單（全部需通過，覆蓋率 100%）
# 使用 tmp_path fixture 建立臨時目錄

# resolve_store_root：
#   project.id 不存在、無 .the-door/snapshots/ → status="not_found", store_root=None
#   project.id 不存在、有 .the-door/snapshots/（舊版 store）→ status="legacy", store_root=codebase/.the-door
#   project.id 存在、store 目錄不存在 → status="path_error", store_root=<UUID path>
#   project.id 存在、store 目錄存在但無 .json 檔案 → status="empty", store_root=<UUID path>
#   project.id 存在、store 目錄有至少一個 .json 檔案 → status="ok", store_root=<UUID path>
#   project.id 內容不是合法 UUID（空白/亂碼）→ status="path_error", detail 說明格式錯誤

# get_or_create：
#   project.id 不存在 → 建立檔案，回傳 UUID 字串
#   project.id 已存在 → 回傳相同 UUID（冪等）
#   連續呼叫兩次 → 兩次回傳值相同
#   建立後 project.id 檔案內容為合法 UUID（符合 uuid4 格式）

# StoreResolutionResult：
#   store_root=None 且 status="not_found" → 合法狀態，不報錯
#   store_root 有值且 status="ok" → 合法狀態
```

### 實作 `core/project_identity.py`

```python
from __future__ import annotations
import uuid
from dataclasses import dataclass
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
                store_root=store_root, status="path_error",
                detail=f"store 目錄不存在：{store_root}",
            )
        if not snapshots_dir.exists() or not any(snapshots_dir.glob("*.json")):
            return StoreResolutionResult(store_root=store_root, status="empty", detail="")
        return StoreResolutionResult(store_root=store_root, status="ok", detail="")
```

---

## 完成條件

- [ ] `test_flow_guard.py` 全部通過，coverage = 100%（`flow_guard.py`）
- [ ] `test_project_identity.py` 全部通過，coverage = 100%（`project_identity.py`）
- [ ] `FlowGuard` 不含任何 IO（無 print / open / sys.stdin）
- [ ] `ProjectIdentity` 不含任何 MCP 或 CLI 引用
