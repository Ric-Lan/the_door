# api_handlers.py 拆分為 api/ package — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `core/ui/api_handlers.py`（1234 行 / 單一 `APIHandlers` 類 / 21 端點）拆成 `core/ui/api/` package（中轉樞紐 router + 共用依賴 `APIContext` + 集中錯誤碼登記表 + 6 領域 handler），HTTP 行為完全不變。

**Architecture:** 新結構與舊 `api_handlers.py` **先共存**，逐一建好新模組（context → error_codes → router → 6 handler）並各自 TDD，最後一次性把 `server.py` 切到 `router.dispatch` 並刪除舊類。兩道安全網（既有 e2e 13 端點 + 新增 router 綁定測試補 8 端點）全程保持 GREEN，任一步變紅即回退。

**Tech Stack:** Python 3.12、pytest、stdlib `http.server`（`BaseHTTPRequestHandler`）。無新依賴。

**參考 spec:** `docs/superpowers/specs/2026-05-31-api-handlers-split-design.md`

**全域指令注意:** 內層專案在 `the_door/` 跑（`testpaths=["tests"]`）。所有 `pytest` / `git` 指令的 cwd = `the_door/`。Windows console 有 cp950 問題，跑會輸出 emoji 的指令時加 `PYTHONUTF8=1`。

---

## 檔案結構（拆分後）

```
the_door/src/the_door/core/ui/
  api/
    __init__.py          # 暴露 Router + APIContext
    context.py           # APIContext：3 個 lazy 依賴存取器
    error_codes.py       # ERROR_CODES 登記表 + build_error() helper
    router.py            # Route dataclass + ROUTES 表 + Router.dispatch
    handlers/
      __init__.py
      project.py         # ProjectHandlers: get / set_project / status
      analysis.py        # AnalysisHandlers: analyze / update / update_status
      catalog.py         # CatalogHandlers: snapshots / timeline / report_latest
      graph.py           # GraphHandlers: get_l1 / get_l2 / generate_l2 / get_structure / get_layer_explanation / generate_layer_explanation
      diff.py            # DiffHandlers: versions / get_explanation / generate_explanation
      annotation.py      # AnnotationHandlers: get_notes / post_notes / doubts
  server.py              # 改：建 APIContext + Router，dispatch 改呼 router
  api_handlers.py        # 最後刪除
```

```
the_door/tests/
  integration/test_router_binding.py   # 新增安全網（補 8 端點）
  unit/core/ui/api/
    test_context.py
    test_error_codes.py
    test_router.py
    handlers/test_project.py
    handlers/test_analysis.py
    handlers/test_catalog.py
    handlers/test_graph.py
    handlers/test_diff.py
    handlers/test_annotation.py
```

舊 `tests/unit/core/ui/test_api_handlers*.py`（6 檔）在 Task 12 移除，斷言內容已遷入上列新測試。

---

## Task 1: 行為安全網 — router 綁定整合測試（補 8 個未被 e2e 覆蓋的端點）

**目的:** 在動任何結構前，先用真 HTTP 釘住目前這 8 個端點的「path→正確回應」，作為 rewire 的網。對**現行 server** 跑，必須立即 GREEN。

**8 個未被 `test_e2e_ui_server.py` 覆蓋的端點:** `POST /api/analyze`、`POST /api/set-project`、`GET /api/status`、`GET /api/diff`、`GET /api/diff-explanations/<fid>`、`POST /api/diff-explanations/<fid>/generate`、`GET /api/notes`、`POST /api/notes`。

**Files:**
- Create: `the_door/tests/integration/test_router_binding.py`

- [ ] **Step 1: 參考既有 e2e 的 server 啟動樣板**

Read `the_door/tests/integration/test_e2e_ui_server.py` 開頭（free-port、起 server thread、`urllib.request` 發請求的 helper）。沿用同樣板，不要自創新起法。

- [ ] **Step 2: 寫整合測試（對現行 server，斷言現況行為）**

對每個端點發一次請求，斷言 HTTP status 與回應 body 的「形狀關鍵欄位」符合現況（不是內容值，是契約）。範例骨架（沿用 e2e 的 `_get`/`_post` helper 名稱）：

```python
"""Router-binding safety net: pins behavior of the 8 endpoints NOT covered by
test_e2e_ui_server.py, so the api/ package rewire cannot silently mis-route them.
"""
def test_get_status_returns_state_envelope(live_server):
    status, body = _get(live_server, "/api/status")
    assert status == 200
    assert "state" in body or "status" in body   # 以現行回應實際鍵為準（先跑現況確認）

def test_get_diff_requires_params(live_server):
    status, body = _get(live_server, "/api/diff")
    assert status == 400
    assert body["error"]["code"] == "missing_params"

def test_post_set_project_invalid_json(live_server):
    status, body = _post_raw(live_server, "/api/set-project", b"{not json")
    assert status == 400
    assert body["error"]["code"] == "invalid_json"

def test_post_notes_roundtrip(live_server):
    status, _ = _post(live_server, "/api/notes", {"feature_id": "feat-x", "text": "n"})
    assert status in (200, 201)
    status, body = _get(live_server, "/api/notes?feature_id=feat-x")
    assert status == 200
# …analyze / diff-explanations(讀+生成) 各補一條
```

> 斷言的確切鍵名以**現況回應為準**：先在實作機跑一次該端點、把實際回應鍵填進斷言，避免臆測。

- [ ] **Step 3: 跑測試，必須 GREEN（釘住現況）**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/integration/test_router_binding.py -v`
Expected: 全 PASS（這是現況基準，非 TDD red）。若紅，表示斷言鍵名臆測錯 → 依實際回應修正，不是改 server。

- [ ] **Step 4: Commit**

```bash
cd the_door && git add tests/integration/test_router_binding.py
git commit -m "test: router-binding safety net for 8 endpoints uncovered by e2e"
```

---

## Task 2: `error_codes.py` 集中錯誤碼登記表

**Files:**
- Create: `the_door/src/the_door/core/ui/api/__init__.py`（空，標記 package）
- Create: `the_door/src/the_door/core/ui/api/error_codes.py`
- Test: `the_door/tests/unit/core/ui/api/test_error_codes.py`

- [ ] **Step 1: 列舉現有錯誤碼（勿臆測）**

Run: `cd the_door && grep -rnoE '"[a-z_]+_?(error|not_found|allowed|json|params|generated|found)"' src/the_door/core/ui/api_handlers.py src/the_door/core/ui/server.py`
把抓到的碼（如 `not_found`/`invalid_json`/`missing_params`/`method_not_allowed`/`l2_not_generated`/`baseline_not_found` 等）記下，連同 router 新增的 4 個 `router.*` 碼，構成完整登記清單。

- [ ] **Step 2: 寫失敗測試**

```python
from the_door.core.ui.api.error_codes import ERROR_CODES, ErrCode, build_error

def test_every_code_has_http_file_desc():
    for code, ec in ERROR_CODES.items():
        assert isinstance(ec.http, int) and ec.file and ec.desc

def test_descs_are_english_ascii():
    for ec in ERROR_CODES.values():
        assert ec.desc.isascii(), f"error desc must be English: {ec.desc!r}"

def test_build_error_fills_source_file_from_registry():
    status, body = build_error("router.no_route", source="router.dispatch")
    assert status == 404
    assert body["error"]["code"] == "router.no_route"
    assert body["error"]["source_file"] == "core/ui/api/router.py"
    assert body["error"]["message"].isascii()

def test_router_codes_registered():
    for c in ("router.no_route","router.method_not_allowed","router.invalid_json","router.handler_error"):
        assert c in ERROR_CODES
```

- [ ] **Step 3: 跑測試，確認 FAIL**

Run: `cd the_door && python -m pytest tests/unit/core/ui/api/test_error_codes.py -v`
Expected: FAIL（module 不存在）。

- [ ] **Step 4: 實作 error_codes.py**

```python
"""Central registry of API-layer error codes. Single source for error responses
and the generated error-code doc. Response values are English (machine-facing);
route summaries (zh-TW) live in router.py, not here."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ErrCode:
    http: int
    file: str   # src-relative path marker
    desc: str   # English

ERROR_CODES: dict[str, ErrCode] = {
    "router.no_route":           ErrCode(404, "core/ui/api/router.py", "Request path matched no route"),
    "router.method_not_allowed": ErrCode(405, "core/ui/api/router.py", "Path exists but HTTP method not allowed"),
    "router.invalid_json":       ErrCode(400, "core/ui/api/router.py", "POST body is not valid JSON"),
    "router.handler_error":      ErrCode(500, "core/ui/api/router.py", "Handler raised an unexpected exception"),
    # —— 以下依 Step 1 grep 結果完整補齊 API 區既有業務碼，範例：——
    "not_found":        ErrCode(404, "core/ui/api/router.py", "Unknown endpoint"),
    "invalid_json":     ErrCode(400, "core/ui/api/router.py", "Request body is not valid JSON"),
    "missing_params":   ErrCode(400, "core/ui/api/handlers/diff.py", "Required query params missing"),
    "method_not_allowed": ErrCode(405, "core/ui/api/router.py", "Method not allowed"),
    "l2_not_generated": ErrCode(404, "core/ui/api/handlers/graph.py", "L2 not yet generated for this feature"),
    # …其餘 grep 到的碼一併登記
}

def build_error(code: str, *, source: str, message: str | None = None,
                source_file: str | None = None) -> tuple[int, dict]:
    ec = ERROR_CODES[code]
    return ec.http, {"error": {
        "code": code,
        "message": message or ec.desc,
        "source": source,
        "source_file": source_file or ec.file,
    }}
```

- [ ] **Step 5: 跑測試，確認 PASS**

Run: `cd the_door && python -m pytest tests/unit/core/ui/api/test_error_codes.py -v`
Expected: PASS。若 `test_descs_are_english_ascii` 紅 → 把該 desc 改英文。

- [ ] **Step 6: Commit**

```bash
cd the_door && git add src/the_door/core/ui/api/__init__.py src/the_door/core/ui/api/error_codes.py tests/unit/core/ui/api/test_error_codes.py
git commit -m "feat(api): central ERROR_CODES registry with English responses + file marker"
```

---

## Task 3: `APIContext` 共用依賴資料袋

**Files:**
- Create: `the_door/src/the_door/core/ui/api/context.py`
- Test: `the_door/tests/unit/core/ui/api/test_context.py`

- [ ] **Step 1: 寫失敗測試（含動態切換不變量）**

```python
from pathlib import Path
from the_door.core.ui.api.context import APIContext

def test_project_root_reflects_current_fn_value(tmp_path):
    current = {"root": tmp_path / "a"}
    ctx = APIContext(
        _project_root_fn=lambda: current["root"],
        _job_store_fn=lambda: "JOB",
        _switch_project_fn=lambda p, f: {"status": "ok"},
    )
    assert ctx.project_root == tmp_path / "a"
    current["root"] = tmp_path / "b"          # 模擬專案切換
    assert ctx.project_root == tmp_path / "b" # 必須跟著變（lazy）

def test_job_store_and_switch_delegate():
    ctx = APIContext(lambda: Path("."), lambda: "JOB", lambda p, f: {"r": (p, f)})
    assert ctx.job_store == "JOB"
    assert ctx.switch_project("x", True) == {"r": ("x", True)}
```

- [ ] **Step 2: 跑測試，確認 FAIL**

Run: `cd the_door && python -m pytest tests/unit/core/ui/api/test_context.py -v`
Expected: FAIL（module 不存在）。

- [ ] **Step 3: 實作 context.py**

```python
"""APIContext: immutable holder of the 3 shared, lazily-accessed dependencies.
Lazy because the active project can switch at runtime; do NOT freeze values.
Stores are NOT held here — handlers construct them per-call from ctx.project_root."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

@dataclass(frozen=True)
class APIContext:
    _project_root_fn: Callable[[], Path]
    _job_store_fn: Callable[[], object]
    _switch_project_fn: Callable[[str, bool], dict]

    @property
    def project_root(self) -> Path:
        return self._project_root_fn()

    @property
    def job_store(self):
        return self._job_store_fn()

    def switch_project(self, path: str, force: bool) -> dict:
        return self._switch_project_fn(path, force)
```

- [ ] **Step 4: 跑測試，確認 PASS**

Run: `cd the_door && python -m pytest tests/unit/core/ui/api/test_context.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
cd the_door && git add src/the_door/core/ui/api/context.py tests/unit/core/ui/api/test_context.py
git commit -m "feat(api): APIContext lazy shared-dependency holder"
```

---

## Task 4: Router 核心（Route + 模板比對 + dispatch + handler_error 兜底）

**Files:**
- Create: `the_door/src/the_door/core/ui/api/router.py`
- Test: `the_door/tests/unit/core/ui/api/test_router.py`

> 本任務先建 router 機制，用**假 handler** 測試；真實 ROUTES 表在 Task 11 組裝。

- [ ] **Step 1: 寫失敗測試**

```python
from the_door.core.ui.api.router import Router, Route

def _ok(ctx, **kw):           # 假 handler
    return 200, {"got": kw}

def _boom(ctx, **kw):
    raise ValueError("kaboom")

def _routes():
    return [
        Route("GET",  "/api/ping",            _ok,   summary="測試用 ping"),
        Route("GET",  "/api/item/{item_id}",  _ok,   summary="測試用取 item"),
        Route("POST", "/api/item/{item_id}",  _ok,   summary="測試用建 item"),
        Route("GET",  "/api/boom",            _boom, summary="測試用爆炸"),
    ]

def test_exact_match_dispatch():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("GET", "/api/ping", raw_body=b"")
    assert status == 200

def test_template_param_extracted():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("GET", "/api/item/42", raw_body=b"")
    assert body["got"]["item_id"] == "42"

def test_no_route_404():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("GET", "/api/nope", raw_body=b"")
    assert status == 404 and body["error"]["code"] == "router.no_route"

def test_method_not_allowed_405():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("DELETE", "/api/ping", raw_body=b"")
    assert status == 405 and body["error"]["code"] == "router.method_not_allowed"

def test_post_bad_json_400():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("POST", "/api/item/1", raw_body=b"{bad")
    assert status == 400 and body["error"]["code"] == "router.invalid_json"

def test_handler_exception_500_with_source_file():
    r = Router(ctx=None, routes=_routes())
    status, body = r.dispatch("GET", "/api/boom", raw_body=b"")
    assert status == 500
    assert body["error"]["code"] == "router.handler_error"
    assert body["error"]["source"].startswith("router:")
    assert body["error"]["source_file"].endswith(".py")

def test_every_route_has_nonempty_summary():
    for rt in _routes():
        assert rt.summary.strip()
```

- [ ] **Step 2: 跑測試，確認 FAIL**

Run: `cd the_door && python -m pytest tests/unit/core/ui/api/test_router.py -v`
Expected: FAIL（module 不存在）。

- [ ] **Step 3: 實作 router.py**

```python
"""Central dispatch hub. One route table (the single owner of the API surface),
a tiny segment-based template matcher, and dispatch that centralizes body parsing
and wraps handler exceptions into a locatable error. NOT a framework."""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Callable
from the_door.core.ui.api.error_codes import build_error

@dataclass(frozen=True)
class Route:
    method: str
    path: str                      # e.g. "/api/item/{item_id}"
    handler: Callable
    summary: str                   # zh-TW，用途註解 + API 文件來源

class Router:
    def __init__(self, ctx, routes: list[Route]) -> None:
        self._ctx = ctx
        self._routes = routes

    def dispatch(self, method: str, path: str, raw_body: bytes,
                 query: dict | None = None) -> tuple[int, dict]:
        query = query or {}
        path = path.split("?")[0]
        path_match = None
        for rt in self._routes:
            params = _match(rt.path, path)
            if params is None:
                continue
            path_match = rt
            if rt.method != method:
                continue
            # method matched
            body = None
            if method == "POST":
                try:
                    body = json.loads(raw_body) if raw_body else {}
                except json.JSONDecodeError:
                    return build_error("router.invalid_json",
                                       source=f"router.parse_body:{rt.handler.__name__}")
            try:
                return rt.handler(self._ctx, body=body, **params, **query)
            except Exception as exc:  # noqa: BLE001 — 兜未預期例外，回 500
                hfile = _handler_file(rt.handler)
                return build_error("router.handler_error",
                                   source=f"router:{rt.handler.__qualname__}",
                                   message=str(exc), source_file=hfile)
        if path_match is not None:
            return build_error("router.method_not_allowed",
                               source=f"router.dispatch:{path_match.path}")
        return build_error("router.no_route", source="router.dispatch")

def _match(template: str, path: str) -> dict | None:
    t, p = template.strip("/").split("/"), path.strip("/").split("/")
    if len(t) != len(p):
        return None
    params: dict = {}
    for seg_t, seg_p in zip(t, p):
        if seg_t.startswith("{") and seg_t.endswith("}"):
            params[seg_t[1:-1]] = seg_p
        elif seg_t != seg_p:
            return None
    return params

def _handler_file(handler: Callable) -> str:
    mod = handler.__module__.replace("the_door.", "").replace(".", "/")
    return f"{mod}.py"
```

> 註：`_handler_file` 對假 handler（定義在測試模組）會回測試檔路徑，斷言只檢查 `.py` 結尾，OK。真 handler 在 `core/ui/api/handlers/*` → 回正確 src 相對路徑。

- [ ] **Step 4: 跑測試，確認 PASS**

Run: `cd the_door && python -m pytest tests/unit/core/ui/api/test_router.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
cd the_door && git add src/the_door/core/ui/api/router.py tests/unit/core/ui/api/test_router.py
git commit -m "feat(api): router dispatch hub with template match + locatable handler errors"
```

---

## Tasks 5–10: 領域 handler 提取（共通做法）

> **每個領域 handler 任務的共通形態（每任務都照此，不要跳讀依賴）：**
> 1. 新建 `handlers/<domain>.py`，類別 `__init__(self, ctx: APIContext)` 存 `self._ctx`。
> 2. 把舊 `api_handlers.py` 對應 `handle_*` 方法的**函式體逐字搬入**，只做兩種機械轉換：
>    - `self._project_root` → `self._ctx.project_root`；`self._job_store` → `self._ctx.job_store`；
>      `self._switch_project_fn(...)` → `self._ctx.switch_project(...)`。
>    - 方法簽名改成 router 呼叫慣例：`def <new_name>(self, ctx=None, *, body=None, **params)`。
>      （router 已持有 ctx，handler 用 `self._ctx`；簽名收 `ctx`/`body`/`params` 以相容 dispatch 呼叫。）
> 3. 業務邏輯、回應 body、錯誤碼**一字不改**（行為不變）。
> 4. 測試：把舊 `test_api_handlers*.py` 相對應斷言搬入新測試檔，建構改為
>    `H = <Domain>Handlers(APIContext(lambda: tmp_path, lambda: job_store, lambda p,f: {...}))`，
>    呼叫改新方法名。
> 5. 舊 `api_handlers.py` 此時**仍保留**（尚未刪），新舊並存。

### Task 5: ProjectHandlers

**Files:**
- Create: `the_door/src/the_door/core/ui/api/handlers/__init__.py`（空）
- Create: `the_door/src/the_door/core/ui/api/handlers/project.py`
- Test: `the_door/tests/unit/core/ui/api/handlers/test_project.py`

**搬移來源（api_handlers.py 行）:** `handle_get_project`(104) → `get`、`handle_post_set_project`(328) → `set_project`、`handle_get_status`(615) → `status`。

- [ ] **Step 1: 寫失敗測試**（搬 `test_api_handlers.py` / `test_api_handlers_set_project.py` 中 project/status/set-project 相關斷言；建構用 APIContext）

```python
from pathlib import Path
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.project import ProjectHandlers
from the_door.core.ui.job_store import JobStore

def _ctx(tmp_path):
    return APIContext(lambda: tmp_path, lambda: JobStore(), lambda p, f: {"status": "ok"})

def test_get_project_uninitialized(tmp_path):
    h = ProjectHandlers(_ctx(tmp_path))
    status, body = h.get()
    assert status == 200
    assert "project_path" in body
# …status / set_project 各補（沿用舊斷言）
```

- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_project.py -v`（FAIL：module 不存在）
- [ ] **Step 3: 實作 project.py** — 依共通做法搬 3 個方法體 + ctx 轉換。class 殼：

```python
"""Project lifecycle handlers: current project, switch, status."""
from the_door.core.ui.api.context import APIContext

class ProjectHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    def get(self, ctx=None, *, body=None, **params):
        ...  # 搬 handle_get_project 體，self._project_root → self._ctx.project_root
    def set_project(self, ctx=None, *, body=None, **params):
        ...  # 搬 handle_post_set_project；self._switch_project_fn → self._ctx.switch_project
    def status(self, ctx=None, *, body=None, **params):
        ...  # 搬 handle_get_status
```

- [ ] **Step 4: 跑測試確認 PASS** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_project.py -v`
- [ ] **Step 5: Commit** — `cd the_door && git add src/the_door/core/ui/api/handlers/__init__.py src/the_door/core/ui/api/handlers/project.py tests/unit/core/ui/api/handlers/test_project.py && git commit -m "feat(api): extract ProjectHandlers"`

### Task 6: AnalysisHandlers

**Files:** Create `handlers/analysis.py`；Test `handlers/test_analysis.py`
**搬移來源:** `handle_post_analyze`(275) → `analyze`、`handle_post_update`(194) → `update`、`handle_get_update_status`(361) → `update_status`。
**注意:** 這些走 async job（用 `self._ctx.job_store`）；行為不變，job 啟動邏輯原樣搬。

- [ ] **Step 1: 寫失敗測試**（搬 `test_api_handlers_analyze.py` 斷言；建構用 APIContext，含 job_store）
- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_analysis.py -v`
- [ ] **Step 3: 實作 analysis.py**（class `AnalysisHandlers(ctx)`，搬 3 方法 + ctx 轉換）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: Commit** — `... && git commit -m "feat(api): extract AnalysisHandlers"`

### Task 7: CatalogHandlers

**Files:** Create `handlers/catalog.py`；Test `handlers/test_catalog.py`
**搬移來源:** `handle_get_snapshots`(148) → `snapshots`、`handle_get_timeline`(406) → `timeline`、`handle_get_report_latest`(165) → `report_latest`。

- [ ] **Step 1: 寫失敗測試**（snapshots/timeline/report-latest 斷言）
- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_catalog.py -v`
- [ ] **Step 3: 實作 catalog.py**（class `CatalogHandlers(ctx)`，搬 3 方法）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: Commit** — `... && git commit -m "feat(api): extract CatalogHandlers"`

### Task 8: GraphHandlers

**Files:** Create `handlers/graph.py`；Test `handlers/test_graph.py`
**搬移來源:** `handle_get_l1`(425) → `get_l1`、`handle_get_l2`(628) → `get_l2`、`handle_post_l2_generate`(651) → `generate_l2`、`handle_get_structure`(766) → `get_structure`、`handle_get_layer_explanation`(695) → `get_layer_explanation`、`handle_post_layer_explanation_generate`(734) → `generate_layer_explanation`。
**注意:** generate 類用 `create_provider(config)`（需 API key 路徑）；行為不變，原樣搬；測試沿用舊測試對「未生成 / 已存在」的斷言。

- [ ] **Step 1: 寫失敗測試**（搬 `test_api_handlers_ui3.py` 的 l1/l2/structure/layer-explanation 斷言）
- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_graph.py -v`
- [ ] **Step 3: 實作 graph.py**（class `GraphHandlers(ctx)`，搬 6 方法 + ctx 轉換）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: Commit** — `... && git commit -m "feat(api): extract GraphHandlers"`

### Task 9: DiffHandlers

**Files:** Create `handlers/diff.py`；Test `handlers/test_diff.py`
**搬移來源:** `handle_diff_versions`(508) → `versions`、`handle_get_diff_explanation`(889) → `get_explanation`、`handle_post_diff_explanation_generate`(913) → `generate_explanation`。
**注意:** `versions` 從 query 取 `baseline`/`current`（router 以 `**query` 傳入）；缺參數回 `missing_params`。

- [ ] **Step 1: 寫失敗測試**（搬 `test_api_handlers_diff_explanation.py` 斷言 + diff versions 缺參數 400）
- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_diff.py -v`
- [ ] **Step 3: 實作 diff.py**（class `DiffHandlers(ctx)`，搬 3 方法；`versions(self, ctx=None, *, body=None, baseline=None, current=None, **_)`）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: Commit** — `... && git commit -m "feat(api): extract DiffHandlers"`

### Task 10: AnnotationHandlers

**Files:** Create `handlers/annotation.py`；Test `handlers/test_annotation.py`
**搬移來源:** `handle_get_notes`(1130) → `get_notes`、`handle_post_notes`(1172) → `post_notes`、`handle_get_doubts`(387) → `doubts`。
**注意:** `get_notes` 收 query（`mode`/`feature_id`/`version_a`/`version_b`）。

- [ ] **Step 1: 寫失敗測試**（搬 `test_api_handlers_notes.py` + doubts 斷言）
- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/handlers/test_annotation.py -v`
- [ ] **Step 3: 實作 annotation.py**（class `AnnotationHandlers(ctx)`，搬 3 方法）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: Commit** — `... && git commit -m "feat(api): extract AnnotationHandlers"`

---

## Task 11: 組裝 ROUTES 表 + 切換 server.py 到 router

**Files:**
- Modify: `the_door/src/the_door/core/ui/api/router.py`（加入真實 `build_routes(handlers)` 或 ROUTES 組裝）
- Modify: `the_door/src/the_door/core/ui/api/__init__.py`（暴露 Router、APIContext、組裝函式）
- Modify: `the_door/src/the_door/core/ui/server.py`（建 APIContext + Router，dispatch 改呼 router；移除舊 GET/POST if-elif 與重複 body 解析）
- Test: 既有 `tests/integration/test_e2e_ui_server.py` + `tests/integration/test_router_binding.py`（皆不改，當切換驗收）

- [ ] **Step 1: 在 router.py 加 ROUTES 組裝（全 21 端點，每條帶繁中 summary）**

```python
def build_routes(p, a, c, g, d, n) -> list[Route]:
    """p/a/c/g/d/n = Project/Analysis/Catalog/Graph/Diff/Annotation handler 實例。"""
    return [
        Route("GET",  "/api/project",                              p.get,        summary="讀取當前專案狀態與基本資訊"),
        Route("POST", "/api/set-project",                          p.set_project,summary="切換當前分析的目標專案"),
        Route("GET",  "/api/status",                               p.status,     summary="回報當前專案狀態與建議下一步"),
        Route("POST", "/api/analyze",                              a.analyze,    summary="啟動完整分析的非同步任務（需 API key）"),
        Route("POST", "/api/update",                               a.update,     summary="啟動增量更新分析的非同步任務"),
        Route("GET",  "/api/update/status/{job_id}",               a.update_status, summary="查詢指定分析任務的進度"),
        Route("GET",  "/api/snapshots",                            c.snapshots,  summary="列出所有版本快照"),
        Route("GET",  "/api/timeline",                             c.timeline,   summary="回傳跨版本時間軸"),
        Route("GET",  "/api/report/latest",                        c.report_latest, summary="讀取最近一次分析報告"),
        Route("GET",  "/api/l1",                                   g.get_l1,     summary="讀取指定版本的 L1 功能圖（節點+關聯）"),
        Route("GET",  "/api/l2/{feature_id}",                      g.get_l2,     summary="讀取指定功能的 L2 模組分解（若已生成）"),
        Route("POST", "/api/l2/{feature_id}/generate",            g.generate_l2,summary="為指定功能啟動 L2 生成任務（需 LLM）"),
        Route("GET",  "/api/structure",                            g.get_structure, summary="讀取原始抽取結構 structure.json"),
        Route("GET",  "/api/layer-explanation/{feature_id}/{layer}", g.get_layer_explanation, summary="讀取指定功能在指定層的說明"),
        Route("POST", "/api/layer-explanation/{feature_id}/{layer}/generate", g.generate_layer_explanation, summary="為指定功能層啟動說明生成（需 LLM）"),
        Route("GET",  "/api/diff",                                 d.versions,   summary="比對 baseline 與 current 兩版本的功能層差異"),
        Route("GET",  "/api/diff-explanations/{feature_id}",       d.get_explanation, summary="讀取指定功能的差異說明（若已生成）"),
        Route("POST", "/api/diff-explanations/{feature_id}/generate", d.generate_explanation, summary="為指定功能啟動差異說明生成（需 LLM）"),
        Route("GET",  "/api/doubts",                               n.doubts,     summary="列出作用域分析產生的疑慮項"),
        Route("GET",  "/api/notes",                                n.get_notes,  summary="讀取使用者註記"),
        Route("POST", "/api/notes",                                n.post_notes, summary="新增使用者註記"),
    ]
```

- [ ] **Step 2: 改 server.py — 建 context+router、dispatch 改呼 router**

把 `server.py` 中 `self._api_handlers = APIHandlers(...)`（約 46 行）改為建 `APIContext` + 6 handler + `Router`：

```python
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.router import Router, build_routes
from the_door.core.ui.api.handlers.project import ProjectHandlers
# … 其餘 5 個 handler import

ctx = APIContext(project_root_fn, job_store_fn, switch_project_fn)  # 沿用現有 fn 來源
routes = build_routes(ProjectHandlers(ctx), AnalysisHandlers(ctx), CatalogHandlers(ctx),
                      GraphHandlers(ctx), DiffHandlers(ctx), AnnotationHandlers(ctx))
self._router = Router(ctx, routes)
```

把 `_handle_get` / `_handle_post`（約 134–300 行）整段 if-elif + 重複 body 解析，換成單一：

```python
def _handle_get(handler, router, static_handler):
    path = handler.path.split("?")[0]
    if path.startswith("/api/"):
        query = _parse_query(handler.path)
        status, body = router.dispatch("GET", path, raw_body=b"", query=query)
        _send_json(handler, status, body); return
    static_handler.serve(handler)   # 非 /api/ 仍走靜態

def _handle_post(handler, router):
    path = handler.path.split("?")[0]
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length) if length > 0 else b""
    status, body = router.dispatch("POST", path, raw_body=raw, query=_parse_query(handler.path))
    _send_json(handler, status, body)
```

> body 解析（json.loads / 壞 JSON→400）現在**只在 router 一處**；server.py 不再重複。

`_parse_query` 小 helper（若 server.py 尚無，於此新增）：

```python
from urllib.parse import urlparse, parse_qs
def _parse_query(full_path: str) -> dict:
    qs = parse_qs(urlparse(full_path).query)
    return {k: v[0] for k, v in qs.items()}   # 取首值，扁平化
```

- [ ] **Step 3: 跑兩道安全網 + 全 ui 測試**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/integration/test_e2e_ui_server.py tests/integration/test_router_binding.py tests/unit/core/ui/ -v`
Expected: 全 PASS（行為不變）。若任一紅 → router 綁定或 server 切換有誤，修到綠；**不得修改 e2e / router_binding 斷言**。

- [ ] **Step 4: Commit**

```bash
cd the_door && git add src/the_door/core/ui/api/router.py src/the_door/core/ui/api/__init__.py src/the_door/core/ui/server.py
git commit -m "feat(api): assemble ROUTES + switch server.py to router dispatch"
```

---

## Task 12: 移除舊 `api_handlers.py` 與其舊測試

**Files:**
- Delete: `the_door/src/the_door/core/ui/api_handlers.py`
- Delete: `the_door/tests/unit/core/ui/test_api_handlers.py`、`test_api_handlers_analyze.py`、`test_api_handlers_diff_explanation.py`、`test_api_handlers_notes.py`、`test_api_handlers_set_project.py`、`test_api_handlers_ui3.py`
- Modify: 任何殘留 import `APIHandlers` 處（Task 11 後應只剩無）

- [ ] **Step 1: 確認無殘留 import**

Run: `cd the_door && grep -rn "api_handlers\|APIHandlers" src/ tests/ | grep -v "core/ui/api/"`
Expected: 無輸出（或僅註解）。有則改掉。

- [ ] **Step 2: 刪除舊檔**

```bash
cd the_door && git rm src/the_door/core/ui/api_handlers.py \
  tests/unit/core/ui/test_api_handlers.py tests/unit/core/ui/test_api_handlers_analyze.py \
  tests/unit/core/ui/test_api_handlers_diff_explanation.py tests/unit/core/ui/test_api_handlers_notes.py \
  tests/unit/core/ui/test_api_handlers_set_project.py tests/unit/core/ui/test_api_handlers_ui3.py
```

- [ ] **Step 3: 跑全套測試確認零回歸**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest -q`
Expected: 全 PASS，無 import 錯誤、無指向死類別殘骸。

- [ ] **Step 4: Commit**

```bash
cd the_door && git commit -m "refactor(api): remove old api_handlers.py and its tests (replaced by api/ package)"
```

---

## Task 13: 兩份同源生成文件 + contract 測試

**Files:**
- Create: `the_door/src/the_door/core/ui/api/docgen.py`（從 ROUTES + ERROR_CODES 生成 markdown）
- Create: `docs/api/ai-agent-api-index.md`（生成產物）
- Create: `docs/api/error-codes.md`（生成產物）
- Test: `the_door/tests/unit/core/ui/api/test_docgen.py`

- [ ] **Step 1: 寫失敗測試（contract：文件涵蓋所有 route / 所有碼）**

```python
from pathlib import Path
from the_door.core.ui.api.docgen import render_api_index, render_error_codes
from the_door.core.ui.api.router import build_routes
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.error_codes import ERROR_CODES
from the_door.core.ui.api.handlers.project import ProjectHandlers
from the_door.core.ui.api.handlers.analysis import AnalysisHandlers
from the_door.core.ui.api.handlers.catalog import CatalogHandlers
from the_door.core.ui.api.handlers.graph import GraphHandlers
from the_door.core.ui.api.handlers.diff import DiffHandlers
from the_door.core.ui.api.handlers.annotation import AnnotationHandlers

def _routes():
    ctx = APIContext(lambda: Path("."), lambda: None, lambda p, f: {})
    return build_routes(ProjectHandlers(ctx), AnalysisHandlers(ctx), CatalogHandlers(ctx),
                        GraphHandlers(ctx), DiffHandlers(ctx), AnnotationHandlers(ctx))

def test_api_index_covers_every_route():
    routes = _routes()
    md = render_api_index(routes)
    for rt in routes:
        assert rt.path in md and rt.summary in md

def test_error_doc_covers_every_code():
    md = render_error_codes(ERROR_CODES)
    for code, ec in ERROR_CODES.items():
        assert code in md and ec.desc in md

def test_every_route_summary_nonempty():
    for rt in _routes():
        assert rt.summary.strip()
```

- [ ] **Step 2: 跑測試確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/test_docgen.py -v`
- [ ] **Step 3: 實作 docgen.py**（`render_api_index(routes)`：快速索引表 method·path·summary·handler + 錯誤碼附錄；`render_error_codes(codes)`：code·http·file·desc 表）
- [ ] **Step 4: 跑測試確認 PASS**
- [ ] **Step 5: 生成兩份文件**

新增 `the_door/src/the_door/core/ui/api/_gen_docs.py`（一次性生成腳本，用 `build_routes` + 各 handler 的零依賴 ctx）：

```python
"""Generate the two API docs from ROUTES + ERROR_CODES. Run from the_door/."""
from pathlib import Path
from the_door.core.ui.api import docgen, error_codes
from the_door.core.ui.api.router import build_routes
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.project import ProjectHandlers
from the_door.core.ui.api.handlers.analysis import AnalysisHandlers
from the_door.core.ui.api.handlers.catalog import CatalogHandlers
from the_door.core.ui.api.handlers.graph import GraphHandlers
from the_door.core.ui.api.handlers.diff import DiffHandlers
from the_door.core.ui.api.handlers.annotation import AnnotationHandlers

ctx = APIContext(lambda: Path("."), lambda: None, lambda p, f: {})
routes = build_routes(ProjectHandlers(ctx), AnalysisHandlers(ctx), CatalogHandlers(ctx),
                      GraphHandlers(ctx), DiffHandlers(ctx), AnnotationHandlers(ctx))
out = Path("../docs/api"); out.mkdir(parents=True, exist_ok=True)
(out / "ai-agent-api-index.md").write_text(docgen.render_api_index(routes), encoding="utf-8")
(out / "error-codes.md").write_text(docgen.render_error_codes(error_codes.ERROR_CODES), encoding="utf-8")
print("generated 2 docs")
```

Run: `cd the_door && PYTHONUTF8=1 python -m the_door.core.ui.api._gen_docs`
Expected: 印出 `generated 2 docs`，`docs/api/` 下出現兩檔。

- [ ] **Step 6: Commit**

```bash
cd the_door && git add src/the_door/core/ui/api/docgen.py src/the_door/core/ui/api/_gen_docs.py tests/unit/core/ui/api/test_docgen.py
cd .. && git add docs/api/ai-agent-api-index.md docs/api/error-codes.md
git commit -m "feat(api): doc generators + generated AI-agent API index & error-code catalog"
```

---

## Task 14: 最終驗收

- [ ] **Step 1: 兩道安全網 + 全套 + 覆蓋率**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest --cov=the_door/core/ui/api --cov-report=term-missing -q`
Expected: 全 PASS；`api/` package 各檔 100% 覆蓋（缺口補測試）。

- [ ] **Step 2: 確認 server.py 已是純殼、舊類已除**

Run: `cd the_door && grep -rn "if path ==.*api\|elif path" src/the_door/core/ui/server.py`
Expected: 無大段 if-elif 路由（已由 router 取代）。

- [ ] **Step 3: 結構 diff 驗「只搬位置」**

啟 viewer 對 the_door 重抽取，確認拓樸語意一致（功能集合不因搬檔而少）。或人工核對 21 端點在 ROUTES 表齊全。

- [ ] **Step 4: 最終 commit（如有覆蓋補測）**

```bash
cd the_door && git add -A && git commit -m "test(api): close coverage gaps to 100% for api/ package"
```

---

## 驗收清單（對齊 spec §12）

- [ ] 兩道安全網全綠：e2e（13）+ router_binding（8）= 全 21 端點路由正確性受覆蓋
- [ ] 全套測試零回歸、`api/` package 100% 覆蓋
- [ ] `server.py` 僅剩 HTTP 殼 + 呼叫 router；`api_handlers.py` 已移除
- [ ] 兩份文件生成且 contract 測試通過
- [ ] 錯誤碼回應值英文、route summary 繁中
- [ ] body 解析僅存在於 router 一處（server.py 不再重複）
