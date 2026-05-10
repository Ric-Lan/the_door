# The Door — Session Summary (2026-05-04, 更新於本次對話)

## 專案概述

The Door 是一個程式碼視覺化工具，將程式碼的「結構與變化」翻譯成功能語言圖形，讓不讀程式的人能直接驗核開發產出。

- **產品 Spec：** `the-door-spec-v4.1.md`（工作區根目錄）
- **架構：** LLM-Centric + AI-Medium-Agnostic
- **技術棧：** Python CLI + MCP Server + tree-sitter + networkx + jsonschema

---

## 已完成 Phase

### Phase 0a ✅ 圖形語言規範
**Spec：** `.kiro/specs/graphical-language-spec/`
**交付物：** `docs/phase-0a/`（12 個組件化文件）

### Phase 1-min ✅
**Spec：** `.kiro/specs/the-door-phase-1-min/`
**測試：** 100 tests
交付物：AST Extraction + Topology Analysis + Output Validation（5 項檢查）+ MCP Server（2 tools）+ CLI（extract/validate/mcp-serve）

### Phase 0b ✅ 信心標示規範
**Spec：** `.kiro/specs/confidence-markers-visual-spec/`
交付物：MarkerDef + MARKER_DEFS（6 種狀態）+ resolve_marker_state() + build_confidence_marker() + render_l1() 擴展

### Phase 1-full ✅
**Spec：** `.kiro/specs/the-door-phase-1-full/`
**測試：** 247 tests
交付物：LLM Layer + Reading Engine + Rendering + Validation Ext + Constraint Prompts + CLI（9 commands）+ MCP Server（7 tools）

### Phase 2 ✅ Diff 引擎
**Spec：** `.kiro/specs/diff-engine/`
**測試：** 322 tests（含 Phase 2 新增 72 tests）
**驗收：** 11/11 步驟通過

### Phase 2.5 ✅ 漏洞資訊層
**Spec：** `.kiro/specs/vulnerability-layer/`
**驗收：** 15/15 步驟通過

### Phase 3 ✅ 範圍驗核層
**Spec：** `.kiro/specs/scope-verification/`
**測試：** 267 unit tests 通過
**驗收：** 75/75 模擬驗收檢查通過

### Phase 4 ✅ 歷史時間軸層
**Spec：** `.kiro/specs/history-timeline/`
**測試：** 267 unit tests 通過
**驗收：** 62/62 模擬驗收檢查通過

### Phase 5 ✅ 即時動態層（版本更新管線）
**Spec：** `.kiro/specs/realtime-dynamic-layer/`
**測試：** 348 通過（2 個 pre-existing failures 與 Phase 5 無關）

交付物：

| 模組 | 檔案位置 | 功能 |
|---|---|---|
| Analyze Pipeline | `core/pipeline/analyze_pipeline.py` | 從 analyze_cmd 提取的可複用分析管線核心函式 |
| Pipeline Orchestrator | `core/pipeline/pipeline_orchestrator.py` | 管線編排：analyze(old) → analyze(new) → diff → scope → timeline → report |
| Report Renderer | `core/pipeline/report_renderer.py` | 三種輸出格式：互動式 Markdown / 結構化 JSON / Mermaid |
| CLI | `cli/update_cmd.py` | `the-door update <old-path> <new-path>` |
| MCP | `mcp/tools/update_tool.py` | MCP update tool（共 18 tools） |
| Schema | `schemas/update-report.schema.json` | Draft 2020-12 |
| Models | `models.py` | 11 新 dataclass + 3 exception classes |

### Phase UI-0 ✅ 靜態前端 Prototype
**位置：** `docs/frontend-local-version-viewer/prototype/`
**交付物：** HTML/CSS/Vanilla JS 三欄工作台，讀取靜態 mock 資料，驗證 UX 方向

### Phase UI-1 ✅ Local Report Viewer
**Spec：** `.kiro/specs/frontend-local-version-viewer/`
**測試：** 19 個 Python 測試通過（12 unit + 7 PBT）

交付物：

| 項目 | 位置 | 說明 |
|---|---|---|
| 前端 Viewer | `docs/frontend-local-version-viewer/viewer/` | HTML/CSS/Vanilla JS，三欄工作台，差異模式 + 單版本模式 |
| ViewModelConverter | `core/ui/view_model.py` | `build_update_report_view_model()` + `build_l1_view_model()` + export 函式 |
| Fixture 資料 | `viewer/data/update-view-model.json` + `l1-view-model.json` | 從 mock UpdateReport + 真實 L1 產生 |
| PBT | `tests/property/test_view_model_properties.py` | 7 個 Hypothesis 屬性（ASCII-only strategy） |

### Phase UI-2 ✅ Local API Server
**Spec：** `.kiro/specs/local-api-server/`
**測試：** 81 個新測試通過（unit + PBT），全套 402 tests 通過（排除 2 個 pre-existing failures）

交付物：

| 模組 | 檔案位置 | 功能 |
|---|---|---|
| JobStore | `core/ui/job_store.py` | `UpdateJob` + `JobStore`，thread-safe in-memory 管線狀態管理 |
| StaticHandler | `core/ui/static_handler.py` | 靜態資源服務，含路徑遍歷防護（403 vs 404 正確區分） |
| Serializers | `core/ui/serializers.py` | `VersionSnapshot`/`DoubtRecord`/`TimelineResult` 序列化純函式 |
| APIHandlers | `core/ui/api_handlers.py` | 7 個 API 端點業務邏輯，每個回傳 `(status_code, body)` |
| UIServer | `core/ui/server.py` | `ThreadingHTTPServer`，只綁 `127.0.0.1` |
| CLI | `cli/ui_cmd.py` | `the-door ui <project-path>` 指令 |
| PBT | `tests/property/test_api_serializer_properties.py` | 5 個 Hypothesis 屬性（Req 13） |

**API 端點：**

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/project` | 專案路徑、可用資料狀態（has_snapshots/has_latest_report/has_doubts/has_scope_config） |
| GET | `/api/snapshots` | 快照列表（依 timestamp 降序） |
| GET | `/api/report/latest` | 最新 UpdateReport JSON（依 generated_at 選最新，fallback: mtime） |
| POST | `/api/update` | 觸發管線（非同步，回傳 job_id） |
| GET | `/api/update/status/<job_id>` | 輪詢管線進度 |
| GET | `/api/doubts` | 疑義列表 |
| GET | `/api/timeline` | 時間軸分析結果 |

**前端升級：**
- `index.html`：加入 PipelineProgress 元件、UpdateModal（old_path/new_path 輸入表單）
- `app.js`：API 呼叫邏輯（`/api/project` → `/api/report/latest` → 輪詢）+ fallback 策略
- `styles.css`：PipelineProgress、Modal 樣式

**關鍵設計決策：**
- MVP server：Python 標準函式庫（`http.server`/`socketserver`），不新增 FastAPI/Flask
- `ThreadingHTTPServer`：允許同時處理靜態資源請求和 API 輪詢，避免 pipeline 執行期間 UI 凍結
- 至多一個並發 UpdateJob；`threading.Lock` 保護 job 狀態
- 輪詢（polling）而非 SSE：標準函式庫不原生支援 SSE；輪詢對本地場景延遲可接受
- UpdateReport 持久化到 `DotTheDoor_Dir/update-report-<generated_at>.json`（`:` 替換 `-`）
- 路徑驗證在 API handler 層（不依賴 orchestrator 的 `PipelineError`）
- `StaticHandler.resolve_path()` 回傳 `None` 只在路徑遍歷時（403）；檔案不存在由 `serve()` 判斷（404）
- `UpdateJob._lock` 為 dataclass 欄位，`update_step()` 使用 `self._lock`（thread-safe）
- 進度訊息解析依 Unicode 符號（`✓`/`✗`/`⊘`），不依賴中文關鍵字（Windows cp950 相容）
- fallback 規則：靜態 JSON 只在 `/api/project` 拋出網路錯誤時（server 未啟動）才使用；server 啟動後 `has_latest_report=false` 顯示 EmptyState
- `viewer_dir` 路徑：5 層 parent 從 `cli/ui_cmd.py` 到 workspace root（假設 editable install）

### Phase UI-3 ✅ Interactive Graph
**Spec：** `.kiro/specs/interactive-graph/`
**測試：** 490 passed（2 個 pre-existing failures 與 Phase UI-3 無關）

交付物：

| 模組 | 檔案位置 | 功能 |
|---|---|---|
| GraphViewModel_Converter | `core/ui/graph_view_model.py` | 純函式：`build_l1_graph_view_model()` / `build_l1_graph_view_model_from_snapshot()` / `build_l2_graph_view_model()` / `build_l3_graph_view_model()` / `build_diff_graph_view_model()` / `sort_diff_nodes_by_risk()` / `sort_diff_nodes_by_semantic_diff()` / `_edit_distance()` |
| L2Generator | `core/ui/l2_generator.py` | `L2GenerationError` + async `generate()` + `load()` staticmethod；持久化到 `.the-door/l2-outputs/<feature_id>.json` |
| APIHandlers 擴展 | `core/ui/api_handlers.py` | 新增 6 個 handler + 2 個私有背景執行緒方法（不修改既有 7 個方法） |
| Server 路由擴展 | `core/ui/server.py` | 新增 `/api/l1`、`/api/structure`（靜態）+ `/api/l2/<fid>`、`/api/layer-explanation/<fid>/<layer>`（動態 GET/POST） |
| Cytoscape.js 本地打包 | `viewer/lib/cytoscape.min.js` | 離線可用，無 CDN 依賴 |
| 前端升級 | `viewer/app.js` / `index.html` / `styles.css` | Cytoscape 渲染、三層導覽（L1→L2→L3）、差異模式圖形、Breadcrumb、Mermaid fallback、Layer Explanation 按需生成 |
| PBT | `tests/property/test_graph_view_model_properties.py` | 12 個 Hypothesis 屬性（Req 12） |

**新增 API 端點：**

| Method | Path | 說明 |
|---|---|---|
| GET | `/api/l1` | L1_Graph_ViewModel（從最新 VersionSnapshot 轉換） |
| GET | `/api/l2/<feature_id>` | L2_Graph_ViewModel（從 `.the-door/l2-outputs/` 讀取） |
| POST | `/api/l2/<feature_id>/generate` | 觸發 L2 LLM 生成（非同步，回傳 job_id） |
| GET | `/api/layer-explanation/<fid>/<layer>` | 讀取 Layer Explanation 快取 |
| POST | `/api/layer-explanation/<fid>/<layer>/generate` | 觸發 Layer Explanation LLM 生成（非同步） |
| GET | `/api/structure` | 回傳 `.the-door/structure.json` 內容 |

---

## Phase 路線圖

```
Phase 0a    ✅ 圖形語言規範
Phase 1-min ✅
Phase 0b    ✅ 信心標示規範
Phase 1-full ✅
Phase 2     ✅ Diff 引擎
Phase 2.5   ✅ 漏洞資訊層
Phase 3     ✅ 範圍驗核層
Phase 4     ✅ 歷史時間軸層
Phase 5     ✅ 即時動態層（版本更新管線）
Phase UI-0  ✅ 靜態前端 Prototype
Phase UI-1  ✅ Local Report Viewer
Phase UI-2  ✅ Local API Server
Phase UI-3  ✅ Interactive Graph
```

---

## 可用指令（30 個）

```bash
# Phase 1–4 既有指令
the-door extract <codebase-path>
the-door validate <l1.json> <struct.json>
the-door analyze <codebase-path>
the-door regenerate <feature_id>
the-door render <output.json>
the-door estimate <codebase-path>
the-door history <codebase-path>
the-door config init
the-door mcp-serve
the-door diff <path> --baseline <ref>
the-door snapshot create <path> --label <name>
the-door snapshot list <path>
the-door snapshot prune <path>
the-door scan <codebase-path>
the-door scope verify <path> --scope <ref>
the-door scope create <scope-name>
the-door scope list
the-door scope show <scope-name>
the-door doubt list
the-door doubt show <doubt-id>
the-door doubt assign <doubt-id> <assignee>
the-door doubt resolve <id> --as <type> --reason <r>
the-door doubt escalate <doubt-id> --reason <r>
the-door timeline <codebase-path>

# Phase 5 新增
the-door update <old-path> <new-path>          # 版本更新管線
the-door update <old-path> <new-path> --scope <name>
the-door update <old-path> <new-path> --json
the-door update <old-path> <new-path> --render
the-door update <old-path> <new-path> --offline
the-door update <old-path> <new-path> --force-reanalyze

# Phase UI-2 新增
the-door ui <project-path>                     # 啟動本地 UI server（http://127.0.0.1:8765）
the-door ui <project-path> --port <N>          # 指定端口
the-door ui <project-path> --no-browser        # 不自動開啟瀏覽器
```

---

## 關鍵設計決策備忘

### 通用
- TDD 原則：測試先寫，實作後補
- Property-based testing：Hypothesis
- MultiDiGraph：正確處理重複邊的度數計算
- Windows 相容：所有 write_text/read_text 需要 `encoding="utf-8"`
- Hypothesis 策略：Windows 上避免 Unicode 字元（cp950 編碼問題），用 ASCII-only 或 `st.builds`

### Phase 5 (Realtime Dynamic Layer)
- Pipeline Orchestrator 為 pure orchestration，不含分析邏輯
- analyze 失敗 = 管線終止；其他步驟失敗 = 繼續執行
- 檔案指紋：路徑 + 大小 + mtime（O(1)，不讀檔案內容）
- 指紋儲存在 `.the-door/fingerprints/`，不修改 VersionSnapshot schema
- PipelineConfig 用 composition 包含 AnalyzeConfig（避免欄位重複）
- Mermaid 漏洞標記用文字摘要（Phase 5 不觸發 L2 分析）
- SIGINT：完成當前步驟後停止，生成部分報告
- MCP update tool 預設 JSON 格式、skip_cost_confirm=True

### Phase UI-1 (Local Report Viewer)
- `diff_available = len(changes_raw) > 0`（非 key 存在性）
- DetailPanel A 類（Python 填「未提供」）直接顯示；B 類（scope_state=null）JS 補值
- 防幻覺：`detail.source` 永遠顯示
- PBT strategy：ASCII-only（min_codepoint=32, max_codepoint=126），Windows cp950 相容
- 前端啟動：`python -m http.server 8765`

### Phase UI-2 (Local API Server)
- MVP server：Python 標準函式庫（`http.server`/`socketserver`），不新增 FastAPI/Flask
- `ThreadingHTTPServer`：允許同時處理靜態資源請求和 API 輪詢
- 至多一個並發 UpdateJob；`threading.Lock` 保護 job 狀態
- 輪詢（polling）而非 SSE：標準函式庫不原生支援 SSE
- UpdateReport 持久化：`update-report-<generated_at>.json`（`:` 替換 `-`）
- 只綁 `127.0.0.1`（loopback），不綁 `0.0.0.0`
- 路徑驗證在 API handler 層（不依賴 orchestrator 的 `PipelineError`）
- `StaticHandler.resolve_path()` 回傳 `None` 只在路徑遍歷時（403）；檔案不存在 → 404
- `UpdateJob._lock` 為 dataclass 欄位（thread-safe）
- 進度訊息解析依 Unicode 符號（`✓`/`✗`/`⊘`），不依賴中文關鍵字
- fallback：靜態 JSON 只在 server 未啟動（網路錯誤）時使用
- `viewer_dir` 路徑：5 層 parent 從 `cli/ui_cmd.py` 到 workspace root（editable install）
- `SnapshotStore(project_root).list_snapshots()`（建構時傳入 project_root）
- `DoubtRecord.source_node`（非 feature_id）；API 序列化：`current_state → state`，`assigned_to → assignee`

### Phase UI-3 (Interactive Graph)
- Cytoscape.js 本地打包（`viewer/lib/cytoscape.min.js`），不使用 CDN，離線環境可用
- Mermaid 文字 fallback：Cytoscape 初始化失敗時不顯示空白畫面
- `GraphViewModel_Converter` 純函式模組（Python），所有轉換邏輯集中、可測試
- `L2Generator` 獨立模組，與 API handler 解耦；async generate() 透過 `asyncio.run()` 在背景執行緒呼叫
- 共用 `JobStore`（Phase UI-2 + UI-3），至多一個並發 job 的約束延伸到所有非同步操作
- Layer-wide 切換（不支援單節點展開），避免混合層級的視覺複雜度
- `difflib.SequenceMatcher` 計算語意差異，Python 標準函式庫，不新增依賴
- `.the-door/layer-explanations/<feature_id>/<layer>.json` 快取格式：`{feature_id, layer, explanation, generated_at}`
- Diff 模式預設 risk-first 排序；client-side 切換 semantic-diff-first，不呼叫 API

---

## 在新對話中繼續

**所有規劃 Phase 已完成。** 如需繼續，可選擇：

1. **手動驗收 Phase UI-3**：實際跑 `the-door ui <path>`，確認互動圖、層切換、Diff 模式如預期運作
2. **端對端整合測試**：跑完整的 `the-door update <old> <new>` → `the-door ui <path>` 流程，確認前後端串接正確
3. **開新 Phase**：根據實際使用回饋定義新功能（參考 `docs/frontend-local-version-viewer/spec.md §15` 的「明確不做」清單作為候選方向）

繼續時告訴 Kiro：「參考 SESSION-SUMMARY.md 了解目前進度」即可。
