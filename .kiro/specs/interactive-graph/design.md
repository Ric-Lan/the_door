# Design Document — Phase UI-3: Interactive Graph

## Overview

Phase UI-3 Interactive Graph 是 The Door 前端工作台的第三個實作階段，在 Phase UI-2 的本地 API server 基礎上，以 **Cytoscape.js（本地打包）** 取代現有 GraphCanvas 節點格線，實作完整的互動式圖形。

**核心目標：**

1. **互動式圖形**：以 Cytoscape.js 渲染 L1/L2/L3 節點與有向邊，支援點選、縮放、拖曳。
2. **三層導覽**：L1（功能層）→ L2（模組層）→ L3（原始碼節點層），全畫布切換。
3. **差異模式圖形**：在 Diff_Mode 下顯示有顏色標示的變更節點與邊。
4. **按需 LLM 說明**：Layer Explanation 只在使用者明確觸發且快取不存在時才呼叫 LLM。
5. **防幻覺**：所有節點、邊、標籤必須來自既有 core 模組輸出，不得創造新語意。

**設計決策：**

| 決策 | 理由 |
|---|---|
| Cytoscape.js 本地打包（`viewer/lib/cytoscape.min.js`） | 離線環境可用；不依賴 CDN；符合 Req 1 AC1 |
| Mermaid 文字 fallback | Cytoscape 初始化失敗時不顯示空白畫面；符合 Req 1 AC2 |
| `GraphViewModel_Converter` 純函式模組（Python） | 可測試性；所有轉換邏輯集中在一處；符合 TDD 原則 |
| `L2Generator` 獨立模組 | 與 API handler 解耦；可單獨測試 LLM 呼叫邏輯 |
| 共用 `JobStore`（Phase UI-2 + UI-3） | 至多一個並發 job 的約束延伸到所有非同步操作 |
| Layer-wide 切換（不支援單節點展開） | 避免混合層級的視覺複雜度；符合 Req 4 AC1 |
| `difflib.SequenceMatcher` 計算語意差異 | Python 標準函式庫；不新增依賴；符合 Req 10 AC4 |
| `.the-door/` 目錄儲存 L2 與 Layer Explanation 快取 | 與既有 snapshot/doubt 儲存模式一致 |

---

## Architecture

### 高層資料流

```
the-door ui <project-path>
        │
        ▼
UIServer (core/ui/server.py) — 擴展路由
        │
        ├── GET  /api/l1                              → APIHandlers.handle_get_l1()
        ├── GET  /api/l2/<feature_id>                 → APIHandlers.handle_get_l2()
        ├── POST /api/l2/<feature_id>/generate        → APIHandlers.handle_post_l2_generate()
        ├── GET  /api/layer-explanation/<fid>/<layer> → APIHandlers.handle_get_layer_explanation()
        ├── POST /api/layer-explanation/<fid>/<layer>/generate → APIHandlers.handle_post_layer_explanation_generate()
        └── GET  /api/structure                       → APIHandlers.handle_get_structure()
        │
        ▼
GraphViewModel_Converter (core/ui/graph_view_model.py)
        │  純函式：build_l1_graph_view_model()
        │           build_l2_graph_view_model()
        │           build_l3_graph_view_model()
        │           build_diff_graph_view_model()
        │           sort_diff_nodes_by_semantic_diff()
        ▼
L2Generator (core/ui/l2_generator.py)
        │  async generate(feature_id, structure_json) -> L2Output
        │  持久化到 .the-door/l2-outputs/<feature_id>.json
        ▼
前端 viewer (docs/frontend-local-version-viewer/viewer/)
        │  app.js — 升級：Cytoscape 渲染、層切換、API 呼叫
        │  index.html — 升級：引用 lib/cytoscape.min.js
        │  styles.css — 升級：圖形樣式
        └── lib/cytoscape.min.js — 新增（本地打包）
```

### 模組邊界

| 模組 | 套件 | 職責 | 類別 |
|---|---|---|---|
| `graph_view_model.py` | `core/ui/` | ViewModel 轉換純函式 | 新建（C 類） |
| `l2_generator.py` | `core/ui/` | L2Output LLM 生成與持久化 | 新建（C 類） |
| `api_handlers.py` | `core/ui/` | 新增 6 個 handler 方法 | 擴展（B 類） |
| `server.py` | `core/ui/` | 擴展路由（新增 elif 分支） | 擴展（B 類） |
| `viewer/app.js` | `viewer/` | 升級：Cytoscape 渲染、層切換 | 升級（C 類） |
| `viewer/index.html` | `viewer/` | 升級：引用本地 Cytoscape | 升級（C 類） |
| `viewer/styles.css` | `viewer/` | 升級：圖形樣式 | 升級（C 類） |
| `viewer/lib/cytoscape.min.js` | `viewer/lib/` | Cytoscape.js 本地打包 | 新建（C 類） |

### 擴展後的資料夾結構

```
the_door/src/the_door/
└── core/ui/
    ├── api_handlers.py        # 擴展：新增 6 個 handler 方法
    ├── server.py              # 擴展：新增路由分支
    ├── graph_view_model.py    # NEW — ViewModel 轉換純函式
    └── l2_generator.py        # NEW — L2Output LLM 生成

docs/frontend-local-version-viewer/viewer/
    ├── app.js                 # 升級：Cytoscape 渲染、層切換
    ├── index.html             # 升級：引用 lib/cytoscape.min.js
    ├── styles.css             # 升級：圖形樣式
    └── lib/
        └── cytoscape.min.js   # NEW — 本地打包

.the-door/                     # 執行時資料目錄
    ├── l2-outputs/
    │   └── <feature_id>.json  # L2Output 快取
    ├── layer-explanations/
    │   └── <feature_id>/
    │       └── <layer>.json   # Layer Explanation 快取
    └── structure.json         # StructureJSON（由 the-door extract -o 產生）

the_door/tests/
├── unit/core/ui/
│   ├── test_graph_view_model.py   # NEW
│   └── test_l2_generator.py       # NEW
└── property/
    └── test_graph_view_model_properties.py  # NEW（Req 12 PBT）
```

---

## Components and Interfaces

### `core/ui/graph_view_model.py` — GraphViewModel_Converter

純函式模組，無狀態，無副作用。所有函式可直接單元測試。

```python
from __future__ import annotations
import difflib
from the_door.models import L1Output, L2Output, StructureJSON

# ── ViewModel TypedDicts（僅用於型別標注，不建立 dataclass）──

# L1_Graph_ViewModel:
# {
#   "nodes": [{"id": str, "label": str, "confidence": str,
#              "description": str, "trigger_description": str | None}],
#   "edges": [{"source": str, "target": str, "relation": str}],
#   "warnings": [str]
# }

# L2_Graph_ViewModel:
# {
#   "nodes": [{"id": str, "label": str, "confidence": str, "source_nodes": list[str]}],
#   "edges": [{"source": str, "target": str, "description": str, "relation_type": str}],
#   "anomalies": [{"anomaly_type": str, "affected_node_ids": list[str],
#                  "explanation": str, "confidence": str}],
#   "warnings": [str]
# }

# L3_Graph_ViewModel:
# {
#   "nodes": [{"id": str, "label": str, "type": str, "file": str}],
#   "edges": [{"source": str, "target": str, "type": str}],
#   "warnings": [str]
# }

# Diff_Graph_ViewModel:
# {
#   "nodes": [{"id": str, "label": str, "change_type": str,
#              "current_label": str | None, "baseline_label": str | None,
#              "current_description": str | None, "baseline_description": str | None,
#              "risk_flags": list[str]}],
#   "edges": [{"source": str, "target": str, "diff_state": str}],
#   "warnings": [str]
# }


def build_l1_graph_view_model(l1_output: L1Output) -> dict:
    """Convert L1Output to L1_Graph_ViewModel.

    - Nodes: one per Feature in l1_output.features
    - Edges: one per FeatureRelation in l1_output.feature_relations
    - Dangling edges (referencing unknown feature_id) are omitted; warning recorded.
    - trigger_description comes from Feature.trigger_description (not in FeatureSummary).

    Returns dict with keys: nodes, edges, warnings.
    """
    ...


def build_l1_graph_view_model_from_snapshot(
    l1_snapshot: dict,  # dict[str, FeatureSummary]
    feature_relations_snapshot: list,  # list[RelationSummary]
) -> dict:
    """Convert VersionSnapshot fields to L1_Graph_ViewModel.

    Used by GET /api/l1 which reads from VersionSnapshot (not L1Output).
    trigger_description is always null (not present in FeatureSummary).

    Returns dict with keys: nodes, edges, warnings.
    """
    ...


def build_l2_graph_view_model(l2_output: L2Output) -> dict:
    """Convert L2Output to L2_Graph_ViewModel.

    - Nodes: one per L2Module in l2_output.modules
    - Edges: one per ModuleInteraction in l2_output.module_interactions
    - Anomalies: all entries from l2_output.anomalies
    - Dangling interactions (referencing unknown module_id) are omitted; warning recorded.

    Returns dict with keys: nodes, edges, anomalies, warnings.
    """
    ...


def build_l3_graph_view_model(
    structure_json: StructureJSON,
    source_node_ids: list[str],
) -> dict:
    """Convert StructureJSON to L3_Graph_ViewModel filtered to source_node_ids.

    - Nodes: ASTNode entries whose node_id is in source_node_ids
    - Edges: Edge entries where both from_node and to_node are in source_node_ids
    - AST nodes not in source_node_ids are excluded.
    - Edges referencing nodes outside source_node_ids are excluded.

    Returns dict with keys: nodes, edges, warnings.
    """
    ...


def build_diff_graph_view_model(
    update_report: dict,
    diff_result: dict | None,
) -> dict:
    """Convert UpdateReport dict + DiffResult dict to Diff_Graph_ViewModel.

    - Nodes: derived from update_report["l1_changes"], pre-sorted by risk-first order
             (calls sort_diff_nodes_by_risk internally; Req 10 AC1 default sort)
    - Edges: derived from diff_result["edge_diffs"] where both from_node and to_node
             are present in the changed node set; if diff_result is None, no edges.
    - change_type values: "added" | "removed" | "attribute_changed" | "dependency_changed"

    Returns dict with keys: nodes (risk-first sorted), edges, warnings.
    """
    ...


def sort_diff_nodes_by_risk(nodes: list[dict]) -> list[dict]:
    """Sort diff nodes by risk-first order (pure function, no mutation).

    Order: out_of_scope → vulnerability → semantic_drift → added →
           attribute_changed → dependency_changed → removed.
    Nodes without risk_flags are sorted by change_type only.

    Called by build_diff_graph_view_model to pre-sort nodes in the returned
    Diff_Graph_ViewModel (default sort order per Req 10 AC1).
    Frontend only needs to re-sort when user switches to semantic-diff-first.

    Returns a new sorted list (does not mutate input).
    """
    ...


def sort_diff_nodes_by_semantic_diff(nodes: list[dict]) -> list[dict]:
    """Sort diff nodes by semantic change magnitude (pure function, no mutation).

    Magnitude = edit_distance(current_label, baseline_label)
              + edit_distance(current_description, baseline_description)
    Edit distance uses difflib.SequenceMatcher ratio converted to character count.
    Nodes with higher magnitude rank first.

    Returns a new sorted list (does not mutate input).
    """
    ...


def _edit_distance(a: str | None, b: str | None) -> int:
    """Compute character-level edit distance between two strings.

    Uses difflib.SequenceMatcher: distance = (1 - ratio) * (len(a) + len(b)).
    None is treated as empty string.
    """
    ...
```

**設計決策：**
- 所有函式回傳 `dict`（而非 dataclass），因為 JSON 序列化不需要額外轉換步驟。
- `warnings` 欄位記錄被省略的邊，供前端 console 顯示，不影響渲染。
- `build_l1_graph_view_model_from_snapshot` 與 `build_l1_graph_view_model` 分開，因為 `VersionSnapshot` 的 `FeatureSummary` 沒有 `trigger_description`，需要明確區分兩個資料來源。

---

### `core/ui/l2_generator.py` — L2Generator

```python
from __future__ import annotations
import json
from pathlib import Path
from the_door.core.llm.provider import LLMProvider
from the_door.models import L2Output, StructureJSON


class L2GenerationError(Exception):
    """Raised when L2 generation fails (LLM error or parse error)."""
    pass


class L2Generator:
    """Generate L2Output for a feature using LLM, then persist to disk.

    Responsibilities:
    - Build prompt from feature_id + relevant StructureJSON nodes
    - Call LLMProvider.complete()
    - Parse LLM response into L2Output
    - Persist to .the-door/l2-outputs/<feature_id>.json

    Does NOT manage job state — that is the caller's responsibility.
    """

    def __init__(self, project_root: Path, llm_provider: LLMProvider) -> None:
        self._project_root = project_root
        self._llm_provider = llm_provider

    async def generate(
        self,
        feature_id: str,
        structure_json: StructureJSON,
    ) -> L2Output:
        """Generate L2Output for the given feature.

        Steps:
        1. Build prompt from feature_id + full StructureJSON
           (LLM identifies relevant nodes by feature_id context)
        2. Call LLMProvider.complete()
        3. Parse response into L2Output
        4. Persist to .the-door/l2-outputs/<feature_id>.json
        5. Return L2Output

        Raises L2GenerationError on LLM failure or parse failure.
        """
        ...

    def _build_prompt(
        self,
        feature_id: str,
        structure_json: StructureJSON,
    ) -> str:
        """Build LLM prompt for L2 generation.

        Prompt includes feature_id and full StructureJSON (nodes + edges + topology).
        Instructs LLM to identify modules, interactions, and anomalies for the feature.
        Returns prompt string.
        """
        ...

    def _parse_response(self, raw: str) -> L2Output:
        """Parse LLM response JSON into L2Output.

        Raises L2GenerationError if JSON is invalid or required fields are missing.
        """
        ...

    def _persist(self, feature_id: str, l2_output: L2Output) -> None:
        """Persist L2Output to .the-door/l2-outputs/<feature_id>.json."""
        ...

    @staticmethod
    def load(project_root: Path, feature_id: str) -> L2Output | None:
        """Load persisted L2Output from disk. Returns None if not found."""
        ...
```

**設計決策：**
- `L2Generator` 是 async，因為 `LLMProvider.complete()` 是 async。
- `load()` 是 staticmethod，供 API handler 直接讀取快取，不需要實例化 generator。
- Prompt 建構邏輯封裝在 `_build_prompt()`，可單獨測試。

---

### `core/ui/api_handlers.py` — 新增 6 個 handler 方法

在現有 `APIHandlers` class 中新增以下方法（不修改現有 7 個方法）：

```python
def handle_get_l1(self) -> tuple[int, dict]:
    """GET /api/l1
    讀取最新 VersionSnapshot，轉換為 L1_Graph_ViewModel。
    使用 build_l1_graph_view_model_from_snapshot(snapshot.l1_snapshot,
                                                  snapshot.feature_relations_snapshot)。
    無 snapshot → 404 code:"no_l1_data"。
    例外 → 500。
    """
    ...

def handle_get_l2(self, feature_id: str) -> tuple[int, dict]:
    """GET /api/l2/<feature_id>
    讀取 .the-door/l2-outputs/<feature_id>.json。
    存在 → 200 + L2_Graph_ViewModel（使用 build_l2_graph_view_model）。
    不存在 → 404 code:"l2_not_generated"。
    例外 → 500。
    """
    ...

def handle_post_l2_generate(self, feature_id: str) -> tuple[int, dict]:
    """POST /api/l2/<feature_id>/generate
    不需要 request body（feature_id 從 URL 路徑解析）。
    1. 讀取 .the-door/structure.json（不存在 → 404 code:"no_structure_data"）
    2. try_create_job()（已有 running job → 409 code:"job_already_running"）
    3. 啟動背景執行緒（同步函式）：
       a. ConfigManager.load() + create_provider(config) 建立 LLMProvider
          （ConfigError → fail_job()）
       b. asyncio.run(L2Generator(project_root, llm_provider).generate(feature_id, structure_json))
          （與 analyze_pipeline.py 的 asyncio.run(reader.read()) 模式一致）
       c. 完成後 complete_job()；失敗後 fail_job()
    4. 回傳 202 {job_id}

    注意：source_node_ids 不從 VersionSnapshot 取得（FeatureSummary 無此欄位）。
    L2Generator 接收完整 StructureJSON，由 LLM 根據 feature_id 識別相關節點。
    """
    ...

def handle_get_layer_explanation(
    self, feature_id: str, layer: str
) -> tuple[int, dict]:
    """GET /api/layer-explanation/<feature_id>/<layer>
    layer 驗證：只接受 "l1" | "l2" | "l3"，否則 400 code:"invalid_layer"。
    讀取 .the-door/layer-explanations/<feature_id>/<layer>.json。
    存在 → 200 + JSON 內容。
    不存在 → 404 code:"explanation_not_cached"。
    例外 → 500。
    """
    ...

def handle_post_layer_explanation_generate(
    self, feature_id: str, layer: str
) -> tuple[int, dict]:
    """POST /api/layer-explanation/<feature_id>/<layer>/generate
    不需要 request body（feature_id 和 layer 從 URL 路徑解析）。
    layer 驗證：只接受 "l1" | "l2" | "l3"，否則 400 code:"invalid_layer"。
    try_create_job()（已有 running job → 409 code:"job_already_running"）。
    啟動背景執行緒：_run_layer_explanation_job() → 覆寫快取檔案 → complete_job()。
    回傳 202 {job_id}。
    """
    ...

def handle_get_structure(self) -> tuple[int, dict]:
    """GET /api/structure
    讀取 .the-door/structure.json。
    存在 → 200 + JSON 內容。
    不存在 → 404 code:"no_structure_data"。
    例外 → 500。
    """
    ...
```

**Layer Explanation 生成邏輯（背景執行緒）：**

```python
def _run_layer_explanation_job(
    self, job: UpdateJob, feature_id: str, layer: str
) -> None:
    """背景執行緒（同步函式）：
    1. ConfigManager.load() + create_provider(config) 建立 LLMProvider
       （ConfigError → fail_job()，不讓例外靜默失敗）
    2. 讀取對應快取資料（layer == "l2" 時讀取 L2Output；layer == "l1" 時讀取 L1 snapshot）
    3. 建構 prompt（包含 feature_id、layer、相關資料摘要）
    4. asyncio.run(llm_provider.complete(prompt))
       （LLMProvider.complete() 是 async，與 analyze_pipeline.py 的 asyncio.run() 模式一致）
    5. 覆寫 .the-door/layer-explanations/<feature_id>/<layer>.json
       格式：{"feature_id": ..., "layer": ..., "explanation": ..., "generated_at": ISO8601}
    6. complete_job() 或 fail_job()

    所有例外（ConfigError、LLMCallError、IOError）均捕捉並呼叫 fail_job()。
    """
    ...
```

---

### `core/ui/server.py` — 擴展路由

在 `_API_ROUTES` 字典新增新端點，並在 `_handle_get()` 和 `_handle_post()` 中新增 `elif` 分支（不修改現有分支）：

```python
# 新增到 _API_ROUTES（GET 端點）
"/api/l1": "GET",
"/api/structure": "GET",

# _handle_get() 新增 elif 分支（在現有 elif 之後）：
elif path == "/api/l1":
    status, body = api_handlers.handle_get_l1()
elif path == "/api/structure":
    status, body = api_handlers.handle_get_structure()
elif path.startswith("/api/l2/") and not path.endswith("/generate"):
    # GET /api/l2/<feature_id>
    feature_id = path[len("/api/l2/"):]
    status, body = api_handlers.handle_get_l2(feature_id)
elif path.startswith("/api/layer-explanation/") and not path.endswith("/generate"):
    # GET /api/layer-explanation/<feature_id>/<layer>
    parts = path[len("/api/layer-explanation/"):].split("/")
    if len(parts) == 2:
        status, body = api_handlers.handle_get_layer_explanation(parts[0], parts[1])
    else:
        _send_api_error(handler, 400, "invalid_path", "Invalid path", path)
        return

# _handle_post() 新增 elif 分支：
# 注意：以下兩個 POST 端點不需要解析 request body（所有參數在 URL 中）
elif path.startswith("/api/l2/") and path.endswith("/generate"):
    # POST /api/l2/<feature_id>/generate（無 request body）
    feature_id = path[len("/api/l2/"):-len("/generate")]
    status, body = api_handlers.handle_post_l2_generate(feature_id)
elif path.startswith("/api/layer-explanation/") and path.endswith("/generate"):
    # POST /api/layer-explanation/<feature_id>/<layer>/generate
    inner = path[len("/api/layer-explanation/"):-len("/generate")]
    parts = inner.split("/")
    if len(parts) == 2:
        status, body = api_handlers.handle_post_layer_explanation_generate(parts[0], parts[1])
    else:
        _send_api_error(handler, 400, "invalid_path", "Invalid path", path)
        return
```

---

### 前端 — `viewer/app.js` 升級

Phase UI-3 在現有 `app.js` 基礎上新增以下功能模組（不刪除現有功能）：

#### 新增狀態欄位

```javascript
const state = {
  // ... 現有欄位 ...

  /** @type {"L1"|"L2"|"L3"} 當前層級 */
  layerState: "L1",
  /** @type {string|null} 當前選定的 feature_id（L2/L3 時必填） */
  selectedFeatureId: null,
  /** @type {string|null} 當前選定的 module_id（L3 時必填） */
  selectedModuleId: null,
  /** @type {object|null} L1_Graph_ViewModel */
  l1GraphViewModel: null,
  /** @type {object|null} L2_Graph_ViewModel */
  l2GraphViewModel: null,
  /** @type {object|null} L3_Graph_ViewModel */
  l3GraphViewModel: null,
  /** @type {object|null} Diff_Graph_ViewModel */
  diffGraphViewModel: null,
  /** @type {cytoscape.Core|null} Cytoscape 實例 */
  cytoscapeInstance: null,
  /** @type {boolean} Cytoscape 是否可用 */
  cytoscapeAvailable: false,
  /** @type {"risk-first"|"semantic-diff-first"} 差異排序模式 */
  diffSortMode: "risk-first",
  /** @type {string|null} 當前 layer explanation 快取內容 */
  layerExplanation: null,
};
```

#### 新增 JavaScript 函式

| 函式 | 職責 |
|---|---|
| `initGraph(containerId, viewModel)` | 初始化 Cytoscape 實例（layerState 從 state 讀取）；失敗時啟動 Mermaid fallback |
| `renderCytoscapeGraph(viewModel, layerState)` | 以 Cytoscape 渲染節點與邊 |
| `renderMermaidFallback(viewModel, layerState)` | 生成 Mermaid 文字並顯示 fallback 訊息 |
| `switchToL2(featureId)` | 切換到 L2 層：GET /api/l2/<featureId>，處理 404 |
| `switchToL3(moduleId)` | 切換到 L3 層：GET /api/structure，過濾 source_nodes |
| `switchToL1()` | 切換回 L1 層，恢復選取狀態 |
| `switchToL2FromL3()` | 切換回 L2 層，恢復選取狀態 |
| `loadL1Graph()` | GET /api/l1，建立 L1_Graph_ViewModel |
| `loadL2Graph(featureId)` | GET /api/l2/<featureId> |
| `loadLayerExplanation(featureId, layer)` | GET /api/layer-explanation/<featureId>/<layer> |
| `generateL2(featureId)` | POST /api/l2/<featureId>/generate，輪詢完成 |
| `generateLayerExplanation(featureId, layer)` | POST /api/layer-explanation/<featureId>/<layer>/generate，輪詢完成 |
| `renderBreadcrumb()` | 根據 layerState 渲染 Breadcrumb |
| `renderDetailPanelL1(node)` | 渲染 L1 節點詳情（含 Enter L2 按鈕） |
| `renderDetailPanelL2(node)` | 渲染 L2 節點詳情（含 Enter L3、Expand Explanation 按鈕） |
| `renderDetailPanelL3(node)` | 渲染 L3 節點詳情 |
| `renderDetailPanelDiff(node)` | 渲染 Diff 節點詳情（無 Enter L2 按鈕） |
| `toggleDiffSort(mode)` | 切換差異排序模式（client-side，不呼叫 API） |
| `applyDiffSort(nodes, mode)` | 對 nodes 套用排序，回傳新陣列 |
| `getNodeColor(changeType)` | 回傳對應 CSS class 名稱 |
| `getConfidenceClass(confidence)` | 回傳對應 CSS class 名稱 |

#### Cytoscape 初始化規格

```javascript
function initGraph(containerId, viewModel) {
  // layerState is read from state.layerState (not passed as parameter, per Req 13 AC5)
  if (typeof cytoscape === "undefined") {
    // Cytoscape.js 未載入 — 啟動 Mermaid fallback
    renderMermaidFallback(viewModel, state.layerState);
    return;
  }
  try {
    const cy = cytoscape({
      container: document.getElementById(containerId),
      elements: buildCytoscapeElements(viewModel),
      style: buildCytoscapeStyle(state.layerState),
      layout: { name: "cose" },
    });
    state.cytoscapeInstance = cy;
    state.cytoscapeAvailable = true;
    bindCytoscapeEvents(cy, state.layerState);
  } catch (err) {
    // 初始化失敗 — 啟動 Mermaid fallback
    renderMermaidFallback(viewModel, state.layerState);
    showFallbackIndicator(err.message);
  }
}
```

#### 節點顏色規格（Cytoscape style）

| change_type / 狀態 | 顏色 |
|---|---|
| `added` | `#28a745`（綠） |
| `removed` | `#dc3545`（紅） |
| `attribute_changed` | `#fd7e14`（橙） |
| `dependency_changed` | `#ffc107`（黃） |
| `unchanged`（Single_Version_Mode） | `#adb5bd`（灰） |

#### Confidence Marker 規格

| confidence | CSS class | 視覺效果 |
|---|---|---|
| `high` | `confidence-high` | 實線邊框（accent 色） |
| `medium` | `confidence-medium` | 虛線邊框（muted 色） |
| `low` | `confidence-low` | 點線邊框（warn 色） |

---

### `viewer/index.html` 升級

新增以下元素（不刪除現有元素）：

```html
<!-- 在 <head> 中新增 -->
<script src="./lib/cytoscape.min.js"></script>

<!-- 在 .canvas section 中新增 -->
<div id="breadcrumb" class="breadcrumb" aria-label="layer navigation"></div>
<div id="graph-container" class="graph-container" aria-label="interactive graph"></div>
<div id="mermaid-fallback" class="mermaid-fallback" hidden>
  <div class="fallback-indicator">互動式圖形不可用，顯示文字圖形</div>
  <pre id="mermaid-output" class="mermaid-output"></pre>
</div>

<!-- 在 .detail-panel 中新增 -->
<div id="layer-explanation" class="layer-explanation" hidden></div>
<div id="diff-sort-toggle" class="diff-sort-toggle" hidden>
  <button id="btn-sort-risk" class="sort-button active" type="button">風險優先</button>
  <button id="btn-sort-semantic" class="sort-button" type="button">語意差異優先</button>
</div>
```

---

## Data Models

Phase UI-3 不新增任何 `models.py` dataclass。所有 ViewModel 以 `dict` 表示（JSON-native），定義在 `graph_view_model.py` 的 docstring 中。

### L1_Graph_ViewModel（dict 格式）

```json
{
  "nodes": [
    {
      "id": "feature_id",
      "label": "Feature Label",
      "confidence": "high",
      "description": "Feature description",
      "trigger_description": "Trigger description or null"
    }
  ],
  "edges": [
    {
      "source": "from_feature_id",
      "target": "to_feature_id",
      "relation": "relation text"
    }
  ],
  "warnings": ["Dangling edge omitted: from=X to=Y"]
}
```

**資料來源：**
- 從 `L1Output`：`Feature.feature_id`, `Feature.label`, `Feature.confidence`, `Feature.description`, `Feature.trigger_description`；`FeatureRelation.from_feature`, `FeatureRelation.to_feature`, `FeatureRelation.relation`
- 從 `VersionSnapshot`（via GET /api/l1）：`FeatureSummary.feature_id`, `FeatureSummary.label`, `FeatureSummary.confidence`, `FeatureSummary.description`；`trigger_description` 為 `null`（FeatureSummary 無此欄位）；`RelationSummary.from_feature`, `RelationSummary.to_feature`, `RelationSummary.relation`

### L2_Graph_ViewModel（dict 格式）

```json
{
  "nodes": [
    {
      "id": "module_id",
      "label": "Module Label",
      "confidence": "medium",
      "source_nodes": ["node_id_1", "node_id_2"]
    }
  ],
  "edges": [
    {
      "source": "from_module_id",
      "target": "to_module_id",
      "description": "interaction description",
      "relation_type": "static"
    }
  ],
  "anomalies": [
    {
      "anomaly_type": "dead_code",
      "affected_node_ids": ["node_id_1"],
      "explanation": "explanation text",
      "confidence": "medium"
    }
  ],
  "warnings": []
}
```

**資料來源：** `L2Module.module_id`, `L2Module.label`, `L2Module.confidence`, `L2Module.source_nodes`；`ModuleInteraction.from_module`, `ModuleInteraction.to_module`, `ModuleInteraction.description`, `ModuleInteraction.relation_type`；`Anomaly.anomaly_type`, `Anomaly.affected_node_ids`, `Anomaly.explanation`, `Anomaly.confidence`

### L3_Graph_ViewModel（dict 格式）

```json
{
  "nodes": [
    {
      "id": "node_id",
      "label": "function_name",
      "type": "function",
      "file": "path/to/file.py"
    }
  ],
  "edges": [
    {
      "source": "from_node_id",
      "target": "to_node_id",
      "type": "calls"
    }
  ],
  "warnings": []
}
```

**資料來源：** `ASTNode.node_id`, `ASTNode.name`, `ASTNode.type`, `ASTNode.file`；`Edge.from_node`, `Edge.to_node`, `Edge.type`（注意：`Edge` 使用 `from_node`/`to_node`，不是 `from`/`to`）

### Diff_Graph_ViewModel（dict 格式）

```json
{
  "nodes": [
    {
      "id": "feature_id",
      "label": "current_label or baseline_label",
      "change_type": "added",
      "current_label": "New Label",
      "baseline_label": null,
      "current_description": "New description",
      "baseline_description": null,
      "risk_flags": ["out_of_scope"]
    }
  ],
  "edges": [
    {
      "source": "from_node",
      "target": "to_node",
      "diff_state": "added"
    }
  ],
  "warnings": []
}
```

**資料來源：** `L1ChangeEntry.feature_id`, `L1ChangeEntry.change_type`, `L1ChangeEntry.current_label`, `L1ChangeEntry.baseline_label`, `L1ChangeEntry.risk_flags`；`EdgeDiff.from_node`, `EdgeDiff.to_node`, `EdgeDiff.diff_state`（序列化格式：`{"from_node": ..., "to_node": ..., "diff_state": ...}`）

### Layer Explanation Cache（JSON 格式）

```json
{
  "feature_id": "feature_id",
  "layer": "l2",
  "explanation": "LLM generated explanation text",
  "generated_at": "2024-01-01T00:00:00Z"
}
```

儲存路徑：`.the-door/layer-explanations/<feature_id>/<layer>.json`

### L2 Output Cache（JSON 格式）

L2Output 序列化為 JSON，儲存路徑：`.the-door/l2-outputs/<feature_id>.json`

格式遵循 `L2Output` dataclass 結構（`modules`, `module_interactions`, `anomalies`）。

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

本功能的核心邏輯集中在 `GraphViewModel_Converter` 的純函式，這些函式將 `L1Output`、`L2Output`、`StructureJSON`、`UpdateReport` 轉換為 ViewModel。這些函式具有明確的輸入/輸出行為，輸入空間大（任意 L1Output、L2Output 等），且有多個通用屬性（無懸空邊、節點唯一性、排序冪等性），非常適合 property-based testing。

**Property Reflection（冗餘消除）：**

初步分析識別出以下可合併的屬性：
- Req 2.4（dangling edge omission）與 Req 2.5（referential integrity）可合併：referential integrity 已涵蓋 dangling edge 的情況。
- Req 5.5（L2 dangling interaction）與 Req 5.6（L2 referential integrity）同理合併。
- Req 3.2（confidence marker）與 Req 3.6（node colors）都是「節點屬性正確映射」，可合併為一個「節點屬性完整性」屬性。
- Req 9.2（diff node colors）與 Req 9.3（diff edge filtering）可合併為「Diff ViewModel 結構完整性」。
- Req 12.1 與 Req 2.5 是同一屬性的重述，合併。
- Req 12.2 與 Req 5.6 是同一屬性的重述，合併。
- Req 12.3（node count = feature count）是 Req 2.5 的推論，但提供獨立的計數驗證，保留。
- Req 12.4（valid change_type values）是 Req 9.5 的子集，合併到 Diff ViewModel 屬性。
- Req 12.5（idempotent sort）獨立保留。

最終保留 **7 個屬性**，每個提供唯一的驗證價值。

---

### Property 1: L1 ViewModel 節點唯一性與邊引用完整性

*For any* valid `L1Output` object, `build_l1_graph_view_model` SHALL produce an `L1_Graph_ViewModel` where:
1. Every node `id` is unique (no duplicate feature_ids in output)
2. Every edge `source` and `target` references an existing node `id` in the same ViewModel (no dangling edges)
3. The count of nodes equals the count of `Feature` objects in `L1Output.features` (one-to-one mapping)

**Validates: Requirements 2.4, 2.5, 12.1, 12.3**

---

### Property 2: L2 ViewModel 節點唯一性與邊引用完整性

*For any* valid `L2Output` object, `build_l2_graph_view_model` SHALL produce an `L2_Graph_ViewModel` where:
1. Every node `id` is unique (no duplicate module_ids in output)
2. Every edge `source` and `target` references an existing node `id` in the same ViewModel (no dangling edges)
3. All anomaly entries from `L2Output.anomalies` are present in the output `anomalies` list

**Validates: Requirements 5.5, 5.6, 12.2**

---

### Property 3: Diff ViewModel 結構完整性

*For any* valid `UpdateReport` dict, `build_diff_graph_view_model` SHALL produce a `Diff_Graph_ViewModel` where:
1. Every node's `change_type` is one of `"added"`, `"removed"`, `"attribute_changed"`, `"dependency_changed"`
2. Every edge `source` and `target` references a node `id` present in the ViewModel's node set (edges only between changed nodes)
3. When `diff_result` is `None`, the ViewModel contains nodes but no edges

**Validates: Requirements 9.3, 9.5, 12.4**

---

### Property 4: 節點屬性完整性（L1 與 L2）

*For any* valid `L1Output` object, every node in `build_l1_graph_view_model` output SHALL contain the fields `id`, `label`, `confidence`, `description` with non-null values (sourced directly from `Feature` fields); `trigger_description` may be `null` only when built from `VersionSnapshot`.

*For any* valid `L2Output` object, every node in `build_l2_graph_view_model` output SHALL contain the fields `id`, `label`, `confidence`, `source_nodes` with non-null values (sourced directly from `L2Module` fields).

**Validates: Requirements 2.2, 5.2**

---

### Property 5: 語意差異排序冪等性

*For any* list of diff nodes, applying `sort_diff_nodes_by_semantic_diff` twice SHALL produce the same result as applying it once:
`sort_diff_nodes_by_semantic_diff(sort_diff_nodes_by_semantic_diff(nodes)) == sort_diff_nodes_by_semantic_diff(nodes)`

**Validates: Requirements 10.4, 12.5**

---

### Property 6: 風險優先排序正確性

*For any* list of diff nodes with varying `risk_flags` and `change_type` values, `sort_diff_nodes_by_risk` SHALL produce a list where:
1. Nodes with `"out_of_scope"` in `risk_flags` appear before nodes without it
2. Among nodes without `"out_of_scope"`, nodes with `"vulnerability"` appear before nodes without it
3. The sort is stable (nodes with equal priority maintain relative order)

**Validates: Requirements 10.1**

---

### Property 7: 語意差異排序單調性

*For any* list of diff nodes, `sort_diff_nodes_by_semantic_diff` SHALL produce a list where the computed magnitude (edit distance of labels + edit distance of descriptions) is non-increasing from first to last element.

**Validates: Requirements 10.2, 10.4**

---

## Error Handling

### 後端錯誤處理

所有新 API handler 遵循 Phase UI-2 建立的統一錯誤格式：

```json
{"error": {"code": "error_code", "message": "human readable", "source": "handler_name"}}
```

| 情境 | HTTP 狀態 | error.code |
|---|---|---|
| 無 VersionSnapshot | 404 | `no_l1_data` |
| L2 快取不存在 | 404 | `l2_not_generated` |
| Layer Explanation 快取不存在 | 404 | `explanation_not_cached` |
| structure.json 不存在 | 404 | `no_structure_data` |
| layer 參數無效（非 l1/l2/l3） | 400 | `invalid_layer` |
| 已有 running job | 409 | `job_already_running` |
| L2 生成失敗（LLM 錯誤） | 500（透過 job status） | `l2_generation_failed` |
| Layer Explanation 生成失敗 | 500（透過 job status） | `explanation_generation_failed` |
| 未預期例外 | 500 | `internal_error` |

**非同步 job 錯誤：** LLM 生成失敗時，`JobStore.fail_job()` 記錄錯誤訊息，前端透過輪詢 `GET /api/update/status/<job_id>` 取得 `status: "failed"` 與 `error_message`。

### 前端錯誤處理

| 情境 | 處理方式 |
|---|---|
| Cytoscape.js 未載入（`typeof cytoscape === "undefined"`） | 啟動 Mermaid fallback，顯示 fallback indicator |
| Cytoscape 初始化拋出例外 | 啟動 Mermaid fallback，顯示錯誤原因 |
| GET /api/l1 返回 404 | 顯示 empty-state：「尚未有 L1 分析資料，請執行 the-door analyze」 |
| GET /api/l2/<id> 返回 404 | 顯示「L2 尚未生成」狀態 + Generate L2 按鈕 |
| GET /api/structure 返回 404 | 顯示錯誤狀態：「結構資料不存在，請執行 the-door extract」 |
| GET /api/layer-explanation 返回 404 | 顯示「說明尚未生成」狀態 + Generate 按鈕 |
| POST generate 返回 409 | 顯示「另一個任務正在執行中，請稍候」 |
| 輪詢 status="failed" | 顯示 error_message，停止輪詢 |
| L1_Graph_ViewModel 節點數為 0 | 顯示 empty-state 訊息，不顯示空白畫面 |
| L3_Graph_ViewModel 節點數為 0 | 顯示 empty-state 訊息（source_nodes 為空） |

### L2Generator 錯誤處理

```python
class L2GenerationError(Exception):
    """Raised when L2 generation fails."""
    pass
```

- LLM 呼叫失敗（`LLMCallError`）→ 包裝為 `L2GenerationError`
- JSON 解析失敗 → 包裝為 `L2GenerationError`（含 raw response 前 200 字元）
- 必要欄位缺失 → 包裝為 `L2GenerationError`（含欄位名稱）

---

## Testing Strategy

### 雙軌測試策略

Phase UI-3 採用 unit tests + property-based tests 的雙軌策略：

- **Unit tests**：驗證具體範例、邊界條件、錯誤處理
- **Property tests**：驗證通用屬性（使用 Hypothesis，最少 100 次迭代）

### Unit Tests — `test_graph_view_model.py`

| 測試名稱 | 覆蓋的 Req |
|---|---|
| `test_build_l1_empty_features` | Req 2.6 |
| `test_build_l1_empty_relations` | Req 2.6 |
| `test_build_l1_dangling_edge_omitted` | Req 2.4, 2.6 |
| `test_build_l1_all_confidence_levels` | Req 2.6 |
| `test_build_l1_trigger_description_present` | Req 2.2 |
| `test_build_l1_from_snapshot_trigger_description_null` | Req 2.2 |
| `test_build_l2_empty_modules` | Req 5.7 |
| `test_build_l2_anomalies_with_multiple_affected_nodes` | Req 5.7 |
| `test_build_l2_dangling_interaction_omitted` | Req 5.5, 5.7 |
| `test_build_l3_empty_source_nodes` | Req 7.8 |
| `test_build_l3_non_existent_source_nodes` | Req 7.8 |
| `test_build_l3_mixed_node_types` | Req 7.8 |
| `test_build_l3_edges_filtered_to_source_nodes` | Req 7.4 |
| `test_build_diff_all_change_types` | Req 9.6 |
| `test_build_diff_empty_l1_changes` | Req 9.6 |
| `test_build_diff_edges_between_different_change_types` | Req 9.6 |
| `test_build_diff_no_diff_result_no_edges` | Req 9.5 |
| `test_sort_risk_first_order` | Req 10.1 |
| `test_sort_semantic_diff_three_nodes_varying_magnitude` | Req 10.4 |
| `test_sort_semantic_diff_null_fields_treated_as_empty` | Req 10.4 |

### Unit Tests — `test_l2_generator.py`

| 測試名稱 | 覆蓋的 Req |
|---|---|
| `test_generate_calls_llm_with_prompt` | Req 11.3 |
| `test_generate_persists_to_disk` | Req 11.3 |
| `test_generate_llm_error_raises_l2_generation_error` | Error handling |
| `test_generate_invalid_json_raises_l2_generation_error` | Error handling |
| `test_load_returns_none_when_not_found` | Req 11.2 |
| `test_load_returns_l2_output_when_found` | Req 11.2 |

### Unit Tests — `test_api_handlers_ui3.py`（新增，不修改現有 test_api_handlers.py）

| 測試名稱 | 覆蓋的 Req |
|---|---|
| `test_get_l1_returns_view_model` | Req 11.1 |
| `test_get_l1_no_snapshot_returns_404` | Req 11.1 |
| `test_get_l2_found_returns_view_model` | Req 11.2 |
| `test_get_l2_not_found_returns_404` | Req 11.2 |
| `test_post_l2_generate_returns_202` | Req 11.3 |
| `test_post_l2_generate_no_structure_returns_404` | Req 11.3 |
| `test_post_l2_generate_job_already_running_returns_409` | Req 11.3 |
| `test_get_layer_explanation_found` | Req 11.4 |
| `test_get_layer_explanation_not_found_returns_404` | Req 11.4 |
| `test_get_layer_explanation_invalid_layer_returns_400` | Req 11.6 |
| `test_post_layer_explanation_generate_returns_202` | Req 11.5 |
| `test_post_layer_explanation_generate_job_running_returns_409` | Req 11.5 |
| `test_get_structure_found` | Req 11.8 |
| `test_get_structure_not_found_returns_404` | Req 11.8 |

### Property Tests — `test_graph_view_model_properties.py`

使用 Hypothesis，`@settings(max_examples=100)`。所有 strategy 使用 ASCII-only 字串（對齊既有 PBT 慣例，Windows cp950 相容）。

| 屬性測試名稱 | 對應 Property | 覆蓋的 Req |
|---|---|---|
| `prop_l1_no_dangling_edges` | Property 1（邊引用完整性） | Req 2.5, 12.1 |
| `prop_l1_node_count_equals_feature_count` | Property 1（計數） | Req 12.3 |
| `prop_l1_node_ids_unique` | Property 1（唯一性） | Req 2.5 |
| `prop_l2_no_dangling_edges` | Property 2（邊引用完整性） | Req 5.6, 12.2 |
| `prop_l2_node_ids_unique` | Property 2（唯一性） | Req 5.6 |
| `prop_diff_valid_change_types` | Property 3（change_type 合法性） | Req 12.4 |
| `prop_diff_no_dangling_edges` | Property 3（邊引用完整性） | Req 9.3 |
| `prop_l1_node_required_fields` | Property 4（節點屬性完整性） | Req 2.2 |
| `prop_l2_node_required_fields` | Property 4（節點屬性完整性） | Req 5.2 |
| `prop_sort_semantic_diff_idempotent` | Property 5（冪等性） | Req 12.5 |
| `prop_sort_risk_first_out_of_scope_before_others` | Property 6（風險排序） | Req 10.1 |
| `prop_sort_semantic_diff_monotone` | Property 7（單調性） | Req 10.2 |

**Property test 標籤格式：**
```python
# Feature: interactive-graph, Property 1: L1 ViewModel 節點唯一性與邊引用完整性
@settings(max_examples=100)
@given(l1_output=st_l1_output())
def prop_l1_no_dangling_edges(l1_output):
    ...
```

### Hypothesis Strategy 設計

```python
# st_l1_output() — 生成任意 L1Output
@st.composite
def st_l1_output(draw):
    feature_ids = draw(st.lists(st.text(ascii_letters, min_size=1, max_size=10),
                                min_size=0, max_size=10, unique=True))
    features = [Feature(feature_id=fid, label=draw(st.text(ascii_letters, min_size=1)),
                        description=draw(st.text(ascii_letters)),
                        trigger="user_action",
                        trigger_description=draw(st.text(ascii_letters)),
                        confidence=draw(st.sampled_from(["high", "medium", "low"])),
                        confidence_reason="") for fid in feature_ids]
    # Relations may include dangling references (to test omission)
    all_ids = feature_ids + draw(st.lists(st.text(ascii_letters, min_size=1, max_size=5),
                                          min_size=0, max_size=3))
    relations = [FeatureRelation(from_feature=draw(st.sampled_from(all_ids)) if all_ids else "",
                                 to_feature=draw(st.sampled_from(all_ids)) if all_ids else "",
                                 relation=draw(st.text(ascii_letters, min_size=1)),
                                 relation_type="static")
                 for _ in range(draw(st.integers(min_value=0, max_value=5)))]
    return L1Output(features=features, feature_relations=relations)
```

### 測試覆蓋率目標

- `graph_view_model.py`：100% 行覆蓋率（純函式，無副作用）
- `l2_generator.py`：≥ 90% 行覆蓋率（LLM 呼叫路徑以 mock 覆蓋）
- `api_handlers.py`（新增方法）：≥ 90% 行覆蓋率

---

*Phase UI-3 不新增任何第三方 Python 依賴。Cytoscape.js 以本地靜態檔案形式引入，不透過 npm 安裝。所有 Python 功能使用標準函式庫（`difflib`、`json`、`pathlib`、`threading`）與既有 core 模組實作。*
