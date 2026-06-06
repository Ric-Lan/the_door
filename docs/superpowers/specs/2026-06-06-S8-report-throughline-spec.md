# S8-report spec：report/viewer 面整膜（agent 邊界投影，人類面零改動）

> **日期**：2026-06-06　**狀態**：spec（pre-plan，寫前已對真實碼 spike＋理論重錨＋連貫律回核）　**性質**：乙案（膜模型）重塑 campaign 的 **report 面整膜刀**（S8-report）——收編 S5（scope）＋S6（diff_state）**deferred 到共用 `render_json` 的軸**。承 S0 膜 primitive ＋ S5 `scope_membrane` ＋ S6 `diff_membrane`。
> **承接**：S5 spec §5.5（「面×軸」交格：共用 renderer 的軸歸該 renderer 所屬面）／S6 spec §0/§1/§5 [F-report-viewer-面 cut]（render_json 三面共用、列此刀收編）。
> **分刀**：S8-report＝本檔（report 面 agent 邊界整膜）。**S7（provenance）已暫緩**（spike 證雙重淨新增＋O3 近期零價值，見 [[handoff_2026_06_06_g]] 後續決策）。
> **連貫律**：對前階段＝§0 回核 S5/S6＋**驗 S6 [F-report-viewer-面 cut] 預判之真偽**（spike 校正：render_json 載 **diff-classification＋scope 兩軸、非含 confidence**；且 scope_state 在 report 面**可空**）；對後階段＝§7 對「人類面整膜（viewer JS）」與 provenance 的外推。

---

## 0. 理論重錨（種子檔 §9.2）＋ S6 [F-report-viewer-面 cut] 預判校正

寫前已回核種子檔 §8.2（A/B 脊椎）／§8.10（B 側送達、共用邊界）／§8.12（膜 primitive 住 emission 邊界非持久化）／§8.13（per-value 切法、缺值退 indeterminate）＋ S5/S6 membrane。**本刀最重要的理論動作＝拿真實 `render_json` 校正 S6 [F-report-viewer-面 cut] 對本面的預判**（連貫律試金石）：

| S6 預判（[F-report-viewer-面 cut]） | spike 對真實碼的校正 |
|---|---|
| render_json 載 **三軸 deferred＝confidence＋scope＋diff_state** | 🔴 **校正：載 diff-classification＋scope 兩軸、不含 confidence**。grep `report_renderer.py` 證 **無 confidence 欄**；S4 deferred 的 `diff.py:19 current_confidence` 是 `NodeDiff` 欄、**`_diff_result_to_dict:815-822` 根本不 emit 它**（只 node_id/diff_state/current_label/baseline_label）⟹ confidence 不在 render_json、非本刀面。本刀＝**diff-classification（change_type＋diff_state）＋scope（scope_state）**。 |
| render_json 投影「連動 viewer JS」⟹ 需碰前端 | 🔴 **校正：可不碰前端**。投影點選在 **agent 邊界（`update_tool` 消費 render_json 處）**、非 render_json 自身 ⟹ 人類面（viewer/CLI/persisted file/schema/frontend JS）**全部零改動**（見 §1 範圍與 §2 三消費者）。「面×軸」交格的乾淨解＝**同一 renderer 輸出、agent 邊界再投影**，非改 renderer。 |
| diff_state 5-val / scope 純格內 | 🔴 **校正：report 面值域與來源面不同**。`change_type`＝**4-val**（`added/removed/attribute_changed/dependency_changed`、**無 unchanged**——l1_changes/l2_details 只收變更項，`:385/:397` 濾掉 unchanged）⊂ NODE_DIFF_CONTRASTS；`scope_state` 在 l2_details **可空 None**（`scope_map.get(fid)`，`:736`）⟹ **report 面 scope 有缺值**（與 S5 scope_verify 恆有值相反）→ None 退 NoisePosition(indeterminate)（§8.13 通則、復用 S4 confidence 缺值退路）。 |

**膜哲學定位（§8.12）**：膜＝emission 邊界投影、非持久化。`render_json` 是**人類/viewer 的持久化報告格式**（`analysis.py:189` 寫 `.the-door/update-report-<ts>.json`、符合 `update-report.schema.json`、7 個 frontend JS 模組重度讀）＝**事實/持久化層、保持 bare**。agent（`update_tool`）對它的消費＝**emit 邊界**＝本刀投影點。⟹ 與 S0-S6 一致（持久化存 bare、emit 投影膜）；本刀只是 emit 邊界落在「agent 消費共用 renderer 之處」。

**LLM-facing 界定（grep 全證）**：
- **本刀投影點（in）**：`mcp/tools/update_tool.py:112` `wrap(render_json(result), context="mcp")`——agent 經 MCP `update` 讀 render_json 的 `l1_changes[].change_type`／`l2_details[].change_type,.scope_state`／`l3_appendix.diff_result_json{node,edge}[].diff_state`／`l3_appendix.scope_result_json.entries[].scope_state`（皆 bare enum）。投影成膜。
- **人類面（out，零改動）**：viewer（`core/ui/api/handlers/analysis.py:188`→persist→frontend JS 7 模組）＋CLI（`cli/update_cmd.py:208`）＝讀 bare render_json。**render_json 本身、`update-report.schema.json`、persisted file、`docs/frontend-local-version-viewer/viewer/`（唯一正式版）全不動。**
- **schema**：`update-report.schema.json` 描述**人類/persisted 格式（bare enum）**＝資料契約、不動（同 S6：schema＝資料模型 bare、膜＝emit 投影、自描述無需 schema）。

---

## 1. 範圍（in / out）

### S8-report 做（in）— render_json 的 agent 邊界膜投影（複用 S5/S6 詞彙）
0. **change_type 專屬 4-val 閉集**（`diff_membrane.py` 新增；concept-review warning 修）：`change_type`（l1_changes/l2_details）的閉集**是 4-val**（`added/removed/attribute_changed/dependency_changed`、**無 unchanged**——schema `update-report.schema.json:99,143` enum 即 4-val、code `:385/397` 濾掉 unchanged）。依 S6 C4（contrasts 集不同＝不同位置＝不同 element、不複用），change_type ≠ node diff_state(5-val)，**須自己的 contrasts**，否則膜會謊報 `unchanged` 為兄弟值（該欄契約上永不可能）：
   - `CHANGE_TYPE_CONTRASTS: tuple = ("added","removed","attribute_changed","dependency_changed")`＝change_type 封閉 4 值唯一來源（NODE_DIFF_CONTRASTS∖{unchanged}＝變更項分類）。
   - `change_type_signal(value)`／`change_type_element(value)`（純 enum 樣板、複用 `_NODE_GLOSS` 子集——4 值 gloss 與 node 同字義、零副本：`gloss=_NODE_GLOSS[value]`）。
1. **新 agent 邊界投影器**（新增 `core/pipeline/report_membrane.py`，純函式、**不新增軸詞彙**、複用 `diff_membrane`＋`scope_membrane`）：
   - `project_report_for_agent(report: dict) -> dict`：深拷貝 render_json 輸出，把下列**已知 enum 欄**就地升膜投影 `{value, position}`：
     - `l1_changes[].change_type` → `change_type_element`（4-val 閉集）。
     - `l2_details[].change_type` → `change_type_element`。
     - `l2_details[].scope_state` → **scope 投影（可空）**：值∈SCOPE_CONTRASTS→`scope_element`；None→NoisePosition(indeterminate)。
     - `l3_appendix.diff_result_json.node_diffs[].diff_state` → `node_diff_element`；`.edge_diffs[].diff_state` → `edge_diff_element`。
     - `l3_appendix.scope_result_json.entries[].scope_state` → `scope_element`（scope_verify 來源恆有值；防呆仍走可空投影）。
2. **scope 可空投影**（report 面缺值，§0 校正）：`scope_membrane` 新增 `scope_element_or_indeterminate(value: str | None)`（值→`scope_element`；None→`MembraneElement(None, NoisePosition(gap_kind="indeterminate"))`，復用 S4 confidence 缺值樣板）。**不動 S5 `scope_element`（恆有值版保留給 scope_verify_tool）。**
3. **emit 接線（唯一 LLM-facing 改動）**：`update_tool.py:112` `wrap(render_json(result), ...)` → `wrap(project_report_for_agent(render_json(result)), ...)`。**characterization 先行**（§6）。

### S8-report 不做（out）
- **改 `render_json` / `_build_*` / `_diff_result_to_dict` / `_scope_result_to_dict`**：人類/persisted 格式保持 bare ⟹ **不動**（投影在 agent 邊界後置）。
- **viewer（`analysis.py`）／CLI（`update_cmd`）／persisted update-report file／frontend JS（7 模組）／`update-report.schema.json`**：人類面零改動（本刀核心承諾）。
- **confidence**：render_json 無此欄（§0 校正）⟹ 非本面。
- **`risk_flags`**（`l1_changes[].risk_flags`＝`out_of_scope/vulnerability/semantic_drift` presence-flags list）：presence-only 多選旗標＝S2 deferred 的 `is_flag` 型，膜尚未建此型 ⟹ **out（待 presence-flag 型落地，同 S2 紀律不預建死碼）**。
- **mermaid／markdown 渲染**（`report_renderer` 人類文字/圖、`:417/505/577/714` 等）：人類面 out。
- **provenance（S7，已暫緩）／summary counts（int 直方圖）**。

---

## 2. Spike 事實（2026-06-06 對真實碼，file:line 已驗）

| 層 | 檔案:line | 事實 |
|---|---|---|
| **render_json 結構** | `report_renderer.py:174-238` | 產 `l1_changes`/`l2_details`/`l3_appendix`(diff_result_json+scope_result_json)/pipeline_summary。enum 軸欄見下。 |
| change_type（l1/l2） | `:197`(l1_changes)/`:207`(l2_details)；填於 `:417 change_type=nd.diff_state` | diff-classification 軸；schema enum `update-report.schema.json:99,143`＝**4-val（無 unchanged）**＝NODE_DIFF_CONTRASTS∖{unchanged}（l1/l2 濾變更項 `:385,397`）。 |
| scope_state（l2） | `:212`（`d.scope_state`）；填於 `:736 scope_map.get(fid)` | scope 軸；schema enum `update-report.schema.json:173-178`＝3-val **＋ null**（可空）。**report 面有缺值。** |
| diff_state（diff_result_json） | `:818`(node)/`:828`(edge)（`_diff_result_to_dict`） | S6 軸；node 5-val/edge 3-val（NODE_/EDGE_DIFF_CONTRASTS）。 |
| scope_state（scope_result_json） | `:842`（`_scope_result_to_dict`） | scope 軸；scope_verify 來源恆有值（S5）。 |
| **三消費者（🟢 grep 釘）** | agent `update_tool.py:112`／CLI `update_cmd.py:208`／viewer `analysis.py:188` | render_json **一形狀三面共用**；viewer `:189 _persist_report` 寫 `.the-door/update-report-<ts>.json`（frontend JS 讀）。 |
| viewer JS 重度讀 | `docs/frontend-local-version-viewer/viewer/js/{viewmodel,ui-list,ui-detail,layers,mindmap-util,graph}.js` | change_type/scope_state/diff_state 散佈 6 JS 模組＋測（坐實種子 §459「顯示層 9 模組 56 處」）⟹ **改 render_json enum 形狀＝破前端＋schema＋persisted**。 |
| schema（人類/persisted 契約） | `update-report.schema.json:97-179` | change_type/scope_state enum-constrained；render_json `:175` 宣告「符合」此 schema。**本刀不動（bare 契約保留）。** |
| risk_flags（out） | `:198`；schema `:106-115` | presence-flags `out_of_scope/vulnerability/semantic_drift`＝多選旗標、非單值軸（S2 is_flag 型未建）。 |
| 樣板 | `core/diff/diff_membrane.py`(S6)／`core/scope/scope_membrane.py`(S5)／`core/reading/confidence_membrane.py:30-39`(缺值退路) | 複用 diff/scope 詞彙＋confidence 缺值樣板（scope 可空版）。 |

**spike 結論**：report 面＝**diff-classification（change_type＋diff_state）＋scope（scope_state，可空）兩軸**的 agent 邊界整膜。**不含 confidence**（render_json 無）。投影選在 **agent 邊界後置**（`update_tool` 消費處）⟹ render_json／viewer／CLI／persisted／schema／frontend JS **全零改動**（破解 S6 預判的「投影連動前端」）。複用 S5/S6 詞彙；新增＝①change_type 4-val 閉集（C4：≠node 5-val）②scope 可空投影（report 面缺值，§0 校正）。**S6 [F-report-viewer-面 cut]「三軸含 confidence」「需碰前端」兩預判經真實碼證偽→收斂**（連貫律試金石再兌現）。

---

## 3. 設計（exact code；落點標注）

### 3.0 change_type 4-val 閉集 `core/diff/diff_membrane.py`（新增，不動 S6 既有）

> change_type（l1_changes/l2_details）＝diff 軸的 **changed-only 閉集**（4-val、無 unchanged）。S6 C4：契約閉集 ≠ node(5-val) ⟹ 獨立 contrasts、不複用 node_diff_element（否則謊報 unchanged 為兄弟值）。gloss **零副本**＝`_NODE_GLOSS` 子集（4 值字義與 node 同）。

```python
# 唯一來源：change_type 封閉 4 值（NODE_DIFF_CONTRASTS ∖ {unchanged}＝變更項分類；
# schema update-report.schema.json:99,143 enum 即此 4 值、producer 濾掉 unchanged）。
CHANGE_TYPE_CONTRASTS: tuple[str, ...] = (
    "added",
    "removed",
    "attribute_changed",
    "dependency_changed",
)


def change_type_signal(value: str) -> SignalPosition:
    """change_type（4 值 categorical enum、無 unchanged）→ Signal。gloss 零副本＝_NODE_GLOSS 子集。"""
    return SignalPosition(contrasts=CHANGE_TYPE_CONTRASTS, gloss=_NODE_GLOSS[value])


def change_type_element(value: str) -> MembraneElement:
    """單一 change_type 值 → MembraneElement（格內 Signal、4-val 閉集）。"""
    return MembraneElement(payload=value, position=change_type_signal(value))
```

> **閉集關係釘樁**（test）：`set(CHANGE_TYPE_CONTRASTS) == set(NODE_DIFF_CONTRASTS) - {"unchanged"}`——兩閉集的衍生關係單一來源化、防 node 軸演化時 change_type 漂移。

### 3.1 scope 可空投影 `core/scope/scope_membrane.py`（新增一函式，不動 S5 既有）

```python
# 既有 import 補 NoisePosition
from the_door.core.membrane import MembraneElement, NoisePosition, SignalPosition

def scope_element_or_indeterminate(value: str | None) -> MembraneElement:
    """report 面的 scope_state 可空（l2_details scope_map.get 可回 None）⟹ 缺值版。

    值∈SCOPE_CONTRASTS → scope_element（格內 Signal）；
    None（report 面未對該 feature 算 scope）→ NoisePosition(indeterminate)
    （格外殘餘、不自鑄 default，復用 S4 confidence 缺值退路）。
    S5 `scope_element`（恆有值版）保留給 scope_verify_tool。
    """
    if value is None:
        return MembraneElement(payload=None, position=NoisePosition(gap_kind="indeterminate"))
    return scope_element(value)
```

### 3.2 agent 邊界投影器 `core/pipeline/report_membrane.py`（新增）

> 慣例釐清（**applier、非詞彙來源**——concept-review suggestion）：本檔**不新增軸詞彙**（不是 `{domain}_membrane.py` 那種 CONTRASTS 來源；CONTRASTS 住 diff/scope_membrane），而是**在 report dict 的已知 enum 欄路徑上套膜投影的純函式**。change_type 走 **`change_type_element`（4-val 閉集，§3.0）**、非 node_diff_element（S6 C4：change_type 4-set ≠ node 5-set＝不同位置；docstring 首行明標 applier 防後人找 CONTRASTS 撲空）。

```python
"""report 面的 agent 邊界膜投影 APPLIER（非軸詞彙來源——CONTRASTS 住 diff/scope_membrane）。

把 render_json（人類/persisted bare 報告）的已知 enum 欄在 agent 消費邊界投影為膜
{value, position}，不動 render_json 本身（人類/viewer/CLI/schema/frontend JS 全保持 bare）。
複用 diff_membrane（change_type=4-val／diff_state node5/edge3）＋scope_membrane（scope 可空）。
膜＝emission 邊界投影（§8.12），此處 emission 邊界＝agent 讀共用 renderer。
"""
from __future__ import annotations

import copy

from the_door.core.diff.diff_membrane import (
    change_type_element, edge_diff_element, node_diff_element,
)
from the_door.core.scope.scope_membrane import scope_element_or_indeterminate


def project_report_for_agent(report: dict) -> dict:
    """深拷貝 report、就地把已知 enum 軸欄升膜投影。純函式、不改入參。"""
    r = copy.deepcopy(report)

    for e in r.get("l1_changes", []):
        if "change_type" in e:
            e["change_type"] = change_type_element(e["change_type"]).to_json()

    for d in r.get("l2_details", []):
        if "change_type" in d:
            d["change_type"] = change_type_element(d["change_type"]).to_json()
        if "scope_state" in d:
            d["scope_state"] = scope_element_or_indeterminate(d["scope_state"]).to_json()

    appendix = r.get("l3_appendix") or {}
    diff_json = appendix.get("diff_result_json") or {}
    for nd in diff_json.get("node_diffs", []):
        if "diff_state" in nd:
            nd["diff_state"] = node_diff_element(nd["diff_state"]).to_json()
    for ed in diff_json.get("edge_diffs", []):
        if "diff_state" in ed:
            ed["diff_state"] = edge_diff_element(ed["diff_state"]).to_json()

    scope_json = appendix.get("scope_result_json") or {}
    for entry in scope_json.get("entries", []):
        if "scope_state" in entry:
            entry["scope_state"] = scope_element_or_indeterminate(entry["scope_state"]).to_json()

    return r
```

> **I4**：change_type 值 ⊆ CHANGE_TYPE_CONTRASTS（4-val）、node/edge diff_state 各 ⊆ 自軸 contrasts、scope_state ⊆ SCOPE_CONTRASTS ⟹ 各 element 的 payload∈contrasts 恆滿足；scope None 走 NoisePosition 分支（非 Signal、I4 不適用）。

### 3.3 emit 接線 `mcp/tools/update_tool.py:112`

```python
# from the_door.core.pipeline.report_membrane import project_report_for_agent
return wrap(project_report_for_agent(renderer.render_json(result)), project_path=project_root, context="mcp")
```
> markdown/mermaid 分支（`:107,109`）＝人類面、**不動**。

---

## 4. 不變量清單（S8-report 強制）

| # | 不變量 | 強制處 | 對應理論 |
|---|---|---|---|
| R1 | agent 邊界 report 的 change_type 經 `change_type_element`(4-val)、node/edge diff_state 經 `node_/edge_diff_element`、scope_state 經 scope 可空投影、皆 `{value,position}`、無裸 enum；**全已知軸欄無殘留 bare**（完整性釘樁） | `project_report_for_agent` ＋ characterization（含「無殘留裸 enum 軸欄」） | §8.2 B 側送達 |
| R2 | **人類面零改動**：`render_json` 輸出形狀、`update-report.schema.json`、persisted file、viewer/CLI/frontend JS 全保持 bare | characterization 釘 render_json 形狀不變＋投影為純後置 | §8.12 持久化/事實層保 bare／S5 §5.5 面×軸 |
| R3 | scope_state None（report 面缺值）→ NoisePosition(indeterminate)、不自鑄 default | `scope_element_or_indeterminate` | §8.13 缺值退 indeterminate／fact-finder |
| R4 | 詞彙住 diff/scope_membrane；change_type＝**4-val 閉集**（CHANGE_TYPE_CONTRASTS，C4：≠node 5-val）、diff_state node5/edge3、scope 3；change_type 值域 ⊆ CHANGE_TYPE_CONTRASTS | diff_membrane CHANGE_TYPE_CONTRASTS ＋ characterization（report change_type ⊆ CHANGE_TYPE_CONTRASTS） | §8.10 單一來源／S6 C4 不同閉集不複用 |
| R5 | 只 agent（`update_tool`）走投影；投影為純函式、不改入參 report | `update_tool` 單點接線 ＋ project 純函式 test | 面×軸 交格 |

> **無新軸、無新 position 變體**——複用 S0 NoisePosition＋S5/S6 既有軸；新增僅＝①`CHANGE_TYPE_CONTRASTS`(4-val，diff 軸的 changed-only 閉集，gloss 零副本)②scope 可空投影（report 面真有缺值）。皆 diff/scope 軸內、非新主軸。

---

## 5. 慣例萃取（交付後續面）＋ 本刀 findings

S5 立面×軸、S6 立多子軸。S8-report 補 **「共用持久化 renderer 的 agent 邊界後置投影」樣板**：
1. **共用 renderer（人類+agent+持久化+schema+前端 多消費）的軸整膜＝agent 邊界後置投影、不改 renderer**：保人類/持久化/schema/前端零改動。判準＝renderer 輸出是否被人類面/持久化/schema 綁定（是→後置投影；否、agent-only→可直接改 emit 如 S4-S6）。**破解「投影必連動前端」的假設**。
2. **同概念軸、不同閉集＝不同 element**（concept-review 修）：change_type（4-val，無 unchanged）與 node diff_state（5-val）概念同屬「diff 分類」、但**契約閉集不同**（schema enum 4 vs 5）⟹ 照 S6 C4「contrasts 集不同＝不同位置＝不同 element」**各自 contrasts**（CHANGE_TYPE_CONTRASTS vs NODE_DIFF_CONTRASTS），gloss 零副本共用（同字義）。**教訓：判準是「契約閉集」非「概念同名」**——欄位的閉集由其 schema/producer 定，不憑直覺合併。
3. **同軸跨面缺值差異**：scope 在 scope_verify 面恆有值（S5 純 element）、在 report 面可空（S8 加可空投影）。**缺值是面的性質、非軸的性質**⟹ 同軸不同面各自決定缺值退路、共用 contrasts。
4. **presence-flags（risk_flags）待型**：S2 deferred 的 is_flag 型未建 ⟹ 多選旗標暫不投影（不預建死碼）；待首個 presence-flag 生產者落地再收。

**findings：**
- **[F-risk-flags-presence]** `l1_changes[].risk_flags`（out_of_scope/vulnerability/semantic_drift presence-flags）＝多選旗標軸，待 membrane 補 presence-flag 型（S2 deferred is_flag）後整膜。
- **[F-confidence-not-in-report]** S6 [F-report-viewer-面 cut] 誤列 confidence；實際 render_json 無 confidence 欄（`current_confidence` 是 NodeDiff 欄、`_diff_result_to_dict` 不 emit）⟹ confidence 的 report 面**不存在**、無 deferred 待收。
- **[F-human-面-membrane]** 若日後要讓 **viewer JS/CLI 人類面**也由結構承載意義（非 bare enum＋JS 重複 gloss），需獨立「人類面整膜」刀（碰 frontend 唯一正式版＋schema＋persisted）＝blast-radius 最大、與 agent 面正交、本刀明確不做。

---

## 6. 測試策略

- **單元**（`tests/unit/core/scope/test_scope_membrane.py` 補）：`scope_element_or_indeterminate("in_scope_complete")`＝Signal 投影；`(None)`＝NoisePosition(indeterminate)、`to_json()` position.kind=="noise"、gap_kind=="indeterminate"。
- **單元**（`tests/unit/core/diff/test_diff_membrane.py` 補）：`change_type_signal/element` 4 值→Signal、`.contrasts == CHANGE_TYPE_CONTRASTS`(4-set、無 unchanged)；`set(CHANGE_TYPE_CONTRASTS) == set(NODE_DIFF_CONTRASTS) - {"unchanged"}`（閉集關係釘樁）。
- **單元**（`tests/unit/core/pipeline/test_report_membrane.py` 新增）：`project_report_for_agent` 對構造 report dict——
  - l1_changes/l2_details 的 change_type → `{value, position(signal, contrasts=CHANGE_TYPE_CONTRASTS 4-set)}`；
  - l2_details scope_state（有值＋None 兩案）→ signal / noise(indeterminate)；
  - l3_appendix diff_result_json node/edge diff_state → 對應 element；scope_result_json scope_state → signal；
  - **R1 完整性釘樁**：對涵蓋全軸欄的 report，投影後**枚舉所有已知軸欄、斷言皆 dict（無殘留 bare str）**——日後 render_json 新增 bare enum 軸欄而投影器漏接即紅。
  - **純函式**：入參 report 不被改（深拷貝）；缺鍵/缺 appendix 不炸（`.get` 防呆）。
- **characterization 先行（R2 人類面零改動）**：
  - 釘 `render_json(result)` 輸出 change_type/scope_state/diff_state **仍 bare**（投影為後置、render_json 不變）——既有 render_json 測（若有）不改即綠；補一條顯式「render_json change_type 是 str」pin。
  - **R1 emit flip**（`update_tool` 測）：pin 現狀「update 經 render_json 出 bare change_type」→ flip：經 `project_report_for_agent` 後 `{value, position}`、無裸 enum。
- **R4 值域釘樁**：characterization 斷言 l1_changes/l2_details 的 change_type 值域 ⊆ `set(CHANGE_TYPE_CONTRASTS)`（report producer ↔ change_type 閉集一致；漂移即紅）。
- **連貫性回驗**：S0-S6 全測綠（`diff_membrane`/`scope_membrane` 既有不動，scope 純加一函式；render_json 不動 ⟹ viewer/CLI/frontend JS 測全綠）。
- **執行**：`cd the_door && PYTHONUTF8=1 python -m pytest -q`。驗收＝S6 基線 1543＋新測、零回歸（除 update_tool emit characterization 有意更新）。

---

## 7. 對後續面的慣例外推回驗 ★（連貫律落點）

- **人類面整膜（viewer JS/CLI）**：[F-human-面-membrane]——若要消費端**人類**也經結構讀意義，需碰 frontend 唯一正式版＋`update-report.schema.json`＋persisted file＝最大 blast-radius。慣例＝本刀的「agent 邊界後置投影」**不適用**（人類面就是要改 render_json/schema/JS 本身）。**待真實需求（使用者明示要 viewer 不顯 bare enum）才起、且須前端連動 spec。**
- **presence-flag 型**（[F-risk-flags-presence]＋S2 deferred is_flag）：首個 presence-only 生產者落地時補 NoisePosition is_flag 或新型；risk_flags 屆時整膜。
- **provenance（S7 暫緩）**：雙重淨新增＋O3 零近期價值；若起，先版本戳持久化基礎（非 membrane）、戳累積後投 Signal。
- **回驗結論**：S0-S6 詞彙對 report 面大體充分；新增＝①change_type 4-val 閉集（C4：契約閉集 vs 概念同名，§慣例 2）②scope 可空投影（面缺值差異，§慣例 3）③agent 邊界後置投影樣板（慣例 1）。零預見返工。

---

## 8. spec 完成後 7 點審查（種子檔 §9.4；第 4 點 grep 已驗）

1. **單一職責**：`report_membrane.project_report_for_agent` 只管「report dict 已知 enum 欄→膜」；`scope_element_or_indeterminate` 只管 scope 可空。emit 點只多一層後置投影。✓
2. **介面最小**：新增 1 模組（1 純函式）＋scope_membrane 加 1 函式＋diff_membrane 加 1 contrasts(4-val)+2 工廠；**不新增主軸/position 變體**；render_json/schema/前端不動。
3. **可測**：純函式＋純值物件；R1-R5 皆可斷言。✓
4. **API 名 grep 驗真**（§2）：render_json 結構 `:174-238`✓／change_type `:197,207`✓/schema 4-val `:99,143`✓／scope_state 可空 `:212`+schema null `:173-178`✓／diff_result_json `:818,828`✓／scope_result_json `:842`✓／三消費者 `update_tool:112`/`update_cmd:208`/`analysis:188`✓／`node_/edge_diff_element`(S6)/`scope_element`(S5)/`NoisePosition`(S0)✓。**無虛構 API。無循環 import**：`report_membrane`→`diff_membrane`/`scope_membrane`（單向）；`update_tool`→`report_membrane`。
5. **錯誤路徑**：缺鍵/缺 appendix→`.get` 防呆不炸；change_type∉CHANGE_TYPE_CONTRASTS→gloss KeyError（防呆，正常經 schema 4-val enum 守住）；scope None→NoisePosition（非錯、是缺值退路）。
6. **向後相容**：純加法；render_json/schema/persisted/前端**逐位元不變**（R2 characterization 見證）；**有意契約變更＝僅 `update` MCP（agent）輸出形狀**（bare→膜，characterization 見證）。
7. **文件**：結構化、exact code、file:line、零佔位符；plan 引本 spec §3.x 不重貼。

---

## 9. 交付物（plan 階段拆 task 用）

> **plan task 結構**：建議 3 task 線性：**(地基)** 交付物 1（diff_membrane CHANGE_TYPE_CONTRASTS ＋ scope 可空投影）→ **(投影器)** 交付物 2（report_membrane＋單元）→ **(emit 接線＋R2 釘樁)** 交付物 3（update_tool 接線＋characterization：agent 升膜、人類面零改動）。

1a. `core/diff/diff_membrane.py` 加 `CHANGE_TYPE_CONTRASTS`(4-val)＋`change_type_signal/element`（gloss 零副本＝`_NODE_GLOSS` 子集）＋`tests/unit/core/diff/test_diff_membrane.py` 補（4-val Signal、`== NODE_DIFF_CONTRASTS - {unchanged}`）。
1b. `core/scope/scope_membrane.py` 加 `scope_element_or_indeterminate`＋`tests/unit/core/scope/test_scope_membrane.py` 補（有值/None 兩案）。
2. `core/pipeline/report_membrane.py`（`project_report_for_agent`，applier 非詞彙來源）＋`tests/unit/core/pipeline/test_report_membrane.py`（各欄投影、R1 完整性釘樁、純函式、防呆、R4 值域）。
3. emit 接線 `update_tool.py:112`＋characterization（R1 flip emit 升膜／R2 render_json 形狀不變＋viewer/CLI 不動）＋全測零回歸。
4. ~~改 render_json / schema / 前端 JS / persisted 格式 / confidence / risk_flags / mermaid / markdown~~＝**無交付物**（§1 out）。

**驗收**：全測零回歸（除 update_tool emit characterization 有意更新）、agent 報告無裸 enum（R1）、人類面逐位元不變（R2）、scope 缺值退 indeterminate（R3）、複用既有軸詞彙（R4）、只 agent 走投影（R5）、S0-S6 全測綠。

**S8-report 完成 → campaign 主軸面（confidence/scope/diff_state × agent 面）整膜收齊**。剩餘待排：人類面整膜（[F-human-面-membrane]，碰前端）／presence-flag 型（[F-risk-flags-presence]）／provenance（S7 暫緩）／F-severity-default（vulnerability 小刀）。
