# T5-V spec：viewer 生成路退場（保留 display-only）

> **日期**：2026-06-08　**狀態**：spec（待雙審 → plan → 雙審 → inline TDD → ff-merge）
> **承接**：丙案種子 §10.7.1 **D1**（viewer L2/diff 退場生成、保留 display、不建 T3/T4）＋ §10.7.2 T5。
> **定位**：T5（終局刪除 provider）的**第一個可獨立執行子刀**。T5 經盤點拆三層：
> **T5-V**（本刀，viewer 生成退場）／T5-A（analyze key-path 退場，需 agent-as-LLM L1 證成）／T5-P（provider 核心純刪，待 V+A 後）。
> **性質**：減法（刪 key-bound 生成路），但**保留 display**＝行為對「已生成過的持久化結果」不變。

---

## 1. 命題與目標

viewer 有三條 **POST `.../generate`** 路徑，在瀏覽器點擊那刻即時叫 LLM provider（key-bound）：
L2 生成、層解釋生成、diff 解釋生成。種子 §10.4 已證：`the-door ui` 是 headless web server，
點擊那刻**無 agent 可當 LLM**⟹ 這三條 key-free 救不回（補三件套也沒用）。D1 已拍板**退場**。

**T5-V 做一件事**：移除這三條生成路（POST handler＋背景 job＋provider 接線＋前端 generate 觸發），
**保留三條對應的 GET 讀取/display 路**（讀持久化結果照常渲染）。

達成：
1. **移除 5 個 `create_provider` 中的 3 個**（graph.py:260/300、diff.py:200）——key-bound surface 縮到只剩 analyze 2 點（留給 T5-A）。
2. **零退化**：使用者無 key、這三條生成早已 fail（`ConfigError`→503/fail_job）；移除後改為「功能不存在」，對**有持久化結果者**display 不變。

**非目標**：不碰 provider 核心（provider.py/4 impl/config key 欄位＝T5-P）、不碰 analyze/update key-path（MCP analyze＋CLI＝T5-A）、不碰 BatchReader/CostEstimator/prompts。

---

## 2. 背景與驗證事實（spike 已對真實碼驗畢，免事後驗證）

| # | 事實 | 依據（file:line） |
|---|---|---|
| 2.1 | 三條 POST 生成 handler＝`generate_l2`、`generate_layer_explanation`（graph.py）、`generate_explanation`（diff.py），各自起背景 thread／即時叫 provider | graph.py:120,225；diff.py:170 |
| 2.2 | 三條 GET display handler＝`get_l2`、`get_layer_explanation`、`get_explanation`，**只讀持久化、不叫 LLM**（get_explanation docstring 明寫 "Never triggers LLM"） | graph.py:97,188；diff.py:143,153 |
| 2.3 | `get_l2` 經 `L2Generator.load()`（staticmethod、純讀盤）取持久化 L2 ⟹ **L2Generator.load 必須存活**；provider-bound 部分（`__init__`/`generate`/`_build_prompt`/`_parse_response`/`_persist`）可刪 | graph.py:100；l2_generator.py:40-71,242-290 |
| 2.4 | `get_explanation` 經 `DiffExplanationStore.get()`（純讀 JSONL）⟹ **store.get 存活**；`store.save` 只被 generate 用 ⟹ 可刪 | diff.py:160-163；diff_explanation_store.py:23,29 |
| 2.5 | 兩個背景 job method＝`_run_l2_generate_job`、`_run_layer_explanation_job`，是 graph.py 內唯一 `create_provider`/`ConfigError`/`L2Generator(__init__)` 消費者 | graph.py:255,295,260,300 |
| 2.6 | **`job_store` 是共用基礎設施**：`analysis.py`（update/analyze 任務）也用 `try_create_job`/`fail_job`/`complete_job` ⟹ **JobStore/UpdateJob/try_create_job 一律不刪**，只刪上述 2 個 generation thread method＋2 個 POST handler | analysis.py:51,92,94,159,190,192 |
| 2.7 | router 三條 POST route 在 :148/:151/:154；三條 GET 在 :147/:150/:153 ⟹ **只刪 POST 三行、留 GET 三行** | router.py:147-154 |
| 2.8 | 前端 generate 接線：`api.js` 三個 generate fetch（l2 :65／layer :73／diff :104）；`layers.js` `generateL2`(:256)/`generateLayerExplanation`(:276)＋按鈕 wiring(:465,:501)；diff display＝`ui-diff-explanation.js`。GET 讀取 fetch（api.js:58,97）＋render 留存 | api.js:58,65,73,97,104；layers.js:256,276,465,501 |
| 2.9 | 孤兒 error code（移除生成路後無消費者）＝`provider_not_configured`（僅 diff.py:203）＋`llm_error`（僅 diff.py:224，**impl 時 grep 複核**）。`invalid_layer`/`l2_read_error`/`l2_not_generated`/`explanation_read_error`/`explanation_not_cached`/`no_structure_data`/`structure_read_error`/`job_already_running` 皆仍被 GET 或 analysis 用 ⟹ **保留** | error_codes.py:125,142,157,162,169,174；graph.py:103,111,192,206,216；diff.py:203,224 |
| 2.10 | `find_latest_report_path`（diff.py:17 import）只被 `_collect_diff_context`（generate 私有 helper）用？**impl 時複核**：若其它 handler 也用則保留 import | diff.py:17,255 |

**結論**：keep/delete 邊界清楚，唯 2.9（`llm_error`）、2.10（import 殘留）兩點留 impl 時 grep 複核（皆為「刪後檢孤兒」、非設計未知）。

---

## 3. 設計（keep / delete 對照）

### 3.1 後端 Python

**刪除（generation，key-bound）：**
| 檔 | 刪除標的 |
|---|---|
| `handlers/graph.py` | `generate_l2`(120-158)、`generate_layer_explanation`(225-249)、`_run_l2_generate_job`(255-293)、`_run_layer_explanation_job`(295-末)；imports：`create_provider`、`ConfigError`、`L2Generator`(改只留 load 用法見下)、`L2GenerationError`、`StructureJSON/ASTNode/Edge`(job 內 local import)、`JobStore/UpdateJob`(若 generate 刪後無消費者) |
| `handlers/diff.py` | `generate_explanation`(170-249)、`_collect_diff_context`(251-)、`_build_diff_explanation_prompt`(285-)；imports：`create_provider`、`ConfigManager`/`ConfigError`、`asyncio`、`datetime`、`find_latest_report_path`（複核 2.10） |
| `ui/l2_generator.py` | `__init__`、`generate`、`_build_prompt`、`_parse_response`、`_persist`、`L2GenerationError`、`from ...provider import LLMProvider`。**保留 `load` staticmethod**（display 用） |
| `ui/diff_explanation_store.py` | `save`(23-27)。**保留 `get`** |
| `api/router.py` | POST 三行(:148,:151,:154) |
| `api/error_codes.py` | `provider_not_configured`、`llm_error`（複核 2.9） |

**保留（display-only，零行為改動）：** `get_l2`、`get_layer_explanation`、`get_explanation`、`L2Generator.load`、`DiffExplanationStore.get`、GET 三 route、上述仍被引用的 error code。

> 🔴 **設計決策（雙審已裁定 (A)）**：`L2Generator` 退化成只有 `load` 一個 staticmethod 後，類名「Generator」名實不符。**採 (A) 維持類名、僅留 `load`**（最小 diff、`get_l2` 呼叫點不動；改名 (B) 留待 display 面另案）。**命名債緩解**：留碼處加 class docstring 註明「display-only 殘件——L2 生成已於 T5-V 退場，本類僅存讀盤 `load`」，讓未來讀者知是刻意保留。

### 3.2 前端 viewer（`docs/frontend-local-version-viewer/viewer/`）

> 🔴 **審查校正（concept-review critical）**：generate **不是**獨立模組，而是**織入 display render 函式內**——render 函式自己建 generate/regen 按鈕。證據：
> - `ui-diff-explanation.js:22-33` `renderExplanationEmpty` 建 generate 按鈕＋綁 `generateDiffExplanation`；`:37,75-77` `renderExplanationContent` 建 regen 按鈕。
> - `layers.js:480-501` `renderL2NotAnalyzed` 建按鈕＋呼 `generateL2`；`:457-465` `renderFeatureList` 經 `onGenerateLayerExplanation` 綁層解釋生成。
>
> ⟹ 刪除是「**編輯 render 函式挖掉內嵌按鈕＋重定義空狀態**」，非「刪一個獨立 generate 函式」。

**刪除（generate 觸發層）：**
- `api.js`：三個 generate fetch(:65,:73,:104)。
- `layers.js`：`generateL2`(:256)、`generateLayerExplanation`(:276)、`renderL2NotAnalyzed` 內的生成按鈕(:494-501)、`renderFeatureList` 的 `onGenerateLayerExplanation` 接線(:465)。
- `ui-diff-explanation.js`：`generateDiffExplanation`(:81)、`renderExplanationEmpty`/`renderExplanationContent` 內的 generate/regen 按鈕建構(:31-33,:75-77)。
- `index.html`/`styles.css`：對應 generate 按鈕的死元素/樣式（impl 時複核 selector）。

**display-only 終態（每 surface 明確定義，取代被挖掉的按鈕）：**
| surface | content（有持久化結果） | empty（無結果） |
|---|---|---|
| L2（`renderL2NotAnalyzed`／L2 render） | 照常渲染 L2 模組圖（不動） | 「尚未生成 L2」**純文字說明、無動作按鈕**（移除「點此生成」鈕） |
| 層解釋（`renderFeatureList`/`layers.js`） | 照常渲染快取說明 | 「此層尚無說明」純文字、無生成鈕 |
| diff 解釋（`ui-diff-explanation.js`） | `renderExplanationContent` 渲染內容、**去掉 regen 鈕** | `renderExplanationEmpty` 顯示「尚無差異說明」純文字、無 generate 鈕 |

**保留：** GET 讀取 fetch(api.js:58,97)＋ render 函式的「資料→DOM」渲染主體（只挖按鈕、不動內容渲染）。

> ⚠ **前端是唯一正式版** `viewer/`（勿動 `prototype/`）。

### 3.3 不動（保證邊界）
- provider.py／openai/anthropic/ollama_provider.py／config key 欄位：**T5-P**，本刀不碰。
- analyze_tool/analyze_pipeline/BatchReader/CostEstimator/prompts：**T5-A**，本刀不碰。
- JobStore/UpdateJob/job_store（共用，2.6）：**不刪**。

---

## 4. 範圍邊界

**In scope**：刪三條 POST 生成路（後端 handler＋job＋provider 接線＋router＋孤兒 error code＋L2Generator/Store 的生成半）＋前端 generate 觸發；保留全部 GET display。

**Out of scope**：
- ❌ provider 核心刪除（T5-P）／analyze key-path（T5-A）。
- ❌ 改 GET display 的行為或外觀（純保留）。
- ❌ 清理持久化資料（`.the-door/l2-outputs`、`layer-explanations`、`diff-explanations`）——既有結果續供 display 讀。
- ❌ C3/C4 gate（另案）。

---

## 5. 驗收 / TDD（紅→綠）

> 雙層測試：Python（pytest，cwd 內層 `the_door/`、`PYTHONUTF8=1`）＋ viewer（vitest，cwd `viewer/`、`npm ci`+`npm test`、gate＝0 red）。

> 🔴 **測試策略校正（concept-review warning）**：本刀是**刪除**。display 的 KEEP 行為**已有測**且採 **mock-loader 模式**——`test_graph.py:44-57` `patch("...graph.L2Generator"); mock_lg.load.return_value=...`。**沿用既有 mock 模式**（mock `L2Generator.load`／`DiffExplanationStore.get`），**不**改用 input-only 落盤 fixture（本刀無真 E2E 需求；input-only 守則只適用真 E2E）。刪除的「red」＝把 generate-path 的既有測**移除**（非留 failing）。

**Python keep-side 回歸（沿用既有 mock 模式，確認 display 不變）：**
| # | 測試 | 斷言 |
|---|---|---|
| K-1 | `get_l2`（mock `L2Generator.load`） | load 回值→200＋view_model；load `None`→404 `l2_not_generated`（既有 test_graph:42-62 保留） |
| K-2 | `get_layer_explanation`（tmp 快取檔／既有法） | 已快取→200；未快取→404 `explanation_not_cached`；非法 layer→400 `invalid_layer` |
| K-3 | `get_explanation`（mock/tmp `DiffExplanationStore.get`） | 已快取→200＋entry；無快取→200＋`{"explanation": null}` |
| K-4 | router 不再含三條 POST generate | POST `/api/l2/.../generate` 等三路由未註冊；GET 三路由仍在（`test_router_binding` 擴充） |
| K-5（回歸護欄） | `analysis.py` job＋`job_store` 全綠 | JobStore/try_create_job 未被波及 |

**Python delete-side（明列移除/縮減的既有測——axis-3）：**
- `test_graph.py`：刪 `generate_l2` 相關（:63-87 `test_no_structure_returns_404`/`test_job_already_running`/`test_valid_returns_202`）＋ `generate_layer_explanation` 相關測。
- `test_diff.py`：刪 `generate_explanation` 相關測（保留 `get_explanation`/`versions` 測）。
- `test_l2_generator.py`：刪 `generate`/`_parse_response`/`_persist` 測，**保留 `load` 測**（檔案縮減、非整刪）。
- `test_providers.py` **不動**（provider 仍存在＝T5-P 才刪）。
- impl 後 grep 確認無 dangling：`provider_not_configured`/`llm_error` 在 `src/` 零命中。

**viewer（vitest）：** `api.test.js`/`layers.test.js`/`ui-diff-explanation.test.js` 中**針對 generate** 的測移除；**display render 測保留並綠**（斷言 render 後 DOM **不再含 generate/regen 按鈕**、content/empty 文案符合 §3.2 終態表）。**gate＝0 red。**

---

## 6. 不做 / 防呆紀錄
- **不刪 job_store**（2.6 共用）。
- **不刪 GET / display**（D1「保留 display」）。
- **不刪持久化資料**（既有結果續讀）。
- **不碰 provider/analyze**（T5-P/T5-A 邊界）。
- **不自鑄**：孤兒 error code 一律 grep 複核才刪（2.9）。

---

## 7. Forward-coherence（對 T5-A / T5-P 提供什麼）
- T5-V 後 `create_provider` 消費者只剩 analyze 2 點（analyze_tool:67、analyze_pipeline:184）⟹ T5-A 的 blast radius 收斂、且與 viewer 完全解耦。
- T5-V **不**動 provider.py／config key ⟹ T5-P 仍可在 V+A 都完成、零消費者後一次純刪。
- **順序鎖驗證**：T5-V 移除 viewer 生成不影響 `edge_projection`（T2 已工具化存活）；analyze 路徑（BatchReader→edge_projection）仍在，故 edge_projection 在 T5-A 前持續有兩個消費者（analyze＋edge_residue），T5-A 後剩 edge_residue。與種子 §9.4 順序鎖一致。

---

## 8. 雙審結果（concept --design ＋ 5 軸；已 inline 修畢）
**已修（critical/warning）：**
- ✅ **critical（Logical Continuity）**：generate 織入 render 函式——§3.2 改為「編輯 render 挖按鈕＋定義 display-only 終態表」（三 surface）。
- ✅ **warning（Conflict Detection）**：測試策略與既有 mock-loader 模式矛盾——§5 改為沿用 mock `L2Generator.load`/`DiffExplanationStore.get`，input-only fixture 只給真 E2E。
- ✅ **axis-3（計數/coverage）**：§5 補「delete-side 既有測明列」（test_graph/test_diff/test_l2_generator 縮減，test_providers 不動）。
- ✅ **suggestion（命名債）**：§3.1 裁定 (A)＋要求 class docstring 標明 display-only 殘件。

**留待 impl 時 grep 複核（非設計未知，皆「刪後檢孤兒」）：**
- 2.9 `llm_error`、2.10 `find_latest_report_path` import 是否真孤兒。
- graph.py 移除 generation 後 `JobStore/UpdateJob` import 是否真無消費者。
- `index.html`/`styles.css` 的 generate 按鈕 selector 確認後再刪。
