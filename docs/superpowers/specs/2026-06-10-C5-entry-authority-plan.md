# C5 plan：強制入口的單一可讀權威（inline TDD）

> 承接 spec `2026-06-10-C5-entry-authority-spec.md`（雙審通過：①目標誠實分層＝first-time
> next-action 一致／incremental prose+deny 兜底；②deny 指回改 MCP-actionable（system_status）；
> ③viewer-surface 排除理由；④after_error boost 測試態須 stamped=True）。
> 執行模式：inline TDD，3 task 依序。環境：pytest cwd 內層 `the_door/`、`PYTHONUTF8=1`、
> `python -m pytest`；commit `git commit -F <repo外檔>`（C4 active）。hook 測為 subprocess 黑箱。

---

## 通則
- C5 純資訊層：不改 gate 強制邏輯（existence/currency/coverage 判定與 exit code 不變），只①修 guidance 權威涵蓋 edge_residue ②deny 多一行指回。
- 不新建靜態 README；不擴 gate 到 snapshot_patch（水平推廣＝下一刀）；不碰 CLAUDE.md。
- **plan 前 grep 全部 `SystemState(` 構造點**，確認新欄位末位預設足以零 churn、僅 boost 相關 2 測試態需顯式 stamped=True。

## Task 1 — StateInspector 感知 edge_residue 蓋章
**測（先紅）**＝`tests/unit/core/guidance/test_state.py`（追加）：
- C5-1 在 tmp 用 `stamp_stage(tmp, STAGE_EDGE_RESIDUE, covered_nodes=["a"], contract_version="1")` 寫 checklist → `StateInspector(tmp).inspect().edge_residue_stamped is True`；無 checklist 的 tmp → `False`；有 `.the-door` 但無 edge_residue stage（只 snapshot_write stage）→ `False`。
**impl**：
- `guidance/state.py`：`SystemState` 末位加 `edge_residue_stamped: bool = False`（帶預設）。
- `StateInspector._inspect_full`：`from the_door.core.checklist import read_checklist, STAGE_EDGE_RESIDUE, FIELD_STAGES`；`cl = read_checklist(self._project_path)`；`stamped = isinstance(cl, dict) and isinstance((cl.get(FIELD_STAGES) or {}).get(STAGE_EDGE_RESIDUE), dict)`；傳入 SystemState。
  - ⚠ `inspect()` 的 early-return（無 `.the-door`）分支也須帶 `edge_residue_stamped=False`（顯式或靠預設；明確傳 False 保險）。
- Verify：`python -m pytest tests/unit/core/guidance/test_state.py tests/contract/test_systemstate_json_contract.py -q`（契約子集測須仍綠）。

## Task 2 — suggester：edge_residue 入鏈
**測（先紅）**＝`tests/unit/core/guidance/test_suggester.py`（追加＋改 2 boost 態）：
- C5-2 state（has_dot_the_door=True, has_structure_json=True, snapshots=(), edge_residue_stamped=**False**）→ `suggest(cli)[0].id == "edge_residue.run"`、`mcp_tool=="edge_residue"`；且**無** `snapshot.write_first`（predicate gated）。
- C5-3 同上但 edge_residue_stamped=**True** → `suggest(cli)[0].id == "snapshot.write_first"`；且無 `edge_residue.run`。
- C5-4 `_rule_first_time` 與 `_rule_incremental` 產出的 action.rationale **含 "edge_residue"**（prose 準確回歸樁）。
- C5-3b **producer↔consumer 接縫 E2E**（走真實 StateInspector，不手構造 SystemState）：tmp 內 `stamp_stage(STAGE_EDGE_RESIDUE,...)` 後 `suggest(StateInspector(tmp).inspect(), "cli")[0].id == "snapshot.write_first"`；另一未蓋章 tmp（有 structure.json、無 snapshot）→ top==`edge_residue.run`。釘住「inspect 寫入欄位 ⟷ suggester 讀欄位」整線。
- **改既有測試態**（spec §4）：`_state_that_triggers("snapshot.write_first")` 分支 + `test_suggester_after_error_no_snapshot_boost` 的 state → 補 `edge_residue_stamped=True`（代表「edge_residue 已跑、回復寫 snapshot」）。改後 C5-5＝既有 boost property 測 `test_property_every_boost_target_reachable_in_after_error_context` 仍綠。
**impl**＝`guidance/suggester.py`：
- 新 `_rule_edge_residue(state, context)` → `NextAction(id="edge_residue.run", title="跑 edge_residue（補雜訊殘餘＋蓋執行 checklist）", rationale="snapshot_write 前置：edge_residue 落盤殘餘並蓋 checklist，gate 才放行。", priority=2, mcp_tool="edge_residue", mcp_arguments={"codebase_path": state.project_path.as_posix()})`。
- `_RULES` 加一列：`(lambda s: s.has_structure_json and not s.snapshots and not s.edge_residue_stamped, ("mcp","after_error"), _rule_edge_residue)`（surfaces 與 sibling snapshot_write_first 一致；agent 走 mcp）。測試用 `context="mcp"`。
- 改 `_rule_snapshot_write_first` 的 predicate 列：`lambda s: s.has_structure_json and not s.snapshots and s.edge_residue_stamped`。
- `_rule_first_time` rationale → 加「…產 L1，跑 edge_residue，再 snapshot_write。」；`_rule_incremental` rationale → 加「…重產，跑 edge_residue，再 snapshot_write(inherit_from)。」
- Verify：`python -m pytest tests/unit/core/guidance/ -q`。

## Task 3 — deny 指回單一權威（c3 hook）
**測（先紅）**＝`tests/unit/hooks/test_execution_gates.py`（追加）：
- C5-6 `run_hook(C3, {"tool_input": {"codebase_path": str(tmp_path)}})`（無 checklist）→ rc==2、stderr 含 `"system_status"`（MCP-actionable 指回）＋仍含 `"edge_residue"`（teach 保留）。
**impl**＝`.claude/hooks/c3_gate_snapshot_write.py`：
- `teach` 字串末補一行：`"（完整鏈與下一步見單一權威：呼叫 system_status 工具，或 the-door status " + codebase_path + "）\n"`。
- 不改三段判定/exit code/既有 teach。
- Verify：`python -m pytest tests/unit/hooks/test_execution_gates.py -q`。

## 最終 Verify（全綠才 ff-merge）
- `python -m pytest -q` 全套 0 failed（含改後 suggester/state/boost/contract）。
- first-time 鏈：未蓋章 → next_actions top＝edge_residue.run；蓋章後 → snapshot.write_first（與 C3 gate 一致）。
- deny（無 checklist）含 system_status 指回 ＋ edge_residue teach。
- production gate 強制邏輯行為不變（existence/currency/coverage 三段＋exit code 不動）。
- `git add -A && git commit -F <repo外msg> && git -C <main> merge --ff-only`（不 push）。更新 MEMORY.md。

## done-state
- [ ] StateInspector.edge_residue_stamped；C5-1 綠；契約子集測綠。
- [ ] suggester edge_residue 入鏈（first-time gated）＋rationale 含 edge_residue；C5-2/3/4 綠；boost 態更新後 C5-5 綠。
- [ ] deny 指回 system_status；C5-6 綠。
- [ ] 全套 0 failed；ff-merge；MEMORY.md 更新。

## 不做（釘樁）
- 不新建靜態 README/checklist 檔；不改 gate 強制邏輯；不擴 gate 到 snapshot_patch（水平推廣）；不為 incremental 加獨立 edge_residue next-action（state 無法精確區分）；不碰 CLAUDE.md prose；不動 viewer surface。
