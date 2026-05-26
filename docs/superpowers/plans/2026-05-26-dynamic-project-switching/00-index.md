# Dynamic Project Path Switching — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 UIServer 在執行期接受新的專案路徑（`POST /api/set-project`），無需重啟 server。

**Architecture:** `APIHandlers.__init__` 改為 callable 注入（backward compatible properties），UIServer 新增 `_switch_lock` 和 `_switch_project()` 方法；JS `ui-wizard.js` 的 PAGE_ACTION 新增切換入口 UI 與 conflict 確認區。

**Tech Stack:** Python 3.11+（pytest + unittest.mock）、Vanilla JS ES modules（Vitest + jsdom）

---

## 任務清單

| # | 類別 | 任務文件 | 依賴 |
|---|---|---|---|
| 01 | Python | [task-01-jobstore.md](task-01-jobstore.md) | 無 |
| 02 | Python | [task-02-api-handlers-refactor.md](task-02-api-handlers-refactor.md) | 無（可與 01 平行）|
| 03 | Python | [task-03-uiserver-switch.md](task-03-uiserver-switch.md) | Task 01 + 02 完成後 |
| 04 | Python | [task-04-route.md](task-04-route.md) | Task 03 完成後 |
| 05 | JS | [task-05-wizard-js.md](task-05-wizard-js.md) | Task 04 完成後（需要 API 存在）|

**建議執行順序：** Task 01 + 02 平行 → Task 03 → Task 04 → Task 05

---

## 架構異動摘要

| 檔案 | 動作 | 說明 |
|---|---|---|
| `the_door/src/the_door/core/ui/job_store.py` | 修改 | 新增 `get_running_job_id()` |
| `the_door/src/the_door/core/ui/api_handlers.py` | 修改 | `__init__` callable 注入；新增 `handle_post_set_project` |
| `the_door/src/the_door/core/ui/server.py` | 修改 | `_switch_lock`；lambda 注入 APIHandlers；新增路由 |
| `the_door/tests/unit/core/ui/test_api_handlers_set_project.py` | 新增 | handle_post_set_project 測試 |
| `the_door/tests/unit/core/ui/test_server_set_project.py` | 新增 | 路由 + 切換整合測試 |
| `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js` | 修改 | 新增 switch 狀態 + UI |
| `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js` | 修改 | 新增 switch 測試 |

---

## 測試指令

```bash
# Python
cd the_door && pytest tests/unit/core/ui/test_api_handlers_set_project.py tests/unit/core/ui/test_server_set_project.py -v

# 全套回歸
cd the_door && pytest tests/ -q 2>&1 | tail -5

# JS
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-wizard.test.js --coverage 2>&1 | tail -10
```
