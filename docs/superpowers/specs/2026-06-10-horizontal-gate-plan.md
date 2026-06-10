# 水平推廣 gate plan：擴 C3 gate 到 snapshot_patch（inline TDD）

> 承接 spec `2026-06-10-horizontal-gate-spec.md`（雙審通過：①gate 統一原則＝gate node-writes，
> snapshot_patch source_nodes-conditional；②tool_name 缺失安全退化＋H-5/H-5c 釘；③repair_drift
> 範圍澄清；④檔名落差以 docstring 註記）。
> 執行模式：inline TDD，3 task。環境：pytest cwd 內層 `the_door/`、`PYTHONUTF8=1`、
> `python -m pytest`；commit `git commit -F <repo外檔>`（C4 active）。hook 測 subprocess 黑箱。

---

## 通則
- 純擴展既有 C3 gate：①`_source_nodes` 加 `source_nodes_by_feature` 來源 ②engage 規則（gate node-writes）③settings 加 matcher ④deny tool-aware ⑤repair_drift rationale prose。
- **不改 snapshot_write 既有 gate 行為**（existence-always/coverage 不動；C2-6..13、C5-6、drift-pin 不回歸）。
- **不 gate 唯讀工具**（diff/analyze_changes/extract/snapshot_create）——守則 #2。
- tool_name 缺失 → 安全退化 existence-always（`data.get("tool_name") or ""`，不 crash）。

## Task 1 — c3 hook：擴 source_nodes 來源 + engage 規則 + tool-aware deny
**測（先紅）**＝`tests/unit/hooks/test_execution_gates.py`（追加；run_hook 既有，H-5/H-5c 需在 payload 帶 tool_name）：
- 先加 helper：`def _patch(payload_extra, codebase_path, tool="snapshot_patch")` → `run_hook(C3, {"tool_name": f"mcp__the-door__{tool}", "tool_input": {"codebase_path": str(codebase_path), **payload_extra}})`。
- H-1 snapshot_patch、無 checklist、`source_nodes_by_feature={"feat-x":["a"]}` → rc2、stderr 提 edge_residue。
- H-2 `stamp_stage(edge_residue, covered=["a","b"])` ＋ `source_nodes_by_feature={"feat-x":["a"]}` → rc0。
- H-3 同上 ＋ `{"feat-x":["a","zzz"]}` → rc2、stderr 含 coverage/涵蓋；**且 stderr 含 `snapshot_patch`**（釘 coverage-deny 路徑也用 tool-aware 標籤，與 H-6 共同覆蓋三段標籤一致）。
- H-4 checklist contract_version="0" ＋ `{"feat-x":["a"]}` → rc2。
- H-5 snapshot_patch、**無 checklist**、payload 只 `feature_metadata_by_feature={"feat-x":{"trigger_description":"t"}}`（無 source_nodes_by_feature）、**帶 tool_name** → rc0（非 node-write、不 engage）。
- H-5b snapshot_patch、無 checklist、`source_nodes_by_feature={}`（空）、帶 tool_name → rc0。
- H-5c snapshot_patch metadata-only payload 但 event **不帶 tool_name** → rc2（安全退化 existence-always）。
- H-6 deny 訊息含短名 `snapshot_patch`（帶 tool_name、無 checklist 觸 deny）。
**impl**＝`.claude/hooks/c3_gate_snapshot_write.py`：
- docstring 更新：明述 gate **snapshot_write 與 snapshot_patch** 兩條 source_nodes 寫入路。
- `_source_nodes(tool_input)`：保留 l1_features/updated_features；新增 flatten `source_nodes_by_feature`（dict，值 list）。
- `main()`：`tool_name = data.get("tool_name") or ""`；`tool_short = tool_name.rsplit("__", 1)[-1]`；`src = _source_nodes(tool_input)`；`engage = (tool_short != "snapshot_patch") or bool(src)`；若 **not engage** → `return 0`（snapshot_patch 非 node-write、豁免）。
- deny 主詞：用 `tool_short or "snapshot 寫入"` 取代硬編 `snapshot_write`（三段 deny 訊息）。existence/currency/coverage 三段邏輯、exit code、fail-open、C5 system_status 指回不變。
- Verify：`python -m pytest tests/unit/hooks/test_execution_gates.py -q`（含 H-7 回歸＝既有 C2-6..13、C5-6、drift-pin 全綠）。

## Task 2 — settings.json 註冊 snapshot_patch matcher
**測（先紅）**＝`tests/unit/hooks/test_execution_gates.py`：
- H-8 settings.json PreToolUse 有 matcher `mcp__the-door__snapshot_patch` 指向 c3 hook command；既有 `mcp__the-door__snapshot_write` matcher 仍在（既有 `test_settings_registers_c3_c4` 不回歸）。
**impl**＝`.claude/settings.json`：PreToolUse 加一條，matcher `mcp__the-door__snapshot_patch`，command 與既有 snapshot_write 條目同形（守衛式 python 指向 `c3_gate_snapshot_write.py`）。
- Verify：`python -m pytest tests/unit/hooks/test_execution_gates.py -q`。

## Task 3 — repair_drift guidance 同步
**測（先紅）**＝`tests/unit/core/guidance/test_suggester.py`：
- H-9 `_rule_repair_drift` 產出 action.rationale 含 `"edge_residue"`（state 帶 source_nodes_drift warning，context="cli"）。
**impl**＝`guidance/suggester.py`：`_rule_repair_drift` rationale 補 edge_residue（「重跑 extract、跑 edge_residue，再用 snapshot_patch 補 source_nodes」）。不改 cli_command。
- Verify：`python -m pytest tests/unit/core/guidance/test_suggester.py -q`。

## 最終 Verify（全綠才 ff-merge）
- `python -m pytest -q` 全套 0 failed（含 H-1..H-9＋既有 C2/C3/C5/drift-pin 回歸）。
- snapshot_patch：無 checklist／coverage 不足／version 過期＋有 source_nodes → deny；合法（蓋章+covered）→ allow；metadata-only（帶 tool_name）→ allow；tool_name 缺失 → 安全退化 deny。
- snapshot_write 路徑零變（C2-6..13、C5-6、drift-pin 全綠）。
- 唯讀工具未被加 gate。
- `git add -A && git commit -F <repo外msg> && git -C <main> merge --ff-only`（不 push）。更新 MEMORY.md。

## done-state
- [ ] c3 hook：source_nodes_by_feature 來源＋engage 規則＋tool-aware deny＋安全退化；H-1..H-6 綠；H-7 回歸綠。
- [ ] settings 加 snapshot_patch matcher；H-8 綠。
- [ ] repair_drift rationale 含 edge_residue；H-9 綠。
- [ ] 全套 0 failed；ff-merge；MEMORY.md 更新。

## 不做（釘樁）
- 不 gate diff/analyze_changes/extract/snapshot_create（守則 #2）；不另寫新 hook；不改 snapshot_write 既有 gate；不改 checklist 欄位常數（drift-pin 不動）；不做 staleness/completeness；不重命名 hook 檔。
