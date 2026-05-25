# Wizard UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `wizard.html` 作為伺服器啟動後的第一個入口頁，引導使用者（或 LLM agent）以結構化問卷完成分析，取代原本對 `index.html` 的直接開啟。

**Architecture:** `wizard.html` 是獨立的多頁問卷頁，共用 `styles.css`，搭配新的 `wizard.css` 與 `ui-wizard.js`。後端新增 `/api/analyze` endpoint（`handle_post_analyze`），`ui_cmd.py` 啟動時改開 `/wizard.html`。

**Tech Stack:** Python 3.11+（pytest + unittest.mock）、Vanilla JS ES modules（Vitest + jsdom）

---

## 任務清單

| # | 檔案類別 | 任務文件 | 依賴 |
|---|---|---|---|
| 01 | Python 後端 | [task-01-backend.md](task-01-backend.md) | 無 |
| 02 | JS 邏輯 | [task-02-wizard-js.md](task-02-wizard-js.md) | 無（可平行） |
| 03 | HTML / CSS | [task-03-wizard-ui.md](task-03-wizard-ui.md) | Task 02 完成後 |
| 04 | CLI 入口 | [task-04-cli.md](task-04-cli.md) | Task 01 完成後 |

**建議執行順序：** Task 01 + Task 02 平行 → Task 03 → Task 04 → 端對端驗收

---

## 檔案對照表

| 路徑 | 動作 | 說明 |
|---|---|---|
| `the_door/src/the_door/models.py` | 修改 | `AnalyzeConfig` 加 `extra_ignore` + `snapshot_label` |
| `the_door/src/the_door/core/extraction/ast_extractor.py` | 修改 | `extract()` 接受 `extra_ignore` |
| `the_door/src/the_door/core/pipeline/analyze_pipeline.py` | 修改 | 傳遞 `extra_ignore` + `snapshot_label` |
| `the_door/src/the_door/core/ui/api_handlers.py` | 修改 | 新增 `handle_post_analyze` |
| `the_door/src/the_door/core/ui/server.py` | 修改 | 註冊 `/api/analyze` POST 路由 |
| `the_door/tests/unit/core/ui/test_api_handlers_analyze.py` | 新增 | `handle_post_analyze` 測試 |
| `the_door/tests/unit/core/ui/test_server_analyze.py` | 新增 | server 路由測試 |
| `the_door/src/the_door/cli/ui_cmd.py` | 修改 | 啟動時開 `wizard.html` |
| `the_door/tests/unit/cli/test_ui_cmd_wizard.py` | 新增 | cli 入口測試 |
| `docs/frontend-local-version-viewer/viewer/wizard.html` | 新增 | 問卷入口頁 |
| `docs/frontend-local-version-viewer/viewer/wizard.css` | 新增 | wizard 專用樣式 |
| `docs/frontend-local-version-viewer/viewer/js/ui-wizard.js` | 新增 | 問卷狀態機 |
| `docs/frontend-local-version-viewer/viewer/tests/ui-wizard.test.js` | 新增 | JS 單元測試 |

---

## 測試指令

```bash
# Python 測試
cd the_door && pytest tests/unit/core/ui/test_api_handlers_analyze.py tests/unit/core/ui/test_server_analyze.py tests/unit/cli/test_ui_cmd_wizard.py -v

# JS 測試（含 coverage）
cd docs/frontend-local-version-viewer/viewer && npx vitest run --coverage
```
