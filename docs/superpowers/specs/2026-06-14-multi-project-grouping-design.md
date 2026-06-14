# Multi-Project Grouping Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 讓 The Door 能夠記錄「哪些專案屬於同一個比較群組」，並在 viewer 頂部提供切換下拉選單；所有改動均為既有工具修改，不引入新的基礎建設。

**Confirmed decisions:**
- 群組機制：手動建立（`the-door group add`）
- 一個專案目前只屬於一個群組（資料模型預留擴充空間）
- Viewer 體驗：切換式（頂部下拉選單）
- Server：不自動管理多 process；每個專案獨立 `the-door ui <path>`

---

## 1. 資料模型

### 1.1 `registry.json` 延伸格式

```json
{
  "001": {
    "name": "ms-ts",
    "path": "C:/test-targets/ms-ts",
    "registered_at": "2026-06-14T10:00:00+00:00",
    "last_opened_at": "2026-06-14T12:00:00+00:00"
  },
  "002": {
    "name": "color-go",
    "path": "C:/test-targets/color-go",
    "registered_at": "2026-06-14T10:01:00+00:00",
    "last_opened_at": null
  },
  "__groups__": {
    "g001": {
      "name": "language-samples",
      "member_ids": ["001", "002"],
      "created_at": "2026-06-14T11:00:00+00:00"
    }
  }
}
```

規則：
- Project id 為零填充三位數字字串（`"001"`, `"002"`…）
- 群組 id 為 `g` + 三位數字（`"g001"`）
- `__groups__` key 以雙底線為前綴，與 project id namespace 不衝突
- `last_opened_at`：`the-door ui <path>` 成功啟動時寫入（ISO 8601 UTC）；初次登記為 `null`
- `member_ids` 是 list（為日後多群組支援預留，目前限制一個專案只能在一個群組）

### 1.2 向後相容性

既有 registry.json 不含 `__groups__`：`_load()` 讀不到 `__groups__` 時視為 `{}`，行為與現在完全相同。

---

## 2. `core/registry.py` 修改

### 2.1 `list_projects()` 修正（防止 `__groups__` 被當成專案）

```python
def list_projects(self) -> list[dict]:
    data = self._load()
    return [
        {"id": pid, **info}
        for pid, info in sorted(data.items())
        if not pid.startswith("__")
    ]
```

### 2.2 新增群組方法

```python
def create_group(self, name: str) -> str:
    """建立群組，回傳 group_id。name 重複則 raise ValueError。"""

def add_to_group(self, group_name_or_id: str, codebase_path: str) -> dict:
    """把路徑加入群組。路徑未登記則先自動登記。
    若該 project 已在另一群組，raise ValueError（附說明訊息）。
    回傳 {"group_id": ..., "project_id": ..., "project_name": ...}。
    """

def remove_from_group(self, group_name_or_id: str, codebase_path: str) -> None:
    """從群組移除。路徑不在群組內時 raise ValueError。"""

def list_groups(self) -> list[dict]:
    """回傳所有群組，每筆含 id, name, created_at, members（含 id/name/path）。"""

def get_group_for_project(self, project_id: str) -> dict | None:
    """回傳此 project 所屬的群組 dict，或 None（未分群）。"""

def update_last_opened(self, codebase_path: str) -> None:
    """寫入 last_opened_at（UTC now）給對應 project entry。找不到 path 則 no-op。"""

def get_most_recently_opened(self) -> dict | None:
    """回傳 last_opened_at 最新的 project entry，或 None（全部為 null）。"""
```

**group_name_or_id 解析**：先以 id（`g001`）查，找不到再以 name 查，找不到則 raise `ValueError("群組不存在：<value>")`。

---

## 3. CLI：`the-door group` 指令群

### 3.1 新檔案：`cli/group_cmd.py`

```python
@click.group("group")
def group_group():
    """管理專案比較群組。"""

@group_group.command("create")
@click.argument("name")
def group_create(name: str):
    """建立比較群組。
    
    範例：the-door group create language-samples
    """

@group_group.command("add")
@click.argument("name")
@click.argument("path", type=click.Path())
def group_add(name: str, path: str):
    """將路徑加入群組（路徑未登記則自動登記）。
    
    範例：the-door group add language-samples ./ms-ts
    """

@group_group.command("remove")
@click.argument("name")
@click.argument("path", type=click.Path())
def group_remove(name: str, path: str):
    """從群組移除路徑。
    
    範例：the-door group remove language-samples ./ms-ts
    """

@group_group.command("list")
def group_list():
    """列出所有群組與成員。"""
```

**group list 輸出格式：**

```
The Door — 群組

  g001  language-samples
        001  ms-ts       C:/test-targets/ms-ts
        002  color-go    C:/test-targets/color-go

  未分群（2 個）：
        003  the-door-v170
        004  pytest-tmp-xxx
```

**錯誤反饋**（所有 group 指令共用）：

```
⛔ 群組 'language-samples' 不存在。
   試試：the-door group create language-samples

⛔ 專案 'ms-ts' 已在群組 'existing-group'（一個專案只能屬於一個群組）。
   如需移動，請先執行：the-door group remove existing-group ./ms-ts
```

### 3.2 `cli/main.py` 掛載

```python
from the_door.cli.group_cmd import group_group
main.add_command(group_group)
```

---

## 4. CLI：`ui_cmd.py` 動態預設改動

### 4.1 `update_last_opened_at` 呼叫時機

`ui_cmd` 成功啟動 server 後（`server.start()` 前）寫入：

```python
ProjectRegistry().update_last_opened(str(root))
```

### 4.2 `_pick_project_interactively()` 優先序

```
1. 正在分析中：掃描所有已登記 project，找 checklist.json mtime 在 30 分鐘內最新的
2. 最近開啟：get_most_recently_opened()
3. 互動 picker：顯示群組結構 + 未分群，使用者輸入序號或路徑
```

**新 picker 輸出：**

```
The Door — 可用專案

  群組: language-samples [g001]
    001  ms-ts        C:/test-targets/ms-ts
    002  color-go     C:/test-targets/color-go

  未分群:
    003  the-door-v170  C:/test-targets/the-door-v170

輸入序號或直接輸入路徑 [003]:
```

（預設值 = 最近開啟或最近分析的專案 id）

---

## 5. MCP 工具修改

### 5.1 `project_list` 工具回傳格式擴充

```json
{
  "projects": [
    {
      "id": "001",
      "name": "ms-ts",
      "path": "C:/test-targets/ms-ts",
      "registered_at": "...",
      "last_opened_at": "...",
      "group_id": "g001",
      "group_name": "language-samples"
    },
    {
      "id": "003",
      "name": "the-door-v170",
      "path": "...",
      "registered_at": "...",
      "last_opened_at": "...",
      "group_id": null,
      "group_name": null
    }
  ],
  "groups": [
    {
      "id": "g001",
      "name": "language-samples",
      "member_ids": ["001", "002"]
    }
  ],
  "count": 3,
  "ungrouped_count": 1,
  "hint": "專案 'the-door-v170' 尚未加入群組。執行 `the-door group add <name> <path>` 建立比較群組。"
}
```

`hint` 只在有未分群專案時出現。

### 5.2 `snapshot_write` 回傳加群組資訊

成功後在回傳 dict 加：

```json
{
  "version_id": "...",
  "label": "v1.0.0",
  "group": {"id": "g001", "name": "language-samples"}
}
```

未分群時：

```json
{
  "version_id": "...",
  "label": "v1.0.0",
  "group": null,
  "hint": "此專案尚未加入群組。執行 `the-door group add <name> <path>` 建立比較群組。"
}
```

### 5.3 跨群組警告的位置

`analyze_changes` 的 `baseline` 參數指向同一個 `codebase_path` 的舊 snapshot（同 path 必然同群組），所以跨群組情況不會在 `analyze_changes` 發生。

跨群組警告的正確位置是 **`project_list` 工具**：回傳的 `projects` 清單附帶每個 project 的 `group_id`，AI 在選擇比較對象前可自行判斷是否跨群組。`project_list` 加一個頂層欄位：

```json
{
  "cross_group_note": "比較不同群組的專案時，diff 結果有效但可能出現大量差異。group_id 不同的專案屬於不同群組。"
}
```

此欄位永遠出現（不只在有跨群組情況時）—— 作為 AI 的操作提示，而非錯誤訊號。

---

## 6. API：`GET /api/group`

### 6.1 新增 handler：`core/ui/api/handlers/group.py`

```python
class GroupHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    def get_group(self, ctx=None, **_) -> tuple[int, dict]:
        """GET /api/group — 回傳當前專案的群組資訊與成員清單。"""
```

**回傳（有群組）：**

```json
{
  "current_project": {
    "id": "001",
    "name": "ms-ts",
    "path": "C:/test-targets/ms-ts"
  },
  "group": {
    "id": "g001",
    "name": "language-samples",
    "members": [
      {"id": "001", "name": "ms-ts",    "path": "C:/test-targets/ms-ts",    "is_current": true},
      {"id": "002", "name": "color-go", "path": "C:/test-targets/color-go", "is_current": false}
    ]
  }
}
```

**回傳（未分群）：**

```json
{
  "current_project": {"id": "003", "name": "the-door-v170", "path": "..."},
  "group": null,
  "hint": "此專案尚未加入群組。執行 `the-door group add <name> <path>` 建立比較群組。"
}
```

### 6.2 `router.py` 加 route

在 `build_routes()` 函式簽名加第六個參數 `gr`（GroupHandlers），新增一條：

```python
Route("GET", "/api/group", gr.get_group, summary="讀取當前專案的群組與成員資訊"),
```

**同步更新兩個呼叫點**（加 `GroupHandlers(ctx)` 參數）：
- `core/ui/server.py:53`：`build_routes(ProjectHandlers(ctx), ..., GroupHandlers(ctx))`
- `core/ui/api/_gen_docs.py:27`：同上

`GroupHandlers` 需要讀取 `project_root`（從 `ctx`），同時也需要讀 `ProjectRegistry`（從 `~/.the-door/registry.json`）來找群組資訊。

---

## 7. 前端：Project Switcher 下拉選單

**檔案**：`docs/frontend-local-version-viewer/viewer/`（唯一正式前端，⛔ 勿動 prototype/）

### 7.1 資料取得

頁面初始化時呼叫 `GET /api/group`：
- `group === null` → 不顯示 switcher（或顯示 greyed-out 佔位）
- `group !== null` → 顯示 switcher，成員 ≥ 2 個

### 7.2 UI 位置與外觀

放在現有 `ui-topbar` 中，與 version picker 同排（左側）：

```
[Project: ms-ts ▼]  [Version: v1.0.0 ▼]   ...其他 topbar 元素
```

下拉展開：

```
✓ ms-ts
  color-go
```

### 7.3 切換行為

點擊其他成員 → `window.location.href = <member.path 對應的 server URL>`

URL 組成：以當前 `window.location.origin` 為基底（因為各專案獨立 server，port 不同），
不由前端自行推算 port；改由 `GET /api/group` 的 `members` 加入 `url` 欄位（server 啟動時
從 `window.location.origin` 讀取自身 URL，由前端在每次 `/api/group` 呼叫時帶入
`X-Server-Origin` header，後端填回）。

> **實作注意**：第一版簡化：`members` 不帶 url，前端點擊後顯示「請確認 {name} 的 server 已啟動：`the-door ui {path}`」提示，而非直接導向。url 自動推算留作後續優化。

### 7.4 未分群時

`group === null`：topbar 不顯示 switcher。不加 hint 文字（避免干擾非群組使用者）。

---

## 8. 不動的部分

- `UIServer` 架構（`UIServer(project_root=root)` 單一路徑）
- MCP 工具介面（只加回傳欄位，不改參數）
- `_signature` / `compute_affected_features` 核心邏輯
- `SNAPSHOT_CONTRACT_VERSION`
- `prototype/` 目錄（廢棄，一律不動）

---

## 9. 測試範圍

| 層 | 測試重點 |
|---|---|
| `test_registry.py` | `list_projects()` 跳過 `__groups__`；create/add/remove/list_groups；一個專案兩個群組 raise；get_most_recently_opened；向後相容（無 `__groups__` key） |
| `test_group_cmd.py` | CLI create/add/remove/list 輸出格式；錯誤訊息 |
| `test_ui_cmd.py` | `_pick_project_interactively` 優先序（mocking checklist mtime / last_opened_at） |
| `test_project_list_tool.py` | group_id/group_name 欄位；groups 清單；hint 出現條件 |
| `test_snapshot_write_tool.py` | group 欄位；未分群 hint |
| `test_project_list_tool.py`（補） | `cross_group_note` 永遠出現 |
| `test_group_handler.py` | `GET /api/group` 有群組 / 無群組回傳格式 |
| `test_router.py` | `/api/group` route 存在 |
| 前端（vitest） | `projectSwitcher` render 有群組 / 無群組；點擊行為 |

---

## 10. 實作順序（建議）

1. `core/registry.py`：`list_projects` 修正 + 群組 CRUD 方法
2. `cli/group_cmd.py`：CLI 指令群
3. `cli/main.py`：掛載 group_cmd
4. `cli/ui_cmd.py`：`update_last_opened` + 動態預設邏輯
5. `mcp/tools/project_list_tool.py`：加 group 欄位
6. `mcp/tools/snapshot_write_tool.py`：加 group hint
7. `core/diff/feature_attribution.py`：`analyze_changes` cross-group warning
8. `core/ui/api/handlers/group.py` + `router.py`：`GET /api/group`
9. 前端：topbar project-switcher
