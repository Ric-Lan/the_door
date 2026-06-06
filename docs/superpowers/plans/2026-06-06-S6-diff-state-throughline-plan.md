# S6 plan：diff_state 整膜（3-task inline TDD）

> **日期**：2026-06-06　**狀態**：plan（待使用者確認後 inline TDD 執行）　**承**：[`2026-06-06-S6-diff-state-throughline-spec.md`](../specs/2026-06-06-S6-diff-state-throughline-spec.md)（spec 已雙審：concept-review＋5 軸；本 plan 引 spec §3.x 不重貼 exact code，防雙源漂移）。
> **執行方式**：inline TDD（S0-S5 皆 inline）。red→green→（必要）refactor。逐 task 跑相關測、末 task 跑全測。完成 ff-merge main、**不主動 push**。
> **基線**：main `4da30e1`、全測 1525 passed。驗收＝1525＋新測、零回歸（除 diff_tool emit characterization 有意更新）。
> **環境**：`pip install -e ./the_door`（換 worktree 必做）；pytest cwd＝內層 `the_door/`；`PYTHONUTF8=1`。

---

## 範圍鎖定（執行前確認，承 spec §1）

- **in**：①`core/diff/diff_membrane.py`（兩 contrasts＋4 工廠）②`diff_tool.py:82,83` json emit 投影 ③`diff_engine` 值域雙向釘樁。
- **out（不得誤動）**：`report_renderer.render_json`／`_diff_result_to_dict`（report/viewer 面 cut）、`cli/diff_cmd`、`diff_renderer`/`scope_renderer` mermaid、`graph_view_model`、`ui/api/handlers/diff.py`、`diff-result.schema.json`、`models/diff.py`（型別不改）、`diff_engine` producer 字面（只加 characterization、不改邏輯）。
- **grep gate（每 task 末）**：確認改動檔僅 `diff_membrane.py`＋`diff_tool.py`＋對應測檔；`git diff --stat` 不含 out 清單。

---

## Task 1 — diff 膜詞彙地基（red→green）

**交付**：`the_door/src/the_door/core/diff/diff_membrane.py`（exact code＝spec §3.1）＋`the_door/tests/unit/core/diff/test_diff_membrane.py`。

**TDD**：
1. **red**：先寫 `test_diff_membrane.py`，import `node_diff_signal/edge_diff_signal/node_diff_element/edge_diff_element/NODE_DIFF_CONTRASTS/EDGE_DIFF_CONTRASTS`（ImportError 紅）。
2. **green**：建 `diff_membrane.py`（照 spec §3.1 逐字；安置 `core/diff/`，產地同 `diff_engine`）。

**測試（對應 spec §4 不變量 C1/C4 ＋ §6）**：
- **C1-node**：`node_diff_signal(v)` 對 5 值各回 `SignalPosition`，`.contrasts == NODE_DIFF_CONTRASTS`（5-set）、`.gloss` 非空；`node_diff_element(v).to_json() == {"value": v, "position": {"kind":"signal", "contrasts":[...5...], "gloss":..., "preconditions":[], "consequences":[], "co_requires":[]}}`。
- **C1-edge**：`edge_diff_signal(v)` 對 3 值同理、`.contrasts == EDGE_DIFF_CONTRASTS`（3-set）。
- **C4-正交**：`set(NODE_DIFF_CONTRASTS) != set(EDGE_DIFF_CONTRASTS)`；交集 == `{"added","removed"}`（共享字串證）；差集非空（node 獨有 attribute_changed/dependency_changed/unchanged、edge 獨有 modified）。
- **I4 防呆**：`node_diff_element("bogus")` → `KeyError`（_NODE_GLOSS 缺鍵）；payload∉contrasts 不會發生（element 永走 signal 分支、payload 來自同一值）。
- **gloss 涵蓋**：`set(_NODE_GLOSS) == set(NODE_DIFF_CONTRASTS)`、`set(_EDGE_GLOSS) == set(EDGE_DIFF_CONTRASTS)`（無漏值/死值）。

**gate**：`cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_diff_membrane.py -q` 綠。`git diff --stat`＝僅 2 新檔。

---

## Task 2 — diff_tool json emit 膜投影（characterization pin→flip）

**交付**：`diff_tool.py:82,83`（投影＝spec §3.2）＋新增 `diff_tool` json happy-path 測（spec §6 C3；🟢 spec §2 證現無此測）。

**TDD（契約改動→characterization 先行）**：
1. **pin（red 前先釘現狀）**：新增測 `tests/unit/mcp/tools/test_diff_tool.py`（或既有 mcp 測檔），構造**兩個 snapshot**（baseline+current，含 added/removed/attribute_changed/unchanged node 與 added/removed/modified edge），呼 `diff_tool.execute({...,"format":"json"})`，**先斷言現狀**：`node_diffs[0]["diff_state"]` 為 **bare str**（pin 當前契約）。確認 pin 綠（現狀）。
   - **fixture 來源**：照 [[feedback_e2e_fixture_input_only]]——snapshot＝diff 的**輸入**（非結果），可建；diff 結果由 `diff_tool.execute` 真實產、不 hand-build DiffResult。**store-population 範本＝`test_snapshot_store_roundtrip.py:226`（已對 store 內兩 snapshot 跑 diff 並斷言 diff_state——`diff_tool.execute` 走 `store.get_latest()`＋`resolve_baseline(ref)`，需 store 內有 current＋可解析 baseline）**；diff_state 各值觸發邏輯參考 `test_diff_engine.py`。`_invocation_recipes._diff_recipe` 為 error 路徑（無 snapshot）、非 happy-path 範本。
2. **flip（改現狀測為新契約）**：改 pin 斷言為**膜投影**：`node_diffs[0]["diff_state"] == {"value": "...", "position": {"kind":"signal", ...}}`；`edge_diffs[0]["diff_state"]` 同理（contrasts 3-set）。此時測紅（emit 仍 bare）。
3. **green**：改 `diff_tool.py:82,83` 照 spec §3.2（加 import `node_diff_element/edge_diff_element`、node/edge 各走對應 element）。測綠。

**測試斷言重點**：
- node diff_state＝`{value, position(signal, contrasts=5-set, gloss)}`、edge＝`{value, position(signal, contrasts=3-set)}`。
- `summary`（int 直方圖）、`baseline_info`/`current_info`、`node_id`/`from_node`/`to_node` **不變**（spec §3.2：只投影 diff_state）。
- `format=="mermaid"` 分支輸出**不變**（人類面 out；可加一行斷言 mermaid 仍回 str，證投影隔離於 json 分支）。

**gate**：`pytest tests/unit/mcp/ -q` 綠。grep 確認**未動** `report_renderer`/`render_json`（spec §1 out）。`git diff --stat`＝`diff_tool.py`＋測檔。

---

## Task 3 — diff_engine 值域雙向釘樁（C2）＋全測 gate

**交付**：`diff_engine` node/edge diff_state 值域 == 對應 `set(CONTRASTS)` characterization（spec §3.3／§4 C2／§6）＋全測零回歸。

**TDD**：
1. **red/green**：在 `tests/unit/core/diff/test_diff_engine.py` 新增（或彙整既有逐值斷言為）**聯集集合斷言**：
   - **⊆ 側**：對涵蓋全分類的 (baseline,current) L1 fixtures，`{nd.diff_state for nd in result.node_diffs} <= set(NODE_DIFF_CONTRASTS)`、edge 同理 `<= set(EDGE_DIFF_CONTRASTS)`。
   - **⊇ 側（聯集==）**：跨案例聯集 `== set(NODE_DIFF_CONTRASTS)`（**dependency_changed 由 L1 fixture 取得**——spec §3.3：L1.5 不產；既有 `test_diff_engine.py:261` dependency_changed 案例＋added/removed/unchanged/attribute_changed 案例彙整）；edge 聯集 `== set(EDGE_DIFF_CONTRASTS)`（added/removed/modified，`test_diff_engine.py:161/179/198`）。
   - import `NODE_DIFF_CONTRASTS/EDGE_DIFF_CONTRASTS` from `diff_membrane`（雙向釘樁：engine producer ↔ membrane CONTRASTS 任一漂移即紅）。
2. **不改 producer 邏輯**（spec §1 out：`diff_engine` assignment 字面保留；本 task 純加 characterization）。

**gate（末 task 全測）**：
- `cd the_door && PYTHONUTF8=1 python -m pytest -q` ＝**1525＋新測、零回歸**（唯一既有改動＝diff_tool json emit 形狀，由 Task 2 characterization 圈住）。
- 特別回驗：S0 `test_primitive.py`、S1-S5 membrane 測、`test_diff_engine.py`/`test_diff_renderer.py`/`test_graph_view_model*.py`/`report_renderer` 測**全綠且未改**（本刀不碰其 emit）。
- `git diff --stat` 總覽＝`diff_membrane.py`(新)＋`test_diff_membrane.py`(新)＋`diff_tool.py`＋`test_diff_tool.py`(新/改)＋`test_diff_engine.py`(加測)。**無 out 清單檔。**

---

## 完成後（ff-merge）

1. 全測綠 → `git add -A && git commit`（逐 task 或一次，commit message 照慣例 `feat(diff-membrane): ...`／`test(diff-c2): ...`）。
2. ff-merge 回 main（`git checkout main && git merge --ff-only <branch>`）。**不主動 push**（聽使用者）。
3. 更新 handoff memory：S6 merged、下一步＝S7（provenance）spec〔首步 spike provenance 型別＋全 emit 面〕＋並行 report/viewer 面 cut（[F-report-viewer-面 cut]，排程 S8-report）。

---

## 驗收清單（對應 spec §4 不變量）

| # | 驗收 | task | 測 |
|---|---|---|---|
| C1 | node/edge diff_state 值→Signal（對應 contrasts+gloss）、to_json 形狀 | 1 | test_diff_membrane |
| C2 | 兩單一來源、producer 值域**聯集 ==** 對應 set(CONTRASTS)（dependency_changed 自 L1） | 3 | test_diff_engine |
| C3 | LLM-facing emit（diff_tool json）無裸 enum、膜投影；report 面未動（out） | 2 | test_diff_tool＋grep gate |
| C4 | node/edge 正交（contrasts 集 5≠3、共享 {added,removed}）、各自 Signal | 1 | test_diff_membrane |
| 回歸 | S0-S5 全測綠、out 清單未動 | 3 | 全測＋git diff --stat |

**plan 完成 → 待使用者確認 → inline TDD 執行 Task 1→2→3 → ff-merge。**
