# Requirements Document

## Introduction

Phase UI-1 Local Report Viewer 是 The Door 前端工作台的第一個正式實作階段。
目標是讓使用者能在本地瀏覽器中讀取真實的 `UpdateReport` JSON，以舊版、新版、差異三種模式檢視版本變更，並在右側詳情面板查看每個變更的 Before/After 對照與資料來源。

本階段包含兩個主要交付物：

1. **Python 端**：`the_door.core.ui.view_model` 模組（`build_update_report_view_model`、`export_update_report_view_model` 等函式已存在），本階段補強 PBT 與邊界測試覆蓋，不重寫現有邏輯。
2. **前端**：HTML/CSS/Vanilla JavaScript 的 Local Report Viewer，接入真實 `UpdateReport` JSON

設計原則：
- TDD first：所有資料轉換邏輯先有失敗測試，再實作。
- No hallucination：UI 不得顯示資料來源不存在的功能、風險或描述。
- Local-first：所有操作在本地完成，不產生外部網路請求。
- 最小技術棧：HTML + CSS + Vanilla JavaScript，不引入 React/TypeScript/Vite。
- Python 轉換函式放在既有 pytest + hypothesis 測試體系中。

---

## Glossary

- **UpdateReport**：`models.py::UpdateReport` 的 JSON 序列化輸出，由 `ReportRenderer.render_json()` 產生，包含 `l0_summary`、`l1_changes`、`l2_details`、`pipeline_summary`、`interrupted` 等欄位。
- **L1ChangeEntry**：`models.py::L1ChangeEntry`，`UpdateReport.l1_changes` 中的單一項目，包含 `feature_id`、`change_type`、`risk_flags`、`current_label`、`baseline_label`。
- **L2DetailEntry**：`models.py::L2DetailEntry`，`UpdateReport.l2_details` 中的單一項目，包含 `feature_id`、`change_type`、`current_label`、`current_description`、`baseline_label`、`baseline_description`、`scope_state`、`related_vulnerabilities`、`affected_relations`。
- **ViewModel**：由 `build_update_report_view_model()` 轉換出的瀏覽器可消費 JSON，包含 `mode`、`diff_available`、`summary`、`changes`、`details`、`change_counts`、`risk_counts`、`pipeline`、`interrupted`、`source` 欄位。`features` 欄位不存在於此 ViewModel，單版本模式另讀 L1 ViewModel。
- **L1 ViewModel**：由 `build_l1_view_model()` 轉換出的單版本 ViewModel，包含 `mode`、`diff_available`（固定為 `false`）、`summary`、`stats`、`features`、`relations`、`source` 欄位。
- **ViewModelConverter**：`the_door.core.ui.view_model` 模組，負責 `UpdateReport` → `ViewModel` 與 `L1Output` → `L1 ViewModel` 的轉換邏輯。
- **LocalViewer**：前端 HTML/CSS/Vanilla JS 應用，讀取 ViewModel JSON 並渲染三欄工作台。必須透過本地 HTTP server 啟動（如 `python -m http.server`），不支援直接 `file://` 開啟。
- **ChangeList**：左側欄位，顯示依風險優先排序的變更清單。
- **GraphCanvas**：中央欄位，顯示功能節點與差異狀態。
- **DetailPanel**：右側欄位，顯示選取變更的 Before/After 對照、scope 狀態、漏洞、受影響關係與資料來源。
- **TopBar**：頂部狀態列，顯示版本資訊、模式切換、分析時間等。
- **MissingValue**：當欄位不存在或為空字串時，UI 顯示的固定字串「未提供」（Python 常數 `MISSING_VALUE = "未提供"`）。
- **DiffState**：`NodeDiff.diff_state` 的可能值：`added`、`removed`、`attribute_changed`、`dependency_changed`、`unchanged`。
- **RiskFlag**：`L1ChangeEntry.risk_flags` 的可能值：`out_of_scope`、`vulnerability`、`semantic_drift`。
- **PBT**：Property-Based Testing，使用 `hypothesis` 函式庫對轉換函式進行屬性測試。

---

## Requirements

### Requirement 1：UpdateReport → ViewModel 轉換正確性

**User Story：** As a developer, I want the `ViewModelConverter` to correctly transform any valid `UpdateReport` JSON into a `ViewModel`, so that the frontend can render accurate version diff information without recalculating business logic.

#### Acceptance Criteria

1. WHEN a valid `UpdateReport` JSON with a non-empty `l1_changes` list is provided, THE `ViewModelConverter` SHALL produce a `ViewModel` where `diff_available` is `true`.
2. WHEN an `UpdateReport` JSON where `l1_changes` is absent OR is an empty list is provided, THE `ViewModelConverter` SHALL produce a `ViewModel` where `diff_available` is `false` and `changes` is an empty list.
3. THE `ViewModelConverter` SHALL count each `change_type` in `change_counts` to match the exact count of entries with that `change_type` in `l1_changes`.
4. THE `ViewModelConverter` SHALL count each `risk_flag` in `risk_counts` to match the exact count of entries containing that flag in `l1_changes`.
5. WHEN `baseline_label` or `baseline_description` is `null` or absent in `l2_details`, THE `ViewModelConverter` SHALL set the corresponding `before.label` or `before.description` to `MissingValue`.
6. WHEN `current_label` or `current_description` is `null` or absent in `l2_details`, THE `ViewModelConverter` SHALL set the corresponding `after.label` or `after.description` to `MissingValue`.
7. THE `ViewModelConverter` SHALL NOT copy `current_label` into `before.label` when `baseline_label` is absent.
8. THE `ViewModelConverter` SHALL NOT copy `baseline_label` into `after.label` when `current_label` is absent.
9. WHEN `l2_details` contains no entry for a given `feature_id`, THE `ViewModelConverter` SHALL still produce a `details` entry for that feature using `l1_changes` data, with `before` and `after` fields set to `MissingValue` where data is absent.

---

### Requirement 2：ViewModel 風險優先排序

**User Story：** As a developer, I want the `ViewModelConverter` to sort changes by risk priority, so that the frontend `ChangeList` always reflects the same ordering as the backend risk logic without duplicating sorting rules.

#### Acceptance Criteria

1. THE `ViewModelConverter` SHALL sort `changes` using the following multi-level key: (a) entries with `out_of_scope` risk flag sort before entries without it; (b) among ties, entries with `vulnerability` flag sort before entries without it; (c) among ties, entries with `semantic_drift` flag sort before entries without it; (d) among ties, `change_type` sorts in the order `added` → `attribute_changed` → `dependency_changed` → `removed`; (e) among ties, sort by `feature_id` ascending lexicographically. An entry with any risk flag always sorts before an entry with no risk flags, regardless of `change_type`.
2. THE `LocalViewer` SHALL render the `ChangeList` in the order provided by the `ViewModel` without applying additional sorting.

---

### Requirement 3：ViewModel 序列化往返一致性（Round-Trip）

**User Story：** As a developer, I want `export_update_report_view_model()` to produce a JSON file that round-trips correctly, so that the static viewer always reads the same data that was computed.

#### Acceptance Criteria

1. WHEN `export_update_report_view_model(input_path, output_path)` is called with a valid `UpdateReport` JSON file, THE `ViewModelConverter` SHALL write a JSON file to `output_path` that, when parsed, is structurally equal to the in-memory `ViewModel` returned by the function.
2. FOR ALL valid `UpdateReport` JSON inputs, parsing the written JSON file and calling `build_update_report_view_model()` on the original input SHALL produce structurally equivalent `ViewModel` dicts (same keys and values after JSON round-trip).
3. WHEN the written JSON file is read and re-parsed without modification, THE resulting dict SHALL be structurally equal to the original parsed `ViewModel` (idempotent parse — no data loss or type coercion).

---

### Requirement 4：前端三欄工作台佈局

**User Story：** As a user, I want to see a three-column workbench layout when I open the Local Report Viewer, so that I can navigate changes, view the graph, and inspect details simultaneously.

#### Acceptance Criteria

1. THE `LocalViewer` SHALL render a `TopBar`, a `ChangeList` column, a `GraphCanvas` column, and a `DetailPanel` column on the same screen.
2. THE `TopBar` SHALL display the `l0_summary` from the `ViewModel`.
3. THE `TopBar` SHALL display the mode indicator showing the current active mode (舊版 / 新版 / 差異).
4. WHEN `diff_available` is `false` in the `ViewModel`, THE `LocalViewer` SHALL disable the 差異 mode button and display an empty-state message indicating that diff data is unavailable.
5. WHEN `diff_available` is `true` in the `ViewModel`, THE `LocalViewer` SHALL activate 差異 mode as the default mode on load.
6. WHEN no item is selected, THE `DetailPanel` SHALL display an empty-state message prompting the user to select an item.

---

### Requirement 5：差異模式 ChangeList 與 GraphCanvas

**User Story：** As a user, I want to see a prioritized list of changes and a visual node grid in diff mode, so that I can quickly identify high-risk changes and navigate to their details.

#### Acceptance Criteria

1. WHEN 差異 mode is active, THE `ChangeList` SHALL display one entry per item in `ViewModel.changes`, in the order provided by the `ViewModel`.
2. WHEN 差異 mode is active, THE `ChangeList` SHALL display the `change_type` symbol (`+` for `added`, `-` for `removed`, `~` for `attribute_changed`, `!=` for `dependency_changed`) alongside each entry label.
3. WHEN 差異 mode is active, THE `GraphCanvas` SHALL display one node per item in `ViewModel.changes`, each showing the `change_type` symbol and the entry label.
4. WHEN 差異 mode is active, THE `TopBar` SHALL display the counts from `ViewModel.change_counts` for `added`, `removed`, and the sum of `attribute_changed` and `dependency_changed`.
5. WHEN 差異 mode is active and `ViewModel.risk_counts` contains non-zero values, THE `TopBar` SHALL display the non-zero risk counts.

---

### Requirement 6：Before/After 詳情面板

**User Story：** As a user, I want to click on a change and see its Before/After details with data source attribution, so that I can verify what changed and where the information comes from.

#### Acceptance Criteria

1. WHEN a change is selected in 差異 mode, THE `DetailPanel` SHALL display the `before.label`, `before.description`, `after.label`, and `after.description` from `ViewModel.details[feature_id]`.
2. WHEN `before.label` is `MissingValue`, THE `DetailPanel` SHALL display the literal string「未提供」and SHALL NOT substitute it with `after.label`.
3. WHEN `after.label` is `MissingValue`, THE `DetailPanel` SHALL display the literal string「未提供」and SHALL NOT substitute it with `before.label`.
4. WHEN `scope_state` is present in `ViewModel.details[feature_id]`, THE `DetailPanel` SHALL display the scope state value.
5. WHEN `scope_state` is `null` or absent, THE `DetailPanel` SHALL display「未提供」for the scope state field.
6. WHEN `related_vulnerabilities` is non-empty, THE `DetailPanel` SHALL display each vulnerability entry.
7. WHEN `related_vulnerabilities` is empty, THE `DetailPanel` SHALL display「未提供」for the vulnerabilities field.
8. WHEN `affected_relations` is non-empty, THE `DetailPanel` SHALL display each relation entry.
9. THE `DetailPanel` SHALL display the `source` field value from `ViewModel.details[feature_id]` as the data attribution label.

---

### Requirement 7：單版本模式（舊版 / 新版）

**User Story：** As a user, I want to switch to 舊版 or 新版 mode to view a single-version feature list, so that I can inspect the baseline or current state independently of the diff.

#### Acceptance Criteria

1. WHEN 舊版 or 新版 mode is selected, THE `LocalViewer` SHALL render the `ChangeList` as a feature list using the `L1 ViewModel.features` array loaded from a separate L1 JSON file, or display an empty-state message if the file is absent or the array is empty. The `L1 ViewModel` is produced by `build_l1_view_model()` and is a separate file from the `UpdateReport` ViewModel.
2. WHEN 舊版 or 新版 mode is active, THE `GraphCanvas` SHALL display feature nodes without `change_type` symbols.
3. WHEN 舊版 or 新版 mode is active, THE `DetailPanel` SHALL display the feature's `description`, `trigger_description`, `confidence`, `confidence_reason`, and `source_nodes` when a feature is selected.
4. WHEN `source_nodes` is empty, THE `DetailPanel` SHALL display「未提供」for the source nodes field.

---

### Requirement 8：空狀態與錯誤處理

**User Story：** As a user, I want to see clear error messages when data is missing or fails to load, so that I am never left with a blank screen or misleading content.

#### Acceptance Criteria

1. WHEN the `ViewModel` JSON file fails to load (network error or file not found), THE `LocalViewer` SHALL display an error message containing the file path and the HTTP status or error description.
2. WHEN the `ViewModel` JSON file is malformed and cannot be parsed, THE `LocalViewer` SHALL display an error message identifying the file and indicating a parse failure.
3. WHEN `diff_available` is `false`, THE `LocalViewer` SHALL display an empty-state message in the `ChangeList` indicating that no diff data is available.
4. IF the `ViewModel` contains a `changes` array with zero entries, THEN THE `LocalViewer` SHALL display an empty-state message in the `ChangeList` rather than a blank list.
5. THE `LocalViewer` SHALL NOT display a blank screen under any data loading or parsing failure condition.

---

### Requirement 9：本地優先與無外部網路請求

**User Story：** As a user, I want the Local Report Viewer to operate entirely from local files, so that it works in offline environments and does not leak project data to external services.

#### Acceptance Criteria

1. THE `LocalViewer` SHALL load all HTML, CSS, and JavaScript resources from local files only.
2. THE `LocalViewer` MUST be served via a local HTTP server (e.g., `python -m http.server`). Direct `file://` access is not supported due to browser CORS restrictions on `fetch()`.
3. WHEN the `LocalViewer` is started, loaded, mode is switched, a node is selected, or the `DetailPanel` is expanded, THE `LocalViewer` SHALL NOT produce any HTTP request to a host other than `127.0.0.1` or `localhost`.
4. THE `LocalViewer` SHALL NOT reference any CDN, external font service, external icon library, or remote analytics endpoint.
5. THE `LocalViewer` SHALL load the `ViewModel` JSON from a local relative path using `fetch()` with `cache: "no-store"`.

---

### Requirement 10：PBT — ViewModel 轉換屬性測試

**User Story：** As a developer, I want property-based tests for `build_update_report_view_model()` using Hypothesis, so that edge cases in arbitrary `UpdateReport` inputs are systematically discovered.

#### Acceptance Criteria

1. FOR ALL valid `UpdateReport`-shaped dicts generated by Hypothesis, THE `ViewModelConverter` SHALL produce a `ViewModel` where `change_counts` values sum to the total number of entries in `l1_changes`.
2. FOR ALL valid `UpdateReport`-shaped dicts generated by Hypothesis, THE `ViewModelConverter` SHALL produce a `ViewModel` where every `id` in `changes` corresponds to a `feature_id` present in `l1_changes`.
3. FOR ALL valid `UpdateReport`-shaped dicts generated by Hypothesis, THE `ViewModelConverter` SHALL produce a `ViewModel` where every key in `details` corresponds to an `id` present in `changes`.
4. FOR ALL valid `UpdateReport`-shaped dicts generated by Hypothesis where `l1_changes` is absent OR is an empty list, THE `ViewModelConverter` SHALL produce a `ViewModel` where `diff_available` is `false`.
5. FOR ALL valid `UpdateReport`-shaped dicts generated by Hypothesis, FOR EACH entry in `l2_details` where `baseline_label` is `null` or absent, THE `ViewModelConverter` SHALL produce a `ViewModel` where the corresponding `details[feature_id].before.label` equals `MISSING_VALUE` (「未提供」).
6. FOR ALL valid `UpdateReport`-shaped dicts generated by Hypothesis, FOR EACH entry in `l2_details` where `current_label` is `null` or absent, THE `ViewModelConverter` SHALL produce a `ViewModel` where the corresponding `details[feature_id].after.label` equals `MISSING_VALUE` (「未提供」).
7. FOR ALL valid `UpdateReport`-shaped dicts generated by Hypothesis, THE `ViewModelConverter` SHALL produce a `ViewModel` where the `changes` list length equals the number of entries in `l1_changes`.

---

### Requirement 11：資料來源顯示（防幻覺 UX）

**User Story：** As a user, I want every piece of information in the Detail Panel to show its data source, so that I can verify that the UI is not displaying invented content.

#### Acceptance Criteria

1. THE `DetailPanel` SHALL display the `source` field from `ViewModel.details[feature_id]` for every selected change.
2. WHEN the `source` field value is `"UpdateReport.l2_details"`, THE `DetailPanel` SHALL display this attribution string visibly.
3. WHEN the `source` field value is `"UpdateReport.l1_changes"` (fallback case with no `l2_details` entry), THE `DetailPanel` SHALL display this attribution string visibly.
4. THE `LocalViewer` SHALL NOT display any feature label, description, scope state, or vulnerability that is not present in the `ViewModel` received from the `ViewModelConverter`.
