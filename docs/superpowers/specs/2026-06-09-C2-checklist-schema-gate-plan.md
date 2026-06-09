# C2 plan：checklist schema gate（inline TDD）

> 承接 spec `2026-06-09-C2-checklist-schema-gate-spec.md`（雙審通過：node_id 同一性已驗、
> currency 涵蓋誠實縮小、validity 讀法界定、drift-pin 機制具體化、stamp 失敗模式）。
> 執行模式：inline TDD，4 task 依序；每 task 先寫測（紅）→ impl（綠）。最後全套＋護欄全綠才 ff-merge。
> 環境：pytest cwd 內層 `the_door/`、`PYTHONUTF8=1`；commit 用 `git commit -F`（C4 active）。
> ⚠ hook 測為 subprocess 黑箱（比照 `tests/unit/hooks/test_execution_gates.py`）。

---

## 通則
- C2 不碰 C4、不碰 edge-residue.json 既有結構、不擴展到其他 gate（spec 非目標）。
- hook stdlib-only 自足（不 import the_door）；生產側單一來源＝`core/checklist.py`；兩端以釘樁測對齊。
- 既有 `test_execution_gates.py` 的 C3 測（驗 edge-residue.json 存在性）語義已變→**改**為 checklist 語義（非新增）。

## Task 1 — `core/checklist.py` 模組（單一真相來源・寫入側）
**測（先紅）**＝`tests/unit/core/test_checklist.py`：
- C2-1 `stamp_stage(tmp, STAGE_EDGE_RESIDUE, covered_nodes=["b","a","a"], contract_version="1")` → 檔生成；`stages.edge_residue` 含 `covered_nodes==["a","b"]`（排序去重）、`node_count==2`、`contract_version=="1"`、`stamped_at` 為 UTC ISO（`Z`/`+00:00` 結尾、可 `datetime.fromisoformat` 解析）。
- C2-2 對既有檔再 `stamp_stage(tmp, "other_stage", covered_nodes=[], contract_version="1")` → `edge_residue` stage 仍在、`other_stage` 新增；contract_version 覆寫為最新。
- C2-3 `read_checklist(缺檔)` → None；`read_checklist(壞 json)` → None。
- C2-4 covered_nodes 去重＋排序穩定（重跑同輸入 → 同輸出）。
**impl**：
- 新檔 `src/the_door/core/checklist.py`：常數 `CHECKLIST_FILENAME="checklist.json"`、`STAGE_EDGE_RESIDUE="edge_residue"`、欄位名常數 `FIELD_CONTRACT_VERSION="contract_version"`/`FIELD_STAGES="stages"`/`FIELD_COVERED_NODES="covered_nodes"`/`FIELD_NODE_COUNT="node_count"`/`FIELD_STAMPED_AT="stamped_at"`。
- `checklist_path(codebase_path)`、`read_checklist()`（壞檔→None）、`stamp_stage(codebase_path, stage, *, covered_nodes, contract_version)`（load-or-init→set stage→write，covered_nodes 排序去重，stamped_at=`datetime.now(timezone.utc).isoformat()`）。
- Verify：`python -m pytest tests/unit/core/test_checklist.py -q`。

## Task 2 — `edge_residue` 工具蓋章
**測（先紅）**＝`tests/unit/mcp/test_edge_residue_tool.py`（既有檔追加，**若不存在則新建同名**；E2E copytree fixture→tmp，守 fixture-input-only）：
- C2-5 `await execute({"codebase_path": tmp})` 後：`checklist.json` 存在、`stages.edge_residue.covered_nodes == sorted({n.node_id for n in ASTExtractor().extract(tmp).nodes})`、`contract_version=="1"`；回傳 payload 含 `checklist_path`。
- C2-5b（失敗模式）：`monkeypatch.setattr("the_door.mcp.tools.edge_residue_tool.stamp_stage", raising_fn)`（patch **匯入端 ref**，非 core.checklist）→ `execute` 回 error envelope（含「checklist」字樣），不靜默成功。
**impl**：
- `edge_residue_tool.execute()` 末端：`covered = sorted({n.node_id for n in extraction.nodes})`；`try: stamp_stage(codebase_path, STAGE_EDGE_RESIDUE, covered_nodes=covered, contract_version=SNAPSHOT_CONTRACT_VERSION)` 失敗則回 `{"error": "checklist stamp failed: ..."}`（或既有 error 風格）；payload 加 `checklist_path`。
- import：`from the_door.core.checklist import stamp_stage, STAGE_EDGE_RESIDUE, checklist_path`；`from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION`。
- Verify：`python -m pytest tests/unit/mcp/test_edge_residue_tool.py -q`。

## Task 3 — C3 hook 升級（讀 checklist：existence＋currency＋coverage）
**測（先紅／改）**＝`tests/unit/hooks/test_execution_gates.py`（C3 段改寫＋新增 C2-6..C2-13；run_hook 既有）：
- C2-6 無 checklist → rc2、stderr 含 `edge_residue`。
- C2-7 **用 `stamp_stage` 寫真實 checklist**（covered=["a","b"]）＋ tool_input source_nodes=["a"] → rc0。
- C2-8 covered=["a"]、source_nodes=["a","zzz"] → rc2、stderr 含 coverage/變動字樣。
- C2-9 checklist contract_version="0" → rc2。
- C2-10 updated_features[].source_nodes 含未涵蓋 node → rc2（驗 updated_features 也納入）。
- C2-11 **先 `stamp_stage` 寫好 edge_residue 關**（隔離 existence，否則會在 existence 就 deny、測不到真空 coverage）；tool_input source_nodes 全空（l1_features 無 source_nodes / inherit-only）→ rc0。
- C2-12 壞 checklist json → rc2。
- C2-13 stdin 非 json → rc0；無 codebase_path → rc0（fail-open）。
- （既有 `test_c3_artifact_present_allows`/`test_c3_artifact_missing_denies` 改成 checklist 語義或移除——避免殘留驗舊 edge-residue.json 存在性的測。）
**impl**：改寫 `.claude/hooks/c3_gate_snapshot_write.py`（stdlib-only）：
- 讀 `<codebase>/.the-door/checklist.json`；解析失敗或缺→deny（提 edge_residue）。
- `stages.edge_residue` 缺→deny。
- `contract_version != "1"`→deny（版本過期，重跑 edge_residue）。
- 蒐集 `tool_input.l1_features[].source_nodes` ∪ `tool_input.updated_features[].source_nodes`；`missing = [n for n in src if n not in set(covered)]`；非空→deny（列前 5 個 missing）。
- 全過→exit 0；stdin/ codebase_path 缺→exit 0（fail-open，與舊一致）。
- docstring 更新（移除「existence check only」舊註，改述 checklist＋coverage＋currency；deferred＝刪除/原地改 staleness）。
- Verify：`python -m pytest tests/unit/hooks/test_execution_gates.py -q`。

## Task 4 — 釘樁＋settings 不回歸
**測（先紅）**＝`tests/unit/hooks/test_execution_gates.py` 追加：
- C2-14 讀 hook 檔文字，assert `'"1"'`/`"1"` 當前版本字串在內，且 `== SNAPSHOT_CONTRACT_VERSION`（import 比對）。
- C2-15 讀 hook 檔文字，assert `core/checklist.py` 每個欄位常數值（CHECKLIST_FILENAME/FIELD_STAGES/STAGE_EDGE_RESIDUE/FIELD_COVERED_NODES/FIELD_CONTRACT_VERSION）字串都出現；**負向**：對一個假常數值 `"__nonexistent_field__"` 斷言不在 hook（證釘樁非恆綠）。
- C2-16 settings.json PreToolUse 仍有 matcher `mcp__the-door__snapshot_write` 指向 c3 hook（既有 G-9 不回歸）。
**impl**：無生產碼（純測）；若 C2-14/15 紅，回頭調 hook 字串使對齊。
- Verify：`python -m pytest tests/unit/hooks/ -q`。

## 最終 Verify（全綠才 ff-merge）
- `python -m pytest -q` 全套 0 failed（含改寫後 C3 段）。
- 真實 codebase 跑 `edge_residue` → `.the-door/checklist.json` 生成、covered_nodes 非空（spec §5 護欄；以既有 E2E fixture 驗）。
- hook：無 checklist/coverage 不足/version 過期皆 deny；合法 allow；fail-open 保留。
- `git add -A && git commit -F <msg> && git -C <main> merge --ff-only`（不 push）。更新 MEMORY.md。

## done-state
- [ ] `core/checklist.py` 單源寫入＋read；4 單元測綠。
- [ ] edge_residue 蓋章＋失敗回 error；E2E 綠。
- [ ] C3 hook 讀 checklist＋coverage/currency；C2-6..C2-13 綠；舊存在性測已改。
- [ ] 釘樁（含負向）＋settings 不回歸綠。
- [ ] 全套 0 failed；ff-merge；MEMORY.md 更新。

## 不做（釘樁）
- 不做 mtime/內容 staleness（刪除/原地改偵測）；不做 completeness coverage；不擴展其他 gate；不碰 C4/C5/C6；不改 edge-residue.json 結構。
