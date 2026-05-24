# Changelog

All notable changes to The Door are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

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
