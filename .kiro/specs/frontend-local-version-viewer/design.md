# Design Document

## Overview

Phase UI-1 Local Report Viewer 的設計以 TDD 為核心原則：所有業務邏輯集中在可測試的 Python 函式中，前端 JavaScript 只負責讀取 ViewModel JSON 並更新 DOM，不重新計算任何業務邏輯。

現有模組 `the_door.core.ui.view_model` 已有完整實作，本階段的工作是：
1. 補強現有函式的測試覆蓋（unit tests + PBT）
2. 建立前端 HTML/CSS/JS viewer，接入真實 UpdateReport ViewModel
3. 補強 `diff_available` 邊界情況（`l1_changes` 為空 list 時應為 `false`）

---

## Architecture

### 資料流

```
UpdateReport JSON          L1Output JSON
       │                        │
       ▼                        ▼
build_update_report_view_model()   build_l1_view_model()
       │                        │
       ▼                        ▼
update-view-model.json     l1-view-model.json
       │                        │
       └──────────┬─────────────┘
                  ▼
           LocalViewer (HTML/JS)
           ├── TopBar
           ├── ChangeList (左側)
           ├── GraphCanvas (中央)
           └── DetailPanel (右側)
```

### 職責分離原則

- **Python 層**：所有業務邏輯（排序、計數、MissingValue 填充、資料來源標記）
- **JavaScript 層**：讀取 ViewModel、更新 DOM、處理點擊狀態切換
- **禁止**：JavaScript 重新計算 diff、排序、風險判斷

---

## Module Design

### 1. Python：`the_door.core.ui.view_model`（現有，補強測試）

#### 1.1 `build_update_report_view_model(report: Mapping[str, Any]) -> dict`

**現有邏輯確認**：
- `diff_available` 判斷：`has_l1_changes = "l1_changes" in report`
- **需修正**：當 `l1_changes` 存在但為空 list `[]` 時，`diff_available` 應為 `false`

**修正後邏輯**：
```python
changes_raw = _list(report.get("l1_changes"))   # _list() 對 None 回傳 []
diff_available = len(changes_raw) > 0            # 變數名稱改為 diff_available，語意更精確
```

注意：`_list()` 對 `None`（key 不存在）和 `[]`（key 存在但為空）都回傳 `[]`，因此不需要先判斷 key 是否存在。`diff_available` 直接由 list 長度決定，語意清晰。

**需同步更新的測試**：現有 `test_update_report_requires_l1_changes_for_diff_mode` 只測了「key 不存在」的情況。需補充「key 存在但 list 為空」的測試案例（見 Section 2.2 新增測試清單）。

**輸出 schema**：
```json
{
  "mode": "update-report",
  "diff_available": true,
  "summary": "string",
  "pipeline": {
    "old_path": "string",
    "new_path": "string",
    "total_duration_ms": 0,
    "steps": []
  },
  "change_counts": {
    "added": 0,
    "removed": 0,
    "attribute_changed": 0,
    "dependency_changed": 0
  },
  "risk_counts": {
    "out_of_scope": 0,
    "vulnerability": 0,
    "semantic_drift": 0
  },
  "changes": [
    {
      "id": "feature_id",
      "label": "string",
      "change_type": "added|removed|attribute_changed|dependency_changed",
      "risk_flags": [],
      "current_label": "string",
      "baseline_label": "string",
      "source": "UpdateReport.l1_changes"
    }
  ],
  "details": {
    "feature_id": {
      "id": "feature_id",
      "change_type": "string",
      "before": { "label": "string", "description": "string" },
      "after": { "label": "string", "description": "string" },
      "scope_state": null,
      "related_vulnerabilities": [],
      "affected_relations": [],
      "source": "UpdateReport.l2_details|UpdateReport.l1_changes"
    }
  },
  "interrupted": false,
  "source": "UpdateReport"
}
```

#### 1.2 `build_l1_view_model(data: Mapping[str, Any]) -> dict`

現有邏輯正確，不需修改。輸出 schema：
```json
{
  "mode": "single-version",
  "diff_available": false,
  "summary": "string",
  "stats": {
    "feature_count": 0,
    "unclassified_count": 0,
    "infrastructure_count": 0
  },
  "features": [
    {
      "id": "feature_id",
      "label": "string",
      "description": "string",
      "trigger_description": "string",
      "confidence": "high|medium|low|unknown",
      "confidence_reason": "string",
      "source_nodes": [],
      "needs_source_review": false,
      "source": "L1Output.features"
    }
  ],
  "relations": [
    {
      "from": "feature_id",
      "to": "feature_id",
      "label": "string",
      "relation_type": "static|inferred|unknown",
      "source": "L1Output.feature_relations"
    }
  ],
  "source": "L1Output"
}
```

#### 1.3 `_change_sort_key` — 排序邏輯

現有實作正確，對應 requirements Req 2 AC1 的 5 層 key：
```python
def _change_sort_key(change):
    risk_flags = set(_list(change.get("risk_flags")))
    return (
        0 if "out_of_scope" in risk_flags else 1,   # (a)
        0 if "vulnerability" in risk_flags else 1,   # (b)
        0 if "semantic_drift" in risk_flags else 1,  # (c)
        _CHANGE_PRIORITY.get(str(change.get("change_type")), 9),  # (d)
        str(change.get("id") or ""),                 # (e)
    )
```

#### 1.4 `_value_or_missing(value)` — MissingValue 填充

現有邏輯：`None` 或空字串 → `"未提供"`。不需修改。

---

### 2. 測試設計（TDD 順序）

#### 2.1 測試檔案位置

```
the_door/tests/
├── unit/
│   └── core/
│       └── test_view_model.py          ← 主要 unit tests（已存在，需補強）
└── property/
    └── test_view_model_properties.py   ← PBT（新建）
```

#### 2.2 Unit Tests — `test_view_model.py`

**已存在的測試（不重複實作）**：

| 現有測試名稱 | 覆蓋的 Req |
|---|---|
| `test_update_report_view_model_counts_changes_from_l1_changes` | Req 1 AC3/AC4、Req 2 AC1（排序） |
| `test_update_report_requires_l1_changes_for_diff_mode` | Req 1 AC2（key 不存在） |
| `test_detail_values_do_not_backfill_missing_before_after_fields` | Req 1 AC5-8 |
| `test_export_update_report_view_model_writes_rebuildable_json` | Req 3 AC1 |
| `test_l1_view_model_uses_only_declared_features` | Req 7（L1 ViewModel） |
| `test_self_analysis_fixture_builds_single_version_view_model` | Req 7（真實 fixture） |
| `test_export_l1_view_model_writes_rebuildable_json` | Req 3（L1 round-trip） |

**需新增的測試（對應 Req 1 AC2 邊界、Req 1 AC9、Req 2 AC1 細節）**：

| 測試名稱 | 輸入 | 預期輸出 | 狀態 |
|---|---|---|---|
| `test_diff_available_false_when_l1_changes_empty_list` | `l1_changes=[]` | `diff_available=False`, `changes=[]` | 🆕 新增 |
| `test_diff_available_true_when_l1_changes_nonempty` | `l1_changes` 有 1 筆 | `diff_available=True` | 🆕 新增（明確驗證正向情況） |
| `test_fallback_detail_when_no_l2_entry` | `l2_details=[]`，`l1_changes` 有 1 筆 | `details[id].source="UpdateReport.l1_changes"`, `before.label=MISSING_VALUE` | 🆕 新增 |
| `test_sort_tiebreak_by_feature_id` | 2 筆相同 risk+type，id="b" 和 "a" | "a" 排第一 | 🆕 新增 |
| `test_missing_value_when_current_label_empty_string` | `current_label=""` | `after.label=MISSING_VALUE` | 🆕 新增（空字串邊界） |

#### 2.3 PBT — `test_view_model_properties.py`

**Hypothesis strategy（Windows ASCII-only，對齊現有 PBT 慣例）**：

```python
from hypothesis import given, settings, strategies as st

# Windows cp950 相容：所有 text strategy 限制在 ASCII 範圍
# 對齊現有 test_rendering_properties.py 的慣例
FEATURE_ID_ST = st.from_regex(r"feat-[a-z]{3,10}", fullmatch=True)

CHANGE_TYPE_ST = st.sampled_from(
    ["added", "removed", "attribute_changed", "dependency_changed"]
)

RISK_FLAG_ST = st.lists(
    st.sampled_from(["out_of_scope", "vulnerability", "semantic_drift"]),
    unique=True,
    max_size=3,
)

# ASCII-only label：避免 Unicode 在 Windows cp950 下的編碼問題
ASCII_LABEL_ST = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=1,
        max_size=50,
    ).filter(lambda s: s.strip()),
)

L1_CHANGE_ST = st.fixed_dictionaries({
    "feature_id": FEATURE_ID_ST,
    "change_type": CHANGE_TYPE_ST,
    "risk_flags": RISK_FLAG_ST,
    "current_label": ASCII_LABEL_ST,
    "baseline_label": ASCII_LABEL_ST,
})

UPDATE_REPORT_ST = st.fixed_dictionaries({
    "l0_summary": st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        max_size=100,
    ),
    "l1_changes": st.lists(L1_CHANGE_ST, max_size=20),
    "l2_details": st.lists(L1_CHANGE_ST, max_size=20),
    "interrupted": st.booleans(),
})
```

**7 個 PBT 屬性（對應 Req 10）**：

| 屬性 | 描述 |
|---|---|
| `prop_change_counts_sum` | `sum(change_counts.values()) == len(l1_changes)` |
| `prop_changes_ids_in_l1` | 每個 `changes[i].id` 都在 `l1_changes` 的 `feature_id` 集合中 |
| `prop_details_keys_in_changes` | 每個 `details` key 都在 `changes` 的 `id` 集合中 |
| `prop_diff_available_false_when_empty` | `l1_changes=[]` → `diff_available=False` |
| `prop_missing_value_when_baseline_null` | `baseline_label=null` → `before.label="未提供"` |
| `prop_missing_value_when_current_null` | `current_label=null` → `after.label="未提供"` |
| `prop_changes_length_equals_l1_changes` | `len(changes) == len(l1_changes)` |

---

### 3. 前端設計

#### 3.1 檔案結構

```
docs/frontend-local-version-viewer/
├── prototype/                    ← Phase UI-0（保留，不修改）
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── data/
│       ├── self-analysis-view-model.json
│       ├── mock-update-report.json
│       └── mock-update-view-model.json
└── viewer/                       ← Phase UI-1（新建）
    ├── index.html
    ├── styles.css
    ├── app.js
    └── data/
        ├── update-view-model.json    ← 由 export_update_report_view_model() 產生
        └── l1-view-model.json        ← 由 export_l1_view_model() 產生
```

#### 3.2 HTML 結構（`index.html`）

```html
<div class="app-shell">
  <header class="topbar">
    <!-- 專案摘要、模式切換按鈕、計數狀態列 -->
  </header>
  <main class="workspace">
    <aside class="sidebar">       <!-- ChangeList / FeatureList -->
    <section class="canvas">      <!-- GraphCanvas + RelationsPanel -->
    <aside class="detail-panel">  <!-- DetailPanel -->
  </main>
</div>
```

#### 3.3 JavaScript 模組邊界（`app.js`）

**State（唯一可變狀態）**：
```javascript
const state = {
  updateModel: null,   // UpdateReport ViewModel
  l1Model: null,       // L1 ViewModel（單版本模式用）
  mode: "diff",        // "diff" | "baseline" | "current"
  selectedId: null,
};
```

**函式職責**：

| 函式 | 職責 | 禁止 |
|---|---|---|
| `loadViewModels()` | fetch 兩個 JSON 檔案，設定初始 mode | 不計算業務邏輯 |
| `setMode(mode)` | 切換 mode，guard diff mode 需 diff_available | 不排序 changes |
| `render()` | 根據 state 呼叫各 render 子函式 | 不修改 state |
| `renderTopBar()` | 顯示 summary、mode 按鈕、計數 | 不計算計數 |
| `renderChangeList()` | 渲染 changes 或 features 清單 | 不排序 |
| `renderGraphCanvas()` | 渲染節點 grid | 不計算 diff_state |
| `renderDetailPanel()` | 渲染 Before/After、source attribution | 不補值 |
| `selectItem(id)` | 更新 selectedId，呼叫 render() | 不修改 model |
| `renderError(msg)` | 顯示錯誤訊息，不顯示空白畫面 | 不吞錯誤 |

**模式切換 guard**：
```javascript
function setMode(mode) {
  if (mode === "diff" && !state.updateModel?.diff_available) return;
  state.mode = mode;
  state.selectedId = firstSelectableId();
  render();
}
```

#### 3.4 DetailPanel 防幻覺規則

DetailPanel 的欄位分兩類，處理方式不同：

**A 類：Python 端已填入 `"未提供"`（直接顯示，JS 不補值）**
- `detail.before.label`
- `detail.before.description`
- `detail.after.label`
- `detail.after.description`

**B 類：Python 端保留 `null`（JS 端補顯示文字）**
- `detail.scope_state`：Python 端 `_detail_to_view_model` 回傳 `null`，JS 端用 `?? "未提供"` 補值

這個不對稱性是刻意的：`before`/`after` 欄位由 `_value_or_missing()` 統一處理，`scope_state` 是可選欄位，`null` 代表「無 scope 資料」而非「資料缺失」，兩者語意不同。

```javascript
function renderDetailPanel() {
  const detail = state.updateModel?.details?.[state.selectedId];
  if (!detail) { renderNoSelection(); return; }

  // A 類：直接顯示，Python 端已填入 "未提供"
  showField("變更前名稱", detail.before.label);
  showField("變更前描述", detail.before.description);
  showField("變更後名稱", detail.after.label);
  showField("變更後描述", detail.after.description);

  // B 類：scope_state 為 null 時 JS 補顯示文字
  showField("範圍狀態", detail.scope_state ?? "未提供");

  // 列表欄位：空陣列顯示 "未提供"
  showListOrMissing("相關漏洞", detail.related_vulnerabilities);
  showListOrMissing("受影響關係", detail.affected_relations);

  // 防幻覺：永遠顯示資料來源
  showAttribution(detail.source);
}
```

#### 3.5 空狀態與錯誤處理

| 情境 | 處理方式 |
|---|---|
| fetch 失敗（404/network） | `renderError(path + ": " + status)` |
| JSON parse 失敗 | `renderError(path + ": parse error")` |
| `diff_available=false` | 差異模式按鈕 disabled，ChangeList 顯示空狀態訊息 |
| `changes` 為空 | ChangeList 顯示「無變更項目」 |
| 無選取項目 | DetailPanel 顯示「選取左側項目以查看詳情」 |

---

### 4. Fixture 設計

#### 4.1 現有 fixture（可直接使用）

```
docs/frontend-local-version-viewer/prototype/data/
├── self-analysis-view-model.json    ← 真實 L1 ViewModel fixture
└── mock-update-view-model.json      ← mock UpdateReport ViewModel
```

#### 4.2 新增 fixture（Phase UI-1）

```
docs/frontend-local-version-viewer/viewer/data/
├── update-view-model.json           ← 由 export_update_report_view_model() 產生
└── l1-view-model.json               ← 由 export_l1_view_model() 產生
```

**初始版本使用 mock 資料**（目前專案無真實 UpdateReport JSON）：

```python
from the_door.core.ui.view_model import export_update_report_view_model, export_l1_view_model

# 初始版本：從現有 mock 產生（檔名含 mock 標示，符合 spec 規範）
export_update_report_view_model(
    "docs/frontend-local-version-viewer/prototype/data/mock-update-report.json",
    "docs/frontend-local-version-viewer/viewer/data/update-view-model.json",
)

# L1 ViewModel：從真實自我分析結果產生
export_l1_view_model(
    "docs/self-analysis-l1-output.json",
    "docs/frontend-local-version-viewer/viewer/data/l1-view-model.json",
)
```

待真實 pipeline 執行後（`the-door update old/ new/`），用真實 `UpdateReport` JSON 替換 `update-view-model.json`。替換後需重新驗證 viewer 顯示正確。

---

### 5. 正確性屬性對應

| Req | 屬性 | 驗證方式 |
|---|---|---|
| Req 1 AC1/AC2 | `diff_available` 正確判斷（含空 list 邊界） | unit test（新增 2 個）+ PBT prop 4 |
| Req 1 AC3 | `change_counts` 計數正確 | unit test（已存在）+ PBT prop 1 |
| Req 1 AC5-8 | MissingValue 不互補 | unit test（已存在）+ PBT prop 5/6 |
| Req 1 AC9 | 無 l2 entry 時 fallback detail | unit test（新增 1 個） |
| Req 2 AC1 | 風險優先排序（含 tiebreak） | unit test（已存在 + 新增 1 個） |
| Req 3 AC1-3 | Round-trip 一致性 | unit test（已存在） |
| Req 4 | 三欄佈局、模式切換 | 程式碼審查 + 手動瀏覽器測試 |
| Req 5 | 差異模式 ChangeList/GraphCanvas | 程式碼審查 + 手動瀏覽器測試 |
| Req 6 | Before/After 詳情面板 | 程式碼審查 + 手動瀏覽器測試 |
| Req 7 | 單版本模式 | unit test（已存在）+ 手動瀏覽器測試 |
| Req 8 | 空狀態與錯誤處理 | 程式碼審查 + 手動瀏覽器測試 |
| Req 9 AC2-3 | 無外部請求 | 程式碼審查（無 CDN 引用） |
| Req 10 | PBT 7 個屬性 | `test_view_model_properties.py` |
| Req 11 | 防幻覺 source 顯示 | DetailPanel 永遠顯示 `detail.source` |

---

### 6. 不做的事（MVP 邊界）

- 不引入 Mermaid 渲染（prototype 已有，Phase UI-1 保持 node grid 形式）
- 不新增 Python HTTP server（用 `python -m http.server` 啟動）
- 不新增前端 build pipeline（直接 Vanilla JS）
- 不實作 snapshot 選擇器（Phase UI-2 的工作）
- 不實作 pipeline progress（Phase UI-2 的工作）
- 不修改現有 prototype（保留在 `prototype/` 目錄）
