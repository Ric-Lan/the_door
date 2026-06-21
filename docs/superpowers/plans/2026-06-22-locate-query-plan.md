# Locate Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **此計畫分拆為多檔以降低長文閱讀幻覺。** 本檔是索引；逐階段任務在 `2026-06-22-locate-query/` 子目錄。**依序執行 Phase 1 → 2 → 3。**

**Goal:** 在 The Door 既有的 `.the-door/structure-view/` 產出上，加一層輕薄的 symbol 定位點查（`search` + `node`），讓 AI（MCP）與人（CLI）能快速定位程式碼——同一份產出、兩處用。

**Architecture:** 一個純函式核心 `core/structure_view/locator.py`（讀 region artifact、建記憶體表、答查詢、算新鮮度），外加兩個薄轉接：MCP `locate` 工具與 CLI `the-door locate` 群組。**零重抽取**（不呼叫 ASTExtractor，只讀持久化 artifact）、**純加法**（不改 model、不 bump 契約、不動 gate）。

**Tech Stack:** Python 3、gzip/json（讀 artifact）、`mcp` SDK（MCP 工具）、`click`（CLI）、pytest（測試）。

---

## 來源 spec

[docs/superpowers/specs/2026-06-21-locate-query-design.md](../specs/2026-06-21-locate-query-design.md)

## 檔案結構（會新增/修改）

| 檔案 | 責任 | 動作 |
|---|---|---|
| `the_door/src/the_door/core/structure_view/locator.py` | 定位查詢唯一邏輯（load/search/node/freshness） | 新增 |
| `the_door/src/the_door/mcp/tools/locate_tool.py` | MCP `locate` 轉接 | 新增 |
| `the_door/src/the_door/mcp/server.py` | 註冊 `locate` 工具 | 修改 |
| `the_door/src/the_door/cli/locate_cmd.py` | CLI `locate` 群組（search/node 子指令） | 新增 |
| `the_door/src/the_door/cli/main.py` | 註冊 `locate_group` | 修改 |
| `docs/locate-query.md` | 使用文件（標 secondary + 兩條限制） | 新增 |
| `CLAUDE.md` | 工具表加一列 | 修改 |
| `the_door/tests/unit/core/structure_view/test_locator.py` | 純函式單元測試（synthetic views） | 新增 |
| `the_door/tests/unit/core/structure_view/test_locator_freshness.py` | freshness 三態（tmp checklist） | 新增 |
| `the_door/tests/integration/test_locator_fixture.py` | 真實 fixture 端到端 | 新增 |
| `the_door/tests/unit/mcp/tools/test_locate_tool.py` | MCP 工具煙霧測試 | 新增 |
| `the_door/tests/unit/cli/test_locate_cmd.py` | CLI 煙霧測試 | 新增 |

> 測試路徑已對齊 repo 的鏡像慣例（測試樹鏡像 `src/` 結構，如
> `tests/unit/core/structure_view/`、`tests/unit/mcp/tools/`、`tests/unit/cli/`）。

## 階段

- **Phase 1 — 核心 locator** → [01-locator-core.md](2026-06-22-locate-query/01-locator-core.md)
  Task 1 load_views、Task 2 search_views、Task 3 node_detail、Task 4 compute_freshness、Task 5 public compose + 真實 fixture 整合測試。
- **Phase 2 — MCP 工具 + CLI** → [02-mcp-and-cli.md](2026-06-22-locate-query/02-mcp-and-cli.md)
  Task 6 locate_tool + server 註冊、Task 7 CLI locate 群組 + main 註冊。
- **Phase 3 — 文件** → [03-docs.md](2026-06-22-locate-query/03-docs.md)
  Task 8 `docs/locate-query.md` + CLAUDE.md 工具表。

## 關鍵事實（執行者必讀，避免臆造）

- **node view 欄位**（來自 `core/structure_view/node_view.py`）：`node_id`、`name`、`type`、`file`、`language`、`start_line`、`end_line`、`topology`（dict 或 **None**）、`in_edges`（`[{from_node_id,type,resolution}]`）、`out_edges`（`[{to_node_id,type,resolution}]`）。
- **node_id 真實格式＝`file::symbol`**（如 `auth.py::authenticate_user`），碰撞時加 `#i` 後綴。**不是** `ClassName.method`（CLAUDE.md 舊述已過時）。
- **region artifact**：`<root>/.the-door/structure-view/regions/<region_id>.json.gz`，gzip JSON＝`{region_id, nodes: [view,...]}`。用 `structure_index.view_dir(codebase_path)` 取得 `structure-view` 目錄，不要硬編路徑。
- **freshness 來源**：`core/checklist.read_checklist(codebase_path)` → `["stages"]["edge_residue"]["source_files"]`＝`{relpath: [mtime_ns, size]}`（fail-soft，缺則 unknown）。
- **`wrap` 簽章**：`from the_door.mcp.tools._response_envelope import wrap` → `wrap(payload: dict, project_path: Path) -> dict`（注入 next_actions）。
- **fixture**：`the_door/tests/conftest.py` 提供 `fixtures_dir` fixture。定位用 fixture＝`fixtures_dir / "sample_codebases" / "python_simple"`（6 nodes，已含 structure-view，**無** checklist.json → 該 fixture freshness=unknown）。

## 自審結果（已修）

見各 phase 檔末的「Phase 自審」。索引層覆蓋檢查：spec §3→Task1、§4.1→Task2、§4.2→Task3、§4.3→Task7、§5→Task4、§2 轉接→Task6/7、§6→Task8、§8 測試→散落各 Task 的 TDD 步驟。無遺漏。
