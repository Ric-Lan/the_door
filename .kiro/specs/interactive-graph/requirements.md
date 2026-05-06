# Requirements Document

## Introduction

Phase UI-3 Interactive Graph 是 The Door 前端工作台的第三個實作階段。

Phase UI-1 建立了靜態前端 viewer（HTML/CSS/Vanilla JS，讀取靜態 JSON ViewModels）。Phase UI-2 新增了 `the-door ui <project-path>` 指令與 7 個本地 API 端點，但 GraphCanvas 目前仍是無邊的節點格線（node grid），尚未使用 Cytoscape.js。

Phase UI-3 的目標是以 **Cytoscape.js（本地打包，不使用 CDN）** 取代現有 GraphCanvas 節點格線，實作完整的互動式圖形，並支援三層導覽（L1 → L2 → L3）、差異模式圖形、以及按需 LLM 說明生成。

本階段的核心設計原則：

- **No hallucination**：圖形層不得創造新的業務語意；所有節點、邊、標籤必須來自既有 core 模組輸出（L1Output、L2Output、StructureJSON、UpdateReport）。
- **Local-first**：Cytoscape.js 必須本地打包；LLM 說明只在使用者明確觸發且快取不存在時才呼叫。
- **Mermaid fallback**：若 Cytoscape.js 渲染失敗，必須退回 Mermaid 文字輸出，不得顯示空白畫面。
- **Layer-wide navigation**：層切換（L1→L2、L2→L3）是全畫布切換，不支援在 L1 視圖中只展開單一節點的 L2。
- **TDD first**：所有 ViewModel 轉換函式必須先有失敗測試，再實作。

---

## Glossary

- **Graph_Canvas**：前端中央畫布元件，Phase UI-3 後由 Cytoscape.js 驅動，取代原有節點格線。
- **Cytoscape_Instance**：在 `Graph_Canvas` 中初始化的 Cytoscape.js 實例，負責節點/邊渲染與互動事件。
- **L1_Graph_ViewModel**：從 `L1Output.features` 與 `L1Output.feature_relations` 轉換而來的圖形資料結構，包含節點列表與有向邊列表，供 `Cytoscape_Instance` 消費。
- **L2_Graph_ViewModel**：從 `L2Output.modules`、`L2Output.module_interactions`、`L2Output.anomalies` 轉換而來的圖形資料結構。
- **L3_Graph_ViewModel**：從 `StructureJSON` 的 source nodes（限定於選定功能的 `source_nodes`）轉換而來的圖形資料結構。
- **Diff_Graph_ViewModel**：從 `UpdateReport.l1_changes` 與 `DiffResult.edge_diffs` 轉換而來的差異圖形資料結構，僅包含有變更的節點與其間的有向邊。
- **Layer_State**：前端目前所在的層級，值為 `"L1"`、`"L2"`、`"L3"` 之一，以及當前選定的 `feature_id`（L2/L3 時必填）。
- **Detail_Panel**：右側詳情面板，顯示選定節點的詳細資訊。
- **Feature_List**：左側功能清單，列出當前層的所有節點，點選後同步選中 `Cytoscape_Instance` 中對應節點。
- **Breadcrumb**：頂部或 `Detail_Panel` 上方的層級導覽路徑，例如 `L1 > feature_name > L2`。
- **Layer_Explanation_Cache**：儲存在 `.the-door/layer-explanations/<feature_id>/<layer>.json` 的 LLM 生成說明快取。
- **L2_Store**：儲存在 `.the-door/l2-outputs/<feature_id>.json` 的 L2 分析結果快取，由 `POST /api/l2/<feature_id>/generate` 生成並持久化，由 `GET /api/l2/<feature_id>` 讀取。
- **API_Handler**：Phase UI-2 定義的後端 API 處理器，Phase UI-3 新增 6 個端點。
- **GraphViewModel_Converter**：Python 純函式模組，負責將 `L1Output`、`L2Output`、`StructureJSON`、`UpdateReport` 轉換為對應的 Graph ViewModel，必須有單元測試。
- **cose_layout**：Cytoscape.js 內建的 force-directed 佈局演算法（`layout: { name: 'cose' }`）。
- **Diff_Mode**：前端差異模式，僅顯示 L1 層級的變更節點與邊，不支援層切換。
- **Single_Version_Mode**：前端單版本模式，支援 L1→L2→L3 層切換。
- **Confidence_Marker**：節點上的信心標示視覺元素，對應 `Feature.confidence`（`"high"` / `"medium"` / `"low"`），沿用 Phase 0b 規範。
- **Job_ID**：`POST /api/l2/<feature_id>/generate` 或 `POST /api/layer-explanation/<feature_id>/<layer>/generate` 回傳的非同步任務識別碼。

---

## Requirements

### Requirement 1：Cytoscape.js 本地打包與初始化

**User Story：** As a developer, I want Cytoscape.js to be bundled locally without any CDN dependency, so that the viewer works in offline environments and does not make external network requests.

#### Acceptance Criteria

1. THE `Graph_Canvas` SHALL load Cytoscape.js from a local file (e.g., `viewer/lib/cytoscape.min.js`) without any CDN URL reference in HTML or JavaScript.
2. WHEN `Cytoscape_Instance` fails to initialize (e.g., due to a missing or corrupt local file), THE `Graph_Canvas` SHALL fall back to rendering the Mermaid text output for the current layer and display an error message identifying the failure reason.
3. THE `Graph_Canvas` SHALL initialize `Cytoscape_Instance` with the `cose_layout` as the default layout for all graph views.
4. THE `Graph_Canvas` SHALL NOT make any outbound network requests to hosts other than `127.0.0.1` or `localhost` during graph initialization or rendering.
5. WHEN the Mermaid fallback is active, THE `Graph_Canvas` SHALL display a visible indicator stating that the interactive graph is unavailable and showing the Mermaid diagram instead.

---

### Requirement 2：L1 Graph ViewModel 轉換

**User Story：** As a developer, I want a tested conversion function that transforms L1Output into a Cytoscape-compatible graph ViewModel, so that the graph layer never invents data and all nodes/edges are traceable to L1Output.

#### Acceptance Criteria

1. THE `GraphViewModel_Converter` SHALL provide a pure function `build_l1_graph_view_model(l1_output: L1Output) -> L1_Graph_ViewModel` that converts `L1Output.features` into graph nodes and `L1Output.feature_relations` into directed edges.
2. EACH node in `L1_Graph_ViewModel` SHALL contain: `id` (from `Feature.feature_id`), `label` (from `Feature.label`), `confidence` (from `Feature.confidence`), `description` (from `Feature.description`), `trigger_description` (from `Feature.trigger_description`). WHEN built from `VersionSnapshot.l1_snapshot` (via `GET /api/l1`), `trigger_description` SHALL be `null` (not present in `FeatureSummary`); the `Detail_Panel` SHALL display "未提供" per Requirement 14 AC5.
3. EACH directed edge in `L1_Graph_ViewModel` SHALL contain: `source` (from `FeatureRelation.from_feature`), `target` (from `FeatureRelation.to_feature`), `relation` (from `FeatureRelation.relation`).
4. IF a `FeatureRelation` references a `feature_id` not present in `L1Output.features`, THEN THE `GraphViewModel_Converter` SHALL omit that edge and record a warning, rather than raising an exception.
5. FOR ALL valid `L1Output` objects, `build_l1_graph_view_model` SHALL produce an `L1_Graph_ViewModel` where every node `id` is unique and every edge `source` and `target` references an existing node `id` in the same ViewModel.
6. THE `GraphViewModel_Converter` SHALL have unit tests covering: empty features list, empty feature_relations list, dangling edge references, and features with all three confidence levels.

---

### Requirement 3：L1 互動圖渲染

**User Story：** As a non-engineer, I want to see all L1 features as nodes with directed arrows showing their relationships, so that I can understand the functional structure of the codebase at a glance.

#### Acceptance Criteria

1. WHEN `Single_Version_Mode` is active and `Layer_State` is `"L1"`, THE `Graph_Canvas` SHALL render the `L1_Graph_ViewModel` using `Cytoscape_Instance` with nodes representing features and directed edges (with arrowheads) representing `feature_relations`.
2. EACH node SHALL display a `Confidence_Marker` visual indicator corresponding to `Feature.confidence`: a distinct visual style for `"high"`, `"medium"`, and `"low"` (following Phase 0b confidence marker conventions).
3. WHEN a node is clicked in `Cytoscape_Instance`, THE `Detail_Panel` SHALL display that feature's `label`, `description`, `confidence`, and `trigger_description` sourced from `L1_Graph_ViewModel`.
4. WHEN a feature is clicked in `Feature_List`, THE `Graph_Canvas` SHALL programmatically select the corresponding node in `Cytoscape_Instance` and THE `Detail_Panel` SHALL update to show that feature's details.
5. WHEN a node is selected, THE `Detail_Panel` SHALL display an "Enter L2" button.
6. THE `Graph_Canvas` SHALL apply node colors consistent with the existing diff vocabulary: `added` = green, `removed` = red, `attribute_changed` = orange, `dependency_changed` = yellow, `unchanged` = muted grey. In `Single_Version_Mode`, all nodes SHALL use the `unchanged` (muted grey) color style.
7. WHEN `L1_Graph_ViewModel` contains zero nodes, THE `Graph_Canvas` SHALL display an empty-state message rather than a blank canvas.

---

### Requirement 4：層切換 — L1 → L2

**User Story：** As a non-engineer, I want to click "Enter L2" to switch the entire canvas to the L2 technical view for a selected feature, so that I can drill into the module-level details without losing context.

#### Acceptance Criteria

1. WHEN the user clicks "Enter L2" in `Detail_Panel` while a feature is selected, THE `Graph_Canvas` SHALL switch the ENTIRE canvas to display L2 content for that feature; the L1 graph SHALL be replaced, not augmented.
2. WHEN switching to L2, THE `Graph_Canvas` SHALL first check if `L2_Graph_ViewModel` for the selected `feature_id` is available (via `GET /api/l2/<feature_id>`).
3. IF `GET /api/l2/<feature_id>` returns HTTP 200, THEN THE `Graph_Canvas` SHALL render the `L2_Graph_ViewModel` immediately without calling LLM.
4. IF `GET /api/l2/<feature_id>` returns HTTP 404, THEN THE `Graph_Canvas` SHALL display a "L2 not yet generated" state with a "Generate L2 Explanation" button; THE `Graph_Canvas` SHALL NOT call LLM automatically.
5. WHEN the user clicks "Generate L2 Explanation", THE `Graph_Canvas` SHALL POST to `/api/l2/<feature_id>/generate`, receive a `Job_ID`, and display a loading indicator while polling for completion.
6. WHEN L2 generation completes, THE `Graph_Canvas` SHALL fetch and render the `L2_Graph_ViewModel` without requiring a page reload.
7. THE `Breadcrumb` SHALL update to show `L1 > <feature_label> > L2` when `Layer_State` is `"L2"`.
8. THE `Layer_State` SHALL record the `feature_id` of the feature whose L2 is being viewed.
9. THE `Graph_Canvas` SHALL fetch `GET /api/layer-explanation/<feature_id>/l2` independently of the L2 graph data fetch; IF the explanation is available (HTTP 200), THE `Detail_Panel` SHALL display it; IF not available (HTTP 404), THE `Detail_Panel` SHALL show a "Generate L2 Explanation" prompt. These two fetches are independent and either may return 404 without blocking the other.

---

### Requirement 5：L2 Graph ViewModel 轉換

**User Story：** As a developer, I want a tested conversion function that transforms L2Output into a Cytoscape-compatible graph ViewModel, so that L2 graph nodes and edges are always traceable to L2Output.

#### Acceptance Criteria

1. THE `GraphViewModel_Converter` SHALL provide a pure function `build_l2_graph_view_model(l2_output: L2Output) -> L2_Graph_ViewModel` that converts `L2Output.modules` into graph nodes and `L2Output.module_interactions` into directed edges.
2. EACH node in `L2_Graph_ViewModel` SHALL contain: `id` (from `L2Module.module_id`), `label` (from `L2Module.label`), `confidence` (from `L2Module.confidence`), `source_nodes` (from `L2Module.source_nodes`).
3. EACH directed edge in `L2_Graph_ViewModel` SHALL contain: `source` (from `ModuleInteraction.from_module`), `target` (from `ModuleInteraction.to_module`), `description` (from `ModuleInteraction.description`), `relation_type` (from `ModuleInteraction.relation_type`).
4. THE `L2_Graph_ViewModel` SHALL include an `anomalies` list derived from `L2Output.anomalies`, where each entry contains `anomaly_type`, `affected_node_ids`, `explanation`, and `confidence`.
5. IF a `ModuleInteraction` references a `module_id` not present in `L2Output.modules`, THEN THE `GraphViewModel_Converter` SHALL omit that edge and record a warning.
6. FOR ALL valid `L2Output` objects, `build_l2_graph_view_model` SHALL produce an `L2_Graph_ViewModel` where every node `id` is unique and every edge `source` and `target` references an existing node `id`.
7. THE `GraphViewModel_Converter` SHALL have unit tests covering: empty modules list, anomalies with multiple affected nodes, and dangling interaction references.

---

### Requirement 6：L2 互動圖渲染

**User Story：** As a non-engineer, I want to see L2 modules as nodes with directed arrows showing their interactions, and anomalies highlighted, so that I can understand the technical structure of a feature.

#### Acceptance Criteria

1. WHEN `Layer_State` is `"L2"`, THE `Graph_Canvas` SHALL render the `L2_Graph_ViewModel` using `Cytoscape_Instance` with module nodes and directed interaction edges.
2. WHEN a module node is clicked, THE `Detail_Panel` SHALL display that module's `label`, `confidence`, and `source_nodes` list.
3. WHEN an anomaly exists in `L2_Graph_ViewModel`, THE `Graph_Canvas` SHALL visually distinguish affected nodes (e.g., with a warning border or icon) corresponding to `Anomaly.affected_node_ids`.
4. THE `Detail_Panel` SHALL display a list of anomalies for the current L2 view, each showing `anomaly_type` and `explanation`.
5. WHEN a module node is selected, THE `Detail_Panel` SHALL display an "Enter L3" button.
6. THE `Detail_Panel` SHALL display an "Expand Explanation" button for the selected module node. WHEN the user clicks "Expand Explanation", THE `Detail_Panel` SHALL display the cached `Layer_Explanation_Cache` content for the current `feature_id` and layer `"l2"` (fetched from `GET /api/layer-explanation/<feature_id>/l2`); IF no cache exists, THE `Detail_Panel` SHALL display a "Generate L2 Explanation" prompt. THE `Graph_Canvas` SHALL NOT trigger a new LLM call from this button.
7. WHEN the user clicks "Back to L1" in `Breadcrumb`, THE `Graph_Canvas` SHALL switch the ENTIRE canvas back to the L1 graph and restore the previously selected feature's selection state.
8. THE `Feature_List` SHALL update to show L2 module items when `Layer_State` is `"L2"`.

---

### Requirement 7：層切換 — L2 → L3

**User Story：** As a developer, I want to click "Enter L3" to switch the entire canvas to the L3 source node view for a selected module, so that I can inspect the specific source code nodes backing a module.

#### Acceptance Criteria

1. WHEN the user clicks "Enter L3" in `Detail_Panel` while an L2 module node is selected, THE `Graph_Canvas` SHALL switch the ENTIRE canvas to display L3 content for that module's `source_nodes`.
2. THE `L3_Graph_ViewModel` SHALL be built from the `StructureJSON` nodes whose `node_id` appears in the selected `L2Module.source_nodes` list; THE `GraphViewModel_Converter` SHALL NOT include AST nodes outside this list. THE `StructureJSON` SHALL be retrieved via `GET /api/structure` (Requirement 11 AC8); IF no `StructureJSON` is available, THE `Graph_Canvas` SHALL display an error state indicating that structure data must be regenerated.
3. EACH node in `L3_Graph_ViewModel` SHALL contain: `id` (from `ASTNode.node_id`), `label` (from `ASTNode.name`), `type` (from `ASTNode.type`), `file` (from `ASTNode.file`).
4. THE `L3_Graph_ViewModel` SHALL include directed edges derived from `StructureJSON.edges` where both `from_node` and `to_node` node_ids are present in the selected `L2Module.source_nodes` list; edges referencing nodes outside this list SHALL be omitted.
5. THE `Breadcrumb` SHALL update to show `L1 > <feature_label> > L2 > <module_label> > L3` when `Layer_State` is `"L3"`.
6. WHEN the user clicks "Back to L2" in `Breadcrumb`, THE `Graph_Canvas` SHALL switch the ENTIRE canvas back to the L2 graph and restore the previously selected module's selection state.
7. WHEN `L3_Graph_ViewModel` contains zero nodes (e.g., `source_nodes` is empty), THE `Graph_Canvas` SHALL display an empty-state message rather than a blank canvas.
8. THE `GraphViewModel_Converter` SHALL have unit tests covering: empty source_nodes list, source_nodes referencing non-existent AST nodes, and mixed node types (function, class, method).

---

### Requirement 8：LLM 說明快取與按需生成

**User Story：** As a non-engineer, I want layer explanations to be generated on demand and cached locally, so that I never wait for LLM calls I didn't ask for, and previously generated explanations load instantly.

#### Acceptance Criteria

1. WHEN switching to L2 for a `feature_id`, THE `Graph_Canvas` SHALL call `GET /api/layer-explanation/<feature_id>/l2` independently of the L2 graph data fetch; IF the response is HTTP 200, THE `Detail_Panel` SHALL display the cached explanation without calling LLM.
2. IF `GET /api/layer-explanation/<feature_id>/l2` returns HTTP 404, THEN THE `Detail_Panel` SHALL display a "L2 explanation not yet generated" state; THE `Graph_Canvas` SHALL NOT call LLM automatically.
3. WHEN the user clicks "Generate L2 Explanation", THE `Graph_Canvas` SHALL POST to `/api/layer-explanation/<feature_id>/l2/generate`, receive a `Job_ID`, and poll for completion before displaying the result.
4. WHEN the user clicks "Regenerate" in `Detail_Panel`, THE `Graph_Canvas` SHALL POST to `/api/layer-explanation/<feature_id>/<layer>/generate`, which SHALL overwrite the existing `Layer_Explanation_Cache` file and return the new explanation.
5. WHEN a `Layer_Explanation_Cache` file exists for a given `feature_id` and layer, THE `API_Handler` SHALL return it directly without calling LLM; THE `API_Handler` SHALL NOT regenerate unless the user explicitly triggers "Regenerate".
6. THE `Layer_Explanation_Cache` SHALL be stored at `.the-door/layer-explanations/<feature_id>/<layer>.json`; IF this file exists, THE `API_Handler` SHALL return HTTP 200 with its contents; IF it does not exist, THE `API_Handler` SHALL return HTTP 404.

---

### Requirement 9：差異模式圖形

**User Story：** As a non-engineer, I want to see changed features as colored nodes with directed arrows in diff mode, so that I can visually identify what changed between versions without switching layers.

#### Acceptance Criteria

1. WHEN `Diff_Mode` is active, THE `Graph_Canvas` SHALL render the `Diff_Graph_ViewModel` using `Cytoscape_Instance`, showing only nodes from `UpdateReport.l1_changes` and directed edges between changed nodes from `DiffResult.edge_diffs`.
2. EACH node in `Diff_Graph_ViewModel` SHALL be colored according to its `change_type` (from `L1ChangeEntry.change_type`): `added` = green, `removed` = red, `attribute_changed` = orange, `dependency_changed` = yellow.
3. THE `Diff_Graph_ViewModel` SHALL include directed edges (with arrowheads) only between nodes that are both present in the changed node set; edges to/from nodes not in `UpdateReport.l1_changes` SHALL be omitted.
4. WHEN `Diff_Mode` is active, THE `Detail_Panel` SHALL NOT display an "Enter L2" button; layer switching SHALL be disabled in diff mode.
5. THE `GraphViewModel_Converter` SHALL provide a pure function `build_diff_graph_view_model(update_report: dict, diff_result: dict | None) -> Diff_Graph_ViewModel` that derives nodes from `update_report["l1_changes"]` and edges from `diff_result["edge_diffs"]` (where `diff_result` is the parsed content of `UpdateReport.l3_appendix.diff_result_json`); IF `diff_result` is `None`, the ViewModel SHALL contain nodes only with no edges.
6. THE `GraphViewModel_Converter` SHALL have unit tests covering: all four `change_type` values (`added`, `removed`, `attribute_changed`, `dependency_changed`), empty `l1_changes`, and edges between nodes of different `change_type` values.

---

### Requirement 10：差異模式排序

**User Story：** As a non-engineer, I want to toggle between risk-first and semantic-diff-first sort orders in diff mode, so that I can prioritize the most critical or most semantically significant changes.

#### Acceptance Criteria

1. WHEN `Diff_Mode` is active, THE `Feature_List` SHALL display changed features in risk-first order by default, where entries with `"out_of_scope"` in `L1ChangeEntry.risk_flags` appear first, followed by entries with `"vulnerability"` in `risk_flags`, then `"semantic_drift"` in `risk_flags`, then by `L1ChangeEntry.change_type` in order: `added` → `attribute_changed` → `dependency_changed` → `removed`.
2. WHEN the user toggles to "Semantic-diff-first" sort, THE `Feature_List` SHALL re-order features by the magnitude of description and label changes (larger textual difference ranked higher), without reloading graph data.
3. THE sort order toggle SHALL NOT trigger any API calls or LLM calls; sorting SHALL be performed client-side on the already-loaded `Diff_Graph_ViewModel` data.
4. THE `GraphViewModel_Converter` SHALL expose a `sort_diff_nodes_by_semantic_diff(nodes: list) -> list` pure function that ranks nodes by description/label change magnitude; magnitude SHALL be calculated as the sum of character-level edit distance between `current_label` and `baseline_label` plus the edit distance between `current_description` and `baseline_description` (using Python's `difflib.SequenceMatcher` or equivalent); this function SHALL have unit tests with at least three nodes of varying change magnitude.
5. WHEN the user switches back to "Risk-first" sort, THE `Feature_List` SHALL restore the risk-first order without any API calls.

---

### Requirement 11：新增 API 端點

**User Story：** As a frontend developer, I want new API endpoints for L1 graph data, L2 data, structure data, and layer explanation management, so that the interactive graph can fetch and cache data without duplicating backend logic.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/l1`, THE `API_Handler` SHALL return HTTP 200 with a JSON body containing the `L1_Graph_ViewModel` derived from the most recent `VersionSnapshot` (using `SnapshotStore(project_root).get_latest()`); the ViewModel SHALL be built from `VersionSnapshot.l1_snapshot` (for nodes) and `VersionSnapshot.feature_relations_snapshot` (for edges); IF no snapshot exists, THE `API_Handler` SHALL return HTTP 404 with an `API_Error_Response` containing `"code": "no_l1_data"`.
2. WHEN a GET request is made to `/api/l2/<feature_id>` and L2 data exists for that feature, THE `API_Handler` SHALL return HTTP 200 with the `L2_Graph_ViewModel`; IF L2 data does not exist, THE `API_Handler` SHALL return HTTP 404 with an `API_Error_Response` containing `"code": "l2_not_generated"`. L2 data SHALL be read from `.the-door/l2-outputs/<feature_id>.json` (the `L2_Store`).
3. WHEN a POST request is made to `/api/l2/<feature_id>/generate`, THE `API_Handler` SHALL start an asynchronous job using the Phase UI-3 new `L2Generator` component (to be implemented in this phase), which takes the `feature_id` and the corresponding `StructureJSON` as input, calls the LLM to produce `L2Output`, and persists the result to `.the-door/l2-outputs/<feature_id>.json`; THE `API_Handler` SHALL return HTTP 202 with a JSON body containing `job_id`; THE `API_Handler` SHALL NOT block the HTTP server during LLM generation. IF a job is already running (shared `JobStore` with Phase UI-2), THE `API_Handler` SHALL return HTTP 409 with an `API_Error_Response` containing `"code": "job_already_running"`.
4. WHEN a GET request is made to `/api/layer-explanation/<feature_id>/<layer>` and the `Layer_Explanation_Cache` file exists, THE `API_Handler` SHALL return HTTP 200 with the cached JSON content; IF the file does not exist, THE `API_Handler` SHALL return HTTP 404 with an `API_Error_Response` containing `"code": "explanation_not_cached"`.
5. WHEN a POST request is made to `/api/layer-explanation/<feature_id>/<layer>/generate`, THE `API_Handler` SHALL start an asynchronous LLM generation job, overwrite any existing `Layer_Explanation_Cache` file upon completion, and return HTTP 202 with a `job_id`. IF a job is already running (shared `JobStore` with Phase UI-2 and `/api/l2/<feature_id>/generate`), THE `API_Handler` SHALL return HTTP 409 with an `API_Error_Response` containing `"code": "job_already_running"`.
6. THE `<layer>` path parameter in `/api/layer-explanation/<feature_id>/<layer>` SHALL accept only `"l1"`, `"l2"`, or `"l3"`; any other value SHALL return HTTP 400 with an `API_Error_Response` containing `"code": "invalid_layer"`.
7. IF an unexpected exception occurs in any new endpoint, THEN THE `API_Handler` SHALL return HTTP 500 with an `API_Error_Response` body following the unified error format defined in Phase UI-2 Requirement 10.
8. WHEN a GET request is made to `/api/structure`, THE `API_Handler` SHALL return HTTP 200 with the `StructureJSON` content read from `.the-door/structure.json`; IF the file does not exist, THE `API_Handler` SHALL return HTTP 404 with an `API_Error_Response` containing `"code": "no_structure_data"`. The `.the-door/structure.json` file is the persisted output of `the-door extract`; how and when it is written is a deployment concern outside this requirement's scope.

---

### Requirement 12：Graph ViewModel 轉換的屬性測試

**User Story：** As a developer, I want property-based tests for all graph ViewModel conversion functions, so that edge cases in arbitrary L1Output, L2Output, and UpdateReport inputs are systematically discovered.

#### Acceptance Criteria

1. FOR ALL valid `L1Output` objects generated by Hypothesis, `build_l1_graph_view_model` SHALL produce an `L1_Graph_ViewModel` where every edge `source` and `target` references an existing node `id` (no dangling edges in the output).
2. FOR ALL valid `L2Output` objects generated by Hypothesis, `build_l2_graph_view_model` SHALL produce an `L2_Graph_ViewModel` where every edge `source` and `target` references an existing node `id`.
3. FOR ALL valid `L1Output` objects generated by Hypothesis, the count of nodes in `L1_Graph_ViewModel` SHALL equal the count of `Feature` objects in `L1Output.features` (one-to-one mapping, no duplication).
4. FOR ALL valid `UpdateReport` dicts generated by Hypothesis, `build_diff_graph_view_model` SHALL produce a `Diff_Graph_ViewModel` where every node's `change_type` is one of `"added"`, `"removed"`, `"attribute_changed"`, `"dependency_changed"` (matching `L1ChangeEntry.change_type` values).
5. FOR ALL valid `L1_Graph_ViewModel` objects, applying `sort_diff_nodes_by_semantic_diff` twice SHALL produce the same result as applying it once (idempotent sort).

---

### Requirement 13：前端整合與無 CDN 約束

**User Story：** As a developer, I want the frontend to integrate Cytoscape.js without any CDN or build pipeline, so that the viewer remains a zero-dependency static HTML/CSS/JS application.

#### Acceptance Criteria

1. THE `Graph_Canvas` SHALL load Cytoscape.js exclusively from a local path (e.g., `viewer/lib/cytoscape.min.js`); THE `index.html` SHALL NOT contain any `<script src="...">` or `<link href="...">` pointing to an external domain.
2. THE viewer SHALL NOT require npm, webpack, Vite, TypeScript compilation, or any build step to function; opening `index.html` served by `UI_Server` SHALL be sufficient.
3. THE viewer SHALL NOT use React, TypeScript, or any UI component library; all DOM manipulation SHALL use Vanilla JavaScript.
4. WHEN `UI_Server` serves `viewer/lib/cytoscape.min.js`, THE `Static_Handler` SHALL serve it with `Content-Type: application/javascript; charset=utf-8`.
5. THE `Graph_Canvas` JavaScript module SHALL expose a `initGraph(containerId, viewModel)` function that initializes `Cytoscape_Instance` in the specified DOM container with the provided ViewModel data.
6. WHEN `initGraph` is called with an empty ViewModel (zero nodes), THE `Graph_Canvas` SHALL display an empty-state message in the container rather than throwing a JavaScript exception.

---

### Requirement 14：防幻覺與資料溯源

**User Story：** As a non-engineer, I want every node and edge in the graph to be traceable to a specific data source, so that I can trust that the visualization reflects actual analysis output and not invented content.

#### Acceptance Criteria

1. THE `Graph_Canvas` SHALL NOT display any node whose `id` does not correspond to a `feature_id` in `L1Output.features`, a `module_id` in `L2Output.modules`, or a `node_id` in `StructureJSON.nodes` (for L3).
2. THE `Graph_Canvas` SHALL NOT display any directed edge whose `source` or `target` does not correspond to an existing node in the current layer's ViewModel.
3. WHEN a node is selected, THE `Detail_Panel` SHALL display a "Data source" field identifying the originating data contract (e.g., `L1Output.features[feature_id=...]`, `L2Output.modules[module_id=...]`).
4. THE `GraphViewModel_Converter` SHALL NOT add, infer, or synthesize any field not present in the source data contract (`L1Output`, `L2Output`, `StructureJSON`, `UpdateReport`); if a field is absent, the ViewModel entry for that field SHALL be `null` or omitted.
5. IF `Detail_Panel` receives a ViewModel entry where `description` is `null` or absent, THEN THE `Detail_Panel` SHALL display "未提供" (not provided) rather than substituting another field's value.

