# Spec：版本敘述（version_narrative）— diff 層白話敘述全鏈

> 日期：2026-06-13
> 狀態：draft
> 需求來源：使用者拍板（[[todo_project_summary_synthesis]] P2）——「版本級更新白話敘述，描述
> transition，欄名擬 version_narrative，與 snapshot 級 project_summary 正交」。

## 0. 目標與兩道閘門自檢

**目標**：讓 agent（執行分析的 LLM）讀兩個 snapshot 的 diff（哪些 feature 增/改/刪），
自己寫一段白話敘述「這個版本相比 baseline 做了什麼更新」，持久化進 current snapshot，
viewer diff 模式顯示。

- **閘門 1（通用型強化 LLM 翻譯證據）**：narrative 的生產者是 agent-as-LLM，消費者是
  人類客群。infra 負責持久化與顯示，不內建任何 LLM provider。✅
- **閘門 2（不引多餘資訊）**：narrative 的資訊上限＝`analyze_changes` /
  `/api/diff` 回傳的 affected/inherited features＋DiffSummary，不引入 snapshot
  以外的資訊。✅

## 1. Spike 已驗事實

| 事實 | 出處 |
|---|---|
| `VersionSnapshot` dataclass（frozen=True）含 `project_summary: str | None = None`，已有 optional 欄先例 | `models/snapshot.py:93` |
| `snapshot_store._serialize_snapshot` 無條件 emit 所有欄位（含 None）；`_deserialize` 用 `.get()` 讀回缺鍵→預設值 | `snapshot_store.py:337-407,409-493` |
| schema strict（root `additionalProperties: false`），加欄必同步改 schema | `schemas/snapshot.schema.json:6` |
| `patch_snapshot()` 目前無 `version_narratives` 參數；接受 keyword-only 擴充 | `snapshot_store.py:201-256` |
| `snapshot_list_tool` 每筆已有 `has_project_summary: bool`，`narrative_summary` 模式可直接比照 | `mcp/tools/snapshot_list_tool.py` |
| `DiffHandlers.versions()` 回傳 body dict，可加頂層 optional 欄不破壞現有消費者 | `handlers/diff.py:91-109` |
| `state.versionDiff` 存放 `/api/diff` 全回應；前端 diff mode summary band 位於 `ui-topbar.js` | `state.js:12`, `ui-topbar.js` |
| 純加法 optional 欄不 bump `SNAPSHOT_CONTRACT_VERSION` | `docs/contract-versioning.md §6` |
| C3/C7 hook 只查 description 指紋＋node coverage＋staleness，新 optional 欄不誤擋 | `c3_gate_snapshot_write.py` |
| Gate 機制：narrative 是 informational 欄位，不影響 diff 結構正確性，不立 checklist gate；靠資訊設計讓 LLM 問人 | 本 session 分析 |

## 2. Gate 機制設計（為何選資訊設計）

### 2.1 問題

The Door 是通用工具，N（snapshot 數）無上限。一個 current snapshot 可和多個 baseline
比較，O(N²) 潛在 pair。未加邊界時，有能力的 LLM 可能善意補完所有缺失 narrative。

### 2.2 決策：資訊設計 + 指引層，不加工具 gate

**理由**：
- narrative scope 是「哪些版本比較有意義」——只有人類使用者知道，LLM 無法自行推斷。
- CHECKPOINT（工具反問）是 LLM 問工具，不是 LLM 問人，解決錯誤的問題層次。
- C3/C7 是結構性 gate（執行序、node coverage、描述指紋）；narrative 是純輸出欄位，
  不適合結構性 gate（能做≠該做，過度設計）。

**機制**：
1. `snapshot_list` 新增頂層 `narrative_summary`，暴露缺口數量與建議。
2. CLAUDE.md 增量鏈明文要求：「寫 narrative 前先 `snapshot_list`，向使用者聲明預計翻譯的
   pair，收到確認後才逐一執行」。
3. 有能力的 LLM 看到缺口統計 + note，自然轉向問人，而非自行全補。

**誠實缺口**：此機制對行為異常的 LLM（Opus 等）無強制力；guide 層限制。
明文記錄在 §7。

## 3. 設計

### 3.1 資料模型（持久層）

**`models/snapshot.py`**

在 `project_summary` 後加：

```python
version_narratives: dict[str, str] = field(default_factory=dict)
# key   = baseline 的 version_id（完整 UUID，不可變身分）
# value = 白話敘述文字（agent 自己寫）
# 空 dict = 尚無 narrative（向下相容；舊 snapshot 缺鍵反序列化得 {}）
```

key 選 `version_id`（UUID）而非 label：label 可被改寫，UUID 是不可變身分。
工具層在存入前統一解析 version_ref → version_id。

**`schemas/snapshot.schema.json`**

在 `"project_summary"` 屬性旁加：

```json
"version_narratives": {
  "type": "object",
  "description": "Map of baseline version_id (UUID) to plain-language narrative describing what changed in this version relative to that baseline. Empty dict = no narratives yet.",
  "additionalProperties": { "type": "string" },
  "default": {}
}
```

**`snapshot_store._serialize_snapshot`**

無條件 emit（同 `commit_hash` 慣例）：

```python
"version_narratives": dict(snapshot.version_narratives),
```

**`snapshot_store._deserialize_snapshot`**

```python
version_narratives=dict(data.get("version_narratives") or {}),
```

（`or {}` 防 null JSON 值；`dict()` 確保可變 copy 不共享）

### 3.2 `snapshot_store.patch_snapshot()`

加 keyword-only 參數：

```python
version_narratives: dict[str, str] | None = None,
```

**語義**：merge 覆寫——傳入的 key 覆蓋舊值，未傳的 key 保留（不清空整個 dict）。

```python
if version_narratives:
    merged = {**existing.version_narratives, **version_narratives}
    snap = dataclasses.replace(snap, version_narratives=merged)
```

### 3.3 MCP 工具

#### `snapshot_patch_tool`

**TOOL_SCHEMA 新增**：

```python
"version_narratives": {
    "type": "object",
    "description": (
        "Optional. Map of baseline_version_id (UUID) → narrative string. "
        "Merge-write: provided keys overwrite existing, absent keys are preserved. "
        "Resolve baseline label/tag to version_id before calling (use snapshot_list to get version_id)."
    ),
    "additionalProperties": {"type": "string"},
},
```

**execute() 新增**：

```python
version_narratives = arguments.get("version_narratives") or {}
# 工具層先解析 version_ref → actual snapshot，確認 version_id 存在
# patch_snapshot 傳入 version_narratives=version_narratives
```

**回傳 payload 新增**：

```python
"version_narratives": dict(snap.version_narratives),
```

#### `snapshot_write_tool`

**TOOL_SCHEMA 新增**：

```python
"version_narratives": {
    "type": "object",
    "description": (
        "Optional. Same schema as snapshot_patch. "
        "In both direct and inherit modes: if omitted, version_narratives defaults to {}. "
        "Baseline narratives are NOT inherited (they describe earlier transitions, not this one). "
        "Provide only the narratives that describe THIS snapshot relative to its baselines."
    ),
    "additionalProperties": {"type": "string"},
},
```

**inherit 模式語義**：
- 未給 `version_narratives` → **空 dict**（不繼承 baseline 的）。
  理由：baseline 的 narratives 描述的是更早的 transition pair，對新版本沒有意義。
- 有給 → 直接用傳入值（不 merge baseline 的）。

**回傳 payload 新增**：

```python
"version_narratives": dict(snap.version_narratives),
```

#### `snapshot_list_tool`

每筆 entry 新增：

```python
"has_version_narrative": bool(s.version_narratives),
"narrative_baselines": list(s.version_narratives.keys()),  # 有 narrative 的 baseline version_id 列表
```

頂層新增：

```python
missing = sum(1 for s in snapshots if not s.version_narratives)
payload["narrative_summary"] = {
    "total": len(snapshots),
    "has_narrative": len(snapshots) - missing,
    "missing_narrative": missing,
    "note": (
        f"{missing} 個 snapshot 缺少 version_narrative。"
        "寫入前請向使用者確認要翻譯的 baseline-current 配對，不得自行決定範圍。"
    ) if missing > 0 else "所有 snapshot 均已有 version_narrative。",
}
```

### 3.4 API — `GET /api/diff`

**`handlers/diff.py` — `DiffHandlers.versions()`**

在 body 組裝完成後，嘗試從 current snapshot 讀出對應 narrative：

```python
baseline_uuid = baseline_snap.version_id
narrative = current_snap.version_narratives.get(baseline_uuid)
body["version_narrative"] = narrative  # str | None
```

理由：diff endpoint 接受 baseline/current ref，已解析兩個 snapshot，零額外查詢。

### 3.5 前端顯示（`docs/frontend-local-version-viewer/viewer/` 唯一正式版）

**`state.js`**

`state.versionDiff` 已存 `/api/diff` 全回應，`version_narrative` 欄自動進來，不需額外 state 欄位。

**`ui-topbar.js`**

在 diff 模式的 summary band（顯示 `added/removed/changed` 數字的區塊）下方加 narrative band：

```javascript
function renderVersionNarrativeBand(diff) {
  const narrative = diff?.version_narrative;
  const el = document.getElementById("version-narrative-band");
  if (!el) return;
  if (narrative) {
    el.textContent = narrative;
    el.hidden = false;
  } else {
    el.hidden = true;
  }
}
```

- 有 narrative → 顯示純文字（agent 產出，不加 HTML 修飾）。
- 無（null / 舊 snapshot / 未指定 baseline）→ 隱藏，不顯示 fallback 文字（缺席誠實）。

**`index.html`**

在 diff summary 數字區塊後加：

```html
<div id="version-narrative-band" hidden class="narrative-band"></div>
```

**`layers.js`**

`loadDiffOverlay()` 拿到 `/api/diff` 回應後，呼叫 `renderVersionNarrativeBand(data)`。

### 3.6 Agent 指引（CLAUDE.md 增量更新）

在「Agent-as-LLM chain (incremental update)」之後新增一節：

```markdown
### Agent-as-LLM chain (version_narrative)

**前置要求**：先 `snapshot_list`，向使用者聲明預計翻譯的 baseline-current 配對，
收到確認後才執行。不得自行決定範圍（`narrative_summary.note` 明示此規則）。

1. `snapshot_list(codebase_path="./my-project")`
   → 讀 `narrative_summary`（缺口數量）＋各筆 `has_version_narrative`
   → **向使用者呈現缺口，詢問「要補哪幾對？」**

2. 對每個確認的 (baseline=vX, current=vY) pair：
   a. `analyze_changes(codebase_path="./my-project", baseline="vX")`
      → 取得 `affected_features`（增/改/刪）＋`inherited_features`（不動）＋`summary`
   b. 你自己讀 diff 資料，寫白話敘述（1-4 句），重點：
      - 說清楚「加了什麼、改了什麼、拿掉了什麼」
      - 面向非技術讀者
      - 不得引入 diff 資料之外的資訊
      - affected set 全空（純繼承版本）→ 可省略 narrative，沿用 baseline 的
   c. `snapshot_patch(codebase_path="./my-project",
                      version_ref="vY",
                      version_narratives={"<baseline-version-id-UUID>": "..."})`
      → key 必須是 baseline 的 `version_id`（UUID），從 `snapshot_list` 或
        `analyze_changes` 回傳的 `baseline_version_id` 取得，不得用 label

3. 驗證：呼叫 `/api/diff?baseline=vX&current=vY`，確認回應含
   `"version_narrative": "<非空字串>"`。
```

## 4. 非目標（明文排除）

- **自動觸發**：snapshot_write / snapshot_patch 不自動生成 narrative（agent-as-LLM 親自寫）。
- **narrative gate**：不立 checklist gate、不加 CHECKPOINT——narrative 是 informational，
  不影響結構正確性（能做≠該做）。
- **多語版本**：只存一個字串，語言由 agent 決定（不立 schema 欄位）。
- **narrative 繼承 immutability**：不立 C7 類指紋 gate——narrative 是聚合產物，
  不是逐 feature 翻譯（類比 project_summary 的處理決策）。

## 5. 改動摘要

| 檔案 | 改動 |
|---|---|
| `models/snapshot.py` | `VersionSnapshot.version_narratives: dict[str, str]` |
| `schemas/snapshot.schema.json` | 加 `version_narratives` property |
| `core/diff/snapshot_store.py` | `_serialize`, `_deserialize`, `patch_snapshot` 簽名＋邏輯 |
| `mcp/tools/snapshot_patch_tool.py` | TOOL_SCHEMA + execute + payload |
| `mcp/tools/snapshot_write_tool.py` | TOOL_SCHEMA + inherit 邏輯 + payload |
| `mcp/tools/snapshot_list_tool.py` | 每筆加 2 欄＋頂層 `narrative_summary` |
| `core/ui/api/handlers/diff.py` | body 加 `version_narrative` |
| `docs/frontend-local-version-viewer/viewer/js/ui-topbar.js` | `renderVersionNarrativeBand()` |
| `docs/frontend-local-version-viewer/viewer/js/layers.js` | `loadDiffOverlay` 後呼叫 render |
| `docs/frontend-local-version-viewer/viewer/index.html` | 加 `#version-narrative-band` element |
| `CLAUDE.md` | 新增 version_narrative agent 鏈指引 |
| tests（4 個檔案）| 見 §6 |

**`SNAPSHOT_CONTRACT_VERSION`**：不 bump（純加法 optional 欄，無 schema 語義變更）。

## 6. 測試邊界

### 6.1 Unit

**`tests/unit/core/diff/test_snapshot_patch.py`** — 新增 `TestPatchSnapshotVersionNarratives`：
- `test_patch_adds_narrative` — patch 空 dict，傳入 `{"uuid-A": "added auth"}` → 落盤正確
- `test_patch_merges_narratives` — 已有 `{"uuid-A": "old"}` → patch `{"uuid-B": "new"}` → 兩個 key 都在
- `test_patch_overwrites_same_key` — patch 同一 key → 新值覆蓋舊值
- `test_patch_without_narratives_untouched` — 不傳 `version_narratives` → 既有 narratives 不動

**`tests/unit/mcp/test_snapshot_patch_tool.py`** — 新增：
- `test_tool_returns_version_narratives_in_payload`
- `test_tool_merges_on_existing_narratives`

**`tests/unit/mcp/tools/test_snapshot_list_tool.py`** — 新增：
- `test_has_version_narrative_false_when_empty`
- `test_has_version_narrative_true_when_nonempty`
- `test_narrative_baselines_list`
- `test_narrative_summary_counts`
- `test_narrative_summary_note_present`

**`tests/unit/mcp/test_snapshot_write_tool.py`** — 新增：
- `test_write_with_version_narratives_persists`
- `test_write_inherit_carries_over_baseline_narratives`
- `test_write_inherit_merges_new_narratives`

**`tests/unit/core/ui/api/handlers/test_diff_handlers.py`**（或現有 diff test 檔）— 新增：
- `test_diff_response_includes_version_narrative_when_present`
- `test_diff_response_narrative_null_when_absent`

### 6.2 Schema round-trip

現有 `test_schema_serialize_field_bijection` 已強制 schema properties ↔ 落盤 keys 雙向相等；
加 `version_narratives` 欄後，`_maximal_snapshot` fixture 需補此欄（非空 dict 值），
`_minimal_snapshot` 不需動（empty dict 是預設值，仍落盤）。

### 6.3 前端

現有 `vitest` 測試套件：
- 加 `renderVersionNarrativeBand` 單元測試（有 narrative → 顯示、無 → 隱藏）。
- 加 `loadDiffOverlay` 整合測試 stub，確認 `version_narrative` 傳遞到 render 函數。

## 7. 誠實缺口

| 缺口 | 說明 | 層級 |
|---|---|---|
| narrative 範圍未強制 | 行為異常的 LLM 可能忽略 `note` 自行補完所有 pair | guide |
| narrative 忠實度無 gate | 工具層不驗「narrative 是否忠實反映 diff」——純文字、semantic | 固有缺口 |
| 多 baseline 的 narrative 一致性 | 同一 snapshot 對不同 baseline 各有一條，無跨 pair 一致性約束 | 接受 |
