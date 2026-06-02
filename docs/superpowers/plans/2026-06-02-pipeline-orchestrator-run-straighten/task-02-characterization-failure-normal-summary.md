# Task 02: Characterization net — failure / normal / summary / validate

**目的**：補齊剩餘離場路徑的刻畫測試：2 條 analyze 失敗終止、正常完成、`_report_summary` 只在正常完成發（不對稱）、`_validate_paths` 拋 `PipelineError`（第 10 條離場）。同樣對現行碼就綠。

**Files:**
- Modify: `the_door/tests/unit/core/pipeline/test_pipeline_orchestrator_run_paths.py`（append 到 Task 01 建立的同一檔）

**前置**：Task 01 已在此檔加入這些 module-level helper，本任務直接沿用，不需重定義：
`_fake_analyze_result()`、`_completed(name)`、`_failed(name)`、`_make_config(tmp_path, *, scope_name, skip_timeline)`、`_trigger_interrupt()`。本任務新增的測試另需 `from the_door.models import PipelineError`（在檔案 import 區補上）。

---

- [ ] **Step 1: 在 import 區補 `PipelineError`**

把檔案頂部：
```python
from the_door.models import AnalyzeConfig, PipelineConfig, PipelineStep
```
改為：
```python
from the_door.models import AnalyzeConfig, PipelineConfig, PipelineError, PipelineStep
```

- [ ] **Step 2: Append 失敗 / 正常 / summary / validate 測試**

把以下測試**附加到該檔末尾**：

```python
# ── analyze failure terminates ───────────────────────────────────────────

def test_analyze_old_failure_terminates(tmp_path):
    """analyze_old 失敗 → 終止；其餘步驟 skipped；snapshot 全 None；
    analyze_new 不被呼叫（side_effect 只給一個元素，被呼叫第二次會 StopIteration）。"""
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path)

    with patch(
        "the_door.core.pipeline.pipeline_orchestrator._count_files",
        return_value=0,
    ), patch.object(
        orch, "_run_analyze_step",
        side_effect=[(_failed("analyze_old"), None)],
    ):
        result = orch.run(config)

    assert result.interrupted is False
    assert result.old_snapshot is None
    assert result.new_snapshot is None
    assert result.diff_result is None
    assert result.steps[0].step_name == "analyze_old"
    assert result.steps[0].status == "failed"
    assert [s.status for s in result.steps[1:]] == ["skipped"] * 5
    assert len(result.steps) == 6


def test_analyze_new_failure_terminates(tmp_path):
    """analyze_old 成功、analyze_new 失敗 → 終止；old_snapshot 設、new None；
    其餘 skipped。"""
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path)
    fake_old = _fake_analyze_result()

    with patch(
        "the_door.core.pipeline.pipeline_orchestrator._count_files",
        return_value=0,
    ), patch.object(
        orch, "_run_analyze_step",
        side_effect=[
            (_completed("analyze_old"), fake_old),
            (_failed("analyze_new"), None),
        ],
    ):
        result = orch.run(config)

    assert result.interrupted is False
    assert result.old_snapshot is fake_old.snapshot
    assert result.new_snapshot is None
    assert result.diff_result is None
    assert result.steps[0].status == "completed"
    assert result.steps[1].step_name == "analyze_new"
    assert result.steps[1].status == "failed"
    assert [s.status for s in result.steps[2:]] == ["skipped"] * 4
    assert len(result.steps) == 6


# ── normal completion ────────────────────────────────────────────────────

def test_normal_completion_all_steps_present(tmp_path):
    """全步成功：6 步皆 completed、各 snapshot/result 齊全、interrupted=False。"""
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path, scope_name="dummy", skip_timeline=False)
    fake_old = _fake_analyze_result()
    fake_new = _fake_analyze_result()
    diff_obj = MagicMock(name="diff_result")
    scope_obj = MagicMock(name="scope_result")
    timeline_obj = MagicMock(name="timeline_result")

    with patch(
        "the_door.core.pipeline.pipeline_orchestrator._count_files",
        return_value=0,
    ), patch.object(
        orch, "_run_analyze_step",
        side_effect=[
            (_completed("analyze_old"), fake_old),
            (_completed("analyze_new"), fake_new),
        ],
    ), patch.object(
        orch, "_run_diff_step",
        return_value=(_completed("diff"), diff_obj),
    ), patch.object(
        orch, "_run_scope_step",
        return_value=(_completed("scope_verify"), scope_obj),
    ), patch.object(
        orch, "_run_timeline_step",
        return_value=(_completed("timeline"), timeline_obj),
    ):
        result = orch.run(config)

    assert result.interrupted is False
    assert result.old_snapshot is fake_old.snapshot
    assert result.new_snapshot is fake_new.snapshot
    assert result.diff_result is diff_obj
    assert result.scope_result is scope_obj
    assert result.timeline_result is timeline_obj
    assert [s.step_name for s in result.steps] == [
        "analyze_old", "analyze_new", "diff", "scope_verify", "timeline", "report",
    ]
    assert all(s.status == "completed" for s in result.steps)


# ── _report_summary asymmetry (observable behavior to preserve) ──────────

def test_report_summary_called_once_on_normal_completion(tmp_path):
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path, scope_name="dummy", skip_timeline=False)
    fake_old = _fake_analyze_result()
    fake_new = _fake_analyze_result()

    with patch.object(orch, "_report_summary") as spy, patch(
        "the_door.core.pipeline.pipeline_orchestrator._count_files",
        return_value=0,
    ), patch.object(
        orch, "_run_analyze_step",
        side_effect=[
            (_completed("analyze_old"), fake_old),
            (_completed("analyze_new"), fake_new),
        ],
    ), patch.object(
        orch, "_run_diff_step",
        return_value=(_completed("diff"), MagicMock()),
    ), patch.object(
        orch, "_run_scope_step",
        return_value=(_completed("scope_verify"), MagicMock()),
    ), patch.object(
        orch, "_run_timeline_step",
        return_value=(_completed("timeline"), MagicMock()),
    ):
        orch.run(config)

    assert spy.call_count == 1


def test_report_summary_not_called_when_interrupted(tmp_path):
    """早退路徑不發 summary。"""
    orch = PipelineOrchestrator()
    config = _make_config(tmp_path)

    def count_files_se(path):
        _trigger_interrupt()  # interrupt before step 1
        return 0

    with patch.object(orch, "_report_summary") as spy, patch(
        "the_door.core.pipeline.pipeline_orchestrator._count_files",
        side_effect=count_files_se,
    ):
        result = orch.run(config)

    assert result.interrupted is True
    assert spy.call_count == 0


# ── _validate_paths raises (the 10th exit, before the try) ───────────────

def test_validate_paths_raises_pipeline_error_for_missing_old(tmp_path):
    orch = PipelineOrchestrator()
    missing = tmp_path / "does_not_exist"
    new_dir = tmp_path / "new"
    new_dir.mkdir()
    config = PipelineConfig(
        old_path=missing,
        new_path=new_dir,
        analyze_config=AnalyzeConfig(skip_cost_confirm=True),
    )
    with pytest.raises(PipelineError):
        orch.run(config)
```

- [ ] **Step 3: 跑全檔，確認對現行碼全綠**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/pipeline/test_pipeline_orchestrator_run_paths.py -v
```
Expected: **12 passed**（task-01 的 6 條中斷 + 本任務 6 條）。
若 FAIL，停下檢查對現行行為的假設，不要改 src。

- [ ] **Step 4: Commit**

```
git add tests/unit/core/pipeline/test_pipeline_orchestrator_run_paths.py
git commit -m "test(pipeline): characterize run() failure/normal/summary/validate paths"
```
