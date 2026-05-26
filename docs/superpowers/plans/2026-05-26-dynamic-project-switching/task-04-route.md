# Task 04 — `handle_post_set_project` + `/api/set-project` 路由

> **依賴：** Task 03 完成

**Files:**
- Modify: `the_door/src/the_door/core/ui/api_handlers.py`
- Modify: `the_door/src/the_door/core/ui/server.py`
- Modify: `the_door/tests/unit/core/ui/test_api_handlers_set_project.py`（新增測試）
- Modify: `the_door/tests/unit/core/ui/test_server_set_project.py`（新增路由測試）

---

## Task 04.1 — `handle_post_set_project` 在 `APIHandlers`

- [ ] **Step 1: 寫失敗測試**

在 `test_api_handlers_set_project.py` 加：

```python
import os
from the_door.core.ui.api_handlers import APIHandlers


def _make_handlers(tmp_path, switch_fn=None):
    return APIHandlers(
        project_root=tmp_path,
        job_store=JobStore(),
        switch_project_fn=switch_fn or (lambda path, force: {"status": "switched", "path": str(path)}),
    )


def test_set_project_returns_200_on_valid_path(tmp_path):
    handlers = _make_handlers(tmp_path)
    result_path = tmp_path / "proj"
    result_path.mkdir()
    status, body = handlers.handle_post_set_project({"path": str(result_path)})
    assert status == 200
    assert body["status"] == "switched"


def test_set_project_returns_400_on_nonexistent_path(tmp_path):
    handlers = _make_handlers(tmp_path)
    status, body = handlers.handle_post_set_project({"path": str(tmp_path / "nonexistent")})
    assert status == 400
    assert body["status"] == "error"


def test_set_project_returns_400_on_file_not_dir(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    handlers = _make_handlers(tmp_path)
    status, body = handlers.handle_post_set_project({"path": str(f)})
    assert status == 400
    assert body["status"] == "error"


def test_set_project_returns_400_on_empty_path(tmp_path):
    handlers = _make_handlers(tmp_path)
    status, body = handlers.handle_post_set_project({"path": ""})
    assert status == 400
    assert body["status"] == "error"


def test_set_project_returns_409_on_conflict(tmp_path):
    new_path = tmp_path / "new"
    new_path.mkdir()
    handlers = _make_handlers(
        tmp_path,
        switch_fn=lambda path, force: {"status": "conflict", "active_job_id": "job-1", "message": "busy"},
    )
    status, body = handlers.handle_post_set_project({"path": str(new_path)})
    assert status == 409
    assert body["status"] == "conflict"
    assert "active_job_id" in body


def test_set_project_passes_force_true(tmp_path):
    new_path = tmp_path / "new"
    new_path.mkdir()
    received = []
    def capture_switch(path, force):
        received.append(force)
        return {"status": "switched", "path": str(path)}

    handlers = _make_handlers(tmp_path, switch_fn=capture_switch)
    handlers.handle_post_set_project({"path": str(new_path), "force": True})
    assert received == [True]


def test_set_project_force_defaults_to_false(tmp_path):
    new_path = tmp_path / "new"
    new_path.mkdir()
    received = []
    def capture_switch(path, force):
        received.append(force)
        return {"status": "switched", "path": str(path)}

    handlers = _make_handlers(tmp_path, switch_fn=capture_switch)
    handlers.handle_post_set_project({"path": str(new_path)})
    assert received == [False]
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_set_project.py -k "set_project" -v
```
期望：7 FAILED（`handle_post_set_project` 不存在）。

- [ ] **Step 3: 實作 `handle_post_set_project`**

開啟 `the_door/src/the_door/core/ui/api_handlers.py`。

首先確認 `import os` 在檔案頂部的 import 區段中已存在；若無則加入。

接著在 `handle_post_analyze` 之後加：

```python
# ------------------------------------------------------------------
# POST /api/set-project
# ------------------------------------------------------------------

def handle_post_set_project(self, body: dict) -> tuple[int, dict]:
    """Validate path and delegate switching to _switch_project_fn.

    Returns:
        200 {"status": "switched", "path": "..."}
        400 {"status": "error", "message": "..."}
        409 {"status": "conflict", "active_job_id": "...", "message": "..."}
    """
    path_str = body.get("path", "")
    force = bool(body.get("force", False))

    if not path_str:
        return 400, {"status": "error", "message": "路徑不存在或無法讀取"}

    try:
        path = Path(path_str)
    except Exception:
        return 400, {"status": "error", "message": "路徑格式無效"}

    if not path.exists() or not path.is_dir() or not os.access(path, os.R_OK):
        return 400, {"status": "error", "message": "路徑不存在或無法讀取"}

    result = self._switch_project_fn(path, force)
    if result["status"] == "switched":
        return 200, result
    if result["status"] == "conflict":
        return 409, result
    return 400, result
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_set_project.py -k "set_project" -v
```
期望：7 PASSED。

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/ui/api_handlers.py the_door/tests/unit/core/ui/test_api_handlers_set_project.py
git commit -m "feat(switch): add handle_post_set_project to APIHandlers"
```

---

## Task 04.2 — 註冊 `/api/set-project` 路由

- [ ] **Step 1: 在 `test_server_set_project.py` 加路由測試**

在 `test_server_set_project.py` 加（在既有 import 後新增 fixtures）：

```python
import json
import socket
import time
from http.client import HTTPConnection
from unittest.mock import patch


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def running_server(tmp_path):
    import threading as _threading
    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir()
    (viewer_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    from the_door.core.ui.server import UIServer
    port = _find_free_port()
    server = UIServer(project_root=tmp_path, viewer_dir=viewer_dir, port=port)
    t = _threading.Thread(target=server.start, daemon=True)
    t.start()
    for _ in range(20):
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/api/status")
            conn.getresponse().read()
            conn.close()
            break
        except Exception:
            time.sleep(0.05)
    yield tmp_path, port
    server.shutdown()


def test_post_set_project_returns_200(running_server, tmp_path):
    project_path, port = running_server
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    conn = HTTPConnection("127.0.0.1", port)
    body = json.dumps({"path": str(new_path)}).encode()
    conn.request("POST", "/api/set-project", body=body,
                 headers={"Content-Type": "application/json", "Content-Length": str(len(body))})
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    assert resp.status == 200
    assert data["status"] == "switched"


def test_get_set_project_returns_405(running_server):
    _, port = running_server
    conn = HTTPConnection("127.0.0.1", port)
    conn.request("GET", "/api/set-project")
    resp = conn.getresponse()
    resp.read()
    conn.close()
    assert resp.status == 405
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/core/ui/test_server_set_project.py -k "post_set_project or get_set_project" -v
```
期望：FAILED — 404。

- [ ] **Step 3: 修改 `server.py`**

**3a.** 在 `_API_ROUTES` dict 加一行：
```python
    "/api/set-project": "POST",
```

**3b.** 在 `_handle_post` 函式，在 `if path == "/api/analyze":` 區塊之前加：

```python
    if path == "/api/set-project":
        content_length = int(handler.headers.get("Content-Length", 0))
        raw_body = handler.rfile.read(content_length) if content_length > 0 else b""
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            _send_api_error(handler, 400, "invalid_json", "Request body is not valid JSON", path)
            return
        status, response_body = api_handlers.handle_post_set_project(body)
        _send_json(handler, status, response_body)
        return
```

- [ ] **Step 4: 確認路由測試通過**

```bash
cd the_door && pytest tests/unit/core/ui/test_server_set_project.py -v
```
期望：所有 PASSED。

- [ ] **Step 5: 確認全套測試不破壞**

```bash
cd the_door && pytest tests/ -x -q 2>&1 | tail -5
```
期望：0 failed。

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/ui/server.py the_door/tests/unit/core/ui/test_server_set_project.py
git commit -m "feat(switch): register /api/set-project POST route in UIServer"
```
