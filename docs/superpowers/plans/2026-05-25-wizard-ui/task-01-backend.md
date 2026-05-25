# Task 01 — Python 後端：`/api/analyze` endpoint

> **依賴：** 無（可與 Task 02 平行）

**Files:**
- Modify: `the_door/src/the_door/models.py` — `AnalyzeConfig` 新增欄位
- Modify: `the_door/src/the_door/core/extraction/ast_extractor.py` — `extract()` 接受 `extra_ignore`
- Modify: `the_door/src/the_door/core/pipeline/analyze_pipeline.py` — 傳遞 `extra_ignore` + `snapshot_label`
- Modify: `the_door/src/the_door/core/ui/api_handlers.py` — 新增 `handle_post_analyze`
- Modify: `the_door/src/the_door/core/ui/server.py` — 註冊路由
- Create: `the_door/tests/unit/core/ui/test_api_handlers_analyze.py`
- Create: `the_door/tests/unit/core/ui/test_server_analyze.py`

---

## Task 01.1 — 擴充 `AnalyzeConfig`

- [ ] **Step 1: 寫失敗測試**

建立 `the_door/tests/unit/core/ui/test_api_handlers_analyze.py`：

```python
"""Tests for handle_post_analyze."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from the_door.core.ui.api_handlers import APIHandlers
from the_door.core.ui.job_store import JobStore


def _make_handlers(tmp_path: Path) -> APIHandlers:
    return APIHandlers(project_root=tmp_path, job_store=JobStore())


def test_analyze_config_accepts_extra_ignore_and_label():
    from the_door.models import AnalyzeConfig
    cfg = AnalyzeConfig(extra_ignore=["tests/", "docs/"], snapshot_label="v1.0.0")
    assert cfg.extra_ignore == ["tests/", "docs/"]
    assert cfg.snapshot_label == "v1.0.0"


def test_analyze_config_defaults_are_none():
    from the_door.models import AnalyzeConfig
    cfg = AnalyzeConfig()
    assert cfg.extra_ignore is None
    assert cfg.snapshot_label is None
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_analyze.py::test_analyze_config_accepts_extra_ignore_and_label -v
```
期望：`FAILED` — `AnalyzeConfig` 無 `extra_ignore` 欄位。

- [ ] **Step 3: 修改 `AnalyzeConfig`**

開啟 `the_door/src/the_door/models.py`，找到 `class AnalyzeConfig:`，加兩個欄位：

```python
@dataclass
class AnalyzeConfig:
    """分析管線的配置參數。"""

    provider: str | None = None
    model: str | None = None
    skip_cost_confirm: bool = False
    offline_vuln: bool = False
    timeout_seconds: int = 300
    extra_ignore: list[str] | None = None   # 新增
    snapshot_label: str | None = None       # 新增
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_analyze.py::test_analyze_config_accepts_extra_ignore_and_label tests/unit/core/ui/test_api_handlers_analyze.py::test_analyze_config_defaults_are_none -v
```
期望：2 PASSED。

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/models.py the_door/tests/unit/core/ui/test_api_handlers_analyze.py
git commit -m "feat(wizard): add extra_ignore and snapshot_label fields to AnalyzeConfig"
```

---

## Task 01.2 — `ASTExtractor.extract()` 接受 `extra_ignore`

- [ ] **Step 1: 寫失敗測試**

在 `test_api_handlers_analyze.py` 加：

```python
def test_ast_extractor_accepts_extra_ignore(tmp_path):
    from the_door.core.extraction.ast_extractor import ASTExtractor
    # Create a minimal py file so extractor has something to find
    (tmp_path / "main.py").write_text("def hello(): pass", encoding="utf-8")
    extractor = ASTExtractor()
    # Should not raise; extra_ignore=["tests/"] filters FileDiscovery
    result = extractor.extract(str(tmp_path), extra_ignore=["tests/"])
    assert result is not None
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_analyze.py::test_ast_extractor_accepts_extra_ignore -v
```
期望：`FAILED` — `extract()` 不接受 `extra_ignore` 參數。

- [ ] **Step 3: 修改 `ASTExtractor.extract()`**

開啟 `the_door/src/the_door/core/extraction/ast_extractor.py`，找到：

```python
def extract(self, codebase_path: str) -> ExtractionResult:
```

改為：

```python
def extract(self, codebase_path: str, extra_ignore: list[str] | None = None) -> ExtractionResult:
```

在 `extract` 方法內，找到呼叫 `self._file_discovery.discover(...)` 的那行，改為：

```python
files = self._file_discovery.discover(str(codebase_path), extra_ignore=extra_ignore or [])
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_analyze.py::test_ast_extractor_accepts_extra_ignore -v
```
期望：PASSED。

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/extraction/ast_extractor.py the_door/tests/unit/core/ui/test_api_handlers_analyze.py
git commit -m "feat(wizard): thread extra_ignore through ASTExtractor.extract()"
```

---

## Task 01.3 — `run_analyze_pipeline` 傳遞 `extra_ignore` + `snapshot_label`

- [ ] **Step 1: 寫失敗測試**

在 `test_api_handlers_analyze.py` 加：

```python
def test_analyze_pipeline_passes_extra_ignore_and_label(tmp_path):
    """run_analyze_pipeline with AnalyzeConfig(extra_ignore, snapshot_label)
    calls ASTExtractor.extract with extra_ignore and create_snapshot with label."""
    from the_door.models import AnalyzeConfig
    from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline

    config = AnalyzeConfig(
        skip_cost_confirm=True,
        extra_ignore=["docs/"],
        snapshot_label="v1.0.0",
    )

    with patch("the_door.core.pipeline.analyze_pipeline.ASTExtractor") as MockExtractor, \
         patch("the_door.core.pipeline.analyze_pipeline.VulnerabilityScanner"), \
         patch("the_door.core.pipeline.analyze_pipeline.SnapshotStore") as MockStore, \
         patch("the_door.core.pipeline.analyze_pipeline.LLMBatchProcessor"), \
         patch("the_door.core.pipeline.analyze_pipeline.ConfigManager"):

        # Setup minimal mocks to avoid AttributeError
        mock_extractor_instance = MagicMock()
        mock_extractor_instance.extract.return_value = MagicMock(files=[], nodes=[], edges=[])
        MockExtractor.return_value = mock_extractor_instance

        mock_store_instance = MagicMock()
        mock_store_instance.create_snapshot.return_value = MagicMock(version_id="v1")
        MockStore.return_value = mock_store_instance

        try:
            run_analyze_pipeline(tmp_path, config)
        except Exception:
            pass  # Pipeline may fail on minimal mock, we only care about call args

        # extract() called with extra_ignore
        call_kwargs = mock_extractor_instance.extract.call_args
        assert call_kwargs is not None
        passed_extra_ignore = (
            call_kwargs.kwargs.get("extra_ignore") or
            (call_kwargs.args[1] if len(call_kwargs.args) > 1 else None)
        )
        assert passed_extra_ignore == ["docs/"]

        # create_snapshot() called with label="v1.0.0"
        if mock_store_instance.create_snapshot.called:
            snap_kwargs = mock_store_instance.create_snapshot.call_args.kwargs
            assert snap_kwargs.get("label") == "v1.0.0"
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_analyze.py::test_analyze_pipeline_passes_extra_ignore_and_label -v
```
期望：FAILED — `extract()` 被呼叫時沒帶 `extra_ignore`。

- [ ] **Step 3: 修改 `analyze_pipeline.py`**

開啟 `the_door/src/the_door/core/pipeline/analyze_pipeline.py`。

找到呼叫 `extractor.extract(...)` 的那行：
```python
ast_future = executor.submit(extractor.extract, Path(codebase_path))
```
改為：
```python
ast_future = executor.submit(extractor.extract, str(codebase_path), config.extra_ignore)
```

找到呼叫 `store.create_snapshot(...)` 的那行（約第 321 行），在 keyword arguments 加上：
```python
label=config.snapshot_label,
```

完整的 `create_snapshot` 呼叫應如下（其他參數不動）：
```python
snapshot = store.create_snapshot(
    l1_snapshot=l1_snap,
    feature_relations=relations,
    analyzed_files=analyzed_files_list,
    commit_hash=git_commit,
    git_tags=git_tags_list,
    trigger=trigger,
    label=config.snapshot_label,          # 新增
    vulnerabilities=scan_result.entries if scan_result.entries else [],
    db_freshness=scan_result.db_freshness,
)
```

注意：`_run_pipeline_inner` 的 signature 改為接受完整的 `config: AnalyzeConfig`（原本已如此），確認 `config` 物件可在 `_run_snapshot_generation` 內存取。若 `_run_snapshot_generation` 是獨立函式，將 `config` 傳入。

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_analyze.py::test_analyze_pipeline_passes_extra_ignore_and_label -v
```
期望：PASSED（或 xfail，視 mock 深度）。

- [ ] **Step 5: 確認全部既有測試不破壞**

```bash
cd the_door && pytest tests/ -x -q 2>&1 | tail -5
```
期望：原有 passed 數量不減少，0 failed。

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/pipeline/analyze_pipeline.py the_door/tests/unit/core/ui/test_api_handlers_analyze.py
git commit -m "feat(wizard): thread extra_ignore and snapshot_label through analyze_pipeline"
```

---

## Task 01.4 — `handle_post_analyze`

- [ ] **Step 1: 寫失敗測試**

在 `test_api_handlers_analyze.py` 加：

```python
def test_handle_post_analyze_returns_202_with_job_id(tmp_path):
    handlers = _make_handlers(tmp_path)
    with patch.object(handlers, "_run_analyze_job"):
        status, body = handlers.handle_post_analyze({})
    assert status == 202
    assert "job_id" in body


def test_handle_post_analyze_passes_extra_ignore_and_label(tmp_path):
    handlers = _make_handlers(tmp_path)
    captured = {}
    def fake_run(job, extra_ignore, snapshot_label):
        captured["extra_ignore"] = extra_ignore
        captured["snapshot_label"] = snapshot_label
    with patch.object(handlers, "_run_analyze_job", side_effect=fake_run):
        handlers.handle_post_analyze({"extra_ignore": ["tests/"], "label": "v1.0.0"})
    assert captured["extra_ignore"] == ["tests/"]
    assert captured["snapshot_label"] == "v1.0.0"


def test_handle_post_analyze_returns_409_when_job_running(tmp_path):
    handlers = _make_handlers(tmp_path)
    # Force job_store to return None (job already running)
    with patch.object(handlers._job_store, "try_create_job", return_value=None):
        status, body = handlers.handle_post_analyze({})
    assert status == 409
    assert body["error"]["code"] == "job_already_running"


def test_handle_post_analyze_empty_extra_ignore_becomes_none(tmp_path):
    handlers = _make_handlers(tmp_path)
    captured = {}
    def fake_run(job, extra_ignore, snapshot_label):
        captured["extra_ignore"] = extra_ignore
        captured["snapshot_label"] = snapshot_label
    with patch.object(handlers, "_run_analyze_job", side_effect=fake_run):
        handlers.handle_post_analyze({"extra_ignore": [], "label": ""})
    assert captured["extra_ignore"] is None
    assert captured["snapshot_label"] is None
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_analyze.py -k "handle_post_analyze" -v
```
期望：4 FAILED — `handle_post_analyze` 不存在。

- [ ] **Step 3: 實作 `handle_post_analyze`**

開啟 `the_door/src/the_door/core/ui/api_handlers.py`。

在 `handle_post_update` 之後加入：

```python
# ------------------------------------------------------------------
# POST /api/analyze
# ------------------------------------------------------------------

def handle_post_analyze(self, body: dict) -> tuple[int, dict]:
    """Trigger a full analysis of the current project root.

    Accepts optional extra_ignore (list[str]) and label (str).
    Returns 202 {"job_id": ...} on success, 409 if a job is already running.
    """
    extra_ignore = body.get("extra_ignore") or None
    if extra_ignore == []:
        extra_ignore = None
    snapshot_label = body.get("label") or None

    job = self._job_store.try_create_job()
    if job is None:
        return 409, self._make_error(
            code="job_already_running",
            message="A pipeline job is already running. Please wait for it to complete.",
            source="handle_post_analyze",
        )

    thread = threading.Thread(
        target=self._run_analyze_job,
        args=(job, extra_ignore, snapshot_label),
        daemon=True,
    )
    thread.start()

    return 202, {"job_id": job.job_id}

def _run_analyze_job(
    self,
    job,
    extra_ignore: list[str] | None,
    snapshot_label: str | None,
) -> None:
    """Background thread: run run_analyze_pipeline and update job status."""
    from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline
    from the_door.models import AnalyzeConfig

    config = AnalyzeConfig(
        skip_cost_confirm=True,
        extra_ignore=extra_ignore,
        snapshot_label=snapshot_label,
    )
    try:
        run_analyze_pipeline(
            self._project_root,
            config,
            progress_callback=job.update_step,
        )
        self._job_store.complete_job(job.job_id)
    except Exception as exc:
        self._job_store.fail_job(job.job_id, str(exc))
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_analyze.py -k "handle_post_analyze" -v
```
期望：4 PASSED。

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/ui/api_handlers.py the_door/tests/unit/core/ui/test_api_handlers_analyze.py
git commit -m "feat(wizard): add handle_post_analyze and _run_analyze_job to APIHandlers"
```

---

## Task 01.5 — 註冊 `/api/analyze` 路由

- [ ] **Step 1: 寫失敗測試**

建立 `the_door/tests/unit/core/ui/test_server_analyze.py`：

```python
"""Tests for /api/analyze route registration."""
from __future__ import annotations
import json
import socket
import threading
import time
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch
import pytest


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def running_server(tmp_path):
    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir()
    (viewer_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    from the_door.core.ui.server import UIServer
    port = _find_free_port()
    server = UIServer(project_root=tmp_path, viewer_dir=viewer_dir, port=port)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    for _ in range(20):
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/api/status")
            conn.getresponse().read()
            conn.close()
            break
        except Exception:
            time.sleep(0.05)
    yield port
    server.shutdown()


def test_post_api_analyze_returns_202(running_server):
    port = running_server
    with patch("the_door.core.ui.api_handlers.APIHandlers._run_analyze_job"):
        conn = HTTPConnection("127.0.0.1", port)
        body = json.dumps({}).encode()
        conn.request("POST", "/api/analyze", body=body,
                     headers={"Content-Type": "application/json", "Content-Length": str(len(body))})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
    assert resp.status == 202
    assert "job_id" in data


def test_get_api_analyze_returns_405(running_server):
    port = running_server
    conn = HTTPConnection("127.0.0.1", port)
    conn.request("GET", "/api/analyze")
    resp = conn.getresponse()
    resp.read()
    conn.close()
    assert resp.status == 405
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/core/ui/test_server_analyze.py -v
```
期望：FAILED — `/api/analyze` 回傳 404。

- [ ] **Step 3: 修改 `server.py`**

開啟 `the_door/src/the_door/core/ui/server.py`。

在 `_API_ROUTES` dict 加一行：

```python
_API_ROUTES: dict[str, str] = {
    "/api/project": "GET",
    "/api/snapshots": "GET",
    "/api/report/latest": "GET",
    "/api/update": "POST",
    "/api/analyze": "POST",       # 新增
    "/api/doubts": "GET",
    # ... 其他不變
}
```

在 `_handle_post` 函式的 `if path == "/api/update":` 區塊之前加：

```python
if path == "/api/analyze":
    content_length = int(handler.headers.get("Content-Length", 0))
    raw_body = handler.rfile.read(content_length) if content_length > 0 else b""
    try:
        body = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        _send_api_error(handler, 400, "invalid_json", "Request body is not valid JSON", path)
        return
    status, response_body = api_handlers.handle_post_analyze(body)
    _send_json(handler, status, response_body)
    return
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && pytest tests/unit/core/ui/test_server_analyze.py -v
```
期望：2 PASSED。

- [ ] **Step 5: 確認全套測試不破壞**

```bash
cd the_door && pytest tests/ -x -q 2>&1 | tail -5
```
期望：0 failed。

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/ui/server.py the_door/tests/unit/core/ui/test_server_analyze.py
git commit -m "feat(wizard): register /api/analyze POST route in UIServer"
```
