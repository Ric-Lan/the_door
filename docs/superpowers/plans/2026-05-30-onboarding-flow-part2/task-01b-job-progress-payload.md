# Task 1b — UpdateJob.progress + handle_get_update_status payload

**Goal:** Add `progress` field + `update_progress()` to `UpdateJob`; surface it via `handle_get_update_status` payload so frontend can render file-level feed.

**Dependencies:** task 1a (ProgressReporter sink hooks into `job.update_progress`).

**Files:**
- Modify: `the_door/src/the_door/core/ui/job_store.py` (add `progress` field + `update_progress` method)
- Modify: `the_door/src/the_door/core/ui/api_handlers.py:343` (`handle_get_update_status` payload — add `progress`)
- Modify: `the_door/src/the_door/core/ui/api_handlers.py` (`_run_analyze_job` / `_run_update_job` — replace TODO sink with `job.update_progress`)
- Modify: `the_door/tests/unit/core/ui/test_job_store.py` (add progress tests)
- Create: `the_door/tests/unit/core/ui/test_handle_get_update_status_progress.py`

---

- [ ] **Step 1: Add failing tests for `UpdateJob.progress`**

Append to `the_door/tests/unit/core/ui/test_job_store.py`:

```python
def test_job_progress_default_none():
    from the_door.core.ui.job_store import UpdateJob
    job = UpdateJob(job_id="t")
    assert job.progress is None


def test_update_progress_sets_field():
    from the_door.core.ui.job_store import UpdateJob
    job = UpdateJob(job_id="t")
    job.update_progress({
        "files_done": 5, "files_total": 10,
        "current_file": "a.py", "current_root": "new",
    })
    assert job.progress == {
        "files_done": 5, "files_total": 10,
        "current_file": "a.py", "current_root": "new",
    }


def test_update_progress_overwrites():
    from the_door.core.ui.job_store import UpdateJob
    job = UpdateJob(job_id="t")
    job.update_progress({"files_done": 1, "files_total": 10, "current_file": "a.py", "current_root": "new"})
    job.update_progress({"files_done": 2, "files_total": 10, "current_file": "b.py", "current_root": "new"})
    assert job.progress["files_done"] == 2
    assert job.progress["current_file"] == "b.py"


def test_update_progress_thread_safe():
    """Calling update_progress while holding job._lock must not deadlock."""
    import threading
    from the_door.core.ui.job_store import UpdateJob
    job = UpdateJob(job_id="t")
    barrier = threading.Barrier(5)
    def worker(i):
        barrier.wait()
        for _ in range(20):
            job.update_progress({
                "files_done": i, "files_total": 100,
                "current_file": f"f{i}.py", "current_root": "new",
            })
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=5)
    assert all(not t.is_alive() for t in threads)
    assert job.progress is not None
```

- [ ] **Step 2: Run job_store tests, verify new ones FAIL**

```bash
pytest the_door/tests/unit/core/ui/test_job_store.py -v -k "progress"
```
Expected: 4 fail (AttributeError on `progress` / `update_progress`).

- [ ] **Step 3: Add `progress` field + `update_progress` to `UpdateJob`**

Modify `the_door/src/the_door/core/ui/job_store.py`:

In `@dataclass class UpdateJob`, add field after `error_message`:
```python
    progress: Optional[dict] = None
```

Add method after `update_step`:
```python
    def update_progress(self, progress: dict) -> None:
        """Set the file-level progress dict (None / {files_done, files_total, current_file, current_root})."""
        with self._lock:
            self.progress = dict(progress) if progress is not None else None
```

- [ ] **Step 4: Run job_store tests, verify all PASS**

```bash
pytest the_door/tests/unit/core/ui/test_job_store.py -v
```
Expected: all pass (originals + 4 new).

- [ ] **Step 5: Add failing test for handle_get_update_status payload**

Path: `the_door/tests/unit/core/ui/test_handle_get_update_status_progress.py`

```python
"""Test handle_get_update_status payload includes progress field when set."""
from __future__ import annotations

import pytest


def _make_handler(tmp_path):
    from the_door.core.ui.api_handlers import Handler
    from the_door.core.ui.job_store import JobStore
    return Handler(project_root=tmp_path, job_store=JobStore()), JobStore()


def test_payload_includes_progress_null_by_default(tmp_path):
    from the_door.core.ui.api_handlers import Handler
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    handler = Handler(project_root=tmp_path, job_store=store)
    job = store.try_create_job()
    code, body = handler.handle_get_update_status(job.job_id)
    assert code == 200
    assert "progress" in body
    assert body["progress"] is None


def test_payload_includes_progress_dict_when_set(tmp_path):
    from the_door.core.ui.api_handlers import Handler
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    handler = Handler(project_root=tmp_path, job_store=store)
    job = store.try_create_job()
    job.update_progress({
        "files_done": 42, "files_total": 100,
        "current_file": "src/foo.py", "current_root": "new",
    })
    code, body = handler.handle_get_update_status(job.job_id)
    assert body["progress"] == {
        "files_done": 42, "files_total": 100,
        "current_file": "src/foo.py", "current_root": "new",
    }


def test_payload_progress_reflects_latest_update(tmp_path):
    from the_door.core.ui.api_handlers import Handler
    from the_door.core.ui.job_store import JobStore
    store = JobStore()
    handler = Handler(project_root=tmp_path, job_store=store)
    job = store.try_create_job()
    job.update_progress({"files_done": 1, "files_total": 10, "current_file": "a.py", "current_root": "new"})
    job.update_progress({"files_done": 9, "files_total": 10, "current_file": "z.py", "current_root": "new"})
    code, body = handler.handle_get_update_status(job.job_id)
    assert body["progress"]["files_done"] == 9
    assert body["progress"]["current_file"] == "z.py"
```

- [ ] **Step 6: Run payload tests, verify FAIL**

```bash
pytest the_door/tests/unit/core/ui/test_handle_get_update_status_progress.py -v
```
Expected: 3 fail (`progress` key missing from payload).

- [ ] **Step 7: Patch `handle_get_update_status` to surface progress**

Modify `the_door/src/the_door/core/ui/api_handlers.py` — locate `handle_get_update_status` (around line 333). In the response-building block, add `progress` field. Existing response likely builds a dict like:

```python
response = {
    "job_id": job.job_id,
    "status": job.status,
    "current_step": job.current_step,
    "steps": list(job.steps),
}
if job.error_message:
    response["error_message"] = job.error_message
return 200, response
```

Add one line before `return`:
```python
response["progress"] = job.progress  # None or {files_done, files_total, current_file, current_root}
```

(Read lines 333-365 to find exact insertion point.)

- [ ] **Step 8: Run payload tests, verify PASS**

```bash
pytest the_door/tests/unit/core/ui/test_handle_get_update_status_progress.py -v
```
Expected: 3 pass.

- [ ] **Step 9: Replace task 1a's TODO sink in `_run_analyze_job` / `_run_update_job`**

Modify `the_door/src/the_door/core/ui/api_handlers.py`:

Locate the `reporter = ProgressReporter(sink=lambda _d: None)  # TODO 1b` lines (added in task 1a). Replace with:

```python
reporter = ProgressReporter(sink=job.update_progress)
```

(Both `_run_analyze_job` around line 272 and `_run_update_job` around line 1052.)

- [ ] **Step 10: Add integration test — progress payload reflects file-level work**

Append to `the_door/tests/integration/test_progress_reporter_e2e.py` (created in task 1a):

```python
@pytest.mark.integration
def test_progress_payload_populated_during_analyze(tmp_path, monkeypatch):
    """Run analyze, fetch status mid-run, assert progress dict present with files_total."""
    # Same monkeypatch setup as test_analyze_job_emits_six_step_structure
    ...
    handler, store = _setup(tmp_path, monkeypatch)
    code, body = handler.handle_post_analyze({})
    job_id = body["job_id"]
    # Wait for first progress update
    import time
    for _ in range(50):
        _, status = handler.handle_get_update_status(job_id)
        if status.get("progress") is not None:
            break
        time.sleep(0.05)
    assert status["progress"] is not None
    assert status["progress"]["files_total"] >= 1
    assert status["progress"]["current_root"] == "new"
    assert "files_done" in status["progress"]
    assert "current_file" in status["progress"]
```

(Helper `_setup` factors out the monkeypatch + handler creation from the existing integration test.)

- [ ] **Step 11: Run all task 1b tests + coverage**

```bash
pytest the_door/tests/unit/core/ui/test_job_store.py \
       the_door/tests/unit/core/ui/test_handle_get_update_status_progress.py \
       the_door/tests/integration/test_progress_reporter_e2e.py -v \
       --cov=the_door.core.ui.job_store \
       --cov=the_door.core.ui.api_handlers \
       --cov-report=term-missing
```
Expected: all pass; coverage 100% on `job_store.py`; new lines in `api_handlers.py` covered.

- [ ] **Step 12: Run full suite — no regressions**

```bash
pytest the_door/tests/ -x --tb=short
```

- [ ] **Step 13: Commit**

```bash
git add the_door/src/the_door/core/ui/job_store.py \
        the_door/src/the_door/core/ui/api_handlers.py \
        the_door/tests/unit/core/ui/test_job_store.py \
        the_door/tests/unit/core/ui/test_handle_get_update_status_progress.py \
        the_door/tests/integration/test_progress_reporter_e2e.py
git commit -m "feat(job_store): UpdateJob.progress field + payload surface

handle_get_update_status payload 加 progress dict（files_done/files_total/
current_file/current_root），由 ProgressReporter sink 寫入。spec §5.1。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
