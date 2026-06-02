# Task 04: 驗收與收尾

**目的**：用客觀指標確認拉直達標且未越護欄，跑完整套件與覆蓋，更新 backlog 進度。

**Files:**
- Modify: `docs/refactoring/2026-05-31-refactoring-backlog.md`（進度勾選）
- Modify: `docs/superpowers/specs/2026-06-02-pipeline-orchestrator-run-straighten-design.md`（狀態改為已實作）

**前置**：Task 03 已 commit、全套件綠。

---

- [ ] **Step 1: 驗「8 個提早離場已收斂」（核心達標指標）**

Run（cwd = `the_door/`）：
```
grep -c "self._build_result(" src/the_door/core/pipeline/pipeline_orchestrator.py
grep -c "self._skip_remaining(" src/the_door/core/pipeline/pipeline_orchestrator.py
```
Expected:
- `self._build_result(` = **2**（`_partial` 內 1 + 正常完成 1；重構前是 9）。
- `self._skip_remaining(` = **1**（只在 `_partial` 內；重構前是 8）。

若數字不符 → 守衛沒真正收斂，回 Task 03 檢查。

- [ ] **Step 2: 驗護欄未越線（簽名/未動區域）**

Run：
```
git diff edd2942..HEAD -- src/the_door/core/pipeline/pipeline_orchestrator.py | grep -E "^[-+].*def _build_result|^[-+].*def _try_cached_analyze"
```
（`edd2942` 是本刀開工前 backlog commit；若實際 base 不同，改用 `git log` 找本刀第一個 commit 的父節點。）
Expected: **無任何輸出** —— 代表 `_build_result` 與 `_try_cached_analyze` 的 `def` 行未被改動（簽名/定義原樣）。

亦可人工確認：`_build_result` 仍是 11 個參數、`_try_cached_analyze` 整段未出現在 diff 中。

- [ ] **Step 3: 全套件 + 覆蓋（零回歸、覆蓋不降）**

Run：
```
PYTHONUTF8=1 python -m pytest --cov=the_door.core.pipeline.pipeline_orchestrator --cov-report=term-missing tests/unit/core/pipeline/
```
Expected: 全 PASS；`pipeline_orchestrator.py` 覆蓋率**不低於**重構前（拉直 + 新刻畫測試後，分支應持平或上升）。記下 miss 行數，若有新 miss 行需補測試或檢查是否有不可達分支。

再跑一次完整套件確認全域零回歸：
```
PYTHONUTF8=1 python -m pytest
```
Expected: 全 PASS。

- [ ] **Step 4: 更新 backlog 進度**

編輯 `docs/refactoring/2026-05-31-refactoring-backlog.md`，把進度區的：
```
- [ ] T4 pipeline_orchestrator 長函式（724 行 ✓ 已重驗）
```
改為：
```
- [x] T4 pipeline_orchestrator 長函式 — 已實作（run() 拉直：8 提早離場收斂為單一 _partial 閉包）
```

- [ ] **Step 5: 更新 spec 狀態**

編輯 `docs/superpowers/specs/2026-06-02-pipeline-orchestrator-run-straighten-design.md` 的標頭，把：
```
> **日期**：2026-06-02　**狀態**：設計核准、待寫 plan
```
改為：
```
> **日期**：2026-06-02　**狀態**：已實作（plan: docs/superpowers/plans/2026-06-02-pipeline-orchestrator-run-straighten/）
```

- [ ] **Step 6: Commit**

```
git add docs/refactoring/2026-05-31-refactoring-backlog.md docs/superpowers/specs/2026-06-02-pipeline-orchestrator-run-straighten-design.md
git commit -m "docs: mark T4 (run straighten) implemented"
```

- [ ] **Step 7: 收尾**

本刀完成。回報：
- `self._build_result(` 9 → 2、`self._skip_remaining(` 8 → 1；
- 11 條刻畫測試 + 既有 pipeline 測試全綠、全套件零回歸、覆蓋不降；
- `_build_result` 簽名與 `_try_cached_analyze` 未動。

接著等使用者決定 merge（依偏好：本地 merge、不主動 push）。後續可動 backlog 的 **T2（models.py 套件化，需獨立 spec）**。
