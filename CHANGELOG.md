# Changelog

All notable changes to The Door are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## v1.5.1 — 2026-05-30

### Fixed
- **Wizard visual port (first pass)**: PAGE_ACTION/SETUP/LABEL/CONFIRM 補上 prototype 視覺層 — eyebrow（每頁皆有）、27px hero heading、lede prose、icon-card 選項 (`.opt > .ico + .tx + .arrow`)、switch-zone 一列式 footer (`.sz-label` + `.switch-row`)、summary 4 row（操作/排除目錄/版本標籤/執行模式）。Icon library `I = {scan/refresh/eye/arrow/info/warn/lines/clock}` 移植進 `ui-wizard.js`。Legacy `.wizard-card` bordered framing 在 `.wizard-shell` 內被中和（border/box-shadow/max-width neutralised）讓 `.wizard-screen` 全幅顯示。Pre-existing FIX-1~5 + 老 test-asserted class 名（`.wizard-option-btn` / `.wizard-eyebrow` / `.wizard-mode-note` 等）保留並列以維持 853 JS 測試綠燈。佈局尚未 100% 對齊 prototype（rail 寬度、screen padding、選項卡片間距仍有差異），待後續 spec 重新撰寫後再迭代。

---

## v1.5.0 — 2026-05-30

### Added
- **Onboarding flow Part 2**: 雙欄精靈外殼（左門外暗面 + 右門內明亮）+ 進度視覺化（phasebar + steplist + 即時檔案 feed）+ 跨頁穿門轉場（spec §0-§9）
- **後端 progress 契約**: `UpdateJob.progress` 欄位（`files_done` / `files_total` / `current_file` / `current_root`）由新 `ProgressReporter` 抽象從 `ASTExtractor` / `BatchReader` 內部 file loop 寫入；`handle_get_update_status` payload 暴露給前端
- **handle_post_analyze adapter**: 精靈 analyze 走 `run_analyze_pipeline` 經 per-request closure 映射為 `[步驟 N/6]` 訊息與 modal `PipelineOrchestrator.run` 對齊（spec §5.1）
- **Viewer modal 進度設計一致化**: `ui-modal.js renderPipelineProgress` 改用 phasebar/steplist/feed（與精靈 PROGRESS 同設計）
- **「上一步」鈕**: PAGE_SETUP / PAGE_LABEL / PAGE_CONFIRM 三處新增 `.wizard-btn-ghost`；通用化 `{ type: 'BACK', target }` action 支援 analyze 與 update 兩條路徑（spec §4.3）
- **`errorOriginPage` state 欄位**: PAGE_ERROR rail stage 由 origin 推回，避免 STATUS_ERROR 在 LOADING 階段被誤顯示為「分析中」（spec §4.1）

### Changed
- 新增共用前端模組 `viewer/js/progress-view.js`（`renderProgressInnerHTML` / `appendPlLine` / `updateProgressCount`）+ `viewer/js/phase-status.js`（`phaseStatus` 4-way + `PHASE_BUCKETS` + `STEP_LABELS`）— 精靈 PAGE_PROGRESS 與 modal `renderPipelineProgress` 共用同一 render 路徑（spec §7 一致化）
- `styles.css` 加 11 個 Part 2 token（terminal / radius / rail 系列）+ 共用進度區（`/* Progress (shared) */`）
- `wizard.css` 加 shell + rail + screen 動畫 + mode-note + ghost button + agent-* + transient；字體 token (`--font-sans` / `--font-mono`) 限定 `.wizard-shell` 後代 scope（不入 styles.css :root 避免 7 處 fallback regression）
- `wizard.html` 移除 `.wizard-root` wrapper（雙欄自滿版）

### Removed
- `styles.css:846-870` 舊 `.step-*` chips 規則（已被 `.wizard-phasebar` / `.wizard-sl-row*` 取代）

### Tests
- 1a/1b: +18 Python tests（progress_reporter / adapter / payload / e2e）
- 2-9: +35 JS tests（shell / phasebar / feed / back / error-origin / transition）
- coverage 維持 100%

---

## v1.4.6 — 2026-05-30

### Edge noise projection (post-v1.4.5 增量)

- **`Edge.resolution` 加 `name_match_ambiguous` 枚舉值**：高 fanout（候選 > N）的裸名匹配標為 ambiguous
- **新增 `core/llm/edge_projection.py` 純函式投影層**：drop ambiguous + 把 `skipped_dynamic` 邊聚合成 `aggregate_call_hints`
- **BatchReader detail mode payload 加 `aggregate_call_hints` 欄位**；minimal mode 不變
- **L1 prompt 教 LLM 看 hint 但不可寫成依賴**

#### Dogfood §7.2 驗收

| Target | 投影前邊數 | 投影後邊數 | drop% | callers with hints |
|---|---|---|---|---|
| `the_door/src/the_door` | 2044 | 1935 | 5.3% | 18 |
| `test-targets/the-door-v105` | 3413 | 3167 | 7.2% | 47 |

`FANOUT_THRESHOLD = 3`（由 dogfood histogram p75/p90 分佈決定：兩 repo p75=1 p90=1，均遠低於門檻，維持預設值）

#### 向後相容

- 既有 snapshot 反序列化不報錯
- source-level guard 釘住 `core/diff/` 不引用 `edge.resolution`，新枚舉值不會造成 diff 假 churn
- viewer 不需要改動

---

## [1.4.5] — 2026-05-29

### Added
- **Scope-aware edge resolution** for all 7 supported languages (Python / TypeScript / Java / Go / Rust / Ruby / PHP / C#).
  - New `ScopeRules` declarative config per language defining import / function / method / inheritance resolution strategies.
  - New `Edge.resolution` field with four values: `scope_rule` (high confidence), `import_alias` (high confidence), `name_match` (low-confidence fallback), `skipped_dynamic` (dynamic-dispatch context — not trusted).
  - LLM prompt teaches the model how to weight edges by resolution provenance.
- New `ScopeContext` dataclass carrying per-file scope state (import aliases, caller class).
- **Receiver-aware method-call resolution**：`Receiver.method()` 形式的呼叫會把 receiver 透過 import alias 或 local class 名解析回 `Class.method`，`self.method()` / `this.method()` 在 method 內也會解析回 `caller_class.method`。Chained call `a.b.c()` 採 immediate-receiver 慣例（receiver = `b`）。
- BatchReader detail payload 現在包含 batch 內的 `edges`，讓 L1 LLM 直接看到 resolution 標籤。

### Changed
- `EdgeBuilder.build_edges()` 新增 optional `configs` 參數（向後相容）。
- `ASTExtractor` 把 `LANGUAGE_CONFIGS` 傳給 `EdgeBuilder`。
- Edge dedup key 維持 `(from, to, type)`；`resolution` 不入 key（讓 scope_rule 邊取代同對 name_match 重複）。
- `_detect_imports` 產生的 import 邊 resolution 從 `name_match` 改為 `import_alias`（語意修正：import 邊定義上就是 alias-based）。

### Backward compatibility
- 舊 snapshot 無 `resolution` 欄位反序列化時自動補 `"name_match"`（不需 migration）。
- `Edge(from_node=..., to_node=..., type=...)` 不帶 `resolution` 仍可用（預設 `"name_match"`）。
- 公開 API 簽名未破壞；`build_edges(nodes, trees)` 仍可用。

### Dogfood acceptance (§7.2)
- `the_door` 自身：name_match 28.8% / high-confidence 71.2% ✅
- `test-targets/the-door-v105`：name_match 30.8% / high-confidence 69.2% ✅
- 兩個 target 都過 `name_match ≤ 40%` 且 `scope_rule + import_alias ≥ 50%`。

---

## [1.4.0] — 2026-05-28

### Added
- **Detail context mode for L1 analysis（預設啟用）**：`the-door analyze`
  與 `the-door update` 現在預設把每個節點的完整 signature、docstring、
  decorators / annotations、檔案路徑送給 LLM，提升非技術讀者的描述
  品質。原有「只送 node_id」行為保留，可用 `--minimal-context` opt-out。
- **多語言 ASTNode 充實**：`_walk_config_driven` 透過擴充後的
  `LanguageConfig` 為 Java / Go / Rust / Ruby / PHP / C# 6 種語言抽取
  parameters、return_type、docstring、decorators。Python 與 TypeScript /
  JavaScript 既有 walker 不變。
- MCP `analyze_tool` 接受 optional `context_mode` 欄位（`detail` /
  `minimal`，預設 `detail`）。
- L1 system prompt 新增硬性規則 5：禁止直接複製 docstring / comments /
  decorators / signature 進 description 或 trigger_description。

### Changed
- `BatchReader` 引入共用 `_serialize_payload` helper，由 `_process_batch`、
  `_maybe_split`、`regenerate` 共同使用。確保切批估算與實送 payload 一致。

### Notes
- Output schema 完全不變。既有 `.the-door/snapshots/` 檔案無需 migration。
- 新模式下 token 用量會明顯上升（估算 5-15 倍）。對成本敏感的工作流可
  加 `--minimal-context`。
- `extract_structure` MCP tool 不受影響。

---

## [1.3.6] — 2026-05-27

### Added
- **L1 Feature Detail Fields**：Viewer 單版本模式詳情欄新增三個欄位：
  - `trigger_description`（觸發方式）：說明該 feature 在什麼情境下被觸發
  - `confidence_reason`（信心理由）：說明 high/medium 信心度的依據
  - `source_nodes`（Source Nodes）：對應的原始碼節點清單
- **`snapshot_patch` 擴充**：`patch_snapshot()` 新增 `feature_metadata_by_feature` 參數，
  可在不更動 `version_id` 的情況下寫入 `trigger_description` / `confidence_reason`；
  MCP tool schema 同步更新，`source_nodes_by_feature` 移出 `required`，
  `patched_features` 回傳值從 count integer 改為 feature ID list。
- **Pipeline 轉發**：`handle_get_l1` → `build_l1_graph_view_model_from_snapshot` →
  `layers.js loadL1Graph` 全路徑轉發新欄位，含防禦性預設值（`source_nodes: []`）。

---

## [1.3.5] — 2026-05-27

### Added
- **Dynamic Project Switching**：新增 `POST /api/set-project`，讓 UIServer 在執行期切換
  分析目標目錄，無需重啟 server。
  - `JobStore.get_running_job_id()` — 查詢當前執行中 job ID
  - `APIHandlers` callable injection（backward compatible）— `project_root`/`job_store`
    改為 callable property，支援 `project_root_fn`/`job_store_fn`/`switch_project_fn` 注入
  - `UIServer._switch_project(new_path, force)` — thread-safe（`threading.Lock`），
    回傳 `switched` / `conflict` / `error`
  - `handle_post_set_project`：路徑驗證（存在、是目錄、可讀）+ 409 conflict 支援
  - Wizard UI（`ui-wizard.js`）新增切換專案區塊：輸入框、切換按鈕、conflict 確認介面

---

## [1.3.1] — 2026-05-26

### Added
- **Wizard UI 入口**：`the-door ui` 改為開啟 `wizard.html` 結構化問卷，引導使用者
  設定分析目標並觸發分析。包含 `/api/analyze` POST endpoint、`ui-wizard.js` 狀態機、
  `wizard.html` / `wizard.css`。

---

## [1.2.3] — 2026-05-24

### Added
- **FlowGuard 程式級流程強制**：新增 `FlowGuard` + `Decision` + `CheckpointOption`
  系統，在關鍵決策點以程式邏輯拋出 checkpoint，取代僅依賴文件的引導方式。
  MCP 層回傳 `{"result": null, ...checkpoint...}`，CLI 層以 `CheckpointRenderer`
  阻塞 stdin，agent 無法拿到資料就無法繼續。
- **Store 解耦（ProjectIdentity）**：新增 `ProjectIdentity` + `StoreResolutionResult`，
  將 snapshot store 遷移至 `~/.the-door/store/<UUID>/`，與 source codebase 路徑分離。
  `VersionSnapshot` 新增 `codebase_path` 欄位記錄來源路徑。
- **MCP CHECKPOINT 強制點**：
  - `system_status_tool`：`unanalyzed-versions-detected`（問題 #1/#4）
  - `snapshot_write`：`new-features-detected` + inherit_from merge bug 修復（問題 #7）
  - `analyze_changes`：`source-path-broken` + `source_path` 參數（問題 #8/#10）
- **CLI CHECKPOINT 強制點**：
  - `analyze_cmd`：`no-api-key`（問題 #2）
  - `status_cmd`：`project-not-initialized` + `unanalyzed-versions-detected`（問題 #3/#4）
  - `extract_cmd`：`backfill-complete` + `_count_empty_source_nodes`（問題 #9/#11）

### Fixed
- `snapshot_write` + `inherit_from` 過濾掉新增 feature 的 merge 邏輯 bug（問題 #7）
- `analyze_changes` 在 store/source 路徑分離時無法運作（問題 #10）

### Internal
- `.kiro/specs/flow-guard-store-decoupling/`：FlowGuard spec + 5 份 task 文件
- 測試覆蓋：898 passed + 45 skipped；新增 contract / integration / unit 全覆蓋

---

## [1.2.2] — 2026-05-23

### Added
- **多語言 L1 抽取（Stream A）**：以 `language_configs.py` config-driven 架構取代
  `_walk_generic`，新增 Rust / Java / Ruby / PHP / C# / Go / Python / TypeScript / JavaScript
  逐語言節點型別對照表；修復 Go methods、orphaned method_types 抽取失效。
  測試覆蓋率 100%（unit + regression + property）。
- **Claude Code hooks（Stream D）**：新增 3 條開發守衛 hook（UserPromptSubmit、
  PostToolUse、Stop），確保前端唯一正式版路徑與 UI 啟動指令。
- **Viewer 設計系統套用（Stream B）**：依 design system v1.1.1 全面更新
  design token、topbar（版本 pill、logo 狀態、risk filter button）、
  list filter bar（信心/類型/排序純函式 pipeline）、CJK-aware word-level diff、
  notes 折疊卡片、doubt 詳情視圖、心智圖 diff badge + anomaly badge + L1 節點尺寸。
- **Diff 詳情面板（Stream C）**：`/api/diff` 回應加入 `node_details` map；
  詳情欄在 structural diff 模式下顯示版本 A/B 說明文字對比；詳情欄加寬。
- **版本選擇器 dropdown 修復**：版本 A/B pill 恢復 `<select>` 下拉；
  `populateVersionSelectors()` 正確掛載。
- **備註 tab**：詳情面板新增「詳情 / 備註」分頁切換，備註區塊移至獨立 tab pane。
- **關聯圖 grid 卡片 layout**：以 CSS grid 卡片取代 Cytoscape 節點圖，
  呈現變更類型色彩與信心度邊框；SVG edge overlay 由 `requestAnimationFrame` 繪製。

### Internal
- `.kiro/specs/consolidated-roadmap-2026-05-23/`：4 工作流合併 spec（10 節）
  + 5 份 task 文件。

---

## [1.2.1] — 2026-05-20

### Added
- **L1 System Prompt**：新增 `L1_SYSTEM_PROMPT`，針對非技術讀者強制輸出規則，
  透過 `batch_reader` provider 傳入所有 L1 分析呼叫。
- **L2 Anomaly Checklist**：`per-module anomaly checklist` 針對 3 種可由 AST 判斷
  的異常類型（過大模組、孤立節點、循環相依）強制執行。
- **Diff Explanation Prompt 強化**：新增 forbidden list + examples，
  防止 LLM 產出過於模糊或重複的差異推論。

---

## [1.2.0] — 2026-05-18

### Added
- **增量分析完整實作**：`compute_affected_features`、`incremental_pipeline`
  orchestrator、`analyze_changes` MCP tool、`snapshot_write` 支援 `inherit_from`
  + `updated_features`，實現跨 snapshot 增量更新。
- **Guidance Engine**：`SystemState` frozen dataclass、`StateInspector`（50ms 限制）、
  `NextActionSuggester` 規則表 + after-error boost、`Remediation` + 標準錯誤信封（F3）。
- **CLI UX**：`the-door status`、`--from-snapshot` 增量旗標、`extract --as-version`
  backfill、所有 CLI 命令加入 post-run Next: hook 與 F3 error envelope。
- **MCP Surface**：`system_status`、`analyze_changes` tool；所有 MCP 工具回應
  統一注入 `next_actions`；shared response envelope helper。
- **Viewer 模組化**：`js/` 拆分為 state / dom / api / viewmodel / graph /
  ui-detail / ui-list / ui-topbar / ui-notes / ui-diff-explanation /
  ui-modal / layers / app.js 共 13 個模組；TDD 逐步實作（Steps 0–10）。
- **Viewer 功能**：`ui-detail.js` 接線真實 notes + diff-explanation；
  `buildMindmapData` 統一 diff 資料來源；onboarding card；Next Actions 區塊；
  版本比較 count badge 修正；state-aware branding；CSS token 統一。
- **Snapshot 強化**：per-version gzipped structure 讀寫；`list_analyzed_versions`；
  `source_nodes` 持久化；`source_node_count` 推導；node_id 碰撞後綴（P3）。
- **測試基礎建設**：Hypothesis property test patterns；contract test skeletons；
  v105 scenario gate（7 steps）；`_seed_helpers` 整合 7 個 call site。

### Changed
- `CLAUDE.md` 重構為決策樹格式，以 `the-door status` 為唯一起點。
- README 重構為 UX-sequence-focused onboarding guide（407 → 182 行）。

---

## [1.1.0] — 2026-05-13

### Added
- **使用者備註（RI-3）**：右側詳情欄新增本地備註系統。備註依 `mode + version key + feature_id`
  嚴格隔離，存為 append-only JSONL（`NoteStore`）。支援 GET/POST `/api/notes`，
  UI 以 `<details>/<summary>` 折疊呈現，每次載入自動讀取歷史備註。
- **輸出語言選擇（RI-4）**：重新分析 Modal 新增語言 select（預設 `zh-Hant`，支援 `en`）。
  選擇值透過 `POST /api/update` 傳入 pipeline，寫入 `PipelineConfig.output_language`
  與 `UpdateReport.output_language`。
- **差異推論（RI-5）**：差異比較模式右側詳情欄新增「差異推論」區塊。使用者手動觸發
  `POST /api/diff-explanations/<id>/generate`，LLM 依差異資料產生自然語言推論（影響、目的、
  連動資源、注意事項、信心水準）。結果存入獨立 JSONL cache（`DiffExplanationStore`），
  不覆寫 `UpdateReport`。A 版/B 版單一模式不顯示此區塊。
- `DiffChangeExplanation` dataclass（frozen）：記錄 LLM 差異推論結果，
  含 `confidence`（high/medium/low）、`language`、`generated_at` 等欄位。
- `NoteStore`、`DiffExplanationStore`：兩個獨立 append-only JSONL store，
  位於 `.the-door/user-notes/` 與 `.the-door/diff-explanations/`。
- API 端點：`GET/POST /api/notes`、`GET /api/diff-explanations/<id>`、
  `POST /api/diff-explanations/<id>/generate`（共新增 4 個端點）。

### Changed
- **Topbar 視覺強化（RI-2b）**：count badge 符號（+/-/~/⚠）改為中文標籤（新增/移除/修改/注意）。
  所有 Topbar 控制項加入原生 `title` tooltip。`.mode-button.active` 改用
  `var(--accent-soft)` 背景 + `var(--accent)` 文字色，視覺可辨識度提升。
- `UpdateReport` 新增 `output_language: str = "zh-Hant"` 與
  `diff_change_explanations: list[DiffChangeExplanation]` 欄位（有預設值，向下相容）。
- `PipelineConfig` 新增 `output_language: str = "zh-Hant"` 欄位。

### Internal
- 新增 hook stub 架構（RI-2）：`_appendDiffExplanationSection`、`_appendUserNotesSection`
  從三個 render 函式呼叫，讓 RI-3/RI-5 只需填入對應函式，不修改 render path。
- 測試數：447 → 647（新增 207 個測試，含 unit、server routing、static viewer 測試）。

---

## [1.0.6] — 2026-05-10

### Added
- `snapshot_write` MCP tool: AI agents can now write their own L1 analysis results
  directly into the snapshot store without requiring an external LLM API key.
  Enables the full MCP agent-mode pipeline: `extract_structure` → analyze → `snapshot_write` → `diff` → UI.
- `CLAUDE.md`: Defines the MCP multi-tool orchestration sequence for AI platforms
  (Claude Code, Kiro IDE, etc.) acting as the analysis LLM.
- `extract_structure` response now includes `analyzed_files` field (list of analyzed file paths).
- `ProjectRegistry`: Auto-registers analyzed projects in `~/.the-door/registry.json`.
- `the-door projects` CLI command: lists all registered projects.
- `project_list` MCP tool: AI can query registered projects via MCP.
- `the-door ui` now supports interactive project picker when called without a path argument.
- UI server: `GET /api/diff?baseline=<version_id>&current=<version_id>` endpoint for
  computing L1 diff between two snapshots by version ID.

### Changed
- README MCP Quick Start: Added reference to `CLAUDE.md` for tool orchestration details.
- UI version selector: version A now defaults to the older (baseline) snapshot,
  version B to the newer (current) snapshot — previously reversed.
- CLAUDE.md Mode B pipeline: removed `validate_output` step (format incompatible with
  Mode B output); added cross-directory snapshot workaround for `diff`.
- Frontend: API base URL now uses `window.location.host` instead of hardcoded port 8765.

### Fixed
- MCP agent-mode pipeline was previously undocumented, causing AI platforms to fail
  to chain tools correctly when attempting no-API-key analysis.
- UI graph drawer now opens automatically on page load when snapshot data is available.
- Frontend version comparison logic overhauled to correctly trigger diff overlay when
  switching versions via the version selector.

---

## [1.0.5] — 2026-05-09

### Changed
- License: Switched from AGPL-3.0 + Commons Clause to dual licensing
  (AGPL-3.0 Community Edition + Commercial License on request).
- README: Split into English (`README.md`) and Traditional Chinese (`README.zh-TW.md`)
  with language switcher. Restructured into Quick Start / Detailed Reference sections.
  Added MCP path documentation.

### Fixed
- L2 graph view model now exposes `confidence_reason` field.

---

## [1.0.4] — 2026-05-09

### Fixed
- L2 mindmap boxes now auto-size with CJK-aware text measurement.
- Anomaly nodes show orange border and badge on all L2 nodes when parent has anomalies.
- L2 source count and confidence displayed as pill badges; removed grey dot indicator.
- Richer L1/L2 node content, dynamic SVG width, reduced whitespace padding.
- Mindmap popup layout redesigned: auto-scale SVG, slide-in detail panel, toolbar legend.

### Added
- Info panel and legend in mindmap popup.
- Project name now displays as basename in mindmap popup header.
- Diff type tags on L1 feature list on the main page.

---

## [1.0.3] — 2026-05-09

### Added
- `mindmap-popup.html`: New dedicated popup window with SVG column tree view and
  visual indicators (anomaly, diff type, confidence).
- Mindmap navigation rewritten to use `sessionStorage` + `window.open` for popup mode.

### Removed
- V1 inline mindmap view removed from `index.html`, `styles.css`, `app.js`, and tests.

---

## [1.0.2] — 2026-05-09

### Added
- `renderMindmap`: Full mindmap render pipeline (all 10 unit assertions green).
- `loadMindmapL2`: Progressive L2 data loading with client-side cache.
- `switchToMindmap`: Navigation function with breadcrumb layer support.
- Mindmap View CSS styles.
- Topbar buttons and `mindmap-view` div in `index.html`.

---

## [1.0.1] — 2026-05-09

### Added
- Mindmap unit test harness (TDD scaffold, all tests initially failing).
- `createMindmapL1Node`: Renders L1 feature nodes in mindmap (T1–T3 pass).
- `_renderMindmapL2Section`: Renders L2 sub-feature sections (T4–T7 pass).
- `mindmapL2Cache` state, element refs, and button event listeners wired up.

---

## [1.0.0] — 2026-05-06

### Added
- Phase UI-1: Local Report Viewer — `ViewModelConverter`, static HTML/CSS/JS viewer.
- Phase UI-2: Local API Server — `UIServer` with 7 REST API endpoints, `JobStore`
  for async analysis jobs.
- Phase UI-3: Interactive Graph — Cytoscape.js-based graph with L1/L2/L3 navigation,
  `GraphViewModel_Converter`, `L2Generator`, 6 additional API endpoints.
- Integration tests: 36 end-to-end tests covering all 13 API endpoints.
- Self-analysis: The Door analyzed its own source (541 nodes, 13 features).
- `the-door ui` CLI command to launch the local UI server.
- `__init__.py` version bumped from 0.1.0 to 1.0.0.
- LICENSE copyright year updated to 2025–2026.

---

## Version History Reference

| Version | Release Date | Key Change |
|---------|-------------|-----------|
| 1.2.2 | 2026-05-23 | Multilang extraction + Viewer design system + Diff detail panel + 3 regression fixes |
| 1.2.1 | 2026-05-20 | L1 system prompt + L2 anomaly checklist + diff explanation prompt 強化 |
| 1.2.0 | 2026-05-18 | 增量分析 + Guidance Engine + CLI UX + MCP surface + Viewer 模組化 |
| 1.1.0 | 2026-05-13 | 使用者備註、輸出語言選擇、差異推論、Topbar 強化 |
| 1.0.6 | 2026-05-10 | `snapshot_write` MCP tool + `CLAUDE.md` agent orchestration + ProjectRegistry |
| 1.0.5 | 2026-05-09 | Dual license + bilingual README + `confidence_reason` |
| 1.0.4 | 2026-05-09 | Mindmap popup polish: CJK sizing, anomaly badges, SVG layout |
| 1.0.3 | 2026-05-09 | Mindmap V2 popup window (SVG column tree, sessionStorage navigation) |
| 1.0.2 | 2026-05-09 | Full mindmap render pipeline (renderMindmap, loadMindmapL2, CSS) |
| 1.0.1 | 2026-05-09 | Mindmap TDD scaffold + L1/L2 node builders |
| 1.0.0 | 2026-05-06 | Full release: Phase UI-1/2/3 Interactive Graph + 36 integration tests |
