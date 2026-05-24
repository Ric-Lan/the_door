# Spec: FlowGuard + Store Decoupling + Flow Enforcement
**Date:** 2026-05-24  
**Status:** Draft  
**Addresses:** Problems #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11 (handoff 2026-05-23-C)

---

## 1. Problem Statement

The Door 目前依賴文件（CLAUDE.md）引導 AI agent 執行正確流程。文件無法強制執行，agent 可以跳過任何步驟。根本問題有三：

1. **沒有程式層斷點** — agent 在錯誤時機仍可繼續執行
2. **store 綁定 source 路徑** — store 和 source 必須同目錄，多版本操作時無法解耦
3. **snapshot 不記錄來源路徑** — 無法驗證各版本的 source 真實存在

---

## 2. Design Principles

- **最小架構異動** — 每層只動自己的邊界，不跨層重寫
- **單一判斷來源** — 同一邏輯不在 CLI 和 MCP 各寫一份
- **result: null 是強制機制** — agent 拿不到 result 就無法繼續，不依賴自然語言引導
- **TDD** — 每個新模組先寫合約測試，再寫實作
- **不引入新外部依賴**

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  CLI Layer                                              │
│  cli/checkpoint_renderer.py                            │
│  — 讀取 Decision，stdin 等待輸入，回傳 choice           │
├─────────────────────────────────────────────────────────┤
│  MCP Layer                                              │
│  mcp/_response_envelope.py（修改）                      │
│  — 讀取 Decision，序列化為 JSON，result=null 強制選擇   │
├─────────────────────────────────────────────────────────┤
│  Core: FlowGuard                                        │
│  core/flow_guard.py（新增）                             │
│  — 判斷邏輯唯一來源，不碰 IO，CLI/MCP 各自渲染          │
├─────────────────────────────────────────────────────────┤
│  Core: ProjectIdentity + Store Decoupling               │
│  core/project_identity.py（新增）                       │
│  core/diff/snapshot_store.py（修改）                    │
│  — UUID-based 中央 store，解耦 source 和 store 路徑     │
└─────────────────────────────────────────────────────────┘
```

---

## 4. FlowGuard

### 4.1 資料結構

```python
# core/flow_guard.py

@dataclass(frozen=True)
class CheckpointOption:
    key: str                 # "A", "B", "C"
    label: str               # 顯示給使用者的說明
    next_call: str = ""      # 帶實際參數的下一步指令字串；中止類選項可為空

@dataclass
class Decision:
    checkpoint_name: str
    status: str                    # 目前偵測到的狀態描述
    options: list[CheckpointOption]
    chosen: str | None = None      # None = 尚未選擇
    
    @property
    def is_resolved(self) -> bool:
        return self.chosen is not None
```

### 4.2 FlowGuard 行為

```python
class FlowGuard:
    def check(
        self,
        name: str,
        status: str,
        options: list[CheckpointOption],
        choice: str | None = None,
    ) -> Decision:
        """
        choice=None        → 回傳 Decision(chosen=None)，未解決
        choice 合法 key    → 回傳 Decision(chosen=key)，已解決
        choice 非法 key    → 回傳 Decision(chosen=None)，重新選擇
        """
```

**FlowGuard 不做 IO，不知道自己在 CLI 或 MCP。**

### 4.3 MCP 回應格式

Decision 未解決時，MCP 工具回傳：

```json
{
  "checkpoint": "source-path-broken",
  "status": "v1.0.5 的來源路徑 /old/path 不存在",
  "options": [
    {
      "key": "A",
      "label": "提供新來源路徑",
      "next_call": "analyze_changes(baseline='v1.0.5', source_path='<填入>')"
    },
    {
      "key": "B",
      "label": "中止操作"
    }
  ],
  "result": null
}
```

`result: null` 是強制機制核心。Agent 無法從 null 取得資料，必須帶 `choice` 重新呼叫。

### 4.4 CLI 渲染

```python
# cli/checkpoint_renderer.py

class CheckpointRenderer:
    def prompt(self, decision: Decision) -> str:
        """
        印出格式化的 CHECKPOINT 區塊，
        從 stdin 讀取 choice，回傳合法的 key。
        """
```

---

## 5. Store Decoupling

### 5.1 ProjectIdentity

```python
# core/project_identity.py

@dataclass
class StoreResolutionResult:
    store_root: Path | None
    status: Literal["ok", "not_found", "empty", "path_error", "legacy"]
    detail: str

class ProjectIdentity:
    ID_FILE = ".the-door/project.id"
    CENTRAL_STORE = Path.home() / ".the-door" / "store"

    @staticmethod
    def get_or_create(codebase_path: Path) -> str:
        """
        讀取現有 UUID，或首次建立並寫入 project.id。
        """

    @staticmethod
    def resolve_store_root(codebase_path: Path) -> StoreResolutionResult:
        """
        解析流程（每步明確，不靜默失敗）：
        
        1. project.id 不存在
           → 檢查 .the-door/snapshots/ 是否存在（舊版 store）
             → 存在：status="legacy"，store_root=codebase_path/.the-door
             → 不存在：status="not_found"（新專案）
        
        2. project.id 存在，讀取 UUID
           → store 目錄不存在：status="path_error"
           → store 目錄存在但無 snapshot：status="empty"
           → store 目錄存在且有 snapshot：status="ok"
        """
```

### 5.2 SnapshotStore 修改

```python
# core/diff/snapshot_store.py

class SnapshotStore:
    def __init__(self, project_root: Path, store_root: Path | None = None):
        self._project_root = project_root
        # store_root=None → 由 ProjectIdentity 自動解析
        # store_root 傳值 → 使用指定路徑（測試用 / 向下相容）
        self._store_root = store_root or self._resolve_store_root()
        self._snapshots_dir = self._store_root / "snapshots"
        self._structures_dir = self._store_root / "structures"
```

### 5.3 向下相容 CHECKPOINT

遇到舊版 store（status="legacy"）：

```
[CHECKPOINT: legacy-store-detected]
狀態：偵測到舊版 store（.the-door/snapshots/ 存在，無 project.id）
請選擇：
  A) 遷移到中央 store（~/.the-door/store/<UUID>/）
     next_call: the-door migrate-store <codebase_path>
  B) 繼續使用原地 store（保持現有行為）
```

### 5.4 路徑破損 CHECKPOINT

遇到 status="path_error"：

```
[CHECKPOINT: store-path-broken]
狀態：project.id 指向 ~/.the-door/store/<UUID>/，但該目錄不存在
請選擇：
  A) 重新初始化 store（建立新空目錄，保留 project.id）
  B) 指定新的 store 位置
  C) 重設 project.id（視為新專案，舊 snapshot 無法存取）
```

---

## 6. Snapshot codebase_path 欄位

每個 snapshot 新增 `codebase_path` 欄位：

```json
{
  "version_id": "...",
  "timestamp": "...",
  "codebase_path": "/absolute/path/to/source",
  "label": "v1.0.5",
  ...
}
```

**用途：**
1. `analyze_changes` 執行前驗證 source 真實存在
2. `status` 顯示各版本 source 狀態
3. 多版本比較時確認每個版本來源

**向下相容：** 舊 snapshot `codebase_path=None`，第一次使用時 CHECKPOINT 補確認。

---

## 7. Bug 修正

### 7.1 問題 #7 — inherit_from 過濾掉新增 feature

**位置：** `mcp/tools/snapshot_write_tool.py`

**現行行為：** `inherit_from` 只保留 baseline 已有的 feature_id，新增 feature 被丟棄。

**修正：** merge 邏輯改為：
- baseline feature + 新增 feature → 全部保留
- 明確標記為 removed 的 feature → 才丟棄

**CHECKPOINT（新 feature 出現時）：**
```
[CHECKPOINT: new-features-detected]
狀態：baseline v1.0.5 有 N 個 feature，本次新增 M 個
請選擇：
  A) 保留新增 feature，合併進 snapshot（推薦）
  B) 僅繼承 baseline，捨棄新增 feature
  C) 中止，重新產 L1
```

### 7.2 問題 #11 — extract --as-version 不同步 source_nodes

**位置：** `cli/extract_cmd.py`

**修正：** `extract --as-version` 寫入 gz 後，讀取 gz 中的 nodes，反查每個 L1 feature 的 source_nodes 並更新 l1_snapshot。

**CHECKPOINT（回填完成後）：**
```
[CHECKPOINT: backfill-complete]
狀態：v1.0.5 結構已回填，source_nodes 已同步（N 個 feature 更新）
下一步必須選擇：
  A) 執行 analyze_changes 驗證差異
     next_call: analyze_changes(baseline="v1.0.5", source_path="<path>")
  B) 直接開啟 viewer
     next_call: the-door ui <path>
```

### 7.3 問題 #10 — analyze_changes source_path

**Store 解耦後**（Section 5）大部分已解決：store 由 UUID 決定，與 source 路徑無關。

**額外加入 source_path 參數（明確覆蓋）：**

```python
analyze_changes(
    codebase_path: str,          # store 所在目錄（含 project.id）
    baseline: str,
    source_path: str | None = None,  # 可選，覆蓋 snapshot.codebase_path
)
```

若 `snapshot.codebase_path` 不存在且 `source_path` 未提供 → CHECKPOINT。

---

## 8. Flow Enforcement CHECKPOINT 對照表

| 問題 | 觸發位置 | CHECKPOINT 名稱 |
|---|---|---|
| #2 API key 不存在 | `provider.py` | `no-api-key` |
| #3 未跑 status | CLI 入口 pre-flight | `status-not-run` |
| #4 store 有 N 版但未提示加新版 | `status_cmd.py` | `version-expansion-available` |
| #5 未先 diff 就寫 snapshot | `snapshot_write_tool.py` | `pre-snapshot-diff-required` |
| #6 diff 目標無 snapshot | `diff_cmd.py` | `snapshot-missing-for-diff` |
| #7 inherit_from 新 feature | `snapshot_write_tool.py` | `new-features-detected` |
| #8/#9 post-snapshot 未呼叫 analyze_changes | `snapshot_write_tool.py` | `post-snapshot-required-action` |
| #10 source_path 不存在 | `analyze_changes_tool.py` | `source-path-broken` |
| #11 回填後 source_nodes 同步 | `extract_cmd.py` | `backfill-complete` |
| #1 git tags 未分析版本 | `status_cmd.py` | `unanalyzed-versions-detected` |
| Store 舊版格式 | `project_identity.py` | `legacy-store-detected` |
| Store 路徑破損 | `project_identity.py` | `store-path-broken` |

---

## 9. Testing Strategy

### 9.1 Unit Tests

**FlowGuard（`tests/core/test_flow_guard.py`）：**
- `choice=None` → Decision.is_resolved=False
- `choice="A"` 合法 → Decision.is_resolved=True, chosen="A"
- `choice="Z"` 非法 → Decision.is_resolved=False
- options 為空時 raise ValueError

**ProjectIdentity（`tests/core/test_project_identity.py`）：**
- project.id 不存在、無舊 store → status="not_found"
- project.id 不存在、有舊 store → status="legacy"
- project.id 存在、store 目錄不存在 → status="path_error"
- project.id 存在、store 空 → status="empty"
- project.id 存在、store 有 snapshot → status="ok"
- get_or_create：連續呼叫回傳同一 UUID

**snapshot_write inherit_from（`tests/mcp/test_snapshot_write_inherit.py`）：**
- baseline 3 feature + 新增 1 feature，choice="A" → 結果 4 feature
- baseline 3 feature + 新增 1 feature，choice="B" → 結果 3 feature
- inherit_from 無新 feature → 不觸發 CHECKPOINT

### 9.2 Contract Tests

**MCP 工具回應格式（`tests/mcp/test_flow_guard_contract.py`）：**
- Decision 未解決時，response 含 `checkpoint` 欄位且 `result=null`
- Decision 已解決時，response 含 `result`，不含 `checkpoint`
- 所有觸發 CHECKPOINT 的工具都必須通過此 contract

### 9.3 Integration Tests（Architectural TDD）

**CLI + FlowGuard 銜接（`tests/integration/test_cli_checkpoint.py`）：**
- 無 API key 情況下呼叫 `analyze_cmd` → stdout 含 CHECKPOINT 格式
- 輸入合法 choice → 程式繼續（不拋錯）
- 輸入非法 choice → 重新列出選項

**MCP + FlowGuard 銜接（`tests/integration/test_mcp_flow_guard.py`）：**
- `snapshot_write(inherit_from=..., l1_features=[新feature])` 且 `choice=None` → result=null
- 同上但 `choice="A"` → result 含 version_id
- `analyze_changes` + source 不存在 + `choice=None` → result=null

**Store 解耦端對端（`tests/integration/test_store_decoupling.py`）：**
- 新專案初始化 → project.id 建立 → store 在中央位置
- source 目錄搬移後，重新呼叫 → store 仍可找到（UUID 不變）
- 舊版 store 偵測 → CHECKPOINT legacy-store-detected 觸發

---

## 10. File Change Summary

| 動作 | 檔案 |
|---|---|
| 新增 | `core/flow_guard.py` |
| 新增 | `core/project_identity.py` |
| 新增 | `cli/checkpoint_renderer.py` |
| 修改 | `core/diff/snapshot_store.py` — 加 `store_root` 參數 |
| 修改 | `mcp/_response_envelope.py` — Decision 序列化 |
| 修改 | `mcp/tools/snapshot_write_tool.py` — inherit_from merge + CHECKPOINT |
| 修改 | `mcp/tools/analyze_changes_tool.py` — `source_path` 參數 + CHECKPOINT |
| 修改 | `cli/extract_cmd.py` — 回填後同步 source_nodes + CHECKPOINT |
| 修改 | `cli/analyze_cmd.py` — no-api-key CHECKPOINT |
| 修改 | `cli/diff_cmd.py` — snapshot-missing CHECKPOINT |
| 修改 | `cli/status_cmd.py` — unanalyzed-versions + version-expansion CHECKPOINT |
| 修改 | `core/diff/snapshot_store.py` — snapshot 加 `codebase_path` 欄位 |

---

## 11. Out of Scope

- 前端 viewer 改動
- LLM provider 新增
- CLAUDE.md 以外的文件更新
- 問題 #1 的「從 GitHub 拉遠端版本」功能（本 spec 只處理 git tags 本地偵測）
