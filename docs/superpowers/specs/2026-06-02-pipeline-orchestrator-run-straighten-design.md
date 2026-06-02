# 第二刀 · `pipeline_orchestrator.run()` 長函式拉直 — 設計

> **日期**：2026-06-02　**狀態**：已實作（plan: docs/superpowers/plans/2026-06-02-pipeline-orchestrator-run-straighten/）
> **這刀做什麼（一句話）**：把 `PipelineOrchestrator.run()`（~220 行、6 次重複中斷守衛）
> 在**行為完全不變**前提下拉直成一條乾淨的線性序列（~80 行）。
> **這刀不做什麼**：不改 `_build_result` 簽名、不碰 `_try_cached_analyze`、不做 step 分發引擎。

本文件給 Claude Code 用：參數精準、自含。所有行號為 2026-06-02 當下 `the_door/src/the_door/core/pipeline/pipeline_orchestrator.py` 的錨點，實作時以符號定位為準（行號會漂移）。

---

## 1. 背景與動機

`run()` 是版本更新管線的指揮中心，順序跑 6 個步驟（analyze_old → analyze_new → diff → scope_verify → timeline → report），收集每步結果後打包成 `PipelineResult` 交給外層（CLI / MCP）渲染。

**問題（已驗證、非死碼、非過大檔的「冗餘」型異味）**：`run()` 約 220 行，其中**同一段「中斷 → 標記其餘步驟 skipped → 組半成品結果 → 回傳」的守衛重複了 6 次**，只在「已累積到第幾個結果」上不同。這是「簡潔不重複」軸的長函式異味，符合重構 backlog T4。

**北極星準則**：①可讀性優先 ②結構先行、行為不變 ③證據驅動 ④能簡潔就簡潔、抽象要償還成本。
**轉換**：第一刀是「搬之前釘住行為」；這刀是「**拉直之前釘住行為**」。

---

## 2. 證據（已驗證事實，無幻覺）

### 2.1 `run()` 的離場結構

`run()`（`def` 在 102 行，`finally` 收在 319 行）共有 **9 個 `_build_result(...)` 回傳點**：

| # | 觸發 | 位置錨點 | `interrupted` 傳值 |
|---|---|---|---|
| 1 | 中斷（step1 前） | 166 `if interrupted:` | `True`（字面） |
| 2 | analyze_old 失敗 | 182 `if step.status == "failed":` | `interrupted`（變數，通常 False） |
| 3 | 中斷（step2 前） | 192 | `True` |
| 4 | analyze_new 失敗 | 210 | `interrupted` |
| 5 | 中斷（step3 前） | 224 | `True` |
| 6 | 中斷（step4 前） | 240 | `True` |
| 7 | 中斷（step5 前） | 262 | `True` |
| 8 | 中斷（step6 前） | 282 | `True` |
| 9 | 正常完成 | 304 | `interrupted`（變數，可能 True——見 2.4） |

即 **6 個中斷守衛 + 2 個 analyze 失敗終止 + 1 個正常完成**。
診斷出的重複＝ #1/#3/#5/#6/#7/#8 這 6 個中斷守衛，加上 #2/#4 兩個失敗終止，結構同型（都先 `_skip_remaining` 再 `_build_result`）。

### 2.2 失敗契約（整張對照表的前提）

`_run_analyze_step`（323 行）在 `except` 分支（**393 行**）回傳 `(failed_step, None)`：
**analyze 失敗 ⇒ `analyze_result` 為 `None`**。

### 2.3 參數對照：`old_snapshot` / `new_snapshot` 恆可從 `analyze_result` 導出

逐一比對 9 個呼叫點傳入的 `old_snapshot`：

| 呼叫點 | 傳的 `old_snapshot` | 此刻 `old_analyze_result` | 等價於 `result.snapshot if result else None`？ |
|---|---|---|---|
| #1, #2 | 字面 `None` | `None`（#2 因失敗回傳 None） | ✅（result 為 None → 導出即 None） |
| #3, #4 | `old_analyze_result.snapshot if old_analyze_result else None` | 已設 | ✅（字面同式） |
| #5–#9 | local `old_snapshot`（220 行 `= old_analyze_result.snapshot`） | 已設、非 None | ✅ |

**結論（無邏輯 bug）**：每個呼叫點的 `old_snapshot` 都 **恆等於** `old_analyze_result.snapshot if old_analyze_result else None`；`new_snapshot` 同理（local 在 221 行 `= new_analyze_result.snapshot`）。
前兩列寫死的 `None` 只是「已知 result 是 None」的捷徑，值完全一致。
⇒ 把累積用 locals 提到頂部初始化為 `None`、各步**成功才賦值**、再用**單一守衛讀 locals**，即可逐點重現全部 9 個呼叫，行為等價。

### 2.4 其他已驗證的不變量

- 8 個提早離場（#1–#8）**全都**先 `steps.extend(self._skip_remaining(_STEP_DEFS, len(steps)))` 再 `_build_result`，`_skip_remaining` 參數一致 ⇒ 可安全統一。
- **只有 analyze_old / analyze_new 兩步會「失敗即終止」**；diff / scope / timeline 失敗**不終止**（標 failed 繼續，符合檔頭 docstring 14–16 行）。run() 在 diff/scope/timeline 後**沒有** `status == "failed"` 守衛。（grep 註：`status == "failed"` 在檔內另有 658 / 672 行，但屬 `_report_step_done` / `_report_summary`，**不在 run() 內**，不計入。）
- 正常完成（#9）的 `_build_result` 傳的是 **`interrupted` 變數**（非字面 False）：若 SIGINT 在最後一個守衛（282）之後、step 6 執行期間到達，最終結果的 `interrupted` 會是 `True`。**這條路徑要保留。**
- **step 6（report）結構與前 5 步不同**：它**不呼叫 `_run_*_step`**，而是 281–301 行**內聯**附加一個 `PipelineStep(step_name="report", status="completed", …)` marker（含 `report_start` / `report_started_at` 計時），實際渲染在外層 CLI/MCP。⇒ §5 的「統一膠水」**不得**把 step 6 硬套進前 5 步的 `_run_X_step` 形狀。
- **`_report_summary`（312 行）只在正常完成（#9）路徑呼叫**；8 條提早離場（#1–#8）**都不發 summary**。這是經由 `progress` callback 可觀察的行為差異，重構須保留「早退不發 summary、正常完成才發」。
- `run()` 的 SIGINT 還原用 **try（164 行）/ finally（316–319 行）**：finally 內 `signal.signal(SIGINT, original_handler)` 還原原 handler，且 handler **只在 main thread 安裝**（144–145 行 `if on_main_thread:`）。重構須完整保留 try/finally 結構與 main-thread 判斷。
- **第 10 條離場（不在 9 個 `_build_result` 內）**：`_validate_paths(config)`（132 行，在 164 行 try **之前**）路徑驗證失敗會 **raise `PipelineError`** 並向外傳遞，不產生 `PipelineResult`。此呼叫位置與行為**原樣保留**，不屬本刀拉直範圍；Phase A 若既有測試已涵蓋則不需重補（plan 確認）。

### 2.5 安全網現況（為何 Phase A 是真需求，非儀式）

跨整個 `tests/unit/core/pipeline/` grep `interrupted|SIGINT|_sigint`：**零命中**。
⇒ 那 6 個中斷守衛的**提早回傳行為、2 個 analyze 失敗終止行為，目前沒有任何測試直接斷言**（正常流程只走過守衛的「未中斷」分支）。
這正是第一刀 Phase 05「100% 行覆蓋擋不住行為沒被釘住」的同類缺口——**我們最想改的那段，恰好最沒被釘**。故必須先補網。

---

## 3. 範圍

**In**
- 僅 `PipelineOrchestrator.run()` 內部的控制流拉直。
- 為 `run()` 的離場路徑補刻畫測試（Phase A）。

**Out（明確不動）**
- `_build_result` 的**簽名與參數**——保持原樣（見 §5 決策）。
- `_try_cached_analyze`（92 行）——另一回事，不併入本刀。
- `_run_*_step`、`_report_*`、`_skip_remaining`、`_validate_paths` 等 helper 的**內部邏輯**（可被 run() 以相同方式呼叫，但不改其實作）。
- 任何步驟分發表 / 通用 step 迴圈引擎（過度抽象，否決）。
- `PipelineResult` / `PipelineStep` 等 model 欄位（護欄：不改 schema）。

---

## 4. 要保留的行為合約（Phase A 釘、Phase B 不可違反）

每條離場路徑產出的 `PipelineResult` 欄位狀態（這是驗收的金標準）：

| 路徑 | steps 內容 | old_snapshot | new_snapshot | diff/scope/timeline | interrupted |
|---|---|---|---|---|---|
| 中斷@step1 前 | 6 步全 skipped | None | None | None | True |
| analyze_old 失敗 | analyze_old=failed＋其餘 5 skipped | None | None | None | False（=當下 interrupted） |
| 中斷@step2 前 | analyze_old=completed＋5 skipped | 設 | None | None | True |
| analyze_new 失敗 | …new=failed＋4 skipped | 設 | None | None | False |
| 中斷@step3 前 | 2 completed＋4 skipped | 設 | 設 | None | True |
| 中斷@step4 前 | 含 diff 步＋其餘 skipped | 設 | 設 | diff 視結果、其餘 None | True |
| 中斷@step5 前 | 含 scope 步（或 skipped）＋其餘 | 設 | 設 | diff/scope 視結果、timeline None | True |
| 中斷@step6 前 | 含 timeline 步（或 skipped） | 設 | 設 | 視結果 | True |
| 正常完成 | 6 步齊全 | 設 | 設 | 視各步結果/skip | 當下 interrupted（可 True） |

掃描/scan_result 欄位由 `_build_result` 內部從 `analyze_result.scan_result` 導出（不變）。

---

## 5. 設計

### Phase A — 先補網（釘住現行行為，對現狀就綠）

新增刻畫測試（建議檔：`tests/unit/core/pipeline/test_pipeline_orchestrator_run_paths.py`），參數化覆蓋 §4 全部 9 條路徑，斷言 `PipelineResult` 的上述欄位狀態。**這些測試必須對「未重構的現行 run()」直接通過**（捕捉現狀，不改行為）。

- **失敗路徑**（analyze_old / analyze_new 失敗）：mock 對應的 `_run_analyze_step` 回傳 `(failed_step, None)`，斷言終止 + 其餘 skipped + 各 snapshot 狀態。
- **中斷路徑**：需在指定步驟前讓 `interrupted` 為 True。**已知挑戰**（見 §7）：`interrupted` 由 SIGINT handler 設定；建議在「前一步的 mock」內以 `signal.raise_signal(signal.SIGINT)` 觸發（pytest 跑在 main thread，handler 已安裝），使下一個守衛捕捉到。plan 須挑最穩健、不 flaky 的注入點。
- **正常完成**：既有 reporter 測試已覆蓋大部分，補齊「正常完成且 `PipelineResult` 欄位齊全」與「step6 執行期間中斷 → 完成但 interrupted=True」兩條斷言。

### Phase B — 拉直（網綠才動，行為等價）

1. **Locals 提頂初始化**：在 try 之前/起始處把累積狀態全初始化為 `None`：
   `old_analyze_result, new_analyze_result, old_snapshot, new_snapshot, diff_result, scope_result, timeline_result`。
   賦值時機分兩類，須精確：
   - **`*_snapshot`（analyze 兩步）**：只在 `status == "failed"` 檢查通過的**成功續流**裡賦值（即現行 220–221 行的 `old_snapshot = old_analyze_result.snapshot`、`new_snapshot = …`），確保 analyze 失敗時 snapshot 維持 `None`——對齊 §2.3。
   - **`diff_result / scope_result / timeline_result`**：**直接從該步呼叫結果賦值**（如現行 235 行 `step, diff_result = self._run_diff_step(...)`），失敗時本就回 `None`、屬正確語意，**不**做「成功才賦值」處理；scope/timeline 僅在各自未 skip 的分支內賦值。

2. **收斂 8 個提早離場為單一處**：以一個讀「當下 locals」的小工具產半成品結果，唯一逐點差異是傳入的 `interrupted` 值（中斷守衛傳 `True`、失敗終止傳當下 `interrupted`）。
   - 推薦形態：`run()` 內的**巢狀閉包**（capture 現行 locals，只收 `interrupted` 旗標參數），避免一個 7+ 參數的方法；plan 若判斷私有方法更清楚亦可，但**不得**改變 `_build_result` 既有簽名。
   - 中斷守衛 ⇒ `if interrupted: return _partial(interrupted=True)`；analyze 失敗 ⇒ `if step.status == "failed": return _partial(interrupted=interrupted)`。

3. **統一步驟膠水（輕量、有界）**：把每步重複的「報進度 announce → `_report_step_done`」記帳收斂（例如一個 `_announce`/`_report` 小 helper 或一致內聯形狀）。
   - **邊界**：各步的 `self._run_X_step(...)` 呼叫**保持顯式、各自具名參數**（analyze/diff/scope/timeline 參數異質）。**不得**抽象成「吃 callable 的通用 step runner」或 step 定義表迴圈——那會滑向被否決的分發引擎。
   - scope（無 `scope_name` 則 skipped）與 timeline（`skip_timeline` 則 skipped）的條件分支**保留語意**。
   - **step 6（report）不納入 `_run_X_step` 形狀的統一**（見 §2.4）：它是內聯 marker append，膠水統一最多套用其 announce/計時記帳，**不得**為了一致性硬造一個 `_run_report_step`。
   - 正常完成路徑末端的 `self._report_summary(progress, result)`（312 行）**只在 #9 呼叫**，早退路徑不呼叫——保留此不對稱（見 §2.4）。

4. **`_build_result` 簽名不動**（決策）：§2.3 證明 snapshot 參數技術上冗餘（恆可從 analyze_result 導出），但收斂它**對 run() 可讀性幾無貢獻**（run() 只是傳 locals），卻要改 internal helper 簽名 + 9 個呼叫點、擴大改動面換邊際效益 ⇒ 判定為**過度設計/資源浪費，砍掉**。`run()` 以提頂 locals 呼叫現有 `_build_result`。

**預期**：`run()` 從 ~220 行降到 ~80 行，讀起來是「驗證路徑 → 裝 SIGINT → 逐步（announce/run/收集/report，遇中斷或 analyze 失敗則 `_partial` 早退）→ 組結果 → finally 還原 handler」一條線。

---

## 6. 護欄（越線即否決）

- 行為零變更：§4 全部 9 條路徑欄位逐一等價。
- 不改 `_build_result` 簽名；不碰 `_try_cached_analyze`；不改任何 `_run_*_step` 內部邏輯。
- 不引入步驟分發表 / 通用 step 迴圈。
- 不改 `PipelineResult` / `PipelineStep` model（schema 護欄）。
- 完整保留 `try/finally` SIGINT handler 還原與 main-thread 判斷。
- 測試零回歸、覆蓋不降。

---

## 7. 風險與緩解

| 風險 | 緩解 |
|---|---|
| **中斷路徑難以在測試中重現**（`interrupted` 由 signal handler 設）⇒ Phase A 可能 flaky | plan 須選穩健注入點：於「前一步 mock」內 `signal.raise_signal(SIGINT)`（main thread、handler 已裝），或直接 patch handler 設的旗標。優先非 signal 的確定性注入。**這是本刀最大的測試風險，plan 要明確解法。** |
| Locals 賦值時機錯置（在失敗檢查前賦 snapshot）導致失敗路徑 snapshot 不再為 None | §5 Phase B-1 明定「成功續流才賦值」；Phase A 的失敗路徑斷言會擋住此迴歸。 |
| 膠水統一不慎滑成通用 dispatcher | §5 Phase B-3 邊界：`_run_X_step` 呼叫保持顯式具名；§6 護欄複述。 |
| 巢狀閉包 capture 易讀性疑慮 | 閉包只收 `interrupted` 參數、其餘讀 live locals；若 plan 認為私有方法更清楚可改用（不違簽名護欄）。 |

---

## 8. 驗收標準

1. Phase A 刻畫測試對**未重構**的 run() 全綠（證明捕捉的是現狀）。
2. Phase B 後：§4 全部 9 條路徑測試仍全綠、欄位逐一等價。
3. 全套件零回歸；`pipeline_orchestrator.py` 覆蓋不降。
4. `run()` 行數顯著下降（目標 ~80 行）、6 次中斷守衛收斂為單一處。
5. `_build_result` 簽名未變、`_try_cached_analyze` 未動（diff 檢查）。

---

## 9. Non-goals

- 不優化管線執行效能（純結構重構）。
- 不調整步驟順序或新增/移除步驟。
- 不處理 backlog 其他刀（T2 models 套件化等）——逐刀獨立。
