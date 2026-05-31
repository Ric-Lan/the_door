# Phase 05 — 移除舊 api_handlers.py（Task 12）

> 讀本檔 + README 即可執行。前置：Phase 04 完成（server 已切到 router、兩道安全網綠）。

## Task 12: 移除舊 `api_handlers.py` 與其舊測試

**Files:**
- Delete: `the_door/src/the_door/core/ui/api_handlers.py`
- Delete: `the_door/tests/unit/core/ui/test_api_handlers.py`、`test_api_handlers_analyze.py`、`test_api_handlers_diff_explanation.py`、`test_api_handlers_notes.py`、`test_api_handlers_set_project.py`、`test_api_handlers_ui3.py`
- Modify: 任何殘留 import `APIHandlers` 處（Phase 04 後應已無）

- [ ] **Step 1: 確認無殘留 import**

Run: `cd the_door && grep -rn "api_handlers\|APIHandlers" src/ tests/ | grep -v "core/ui/api/"`
Expected: 無輸出（或僅註解）。有則改掉。

- [ ] **Step 2: 刪除舊檔**

```bash
cd the_door && git rm src/the_door/core/ui/api_handlers.py \
  tests/unit/core/ui/test_api_handlers.py tests/unit/core/ui/test_api_handlers_analyze.py \
  tests/unit/core/ui/test_api_handlers_diff_explanation.py tests/unit/core/ui/test_api_handlers_notes.py \
  tests/unit/core/ui/test_api_handlers_set_project.py tests/unit/core/ui/test_api_handlers_ui3.py
```

- [ ] **Step 3: 跑全套測試確認零回歸**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest -q`
Expected: 全 PASS，無 import 錯誤、無指向死類別殘骸。

- [ ] **Step 4: Commit**

```bash
cd the_door && git commit -m "refactor(api): remove old api_handlers.py and its tests (replaced by api/ package)"
```
