# Implementation Tasks

## TDD 執行原則

每個 Python 任務遵循：先寫失敗測試 → 確認失敗 → 實作最小邏輯 → 測試通過。
前端任務遵循：先確認 API 回應格式 → 實作 JS 呼叫邏輯 → 驗證行為。

---

## Task 1: `UpdateJob` + `JobStore`（in-memory 狀態管理）

**對應 Req 6 AC1/AC5/AC6、Req 7 AC1–AC5、Design `job_store.py`**

- [x] 1.1 建立 `tests/unit/core/ui/test_job_store.py`，先寫失敗測試：
  - `test_create_job_returns_job`：`try_create_job()` 回傳 `UpdateJob`，`status="running"`
  - `test_create_job_when_running_returns_none`：已有 running job → `try_create_job()` 回傳 `None`
  - `test_get_job_running`：`get_job(job_id)` 回傳 running job
  - `test_get_job_completed`：`complete_job()` 後 `get_job()` 回傳 `status="completed"`
  - `test_get_job_unknown_returns_none`：未知 job_id → `get_job()` 回傳 `None`
  - `test_complete_job`：`complete_job(job_id)` 後 `has_running_job=False`
  - `test_fail_job`：`fail_job(job_id, "err")` 後 `status="failed"`, `error_message="err"`
  - `test_update_step_parses_completed_message`：傳入含 `✓` 的訊息 → `steps` 新增一筆 `status="completed"`，`current_step=None`
  - `test_update_step_parses_failed_message`：傳入含 `✗` 的訊息 → `steps` 新增一筆 `status="failed"`
  - `test_update_step_parses_skipped_message`：傳入含 `⊘` 的訊息 → `steps` 新增一筆 `status="skipped"`
  - `test_update_step_sets_current_step`：傳入不含 `✓`/`✗`/`⊘` 的步驟訊息 → `current_step` 更新
  - `test_update_step_thread_safety`：兩個執行緒同時呼叫 `update_step()`，不拋出例外，`steps` 長度正確
- [x] 1.2 建立 `the_door/src/the_door/core/ui/job_store.py`：
  - `UpdateJob` dataclass（非 frozen）：`job_id`, `status`, `current_step`, `steps`, `error_message`, `_lock`
  - `update_step(msg)` 使用 `self._lock`，依 Unicode 符號（`✓`/`✗`/`⊘`）解析，step_name 從 `[步驟 N/M] <symbol> <step_name>` 格式提取
  - `JobStore`：`try_create_job()`, `get_job()`, `complete_job()`, `fail_job()`, `has_running_job`
  - 所有讀寫操作使用 `threading.Lock` 保護
- [x] 1.3 執行測試，確認全部通過

**Checkpoint**：`pytest tests/unit/core/ui/test_job_store.py` 全部通過

---

## Task 2: `StaticHandler`（靜態資源服務）

**對應 Req 2、Req 12 AC2、Design `static_handler.py`**

- [x] 2.1 建立 `tests/unit/core/ui/test_static_handler.py`，先寫失敗測試：
  - `test_serve_index_html`：GET `/index.html` → 200, `text/html; charset=utf-8`
  - `test_serve_root_redirects_to_index`：GET `/` → 200, 回傳 `index.html` 內容
  - `test_serve_css_correct_content_type`：GET `/styles.css` → 200, `text/css; charset=utf-8`
  - `test_serve_js_correct_content_type`：GET `/app.js` → 200, `application/javascript; charset=utf-8`
  - `test_serve_json_correct_content_type`：GET `/data/foo.json` → 200, `application/json; charset=utf-8`
  - `test_serve_missing_file_returns_404`：GET `/nonexistent.txt` → 404（路徑合法但檔案不存在）
  - `test_path_traversal_rejected`：GET `/../secret.txt` → `resolve_path()` 回傳 `None`，`serve()` 回傳 403
  - `test_path_traversal_encoded_dots_rejected`：GET `/%2e%2e/secret.txt` → `resolve_path()` 回傳 `None`，`serve()` 回傳 403
- [x] 2.2 建立 `the_door/src/the_door/core/ui/static_handler.py`：
  - `StaticHandler.__init__(viewer_dir: Path)`：`self._viewer_dir = viewer_dir.resolve()`
  - `resolve_path(request_path: str) -> Path | None`：正規化後若路徑在 `_viewer_dir` 之外回傳 `None`（403）；路徑合法但檔案不存在時回傳對應 Path（`serve()` 再判斷 404）
  - `serve(request_path: str) -> tuple[int, str, bytes]`：先呼叫 `resolve_path()`，`None` → 403；再檢查 `path.exists()`，不存在 → 404；否則 200
  - `CONTENT_TYPES` dict
- [x] 2.3 執行測試，確認全部通過

**Checkpoint**：`pytest tests/unit/core/ui/test_static_handler.py` 全部通過

---

## Task 3: `serializers.py`（core 物件序列化）

**對應 Req 4 AC3、Req 8 AC3、Req 9 AC2/AC3、Req 13、Design `serializers.py`**

- [x] 3.1 建立 `tests/unit/core/ui/test_serializers.py`，先寫失敗測試：
  - `test_serialize_snapshot_fields`：`VersionSnapshot` → 包含 `version_id`, `timestamp`, `trigger`, `label`, `git_tags`
  - `test_serialize_snapshot_null_label`：`label=None` → `"label": null`
  - `test_serialize_doubt_field_mapping`：`current_state` → `state`，`assigned_to` → `assignee`
  - `test_serialize_doubt_null_assignee`：`assigned_to=None` → `"assignee": null`
  - `test_serialize_timeline_result`：包含 `snapshot_count`, `time_range_start`, `time_range_end`, `feature_timelines`, `summary`
  - `test_empty_timeline_result`：`snapshot_count=0`, `time_range_start=null`, `time_range_end=null`, `feature_timelines=[]`
- [x] 3.2 建立 `the_door/src/the_door/core/ui/serializers.py`：
  - `serialize_snapshot(snapshot: VersionSnapshot) -> dict`
  - `serialize_doubt(doubt: DoubtRecord) -> dict`（`current_state → state`，`assigned_to → assignee`）
  - `serialize_timeline_result(result: TimelineResult) -> dict`
  - `empty_timeline_result() -> dict`
- [x] 3.3 執行測試，確認全部通過

**Checkpoint**：`pytest tests/unit/core/ui/test_serializers.py` 全部通過

---

## Task 4: `APIHandlers`（API 端點業務邏輯）

**對應 Req 3–9、Req 10、Req 12 AC3/AC5、Design `api_handlers.py`**

- [x] 4.1 建立 `tests/unit/core/ui/test_api_handlers.py`，先寫失敗測試（mock 所有 core 模組）：
  - `test_get_project_dot_dir_exists`：`.the-door/` 存在 → `dot_the_door_exists=true`
  - `test_get_project_dot_dir_missing`：`.the-door/` 不存在 → `dot_the_door_exists=false`，`available_data` 全 false
  - `test_get_project_available_data_fields`：mock `list_snapshots()` 回傳 1 筆、`list_doubts()` 回傳空、`scope-config.json` 存在 → `has_snapshots=true`, `has_doubts=false`, `has_scope_config=true`, `has_latest_report` 依檔案存在與否
  - `test_get_project_exception_returns_500`：讀取時拋出例外 → 500
  - `test_get_snapshots_returns_sorted_list`：mock `list_snapshots()` 回傳 2 筆 → 依 timestamp 降序
  - `test_get_snapshots_empty`：`list_snapshots()` 回傳 `[]` → `{"snapshots": []}`
  - `test_get_snapshots_exception_returns_500`：拋出例外 → 500, `code="snapshot_read_error"`
  - `test_get_report_latest_found`：存在 `update-report-*.json` → 200, 回傳 JSON 內容
  - `test_get_report_latest_not_found`：無檔案 → 404, `code="no_report_found"`
  - `test_get_report_latest_invalid_json`：檔案存在但 JSON 損壞 → 500, `code="report_parse_error"`
  - `test_get_report_latest_selects_newest_by_generated_at`：2 個檔案，依 `generated_at` 選最新
  - `test_get_report_latest_fallback_to_mtime`：`generated_at` 無法解析 → 依 mtime 選最新
  - `test_post_update_missing_field`：body 缺少 `old_path` → 400, `code="missing_required_field"`
  - `test_post_update_invalid_path`：路徑不存在或不是目錄 → 400, `code="invalid_path"`
  - `test_post_update_same_path`：`old_path == new_path` → 400, `code="same_path"`
  - `test_post_update_job_already_running`：已有 running job → 409, `code="job_already_running"`
  - `test_post_update_path_outside_project_root`：路徑在 `project_root` 之外 → 400, `code="invalid_path"`
  - `test_post_update_success_returns_202_with_job_id`：合法請求 → 202, 含 `job_id`
  - `test_post_update_pipeline_runs_in_background`：mock `threading.Thread`，驗證 `.start()` 被呼叫一次，且 `handle_post_update()` 立即回傳 202（不等待管線完成）
  - `test_post_update_persists_report_on_completion`：管線完成後，`DotTheDoor_Dir` 下存在 `update-report-*.json`
  - `test_get_update_status_running`：running job → `status="running"`, `current_step` 非 null
  - `test_get_update_status_completed`：completed job → `status="completed"`, `current_step=null`, `steps` 非空
  - `test_get_update_status_failed`：failed job → `status="failed"`, `error_message` 非 null
  - `test_get_update_status_unknown_job`：未知 job_id → 404, `code="job_not_found"`
  - `test_get_doubts_returns_list`：mock `list_doubts()` 回傳 1 筆 → `doubts` 長度 1, `summary.total=1`
  - `test_get_doubts_empty`：`list_doubts()` 回傳 `[]` → `{"doubts": [], "summary": {"total": 0}}`
  - `test_get_doubts_exception_returns_500`：拋出例外 → 500, `code="doubt_read_error"`
  - `test_get_timeline_with_snapshots`：mock `list_snapshots()` 回傳 1 筆 → 呼叫 `TimelineEngine().analyze()`，回傳 200
  - `test_get_timeline_no_snapshots`：`list_snapshots()` 回傳 `[]` → 回傳 `empty_timeline_result()`，不呼叫 `TimelineEngine`
  - `test_get_timeline_exception_returns_500`：拋出例外 → 500, `code="timeline_error"`
- [x] 4.2 建立 `the_door/src/the_door/core/ui/api_handlers.py`：
  - `APIHandlers.__init__(project_root: Path, job_store: JobStore)`
  - 實作 7 個 `handle_*` 方法，每個回傳 `(status_code: int, body: dict)`
  - `_run_pipeline_job(job, old_path, new_path)`：背景執行緒邏輯
  - `_persist_report(report: dict)`：持久化，`:` 替換 `-`，`encoding="utf-8"`
  - `_find_latest_report_path() -> Path | None`：依 `generated_at`（fallback: mtime）
  - `_make_error(code, message, source) -> dict`：靜態方法
- [x] 4.3 執行測試，確認全部通過

**Checkpoint**：`pytest tests/unit/core/ui/test_api_handlers.py` 全部通過

---

## Task 5: `UIServer` + `_RequestHandler`（HTTP server + 請求路由）

**對應 Req 1 AC1/AC6/AC7、Req 10 AC3/AC4/AC5、Req 12 AC1、Design `server.py`**

- [x] 5.1 建立 `tests/unit/core/ui/test_server.py`，先寫失敗測試：
  - `test_method_not_allowed_on_get_endpoint`：對 GET-only 端點（如 `/api/project`）發 POST → 405, `code="method_not_allowed"`
  - `test_invalid_json_body_returns_400`：POST `/api/update` body 非 JSON → 400, `code="invalid_json"`
  - `test_cors_header_present`：任意 API 請求 → response 含 `Access-Control-Allow-Origin: *`
- [x] 5.2 建立 `the_door/src/the_door/core/ui/server.py`：
  - `UIServer.__init__(project_root, viewer_dir, port=8765)`：建立 `JobStore`、`APIHandlers`、`StaticHandler`
  - `UIServer.start()`：`ThreadingHTTPServer(("127.0.0.1", port), _RequestHandler).serve_forever()`；捕捉 `OSError` 讓呼叫方處理
  - `UIServer.shutdown()`：呼叫 `server.shutdown()`
  - `UIServer.url` property
  - `_RequestHandler(BaseHTTPRequestHandler)`：
    - `do_GET()`：路由到 `APIHandlers` 或 `StaticHandler`
    - `do_POST()`：只處理 `/api/update`，解析 JSON body
    - `_send_json(status, body)`：序列化 + 設定 headers（含 `Access-Control-Allow-Origin: *`）
    - `_send_api_error(status, code, message, source)`
    - `log_message()` 覆寫為 no-op
    - 不符合 method 的 `/api/*` 請求 → 405
    - POST body 解析失敗 → 400 `invalid_json`
- [x] 5.3 確認 `UIServer` 只綁 `127.0.0.1`（不綁 `0.0.0.0`）
- [x] 5.4 執行測試，確認全部通過

**Checkpoint**：`pytest tests/unit/core/ui/test_server.py` 全部通過；手動 curl `http://127.0.0.1:8765/api/project` 回傳 JSON

---

## Task 6: `ui_cmd.py`（CLI 指令）

**對應 Req 1、Design `ui_cmd.py`**

- [x] 6.1 建立 `tests/unit/cli/test_ui_cmd.py`，先寫失敗測試：
  - `test_ui_cmd_invalid_path_exits_nonzero`：傳入不存在路徑 → stderr 有錯誤訊息，exit code 非 0
  - `test_ui_cmd_port_in_use_exits_nonzero`：端口已佔用 → stderr 有端口衝突訊息，exit code 非 0
  - `test_ui_cmd_no_browser_flag`：`--no-browser` → 不呼叫 `webbrowser.open()`
  - `test_ui_cmd_prints_url_to_stdout`：啟動後 stdout 含 `http://127.0.0.1:`
  - `test_ui_cmd_dot_dir_missing_still_starts`：`project_path` 存在但無 `.the-door/` → server 仍啟動
- [x] 6.2 建立 `the_door/src/the_door/cli/ui_cmd.py`：
  - `@click.command("ui")`，`@click.argument("project_path")`，`@click.option("--port", default=8765)`，`@click.option("--no-browser", is_flag=True)`
  - 驗證 `project_path` 存在且為目錄 → 否則 `click.echo(err=True)` + `sys.exit(1)`
  - 解析 `viewer_dir`：`Path(__file__).parent.parent.parent.parent.parent / "docs/frontend-local-version-viewer/viewer"`（5 層 parent 從 `cli/ui_cmd.py` 到 workspace root；此路徑假設 editable install 開發環境）
  - 建立 `UIServer`；捕捉 `OSError` → 端口衝突訊息 + `sys.exit(1)`
  - `click.echo(server.url)` 到 stdout
  - 非 `--no-browser` → `threading.Timer(0.5, webbrowser.open, [server.url]).start()`（server ready 後開啟）
  - `try: server.start()` / `except KeyboardInterrupt: server.shutdown(); sys.exit(0)`
- [x] 6.3 在 `the_door/src/the_door/cli/main.py` 加入 `ui_cmd`
- [x] 6.4 執行測試，確認全部通過

**Checkpoint**：`pytest tests/unit/cli/test_ui_cmd.py` 全部通過；`the-door ui --help` 顯示正確說明

---

## Task 7: PBT — `test_api_serializer_properties.py`

**對應 Req 13、Design PBT 章節**

- [x] 7.1 建立 `tests/property/test_api_serializer_properties.py`，定義 ASCII-only Hypothesis strategies：
  - `VERSION_SNAPSHOT_ST`：`st.builds(VersionSnapshot, ...)` 含 `version_id`, `timestamp`, `trigger`, `label`, `git_tags`
  - `DOUBT_RECORD_ST`：`st.builds(DoubtRecord, ...)` 含必要欄位
  - `TIMELINE_RESULT_ST`：`st.builds(TimelineResult, ...)`
- [x] 7.2 實作 5 個 PBT 屬性：
  - `prop_snapshot_serialization_json_safe`：任意 `VersionSnapshot` → `serialize_snapshot()` → `json.dumps()` 不拋出例外，包含 `version_id`, `timestamp`, `trigger`, `label`, `git_tags`
  - `prop_doubt_serialization_json_safe`：任意 `DoubtRecord` → `serialize_doubt()` → `json.dumps()` 不拋出例外，包含 `doubt_id`, `doubt_type`, `state`, `source_node`, `created_at`
  - `prop_timeline_serialization_json_safe`：任意 `TimelineResult` → `serialize_timeline_result()` → `snapshot_count` 為 int，`feature_timelines` 為 list
  - `prop_update_report_round_trip`：任意 `UpdateReport` dict → `json.dumps(json.loads(json.dumps(report)))` 結構等價
  - `prop_api_error_response_structure`：任意 `(code, message, source)` → `APIHandlers._make_error()` → `error.code`/`error.message`/`error.source` 均為非空字串
- [x] 7.3 執行 PBT，確認 5 個屬性全部通過

**Checkpoint**：`pytest tests/property/test_api_serializer_properties.py` 全部通過

---

## Task 8: 前端 viewer 升級 — 動態 API 呼叫

**對應 Req 11、Design Frontend Upgrade Design**

- [x] 8.1 升級 `docs/frontend-local-version-viewer/viewer/app.js`：
  - 新增 `loadProjectStatus()`：GET `/api/project`，更新 `state.projectStatus`
  - 新增 `loadReport()`：GET `/api/report/latest`，更新 `state.updateModel`
  - 新增 `loadSnapshots()`：GET `/api/snapshots`，更新 `state.snapshots`
  - 修改初始化邏輯：先呼叫 `loadProjectStatus()`，依 `available_data` 決定後續呼叫
  - fallback 規則：只有 `fetch('/api/project')` 拋出網路錯誤時，才嘗試讀取靜態 JSON；server 啟動後 `has_latest_report=false` 顯示 EmptyState
- [x] 8.2 新增 `showUpdateModal()`：顯示 `old_path`/`new_path` 輸入表單（form 或 modal）
- [x] 8.3 新增 `submitUpdate(oldPath, newPath)`：POST `/api/update`，取得 `job_id`，啟動輪詢
- [x] 8.4 新增 `pollJobStatus(jobId)`：每 1.5 秒 GET `/api/update/status/<jobId>`；`completed` → 停止輪詢 + `loadReport()`；`failed` → 停止輪詢 + 顯示錯誤
- [x] 8.5 新增 `renderPipelineProgress(job)`：顯示 `current_step` 和已完成步驟清單（含 `duration_ms`）
- [x] 8.6 新增 `handleApiError(response)`：解析 `API_Error_Response`，顯示 `error.message`，不顯示空白畫面
- [x] 8.7 確認：所有 API 請求只發往 `127.0.0.1` 或 `localhost`（Req 11 AC8）
- [x] 8.8 升級 `docs/frontend-local-version-viewer/viewer/styles.css`：新增 `PipelineProgress` 元件樣式

**Checkpoint**：啟動 `the-door ui <project-path>`，瀏覽器開啟後可看到 API 資料（或 EmptyState），重新分析按鈕可觸發管線

---

## Task 9: 整合驗收

**對應 Req 1–13 完整驗收**

- [x] 9.1 執行完整測試套件：
  ```
  pytest tests/unit/core/ui/
  pytest tests/unit/cli/test_ui_cmd.py
  pytest tests/property/test_api_serializer_properties.py
  ```
  確認無退步，新增測試全部通過
- [ ] 9.2 手動驗收（啟動 `the-door ui <project-path>`）：
  - [ ] Req 1：`the-door ui <path>` 啟動 server，stdout 顯示 URL，瀏覽器自動開啟
  - [ ] Req 1 AC5：傳入不存在路徑 → stderr 錯誤，非 0 exit
  - [ ] Req 1 AC6：端口衝突 → stderr 錯誤，非 0 exit
  - [ ] Req 1 AC7：Ctrl+C → 優雅關閉，exit 0
  - [ ] Req 2：靜態資源正確服務，Content-Type 正確
  - [ ] Req 3：`/api/project` 回傳正確 JSON
  - [ ] Req 11 AC4：重新分析 form 可輸入路徑，觸發管線
  - [ ] Req 11 AC5：管線執行期間顯示 PipelineProgress
  - [ ] Req 11 AC6：管線完成後自動刷新報告
  - [ ] Req 11 AC7：API 錯誤時顯示訊息，不顯示空白畫面
  - [ ] Req 12 AC1：server 只綁 `127.0.0.1`（`netstat` 確認）
- [x] 9.3 確認無外部網路請求（Req 12 AC4）：
  ```powershell
  Select-String -Path "docs/frontend-local-version-viewer/viewer/*.js" -Pattern "https?://" | Where-Object { $_ -notmatch "127\.0\.0\.1|localhost" }
  ```
  無任何輸出即為通過

**Checkpoint**：所有 Python 測試通過，手動驗收 12 項全部確認
