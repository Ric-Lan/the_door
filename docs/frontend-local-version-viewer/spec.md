# The Door — 本地版本驗核前端規格

## 1. 目的

本文件定義 The Door 未來前端 UI/UX 的開發依據。前端的核心目標不是取代既有 CLI/MCP 能力，而是把既有本地分析結果呈現成可讀、可點、可驗核的版本差異工作台。

本前端應回答四個問題：

1. 目前這個系統能做什麼？
2. 這一版相對上一版改了什麼？
3. 哪些改動超出範圍、有漏洞、低信心或語意漂移？
4. 點到一個變更時，能否看到它來自哪些現有分析資料，而不是憑空推測？

本文件的約束原則：

- Clean Code：前端、API、資料轉換層職責清楚，避免重複邏輯。
- Local-first：除 LLM 呼叫外，分析結果儲存、讀取、比對、渲染、UI 呈現都應優先在本地完成。
- No hallucination：UI 不得展示資料來源不存在的功能、關係、風險、檔案或推論。
- No over-engineering：MVP 不建大型狀態平台、多人協作、雲端帳號、遠端同步或自訂圖形引擎。
- No resource waste：預設讀取已產出的 JSON/Mermaid/Markdown；只有使用者明確要求重新分析時才可能觸發 LLM。
- Program alignment：所有畫面必須對齊現有程式輸出與模型，不得為了 UI 效果編造欄位。
- TDD first：任何資料轉換、差異計數、缺欄位處理、錯誤狀態，在實作前必須先有失敗測試描述預期行為。

## 2. 現有能力對齊

以下能力已存在於目前專案，可作為前端資料來源或後端 API 包裝對象。

| 能力 | 現有位置 | 前端用途 |
|---|---|---|
| L1 功能輸出 | `docs/self-analysis-l1-output.json`、`models.py::L1Output` | 單版本功能總覽、功能詳情 |
| Mermaid 圖形輸出 | `docs/self-analysis-l1-diagram.md`、`core/rendering/mermaid_renderer.py` | MVP 圖形顯示 |
| AST 結構原料 | `docs/self-analysis-structure.json`、`models.py::StructureJSON` | 結構統計、來源證據，不預設完整展示 |
| 版本快照 | `core/diff/snapshot_store.py`、`models.py::VersionSnapshot` | 版本選擇、舊版/新版來源 |
| Diff 計算 | `core/diff/diff_engine.py`、`models.py::DiffResult` | 差異模式 |
| Diff 渲染 | `core/diff/diff_renderer.py` | 差異 Mermaid fallback |
| Scope 驗核 | `core/scope/scope_verifier.py`、`models.py::ScopeResult` | 範圍徽章、超出範圍清單 |
| 疑義追蹤 | `core/scope/doubt_store.py`、`models.py::DoubtRecord` | 疑義列表與詳情 |
| 時間軸 | `core/timeline/timeline_engine.py`、`models.py::TimelineResult` | 功能演進 tab |
| 更新報告 | `core/pipeline/report_renderer.py`、`models.py::UpdateReport` | 版本差異主資料來源 |
| 更新管線 | `core/pipeline/pipeline_orchestrator.py` | 重新分析與進度顯示 |

若前端需要顯示的欄位不在上述資料中，應先擴充後端資料契約與測試，再進入 UI。不得在前端以字串規則自行猜測。

## 3. 產品形態

### 3.1 推薦形態

新增一個本地 UI 入口：

```bash
the-door ui <project-path>
```

行為：

1. 啟動本地 HTTP server，例如 `http://127.0.0.1:<port>`。
2. 讀取指定專案的 `.the-door/` 與既有輸出資料。
3. 顯示最近一次分析與可用快照。
4. 若沒有可用資料，顯示明確空狀態，引導使用者執行 `the-door analyze` 或 `the-door update`。
5. 不自動呼叫 LLM。

實作限制：

- MVP server 優先使用 Python 標準函式庫或既有依賴實作，不新增 FastAPI、Flask、資料庫或背景工作框架。
- 若僅提供靜態檔案，可使用 Python 標準函式庫的本地 HTTP server 包裝 build output。
- 新增第三方套件前必須先證明標準函式庫與現有依賴無法合理完成需求，並另行更新 spec。

### 3.2 MVP 可接受替代形態

先做純本地靜態 Viewer，讀取 `docs/` 下的固定輸出：

```text
docs/
  self-analysis-l1-output.json
  self-analysis-l1-diagram.md
  self-analysis-structure.json
```

此模式只驗證 UI/UX，不提供重新分析、不提供快照選擇、不提供即時後端呼叫。這是 prototype，不應被標記為完整前端。

## 4. 核心 UX 模型

前端主畫面是一個「本地版本驗核工作台」，不是文件瀏覽器，也不是一般 dashboard。

畫面分為三欄：

```text
左側：版本與變更清單
中央：功能圖 / 差異圖 / 結構概覽
右側：詳情、證據、Before/After 對照
```

### 4.1 頂部狀態列

必須顯示：

- 專案名稱或路徑。
- Baseline 版本。
- Current 版本。
- 目前模式：舊版、新版、差異。
- Scope 名稱，若未指定則顯示未套用。
- 最後分析時間，若資料中不存在則顯示未知，不得編造。
- LLM provider，若資料中不存在則顯示未記錄。

### 4.2 模式切換

提供三個主要模式：

| 模式 | 用途 | 資料來源 |
|---|---|---|
| 舊版 | 顯示 baseline 的功能狀態 | `VersionSnapshot` 或舊版 `L1Output` |
| 新版 | 顯示 current 的功能狀態 | `VersionSnapshot` 或新版 `L1Output` |
| 差異 | 顯示新增、移除、修改、依賴變更 | `DiffResult` / `UpdateReport` |

差異模式是預設主模式。若沒有 DiffResult，UI 必須顯示缺資料狀態，而不是用單版本資料假裝有差異。

### 4.3 視角切換

在每個版本模式內提供：

- L1 功能總覽。
- L1.5 結構概覽。

L1 與 L1.5 是平行視角，不得做成父子展開。這必須遵守 `docs/phase-0a/07-layer-switching.md`。

L2 只能從 L1.5 的區塊或變更詳情中展開，不做主 tab。

## 5. 版本差異呈現

### 5.1 差異圖規則

差異模式中，節點狀態直接來自 `NodeDiff.diff_state`。

| `diff_state` | UI 符號 | UI 語意 |
|---|---|---|
| `added` | `+` | 新增功能 |
| `removed` | `-` | 移除功能 |
| `attribute_changed` | `~` | 功能描述或屬性變更 |
| `dependency_changed` | `!=` | 功能依賴關係變更 |
| `unchanged` | 無或降調 | 未變更 |

UI 的顏色與符號必須沿用 `docs/phase-0a/08-vocabulary-table.md` 與 `core/diff/diff_renderer.py` 的語意，不可另創衝突語言。

### 5.2 變更清單排序

左側變更清單排序應與 `core/pipeline/report_renderer.py` 的風險優先邏輯一致：

1. 超出範圍。
2. 漏洞風險。
3. 語意漂移。
4. 新增。
5. 修改。
6. 移除。

若前端需要重新排序，必須以後端輸出的排序結果為準，或在共用資料契約中新增排序欄位。不得在前端複製一份不一致的風險排序規則。

### 5.3 Before/After 詳情

點選變更時，右側詳情面板必須顯示：

- 功能名稱。
- 變更狀態。
- `baseline_label`，若存在。
- `current_label`，若存在。
- `baseline_description`，若存在。
- `current_description`，若存在。
- scope 狀態，若存在。
- related vulnerabilities，若存在。
- affected relations，若存在。
- 原始資料來源，例如 `DiffResult.node_diffs` 或 `UpdateReport.l2_details`。

若某欄位不存在，顯示「未提供」，不得補寫看似合理的文字。

### 5.4 新增前端時的預期展示

若未來把前端功能加入 The Door 專案，差異模式應能自然顯示類似下列變更，但這些項目只能在 LLM/分析結果實際產生時顯示：

- 新增：本地前端工作台。
- 新增：版本差異 Viewer。
- 新增：功能詳情側欄。
- 修改：功能圖形產出，從 Mermaid 文字輸出擴展為互動式呈現。
- 修改：版本更新管線，新增前端可消費資料。

以上只是未來可能出現的分析結果範例，不得硬編進 UI。

## 6. 資料契約

### 6.1 MVP 主要輸入

MVP 優先吃 `UpdateReport` JSON。其來源是 `ReportRenderer.render_json()`。

必要欄位：

```text
report_version
generated_at
pipeline_summary
l0_summary
l1_changes
l2_details
l3_appendix
interrupted
```

若沒有 `UpdateReport`，可退回單版本展示模式，讀取 `L1Output` JSON。此時必須關閉差異模式。

MVP 不新增新的 report schema。若現有 `UpdateReport` 欄位不足，應先擴充 `models.py` / `ReportRenderer.render_json()` / 對應 schema / 測試，再讓 UI 使用新欄位。

### 6.2 建議 UI Cache

未來可在專案本地新增 UI cache，但內容只能是既有分析結果的投影，不得成為新的事實來源。

```text
.the-door/
  ui-cache/
    latest-update-report.json
    latest-l1-output.json
    latest-l1-diagram.mmd
    latest-structure-summary.json
```

UI cache 可以被刪除並由既有資料重建。任何不能重建的資料不應放在 UI cache 中。

### 6.3 Structure JSON 使用限制

`StructureJSON` 可能很大，例如目前 `docs/self-analysis-structure.json` 約 500KB。前端不得預設渲染完整 AST graph。

允許用途：

- 顯示統計數字。
- 顯示被選功能的 `source_nodes`。
- 顯示模組分布摘要。

禁止用途：

- 首屏渲染 459 個節點與 1,145 條邊。
- 在前端用 AST node 名稱自行推測 L1 功能。
- 在 UI 中把未經 LLM/驗證輸出的 AST 關係標成業務關係。

## 7. 本地資源與網路使用

### 7.0 最小技術棧

MVP 前端技術棧：

- HTML。
- CSS。
- Vanilla JavaScript。
- 本地 JSON 檔案。
- 現有 Python CLI/core 作為資料產生來源。

允許但非必需：

- 本地打包的 Mermaid，用於渲染現有 `.mmd` 或 Markdown code fence 中的 Mermaid 圖。

MVP 不引入：

- React。
- TypeScript。
- Vite。
- React Flow。
- Zustand。
- TanStack Query。
- 前端測試框架。
- UI component library。

若未來需要互動圖框架或前端 build pipeline，必須在 Phase UI-3 另開設計決策，說明為什麼 Mermaid + Vanilla JS 不足。

### 7.1 本地優先

若 MVP 使用純靜態檔，所有資源必須來自本地檔案：

- HTML。
- CSS。
- JavaScript。
- 可選的 Mermaid 本地檔案。

MVP 不要求 build pipeline，也不要求 icon 套件。若需要圖示，優先使用文字符號與現有視覺詞彙，例如 `+`、`-`、`~`、`!=`、`?`、`!`。

禁止預設依賴：

- CDN 字體。
- CDN icon。
- 外部 analytics。
- 遠端圖片。
- 需要雲端登入的 UI framework。

### 7.2 LLM 使用邊界

前端不得自動呼叫 LLM。只有下列明確使用者行為可以觸發 LLM 相關分析：

- 重新分析。
- 強制重新分析。
- 產生 L2。
- 重新生成某個功能。
- source review。

觸發前必須顯示成本、provider 或本地模型資訊。若資訊不存在，顯示未知並要求使用者確認。

## 8. API 邊界

若實作 `the-door ui`，後端 API 應是薄包裝，不重寫核心邏輯。

MVP 可以先不提供 JSON API，只用靜態 viewer 讀取固定資料檔。只有當需要列出 snapshots、執行 update pipeline、或顯示 pipeline progress 時，才新增本地 API。

建議端點：

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/project` | 專案路徑、可用資料狀態 |
| GET | `/api/snapshots` | 讀取 `SnapshotStore.list_snapshots()` |
| GET | `/api/report/latest` | 讀取最新 `UpdateReport` 或回傳缺資料 |
| POST | `/api/update` | 呼叫 `PipelineOrchestrator.run()` |
| GET | `/api/doubts` | 讀取 `DoubtStore.list_doubts()` |
| GET | `/api/timeline` | 讀取或計算 `TimelineResult` |

API 回應必須使用結構化 JSON。錯誤回應必須包含：

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "source": "string"
  }
}
```

## 9. 前端元件邊界

### 9.1 建議元件

此處的「元件」是邏輯模組，不要求使用 React 或任何 component framework。MVP 可用普通 JavaScript function 與 DOM template 實作。

| 元件 | 職責 |
|---|---|
| `AppShell` | 頂部狀態列、三欄布局 |
| `VersionSelector` | baseline/current 選擇 |
| `ModeTabs` | 舊版/新版/差異 |
| `ViewTabs` | L1/L1.5 |
| `ChangeList` | 風險優先變更清單 |
| `GraphCanvas` | Mermaid 或互動圖呈現 |
| `DetailPanel` | Before/After、證據、source nodes |
| `RawDataPanel` | JSON/Mermaid 原文 |
| `PipelineProgress` | 管線步驟與耗時 |
| `EmptyState` | 缺資料狀態 |

### 9.2 禁止的元件行為

- `GraphCanvas` 不得直接修改資料狀態。
- `DetailPanel` 不得自行推測缺失欄位。
- `ChangeList` 不得使用與後端不一致的排序規則。
- `RawDataPanel` 不得成為使用者主要操作入口。
- 任一元件不得直接讀 filesystem；本地檔案讀取由後端或靜態資料載入層負責。

## 10. 視覺與互動規則

### 10.1 首屏

首屏必須優先呈現：

- L0 摘要。
- 差異或功能總覽。
- 風險項目數量。
- 可點選的變更清單。

不得首屏呈現：

- 完整 JSON。
- 完整 AST graph。
- 大段說明文字。
- 產品宣傳 hero。

### 10.2 圖形渲染策略

MVP 使用 Mermaid：

- 優點：直接對齊現有 renderer。
- 限制：互動能力有限。

第二階段若需要完整互動圖，可另行評估本地圖形套件：

- 只能從 `L1Output`、`L1_5Output`、`DiffResult`、`UpdateReport` 轉換。
- 轉換函式必須有單元測試。
- Mermaid fallback 必須保留，避免互動圖渲染失敗時完全無圖。
- 不得在本 spec 的 MVP 中直接引入互動圖框架。

### 10.3 詳情面板

點選節點或變更時，右側面板必須顯示資料來源。

例如：

```text
資料來源：
UpdateReport.l2_details[feature_id=...]
DiffResult.node_diffs[node_id=...]
```

這是防幻覺 UX 的核心。使用者必須能知道畫面上的文字來自哪個輸出。

## 11. 錯誤與空狀態

| 情境 | UI 行為 |
|---|---|
| 沒有分析結果 | 顯示「尚未分析」，提供本地指令建議 |
| 沒有 DiffResult | 關閉差異模式，提示需執行 update |
| JSON 解析失敗 | 顯示檔案名稱與錯誤訊息，不吞錯 |
| Mermaid 渲染失敗 | 顯示原始 Mermaid text 與錯誤 |
| Pipeline step failed | 顯示對應 step、error_message、可用部分結果 |
| LLM provider 未設定 | 不自動分析，提示設定方式 |

不得在錯誤時顯示空白畫面。

## 12. 正確性屬性

### Property 1: UI-Diff count consistency

對任一有效 `UpdateReport`，UI 變更清單中各 `change_type` 的數量必須與 `l1_changes` 中對應數量一致。

### Property 2: No invented features

UI 中顯示的每一個功能，必須能追溯到以下至少一種資料來源：

- `L1Output.features`
- `VersionSnapshot.l1_snapshot`
- `DiffResult.node_diffs`
- `UpdateReport.l1_changes`
- `UpdateReport.l2_details`

否則不得顯示為功能。

### Property 3: Diff mode requires diff data

若沒有 `DiffResult` 或 `UpdateReport.l1_changes`，差異模式不可啟用。

### Property 4: Before/After truthfulness

若 `baseline_label` 或 `baseline_description` 不存在，UI 必須顯示未提供；不得用 current 欄位補值。

若 `current_label` 或 `current_description` 不存在，UI 必須顯示未提供；不得用 baseline 欄位補值。

### Property 5: Raw data round trip

UI 讀取的 JSON 檔案若未被使用者編輯，RawDataPanel 顯示的 JSON 重新 parse 後必須與原始資料等價。

### Property 6: Local-only default

啟動 UI、切換版本、切換模式、點選節點、展開詳情，不得產生任何外部網路請求。

### Property 7: Resource bound

首屏不得渲染完整 `StructureJSON` graph。若使用者開啟原料或來源節點，應按需顯示局部資料。

## 13. 測試策略

### 13.0 TDD 執行順序

所有 UI 資料邏輯必須依下列順序實作：

1. 先寫 fixture 或測試案例，描述輸入 JSON 與預期 view model。
2. 執行測試，確認失敗。
3. 實作最小資料轉換邏輯讓測試通過。
4. 補上缺欄位、錯誤 JSON、無 DiffResult、空變更清單等邊界測試。
5. 最後才接 DOM 呈現。

DOM 呈現不得包含業務判斷。業務判斷應在可測試的資料轉換函式中完成。

MVP 的資料轉換函式優先用 Python 實作，放在既有測試體系可覆蓋的位置，輸出靜態 view model JSON 給前端讀取。Vanilla JavaScript 只負責讀取 view model、更新 DOM、處理點擊狀態，不重新計算 diff、scope 或風險排序。

### 13.1 Unit Tests

必測：

- `UpdateReport` 到 UI view model 的轉換。
- `L1Output` 到單版本 view model 的轉換。
- `DiffResult` 到 graph node/edge view model 的轉換。
- 缺欄位時的顯示策略。
- 風險排序與後端輸出一致。
- Mermaid 缺失或渲染失敗時的 fallback view model。

### 13.2 Property-Based Tests

優先使用既有 Python 測試棧 `pytest` 與 `hypothesis` 驗證資料轉換與 correctness properties。MVP 不新增前端 property-based testing 套件。

測試屬性至少包含第 12 節的七項 correctness properties。

### 13.3 Fixture Tests

固定使用目前 `docs/` 的自我分析成果作為 fixture：

```text
docs/self-analysis-l1-output.json
docs/self-analysis-l1-diagram.md
docs/self-analysis-structure.json
```

未來新增前端功能後，應新增 before/after fixture：

```text
docs/fixtures/frontend-update/before/
docs/fixtures/frontend-update/after/
docs/fixtures/frontend-update/update-report.json
```

fixture 不得手寫捏造為正式驗收資料。若需手寫 mock，檔名必須標示 `mock`，並不得用於宣稱真實分析效果。

## 14. 開發階段

### Phase UI-0: Static Prototype

目標：驗證三欄工作台與單版本自我分析呈現。

輸入：

- `docs/self-analysis-l1-output.json`
- `docs/self-analysis-l1-diagram.md`
- `docs/self-analysis-structure.json`

限制：

- 不跑後端。
- 不執行分析。
- 不提供差異模式，除非有真實或明確 mock 的 `UpdateReport`。
- 使用 HTML/CSS/Vanilla JavaScript。
- 不新增 npm build pipeline。

### Phase UI-1: Local Report Viewer

目標：讀取 `UpdateReport`，提供舊版/新版/差異模式。

輸入：

- `ReportRenderer.render_json()` 輸出的 JSON。

功能：

- 版本狀態列。
- 差異清單。
- 差異圖。
- 詳情面板。
- Raw data panel。

### Phase UI-2: Local API Server

目標：新增 `the-door ui <project-path>`。

功能：

- 讀取本地 `.the-door/`。
- 列出 snapshots。
- 執行 update pipeline。
- 顯示 progress。

限制：

- API 僅包裝既有 core。
- 不重寫 diff/scope/timeline 邏輯。

### Phase UI-3: Interactive Graph

目標：加入更完整的互動圖。

限制：

- 此階段需要另行設計決策，不屬於 MVP。
- 保留 Mermaid fallback。
- graph view model 必須由正式資料契約轉換。
- 不得在圖形層創造新的業務語意。

## 15. 明確不做

MVP 不做：

- 雲端帳號。
- 多人即時協作。
- 遠端專案同步。
- 外部資料庫。
- 新增前端 framework 或 build tool。
- 自動背景監控檔案變化。
- 在瀏覽器端直接呼叫 LLM provider。
- 完整 AST graph 首屏視覺化。
- 工程師手動校正 LLM 輸出。
- 以 UI 狀態取代 `.the-door/` 的本地資料。

這些項目若未來需要，必須另開 spec，不得混入本前端 MVP。

## 16. 驗收標準

前端 MVP 完成的最低標準：

1. 可在無外部網路的情況下啟動並讀取本地分析資料。
2. 可顯示單版本 L1 功能總覽。
3. 有 `UpdateReport` 時，可切換舊版、新版、差異模式。
4. 差異清單數量與 `UpdateReport.l1_changes` 一致。
5. 點選任一變更，可看到 Before/After 與資料來源。
6. 無 `DiffResult` 時，差異模式不可假裝可用。
7. 不顯示任何資料中不存在的功能、風險或來源檔案。
8. 首屏不渲染完整 AST graph。
9. 所有錯誤狀態有明確訊息。
10. 測試覆蓋資料轉換、缺欄位、差異計數、無網路預設行為。
