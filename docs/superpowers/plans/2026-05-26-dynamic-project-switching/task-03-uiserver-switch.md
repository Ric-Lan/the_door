# Task 03 — UIServer: `_switch_lock` + `_switch_project()` + lambda 注入

> **依賴：** Task 01（`get_running_job_id`）+ Task 02（callable injection）完成

**Files:**
- Modify: `the_door/src/the_door/core/ui/server.py`
- Create: `the_door/tests/unit/core/ui/test_server_set_project.py`

---

## Task 03.1 — `UIServer._switch_project()` 方法 + `_switch_lock`

- [ ] **Step 1: 寫失敗測試**

建立 `the_door/tests/unit/core/ui/test_server_set_project.py`：

```python
"""Tests for UIServer._switch_project() and lock behavior."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from the_door.core.ui.server import UIServer
from the_door.core.ui.job_store import JobStore


def _make_server(tmp_path: Path) -> UIServer:
    viewer_dir = tmp_path / "viewer"
    viewer_dir.mkdir()
    (viewer_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    return UIServer(project_root=tmp_path, viewer_dir=viewer_dir, port=0)


def test_switch_project_returns_switched_on_valid_path(tmp_path):
    server = _make_server(tmp_path)
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    result = server._switch_project(new_path, force=False)
    assert result["status"] == "switched"
    assert result["path"] == str(new_path)
    assert server._project_root == new_path


def test_switch_project_returns_conflict_when_job_running(tmp_path):
    server = _make_server(tmp_path)
    job = server._job_store.try_create_job()
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    result = server._switch_project(new_path, force=False)
    assert result["status"] == "conflict"
    assert result["active_job_id"] == job.job_id
    # project_root NOT changed
    assert server._project_root == tmp_path


def test_switch_project_force_cancels_running_job(tmp_path):
    server = _make_server(tmp_path)
    job = server._job_store.try_create_job()
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    result = server._switch_project(new_path, force=True)
    assert result["status"] == "switched"
    # old job is now failed
    old_store = server._api_handlers._job_store
    # new job_store is empty (no running job)
    assert not server._job_store.has_running_job


def test_switch_project_replaces_job_store_on_success(tmp_path):
    server = _make_server(tmp_path)
    old_job_store = server._job_store
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    server._switch_project(new_path, force=False)
    assert server._job_store is not old_job_store


def test_switch_project_api_handlers_sees_new_root(tmp_path):
    server = _make_server(tmp_path)
    new_path = tmp_path / "new_project"
    new_path.mkdir()
    server._switch_project(new_path, force=False)
    # APIHandlers uses lambda — must return new path
    assert server._api_handlers._project_root == new_path
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/core/ui/test_server_set_project.py -v
```
期望：全部 FAILED（`UIServer` 無 `_switch_project` 方法）。

- [ ] **Step 3: 修改 `server.py`**

開啟 `the_door/src/the_door/core/ui/server.py`。

**3a.** 在 import 區加：
```python
import threading
```
（若已存在則跳過）

**3b.** 在 `UIServer.__init__` 中，找到：
```python
        self._job_store = JobStore()
        self._api_handlers = APIHandlers(project_root=project_root, job_store=self._job_store)
```
改為：
```python
        self._job_store = JobStore()
        self._switch_lock = threading.Lock()
        self._api_handlers = APIHandlers(
            project_root_fn=lambda: self._project_root,
            job_store_fn=lambda: self._job_store,
            switch_project_fn=self._switch_project,
        )
```

**3c.** 在 `shutdown()` 方法之後加入新方法：

```python
    def _switch_project(self, new_path: Path, force: bool) -> dict:
        """Switch the server's bound project path.

        Thread-safe: protected by _switch_lock.
        Returns a dict suitable for JSON serialisation.
        """
        with self._switch_lock:
            running_job_id = self._job_store.get_running_job_id()
            if running_job_id is not None:
                if not force:
                    return {
                        "status": "conflict",
                        "active_job_id": running_job_id,
                        "message": "有進行中的分析任務，請選擇處理方式",
                    }
                self._job_store.fail_job(running_job_id, "switched away")
            self._project_root = new_path
            self._job_store = JobStore()
            return {"status": "switched", "path": str(new_path)}
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && pytest tests/unit/core/ui/test_server_set_project.py -v
```
期望：5 PASSED。

- [ ] **Step 5: 確認全套測試不破壞**

```bash
cd the_door && pytest tests/ -x -q 2>&1 | tail -5
```
期望：0 failed。

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/ui/server.py the_door/tests/unit/core/ui/test_server_set_project.py
git commit -m "feat(switch): add UIServer._switch_project() with threading.Lock and lambda injection"
```
