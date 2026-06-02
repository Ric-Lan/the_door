# Task 03: 拉直 `run()`（hoist locals + 收斂守衛 + 輕量膠水）

**目的**：在 Phase A 安全網保護下，把 `run()` 拉直。三件事一次到位（皆行為等價）：
1. 累積狀態 locals 提頂初始化為 `None`，各步**成功才賦 `*_snapshot`**；
2. 8 個提早離場（6 中斷 + 2 analyze 失敗）收斂成單一 `_partial` 閉包；
3. 重複的「正在執行」announce 抽成 `_running` 閉包。

**Files:**
- Modify: `the_door/src/the_door/core/pipeline/pipeline_orchestrator.py`（整個 `run()` 方法，現約 102–319 行）

**前置**：Task 01–02 的 11 條刻畫測試已 commit 並全綠。

**關鍵等價性（務必理解再動）**：因 `_run_analyze_step` 失敗回 `(step, None)`，把 `old_snapshot = old_analyze_result.snapshot` 移到「analyze_old 失敗檢查**通過後**」賦值，可讓失敗時 `old_snapshot` 維持 `None`、成功後等於 `result.snapshot` —— 與現行每個離場點傳的值逐點一致。`new_snapshot` 同理。`_partial` 閉包讀「當下 locals」，於各守衛點自動得到正確子集。

**護欄複述**：不改 `_build_result` 簽名；不碰 `_try_cached_analyze` 與各 `_run_*_step` 內部；step 6 維持內聯 marker；`_report_summary` 只在正常完成呼叫；保留 `try/finally` 與 `on_main_thread`；不做 step 分發迴圈。

---

- [ ] **Step 1: 整個替換 `run()` 方法**

用下面這版**完整**取代現行 `run()`（從 `def run(` 到其 `finally` 區塊結束）。其餘方法（`_run_analyze_step` 等）一律不動。

```python
    def run(
        self,
        config: PipelineConfig,
        *,
        progress_callback: Callable[[str], None] | None = None,
        reporter: ProgressReporter | None = None,
    ) -> PipelineResult:
        """Execute the full version update pipeline.

        Parameters
        ----------
        config : PipelineConfig
            Complete pipeline configuration.
        progress_callback : Callable[[str], None] | None
            Progress reporter. Messages go to stderr in CLI mode.

        Returns
        -------
        PipelineResult
            Complete pipeline result with all step states.

        Raises
        ------
        PipelineError
            Path validation failures (non-existent, not directory, same path).
        """
        progress = progress_callback or _noop_progress
        rep = reporter or NoOpProgressReporter()

        # ── Path validation ──────────────────────────────────────────
        self._validate_paths(config)

        # ── SIGINT handling ──────────────────────────────────────────
        interrupted = False
        original_handler = signal.getsignal(signal.SIGINT)

        def _sigint_handler(signum, frame):  # noqa: ARG001
            nonlocal interrupted
            interrupted = True

        # Only install signal handler on main thread
        on_main_thread = threading.current_thread() is threading.main_thread()
        if on_main_thread:
            signal.signal(signal.SIGINT, _sigint_handler)

        # ── Estimate total time ──────────────────────────────────────
        old_file_count = _count_files(config.old_path)
        new_file_count = _count_files(config.new_path)
        progress(
            f"預估分析時間：約 2–5 分鐘"
            f"（舊版 {old_file_count} 個檔案 + 新版 {new_file_count} 個檔案）"
        )

        # ── Pipeline state (accumulated as steps complete) ───────────
        pipeline_start = time.monotonic()
        steps: list[PipelineStep] = []
        old_analyze_result: AnalyzeResult | None = None
        new_analyze_result: AnalyzeResult | None = None
        old_snapshot: VersionSnapshot | None = None
        new_snapshot: VersionSnapshot | None = None
        diff_result: DiffResult | None = None
        scope_result: ScopeResult | None = None
        timeline_result: TimelineResult | None = None

        def _running(step_num: int, name: str) -> None:
            progress(f"[步驟 {step_num}/{_TOTAL_STEPS}] 正在執行：{name}...")

        def _partial(was_interrupted: bool) -> PipelineResult:
            """Skip all remaining steps and build the partial result from the
            live accumulator locals. The only per-site variation is the
            interrupted flag (True for SIGINT guards, current value for an
            analyze failure)."""
            steps.extend(self._skip_remaining(_STEP_DEFS, len(steps)))
            return self._build_result(
                config, steps, old_snapshot, new_snapshot,
                diff_result, scope_result, timeline_result,
                old_analyze_result, new_analyze_result,
                pipeline_start, was_interrupted,
            )

        try:
            # ── Step 1: analyze_old ──────────────────────────────────
            if interrupted:
                return _partial(True)
            _running(1, "analyze_old")
            step, old_analyze_result = self._run_analyze_step(
                config.old_path, "analyze_old", config, reporter=rep,
            )
            steps.append(step)
            self._report_step_done(progress, 1, step)
            if step.status == "failed":
                return _partial(interrupted)
            old_snapshot = old_analyze_result.snapshot

            # ── Step 2: analyze_new ──────────────────────────────────
            if interrupted:
                return _partial(True)
            _running(2, "analyze_new")
            step, new_analyze_result = self._run_analyze_step(
                config.new_path, "analyze_new", config, reporter=rep,
            )
            steps.append(step)
            self._report_step_done(progress, 2, step)
            if step.status == "failed":
                return _partial(interrupted)
            new_snapshot = new_analyze_result.snapshot

            # ── Step 3: diff ─────────────────────────────────────────
            if interrupted:
                return _partial(True)
            _running(3, "diff")
            step, diff_result = self._run_diff_step(old_snapshot, new_snapshot)
            steps.append(step)
            self._report_step_done(progress, 3, step)

            # ── Step 4: scope_verify (optional) ──────────────────────
            if interrupted:
                return _partial(True)
            if config.scope_name is None:
                steps.append(PipelineStep(step_name="scope_verify", status="skipped"))
                progress(f"[步驟 4/{_TOTAL_STEPS}] ⊘ scope_verify（已跳過：未指定 scope）")
            else:
                _running(4, "scope_verify")
                step, scope_result = self._run_scope_step(
                    config.scope_name, config.new_path, new_analyze_result.l1_output,
                )
                steps.append(step)
                self._report_step_done(progress, 4, step)

            # ── Step 5: timeline (optional) ──────────────────────────
            if interrupted:
                return _partial(True)
            if config.skip_timeline:
                steps.append(PipelineStep(step_name="timeline", status="skipped"))
                progress(f"[步驟 5/{_TOTAL_STEPS}] ⊘ timeline（已跳過）")
            else:
                _running(5, "timeline")
                step, timeline_result = self._run_timeline_step(config.new_path)
                steps.append(step)
                self._report_step_done(progress, 5, step)

            # ── Step 6: report (placeholder — actual rendering is external) ──
            if interrupted:
                return _partial(True)
            report_start = time.monotonic()
            report_started_at = _now_iso()
            # Report step is a marker — actual rendering happens in CLI/MCP layer
            steps.append(PipelineStep(
                step_name="report",
                status="completed",
                started_at=report_started_at,
                completed_at=_now_iso(),
                duration_ms=_elapsed_ms(report_start),
            ))
            progress(f"[步驟 6/{_TOTAL_STEPS}] ✓ report（耗時 0.0s）")

            result = self._build_result(
                config, steps, old_snapshot, new_snapshot,
                diff_result, scope_result, timeline_result,
                old_analyze_result, new_analyze_result,
                pipeline_start, interrupted,
            )

            # ── Summary ──────────────────────────────────────────────
            self._report_summary(progress, result)
            return result

        finally:
            # Restore original signal handler
            if on_main_thread:
                signal.signal(signal.SIGINT, original_handler)
```

- [ ] **Step 2: 跑刻畫網，確認行為等價（必須仍全綠）**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/pipeline/test_pipeline_orchestrator_run_paths.py -v
```
Expected: **11 passed**（與 Task 02 後相同）。
若任何一條 FAIL → 拉直破壞了該離場路徑的行為，**回頭比對該路徑的 snapshot/result/steps 與 `_partial` 讀到的 locals**，修到綠。不可改測試來迎合。

- [ ] **Step 3: 跑既有 orchestrator 相關測試（確認沒踩到 reporter/cache 行為）**

Run：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/pipeline/ -v
```
Expected: 全 PASS（含既有 `test_pipeline_orchestrator_reporter.py`、`test_pipeline_orchestrator_cache.py` 等）。

- [ ] **Step 4: 跑全套件（零回歸）**

Run：
```
PYTHONUTF8=1 python -m pytest
```
Expected: 全 PASS（與重構前數量一致；無新 fail）。

- [ ] **Step 5: Commit**

```
git add the_door/src/the_door/core/pipeline/pipeline_orchestrator.py
git commit -m "refactor(pipeline): straighten run() - collapse interrupt guards into _partial"
```
