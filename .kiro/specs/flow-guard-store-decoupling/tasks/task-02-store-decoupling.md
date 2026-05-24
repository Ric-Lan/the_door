# Task 02 — Store Decoupling: SnapshotStore + Snapshot codebase_path

**依賴：** Task 01（ProjectIdentity）  
**測試覆蓋率目標：** 100%（新增路徑）；現有測試不得退步

---

## 產出檔案分類

### 修改
| 檔案 | 修改內容 |
|---|---|
| `the_door/src/the_door/core/diff/snapshot_store.py` | 加 `store_root` 參數；snapshot 加 `codebase_path` 欄位 |

### 新增
| 檔案 | 說明 |
|---|---|
| `the_door/tests/unit/core/test_snapshot_codebase_path.py` | codebase_path 序列化測試 |
| `the_door/tests/unit/core/diff/test_snapshot_store_store_root.py` | store_root 解耦測試 |

### 現有測試（必須繼續通過）
| 檔案 |
|---|
| `the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py` |
| `the_door/tests/unit/core/diff/test_diff_engine.py` |
| `the_door/tests/unit/core/diff/test_feature_attribution.py` |

---

## 2.1 SnapshotStore store_root 參數

### TDD — 先寫測試 `tests/unit/core/diff/test_snapshot_store_store_root.py`

```python
# 測試清單（覆蓋率 100% for 新增路徑）

# store_root=None，project.id 不存在，無舊版 store
#   → 觸發 FlowGuard CHECKPOINT "project-not-initialized"（由呼叫端處理）
#   → SnapshotStore 本身不拋 RuntimeError，回傳 StoreResolutionResult

# store_root=None，project.id 存在，status="ok"
#   → self._snapshots_dir = ~/.the-door/store/<UUID>/snapshots
#   → self._structures_dir = ~/.the-door/store/<UUID>/structures

# store_root=None，status="legacy"（有舊版 .the-door/snapshots/）
#   → self._snapshots_dir = <codebase>/.the-door/snapshots（向下相容）

# store_root=Path("/explicit/path") 傳入
#   → 直接使用，不呼叫 ProjectIdentity
#   → self._snapshots_dir = /explicit/path/snapshots

# 現有呼叫端相容：SnapshotStore(path) 不帶 store_root
#   → 等同 store_root=None，行為由 ProjectIdentity 決定
#   → 測試 legacy 情況下回傳 codebase/.the-door/snapshots（行為不變）
```

### 修改 `core/diff/snapshot_store.py`

**修改點 1：`__init__` 加 `store_root` 參數**

```python
# 在 import 區加入
from the_door.core.project_identity import ProjectIdentity

class SnapshotStore:
    def __init__(self, project_root: Path, store_root: Path | None = None):
        self._project_root = project_root
        if store_root is not None:
            resolved_root = store_root
        else:
            result = ProjectIdentity.resolve_store_root(project_root)
            # status="legacy" 或 "ok" 或 "empty" → 使用 result.store_root
            # status="not_found" → store 尚未初始化，resolved_root 設為預設位置
            #   （呼叫端透過 FlowGuard 處理；SnapshotStore 仍建立，只是 snapshots_dir 空）
            resolved_root = result.store_root or (project_root / ".the-door")
        
        self._store_root = resolved_root
        self._snapshots_dir = resolved_root / "snapshots"   # 原 project_root/.the-door/snapshots
        self._structures_dir = resolved_root / "structures" # 原 project_root/.the-door/structures
```

**注意：** `self._project_path` 舊引用（line 52、160、161、194）需同步更新為新欄位名稱。
- `self._project_path` → 改為 `self._project_root`（或保留 alias 以免影響其他方法）
- `self._snapshots_dir`、`self._structures_dir` 路徑來源從 `project_root` 改為 `self._store_root`

---

## 2.2 Snapshot codebase_path 欄位

### TDD — 先寫測試 `tests/unit/core/test_snapshot_codebase_path.py`

```python
# 測試清單（覆蓋率 100% for 新增路徑）

# 序列化：VersionSnapshot 含 codebase_path="/some/path"
#   → JSON 含 "codebase_path": "/some/path"

# 序列化：VersionSnapshot codebase_path=None
#   → JSON 含 "codebase_path": null（不省略欄位）

# 反序列化：JSON 含 "codebase_path": "/some/path"
#   → snapshot.codebase_path == Path("/some/path")（或字串，視 VersionSnapshot 型別）

# 反序列化：舊格式 JSON（無 codebase_path 欄位）
#   → snapshot.codebase_path is None（向下相容，不拋錯）

# Round-trip：序列化後再反序列化，codebase_path 值不變

# snapshot_store.create_snapshot 呼叫時，自動帶入 codebase_path=project_root
#   → 存入的 snapshot JSON 含正確 codebase_path
```

### 修改 `core/diff/snapshot_store.py`

**修改點 2：`_serialize_snapshot` 加入 codebase_path**

```python
# 在 return dict 加入
"codebase_path": str(snapshot.codebase_path) if snapshot.codebase_path else None,
```

**修改點 3：`_deserialize_snapshot` 讀取 codebase_path**

```python
# 在 return VersionSnapshot(...) 加入
codebase_path=Path(data["codebase_path"]) if data.get("codebase_path") else None,
```

**修改點 4：`VersionSnapshot` dataclass 加欄位**

確認 `VersionSnapshot` 定義位置（`core/diff/snapshot_store.py` 或獨立 dataclass 檔），加入：
```python
codebase_path: Path | None = None
```

**修改點 5：`create_snapshot` 傳入 codebase_path**

```python
# create_snapshot 呼叫 VersionSnapshot 時自動帶入
codebase_path=self._project_root,
```

---

## 完成條件

- [ ] `test_snapshot_store_store_root.py` 全部通過，新增路徑 coverage = 100%
- [ ] `test_snapshot_codebase_path.py` 全部通過，coverage = 100%
- [ ] 現有 `test_snapshot_store_roundtrip.py` 繼續通過（不退步）
- [ ] 現有 23 個 `SnapshotStore(path)` 呼叫端不需修改，行為不變（legacy fallback）
- [ ] `VersionSnapshot.codebase_path=None` 不影響現有 snapshot 讀取
