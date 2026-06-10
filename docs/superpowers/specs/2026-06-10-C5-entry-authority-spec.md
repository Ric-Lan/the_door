# C5 spec：強制入口的單一可讀權威（丙案 軌2 階段2）

> 承接：種子 `2026-06-08-execution-model-control-via-structure-seed.md` 支柱⑤（§101-109）、
> §10.6 表（skill/README＝deny 指回的單一可讀權威，層級＝資訊）、§10.7 表（C5：強制入口
> per-version README，依賴 C2/C3）、§10.7.2 階段2。
> 承接 C2/C3/C6（已 merged）：C3 gate 在 snapshot_write 前要求 edge_residue 已蓋章。
>
> **核心洞察（spike 實證，§1）**：The Door 的「單一可讀權威」已存在＝**工具自動生成的 guidance**
> （`StateInspector` + `NextActionSuggester`，經 `_response_envelope.wrap` 注入每個工具回應的
> `next_actions`，並由 `the-door status` 印出 `Next:` 區塊）。**但該權威目前漏掉 `edge_residue`
> 關卡**：`suggester` 在「有 structure、無 snapshot」時直接建議 `snapshot_write`，agent 照走即被
> C3 gate deny。**C5 = 把這個自動生成的權威修正成與 gate 一致（涵蓋 edge_residue），並讓 gate 的
> deny 訊息指回該權威。** 不新建靜態 README（§155 明文：手寫 per-version checklist＝多開漂移點、
> 應由工具自動生成；既有 guidance 正是工具自動生成）。

---

## 1. spike（已對真實碼驗，事實寫入；不需事後再驗）

| 事實 | 來源 file:line | 對設計的影響 |
|---|---|---|
| 「單一權威」已存在且工具自動生成＝`StateInspector`+`NextActionSuggester`，`wrap()` 注入每個工具回應的 `next_actions`，`the-door status`/`system_status` 印 | `guidance/state.py`、`guidance/suggester.py`、`mcp/tools/_response_envelope.py:35-37`、`system_status_tool.py:87-90` | C5 修這個既有權威、不新建靜態 README（避免 §155 漂移點） |
| 🔴 **權威與 gate 矛盾**：`_rule_snapshot_write_first`（predicate `has_structure_json and not snapshots`）直接建議 `snapshot_write`，**漏 edge_residue**；`_rule_first_time` rationale 也只寫「extract→產 L1→snapshot_write」 | `suggester.py:20-24,11-17,97` | 照 `next_actions` 走＝extract→snapshot_write→**被 C3 deny**。C5 補 edge_residue 關 |
| C3 gate 要求 snapshot_write 前 checklist 有 edge_residue 蓋章 | `.claude/hooks/c3_gate_snapshot_write.py:86-91` | 權威必須把 edge_residue 列為 snapshot_write 的前置 |
| checklist 蓋章 = `edge_residue` MCP 工具完成時寫 `.the-door/checklist.json` stages.edge_residue | `core/checklist.py:stamp_stage`、`edge_residue_tool.py:58-66` | StateInspector 可讀 checklist 判斷 edge_residue 是否已跑 |
| `SystemState` 是 frozen dataclass、欄位皆無預設 | `guidance/state.py:18-25` | 新欄位用**末位帶預設值** `edge_residue_stamped: bool = False` → 既有 constructor（皆 keyword、不傳此欄）零 churn |
| SystemState JSON 契約測＝**子集檢查**（`required_keys - produced == set()`），非精確等值 | `tests/contract/test_systemstate_json_contract.py:23-28` | `to_json_dict` 多一鍵**不破壞**契約測（subset 仍滿足） |
| `_rule_snapshot_write_first` 被 after_error boost（`no_snapshot_for_baseline`）引用；property 測 `_state_that_triggers` 構造其觸發態 | `suggester.py:111-113`、`test_suggester.py:133-189` | 若改其 predicate 需同步該 2 個測試態（設 `edge_residue_stamped=True`） |
| `core/checklist.py` 僅依賴 json/datetime/pathlib | `core/checklist.py` | StateInspector import `read_checklist` **無循環 import**（guidance 已 import core.diff） |
| deny 訊息（c3 hook）目前內嵌 actionable teach（「請先呼叫 edge_residue…」），**未指回單一權威** | `c3_gate_snapshot_write.py:73-76` | C5 在 deny 末補一行指回 `the-door status`（單一權威），teach 仍保留 |
| hook stdlib-only、cp950-safe（`stderr.buffer`）、fail-open | C3+C4 spec | deny 指回只是**靜態文字指標**（hook 不執行 status）；沿用既有寫法 |

### spike 校正（種子文字 → 真實可行）
- 種子寫「per-version README（靜態檔）」。**校正為「修正既有工具自動生成的 guidance 權威 ＋ deny 指回它」**，理由：
  1. §155 明文反對手寫 per-version checklist（多開漂移點）＝**靜態 README 本身就是漂移點**。既有 guidance 是工具自動生成（StateInspector 即時讀真實 `.the-door/` 狀態）＝零漂移、per-current-state。
  2. §109 守則：「強制力在 hook 的 state-gate，README 只是 gate 指回的可讀權威」。既有 guidance＋`the-door status` 完全勝任「可讀權威」角色，且已被 `wrap()` 注入每個回應。
  3. 真正的缺陷不是「缺一份 README」，而是「**現有權威漏掉 edge_residue 關、與 gate 矛盾**」。修這個矛盾才是 C5 的實質價值。

---

## 2. 目標與非目標

**目標**（誠實分層——first-time 與 incremental 兌現程度不同，見下）：
1. **權威涵蓋 edge_residue**：`StateInspector` 感知 edge_residue 是否已蓋章；`suggester` 把 snapshot_write 鏈的前置 edge_residue 顯式化。
   - **first-time 鏈（next-action 層一致）**：可由 `has_structure_json and not snapshots and not edge_residue_stamped` 精確偵測 → 顯式 next-action `edge_residue.run`。**機械跟隨 `next_actions[0]` 也不撞 deny。**
   - **incremental 鏈（prose 層準確 ＋ deny 兜底）**：state 無法區分「正在分析新版本、edge_residue 未跑」與「無事進行中」（§2 非目標）→ edge_residue **僅以 rationale prose 明示**。機械式只跟隨 `next_actions[0].mcp_tool`（analyze_changes→snapshot_write(inherit)）的 agent **仍可能撞 C3 deny**；此為**已接受的殘餘**——deny 會即時教 edge_residue（§1「deny＝re-force」），非宣稱完全消除。
2. **deny 指回單一權威**：C3 gate 的 deny 訊息末補一行指回單一可讀權威，形式對**當下 MCP agent 可直接執行**：`system_status`（MCP 工具）／`the-door status <path>`（CLI）。actionable teach 保留。

**非目標（釘樁，防 gold-plating）**：
- ❌ **不新建靜態 README/checklist 檔**（§155 漂移點；既有 guidance＝工具自動生成的權威已足）。
- ❌ **不改 gate 的強制邏輯**（C5 是資訊層；強制力 100% 仍在既有 deny gate，守 §10.6 守則 1）。deny 只增一行指標、不改 existence/currency/coverage 判定。
- ❌ **不為 incremental 鏈新增獨立 edge_residue next-action**：state 模型無法區分「baseline 已在、正在分析新版本、edge_residue 未跑」與「baseline 已在、無事進行中」（兩者 `len(snapshots)>=1` 同態）。incremental 的 edge_residue **僅以 rationale 文字明示**（prose 準確），不臆造 state（避免無依據新增）。first-time 鏈（可由 `has_structure_json and not snapshots and not edge_residue_stamped` 精確偵測）才給顯式 next-action。
- ❌ **不擴 gate 到 snapshot_patch**（那是水平推廣，緊接下一刀；C5 先把權威修對，水平推廣才不與權威矛盾）。
- ❌ **不碰 CLAUDE.md prose 整併**（CLAUDE.md 已正確描述 edge_residue 鏈；本刀只修漂移的那一端＝guidance）。

---

## 3. 設計

### 3.1 `SystemState` + `StateInspector`：感知 edge_residue 蓋章
- `SystemState` 末位加 `edge_residue_stamped: bool = False`（帶預設＝既有 constructor 零 churn）。
- `StateInspector._inspect_full`：讀 `core.checklist.read_checklist(project_path)`；`stages.edge_residue` 為 dict → `edge_residue_stamped=True`。fail-soft（無 checklist/壞檔→False，沿用 read_checklist 的 None）。
- `to_json_dict` 自動含新欄位（contract 子集測不破）。

### 3.2 `suggester`：edge_residue 入鏈
- 新 `_rule_edge_residue`（priority 2，surfaces＝`("mcp","after_error")`——**與其 sibling `_rule_snapshot_write_first` 的既有 surfaces 一致**（agent 走 mcp；spike 校正：原 snapshot_write_first 不在 cli，edge_residue 平行之，不擴動既有規則 surface；viewer 亦不含＝headless 無法呼叫）：
  predicate＝`has_structure_json and not snapshots and not edge_residue_stamped` →
  `NextAction(id="edge_residue.run", title="跑 edge_residue（補雜訊殘餘＋蓋執行 checklist）",
  rationale="snapshot_write 前置：edge_residue 落盤殘餘並蓋 checklist，gate 才放行。",
  priority=2, mcp_tool="edge_residue", mcp_arguments={"codebase_path": ...})`。
- `_rule_snapshot_write_first` predicate 改 `has_structure_json and not snapshots and **edge_residue_stamped**`
  （只在 edge_residue 已跑後才建議 snapshot_write）→ 與 `_rule_edge_residue` 互斥，鏈不歧義。
- rationale 修正（prose 準確，涵蓋 edge_residue）：
  - `_rule_first_time`：「…用 extract_structure 抽結構，由 agent 產 L1，**跑 edge_residue**，再 snapshot_write。」
  - `_rule_incremental`：「…用 analyze_changes 取受影響功能，由 agent 重產，**跑 edge_residue**，再 snapshot_write(inherit_from)。」

### 3.3 deny 指回單一權威（c3 hook）
- `teach` 字串末補一行，指回的權威形式對**當下 agent 可執行**（被 gate 的 snapshot_write 是 MCP 工具⟹agent 在 MCP 面）：
  `"（完整鏈與下一步見單一權威：呼叫 system_status 工具，或 the-door status " + codebase_path + "）\n"`。
- 不改 existence/currency/coverage 三段判定與 exit code；deny 僅多一行可讀指標。

---

## 4. 向後相容 / 遷移
- `edge_residue_stamped` 末位帶預設 → 既有 SystemState 構造（CLI/MCP/viewer/測試）皆不傳此欄、預設 False，行為等同「未蓋章」。
- 既有 dogfood／專案無 checklist → `edge_residue_stamped=False` → first-time 路徑會先建議 edge_residue（正確，符合 gate）。
- after_error boost（`no_snapshot_for_baseline`→snapshot.write_first）：因 snapshot_write_first 改 gate on stamped，受影響的 2 個測試態（`_state_that_triggers` 的 snapshot.write_first 分支、`test_suggester_after_error_no_snapshot_boost`）需設 `edge_residue_stamped=True`（代表「edge_residue 已跑、正回復寫 snapshot」的真實態）——plan 列為改動。

## 5. 測試（spec 層；plan 細分 task）

**StateInspector（單元）**：
- C5-1 `.the-door/checklist.json` 有 edge_residue 蓋章 → `inspect().edge_residue_stamped is True`；無 checklist／無該 stage → False。

**suggester（單元）**：
- C5-2 state＝has_structure、no snapshot、**未蓋章** → top action `edge_residue.run`（mcp_tool=="edge_residue"）；snapshot.write_first **不在**列（predicate gated）。
- C5-3 state＝has_structure、no snapshot、**已蓋章** → top action `snapshot.write_first`（mcp_tool=="snapshot_write"）；edge_residue.run 不在列。
- C5-4 `_rule_first_time` / `_rule_incremental` rationale **含 "edge_residue"**（prose 準確回歸樁）。
- C5-5 既有 boost property 測（`no_snapshot_for_baseline`→snapshot.write_first）在更新後測試態（stamped=True）下仍綠。

**deny 指回（hook 黑箱 subprocess）**：
- C5-6 無 checklist → deny(rc2)，stderr 含 `system_status`（MCP-actionable 指回單一權威）＋仍含 `edge_residue`（teach 保留）。

**回歸**：
- C5-7 既有 suggester/state/contract 測全綠（新欄位末位預設＋契約子集）。

## 6. 終局護欄
- Python 全套 0 failed；新測 C5-1..C5-6 綠。
- 照 `next_actions`／`the-door status` 走 first-time 鏈＝extract → **edge_residue** → snapshot_write（與 C3 gate 一致、不再撞 deny）。
- deny 訊息指回 `the-door status`（單一權威）。
- 既有 guidance/state/contract/boost 測全綠（向後相容）。
- 無新建靜態 README；gate 強制邏輯（existence/currency/coverage）行為不變。

## 7. Forward-coherence（against 水平推廣＝緊接下一刀）
- 水平推廣對 `snapshot_patch` 加 gate 後，**repair-drift 流程**（`_rule_repair_drift`：補 source_nodes）也需先 edge_residue。本刀 C5 已把「edge_residue 為 source_nodes 寫入前置」的權威骨架立好；水平推廣那刀再把 repair-drift rationale 同步成「edge_residue → snapshot_patch」，與其 gate 一起落（同刀自洽）。✓
- deny 指回 `the-door status` 的字串在共用 hook 中；水平推廣讓 snapshot_patch 走同一 hook → 自動繼承此指回。✓
