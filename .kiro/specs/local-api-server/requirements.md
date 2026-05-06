# Requirements Document

## Introduction

Phase UI-2 Local API Server 是 The Door 前端工作台的第二個實作階段。

Phase UI-1 已建立靜態前端 viewer（`docs/frontend-local-version-viewer/viewer/`），讀取預先產生的 ViewModel JSON 檔案。Phase UI-2 的目標是新增 `the-door ui <project-path>` 指令，啟動本地 HTTP server，讓前端 viewer 能動態讀取真實的本地分析資料，而不是靜態 mock。

本階段包含三個主要交付物：

1. **`the-door ui` CLI 指令**：啟動本地 HTTP server，提供靜態前端資源與 JSON API 端點。
2. **本地 HTTP Server**：使用 Python 標準函式庫（`http.server` / `socketserver`）實作，薄包裝既有 core 模組，不重寫分析邏輯。
3. **前端 viewer 升級**：從靜態 JSON 改為呼叫本地 API，並新增 pipeline progress 顯示。

設計原則：
- TDD first：所有 API 回應格式、資料轉換、錯誤處理，先有失敗測試，再實作。
- No hallucination：API 只回傳既有 core 模組的真實輸出，不補造欄位。
- Local-first：所有操作在本地完成，不產生外部網路請求。
- 最小依賴：MVP server 使用 Python 標準函式庫，不新增 FastAPI、Flask 或資料庫。
- 薄包裝原則：API 端點只包裝既有 core，不重寫 diff/scope/timeline 邏輯。

---

## Glossary

- **UI_Server**：Phase UI-2 新增的本地 HTTP server，使用 Python 標準函式庫（`http.server` / `socketserver`）實作，監聽 `127.0.0.1:<port>`。
- **CLI_UI_Command**：`the-door ui <project-path>` 指令，負責啟動 `UI_Server` 並開啟瀏覽器。
- **Project_Root**：使用者傳入的 `<project-path>` 參數，指向含有 `.the-door/` 目錄的專案根目錄。
- **DotTheDoor_Dir**：`<project-path>/.the-door/` 目錄，存放 snapshots、scope definitions、doubts 等本地分析資料。
- **API_Handler**：`UI_Server` 中處理 `/api/*` 路徑的請求處理器，負責呼叫既有 core 模組並回傳 JSON。
- **Static_Handler**：`UI_Server` 中處理靜態前端資源（HTML/CSS/JS）的請求處理器，服務 `docs/frontend-local-version-viewer/viewer/` 目錄下的檔案。
- **SnapshotStore**：`the_door.core.diff.snapshot_store.SnapshotStore`，管理 `.the-door/snapshots/` 下的版本快照。建構時接收 `project_root: Path`，呼叫方式為 `SnapshotStore(project_root).list_snapshots()`。
- **DoubtStore**：`the_door.core.scope.doubt_store.DoubtStore`，管理 `.the-door/doubts/` 下的疑義記錄。建構時接收 `project_root: Path`，呼叫方式為 `DoubtStore(project_root).list_doubts()`。`DoubtRecord` 的欄位名稱為 `source_node`（語意等同 feature_id），API 序列化時以 `source_node` 欄位名稱回傳。
- **TimelineEngine**：`the_door.core.timeline.timeline_engine.TimelineEngine`，計算多版本時間軸分析（pure function，無 I/O）。
- **PipelineOrchestrator**：`the_door.core.pipeline.pipeline_orchestrator.PipelineOrchestrator`，執行完整版本更新管線。呼叫方式為先建構 `PipelineConfig(old_path=Path(old_path), new_path=Path(new_path))` 再呼叫 `orchestrator.run(config, progress_callback=callback)`，回傳 `PipelineResult`。`run()` 在非主執行緒中不安裝 SIGINT handler（設計如此，背景執行緒安全）。
- **ReportRenderer**：`the_door.core.pipeline.report_renderer.ReportRenderer`，將 `PipelineResult` 渲染為 `UpdateReport` JSON。
- **UpdateReport**：`ReportRenderer.render_json()` 的輸出（回傳 `dict`），由 `UI_Server` 持久化為 `DotTheDoor_Dir/update-report-<generated_at_iso>.json`（`generated_at` 中的 `:` 替換為 `-`，確保 Windows 檔名相容）。「最新報告」由 `generated_at` 欄位決定；若 `generated_at` 無法解析，以檔案 mtime 作為 fallback。
- **ProgressEvent**：`POST /api/update` 執行期間，`UI_Server` 透過 Server-Sent Events（SSE）或輪詢機制向前端回報的步驟進度訊息。
- **API_Error_Response**：所有 API 端點在錯誤時回傳的統一 JSON 格式：`{"error": {"code": "string", "message": "string", "source": "string"}}`。
- **Port**：`UI_Server` 監聽的 TCP 端口，預設 `8765`，可透過 `--port` 選項覆蓋。
- **Viewer_Dir**：前端靜態資源目錄，路徑為 `docs/frontend-local-version-viewer/viewer/`（相對於 The Door 套件安裝位置）。
- **UpdateJob**：`POST /api/update` 觸發的非同步管線執行任務，具有唯一 `job_id`，可透過 `GET /api/update/status/<job_id>` 查詢進度。

---

## Requirements

### Requirement 1：`the-door ui` CLI 指令

**User Story：** As a developer, I want to run `the-door ui <project-path>` to start a local HTTP server and open the viewer in my browser, so that I can inspect live project analysis data without manually setting up a server.

#### Acceptance Criteria

1. WHEN `the-door ui <project-path>` is executed with a valid directory path, THE `CLI_UI_Command` SHALL start the `UI_Server` on `http://127.0.0.1:<port>` and print the URL to stdout.
2. WHEN `the-door ui <project-path>` is executed with a `--port <N>` option, THE `CLI_UI_Command` SHALL start the `UI_Server` on the specified port `N` instead of the default port `8765`.
3. WHEN `the-door ui <project-path>` is executed with a `--no-browser` flag, THE `CLI_UI_Command` SHALL start the `UI_Server` without opening a browser tab.
4. WHEN `the-door ui <project-path>` is executed without `--no-browser`, THE `CLI_UI_Command` SHALL attempt to open `http://127.0.0.1:<port>` in the default system browser after the server is ready.
5. WHEN `<project-path>` does not exist or is not a directory, THE `CLI_UI_Command` SHALL print an error message to stderr and exit with a non-zero status code without starting the server.
6. WHEN the specified port is already in use, THE `CLI_UI_Command` SHALL print an error message identifying the port conflict and exit with a non-zero status code.
7. WHEN the `UI_Server` is running and the user presses Ctrl+C, THE `CLI_UI_Command` SHALL shut down the server gracefully and exit with status code 0.
8. WHEN `<project-path>` exists but the `DotTheDoor_Dir` does not exist, THE `CLI_UI_Command` SHALL still start the server and serve the viewer; the API endpoints SHALL return appropriate empty-state responses rather than errors.

---

### Requirement 2：靜態資源服務

**User Story：** As a developer, I want the local server to serve the frontend viewer files, so that I can open the viewer in a browser without running a separate static file server.

#### Acceptance Criteria

1. WHEN a GET request is made to `/` or `/index.html`, THE `Static_Handler` SHALL serve the `index.html` file from `Viewer_Dir` with HTTP status 200.
2. WHEN a GET request is made to a path matching a file in `Viewer_Dir` (e.g., `/styles.css`, `/app.js`), THE `Static_Handler` SHALL serve that file with the correct `Content-Type` header and HTTP status 200.
3. WHEN a GET request is made to a path that does not match any file in `Viewer_Dir` and does not start with `/api/`, THE `Static_Handler` SHALL return HTTP status 404.
4. THE `Static_Handler` SHALL set `Content-Type: text/html; charset=utf-8` for `.html` files, `text/css; charset=utf-8` for `.css` files, and `application/javascript; charset=utf-8` for `.js` files.
5. THE `Static_Handler` SHALL set `Content-Type: application/json; charset=utf-8` for `.json` files served from `Viewer_Dir`.
6. THE `UI_Server` SHALL NOT serve any files outside of `Viewer_Dir` via the static handler (path traversal prevention).

---

### Requirement 3：`GET /api/project` — 專案狀態端點

**User Story：** As a frontend developer, I want a `/api/project` endpoint that returns the project path and available data status, so that the viewer can display accurate project metadata and guide users when data is missing.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/project`, THE `API_Handler` SHALL return HTTP status 200 with a JSON body containing `project_path` (absolute path string), `dot_the_door_exists` (boolean), and `available_data` (object).
2. WHEN `DotTheDoor_Dir` exists, THE `API_Handler` SHALL set `dot_the_door_exists` to `true` in the response.
3. WHEN `DotTheDoor_Dir` does not exist, THE `API_Handler` SHALL set `dot_the_door_exists` to `false` and set all fields in `available_data` to `false`.
4. THE `available_data` object SHALL contain boolean fields: `has_snapshots` (true if `SnapshotStore.list_snapshots()` returns at least one snapshot), `has_latest_report` (true if a latest `UpdateReport` JSON file exists in `DotTheDoor_Dir`), `has_doubts` (true if `DoubtStore.list_doubts()` returns at least one record), `has_scope_config` (true if `.the-door/scope-config.json` exists).
5. IF an exception occurs while reading project data, THEN THE `API_Handler` SHALL return HTTP status 500 with an `API_Error_Response` body.

---

### Requirement 4：`GET /api/snapshots` — 快照列表端點

**User Story：** As a frontend developer, I want a `/api/snapshots` endpoint that returns the list of available version snapshots, so that the viewer can offer snapshot selection for diff and timeline views.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/snapshots`, THE `API_Handler` SHALL instantiate `SnapshotStore(project_root)` and call `.list_snapshots()`, then return HTTP status 200 with a JSON body containing a `snapshots` array.
2. WHEN `SnapshotStore.list_snapshots()` returns an empty list, THE `API_Handler` SHALL return HTTP status 200 with `{"snapshots": []}`.
3. EACH snapshot entry in the `snapshots` array SHALL contain at minimum: `version_id` (string), `timestamp` (ISO 8601 string), `trigger` (string), `label` (string or null), `git_tags` (array of strings).
4. THE `snapshots` array SHALL be ordered by `timestamp` descending (newest first).
5. IF `SnapshotStore.list_snapshots()` raises an exception, THEN THE `API_Handler` SHALL return HTTP status 500 with an `API_Error_Response` body containing `"code": "snapshot_read_error"`.

---

### Requirement 5：`GET /api/report/latest` — 最新報告端點

**User Story：** As a frontend developer, I want a `/api/report/latest` endpoint that returns the latest UpdateReport, so that the viewer can display the most recent version diff without requiring the user to specify a file path.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/report/latest` and a latest `UpdateReport` JSON file exists in `DotTheDoor_Dir`, THE `API_Handler` SHALL return HTTP status 200 with the parsed `UpdateReport` JSON as the response body.
2. WHEN no `UpdateReport` JSON file exists in `DotTheDoor_Dir`, THE `API_Handler` SHALL return HTTP status 404 with an `API_Error_Response` body containing `"code": "no_report_found"`.
3. WHEN the latest `UpdateReport` JSON file exists but cannot be parsed as valid JSON, THE `API_Handler` SHALL return HTTP status 500 with an `API_Error_Response` body containing `"code": "report_parse_error"`.
4. THE `API_Handler` SHALL determine "latest" by selecting the `UpdateReport` file with the most recent `generated_at` timestamp among all `update-report-*.json` files in `DotTheDoor_Dir`. IF `generated_at` cannot be parsed from a file, THE `API_Handler` SHALL use that file's filesystem mtime as a fallback for ordering.
5. IF an unexpected exception occurs while reading the report, THEN THE `API_Handler` SHALL return HTTP status 500 with an `API_Error_Response` body.

---

### Requirement 6：`POST /api/update` — 觸發管線端點

**User Story：** As a developer, I want a `/api/update` endpoint that triggers the update pipeline, so that I can re-analyze the project from the viewer without switching to the terminal.

#### Acceptance Criteria

1. WHEN a POST request is made to `/api/update` with a valid JSON body containing `old_path` and `new_path` fields, THE `API_Handler` SHALL start an `UpdateJob` by constructing a `PipelineConfig(old_path=Path(old_path), new_path=Path(new_path))` and calling `PipelineOrchestrator().run(config, progress_callback=...)` in a background thread, then return HTTP status 202 with a JSON body containing `job_id` (string).
2. WHEN `old_path` or `new_path` is missing from the request body, THE `API_Handler` SHALL return HTTP status 400 with an `API_Error_Response` body containing `"code": "missing_required_field"`.
3. WHEN `old_path` or `new_path` does not exist as a directory on the filesystem, THE `API_Handler` SHALL return HTTP status 400 with an `API_Error_Response` body containing `"code": "invalid_path"`. This validation MUST be performed in the `API_Handler` layer before constructing `PipelineConfig` or invoking `PipelineOrchestrator`; the handler SHALL NOT rely on `PipelineError` from the orchestrator to detect missing paths.
4. WHEN `old_path` equals `new_path`, THE `API_Handler` SHALL return HTTP status 400 with an `API_Error_Response` body containing `"code": "same_path"`.
5. WHILE an `UpdateJob` is running, THE `UI_Server` SHALL accept at most one concurrent `UpdateJob`; a second POST to `/api/update` SHALL return HTTP status 409 with an `API_Error_Response` body containing `"code": "job_already_running"`.
6. THE `API_Handler` SHALL NOT block the HTTP server while `PipelineOrchestrator.run()` is executing; the pipeline MUST run in a separate thread.
7. WHEN `PipelineOrchestrator.run()` completes successfully, THE `UI_Server` SHALL call `ReportRenderer().render_json(pipeline_result)` to obtain the `UpdateReport` dict, then persist it as `DotTheDoor_Dir/update-report-<generated_at>.json` (with `:` replaced by `-` in the timestamp for Windows filename compatibility), using `encoding="utf-8"`.

---

### Requirement 7：`GET /api/update/status/<job_id>` — 管線進度端點

**User Story：** As a developer, I want to poll the pipeline progress from the viewer, so that I can see which step is currently running and how long each step took.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/update/status/<job_id>` for a known `job_id`, THE `API_Handler` SHALL return HTTP status 200 with a JSON body containing `job_id`, `status` (one of `"running"`, `"completed"`, `"failed"`), `steps` (array of completed step records), and `current_step` (string or null).
2. WHEN the `UpdateJob` is still running, THE `API_Handler` SHALL return `"status": "running"` and populate `current_step` with the name of the step currently executing.
3. WHEN the `UpdateJob` has completed successfully, THE `API_Handler` SHALL return `"status": "completed"`, `current_step` as `null`, and `steps` containing all step records with `step_name`, `status`, and `duration_ms`.
4. WHEN the `UpdateJob` has failed, THE `API_Handler` SHALL return `"status": "failed"`, `current_step` as `null`, and include `error_message` in the response body.
5. WHEN a GET request is made to `/api/update/status/<job_id>` for an unknown `job_id`, THE `API_Handler` SHALL return HTTP status 404 with an `API_Error_Response` body containing `"code": "job_not_found"`.
6. EACH step record in the `steps` array SHALL contain: `step_name` (string), `status` (string), `duration_ms` (integer or null), `error_message` (string or null).

---

### Requirement 8：`GET /api/doubts` — 疑義列表端點

**User Story：** As a developer, I want a `/api/doubts` endpoint that returns the current list of active doubts, so that the viewer can display scope verification issues alongside the diff view.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/doubts`, THE `API_Handler` SHALL instantiate `DoubtStore(project_root)` and call `.list_doubts()`, then return HTTP status 200 with a JSON body containing a `doubts` array and a `summary` object.
2. WHEN `DoubtStore.list_doubts()` returns an empty list, THE `API_Handler` SHALL return HTTP status 200 with `{"doubts": [], "summary": {"total": 0}}`.
3. EACH doubt entry in the `doubts` array SHALL contain at minimum: `doubt_id` (string), `doubt_type` (string), `state` (string, mapped from `current_state`), `source_node` (string, the feature_id this doubt is associated with), `created_at` (ISO 8601 string), `assignee` (string or null, mapped from `assigned_to`).
4. THE `summary` object SHALL contain `total` (integer count of all doubts returned).
5. IF `DoubtStore.list_doubts()` raises an exception, THEN THE `API_Handler` SHALL return HTTP status 500 with an `API_Error_Response` body containing `"code": "doubt_read_error"`.

---

### Requirement 9：`GET /api/timeline` — 時間軸端點

**User Story：** As a developer, I want a `/api/timeline` endpoint that returns the feature evolution timeline, so that the viewer can display semantic drift and feature history without requiring a separate CLI command.

#### Acceptance Criteria

1. WHEN a GET request is made to `/api/timeline` and at least one snapshot exists, THE `API_Handler` SHALL instantiate `SnapshotStore(project_root)` and call `.list_snapshots()` to load all snapshots, then call `TimelineEngine.analyze()` with those snapshots, and return HTTP status 200 with the `TimelineResult` serialized as JSON.
2. WHEN no snapshots exist, THE `API_Handler` SHALL return HTTP status 200 with a JSON body representing an empty `TimelineResult`: `{"snapshot_count": 0, "time_range_start": null, "time_range_end": null, "feature_timelines": [], "summary": {"active_count": 0, "removed_count": 0, "total_drift_events": 0}}`.
3. THE `TimelineResult` JSON body SHALL contain: `snapshot_count` (integer), `time_range_start` (ISO 8601 string or null), `time_range_end` (ISO 8601 string or null), `feature_timelines` (array), `summary` (object with `active_count`, `removed_count`, `total_drift_events`).
4. IF `SnapshotStore.list_snapshots()` or `TimelineEngine.analyze()` raises an exception, THEN THE `API_Handler` SHALL return HTTP status 500 with an `API_Error_Response` body containing `"code": "timeline_error"`.

---

### Requirement 10：統一 API 錯誤格式

**User Story：** As a frontend developer, I want all API error responses to follow a consistent JSON structure, so that the viewer can handle errors uniformly without special-casing each endpoint.

#### Acceptance Criteria

1. THE `API_Handler` SHALL return all error responses with `Content-Type: application/json; charset=utf-8`.
2. WHEN any API endpoint returns an HTTP error status (4xx or 5xx), THE response body SHALL be a JSON object with an `"error"` key containing `"code"` (string), `"message"` (string), and `"source"` (string identifying the endpoint or module that raised the error).
3. THE `API_Handler` SHALL return HTTP status 405 with an `API_Error_Response` body containing `"code": "method_not_allowed"` when an HTTP method other than the documented method is used on any `/api/*` endpoint.
4. THE `API_Handler` SHALL return HTTP status 400 with an `API_Error_Response` body containing `"code": "invalid_json"` when a POST request body cannot be parsed as JSON.
5. FOR ALL API endpoints, THE `API_Handler` SHALL set the `Access-Control-Allow-Origin: *` response header to allow the frontend to call the API from the same local origin.

---

### Requirement 11：前端 viewer 升級 — 動態 API 呼叫

**User Story：** As a developer, I want the frontend viewer to fetch data from the local API instead of static JSON files, so that it always reflects the current state of the project without requiring manual file regeneration.

#### Acceptance Criteria

1. WHEN the viewer loads, THE `LocalViewer` SHALL fetch project status from `GET /api/project` and display `dot_the_door_exists` and `available_data` in the UI.
2. WHEN `available_data.has_latest_report` is `true`, THE `LocalViewer` SHALL fetch the report from `GET /api/report/latest` and use it as the primary data source instead of the static `update-view-model.json` file.
3. WHEN `available_data.has_snapshots` is `true`, THE `LocalViewer` SHALL fetch the snapshot list from `GET /api/snapshots` and display it in a version selector component.
4. WHEN the user triggers a re-analysis, THE `LocalViewer` SHALL display a form or modal prompting the user to enter `old_path` and `new_path` (absolute directory paths on the local filesystem). After the user confirms, THE `LocalViewer` SHALL POST to `/api/update` with those paths, receive the `job_id`, and begin polling `GET /api/update/status/<job_id>` to display pipeline progress.
5. WHILE an `UpdateJob` is running, THE `LocalViewer` SHALL display a `PipelineProgress` component showing the `current_step` and the list of completed steps with their `duration_ms`.
6. WHEN the `UpdateJob` status becomes `"completed"`, THE `LocalViewer` SHALL automatically refresh the report by fetching `GET /api/report/latest` and re-rendering the viewer.
7. WHEN any API call returns an error response, THE `LocalViewer` SHALL display the `error.message` from the `API_Error_Response` body and SHALL NOT display a blank screen.
8. THE `LocalViewer` SHALL NOT make any HTTP requests to hosts other than `127.0.0.1` or `localhost`.

---

### Requirement 12：本地優先與安全性

**User Story：** As a developer, I want the local server to be safe to run on my machine, so that it does not expose project data to external networks or allow path traversal attacks.

#### Acceptance Criteria

1. THE `UI_Server` SHALL bind exclusively to `127.0.0.1` (loopback interface) and SHALL NOT bind to `0.0.0.0` or any external network interface.
2. THE `Static_Handler` SHALL resolve all requested file paths relative to `Viewer_Dir` and SHALL reject any path that, after normalization, resolves outside of `Viewer_Dir`.
3. THE `API_Handler` SHALL resolve all file paths relative to `Project_Root` and SHALL reject any path that, after normalization, resolves outside of `Project_Root`.
4. THE `UI_Server` SHALL NOT make any outbound HTTP requests to external hosts during normal operation (project data reading, API responses, static file serving).
5. WHEN `POST /api/update` is called, THE `API_Handler` SHALL validate that `old_path` and `new_path` are subdirectories of or equal to `Project_Root` before constructing `PipelineConfig` or passing them to `PipelineOrchestrator`. This check MUST occur in the `API_Handler` layer prior to any orchestrator invocation.

---

### Requirement 13：PBT — API 回應格式屬性測試

**User Story：** As a developer, I want property-based tests for the API response serialization functions, so that edge cases in arbitrary core module outputs are systematically discovered.

#### Acceptance Criteria

1. FOR ALL valid `VersionSnapshot` lists generated by Hypothesis, THE `API_Handler` serialization for `/api/snapshots` SHALL produce a JSON-serializable dict where every entry contains `version_id`, `timestamp`, `trigger`, `label`, and `git_tags`.
2. FOR ALL valid `DoubtRecord` lists generated by Hypothesis, THE `API_Handler` serialization for `/api/doubts` SHALL produce a JSON-serializable dict where every entry contains `doubt_id`, `doubt_type`, `state`, `source_node`, and `created_at`.
3. FOR ALL valid `TimelineResult` objects generated by Hypothesis, THE `API_Handler` serialization for `/api/timeline` SHALL produce a JSON-serializable dict that contains a `snapshot_count` field of integer type and a `feature_timelines` field of array type.
4. FOR ALL valid `UpdateReport` dicts, THE round-trip `json.dumps(json.loads(json.dumps(report)))` SHALL produce a dict structurally equal to the original (idempotent JSON serialization).
5. FOR ALL `API_Error_Response` dicts generated by the `API_Handler`, THE response SHALL contain `"error"` with non-empty `"code"`, `"message"`, and `"source"` string fields.

