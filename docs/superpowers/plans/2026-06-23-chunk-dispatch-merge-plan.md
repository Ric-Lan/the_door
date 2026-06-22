# Chunk Dispatch + Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **此計畫分拆為多檔以降低長文閱讀幻覺。** 本檔是索引；逐階段任務在 `2026-06-23-chunk-dispatch-merge/` 子目錄。**依序執行 Phase 1 → 2 → 3。**

**Goal:** 補上大專案分塊翻譯的「合併」與「天花板守衛」：(1) `chunk_planner` 加 feasibility 守衛（超載回饋無法翻譯）；(2) 新 `chunk_merge` 決定性工具，收齊各 chunk 的 features、從結構邊推導 static relations、組裝成可寫入 payload；(3) CLAUDE.md 分塊翻譯協定。

**Architecture:** subagent 只產 features（命名空間 feature_id、無 relations）；`chunk_merge` 從 structure-view 邊**決定性推導**整張 feature relation 圖（CLAUDE.md 閘門：結構走純程式）。dispatch 是執行 agent 的事（協定文件），The Door 只提供工具。純加法，不改 gate / 契約 / viewer / 單-agent 既有路徑。

**Tech Stack:** Python 3（stdlib only）、`mcp` SDK、pytest。複用 `locator.load_views`。

---

## 來源 spec
[docs/superpowers/specs/2026-06-23-chunk-dispatch-merge-design.md](../specs/2026-06-23-chunk-dispatch-merge-design.md)

## 檔案結構
| 檔案 | 責任 | 動作 |
|---|---|---|
| `the_door/src/the_door/core/structure_view/chunk_planner.py` | `plan()` 加 `max_total_tokens` + `feasible` + `too_large` regime | 純加法改 |
| `the_door/src/the_door/core/structure_view/chunk_merge.py` | 合併核心（收 features / node→feature 映射 / 推導 relations / 組裝） | 新增 |
| `the_door/src/the_door/mcp/tools/chunk_merge_tool.py` | MCP `chunk_merge` 轉接 | 新增 |
| `the_door/src/the_door/mcp/server.py` | 註冊 `chunk_merge`（唯讀、不入 gate） | 改 |
| `CLAUDE.md` | 大專案分塊翻譯協定段 + 工具表一列 | 改 |
| `the_door/tests/unit/core/structure_view/test_chunk_planner.py` | feasibility 守衛測試 | 加 |
| `the_door/tests/unit/core/structure_view/test_chunk_merge.py` | 合併核心測試 | 新增 |
| `the_door/tests/unit/mcp/tools/test_chunk_merge_tool.py` | MCP 轉接煙霧測試 | 新增 |

## 階段
- **Phase 1 — Planner feasibility 守衛** → [01-planner-guard.md](2026-06-23-chunk-dispatch-merge/01-planner-guard.md)
- **Phase 2 — chunk_merge 核心** → [02-merge-core.md](2026-06-23-chunk-dispatch-merge/02-merge-core.md)
- **Phase 3 — MCP 工具 + CLAUDE.md 協定** → [03-tool-and-protocol.md](2026-06-23-chunk-dispatch-merge/03-tool-and-protocol.md)

## 關鍵事實（執行者必讀，避免臆造）
- **複用** `from the_door.core.structure_view.locator import load_views, LocateError`。`load_views(codebase_path) -> {node_id: view}`，缺 artifact 拋 `LocateError`。
- **node view 欄位**：`out_edges`＝`[{to_node_id, type, resolution}]`，`type` ∈ {`calls`,`imports`,`extends`}（真實邊型別，已實測）。
- **node_id 格式**＝`file::symbol`。
- **`_response_envelope.wrap(payload, project_path)`**：注入 next_actions，回 dict。
- **server 註冊三點**：`mcp/server.py` 的 import 區、`_build_tools()` 的 `Tool(name=, description=, inputSchema=)` 清單、`call_tool` 的 `elif name == ...: return await self._dispatch_tool(module, arguments)`。`REGISTERED_TOOL_NAMES` 由 `_build_tools()` 自動衍生。
- **chunk_merge 唯讀**：回 payload、不寫 snapshot、**不入 C3 gate**（gate 只管 snapshot_write/patch）。
- **chunk_planner 現有輸出**：`{target_tokens, regime, needs_split, total_est_tokens, chunks, rollup}`；`_plan_from_views(views, target_tokens, large_ratio)` 是純核心；`_assemble(...)` 組裝輸出。
- **fixture**：`fixtures_dir / "sample_codebases" / "python_simple"`（6 nodes：`app.py::login`→`auth.py::authenticate_user`(calls)→`auth.py::generate_token`(calls)；`login`→`tasks.py::schedule_cleanup`(imports)）。

## Spec ↔ Task 覆蓋（自審見各 phase 末）
spec §5 守衛→Phase1；§4 chunk_merge（id 唯一/映射/推導/聚合/rollup）→Phase2；§3+§4 工具+§2 協定→Phase3。§6 非目標＝不實作的邊界（碎裂不去重、只 static relation、不 spawn）。

## 刻意延後（非遺漏）
- **dispatch 編排本身無程式碼**：The Door 不 spawn subagent，派發是 agent 依 CLAUDE.md 協定（Phase 3 文件）執行。本計畫交付工具 + 協定，不交付編排引擎。
- **語意去重 / inferred relation / 增量×分塊**：spec §6 明列出範圍。
