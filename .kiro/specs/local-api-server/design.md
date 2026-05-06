# Design Document — Phase UI-2: Local API Server

## Overview

Phase UI-2 在 Phase UI-1 的靜態前端 viewer 基礎上，新增 `the-door ui <project-path>` 指令，啟動本地 HTTP server，讓前端 viewer 能動態讀取真實的本地分析資料。

**核心定位：** Phase UI-2 是薄包裝層，不重寫任何分析邏輯。所有資料讀取完全委派給 Phase 1–5 的既有 core 模組。

**設計決策：**

| 決策 | 理由 |
|---|---|
| Python 標準函式庫（`http.server` / `socketserver`） | spec §3.1 明確要求 MVP 不新增 FastAPI/Flask |
| `ThreadingHTTPServer` | 允許同時處理靜態資源請求和 API 輪詢，避免 pipeline 執行期間 UI 凍結 |
| 至多一個並發 UpdateJob | 本地工具；`threading.Lock` 保護 job 狀態 |
| 輪詢（polling）而非 SSE | 標準函式庫不原生支援 SSE；輪詢對本地場景延遲可接受 |
| UpdateReport 持久化到 `DotTheDoor_Dir` | 與既有 snapshot/doubt 儲存模式一致；重啟後仍可讀取 |
| 只綁 `127.0.0.1` | 安全性：不暴露到外部網路 |
| 路徑驗證在 API handler 層 | 安全性：不依賴 orchestrator 的 `PipelineError` |
| `progress_callback` 更新 job 狀態 | `PipelineOrchestrator.run()` 已有此機制；注入 callback 寫入 job 狀態，前端輪詢取得進度 |

---

## Architecture

### 高層資料流

```
the-door ui <project-path>
        │
        ▼
CLI_UI_Command (cli/ui_cmd.py)
        │  建構 UIServer，傳入 project_root + viewer_dir
        ▼
UIServer (core/ui/server.py)
ThreadingHTTPServer on 127.0.0.1:<port>
        │
        ├── /  /index.html  /styles.css  /app.js
        │       → StaticHandler → Viewer_Dir/
        │
        ├── GET  /api/project              → APIHandlers
        ├── GET  /api/snapshots            → APIHandlers
        ├── GET  /api/report/latest        → APIHandlers
        ├── POST /api/update               → APIHandlers → 背景執行緒
        ├── GET  /api/update/status/<id>   → APIHandlers
        ├── GET  /api/doubts               → APIHandlers
        └── GET  /api/timeline             → APIHandlers
```

### 模組邊界

| 模組 | 套件 | 職責 |
|---|---|---|
| `ui_cmd` | `cli/` | `the-door ui` CLI 指令，啟動 UIServer |
| `server` | `core/ui/` | ThreadingHTTPServer + 請求路由 |
| `api_handlers` | `core/ui/` | 7 個 API 端點業務邏輯 |
| `static_handler` | `core/ui/` | 靜態資源服務 + 路徑遍歷防護 |
| `job_store` | `core/ui/` | UpdateJob in-memory 狀態管理 |
| `serializers` | `core/ui/` | core 物件序列化為 JSON-safe dict |

### 擴展後的資料夾結構

```
the_door/src/the_door/
├── cli/
│   ├── main.py                    # 擴展：加入 ui 指令
│   └── ui_cmd.py                  # NEW
└── core/ui/                       # 擴展（Phase UI-1 已有 view_model.py）
    ├── view_model.py              # 既有（不修改）
    ├── server.py                  # NEW
    ├── api_handlers.py            # NEW
    ├── static_handler.py          # NEW
    ├── job_store.py               # NEW
    └── serializers.py             # NEW

the_door/tests/
├── unit/core/ui/
│   ├── test_view_model.py         # 既有（不修改）
│   ├── test_api_handlers.py       # NEW
│   ├── test_static_handler.py     # NEW
│   ├── test_job_store.py          # NEW
│   └── test_serializers.py        # NEW
└── property/
    └── test_api_serializer_properties.py  # NEW（Req 13 PBT）
```

---

## Components and Interfaces

### `core/ui/server.py` — UIServer

```python
class UIServer:
    """本地 HTTP server。ThreadingHTTPServer，只綁 127.0.0.1。"""

    def __init__(self, project_root: Path, viewer_dir: Path, port: int = 8765) -> None: ...

    def start(self) -> None:
        """啟動 server，阻塞直到 shutdown()。
        若端口已佔用拋出 OSError(EADDRINUSE)，由 CLI 捕捉顯示友善錯誤。"""
        ...

    def shutdown(self) -> None:
        """優雅關閉（供 Ctrl+C handler 呼叫）。"""
        ...

    @property
    def url(self) -> str:
        """回傳 http://127.0.0.1:<port>"""
        ...
```

**請求路由規則（`_RequestHandler`）：**
- path 以 `/api/` 開頭 → `APIHandlers`
- 其他 → `StaticHandler`
- 所有 API 回應加入 `Access-Control-Allow-Origin: *`（Req 10 AC5）
- `/api/update` 只接受 POST，其他 `/api/*` 只接受 GET；不符合回傳 405（Req 10 AC3）
- POST body 解析失敗回傳 400 `invalid_json`（Req 10 AC4）
- `log_message` 覆寫為 no-op（避免污染 CLI 輸出）

### `core/ui/api_handlers.py` — APIHandlers

每個方法回傳 `(status_code: int, body: dict)`，無 HTTP 副作用。

```python
class APIHandlers:
    def __init__(self, project_root: Path, job_store: JobStore) -> None: ...

    def handle_get_project(self) -> tuple[int, dict]:
        """GET /api/project
        回傳：{project_path, dot_the_door_exists, available_data:{has_snapshots,
               has_latest_report, has_doubts, has_scope_config}}
        .the-door/ 不存在時 available_data 全為 false，不呼叫 Store。
        例外 → 500 + API_Error_Response。"""
        ...

    def handle_get_snapshots(self) -> tuple[int, dict]:
        """GET /api/snapshots
        SnapshotStore(project_root).list_snapshots()，依 timestamp 降序。
        回傳：{"snapshots": [serialize_snapshot(s) for s in snapshots]}
        例外 → 500 code:"snapshot_read_error"。"""
        ...

    def handle_get_report_latest(self) -> tuple[int, dict]:
        """GET /api/report/latest
        掃描 DotTheDoor_Dir/update-report-*.json，依 generated_at 選最新
        （fallback: 檔案 mtime）。直接回傳 JSON 內容。
        無檔案 → 404 code:"no_report_found"。
        JSON 解析失敗 → 500 code:"report_parse_error"。"""
        ...

    def handle_post_update(self, body: dict) -> tuple[int, dict]:
        """POST /api/update
        驗證順序（全在 handler 層，不依賴 orchestrator）：
        1. body 中缺少 old_path 或 new_path → 400 missing_required_field
        2. old_path 或 new_path 不存在或不是目錄 → 400 invalid_path
        3. old_path == new_path → 400 same_path
        4. old_path 或 new_path 不在 Project_Root 之下 → 400 invalid_path（安全性）
        5. 已有 running job → 409 job_already_running
        通過後：建立 UpdateJob，啟動背景執行緒，回傳 202 {job_id}。"""
        ...

    def handle_get_update_status(self, job_id: str) -> tuple[int, dict]:
        """GET /api/update/status/<job_id>
        回傳：{job_id, status, current_step, steps:[{step_name,status,duration_ms,error_message}]}
        status="failed" 時加入 error_message。
        未知 job_id → 404 code:"job_not_found"。"""
        ...

    def handle_get_doubts(self) -> tuple[int, dict]:
        """GET /api/doubts
        DoubtStore(project_root).list_doubts()。
        回傳：{"doubts": [serialize_doubt(d)], "summary": {"total": N}}
        例外 → 500 code:"doubt_read_error"。"""
        ...

    def handle_get_timeline(self) -> tuple[int, dict]:
        """GET /api/timeline
        SnapshotStore(project_root).list_snapshots() → TimelineEngine().analyze(snapshots)。
        不快取：每次請求重新計算（snapshots 可能在兩次請求之間更新）。
        無 snapshot → 回傳 empty_timeline_result()（不呼叫 TimelineEngine）。
        例外 → 500 code:"timeline_error"。"""
        ...

    def _run_pipeline_job(self, job: UpdateJob, old_path: Path, new_path: Path) -> None:
        """背景執行緒：
        1. PipelineConfig(old_path=old_path, new_path=new_path)
        2. progress_callback → job.update_step(msg)
        3. PipelineOrchestrator().run(config, progress_callback=callback)
        4. 成功：ReportRenderer().render_json(result) → 持久化 → job completed
        5. 失敗：job failed + error_message"""
        ...

    def _persist_report(self, report: dict) -> None:
        """持久化為 DotTheDoor_Dir/update-report-<generated_at>.json
        generated_at 中的 ':' 替換為 '-'（Windows 檔名相容）。encoding="utf-8"。"""
        ...

    def _find_latest_report_path(self) -> Path | None:
        """掃描 update-report-*.json，依 generated_at（fallback: mtime）回傳最新路徑。"""
        ...

    @staticmethod
    def _make_error(code: str, message: str, source: str) -> dict:
        return {"error": {"code": code, "message": message, "source": source}}
```

### `core/ui/static_handler.py` — StaticHandler

```python
class StaticHandler:
    """靜態資源服務，含路徑遍歷防護。"""

    CONTENT_TYPES = {
        ".html": "text/html; charset=utf-8",
        ".css":  "text/css; charset=utf-8",
        ".js":   "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }

    def __init__(self, viewer_dir: Path) -> None:
        self._viewer_dir = viewer_dir.resolve()

    def resolve_path(self, request_path: str) -> Path | None:
        """解析請求路徑為絕對路徑。
        '/' 或 '/index.html' → viewer_dir/index.html。
        呼叫 .resolve() 正規化後，若路徑不在 viewer_dir 之下回傳 None。
        檔案不存在回傳 None。"""
        ...

    def serve(self, request_path: str) -> tuple[int, str, bytes]:
        """回傳 (status_code, content_type, body_bytes)。
        200 成功 / 404 不存在 / 403 路徑遍歷嘗試。"""
        ...
```

### `core/ui/job_store.py` — JobStore + UpdateJob

```python
@dataclass
class UpdateJob:
    """UpdateJob 執行狀態（in-memory，非持久化）。非 frozen。"""
    job_id: str
    status: str = "running"          # "running" | "completed" | "failed"
    current_step: str | None = None
    steps: list[dict] = field(default_factory=list)
    error_message: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def update_step(self, progress_msg: str) -> None:
        """解析 PipelineOrchestrator 進度訊息，更新 current_step / steps。
        使用 self._lock 保護（thread-safe）。
        解析依據為 Unicode 符號（不依賴中文關鍵字，避免 Windows cp950 問題）：
        - 含 '✓' → steps.append({step_name, status:"completed", duration_ms})，current_step = None
        - 含 '✗' → steps.append({step_name, status:"failed", error_message})，current_step = None
        - 含 '⊘' → steps.append({step_name, status:"skipped"})，current_step = None
        - 其他（含步驟名稱但無上述符號）→ current_step = 解析出的 step_name
        step_name 從訊息格式 '[步驟 N/M] <symbol> <step_name>' 中提取。"""
        ...


class JobStore:
    """UpdateJob in-memory 儲存。至多一個並發 job。"""

    def try_create_job(self) -> UpdateJob | None:
        """有 running job → None（呼叫方回傳 409）。否則建立新 job。"""
        ...

    def get_job(self, job_id: str) -> UpdateJob | None: ...
    def complete_job(self, job_id: str) -> None: ...
    def fail_job(self, job_id: str, error_message: str) -> None: ...

    @property
    def has_running_job(self) -> bool: ...
```

### `core/ui/serializers.py` — 序列化函式

```python
def serialize_snapshot(snapshot: VersionSnapshot) -> dict:
    """回傳 {version_id, timestamp, trigger, label, git_tags}（Req 4 AC3）。"""
    ...

def serialize_doubt(doubt: DoubtRecord) -> dict:
    """回傳 {doubt_id, doubt_type, state, source_node, created_at, assignee}。
    current_state → state，assigned_to → assignee（Req 8 AC3）。"""
    ...

def serialize_timeline_result(result: TimelineResult) -> dict:
    """回傳 {snapshot_count, time_range_start, time_range_end,
             feature_timelines, summary:{active_count,removed_count,total_drift_events}}（Req 9 AC3）。"""
    ...

def empty_timeline_result() -> dict:
    """回傳空 TimelineResult JSON（Req 9 AC2）：
    {snapshot_count:0, time_range_start:null, time_range_end:null,
     feature_timelines:[], summary:{active_count:0,removed_count:0,total_drift_events:0}}"""
    ...
```

### `cli/ui_cmd.py` — CLI 指令

```python
@click.command("ui")
@click.argument("project_path", type=click.Path())
@click.option("--port", default=8765, show_default=True)
@click.option("--no-browser", is_flag=True)
def ui_cmd(project_path: str, port: int, no_browser: bool) -> None:
    """啟動本地 UI server。
    1. 驗證 project_path 存在且為目錄 → 否則 stderr + sys.exit(1)
    2. 解析 viewer_dir（相對套件安裝位置）
    3. 建立 UIServer；捕捉 OSError(EADDRINUSE) → 端口衝突錯誤 + sys.exit(1)
    4. 啟動 server（主執行緒阻塞）
    5. 非 --no-browser → server ready 後開啟瀏覽器
    6. KeyboardInterrupt → server.shutdown()，sys.exit(0)"""
    ...
```

---

## Data Models

Phase UI-2 不新增任何 `models.py` dataclass。`UpdateJob` 定義在 `core/ui/job_store.py`（server 執行狀態，非業務資料）。所有 API 回應格式以 `serializers.py` 函式定義，不建立新 dataclass。

---

## Frontend Upgrade Design

### 升級策略

Phase UI-1 的 `app.js` 讀取靜態 JSON。Phase UI-2 升級為呼叫本地 API。

fallback 規則：靜態 JSON（`data/update-view-model.json`）只在 server 完全未啟動時作為 fallback（即 `fetch('/api/project')` 拋出網路錯誤）。當 server 已啟動但 `has_latest_report=false` 時，顯示 EmptyState，不回退讀取靜態 JSON——靜態 JSON 是舊版 Phase UI-1 的產物，不代表當前專案狀態。

### 前端狀態機

```
初始化
  │
  ▼
GET /api/project
  ├── has_latest_report=true → GET /api/report/latest → 渲染 viewer
  ├── has_snapshots=true     → GET /api/snapshots → 渲染版本選擇器
  └── 無資料                 → EmptyState（引導執行 the-door analyze）

使用者點擊「重新分析」
  │
  ▼
顯示 form（輸入 old_path / new_path）
  │
  ▼
POST /api/update {old_path, new_path}
  ├── 202 → 輪詢 GET /api/update/status/<job_id>（每 1.5 秒）
  │         ├── running  → 更新 PipelineProgress 元件
  │         └── completed → 停止輪詢 → GET /api/report/latest
  └── 4xx/5xx → 顯示 error.message
```

### 新增 JavaScript 函式

| 函式 | 職責 |
|---|---|
| `loadProjectStatus()` | GET /api/project |
| `loadReport()` | GET /api/report/latest |
| `loadSnapshots()` | GET /api/snapshots |
| `showUpdateModal()` | 顯示 old_path/new_path 輸入表單 |
| `submitUpdate(oldPath, newPath)` | POST /api/update，啟動輪詢 |
| `pollJobStatus(jobId)` | 輪詢 GET /api/update/status/<jobId> |
| `renderPipelineProgress(job)` | 渲染管線進度元件 |
| `handleApiError(response)` | 解析 API_Error_Response，顯示錯誤訊息 |

### 錯誤處理規則

| 情境 | 處理方式 |
|---|---|
| GET /api/project 失敗 | 顯示「無法連線到本地 server」 |
| GET /api/report/latest 404 | EmptyState，引導執行 `the-door update` |
| POST /api/update 409 | 顯示「管線正在執行中，請稍候」 |
| POST /api/update 400 | 顯示 error.message |
| 輪詢 status="failed" | 顯示 error_message，停止輪詢 |

---

## Test Design

### Unit Tests — `test_ui_cmd.py`（CLI 指令，Req 1）

| 測試名稱 | 覆蓋的 Req |
|---|---|
| `test_ui_cmd_invalid_path_exits_nonzero` | Req 1 AC5 |
| `test_ui_cmd_port_in_use_exits_nonzero` | Req 1 AC6 |
| `test_ui_cmd_no_browser_flag` | Req 1 AC3 |
| `test_ui_cmd_prints_url_to_stdout` | Req 1 AC1 |
| `test_ui_cmd_dot_dir_missing_still_starts` | Req 1 AC8 |

### Unit Tests — `test_api_handlers.py`

所有測試 mock 既有 core 模組，不執行真實分析。

| 測試名稱 | 覆蓋的 Req |
|---|---|
| `test_get_project_dot_dir_exists` | Req 3 AC1/AC2 |
| `test_get_project_dot_dir_missing` | Req 3 AC3 |
| `test_get_project_exception_returns_500` | Req 3 AC5 |
| `test_get_snapshots_returns_sorted_list` | Req 4 AC1/AC4 |
| `test_get_snapshots_empty` | Req 4 AC2 |
| `test_get_snapshots_exception_returns_500` | Req 4 AC5 |
| `test_get_report_latest_found` | Req 5 AC1 |
| `test_get_report_latest_not_found` | Req 5 AC2 |
| `test_get_report_latest_invalid_json` | Req 5 AC3 |
| `test_get_report_latest_selects_newest_by_generated_at` | Req 5 AC4 |
| `test_get_report_latest_fallback_to_mtime` | Req 5 AC4 fallback |
| `test_post_update_missing_field` | Req 6 AC2 |
| `test_post_update_invalid_path` | Req 6 AC3 |
| `test_post_update_same_path` | Req 6 AC4 |
| `test_post_update_job_already_running` | Req 6 AC5 |
| `test_post_update_path_outside_project_root` | Req 12 AC5 |
| `test_post_update_success_returns_202_with_job_id` | Req 6 AC1 |
| `test_post_update_pipeline_runs_in_background` | Req 6 AC6 |
| `test_post_update_persists_report_on_completion` | Req 6 AC7 |
| `test_get_update_status_running` | Req 7 AC1/AC2 |
| `test_get_update_status_completed` | Req 7 AC3 |
| `test_get_update_status_failed` | Req 7 AC4 |
| `test_get_update_status_unknown_job` | Req 7 AC5 |
| `test_get_doubts_returns_list` | Req 8 AC1 |
| `test_get_doubts_empty` | Req 8 AC2 |
| `test_get_doubts_exception_returns_500` | Req 8 AC5 |
| `test_get_timeline_with_snapshots` | Req 9 AC1 |
| `test_get_timeline_no_snapshots` | Req 9 AC2 |
| `test_get_timeline_exception_returns_500` | Req 9 AC4 |

### Unit Tests — `test_static_handler.py`

| 測試名稱 | 覆蓋的 Req |
|---|---|
| `test_serve_index_html` | Req 2 AC1 |
| `test_serve_root_redirects_to_index` | Req 2 AC1 |
| `test_serve_css_correct_content_type` | Req 2 AC4 |
| `test_serve_js_correct_content_type` | Req 2 AC4 |
| `test_serve_json_correct_content_type` | Req 2 AC5 |
| `test_serve_missing_file_returns_404` | Req 2 AC3 |
| `test_path_traversal_rejected` | Req 2 AC6 / Req 12 AC2 |
| `test_path_traversal_encoded_dots_rejected` | Req 12 AC2 |

### Unit Tests — `test_job_store.py`

| 測試名稱 | 覆蓋的 Req |
|---|---|
| `test_create_job_returns_job` | Req 6 AC1 |
| `test_create_job_when_running_returns_none` | Req 6 AC5 |
| `test_get_job_running` | Req 7 AC1 |
| `test_get_job_completed` | Req 7 AC3 |
| `test_get_job_unknown_returns_none` | Req 7 AC5 |
| `test_complete_job` | Req 7 AC3 |
| `test_fail_job` | Req 7 AC4 |
| `test_update_step_parses_running_message` | Req 7 AC2 |
| `test_update_step_parses_completed_message` | Req 7 AC3 |
| `test_update_step_parses_skipped_message` | Req 7 AC3 |
| `test_update_step_thread_safety` | Req 6 AC6 |

### Unit Tests — `test_serializers.py`

| 測試名稱 | 覆蓋的 Req |
|---|---|
| `test_serialize_snapshot_fields` | Req 4 AC3 |
| `test_serialize_snapshot_null_label` | Req 4 AC3 |
| `test_serialize_doubt_field_mapping` | Req 8 AC3 |
| `test_serialize_doubt_null_assignee` | Req 8 AC3 |
| `test_serialize_timeline_result` | Req 9 AC3 |
| `test_empty_timeline_result` | Req 9 AC2 |

### PBT — `test_api_serializer_properties.py`（Req 13）

使用 Hypothesis，ASCII-only strategy（對齊既有 PBT 慣例，Windows cp950 相容）。

**5 個屬性：**

| 屬性 | 描述 |
|---|---|
| `prop_snapshot_serialization_json_safe` | 任意 VersionSnapshot → serialize_snapshot() → json.dumps() 不拋出例外，包含必要欄位 |
| `prop_doubt_serialization_json_safe` | 任意 DoubtRecord → serialize_doubt() → json.dumps() 不拋出例外，包含必要欄位 |
| `prop_timeline_serialization_json_safe` | 任意 TimelineResult → serialize_timeline_result() → snapshot_count 為 int、feature_timelines 為 list |
| `prop_update_report_round_trip` | 任意 UpdateReport dict → json.dumps(json.loads(json.dumps(report))) 結構等價 |
| `prop_api_error_response_structure` | 任意 (code, message, source) → _make_error() → error.code/message/source 均為非空字串 |

---

## Correctness Properties

### Property 1: API 回應格式一致性
對任意有效的 `VersionSnapshot` 列表，`/api/snapshots` 序列化輸出必須是 JSON-serializable，且每個 entry 包含 `version_id`、`timestamp`、`trigger`、`label`、`git_tags`。
**驗證：** Req 13 AC1 / `prop_snapshot_serialization_json_safe`

### Property 2: DoubtRecord 欄位映射正確性
對任意有效的 `DoubtRecord`，序列化後 `state` 等於原始 `current_state`，`assignee` 等於原始 `assigned_to`（或 null）。
**驗證：** Req 13 AC2 / `prop_doubt_serialization_json_safe`

### Property 3: TimelineResult 結構完整性
對任意有效的 `TimelineResult`，序列化輸出包含 `snapshot_count`（integer）和 `feature_timelines`（array）。空結果必須包含 `time_range_start: null` 和 `time_range_end: null`。
**驗證：** Req 13 AC3 / `prop_timeline_serialization_json_safe`

### Property 4: UpdateReport JSON 冪等性
對任意有效的 `UpdateReport` dict，`json.dumps(json.loads(json.dumps(report)))` 結構等價於原始 dict。
**驗證：** Req 13 AC4 / `prop_update_report_round_trip`

### Property 5: API_Error_Response 結構完整性
對任意 API 端點產生的錯誤回應，`error.code`、`error.message`、`error.source` 均為非空字串。
**驗證：** Req 13 AC5 / `prop_api_error_response_structure`

### Property 6: 路徑遍歷防護
對任意請求路徑（含 `../`、`%2e%2e/`、絕對路徑），`StaticHandler.resolve_path()` 解析後路徑必須在 `viewer_dir` 之下，否則回傳 None。
**驗證：** Req 2 AC6 / Req 12 AC2

### Property 7: UpdateJob 狀態機完整性
`UpdateJob.status` 只能為 `"running"`、`"completed"`、`"failed"` 之一。從 `"running"` 只能轉換到 `"completed"` 或 `"failed"`，不能回到 `"running"`。
**驗證：** `test_job_store.py`

---

*Phase UI-2 不新增任何第三方依賴。所有功能使用 Python 標準函式庫（`http.server`、`socketserver`、`threading`、`json`、`pathlib`、`webbrowser`）實作。*
