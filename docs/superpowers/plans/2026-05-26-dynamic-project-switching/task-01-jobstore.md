# Task 01 — JobStore: `get_running_job_id()`

> **依賴：** 無

**Files:**
- Modify: `the_door/src/the_door/core/ui/job_store.py`
- Modify: `the_door/tests/unit/core/ui/test_api_handlers_set_project.py`（建立新檔）

---

## Task 01.1 — 新增 `get_running_job_id()`

- [ ] **Step 1: 建立測試檔，寫失敗測試**

建立 `the_door/tests/unit/core/ui/test_api_handlers_set_project.py`：

```python
"""Tests for handle_post_set_project and JobStore.get_running_job_id."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch
import pytest
from the_door.core.ui.job_store import JobStore


def test_get_running_job_id_returns_none_when_no_job():
    store = JobStore()
    assert store.get_running_job_id() is None


def test_get_running_job_id_returns_id_when_running():
    store = JobStore()
    job = store.try_create_job()
    assert store.get_running_job_id() == job.job_id


def test_get_running_job_id_returns_none_after_complete():
    store = JobStore()
    job = store.try_create_job()
    store.complete_job(job.job_id)
    assert store.get_running_job_id() is None
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_set_project.py::test_get_running_job_id_returns_none_when_no_job -v
```
期望：`FAILED` — `JobStore` 無 `get_running_job_id` 方法。

- [ ] **Step 3: 新增方法到 `job_store.py`**

開啟 `the_door/src/the_door/core/ui/job_store.py`，在 `has_running_job` property 之後加：

```python
def get_running_job_id(self) -> str | None:
    """Return the job_id of the currently running job, or None."""
    with self._lock:
        return self._current_job.job_id if self._current_job is not None else None
```

- [ ] **Step 4: 確認測試通過**

```bash
cd the_door && pytest tests/unit/core/ui/test_api_handlers_set_project.py::test_get_running_job_id_returns_none_when_no_job tests/unit/core/ui/test_api_handlers_set_project.py::test_get_running_job_id_returns_id_when_running tests/unit/core/ui/test_api_handlers_set_project.py::test_get_running_job_id_returns_none_after_complete -v
```
期望：3 PASSED。

- [ ] **Step 5: 確認全套測試不破壞**

```bash
cd the_door && pytest tests/ -x -q 2>&1 | tail -5
```
期望：0 failed。

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/ui/job_store.py the_door/tests/unit/core/ui/test_api_handlers_set_project.py
git commit -m "feat(switch): add JobStore.get_running_job_id()"
```
