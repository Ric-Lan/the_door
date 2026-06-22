# Chunk Split Principle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **此計畫分拆為多檔以降低長文閱讀幻覺。** 本檔是索引；逐階段任務在 `2026-06-22-chunk-split/` 子目錄。**依序執行 Phase 1 → 2 → 3 → 4。**

**Goal:** 給定既有 structure-view，純程式地評估專案規模（triage）並把節點切成 token 預算內、可獨立交給一個 LLM subagent 翻譯的 chunk。

**Architecture:** 新增純函式模組 `core/structure_view/chunk_planner.py`。資料來源複用已存在的 `locator.load_views`（讀 structure-view regions）。流程＝逐節點估 token → triage 決定 regime/要不要切 → 連通分量打包（Tier 1）/ BFS 排序切分（Tier 2）/ 依序切原語（Tier 3 保底）→ 組裝 chunk 計畫 + 品質 rollup。**零 LLM、純決定性、純加法**（不改 models/extract_structure/契約/gate/viewer/region_partition）。

**Tech Stack:** Python 3（stdlib only：json/collections）、pytest。**不引圖論套件**（networkx 等）。

---

## 來源 spec
[docs/superpowers/specs/2026-06-22-chunk-split-principle-design.md](../specs/2026-06-22-chunk-split-principle-design.md)

## 檔案結構

| 檔案 | 責任 | 動作 |
|---|---|---|
| `the_door/src/the_door/core/structure_view/chunk_planner.py` | 切分唯一邏輯（estimator/graph/tiers/triage/plan） | 新增（分 4 phase 漸進建構） |
| `the_door/tests/unit/core/structure_view/test_chunk_estimator.py` | Phase 1 token 估計 | 新增 |
| `the_door/tests/unit/core/structure_view/test_chunk_graph.py` | Phase 2 鄰接/連通分量 | 新增 |
| `the_door/tests/unit/core/structure_view/test_chunk_tiers.py` | Phase 3 三層原語 | 新增 |
| `the_door/tests/unit/core/structure_view/test_chunk_planner.py` | Phase 4 triage + plan 整合 | 新增 |

> 測試路徑對齊 repo 鏡像慣例（`tests/unit/core/structure_view/`，與 `test_locator.py` 同目錄）。

## 階段
- **Phase 1 — Token 估計器** → [01-estimator.md](2026-06-22-chunk-split/01-estimator.md)（`estimate_tokens` / `_is_cjk`）
- **Phase 2 — 圖工具** → [02-graph.md](2026-06-22-chunk-split/02-graph.md)（`_in_degree` / `build_adjacency` / `connected_components`）
- **Phase 3 — 三層原語** → [03-tiers.md](2026-06-22-chunk-split/03-tiers.md)（`_slice_by_order`(Tier3) / `_bfs_order`+Tier2 用法 / `_pack`(Tier1)）
- **Phase 4 — Triage + 組裝** → [04-triage-and-plan.md](2026-06-22-chunk-split/04-triage-and-plan.md)（`triage` / `plan` / `_cross_chunk_edges` / `_assemble` + 真實 fixture 測試）

## 關鍵事實（執行者必讀，避免臆造）
- **資料來源複用**：`from the_door.core.structure_view.locator import load_views`。`load_views(codebase_path) -> dict[str, dict]`（{node_id: view}），缺 artifact 拋 `LocateError`。**不要重寫 gz 讀取**。`plan()` 讓 `LocateError` 自然向上拋。
- **node view 欄位**（`core/structure_view/node_view.py`）：`node_id`、`name`、`file`、`language`、`start_line`、`end_line`、`topology`（**dict 或 None**：`in_degree`/`out_degree`/`topology_rank`/`is_entry_point`/`batch_assignment`）、`out_edges`（`[{to_node_id,type,resolution}]`）、`in_edges`（`[{from_node_id,type,resolution}]`）、`docstring`/`comments`/`parameters` 等。
- **node_id 格式**＝`file::symbol`（如 `auth.py::authenticate_user`）。
- **邊的完整性**：每條邊 A→B 同時是 A 的 `out_edges` 與 B 的 `in_edges`，故**只遍歷各節點 `out_edges` 即涵蓋所有邊一次**。`to_node_id` 不在 views 內者（外部/殘餘）→ 不連邊、略過。
- **fixture**：`fixtures_dir`（conftest）→ `fixtures_dir / "sample_codebases" / "python_simple"`（6 nodes：`app.py::login`→`auth.py::authenticate_user`→`auth.py::generate_token`；`app.py::login` 亦連 `tasks.py::schedule_cleanup`；`app.py::list_users`、`tasks.py::notify_admin` 較孤立）。
- **決定性鐵則**：所有產生順序處用穩定排序（node_id 字典序 / `(-in_degree, node_id)`）；同輸入必同輸出。

## Spec ↔ Task 覆蓋（自審見各 phase 末）
spec §2 triage→Phase4；§3 Tier1→Phase3 `_pack`、Tier2→Phase3 `_bfs_order`+Phase4 用法、Tier3→Phase3 `_slice_by_order`；§4 估計→Phase1；§5 輸出/rollup/cross_chunk_edges→Phase4；§9 測試→各 phase TDD（plan 層精確案例用 Phase4 的純核心 `_plan_from_views` 以合成 views 測）。

## 刻意延後（非遺漏）
- **spec §5「複用 region 當粗切第一刀」是 optional 優化**——本計畫**不實作**。理由：spike 觀測規模（~2782 nodes）下直接建全圖 + 連通分量極廉價，region 預切屬 YAGNI；`connected_components` 已自然分區。若未來遇超大專案建圖成本浮現再加（屆時 region 預切是純效能優化、不改輸出語義）。
- **MCP/CLI 轉接**：spec §8 言明不強制；本計畫只交付純函式核心 `plan()`/`_plan_from_views()`，轉接留待後續 dispatch spec 一併決定。
