# Implementation Tasks — Phase UI-3: Interactive Graph

## Task 1: GraphViewModel_Converter 純函式模組（TDD）

- [x] 1.1 建立 `the_door/tests/unit/core/ui/test_graph_view_model.py`，寫入所有 unit tests（先失敗）
  - `test_build_l1_empty_features`
  - `test_build_l1_empty_relations`
  - `test_build_l1_dangling_edge_omitted`
  - `test_build_l1_all_confidence_levels`
  - `test_build_l1_trigger_description_present`
  - `test_build_l1_from_snapshot_trigger_description_null`
  - `test_build_l2_empty_modules`
  - `test_build_l2_anomalies_with_multiple_affected_nodes`
  - `test_build_l2_dangling_interaction_omitted`
  - `test_build_l3_empty_source_nodes`
  - `test_build_l3_non_existent_source_nodes`
  - `test_build_l3_mixed_node_types`
  - `test_build_l3_edges_filtered_to_source_nodes`
  - `test_build_diff_all_change_types`
  - `test_build_diff_empty_l1_changes`
  - `test_build_diff_edges_between_different_change_types`
  - `test_build_diff_no_diff_result_no_edges`
  - `test_sort_risk_first_order`
  - `test_sort_semantic_diff_three_nodes_varying_magnitude`
  - `test_sort_semantic_diff_null_fields_treated_as_empty`
- [x] 1.2 實作 `the_door/src/the_door/core/ui/graph_view_model.py`
  - `build_l1_graph_view_model(l1_output: L1Output) -> dict`
  - `build_l1_graph_view_model_from_snapshot(l1_snapshot: dict, feature_relations_snapshot: list) -> dict`
  - `build_l2_graph_view_model(l2_output: L2Output) -> dict`
  - `build_l3_graph_view_model(structure_json: StructureJSON, source_node_ids: list[str]) -> dict`
  - `build_diff_graph_view_model(update_report: dict, diff_result: dict | None) -> dict`（內部呼叫 `sort_diff_nodes_by_risk`）
  - `sort_diff_nodes_by_risk(nodes: list[dict]) -> list[dict]`
  - `sort_diff_nodes_by_semantic_diff(nodes: list[dict]) -> list[dict]`
  - `_edit_distance(a: str | None, b: str | None) -> int`
- [x] 1.3 確認所有 unit tests 通過

## Task 2: GraphViewModel_Converter 屬性測試（PBT）

- [x] 2.1 建立 `the_door/tests/property/test_graph_view_model_properties.py`，寫入 12 個 Hypothesis 屬性測試
  - `prop_l1_no_dangling_edges`
  - `prop_l1_node_count_equals_feature_count`
  - `prop_l1_node_ids_unique`
  - `prop_l2_no_dangling_edges`
  - `prop_l2_node_ids_unique`
  - `prop_diff_valid_change_types`
  - `prop_diff_no_dangling_edges`
  - `prop_l1_node_required_fields`
  - `prop_l2_node_required_fields`
  - `prop_sort_semantic_diff_idempotent`
  - `prop_sort_risk_first_out_of_scope_before_others`
  - `prop_sort_semantic_diff_monotone`
  - 所有 strategy 使用 ASCII-only 字串（`@settings(max_examples=100)`）
- [x] 2.2 確認所有 PBT 通過

## Task 3: L2Generator 模組（TDD）

- [x] 3.1 建立 `the_door/tests/unit/core/ui/test_l2_generator.py`，寫入所有 unit tests（先失敗）
  - `test_generate_calls_llm_with_prompt`
  - `test_generate_persists_to_disk`
  - `test_generate_llm_error_raises_l2_generation_error`
  - `test_generate_invalid_json_raises_l2_generation_error`
  - `test_load_returns_none_when_not_found`
  - `test_load_returns_l2_output_when_found`
- [x] 3.2 實作 `the_door/src/the_door/core/ui/l2_generator.py`
  - `L2GenerationError` exception class
  - `L2Generator.__init__(project_root: Path, llm_provider: LLMProvider)`
  - `L2Generator.generate(feature_id: str, structure_json: StructureJSON) -> L2Output`（async）
  - `L2Generator._build_prompt(feature_id: str, structure_json: StructureJSON) -> str`
  - `L2Generator._parse_response(raw: str) -> L2Output`
  - `L2Generator._persist(feature_id: str, l2_output: L2Output) -> None`
  - `L2Generator.load(project_root: Path, feature_id: str) -> L2Output | None`（staticmethod）
- [x] 3.3 確認所有 unit tests 通過

## Task 4: API Handlers 擴展（TDD）

- [x] 4.1 建立 `the_door/tests/unit/core/ui/test_api_handlers_ui3.py`，寫入所有 unit tests（先失敗）
  - `test_get_l1_returns_view_model`
  - `test_get_l1_no_snapshot_returns_404`
  - `test_get_l2_found_returns_view_model`
  - `test_get_l2_not_found_returns_404`
  - `test_post_l2_generate_returns_202`
  - `test_post_l2_generate_no_structure_returns_404`
  - `test_post_l2_generate_job_already_running_returns_409`
  - `test_get_layer_explanation_found`
  - `test_get_layer_explanation_not_found_returns_404`
  - `test_get_layer_explanation_invalid_layer_returns_400`
  - `test_post_layer_explanation_generate_returns_202`
  - `test_post_layer_explanation_generate_job_running_returns_409`
  - `test_get_structure_found`
  - `test_get_structure_not_found_returns_404`
- [x] 4.2 在 `api_handlers.py` 新增 6 個 handler 方法 + 2 個私有背景執行緒方法（不修改現有 7 個方法）
  - `handle_get_l1(self) -> tuple[int, dict]`
  - `handle_get_l2(self, feature_id: str) -> tuple[int, dict]`
  - `handle_post_l2_generate(self, feature_id: str) -> tuple[int, dict]`
  - `handle_get_layer_explanation(self, feature_id: str, layer: str) -> tuple[int, dict]`
  - `handle_post_layer_explanation_generate(self, feature_id: str, layer: str) -> tuple[int, dict]`
  - `handle_get_structure(self) -> tuple[int, dict]`
  - `_run_l2_generate_job(self, job, feature_id: str, structure_json) -> None`（私有，背景執行緒，使用 `asyncio.run()` 呼叫 async `L2Generator.generate()`；捕捉 `ConfigError`/`L2GenerationError` 並呼叫 `fail_job()`）
  - `_run_layer_explanation_job(self, job, feature_id: str, layer: str) -> None`（私有，背景執行緒，使用 `asyncio.run()` 呼叫 async `llm_provider.complete()`；捕捉所有例外並呼叫 `fail_job()`）
- [x] 4.3 確認所有 unit tests 通過

## Task 5: Server 路由擴展

- [x] 5.1 在 `server.py` 的 `_API_ROUTES` 新增靜態 GET 端點：`"/api/l1": "GET"`, `"/api/structure": "GET"`
- [x] 5.2 在 `_handle_get()` 新增 elif 分支處理動態路徑：`/api/l2/<feature_id>`、`/api/layer-explanation/<feature_id>/<layer>`
- [x] 5.3 在 `_handle_post()` 新增 elif 分支處理動態路徑：`/api/l2/<feature_id>/generate`、`/api/layer-explanation/<feature_id>/<layer>/generate`（這兩個端點不需要解析 request body，所有參數從 URL 路徑解析）
- [x] 5.4 確認路由邏輯正確（path 解析、405 method not allowed 不影響現有端點）

## Task 6: Cytoscape.js 本地打包與前端基礎

- [x] 6.1 下載 `cytoscape.min.js` 並放置於 `docs/frontend-local-version-viewer/viewer/lib/cytoscape.min.js`
- [x] 6.2 在 `viewer/index.html` 的 `<head>` 新增 `<script src="./lib/cytoscape.min.js"></script>`（無 CDN 引用）
- [x] 6.3 在 `viewer/index.html` 新增 HTML 元素：`#breadcrumb`、`#graph-container`、`#mermaid-fallback`、`#layer-explanation`、`#diff-sort-toggle`
- [x] 6.4 確認 `viewer/index.html` 不含任何外部 domain 的 `<script src>` 或 `<link href>`

## Task 7: 前端 app.js 升級 — 圖形渲染核心

- [x] 7.1 在 `app.js` 新增 state 欄位：`layerState`、`selectedFeatureId`、`selectedModuleId`、`l1GraphViewModel`、`l2GraphViewModel`、`l3GraphViewModel`、`diffGraphViewModel`、`cytoscapeInstance`、`cytoscapeAvailable`、`diffSortMode`、`layerExplanation`
- [x] 7.2 實作 `initGraph(containerId, viewModel)` — 初始化 Cytoscape 實例，失敗時啟動 Mermaid fallback
- [x] 7.3 實作 `buildCytoscapeElements(viewModel)` — 將 ViewModel 轉換為 Cytoscape elements 格式
- [x] 7.4 實作 `buildCytoscapeStyle(layerState)` — 根據層級回傳 Cytoscape style 陣列（含節點顏色、confidence marker）
- [x] 7.5 實作 `renderMermaidFallback(viewModel, layerState)` — 生成 Mermaid 文字並顯示 fallback 訊息
- [x] 7.6 實作 `bindCytoscapeEvents(cy, layerState)` — 綁定節點點選事件，更新 Detail_Panel
- [x] 7.7 確認 `initGraph` 在空 ViewModel（零節點）時顯示 empty-state 訊息，不拋出例外（Req 13 AC6）

## Task 8: 前端 app.js 升級 — 層切換與 API 呼叫

- [x] 8.1 實作 `loadL1Graph()` — GET /api/l1，建立 L1_Graph_ViewModel，呼叫 `initGraph`
- [x] 8.2 實作 `switchToL2(featureId)` — 同時觸發兩個獨立 fetch：(1) GET /api/l2/<featureId> 取得 L2 圖形資料，(2) `loadLayerExplanation(featureId, "l2")` 取得說明快取；兩者互不阻塞（Req 4 AC9）；更新 Breadcrumb 和 Layer_State
- [x] 8.3 實作 `switchToL3(moduleId)` — 從 `state.l2GraphViewModel.nodes` 找到對應 module 的 `source_nodes`，GET /api/structure 取得 StructureJSON（JSON 格式），在前端 JS 中過濾節點（`node_id` 在 `source_nodes` 中）和邊（`from_node`/`to_node` 均在 `source_nodes` 中），建構 L3_Graph_ViewModel dict，呼叫 `initGraph`
- [x] 8.4 實作 `switchToL1()` — 切換回 L1，恢復選取狀態
- [x] 8.5 實作 `switchToL2FromL3()` — 切換回 L2，恢復選取狀態
- [x] 8.6 實作 `loadLayerExplanation(featureId, layer)` — GET /api/layer-explanation/<featureId>/<layer>（獨立於 L2 圖形資料 fetch）
- [x] 8.7 實作 `generateL2(featureId)` — POST /api/l2/<featureId>/generate，輪詢 GET /api/update/status/<job_id>
- [x] 8.8 實作 `generateLayerExplanation(featureId, layer)` — POST /api/layer-explanation/<featureId>/<layer>/generate，輪詢完成
- [x] 8.9 實作 `renderBreadcrumb()` — 根據 `state.layerState` 渲染 Breadcrumb 路徑
- [x] 8.10 實作 `renderFeatureList(viewModel, layerState)` — 渲染左側 Feature_List；L1 時顯示 feature 節點，L2 時顯示 module 節點，Diff_Mode 時顯示已排序的變更節點
- [x] 8.11 確認點選 Feature_List 項目時，Cytoscape 實例中對應節點被程式化選取（Req 3 AC4）

## Task 9: 前端 app.js 升級 — Detail Panel 與差異模式

- [x] 9.1 實作 `renderDetailPanelL1(node)` — 顯示 label、description、confidence、trigger_description、Enter L2 按鈕、Data source 欄位
- [x] 9.2 實作 `renderDetailPanelL2(node)` — 顯示 label、confidence、source_nodes 列表、Enter L3 按鈕、Expand Explanation 按鈕；anomalies 列表從 `state.l2GraphViewModel.anomalies` 讀取（非節點資料），顯示 anomaly_type 和 explanation（Req 6 AC4）
- [x] 9.3 實作 `renderDetailPanelL3(node)` — 顯示 label、type、file、Data source 欄位
- [x] 9.4 實作 `renderDetailPanelDiff(node)` — 顯示 change_type、current_label、baseline_label、risk_flags（無 Enter L2 按鈕）
- [x] 9.5 實作 `toggleDiffSort(mode)` — 切換 `state.diffSortMode`，重新渲染 Feature_List（client-side，不呼叫 API）
- [x] 9.6 實作 `applyDiffSort(nodes, mode)` — 根據 mode 排序 nodes，回傳新陣列
- [x] 9.7 確認 Diff_Mode 下 Detail_Panel 不顯示 Enter L2 按鈕（Req 9 AC4）
- [x] 9.8 確認 description 為 null 時顯示「未提供」（Req 14 AC5）

## Task 10: 前端 styles.css 升級

- [x] 10.1 新增 `#graph-container` 樣式（高度、邊框）
- [x] 10.2 新增 `.breadcrumb` 樣式
- [x] 10.3 新增 `.mermaid-fallback` 和 `.fallback-indicator` 樣式
- [x] 10.4 新增 `.confidence-high`、`.confidence-medium`、`.confidence-low` CSS class
- [x] 10.5 新增 `.diff-sort-toggle` 和 `.sort-button` 樣式
- [x] 10.6 新增 `.layer-explanation` 樣式

## Task 11: 整合驗收測試

- [x] 11.1 執行完整測試套件，確認所有既有測試仍通過（不破壞 Phase UI-2 的 402 tests）
- [x] 11.2 確認 `graph_view_model.py` 達到 100% 行覆蓋率
- [x] 11.3 確認 `l2_generator.py` 達到 ≥ 90% 行覆蓋率
- [x] 11.4 確認 `api_handlers.py` 新增方法達到 ≥ 90% 行覆蓋率
- [x] 11.5 確認 `viewer/index.html` 不含任何外部 CDN 引用（Req 1 AC1、Req 13 AC1）
- [x] 11.6 確認 `Static_Handler` 正確服務 `viewer/lib/cytoscape.min.js`（Content-Type: application/javascript）
