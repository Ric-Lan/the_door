# Phase 02 — 根模組（Task 2–4）

> 讀本檔 + README 即可執行。順序：error_codes → context → router（router 依賴 error_codes）。

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

- [ ] **Step 3: 跑測試，確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/test_error_codes.py -v`（FAIL：module 不存在）

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

- [ ] **Step 5: 跑測試，確認 PASS** — `cd the_door && python -m pytest tests/unit/core/ui/api/test_error_codes.py -v`（若 `test_descs_are_english_ascii` 紅 → 把該 desc 改英文）

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

- [ ] **Step 2: 跑測試，確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/test_context.py -v`（FAIL：module 不存在）

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

- [ ] **Step 4: 跑測試，確認 PASS** — `cd the_door && python -m pytest tests/unit/core/ui/api/test_context.py -v`

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

> 本任務先建 router 機制，用**假 handler** 測試；真實 `build_routes` 在 Task 11（Phase 04）組裝。

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

- [ ] **Step 2: 跑測試，確認 FAIL** — `cd the_door && python -m pytest tests/unit/core/ui/api/test_router.py -v`（FAIL：module 不存在）

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

- [ ] **Step 4: 跑測試，確認 PASS** — `cd the_door && python -m pytest tests/unit/core/ui/api/test_router.py -v`

- [ ] **Step 5: Commit**

```bash
cd the_door && git add src/the_door/core/ui/api/router.py tests/unit/core/ui/api/test_router.py
git commit -m "feat(api): router dispatch hub with template match + locatable handler errors"
```
