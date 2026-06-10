# C6 plan：跑完彙整回報使用者（inline TDD）

> 承接 spec `2026-06-10-C6-chain-report-spec.md`（雙審通過：①fail-soft 回傳 ledger 用記憶體事實補本關、
> 不與 payload 自相矛盾；②`except OSError` 不遮簽章 bug；③read_ledger 非破壞移除＋details 保留鍵約束；
> ④軸3 誠實邊界；⑤軸5 副作用污染——plan 前已查實：全 snapshot_write 測跑 tmp、無精確鍵集斷言）。
> 執行模式：inline TDD，3 task 依序；每 task 先寫測（紅）→ impl（綠）。最後全套＋護欄全綠才 ff-merge。
> 環境：pytest cwd 內層 `the_door/`、`PYTHONUTF8=1`、一律 `python -m pytest`；commit 用 `git commit -F`（C4 active）。

---

## 通則
- C6 純資訊層：**不加 hook、不加 gate、不改 C3/C4/edge_residue 既有蓋章**（spec §2 非目標）。
- ledger 投影排除 covered_nodes 陣列（只 node_count）；details 保留鍵約束（`stage`/`stamped_at`/`node_count`/`covered_nodes` 不得用）。
- snapshot_write 蓋章 fail-soft（`except OSError`）；回傳 ledger 靠記憶體事實保證不漏報本關。
- **已查實（plan 前 spike）**：`test_snapshot_write_checkpoint_e2e`(tmp_path fixture)/`test_incremental_source_nodes`(tmp_path)/`test_mcp_flow_guard`(tmp_path)/`test_v105_incremental_flow`(v105_fixture=tmp_path) 全跑 tmp；無對 snapshot_write payload 做精確鍵集斷言 → 新副作用＋新鍵皆安全。

## Task 1 — `core/checklist.py`：stamp_stage 擴充 ＋ read_ledger
**測（先紅）**＝`tests/unit/core/test_checklist.py`（既有檔追加）：
- C6-1 `stamp_stage(tmp, STAGE_SNAPSHOT_WRITE, contract_version="1", details={"version_id":"v","feature_count":3})`（**不傳 covered_nodes**）→ `stages.snapshot_write` 含 `stamped_at`＋`version_id`＋`feature_count`，**不含** `node_count`/`covered_nodes`。
- C6-2 回歸：`stamp_stage(tmp, STAGE_EDGE_RESIDUE, covered_nodes=["b","a"], contract_version="1")`（既有用法）行為不變——仍寫 `covered_nodes==["a","b"]`、`node_count==2`。
- C6-3 `read_ledger(缺檔)` → `[]`；`read_ledger(壞 json)` → `[]`。
- C6-4 先 `stamp_stage(edge_residue, covered_nodes=["x","y"])` ＋ `stamp_stage(snapshot_write, details={...})` → `read_ledger` 回 list 長度 2、順序 `[edge_residue, snapshot_write]`（STAGE_ORDER）、每項含 `stage` 名、**edge_residue 項無 `covered_nodes` 鍵但有 `node_count`**、snapshot_write 項投影不 KeyError（非破壞移除驗證）。
- C6-5 額外 `stamp_stage("future_stage", covered_nodes=[])` → `read_ledger` 把 `future_stage` 排在 `[edge_residue, snapshot_write]` 之後（未知 stage 字母序附後、向前相容）。
**impl**＝`src/the_door/core/checklist.py`：
- 新常數：`STAGE_SNAPSHOT_WRITE = "snapshot_write"`；`STAGE_ORDER = (STAGE_EDGE_RESIDUE, STAGE_SNAPSHOT_WRITE)`。
- `stamp_stage(codebase_path, stage, *, contract_version, covered_nodes=None, details=None)`：
  - `entry = {FIELD_STAMPED_AT: now}`；`if covered_nodes is not None:` 寫 `node_count`/`covered_nodes`（排序去重，沿用既有邏輯）；`if details: entry.update(details)`。
  - 其餘（load-or-init、寫回、contract_version 覆寫）不變。
- `read_ledger(codebase_path) -> list[dict]`：`data = read_checklist(...)`；None→`[]`；取 `stages` dict；排序鍵＝`STAGE_ORDER` 內者依序、其餘 `sorted()` 附後；每 stage：`e = dict(stage_dict); e.pop(FIELD_COVERED_NODES, None); e["stage"] = name`（**`stage` 鍵最後塞，details 保留鍵約束保證不覆蓋**）；append。
- 模組 docstring 補一句：含讀取側投影 `read_ledger`（供 C6 回報）。
- Verify：`python -m pytest tests/unit/core/test_checklist.py -q`。

## Task 2 — `snapshot_write_tool`：蓋章 ＋ 嵌 ledger（fail-soft）
**測（先紅）**＝`tests/unit/mcp/tools/test_snapshot_write_tool.py`（**新建**；direct 模式、tmp_path）：
- C6-6 先 `stamp_stage(tmp, STAGE_EDGE_RESIDUE, covered_nodes=[...], contract_version=...)`（模擬 edge_residue 已跑，使 ledger 有前關）→ `await execute({"codebase_path":tmp, "l1_features":[{feature_id,label,description,confidence,source_nodes}], "label":"v1"})` → ①payload 含 `execution_ledger`；②ledger 內有 `stage=="snapshot_write"` 項（`version_id`==payload version_id、`feature_count`==1）；③`read_checklist(tmp).stages` 確實落了 `snapshot_write` stage。
- C6-7 **磁碟蓋章失敗**：`monkeypatch.setattr("the_door.mcp.tools.snapshot_write_tool.stamp_stage", lambda *a,**k:(_ for _ in ()).throw(OSError("disk")))` → `execute(...)` ①**仍回 snapshot 結果**（`result["version_id"]` 在、無 `error`）；②`execution_ledger` **仍含 `snapshot_write` 項**（記憶體補回、version_id 一致）——第一輪審 warning 回歸樁。
  - 註：patch **匯入端 ref**（snapshot_write_tool.stamp_stage），非 core.checklist。
- C6-7b **負向樁（防 except 寬化回歸；第二輪審 warning）**：`monkeypatch` stamp_stage 拋 **`TypeError`**（模擬簽章/邏輯 bug）→ `with pytest.raises(TypeError): await execute(...)`——驗 `except OSError` 只吞 I/O、**不遮簽章 bug**。若有人把 except 改寬成 `Exception`，此測轉紅。
**impl**＝`src/the_door/mcp/tools/snapshot_write_tool.py`：
- import：`from the_door.core.checklist import STAGE_SNAPSHOT_WRITE, read_ledger, stamp_stage`；`from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION`。
- `create_snapshot(...)` 後、build payload 處：組 `sw_details = {"version_id":..., "label":..., "feature_count":len(l1_snapshot), "relation_count":len(relations)}`；`try: stamp_stage(codebase_path, STAGE_SNAPSHOT_WRITE, contract_version=SNAPSHOT_CONTRACT_VERSION, details=sw_details) except OSError: pass`。
- module-level helper `_ledger_with_snapshot_write(codebase_path, sw_details)`：`led = read_ledger(codebase_path); if not any(e["stage"]==STAGE_SNAPSHOT_WRITE for e in led): led.append({"stage":STAGE_SNAPSHOT_WRITE, **sw_details}); return led`。
- `payload["execution_ledger"] = _ledger_with_snapshot_write(codebase_path, sw_details)`（在現有 `if warnings:` 與 `return wrap(...)` 之間；只在成功路徑）。
- Verify：`python -m pytest tests/unit/mcp/tools/test_snapshot_write_tool.py -q`。

## Task 3 — 整鏈 E2E ＋ 回歸掃描
**測（先紅）**＝`tests/unit/mcp/tools/test_snapshot_write_tool.py` 追加（input-only fixture→copytree tmp，守 fixture-input-only）：
- C6-8 用 `python_simple` fixture copytree→tmp：`await edge_residue_tool.execute({codebase_path})` → 再 `await snapshot_write_tool.execute({codebase_path, l1_features:[...真實 node 的 source_nodes 子集...]})` → `execution_ledger` 長度==2、`[0].stage=="edge_residue"`、`[1].stage=="snapshot_write"`、**任一項都無 `covered_nodes` 鍵**（投影剝除驗證）、edge_residue 項有 `node_count>0`。
  - source_nodes 取 `edge_residue` 後 checklist 的 covered 子集（保證過 coverage 語義；本測不經 hook，但取真實 node 維持誠實）。
**回歸**：
- C6-9 跑既有 `tests/unit/hooks/test_execution_gates.py`＋`tests/unit/core/test_checklist.py`＋`tests/unit/mcp/tools/test_edge_residue_tool.py` 全綠（snapshot_write stage 與新簽章不破壞 C2/C3）。
- 跑既有 snapshot_write 整合測（`tests/integration/test_snapshot_write_checkpoint_e2e.py`、`test_incremental_source_nodes.py`、`test_mcp_flow_guard.py`、`tests/scenario/test_v105_incremental_flow.py`）全綠（新 `execution_ledger` 鍵＝純加法、副作用跑 tmp）。
- Verify：`python -m pytest -q`（全套 0 failed）。

## 最終 Verify（全綠才 ff-merge）
- `python -m pytest -q` 全套 0 failed。
- 真實 codebase 跑 `edge_residue → snapshot_write` → snapshot_write 回應 `execution_ledger` 含兩 stage、無 covered_nodes 灌爆（spec §6 護欄；以 C6-8 E2E 驗）。
- production hook diff 空（無新增/改 hook）。
- `git add -A && git commit -F <repo外msg檔> && git -C <main> merge --ff-only`（不 push）。更新 MEMORY.md。

## done-state
- [ ] checklist.py：stamp_stage 加 details/covered_nodes-optional＋read_ledger；C6-1..C6-5 綠；既有 C2-1..C2-4 回歸綠。
- [ ] snapshot_write 蓋章 fail-soft（except OSError）＋嵌 ledger（記憶體補本關）；C6-6/C6-7/C6-7b 綠（含非-OSError 傳播負向樁）。
- [ ] 整鏈 E2E C6-8 綠；C2/C3/edge_residue＋snapshot_write 整合測全綠回歸。
- [ ] 全套 0 failed；ff-merge；MEMORY.md 更新。

## 不做（釘樁）
- 不加 PostToolUse hook／任何 gate；不擴 system_status／不新增 report 工具；不碰 C3/C4/C5；不在 ledger 投影 covered_nodes 全陣列；不做 staleness/新鮮度判定；不渲染人類最終文字（agent 轉述）。
