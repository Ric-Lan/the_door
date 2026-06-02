# `pipeline_orchestrator.run()` 長函式拉直 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在行為完全不變前提下，把 `PipelineOrchestrator.run()`（~217 行、6 次重複中斷守衛）拉直成一條乾淨的線性序列。

**Architecture:** 兩階段。Phase A 先補刻畫測試（characterization net）釘住 `run()` 全部 9 條離場路徑（對未重構的現行碼就綠）；Phase B 才動：把累積狀態 locals 提頂初始化、各步成功才賦值，將 8 個提早離場收斂成單一 `_partial` 閉包，並輕量統一步驟膠水。

**Tech Stack:** Python 3.12、pytest、unittest.mock。設計依據：`docs/superpowers/specs/2026-06-02-pipeline-orchestrator-run-straighten-design.md`。

---

## 關鍵事實（執行前必讀，省去翻 spec）

**目標檔**：`the_door/src/the_door/core/pipeline/pipeline_orchestrator.py`，方法 `PipelineOrchestrator.run()`（`def` 約在 102 行）。

**測試 cwd**：所有 pytest / git 指令在**內層** `the_door/` 目錄執行（`testpaths=["tests"]`）。Windows console 是 cp950，跑測試前置 `PYTHONUTF8=1` 避免 emoji/CJK 編碼錯誤。

**`run()` 的 9 個離場點**（Phase A 要全釘、Phase B 不可違反）：
- 6 個 `if interrupted:` 中斷守衛（step 1–6 前）→ `_build_result(..., interrupted=True)`
- 2 個 `if step.status == "failed":` analyze 終止（analyze_old / analyze_new）→ `_build_result(..., interrupted=<當下值>)`
- 1 個正常完成 → `_build_result(..., interrupted=<當下值>)` + `_report_summary`

**已驗證的參數對照（無邏輯 bug 的依據）**：因 `_run_analyze_step` 失敗回 `(step, None)`，每個離場點的 `old_snapshot` 都恆等於 `old_analyze_result.snapshot if old_analyze_result else None`（`new_snapshot` 同理）。⇒ 提頂 locals、**成功才賦 `*_snapshot`**，即可逐點重現。

**護欄（越線即否決）**：
- 行為零變更，9 條路徑欄位逐一等價，測試零回歸、覆蓋不降。
- **不改 `_build_result` 簽名**（snapshot 參數技術上冗餘，但收斂它不增可讀性、徒增改動面 → 砍）。
- **不碰 `_try_cached_analyze`**、不改任何 `_run_*_step` 內部邏輯。
- **不做 step 分發表 / 通用 step 迴圈**（過度抽象）。各步 `_run_X_step(...)` 呼叫保持顯式具名。
- **step 6（report）是內聯 marker**（非 `_run_*_step`），不得硬套進統一形狀。
- `_report_summary`（312 行）**只在正常完成**呼叫，8 條早退不發 summary — 保留此不對稱。
- 完整保留 `try/finally`（SIGINT handler 還原）與 `on_main_thread` 判斷。

**確定性中斷注入機制**（Phase A 測試核心，解掉 spec §7 最大風險）：
`run()` 在 main thread 安裝 `_sigint_handler` 設 `interrupted=True`。測試在 mock 的某一步內**直接呼叫已安裝的 handler**，同步翻旗、不依賴非同步 signal 遞送：
```python
def _trigger_interrupt() -> None:
    handler = signal.getsignal(signal.SIGINT)
    handler(signal.SIGINT, None)
```

---

## 任務順序（嚴格依序，後者依賴前者的程式碼狀態）

1. **task-01** — 補網：6 條中斷路徑刻畫測試（建立測試檔 + 共用 helper）。
2. **task-02** — 補網：2 條 analyze 失敗 + 正常完成 + summary 不對稱 + validate 離場。
3. **task-03** — 拉直 `run()`（hoist locals + 收斂 8 守衛成 `_partial` + 輕量膠水）。
4. **task-04** — 驗收與收尾（斷言守衛已收斂、簽名未變、`_try_cached_analyze` 未動、全套件 + 覆蓋、更新 backlog 進度）。

Phase A（task 01–02）的測試**必須對「未重構的現行 `run()`」就通過** — 它們捕捉的是現狀。Phase B（task 03）改完後，這些測試必須**仍全綠**。
