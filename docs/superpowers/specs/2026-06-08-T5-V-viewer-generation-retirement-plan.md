# T5-V plan：viewer 生成路退場（inline TDD 任務分解）

> **承接 spec**：`2026-06-08-T5-V-viewer-generation-retirement-spec.md`（已雙審通過、findings 修畢）。
> **執行模式**：inline TDD，分 3 task；全綠後一次 ff-merge（commit 已獲連跑授權、不 push）。
> **雙層環境**：Python＝pytest cwd 內層 `the_door/`、`PYTHONUTF8=1`；viewer＝cwd `docs/frontend-local-version-viewer/viewer/`、`npm ci` 後 `npm test`、gate＝0 red。
> **性質**：刪除＋display 保留。red＝(a) keep-side 行為測續綠（沿用既有 mock 模式）；(b) generate-path 測移除；(c) 前端 render 測斷言「無 generate 按鈕」。

---

## 測試策略（雙審已定，記此免重議）
- **不**新建 input-only 落盤 fixture；display 的 KEEP 行為沿用既有 **mock-loader** 模式（`patch("...graph.L2Generator")`、`mock.load.return_value`），見 spec §5。
- 刪除的「red」＝把 generate-path 既有測**移除**（非留 failing）。
- 前端 display 測**升級斷言**：render 後 DOM **不含** generate/regen 按鈕、空狀態文案符合 spec §3.2 終態表。

---

## Task 1 — 後端生成路刪除（Python）

**先複核（impl 起手 grep，關 spec §8 留檢項）**
1. `grep -rn "llm_error" src/` → 確認僅 diff.py generate 用（真孤兒才刪 error_codes）。
2. `grep -rn "find_latest_report_path" src/` → 確認僅 `_collect_diff_context` 用（才連 import 刪）。
3. `grep -rn "JobStore\|UpdateJob" src/the_door/core/ui/api/handlers/graph.py` → 確認 generation 刪後 graph.py 無 job 用法（才刪 import；2.6 全域 JobStore 不動）。
4. `grep -rn "L2GenerationError" src/ tests/` → 確認刪後無 dangling。

**Green-keep（先跑既有 keep 測確認綠基線）**
- `PYTHONUTF8=1 python -m pytest tests/unit/core/ui/api/handlers/test_graph.py tests/unit/core/ui/api/handlers/test_diff.py tests/unit/core/ui/test_l2_generator.py -q`

**刪除（spec §3.1）**
- `handlers/graph.py`：`generate_l2`、`generate_layer_explanation`、`_run_l2_generate_job`、`_run_layer_explanation_job`＋孤兒 import（`create_provider`/`ConfigError`/`L2GenerationError`/job-local imports／確認後的 `JobStore,UpdateJob`）。**保留** `get_l2`/`get_layer_explanation`/`get_structure`。
- `handlers/diff.py`：`generate_explanation`、`_collect_diff_context`、`_build_diff_explanation_prompt`＋孤兒 import（`create_provider`/`ConfigManager,ConfigError`/`asyncio`/`datetime`/複核後的 `find_latest_report_path`）。**保留** `versions`/`get_explanation`。
- `ui/l2_generator.py`：刪 `__init__`/`generate`/`_build_prompt`/`_parse_response`/`_persist`/`L2GenerationError`/`LLMProvider` import；**保留 `load`**＋加 class docstring「display-only 殘件」（spec §3.1 決策 A）。
- `ui/diff_explanation_store.py`：刪 `save`；保留 `get`。
- `api/router.py`：刪 POST 三行(:148,:151,:154)；GET 三行(:147,:150,:153)留。
- `api/error_codes.py`：刪複核後確認的孤兒（`provider_not_configured`＋`llm_error`）。

**測試（delete-side ＋ keep-side）**
- 移除：
  - `test_graph.py` 的 generate_l2／generate_layer_explanation 測（spec §5 列；也涵蓋 l2/layer generate「不存在」）。
  - `test_diff.py` 的 generate_explanation 測（保留 `get_explanation`/`versions`）。
  - `test_l2_generator.py` 的 generate/_parse/_persist 測（**保留 load 測**）。
  - 🔴 **`test_router_binding.py:261-290` 整個 `TestPostDiffExplanationsGenerate` 類**（live-HTTP 測被刪端點、且 :283 斷言被刪的 `provider_not_configured`）——**與刪 error code 同一步收尾**（plan-review critical/warning）。
- keep 測 K-1..K-3（沿用 mock 模式，多為既有保留）＋ K-4。
- **K-4（router 無 POST generate，改寫）**：在 `test_router_binding.py` 加一測——POST `/api/diff-explanations/feat-auth/generate` → **404＋`router.no_route`**（router.py:127 unmatched path 行為已驗；移除 POST route 後此 4-段路徑不匹配保留的 3-段 GET template）。GET `/api/diff-explanations/<fid>` 仍 200（既有 `TestGetDiffExplanations` 保留）。
- `test_providers.py` 不動（provider 仍存在＝T5-P 才刪）。

**Verify**：`PYTHONUTF8=1 python -m pytest tests/unit/core/ui/ tests/integration/test_router_binding.py -q` 全綠。

---

## Task 2 — 前端生成觸發刪除＋display 終態（viewer）

**先讀真實 render 函式**（impl 起手）：`ui-diff-explanation.js`（renderExplanationEmpty/Content、generateDiffExplanation）、`layers.js`（renderL2NotAnalyzed、renderFeatureList 的 onGenerateLayerExplanation、generateL2/generateLayerExplanation）、`api.js`（三 generate fetch）。

**Red（先改測，斷言新終態）**
- `ui-diff-explanation.test.js`：移除 generate 測；新增/改 display 測——`renderExplanationContent` 後 DOM **無** `.diff-explanation-generate-btn`；`renderExplanationEmpty` 顯示「尚無差異說明」純文字、無按鈕。
- `layers.test.js`：移除 generateL2/generateLayerExplanation 測；改 `renderL2NotAnalyzed` 測斷言**無生成按鈕**、顯示純文字終態。
- `api.test.js`：移除三 generate fetch 測；保留 GET fetch 測。

**Green（impl）**：依 spec §3.2
- `api.js`：刪三 generate fetch(:65,:73,:104)；留 GET(:58,:97)。
- `layers.js`：刪 `generateL2`/`generateLayerExplanation`；`renderL2NotAnalyzed` 挖生成按鈕→純文字；`renderFeatureList` 去 `onGenerateLayerExplanation` 接線。
- `ui-diff-explanation.js`：刪 `generateDiffExplanation`；`renderExplanationContent` 去 regen 鈕；`renderExplanationEmpty` 去 generate 鈕→純文字。
- `index.html`/`styles.css`：複核 selector 後刪死按鈕元素/樣式。

**Verify**：`cd viewer && npm test` → **gate＝0 red**（display 測綠、generate 測已除）。

---

## Task 3 — 全套驗證（雙層零回歸）

- Python 全套：`PYTHONUTF8=1 python -m pytest -q`（預期 passed 數＝baseline 減去移除的 generate 測數；**0 failed**）。
- viewer 全套：`cd viewer && npm test`（**0 failed**）。
- dangling 終檢：`grep -rn "create_provider" src/the_door/core/ui/` → **零命中**（3 個 viewer call site 已除，只剩 analyze 2 點在 mcp/core.pipeline）。
- `grep -rn "provider_not_configured\|llm_error\|L2GenerationError\|\.save(" src/the_door/core/ui/` → 確認孤兒清乾淨。

**done-state（全綠才 ff-merge）**
- [ ] graph.py/diff.py 三 generate handler＋2 job method 已刪；GET display 三 handler 保留且測綠。
- [ ] l2_generator 只剩 `load`＋docstring；diff_explanation_store 只剩 `get`。
- [ ] router 無三 POST generate；GET 三在。
- [ ] 孤兒 error code/import 清除、grep 零 dangling。
- [ ] viewer 三 surface display-only 終態（無 generate/regen 按鈕）、render 測綠、gate 0 red。
- [ ] `create_provider` 在 `core/ui/` 零命中（3/5 call site 已除）。
- [ ] Python＋viewer 全套 0 failed。

## 不做（再次釘樁，承 spec §4/§6）
- 不碰 provider 核心/config key（T5-P）、不碰 analyze/BatchReader（T5-A）、不刪 JobStore（共用）、不刪持久化資料、不改 GET display 行為/外觀（只挖按鈕）。
