# S8-report plan：report 面 agent 邊界整膜（3-task inline TDD）

> **日期**：2026-06-06　**狀態**：plan（待執行 inline TDD）　**承**：[`2026-06-06-S8-report-throughline-spec.md`](../specs/2026-06-06-S8-report-throughline-spec.md)（spec 已雙審：concept-review＋5 軸；本 plan 引 spec §3.x 不重貼 exact code，防雙源漂移）。
> **執行方式**：inline TDD（red→green→必要 refactor）。逐 task 跑相關測、末 task 全測。完成 ff-merge main、**不主動 push**。
> **基線**：main `80be905`、全測 1543 passed。驗收＝1543＋新測、零回歸（除 update_tool emit characterization 有意更新）。
> **環境**：`pip install -e ./the_door`（換 worktree 必做，本 session 已裝）；pytest cwd＝內層 `the_door/`；`PYTHONUTF8=1`。

---

## 範圍鎖定（執行前確認，承 spec §1）

- **in**：①`diff_membrane.py` 加 `CHANGE_TYPE_CONTRASTS`(4-val)＋`change_type_signal/element` ②`scope_membrane.py` 加 `scope_element_or_indeterminate` ③新 `core/pipeline/report_membrane.py`（`project_report_for_agent`）④`update_tool.py:112` emit 接線。
- **out（不得誤動）**：`render_json`／`_build_*`／`_diff_result_to_dict`／`_scope_result_to_dict`（report_renderer 全不動）、`update-report.schema.json`、persisted update-report file、`docs/frontend-local-version-viewer/viewer/`（前端）、`cli/update_cmd.py`、`core/ui/api/handlers/analysis.py`、S5 `scope_element`、S6 `node_/edge_diff_element`/CONTRASTS（只加 change_type、不改既有）。
- **grep gate（每 task 末）**：`git diff --stat` 僅含 `diff_membrane.py`＋`scope_membrane.py`＋`report_membrane.py`＋`update_tool.py`＋對應測檔；**無 out 清單檔**（特別確認 report_renderer.py／schema／前端 未動）。

---

## Task 1 — 詞彙地基：change_type 4-val 閉集 ＋ scope 可空投影（red→green）

**交付**：
- `diff_membrane.py`：`CHANGE_TYPE_CONTRASTS`＋`change_type_signal`＋`change_type_element`（exact code＝spec §3.0）。
- `scope_membrane.py`：`scope_element_or_indeterminate`（exact code＝spec §3.1；補 import `NoisePosition`）。

**TDD**：
1. **red**：
   - `tests/unit/core/diff/test_diff_membrane.py` 補：import `CHANGE_TYPE_CONTRASTS`/`change_type_signal`/`change_type_element`（ImportError 紅）。
   - `tests/unit/core/scope/test_scope_membrane.py` 補：import `scope_element_or_indeterminate`（紅）。
2. **green**：照 spec §3.0/§3.1 加碼。

**測試（對應 spec §4 R3/R4 ＋ §6）**：
- **change_type C1**：`change_type_signal(v)` 對 4 值各回 SignalPosition、`.contrasts == CHANGE_TYPE_CONTRASTS`（4-set）、gloss 非空；`change_type_element("added").to_json()` 形狀（value+position.kind=="signal"+contrasts 4-set）。
- **閉集關係釘樁**（spec §3.0 / S6 C4）：`set(CHANGE_TYPE_CONTRASTS) == set(NODE_DIFF_CONTRASTS) - {"unchanged"}`（衍生關係單源、防漂移）。
- **change_type 防呆**（兩種例外分開）：`change_type_element("unchanged")` → **ValueError**（`_NODE_GLOSS` 含 unchanged、gloss 查找成功，但 payload "unchanged" ∉ CHANGE_TYPE_CONTRASTS 4-set → MembraneElement I4 ValueError）；`change_type_element("bogus")` → **KeyError**（_NODE_GLOSS 無 bogus）。
- **scope 可空 R3**：`scope_element_or_indeterminate("in_scope_complete")` → Signal 投影（position.kind=="signal"）；`(None)` → `to_json()` position.kind=="noise"、gap_kind=="indeterminate"、value==None。
- **S5 不回歸**：既有 `scope_element`（恆有值版）測不動、仍綠。

**gate**：`PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_diff_membrane.py tests/unit/core/scope/test_scope_membrane.py -q` 綠。`git diff --stat`＝2 src＋2 test。

---

## Task 2 — agent 邊界投影器 report_membrane（red→green）

**交付**：`core/pipeline/report_membrane.py`（`project_report_for_agent`，exact code＝spec §3.2）＋`tests/unit/core/pipeline/test_report_membrane.py`。

**TDD**：
1. **red**：寫 `test_report_membrane.py`、import `project_report_for_agent`（紅）。
2. **green**：建 `report_membrane.py`（照 spec §3.2；applier 非詞彙來源；import change_type/node/edge_diff_element＋scope_element_or_indeterminate）。

**測試（spec §4 R1/R5 ＋ §6）**：
- 構造涵蓋全軸欄的 report dict（l1_changes change_type／l2_details change_type+scope_state〔有值＋None 兩案〕／l3_appendix.diff_result_json node+edge diff_state／scope_result_json.entries scope_state）。
- **各欄投影**：change_type → `{value, position(signal, contrasts=CHANGE_TYPE_CONTRASTS 4-set)}`；node/edge diff_state → 對應 element（5-set/3-set）；scope_state 有值→signal、None→noise(indeterminate)。
- **R1 完整性釘樁**：投影後枚舉所有已知軸欄、斷言皆 dict（無殘留 bare str）——日後 render_json 新增 bare enum 軸欄而投影器漏接即紅。
- **R5 純函式**：入參 report **不被改**（深拷貝；斷言原 dict 的 change_type 仍 str）；缺鍵 report（無 l2_details／無 l3_appendix／appendix 為 None）不炸（`.get` 防呆）。

**gate**：`pytest tests/unit/core/pipeline/test_report_membrane.py -q` 綠。grep 確認**未動** report_renderer.py。`git diff --stat`＝report_membrane.py＋測。

---

## Task 3 — emit 接線 update_tool ＋ R2 人類面零改動釘樁 ＋ 全測 gate

**交付**：`update_tool.py:112` 接 `project_report_for_agent`（spec §3.3）＋characterization（R1 emit flip／R2 人類面零改動）＋全測零回歸。

**TDD（契約改動→characterization 先行；🟢 spike 證無現成 update_tool/report_renderer 測 → 直接建 `PipelineResult` dataclass，免跑 orchestrator）**：

> **fixture 策略**（concept-review 修）：`PipelineResult` 是 frozen dataclass（[pipeline.py:175](../../../the_door/src/the_door/models/pipeline.py)，可直接構造），塞最小 `DiffResult`（幾個 NodeDiff 含 added/attribute_changed/+邊變 dependency_changed、EdgeDiff modified）＋`ScopeResult`（含一 in_scope + 一無 scope→l2 scope_state None），呼**真實 `render_json`**。**不跑 `update_tool.execute`（全 orchestrator，重）。** 新增 `tests/unit/core/pipeline/test_report_renderer_membrane.py`（或併入 test_report_membrane.py）。

1. **R2 pin（人類面零改動，先釘）**：`render_json(built_result)` 的 `l1_changes[].change_type`／`l2_details[].scope_state`／`l3_appendix.diff_result_json.node_diffs[].diff_state` **仍 bare str/None**（投影為後置、render_json 不變）。確認綠（現狀）。
2. **R1 pin→flip（agent emit 升膜）**：pin `render_json(built_result)` change_type 為 bare → flip：`project_report_for_agent(render_json(built_result))` 後 change_type/scope_state/diff_state 皆 `{value, position}`（scope None→noise）、無裸 enum。
3. **green（接線）**：改 `update_tool.py:112` 照 spec §3.3（加 import、`wrap(project_report_for_agent(render_json(result)), ...)`）。markdown/mermaid 分支（`:107,109`）不動。
   - **:112 接線見證**：接線＝`project_report_for_agent ∘ render_json` 的一行組合；其正確性由「`project_report_for_agent` 單元（Task 2）＋`render_json` bare（R2 pin）＋組合測（R1 flip）」共同保證。**R2 主證另含 git-diff-stat（report_renderer.py/schema/前端未動）＋全測綠**（report_renderer 未動 ⟹ render_json 輸出逐位元不變）。

**gate（末 task 全測）**：
- `cd the_door && PYTHONUTF8=1 python -m pytest -q` ＝**1543＋新測、零回歸**（唯一既有改動＝update_tool json emit 形狀，由 R1 characterization 圈住）。
- 特別回驗：S0-S6 membrane 測全綠；`report_renderer`／viewer handlers／CLI update 測**全綠且未改**（render_json 不動 → 人類面零回歸＝R2 見證）。
- `git diff --stat`＝`diff_membrane.py`＋`scope_membrane.py`＋`report_membrane.py`(新)＋`update_tool.py`＋`test_diff_membrane.py`＋`test_scope_membrane.py`＋`test_report_membrane.py`(新)＋（R1/R2 characterization 測檔）。**無 report_renderer.py／schema／前端／update_cmd／analysis.py。**

---

## 完成後（ff-merge）

1. 全測綠 → commit（campaign 風格，建議 3 commit：`feat(diff/scope-membrane): change_type 4-val + scope 可空`／`feat(report-membrane): agent 邊界 render_json 膜投影`／`test(report-c2/r2): emit flip + 人類面零改動釘樁`；或併）。
2. ff-merge 回 main（`git -C <主repo> merge --ff-only <branch>`）。**不主動 push**。
3. 更新 handoff memory：S8-report merged、campaign 主軸面（confidence/scope/diff_state × agent 面）整膜收齊；剩餘待排＝人類面整膜（[F-human-面-membrane]，碰前端）／presence-flag 型（[F-risk-flags-presence]）／provenance（S7 暫緩）／F-severity-default。

---

## 驗收清單（對應 spec §4 不變量）

| # | 驗收 | task | 測 |
|---|---|---|---|
| R1 | agent 報告 change_type(4-val)/diff_state/scope_state 經膜、無裸 enum；全軸欄無殘留 bare | 2,3 | test_report_membrane＋update flip |
| R2 | 人類面逐位元不變（render_json/schema/persisted/viewer/CLI/前端） | 3 | render_json bare pin＋全測＋git diff --stat |
| R3 | scope_state None → NoisePosition(indeterminate)、不自鑄 default | 1 | test_scope_membrane |
| R4 | change_type ⊆ CHANGE_TYPE_CONTRASTS(4-val)；閉集＝NODE_DIFF_CONTRASTS−{unchanged} | 1 | test_diff_membrane 釘樁 |
| R5 | 只 agent 走投影；純函式不改入參 | 2,3 | test_report_membrane 純函式＋update_tool 單點 |
| 回歸 | S0-S6 全測綠、out 清單未動 | 3 | 全測＋git diff --stat |

**plan 完成 → inline TDD 執行 Task 1→2→3 → ff-merge。**
