# Multi-Project Grouping — Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Read ONLY this index first; load each task file on demand when you reach that task.

**Goal:** 讓 The Door 支援手動專案群組，registry 記錄群組關係，viewer 頂部顯示同群切換下拉選單。

**Architecture:** 以 `registry.json` 的 `__groups__` 段落作為群組持久化層；CLI `the-door group` 指令管理群組；MCP 工具回傳群組資訊作為 AI 操作提示；API `GET /api/group` 讓 viewer 查詢同群成員；前端 `project-switcher.js` 純函式模組提供下拉 UI 與 inline toast 切換行為。

**Tech Stack:** Python 3.12, Click, pytest + tmp_path, JavaScript ES modules, Vitest (jsdom)

**Spec:** `docs/superpowers/specs/2026-06-14-multi-project-grouping-design.md`

---

## File Map

| 動作 | 檔案 |
|---|---|
| Modify | `the_door/src/the_door/core/registry.py` |
| Create | `the_door/src/the_door/cli/group_cmd.py` |
| Modify | `the_door/src/the_door/cli/main.py` |
| Modify | `the_door/src/the_door/cli/ui_cmd.py` |
| Modify | `the_door/src/the_door/mcp/tools/project_list_tool.py` |
| Modify | `the_door/src/the_door/mcp/tools/snapshot_write_tool.py` |
| Create | `the_door/src/the_door/core/ui/api/handlers/group.py` |
| Modify | `the_door/src/the_door/core/ui/api/router.py` |
| Modify | `the_door/src/the_door/core/ui/server.py` |
| Modify | `the_door/src/the_door/core/ui/api/_gen_docs.py` |
| Create | `docs/frontend-local-version-viewer/viewer/js/project-switcher.js` |
| Modify | `docs/frontend-local-version-viewer/viewer/js/api.js` |
| Modify | `docs/frontend-local-version-viewer/viewer/js/app.js` |
| Modify | `docs/frontend-local-version-viewer/viewer/index.html` |
| Modify | `the_door/tests/unit/core/test_registry.py` |
| Create | `the_door/tests/unit/cli/test_group_cmd.py` |
| Create | `the_door/tests/unit/cli/test_ui_cmd.py` |
| Create | `the_door/tests/unit/mcp/tools/test_project_list_tool.py` |
| Create | `the_door/tests/unit/core/ui/api/handlers/test_group_handler.py` |
| Create | `docs/frontend-local-version-viewer/viewer/tests/project-switcher.test.js` |

---

## Task Summary

| Task | 內容 | 檔案 |
|---|---|---|
| 1 | `ProjectRegistry` — group CRUD + helpers + `list_projects()` fix | [task-1-registry.md](task-1-registry.md) |
| 2 | `the-door group` CLI 指令群 (create/add/remove/list) | [task-2-cli-group-cmd.md](task-2-cli-group-cmd.md) |
| 3 | 掛載 group_cmd + `ui_cmd` 動態預設 + last_opened_at | [task-3-cli-main-ui-cmd.md](task-3-cli-main-ui-cmd.md) |
| 4 | `project_list` MCP 加 group 欄位 + ungrouped hint | [task-4-mcp-project-list.md](task-4-mcp-project-list.md) |
| 5 | `snapshot_write` MCP 加 group hint | [task-5-mcp-snapshot-write.md](task-5-mcp-snapshot-write.md) |
| 6 | `GET /api/group` endpoint + GroupHandlers + router/server/_gen_docs | [task-6-api-group.md](task-6-api-group.md) |
| 7 | 前端 project-switcher.js + api.js + app.js + index.html | [task-7-frontend.md](task-7-frontend.md) |

---

## 完整回歸（所有 task 完成後執行）

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/ -q 2>&1 | tail -5
```

```bash
cd docs/frontend-local-version-viewer/viewer && npx vitest run 2>&1 | tail -5
```

Expected: 全部 PASSED
