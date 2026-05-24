# Task 03 — MCP Layer: response_envelope + tool schema + CHECKPOINT

**依賴：** Task 01（FlowGuard）  
**測試覆蓋率目標：** 100%（新增路徑）

---

## 產出檔案分類

### 修改
| 檔案 | 修改內容 |
|---|---|
| `the_door/src/the_door/mcp/tools/_response_envelope.py` | 支援 Decision 序列化（result=null） |
| `the_door/src/the_door/mcp/tools/snapshot_write_tool.py` | 加 `choice` schema；觸發 CHECKPOINT |
| `the_door/src/the_door/mcp/tools/analyze_changes_tool.py` | 加 `choice` + `source_path` schema；觸發 CHECKPOINT |
| `the_door/src/the_door/mcp/tools/system_status_tool.py` | 加 `choice` schema；觸發 CHECKPOINT |

### 新增
| 檔案 | 說明 |
|---|---|
| `the_door/tests/unit/mcp/test_snapshot_write_inherit.py` | inherit_from merge 邏輯測試 |
| `the_door/tests/integration/test_mcp_flow_guard.py` | MCP + FlowGuard 整合測試 |

**注意：** `tests/contract/test_flow_guard_contract.py` 由 Task 05 負責建立，本 task 不新增。

---

## 3.1 _response_envelope.py Decision 序列化

### 修改 `mcp/tools/_response_envelope.py`

現有 `wrap(payload, project_path, context)` 只注入 `next_actions`。
加入 Decision 處理路徑：

```python
from the_door.core.flow_guard import Decision

def wrap(payload: dict, project_path, context: str = "mcp") -> dict:
    # 若 payload 含 "_decision" key，代表 FlowGuard 要求暫停
    decision: Decision | None = payload.pop("_decision", None)
    if decision is not None and not decision.is_resolved:
        return {
            "checkpoint": decision.checkpoint_name,
            "status": decision.status,
            "options": [
                {"key": o.key, "label": o.label, "next_call": o.next_call}
                for o in decision.options
            ],
            "result": None,
        }
    # 原有邏輯：注入 next_actions
    ...（保留現有程式碼）
```

---

## 3.2 Contract Tests

### TDD — 先寫 `tests/contract/test_flow_guard_contract.py`

```python
# 測試清單（覆蓋率 100%）

# Decision 未解決（chosen=None）時，wrap() 回傳：
#   - "checkpoint" key 存在
#   - "result" == None
#   - "options" 為 list，每項含 key、label、next_call
#   - 不含 "next_actions" key

# Decision 已解決（chosen="A"）時，wrap() 回傳：
#   - 不含 "checkpoint" key
#   - 含 "result"（payload 原內容）
#   - 含 "next_actions"（原有行為）

# 所有觸發 CHECKPOINT 的工具（snapshot_write、analyze_changes、system_status）
# 在 choice=None 條件下回傳 result=None
#   → 針對每個工具各寫一條 parametrize 測試
```

---

## 3.3 MCP Tool Schema 修改

三個工具的 `TOOL_SCHEMA["properties"]` 各加入：

```python
"choice": {
    "type": "string",
    "description": (
        "CHECKPOINT 選項的 key（'A'、'B'、'C'）。"
        "首次呼叫省略；收到 result=null 後帶入選擇重新呼叫。"
    ),
},
```

`TOOL_SCHEMA["required"]` 不加入 `choice`（保持 optional）。

---

## 3.4 snapshot_write_tool.py — inherit_from Bug Fix (#7) + CHECKPOINT

### TDD — 先寫 `tests/unit/mcp/test_snapshot_write_inherit.py`

```python
# 測試清單（覆蓋率 100% for 新增路徑）

# inherit_from 無新 feature（L1 feature 全部在 baseline 中）
#   → 不觸發 CHECKPOINT，直接寫入，結果 = baseline feature 數量

# inherit_from 有新 feature，choice=None
#   → response["result"] == None
#   → response["checkpoint"] == "new-features-detected"
#   → response["options"] 含 "A"（保留）、"B"（捨棄）、"C"（中止）

# inherit_from 有新 feature，choice="A"（保留新 feature）
#   → 結果 feature 數 = baseline 數 + 新增數
#   → 新增的 feature_id 存在於寫入的 snapshot

# inherit_from 有新 feature，choice="B"（捨棄新 feature）
#   → 結果 feature 數 = baseline 數
#   → 新增的 feature_id 不存在於寫入的 snapshot

# inherit_from 有新 feature，choice="C"（中止）
#   → response["result"] == None，不寫入任何 snapshot

# 非法 choice（choice="Z"）
#   → 重新觸發 CHECKPOINT（result=None）
```

### 修改邏輯（`snapshot_write_tool.py`）

```
現行 merge 邏輯：
    merged = {fid: baseline[fid] for fid in baseline if fid in new_features}
    # 只保留 baseline 已有的 → 新增 feature 被丟棄

修正後：
    baseline_ids = set(baseline.keys())
    new_ids = set(new_features.keys())
    added_ids = new_ids - baseline_ids

    if added_ids and choice is None:
        # 觸發 CHECKPOINT
        payload["_decision"] = flow_guard.check("new-features-detected", ...)
        return wrap(payload, ...)

    if choice == "A":
        # baseline 全部保留 + 新增 feature 加入
        merged = {**baseline, **{fid: new_features[fid] for fid in added_ids}}
    elif choice == "B":
        # 只保留 baseline 已有且本次也提供的 feature
        merged = {fid: baseline[fid] for fid in baseline_ids & new_ids}
    elif choice == "C":
        # 中止：直接回傳 result=null，不經 FlowGuard（已是明確選擇，無需再問）
        return {"result": None, "aborted": True}
```

---

## 3.5 analyze_changes_tool.py — source_path 參數 + CHECKPOINT (#10)

### 修改 TOOL_SCHEMA 加 source_path

```python
"source_path": {
    "type": "string",
    "description": (
        "Source codebase 路徑（當 source 和 store 在不同目錄時使用）。"
        "省略時使用 snapshot.codebase_path。"
    ),
},
```

### CHECKPOINT 邏輯

```python
# 執行前：
#   1. 讀取 baseline snapshot.codebase_path
#   2. source_path 參數有值 → 使用 source_path
#   3. source_path 無值 + codebase_path 有值 + 路徑存在 → 使用 codebase_path
#   4. 以上皆無或路徑不存在 → 觸發 CHECKPOINT "source-path-broken"

if not resolved_source.exists():
    payload["_decision"] = flow_guard.check(
        "source-path-broken",
        f"v{baseline} 的來源路徑 {resolved_source} 不存在",
        options=[
            CheckpointOption("A", "提供新路徑",
                f"analyze_changes(baseline='{baseline}', source_path='<填入>')"),
            CheckpointOption("B", "中止"),
        ],
        choice=choice,
    )
    return wrap(payload, codebase_path)
```

---

## 3.6 system_status_tool.py — unanalyzed-versions CHECKPOINT (#1/#4)

### CHECKPOINT 邏輯

```python
# status 輸出後，若偵測到：
#   - git tags 存在但部分無對應 snapshot → CHECKPOINT "unanalyzed-versions-detected"
#   - store 有 ≥1 snapshot 且可新增更多 → CHECKPOINT "version-expansion-available"

if unanalyzed_tags and choice is None:
    payload["_decision"] = flow_guard.check(
        "unanalyzed-versions-detected",
        f"偵測到 {len(unanalyzed_tags)} 個未分析版本：{', '.join(unanalyzed_tags)}",
        options=[
            CheckpointOption("A", f"為 {unanalyzed_tags[0]} 建立 snapshot",
                f"extract_structure(codebase_path='<path>')"),
            CheckpointOption("B", "略過，繼續"),
        ],
        choice=choice,
    )
```

---

## 完成條件

- [ ] `test_flow_guard_contract.py` 全部通過（三個工具各在 choice=None 時 result=null）
- [ ] `test_snapshot_write_inherit.py` 全部通過，新增路徑 coverage = 100%
- [ ] `test_mcp_flow_guard.py` 整合測試通過
- [ ] `choice` 欄位加入 snapshot_write、analyze_changes、system_status 三個 TOOL_SCHEMA
- [ ] inherit_from 新 feature 在 choice="A" 時確實出現在寫入的 snapshot 中
- [ ] 現有 MCP 工具測試不退步
