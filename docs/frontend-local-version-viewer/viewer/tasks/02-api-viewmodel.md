# 步驟 2 — api.js + viewmodel.js

## 概覽

| 模組 | 來源行號（app.js） | 預估行數 | 依賴 |
|---|---|---|---|
| `js/api.js` | 143–528（分散） | ~235 | 無（`API_BASE` 為私有常數） |
| `js/viewmodel.js` | 339–418, 236–241 | ~100 | 無（純函式） |

---

## js/api.js

### 規則

每個 function **只做 fetch + return data**，不碰 DOM、不改 state。

`API_BASE` 定義於模組頂層（私有，不匯出）：

```js
const API_BASE = "";
```

### 匯出介面

```js
export async function fetchProjectStatus()
export async function fetchLatestReport()
export async function fetchSnapshots()
export async function postUpdate(oldPath, newPath, lang)
export async function fetchJobStatus(jobId)
export async function fetchL1Graph(versionId)          // versionId 可為 null
export async function fetchDiff(baselineId, currentId)
export async function fetchL2Graph(featureId)
export async function fetchStructure()
export async function fetchLayerExplanation(featureId, layer)
export async function postGenerateL2(featureId)
export async function postGenerateLayerExplanation(featureId, layer)
export async function fetchNotes(params)               // params: URLSearchParams 或 object
export async function postNote(payload)
export async function fetchDiffExplanation(featureId, params)
export async function postGenerateDiffExplanation(featureId, payload)
export async function fetchStaticUpdateViewModel()     // GET ./data/update-view-model.json
export async function fetchStaticL1ViewModel()         // GET ./data/l1-view-model.json
```

### URL 對照表

| Function | Method | URL |
|---|---|---|
| fetchProjectStatus | GET | `/api/project` |
| fetchLatestReport | GET | `/api/report/latest` |
| fetchSnapshots | GET | `/api/snapshots` |
| postUpdate | POST | `/api/update` |
| fetchJobStatus | GET | `/api/update/status/:jobId` |
| fetchL1Graph(null) | GET | `/api/l1` |
| fetchL1Graph(id) | GET | `/api/l1?version_id=<encoded>` |
| fetchDiff | GET | `/api/diff?baseline=<encoded>&current=<encoded>` |
| fetchL2Graph | GET | `/api/l2/<encoded>` |
| fetchStructure | GET | `/api/structure` |
| fetchLayerExplanation | GET | `/api/layer-explanation/<featureId>/<layer>` |
| postGenerateL2 | POST | `/api/l2/<encoded>/generate` |
| postGenerateLayerExplanation | POST | `/api/layer-explanation/<featureId>/<layer>/generate` |
| fetchNotes | GET | `/api/notes?<params>` |
| postNote | POST | `/api/notes` |
| fetchDiffExplanation | GET | `/api/diff-explanation/<featureId>?<params>` |
| postGenerateDiffExplanation | POST | `/api/diff-explanation/<featureId>/generate` |
| fetchStaticUpdateViewModel | GET | `./data/update-view-model.json` |
| fetchStaticL1ViewModel | GET | `./data/l1-view-model.json` |

所有 fetch 加 `{ cache: "no-store" }`。POST 加 `Content-Type: application/json`。

---

## js/viewmodel.js

### 匯出介面

```js
export function buildViewModelFromReport(report)
export function buildL1ViewModelFromStatic(graphData)
export function snapshotLabel(snapshot)
```

### buildViewModelFromReport 規格

輸入：raw UpdateReport dict（`/api/report/latest` 回傳）  
輸出：UpdateReport ViewModel

```js
{
  mode: "update-report",
  diff_available: boolean,       // l1_changes.length > 0
  summary: string,               // report.l0_summary || "（無摘要）"
  change_counts: {               // 從 l1_changes 計數
    added, removed, attribute_changed, dependency_changed
  },
  risk_counts: {                 // 從 l1_changes.risk_flags 計數
    out_of_scope, vulnerability, semantic_drift
  },
  changes: Array,                // 每個 l1_changes 項目 mapping
  details: Object,               // keyed by feature_id，優先 l2_details，否則 fallback
  interrupted: boolean,
  source: "UpdateReport",
}
```

### buildL1ViewModelFromStatic 規格

輸入：`./data/l1-view-model.json` 的 graphData  
輸出：`{ features: [...], stats: { feature_count: N } }`  
每個 feature：`{ id, label, confidence, description, trigger_description, source: "L1Output.features" }`

### snapshotLabel 規格

| 輸入 | 輸出 |
|---|---|
| null / undefined | `"（未知）"` |
| `{ git_tags: ["v1.0.0"] }` | `"v1.0.0"` |
| `{ label: "my-label" }` | `"my-label"` |
| `{ timestamp: "2026-05-14T12:34:56" }` | `"2026-05-14 12:34"` |
| `{}` | `"（無時間）"` |

---

## 測試規格

### tests/api.test.js

測試方法：`vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, json: async () => data })`

| 測試案例 | 驗證項目 |
|---|---|
| fetchProjectStatus | fetch 呼叫 `/api/project`，cache: no-store |
| fetchL1Graph(null) | URL 為 `/api/l1`，無 query string |
| fetchL1Graph("abc def") | URL 含 `version_id=abc%20def` |
| fetchDiff("v1","v2") | URL 含 `baseline=v1&current=v2`（均 encoded） |
| fetchL2Graph("feat-x") | URL 為 `/api/l2/feat-x` |
| postUpdate(old, new, lang) | method POST，body JSON 含三個欄位 |
| fetchJobStatus("job-1") | URL 為 `/api/update/status/job-1` |
| 各 fetch 的回傳值 | mock ok → function 回傳 json() 結果 |

### tests/viewmodel.test.js

| 測試案例 | 驗證項目 |
|---|---|
| buildViewModelFromReport({}) | diff_available=false, changes=[], change_counts 全 0 |
| buildViewModelFromReport 含 l1_changes | change_counts 正確計算 |
| buildViewModelFromReport 含 risk_flags | risk_counts 正確計算 |
| buildViewModelFromReport 含 l2_details | details map 含 before/after label |
| l1_changes 無對應 l2_details | fallback detail 自動建立 |
| interrupted: true | ViewModel.interrupted = true |
| buildL1ViewModelFromStatic | features 長度 = nodes 長度，欄位正確 mapping |
| buildL1ViewModelFromStatic(null nodes) | features=[], feature_count=0 |
| snapshotLabel(null) | "（未知）" |
| snapshotLabel(有 git_tags) | 第一個 tag |
| snapshotLabel(無 tag, 有 label) | label |
| snapshotLabel(有 timestamp) | 前 16 碼，T→空格 |
| snapshotLabel({}) | "（無時間）" |

---

## TDD 步驟（每個模組）

1. **RED**：寫測試，確認失敗（模組不存在）
2. **GREEN**：建立模組，最小實作通過測試
3. **REFACTOR**：確認無多餘程式碼

## 驗證檢查清單

- [ ] `npm test tests/api.test.js` — 全部通過
- [ ] `npm test tests/viewmodel.test.js` — 全部通過
- [ ] 兩個模組不依賴 DOM，測試不需要 setup.js fixture
