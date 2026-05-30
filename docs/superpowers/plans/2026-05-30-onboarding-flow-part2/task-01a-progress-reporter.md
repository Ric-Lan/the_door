# Task 1a — ProgressReporter abstraction + entry hooks + analyze adapter

**Goal:** Introduce `ProgressReporter` so `ASTExtractor`/`BatchReader` emit structured file-level progress; wrap `handle_post_analyze` callback so精靈 `run_analyze_pipeline` 訊息映射成 `[步驟 N/6]` 格式（與 modal `PipelineOrchestrator.run` 對齊）。

**Dependencies:** none (critical path root).

**Files:**
- Create: `the_door/src/the_door/core/pipeline/progress_reporter.py`
- Create: `the_door/tests/unit/core/pipeline/test_progress_reporter.py`
- Modify: `the_door/src/the_door/core/extraction/ast_extractor.py` (`extract` 簽名加 `reporter=None`)
- Modify: `the_door/src/the_door/core/reading/batch_reader.py` (`BatchReader.run` 簽名加 `reporter=None`)
- Modify: `the_door/src/the_door/core/pipeline/analyze_pipeline.py` (`run_analyze_pipeline` 簽名加 `reporter=None`，傳給 ASTExtractor/BatchReader)
- Modify: `the_door/src/the_door/core/pipeline/pipeline_orchestrator.py` (`PipelineOrchestrator.run` 接 reporter，傳給內部 `_run_analyze_step`)
- Modify: `the_door/src/the_door/core/ui/api_handlers.py:272-294` (`_run_analyze_job` 套 adapter + 建立 reporter)
- Modify: `the_door/src/the_door/core/ui/api_handlers.py` modal handler (`_run_update_job` 約 line 1052) 也建立 reporter
- Create: `the_door/tests/unit/core/ui/test_handle_post_analyze_adapter.py`
- Create: `the_door/tests/integration/test_progress_reporter_e2e.py`

---

- [ ] **Step 1: Create test file for ProgressReporter abstraction**

Path: `the_door/tests/unit/core/pipeline/test_progress_reporter.py`

```python
"""Tests for ProgressReporter abstraction (file-level progress channel)."""
from __future__ import annotations

import pytest

from the_door.core.pipeline.progress_reporter import (
    ProgressReporter,
    NoOpProgressReporter,
)


def test_reporter_default_state_is_none():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    assert captured == []  # no auto-emit on construction


def test_report_file_emits_full_payload():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    r.set_total(247, root="new")
    r.report_file("src/foo.py")
    assert captured[-1] == {
        "files_done": 1, "files_total": 247,
        "current_file": "src/foo.py", "current_root": "new",
    }


def test_report_file_increments_done():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    r.set_total(10, root="new")
    r.report_file("a.py")
    r.report_file("b.py")
    assert [d["files_done"] for d in captured] == [1, 2]


def test_report_file_without_set_total_uses_zero_total():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    r.report_file("a.py")
    assert captured[-1]["files_total"] == 0
    assert captured[-1]["files_done"] == 1


def test_switch_root_resets_done():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    r.set_total(10, root="old")
    r.report_file("a.py")
    r.set_total(20, root="new")
    r.report_file("b.py")
    assert captured[-1] == {
        "files_done": 1, "files_total": 20,
        "current_file": "b.py", "current_root": "new",
    }


def test_noop_reporter_swallows_calls():
    r = NoOpProgressReporter()
    r.set_total(10, root="new")
    r.report_file("a.py")  # must not raise


def test_done_never_exceeds_total():
    captured = []
    r = ProgressReporter(sink=lambda d: captured.append(dict(d)))
    r.set_total(2, root="new")
    r.report_file("a.py")
    r.report_file("b.py")
    r.report_file("c.py")  # overflow
    assert captured[-1]["files_done"] == 2
    assert captured[-1]["files_total"] == 2


def test_current_root_invalid_raises():
    r = ProgressReporter(sink=lambda d: None)
    with pytest.raises(ValueError, match="root must be 'new' or 'old'"):
        r.set_total(10, root="bogus")
```

- [ ] **Step 2: Run test, verify all FAIL**

```bash
pytest the_door/tests/unit/core/pipeline/test_progress_reporter.py -v
```
Expected: ModuleNotFoundError on import.

- [ ] **Step 3: Implement `progress_reporter.py`**

Path: `the_door/src/the_door/core/pipeline/progress_reporter.py`

```python
"""ProgressReporter — file-level progress channel for analyze/update pipelines.

Decoupled from job_store / api_handlers: callers inject any `sink` callable
that consumes a progress dict. Production wiring routes sink to
`UpdateJob.update_progress`. Tests use list-append sinks.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Literal

ProgressDict = dict
Sink = Callable[[ProgressDict], None]


class ProgressReporter:
    """Tracks file-level analysis progress and pushes dicts to a sink."""

    def __init__(self, sink: Sink) -> None:
        self._sink = sink
        self._files_done = 0
        self._files_total = 0
        self._root: Literal["new", "old"] = "new"

    def set_total(self, total: int, *, root: Literal["new", "old"]) -> None:
        if root not in ("new", "old"):
            raise ValueError("root must be 'new' or 'old'")
        self._files_total = total
        self._files_done = 0
        self._root = root

    def report_file(self, path: str) -> None:
        if self._files_total > 0:
            self._files_done = min(self._files_done + 1, self._files_total)
        else:
            self._files_done += 1
        self._sink({
            "files_done": self._files_done,
            "files_total": self._files_total,
            "current_file": path,
            "current_root": self._root,
        })


class NoOpProgressReporter(ProgressReporter):
    """Default reporter when caller does not wire one (CLI / MCP path)."""

    def __init__(self) -> None:
        super().__init__(sink=lambda _d: None)
```

- [ ] **Step 4: Run test, verify all PASS + 100% coverage on the new module**

```bash
pytest the_door/tests/unit/core/pipeline/test_progress_reporter.py -v \
  --cov=the_door.core.pipeline.progress_reporter --cov-report=term-missing
```
Expected: 8 passed, coverage 100%.

- [ ] **Step 5: Hook ProgressReporter into ASTExtractor**

Modify `the_door/src/the_door/core/extraction/ast_extractor.py`:

In `ASTExtractor.extract(self, codebase_path: str, extra_ignore=None)` — add optional kwarg `reporter: ProgressReporter | None = None`. Inside file loop, before processing each file call `if reporter: reporter.report_file(relative_path)`.

If a `set_total` call is needed (caller knows total file count), do it in `run_analyze_pipeline` (Step 8), not inside extractor.

Locate file loop: `grep -n "for .* in .*files" the_door/src/the_door/core/extraction/ast_extractor.py` — patch the discovered loop body.

Add test `test_extract_calls_reporter_per_file` in existing `test_ast_extractor.py` (find via `find the_door/tests -name 'test_ast_extractor*'`; if absent, create `the_door/tests/unit/core/extraction/test_ast_extractor_reporter.py`):

```python
from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.pipeline.progress_reporter import ProgressReporter


def test_extract_calls_reporter_per_file(tmp_path):
    (tmp_path / "a.py").write_text("def f(): pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def g(): pass\n", encoding="utf-8")
    captured = []
    reporter = ProgressReporter(sink=lambda d: captured.append(d["current_file"]))
    reporter.set_total(2, root="new")
    ASTExtractor().extract(str(tmp_path), reporter=reporter)
    assert sorted(c.replace("\\", "/").split("/")[-1] for c in captured) == ["a.py", "b.py"]
```

- [ ] **Step 6: Run extractor test, verify PASS**

```bash
pytest the_door/tests/unit/core/extraction/test_ast_extractor_reporter.py -v
```

- [ ] **Step 7: Hook ProgressReporter into BatchReader**

Modify `the_door/src/the_door/core/reading/batch_reader.py`:

`BatchReader.run(...)` (or the file-iteration method) — accept `reporter: ProgressReporter | None = None`; call `reporter.report_file(file_path)` inside the per-file loop.

Locate file loop via `grep -n "for .* in .*\.files\|for path in" the_door/src/the_door/core/reading/batch_reader.py`.

Add test `the_door/tests/unit/core/reading/test_batch_reader_reporter.py`:

```python
from unittest.mock import MagicMock

from the_door.core.pipeline.progress_reporter import ProgressReporter


def test_batch_reader_calls_reporter_per_file(monkeypatch, tmp_path):
    # Minimal smoke: instantiate BatchReader, inject reporter, verify report_file called.
    # Skip if BatchReader needs heavy fixtures; assert reporter signature accepted.
    from the_door.core.reading.batch_reader import BatchReader
    sig = BatchReader.run.__code__.co_varnames
    assert "reporter" in sig, "BatchReader.run must accept reporter kwarg"
```

(Full integration covered by `test_progress_reporter_e2e.py` in Step 12.)

- [ ] **Step 8: Wire ProgressReporter into `run_analyze_pipeline`**

Modify `the_door/src/the_door/core/pipeline/analyze_pipeline.py`:

```python
# Add to imports
from the_door.core.pipeline.progress_reporter import ProgressReporter, NoOpProgressReporter

# Modify signature (around line 46):
def run_analyze_pipeline(
    codebase_path: Path,
    config: AnalyzeConfig,
    *,
    progress_callback: Callable[[str], None] | None = None,
    reporter: ProgressReporter | None = None,
) -> AnalyzeResult:
    ...
    rep = reporter or NoOpProgressReporter()
    return _run_pipeline_inner(codebase_path, config, progress, rep)

# Modify _run_pipeline_inner signature + body:
def _run_pipeline_inner(
    codebase_path: Path,
    config: AnalyzeConfig,
    progress: Callable[[str], None],
    reporter: ProgressReporter,
) -> AnalyzeResult:
    ...
    # Before ASTExtractor.extract call, count files for set_total
    from the_door.core.extraction.file_discovery import FileDiscovery
    file_count = FileDiscovery().count(str(codebase_path), config.extra_ignore)
    reporter.set_total(file_count, root="new")
    ...
    # Pass reporter through:
    ast_future = executor.submit(extractor.extract, str(codebase_path), config.extra_ignore, reporter=reporter)
    ...
    # Pass reporter into BatchReader:
    reader = BatchReader(..., reporter=reporter)
```

If `FileDiscovery` lacks a `count()`, add it as a 3-line method or call existing discovery + `len()`.

- [ ] **Step 9: Wire ProgressReporter into `PipelineOrchestrator.run`**

Modify `the_door/src/the_door/core/pipeline/pipeline_orchestrator.py`:

```python
# Add to imports
from the_door.core.pipeline.progress_reporter import ProgressReporter, NoOpProgressReporter

# Modify run() signature:
def run(
    self,
    config: PipelineConfig,
    *,
    progress_callback: Callable[[str], None] | None = None,
    reporter: ProgressReporter | None = None,
) -> PipelineResult:
    ...
    rep = reporter or NoOpProgressReporter()
    # Pass to _run_analyze_step for analyze_old:
    step, old_analyze_result = self._run_analyze_step(
        config.old_path, "analyze_old", config, reporter=rep,
    )
    # Pass to _run_analyze_step for analyze_new:
    step, new_analyze_result = self._run_analyze_step(
        config.new_path, "analyze_new", config, reporter=rep,
    )
```

Modify `_run_analyze_step` to accept and forward `reporter` into the internal `run_analyze_pipeline` call. Before calling, switch root: `reporter.set_total(<count>, root="old" if step_name == "analyze_old" else "new")` (set inside `_run_analyze_step` based on `step_name`).

- [ ] **Step 10: Add test for analyze adapter (handle_post_analyze)**

Path: `the_door/tests/unit/core/ui/test_handle_post_analyze_adapter.py`

```python
"""Test handle_post_analyze adapter wraps run_analyze_pipeline progress.

Adapter must:
1. Emit 3 skipped steps (1/3/4) on first transferred message.
2. Map "Extracting structure from ..." → "[步驟 2/6] 正在執行：analyze_new..."
3. Swallow "Provider:", "Structure JSON persisted to ...", "Running batch analysis..."
4. On "Snapshot saved: <sha>" emit 3 messages: step 2 ✓, step 5 ✓, step 6 ✓.
"""
from __future__ import annotations

import pytest

from the_door.core.ui.job_store import UpdateJob


def _adapter_for(job):
    """Reach into api_handlers to build adapter; expose helper."""
    from the_door.core.ui.api_handlers import _make_analyze_progress_adapter
    return _make_analyze_progress_adapter(job)


def test_adapter_emits_skipped_steps_on_first_call():
    job = UpdateJob(job_id="t")
    adapter = _adapter_for(job)
    adapter("Provider: anthropic")
    names_status = [(s["step_name"], s["status"]) for s in job.steps]
    assert ("analyze_old", "skipped") in names_status
    assert ("diff", "skipped") in names_status
    assert ("scope_verify", "skipped") in names_status


def test_adapter_skipped_steps_only_emitted_once():
    job = UpdateJob(job_id="t")
    adapter = _adapter_for(job)
    adapter("Provider: anthropic")
    n1 = len(job.steps)
    adapter("Provider: anthropic")
    assert len(job.steps) == n1


def test_adapter_maps_extracting_to_running_step2():
    job = UpdateJob(job_id="t")
    adapter = _adapter_for(job)
    adapter("Provider: x")
    adapter("Extracting structure from /foo...")
    assert job.current_step == "analyze_new"


def test_adapter_swallows_intermediate_messages():
    job = UpdateJob(job_id="t")
    adapter = _adapter_for(job)
    adapter("Provider: x")
    adapter("Extracting structure from /foo...")
    before_steps = list(job.steps)
    adapter("Structure JSON persisted to /tmp/x.json")
    adapter("Running batch analysis...")
    assert job.steps == before_steps  # nothing added
    assert job.current_step == "analyze_new"  # still running


def test_adapter_snapshot_saved_emits_three_completed():
    job = UpdateJob(job_id="t")
    adapter = _adapter_for(job)
    adapter("Provider: x")
    adapter("Extracting structure from /foo...")
    adapter("Snapshot saved: abc12345")
    completed = [s["step_name"] for s in job.steps if s.get("status") == "completed"]
    assert "analyze_new" in completed
    assert "timeline" in completed
    assert "report" in completed
```

- [ ] **Step 11: Implement adapter in api_handlers.py**

Modify `the_door/src/the_door/core/ui/api_handlers.py`:

Add module-level helper above the `Handler` class:

```python
def _make_analyze_progress_adapter(job):
    """Per-request closure that wraps run_analyze_pipeline messages into
    PipelineOrchestrator-compatible [步驟 N/6] format. See spec §5.1."""
    sent_skipped = False
    extracting_started = False
    def adapter(msg: str) -> None:
        nonlocal sent_skipped, extracting_started
        if not sent_skipped:
            job.update_step("[步驟 1/6] ⊘ analyze_old（已跳過：首次分析無舊版）")
            job.update_step("[步驟 3/6] ⊘ diff（已跳過：首次分析無舊版）")
            job.update_step("[步驟 4/6] ⊘ scope_verify（已跳過：首次分析無 scope）")
            sent_skipped = True
        if msg.startswith("Extracting structure from"):
            job.update_step("[步驟 2/6] 正在執行：analyze_new...")
            extracting_started = True
            return
        if msg.startswith("Snapshot saved:"):
            job.update_step("[步驟 2/6] ✓ analyze_new（耗時 0.0s）")
            job.update_step("[步驟 5/6] ✓ timeline（耗時 0.0s）")
            job.update_step("[步驟 6/6] ✓ report（耗時 0.0s）")
            return
        # Provider:, Structure JSON persisted to ..., Running batch analysis ...
        # → swallowed (step 2 stays running, file-level progress via reporter)
    return adapter
```

Modify `_run_analyze_job` (around line 272-294) to use adapter + reporter:

```python
def _run_analyze_job(self, job, extra_ignore, snapshot_label) -> None:
    from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline
    from the_door.core.pipeline.progress_reporter import ProgressReporter
    from the_door.models import AnalyzeConfig
    config = AnalyzeConfig(
        skip_cost_confirm=True,
        extra_ignore=extra_ignore,
        snapshot_label=snapshot_label,
    )
    adapter = _make_analyze_progress_adapter(job)
    reporter = ProgressReporter(sink=job.update_progress)  # update_progress arrives in task 1b
    try:
        run_analyze_pipeline(
            self._project_root, config,
            progress_callback=adapter,
            reporter=reporter,
        )
        self._job_store.complete_job(job.job_id)
    except Exception as exc:
        self._job_store.fail_job(job.job_id, str(exc))
```

Same pattern in modal `_run_update_job` (around line 1052) — reporter only (no adapter; PipelineOrchestrator already emits `[步驟 N/6]`):

```python
reporter = ProgressReporter(sink=job.update_progress)
result = PipelineOrchestrator().run(config, progress_callback=job.update_step, reporter=reporter)
```

> Note: `job.update_progress` is added in task 1b. Until task 1b lands, replace `sink=job.update_progress` with `sink=lambda _d: None` and add a TODO comment; task 1b will swap it.

- [ ] **Step 12: Run adapter test + integration**

```bash
pytest the_door/tests/unit/core/ui/test_handle_post_analyze_adapter.py -v
```
Expected: 5 passed.

- [ ] **Step 13: Integration test — analyze e2e produces expected step sequence**

Path: `the_door/tests/integration/test_progress_reporter_e2e.py`

```python
"""E2E: run_analyze_pipeline through handle_post_analyze produces:
- 3 skipped steps (analyze_old/diff/scope_verify)
- step 2 (analyze_new) running → completed
- step 5 (timeline) + step 6 (report) completed
"""
from __future__ import annotations

import time

import pytest


@pytest.mark.integration
def test_analyze_job_emits_six_step_structure(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("def f(): pass\n", encoding="utf-8")

    from the_door.core.ui.api_handlers import Handler
    from the_door.core.ui.job_store import JobStore
    # Stub LLM provider creation to avoid network
    monkeypatch.setattr(
        "the_door.core.pipeline.analyze_pipeline.create_provider",
        lambda cfg: _stub_provider(),
    )
    # Stub batch reader to instantly return empty result
    # (or use existing fixture if one exists)
    ...

    job_store = JobStore()
    handler = Handler(project_root=tmp_path, job_store=job_store)
    code, body = handler.handle_post_analyze({})
    assert code == 202
    job_id = body["job_id"]

    # Poll until job completes (test timeout 10s)
    for _ in range(100):
        job = job_store.get_job(job_id)
        if job.status in ("completed", "failed"):
            break
        time.sleep(0.1)

    step_names = [(s["step_name"], s["status"]) for s in job.steps]
    assert ("analyze_old", "skipped") in step_names
    assert ("diff", "skipped") in step_names
    assert ("scope_verify", "skipped") in step_names
    assert ("analyze_new", "completed") in step_names
    assert ("timeline", "completed") in step_names
    assert ("report", "completed") in step_names


def _stub_provider():
    class _P:
        async def analyze(self, *_, **__): return {"l1": []}
    return _P()
```

If existing integration tests already monkeypatch provider/batch (search `find the_door/tests/integration -name '*analyze*'`), copy their fixture pattern instead.

- [ ] **Step 14: Run all task 1a tests + coverage check**

```bash
pytest the_door/tests/unit/core/pipeline/test_progress_reporter.py \
       the_door/tests/unit/core/extraction/test_ast_extractor_reporter.py \
       the_door/tests/unit/core/reading/test_batch_reader_reporter.py \
       the_door/tests/unit/core/ui/test_handle_post_analyze_adapter.py \
       the_door/tests/integration/test_progress_reporter_e2e.py -v \
       --cov=the_door.core.pipeline.progress_reporter \
       --cov=the_door.core.ui.api_handlers \
       --cov-report=term-missing
```
Expected: all pass; coverage 100% on `progress_reporter.py` and 100% on new `_make_analyze_progress_adapter`.

If any uncovered line in adapter or reporter, add a targeted test before commit.

- [ ] **Step 15: Run full Python test suite — no regressions**

```bash
pytest the_door/tests/ -x --tb=short
```
Expected: 1289 + new tests passing, 0 regressions.

- [ ] **Step 16: Commit**

```bash
git add the_door/src/the_door/core/pipeline/progress_reporter.py \
        the_door/src/the_door/core/pipeline/analyze_pipeline.py \
        the_door/src/the_door/core/pipeline/pipeline_orchestrator.py \
        the_door/src/the_door/core/extraction/ast_extractor.py \
        the_door/src/the_door/core/reading/batch_reader.py \
        the_door/src/the_door/core/ui/api_handlers.py \
        the_door/tests/unit/core/pipeline/test_progress_reporter.py \
        the_door/tests/unit/core/extraction/test_ast_extractor_reporter.py \
        the_door/tests/unit/core/reading/test_batch_reader_reporter.py \
        the_door/tests/unit/core/ui/test_handle_post_analyze_adapter.py \
        the_door/tests/integration/test_progress_reporter_e2e.py
git commit -m "feat(progress): ProgressReporter + analyze adapter for 6-step alignment

精靈 run_analyze_pipeline 經 _make_analyze_progress_adapter 映射成
[步驟 N/6] 訊息與 modal PipelineOrchestrator.run 對齊。新增 ProgressReporter
抽象貫穿 ASTExtractor / BatchReader file loop。spec §5.1。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
