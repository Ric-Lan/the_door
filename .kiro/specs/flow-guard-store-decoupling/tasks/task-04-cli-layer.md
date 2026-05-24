# Task 04 — CLI Layer: CheckpointRenderer + CLI CHECKPOINT 整合

**依賴：** Task 01（FlowGuard）  
**測試覆蓋率目標：** 100%（新增路徑）

---

## 產出檔案分類

### 新增
| 檔案 | 說明 |
|---|---|
| `the_door/src/the_door/cli/checkpoint_renderer.py` | CLI CHECKPOINT 互動渲染器 |
| `the_door/tests/unit/cli/test_checkpoint_renderer.py` | CheckpointRenderer 單元測試 |

### 修改
| 檔案 | 修改內容 |
|---|---|
| `the_door/src/the_door/cli/analyze_cmd.py` | 無 API key → CHECKPOINT `no-api-key` |
| `the_door/src/the_door/cli/diff_cmd.py` | snapshot 不存在 → CHECKPOINT `snapshot-missing-for-diff` |
| `the_door/src/the_door/cli/status_cmd.py` | 未初始化 → `project-not-initialized`；未分析版本 → `unanalyzed-versions-detected` |
| `the_door/src/the_door/cli/extract_cmd.py` | 回填後同步 source_nodes + CHECKPOINT `backfill-complete` |

### 現有測試（必須繼續通過）
| 檔案 |
|---|
| `the_door/tests/unit/cli/test_cli_commands.py` |
| `the_door/tests/unit/cli/test_extract_as_version.py` |
| `the_door/tests/unit/cli/test_status_cmd.py` |
| `the_door/tests/unit/cli/test_next_action_renderer.py` |

---

## 4.1 CheckpointRenderer

### TDD — 先寫測試 `tests/unit/cli/test_checkpoint_renderer.py`

```python
# 測試清單（覆蓋率 100%）
# 使用 monkeypatch 替換 sys.stdin，capsys 捕捉 stdout

# Decision 未解決時，prompt() 輸出含：
#   - "[CHECKPOINT: <name>]" 前綴
#   - status 描述
#   - 每個 option 的 key 和 label
#   - next_call 非空時顯示 next_call

# 合法輸入 "A"（大寫）→ 回傳 "A"
# 合法輸入 "a"（小寫）→ 回傳 "A"（FlowGuard 已處理大小寫）
# 非法輸入 "Z" 後輸入 "B" → 第一次印出錯誤提示，第二次回傳 "B"
# options 只有一個選項時正常運作
# Decision is_resolved=True（已選擇）→ prompt() 直接回傳 chosen，不等待輸入

# 非互動環境（stdin 為 pipe/EOF）→ raise EOFError 或回傳 None（不無限等待）
```

### 實作 `cli/checkpoint_renderer.py`

```python
from __future__ import annotations
import sys
from the_door.core.flow_guard import Decision, FlowGuard

class CheckpointRenderer:
    def __init__(self, guard: FlowGuard | None = None):
        self._guard = guard or FlowGuard()

    def prompt(self, decision: Decision) -> str:
        if decision.is_resolved:
            return decision.chosen  # type: ignore[return-value]

        self._print_checkpoint(decision)

        while True:
            try:
                raw = input("請輸入選項：").strip()
            except EOFError:
                raise EOFError("非互動環境，無法等待使用者輸入")
            
            resolved = self._guard.check(
                decision.checkpoint_name,
                decision.status,
                decision.options,
                choice=raw,
            )
            if resolved.is_resolved:
                return resolved.chosen  # type: ignore[return-value]
            print(f"⚠ 無效選項：{raw!r}，請重新輸入")

    def _print_checkpoint(self, decision: Decision) -> None:
        print(f"\n[CHECKPOINT: {decision.checkpoint_name}]")
        print(f"狀態：{decision.status}")
        print("請選擇：")
        for opt in decision.options:
            print(f"  {opt.key}) {opt.label}")
            if opt.next_call:
                print(f"     → {opt.next_call}")
        print()
```

---

## 4.2 analyze_cmd.py — CHECKPOINT no-api-key (#2)

### 修改 `cli/analyze_cmd.py`

觸發位置：provider 初始化前的 API key 檢查。

```python
# 在 provider 建立前加入：
from the_door.core.flow_guard import FlowGuard, CheckpointOption
from the_door.cli.checkpoint_renderer import CheckpointRenderer

guard = FlowGuard()
renderer = CheckpointRenderer(guard)

if not (config.anthropic_api_key or config.openai_api_key):
    decision = guard.check(
        "no-api-key",
        "未偵測到 API key（~/.the-door/config.toml 無設定）",
        options=[
            CheckpointOption(
                "A", "你是 AI agent → 使用 MCP agent-as-LLM 路徑",
                "extract_structure(codebase_path='<path>')",
            ),
            CheckpointOption(
                "B", "你是人類使用者 → 設定 API key 後重試",
                "編輯 ~/.the-door/config.toml：[anthropic] api_key = '...'",
            ),
        ],
    )
    choice = renderer.prompt(decision)
    if choice == "B":
        click.echo("請設定 API key 後重新執行。")
        raise SystemExit(0)
    # choice == "A" → 印出 MCP 指引後結束
    click.echo("請使用 MCP 工具：extract_structure → snapshot_write")
    raise SystemExit(0)
```

**注意：** `config.anthropic_api_key` 和 `config.openai_api_key` 是 `LLMConfig` 的屬性（確認於 `config_manager.py:59,66`）。`has_any_api_key()` 方法不存在，不要使用。

---

## 4.3 diff_cmd.py — CHECKPOINT snapshot-missing-for-diff (#6)

### 修改 `cli/diff_cmd.py`

現有 `diff_cmd.py:34` 有 `SnapshotStore(Path(codebase_path))`。

```python
# 在 resolve_baseline 前加入：
baselines = store.list_snapshots()
baseline_ids = {s.version_id for s in baselines} | {s.label for s in baselines if s.label}

if baseline_ref not in baseline_ids:
    decision = guard.check(
        "snapshot-missing-for-diff",
        f"要比對的版本 {baseline_ref!r} 尚無 snapshot",
        options=[
            CheckpointOption(
                "A", f"先為 {baseline_ref} 建立 snapshot（MCP 流程）",
                f"extract_structure(codebase_path='{codebase_path}')",
            ),
            CheckpointOption("B", "中止"),
        ],
    )
    choice = renderer.prompt(decision)
    raise SystemExit(0)
```

---

## 4.4 status_cmd.py — CHECKPOINT project-not-initialized + unanalyzed-versions (#3/#4)

### 修改 `cli/status_cmd.py`

```python
# 在 status 輸出前加入 ProjectIdentity 檢查：
from the_door.core.project_identity import ProjectIdentity

result = ProjectIdentity.resolve_store_root(Path(path))

if result.status == "not_found":
    decision = guard.check(
        "project-not-initialized",
        "專案尚未初始化（無 project.id，無舊版 store）",
        options=[
            CheckpointOption("A", "初始化並開始分析（MCP）",
                "extract_structure(codebase_path='<path>')"),
            CheckpointOption("B", "僅顯示現有狀態，不初始化"),
        ],
    )
    choice = renderer.prompt(decision)
    if choice == "A":
        raise SystemExit(0)

# 現有 status 邏輯執行完後，加入 git tag 偵測：
unanalyzed = _get_unanalyzed_git_tags(Path(path), store)
if unanalyzed:
    decision = guard.check(
        "unanalyzed-versions-detected",
        f"偵測到 {len(unanalyzed)} 個 git tag 尚無 snapshot：{', '.join(unanalyzed[:3])}",
        options=[
            CheckpointOption("A", f"為 {unanalyzed[0]} 建立 snapshot",
                f"extract_structure(codebase_path='{path}')"),
            CheckpointOption("B", "略過，結束"),
        ],
    )
    choice = renderer.prompt(decision)
```

**新增 helper（`status_cmd.py` 內部函式）：**

```python
def _get_unanalyzed_git_tags(project_path: Path, store: SnapshotStore) -> list[str]:
    """讀取 git tags，回傳尚無對應 snapshot 的 tag 列表。"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "tag", "--list"],
            cwd=project_path, capture_output=True, text=True, timeout=5
        )
        tags = [t.strip() for t in result.stdout.splitlines() if t.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    
    snapshots = store.list_snapshots()  # 只呼叫一次
    existing_labels = {s.label for s in snapshots if s.label}
    existing_tags = {t for s in snapshots for t in s.git_tags}
    analyzed = existing_labels | existing_tags
    return [t for t in tags if t not in analyzed]
```

---

## 4.5 extract_cmd.py — source_nodes 回填同步 (#11)

### 新增測試 `tests/unit/cli/test_extract_backfill.py`

```python
# 測試清單（覆蓋率 100% for 新增路徑）

# extract --as-version 寫入 gz 後：
#   - l1_snapshot 中各 feature 的 source_nodes 非空
#   - source_nodes 內容來自 gz 中的 nodes（node_id 格式正確）

# gz 不含某 feature 的任何 node → 該 feature source_nodes 保持原值（不清空）

# gz 讀取失敗（檔案損毀）→ CHECKPOINT 詢問，不靜默跳過
#   → response 含 CHECKPOINT "backfill-read-error"
```

### 修改 `cli/extract_cmd.py`

在現有 `extract --as-version` 寫完 gz 後（約 `extract_cmd.py:98` 附近）加入：

```python
# 回填後同步 source_nodes
from the_door.core.diff.snapshot_store import SnapshotStore

store = SnapshotStore(project_root)
snapshot = store.get_snapshot(version_id)
structure = store.get_structure(version_id)  # 讀剛寫入的 gz

if structure and snapshot:
    empty_count = _count_empty_source_nodes(snapshot)

    # CHECKPOINT：告知回填完成，source_nodes 需由 agent 補入
    decision = guard.check(
        "backfill-complete",
        f"結構已回填（gz 已寫入）。{empty_count} 個 feature 的 source_nodes 為空，"
        f"需由 agent 執行 agent-as-LLM 流程補入後再呼叫 snapshot_write 更新。",
        options=[
            CheckpointOption("A", "執行 analyze_changes 驗證差異",
                f"analyze_changes(codebase_path='{project_root}', baseline='{version_ref}')"),
            CheckpointOption("B", "直接開啟 viewer",
                f"the-door ui {project_root}"),
        ],
    )
    renderer.prompt(decision)
```

**新增 helper：**

```python
def _count_empty_source_nodes(snapshot) -> int:
    """
    回傳 source_nodes 為空的 feature 數量。
    
    source_nodes 的填入必須由 agent-as-LLM 完成（feature→node 對應是語意判斷，
    無法從 AST structure 自動推導）。此函式只用於 CHECKPOINT 提示中顯示需要補入的數量。
    """
    return sum(
        1 for feature in snapshot.l1_snapshot.values()
        if not feature.source_nodes
    )
```

---

## 完成條件

- [ ] `test_checkpoint_renderer.py` 全部通過，coverage = 100%
- [ ] `test_extract_backfill.py` 全部通過，新增路徑 coverage = 100%
- [ ] 無 API key 時 `analyze_cmd` 印出 CHECKPOINT 格式（非 ConfigError traceback）
- [ ] `diff_cmd` 在 baseline 無 snapshot 時印出 CHECKPOINT（非 KeyError）
- [ ] `status_cmd` 呼叫 `_get_unanalyzed_git_tags`，git 不存在時安全回傳 `[]`
- [ ] `extract --as-version` 後 snapshot source_nodes 非空（regression test）
- [ ] 現有 CLI 測試不退步
