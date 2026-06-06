# S6 spec：diff_state 整膜（node/edge 兩條閉集 enum 的 B 側 Signal 投影）

> **日期**：2026-06-06　**狀態**：spec（pre-plan，寫前已對真實碼 spike＋理論重錨＋連貫律回核）　**性質**：乙案（膜模型）重塑 campaign 的 **diff_state 整膜刀**（S6），承 S0 膜 primitive ＋ S1 doubt（純 enum Signal 樣板）＋ S2 NoisePosition ＋ S3 RelayedVerdict ＋ S4 confidence（缺值通則＋schema parity）＋ S5 scope（**純格內全覆蓋分類軸最小樣板**＋「面×軸」交格慣例＋C4 正交判準）。
> **承接**：S5 spec §3.1（純 enum `{domain}_membrane.py` 最小樣板：CONTRASTS+signal+element、無 None 分支、無 schema_fragment）／§5（慣例：純 enum 最小膜、C4 正交判準、共用 renderer 歸所屬面、無 schema 不建 fragment）／§7（對 S6 預判——**本 spec §0 驗其真偽**）。
> **分刀**：S6＝本檔（diff_state LLM-facing emit 整膜）。S7＝provenance（唯一淨新增軸）。順序 S0→…→S5→**S6**→S7。**並行衍生軌**＝report/viewer 面整膜 cut（render_json 共用面，收編 S4 deferred `current_confidence`＋S5 deferred `scope_state`＋本刀 deferred diff_state，見 §1/§5）。
> **連貫律（使用者 2026-06-05 立）**：對前階段＝§0 回核 S0-S5＋**驗 S5 §7 對 S6 外推之真偽**（spike 證實 S5 §7「diff_state 值集不一致待校正」之真相＝**兩個不同實體各有閉集、非不一致**；其餘預判全中）；對後階段＝§7 對 S7（provenance）＋report/viewer 面 cut 的慣例外推回驗。

---

## 0. 理論重錨（種子檔 §9.2 強制）＋ S5 §7 預判校正

寫前已逐項回核種子檔 §181/§278/§433/§444/§451/§8.10/§8.12/§8.13 ＋ S1 `doubt_membrane.py` ＋ S5 `scope_membrane.py` ＋ S5 spec §7。**本刀最重要的理論動作＝拿真實標的校正種子 §433/§444「diff_state :14 五值 vs :29 三值不一致」與 S5 §7 對 diff 的預判**（連貫律的試金石功能）：

| 理論約束（出處） | spike 對真實碼的校正 ＋ S6 如何遵守 |
|---|---|
| **種子 §433/§444：`diff_state` :14 五值 vs :29 三值「不一致」** | 🔴 **spike 證偽「不一致」框架（以真實標的為準）**：`models/diff.py:14` 是 **`NodeDiff.diff_state`**（5 值），`:29` 是 **`EdgeDiff.diff_state`**（3 值）——**兩個不同 dataclass、各自的閉集**，非同一欄位的兩種宣告。`diff_engine` 對 node（`:69/82/96-98/101/323`）窮盡產 5 值、對 edge（`:246/259/275`）窮盡產 3 值。**⟹ 不是「待修的不一致」，是兩條正交子軸各有閉集**（同 S5 校正種子 §181「in/out/unrecognized」）。 |
| **per-value 切法**（§8.13 勘誤：閉集值→格內 Signal、格外殘餘→Noise） | node 5 值、edge 3 值**全落各自閉集、全覆蓋**（diff_engine 對每筆恆指派）→ **純格內 Signal、零格外殘餘**。⟹ **S6 不建 NoisePosition、不退 indeterminate**（同 S5 scope）。 |
| **缺值退 indeterminate**（§8.13 通則、S4 立） | 🔵 **不適用**：`diff_engine.compute_l1_diff/_compute_edge_diffs` 是純函式，對每個 node_id／edge key **恆指派**閉集之一（node：added/removed/(un)changed→可能升 dependency_changed；edge：added/removed/modified）。**無 LLM/外部缺值來源**（diff_state 是內部 derived、結構比對產）⟹ element 不需 None 分支（同 S5、與 S4 confidence 缺值相反）。 |
| **三主軸＋軸正交、不可同縫別名**（§181/§197 三檢） | diff_state **非** §181 三主軸（confidence/scope/provenance）之一——它是 **diff 面專屬的結構分類軸**（版本比對結果），與三主軸正交。**真實重疊點＝node 與 edge 共享 `"added"/"removed"` 兩字串**：判定＝**非同縫別名**（node contrasts＝5-set、edge contrasts＝3-set，同字串在兩集帶不同對比位置）⟹ 兩條正交子軸、各自 Signal、**不單源化**（強綁不同 contrast 集才是同縫別名，S5 C4 判準直接適用）。 |
| **單一來源**（§8.10 B 操作位置優先用內部單一來源） | diff_state 值集散落：model 行註解（`diff.py:14,29`）＋producer 字面（`diff_engine` 多處）＋schema enum（`diff-result.schema.json:16,34`）＋human 面（`diff_renderer`/`scope_renderer` mermaid classDef、`report_renderer` 文字）。S6 建 `NODE_DIFF_CONTRASTS`＋`EDGE_DIFF_CONTRASTS` 為**emit 詞彙單一來源**：LLM-facing emit 衍生、producer 以 characterization 雙向釘其值域 ==（同 S5 C2）。schema/human 面字面同 S4/S5＝**保留（out）**、慣例供日後照抄。 |
| **B 側送達 emit 無裸 enum**（§8.2/§8.10） | `diff_tool.py:82,83`（json format）node_diffs/edge_diffs 的 diff_state（裸 enum）→ 經 `node_diff_element/edge_diff_element(...).to_json()` 投影。**唯一在本刀投影的 LLM-facing emit 點。** |
| **provenance＝唯一淨新增軸**（§8.13-O3） | S6 **不**碰 provenance（S7）。diff_state 無成對 reserved 自由文字欄（diff 的自由文字＝`current_label/relation` 等，非 diff_state 的 reason 欄）⟹ **本刀無 ReservedPassthrough 面**（同 S5）。 |

**LLM-facing 界定（決定性依據，🟢 grep/read 驗全 MCP 出口 `diff_state`／`render_json` 消費者）**：diff_state 的 agent-as-LLM 直讀面＝**兩條 MCP 路徑**（同 S5 教訓，grep 全 `mcp/tools/` 不信「唯一一點」直覺）：
- **本刀投影點（in）**：`mcp/tools/diff_tool.py:82,83`（`format=="json"` 分支，`diff_result.node_diffs[].diff_state` 5-val ＋ `edge_diffs[].diff_state` 3-val，bare enum）。此處 dict **inline 自建、不經 render_json**（不與 viewer/CLI 共用）⟹ 投影隔離、agent-only。同檔 `:75-81` `summary`＝計數直方圖（int、非 enum 值）⟹ 保留。`format=="mermaid"` 分支（`:86-91`）＝人類視覺 mermaid（out）。
- **report 面（out，S5 deferred 之 scope_state 同住此面，本刀亦 deferred）**：`mcp/tools/update_tool.py:112` `wrap(render_json(result), context="mcp")` → `report_renderer.render_json` 內 `_diff_result_to_dict`（`:818,828`）亦 bare diff_state、經 MCP `update` 送 agent。**但 `render_json` 由三面共用**（🟢 grep 證：`cli/update_cmd.py:208` 人類 CLI ＋ `mcp/tools/update_tool.py:112` agent ＋ `core/ui/api/handlers/analysis.py:188` viewer 前端 JS）——投影它會連動 CLI／viewer 人類面（viewer JS 讀 bare diff_state，見 `graph_view_model.py:288`）⟹ 屬 **report/viewer 面整膜（並行衍生軌 cut）**，本刀**不投影、明確 out**。**直接先例＝S5 spec §1 將 `scope_state`-via-`update_tool`→`render_json` 列「report/viewer 面（S6 鄰域）、本刀 out」；S4 將 `diff.py:19 current_confidence` 同列。** 三軸（confidence/scope/diff_state）皆 deferred 到同一 render_json 共用面 ⟹ 應**一刀整膜該面**（viewer JS 只動一次），非逐軸滲入共用 renderer（§5）。
- **input schema**：🔵 **無**——`diff_tool` input＝`codebase_path`+`baseline`+`format`+`layer`（`:4-13`）；無 diff_state input（diff_state 是 output-only derived）⟹ **無 input 寫嚴面**。
- **output schema**：🔵 **不在本刀動**——`schemas/diff-result.schema.json` **存在**且含 diff_state enum（node 5-val `:16`／edge 3-val `:34`），但：①🟢 grep 證**全 repo 零引用**（orphan doc schema、非 runtime 校驗）；②它描述 **DiffResult 資料模型全欄**（`NodeDiff`/`EdgeDiff` 完整 dataclass，是 emit 的超集——`diff_tool:82` 只 emit `{node_id,diff_state}` 子集）＝**資料模型契約、非 emit 契約**；③膜＝emit 層投影（`primitive.py` docstring「非持久化層、住 emission 邊界」），diff_state model 型別仍 `str`（不改）。**先例＝S4：schema parity＝缺值 nullable 誠實化（oneOf+const+null），非「把 emit 的 {value,position} 巢狀形狀寫進 schema」——analyze_tool emit 巢狀 confidence 但 l1-output.schema confidence 仍 bare-oneOf。** diff_state **無缺值**（恆指派）⟹ 無 nullable 面 ⟹ **無 schema parity 動作**（同 S5 無 schema）。schema 與 render_json 同歸 report/viewer 面 cut 一併重審（§5 finding）。

**非 LLM-facing→out**：`render_json`-via-CLI（`update_cmd.py:208`）＋`render_json`-via-viewer（`analysis.py:188`）＋mermaid（`diff_renderer.py` classDef／`scope_renderer.py:410-430`）＋`report_renderer` 人類文字（`:417 change_type`／`:714 rel_desc`）＋`cli/diff_cmd.py:147,161`＋`graph_view_model.py:288`＋`ui/api/handlers/diff.py:82`＝人類／viewer 面，S6 立慣例供 report/viewer 面 cut 照抄（同 S1/S4/S5）。`diff_engine` producer 字面＝生產端內部、characterization 釘值域、不投影（同 doubt lifecycle／scope_verifier 不被膜反寫）。

---

## 1. 範圍（in / out）

### S6 做（in）— diff_state 的 agent-facing emit 整膜（兩子軸純 Signal）
1. **膜詞彙單一來源**（新增 `core/diff/diff_membrane.py`，慣例＝`{domain}_membrane.py`，安置 diff 產地 `core/diff`，同 scope 置 `core/scope`）：
   - `NODE_DIFF_CONTRASTS: tuple = ("added","removed","attribute_changed","dependency_changed","unchanged")`＝`NodeDiff.diff_state` 封閉 5 值唯一來源（**categorical、非全序**——結構分類、無消費端磁量序。註：engine 內有**計算優先序**〔added/removed terminal、dependency_changed>attribute_changed，`diff_engine:300-302`〕，但該序＝生產端內部裁決、非送達消費端的對比磁量 ⟹ contrasts 不編序）。
   - `EDGE_DIFF_CONTRASTS: tuple = ("added","removed","modified")`＝`EdgeDiff.diff_state` 封閉 3 值唯一來源（categorical）。
   - `node_diff_signal(value)`／`edge_diff_signal(value) -> SignalPosition`（純 enum 樣板：只 contrasts+gloss，**承 S5 `scope_signal`／S1 `doubt_type_signal`**，無前件/後件/共依）。
   - `node_diff_element(value)`／`edge_diff_element(value) -> MembraneElement`（**皆無 None 分支**——diff_state 恆有值）。
   - **兩 contrasts／兩 gloss／兩工廠並列、不單源化為一**（C4：兩子軸正交，共享 added/removed 字串但 contrast 集不同 5 vs 3）。
2. **output 投影（B 側送達、唯一 LLM-facing 改動）**：`diff_tool.py:82,83`（json 分支）node_diffs[].diff_state 經 `node_diff_element(...).to_json()`、edge_diffs[].diff_state 經 `edge_diff_element(...).to_json()`，投影為 `{value, position(signal)}`。**契約改動→characterization 先行**（§6）。
3. **單一來源釘樁**（C2，雙向）：characterization 釘 `diff_engine` 產出 node diff_state 值域 == `set(NODE_DIFF_CONTRASTS)`、edge diff_state 值域 == `set(EDGE_DIFF_CONTRASTS)`（雙向：⊆ 抓 producer 冒未登錄值、⊇ 抓 CONTRASTS 列了 producer 不產的死值）。

### S6 不做（out）
- **NoisePosition / 缺值退路 / 格外殘餘**：diff_state 純格內全覆蓋、恆指派 ⟹ 無觸發面（§0）。
- **input schema 寫嚴**：diff_state 非 input（output-only derived）⟹ 無面。
- **output schema parity / `*_schema_fragment`**：diff-result.schema.json＝orphan 資料模型契約、diff_state 無缺值 ⟹ 不動（防死碼；歸 report/viewer 面 cut 重審，§0/§5）。
- **ReservedPassthrough**：diff_state 無成對自由文字 reason 欄 ⟹ 無面（同 S5）。
- **node 與 edge contrasts 單一來源化**：兩子軸 contrast 集不同（5 vs 3）、強綁＝同縫別名 ⟹ 各自獨立（§0、C4）。
- **report/viewer 面 diff_state**（`update_tool`→`render_json`→`_diff_result_to_dict:818,828`，及共用此 renderer 的 CLI `update_cmd:208`／viewer `analysis.py:188`／`graph_view_model`）：經 MCP `update` 雖 agent-facing，但 render_json 三面共用、投影連動人類面與 viewer JS ⟹ 歸 **report/viewer 面整膜 cut**、本刀 out（先例＝S5 scope_state／S4 current_confidence）。**本刀標注不漏、不強行擴入共用 renderer。**
- **mermaid／CLI diff_cmd／human 文字**（`diff_renderer`／`scope_renderer`／`diff_cmd.py`／`report_renderer:417,714`／`ui/api/handlers/diff.py`）＝人類面（同 S1/S4/S5 out）。
- **provenance（S7）／summary counts 投影**（counts＝int 直方圖、非 enum）。

---

## 2. Spike 事實（2026-06-06 對真實碼，file:line 已驗）

| 層 | 檔案:line | 事實 |
|---|---|---|
| 模型（node） | `models/diff.py:14`（NodeDiff） | `diff_state: str`、valid set 住行註解 `# "added"\|"removed"\|"attribute_changed"\|"dependency_changed"\|"unchanged"`；無 default（必填、恆由 engine 填）。 |
| 模型（edge） | `models/diff.py:29`（EdgeDiff） | `diff_state: str`、行註解 `# "added"\|"removed"\|"modified"`。**與 node 不同 dataclass、不同閉集（種子 §433/§444「不一致」之真相）。** |
| 生產端（node 恆指派） | `core/diff/diff_engine.py:65-107,293-333` | added（current∖baseline）／removed（baseline∖current）／matched→unchanged｜attribute_changed（`:95-98`）／`_upgrade_dependency_changed:307-323`（unchanged/attr+邊變→dependency_changed）。**窮盡 `current∪baseline`、每 node 恆得一值、無第四類外殘餘。** |
| 生產端（edge 恆指派） | `core/diff/diff_engine.py:237-281`（`_compute_edge_diffs`） | added／removed／modified（同 key、relation 文字異）。**窮盡、恆指派、無殘餘。** |
| **LLM-facing emit（本刀投影）** | `mcp/tools/diff_tool.py:82,83` | json 分支：`"diff_state": nd.diff_state`（node 5-val）／`ed.diff_state`（edge 3-val），bare enum、**inline dict、不經 render_json**。`:75-81` summary＝int 直方圖。`:86-91` mermaid＝人類視覺。**agent 直讀✓、投影隔離。** |
| **LLM-facing emit（report 面、out 標注）** | `update_tool.py:112`→`report_renderer._diff_result_to_dict:818,828` | bare diff_state 經 MCP `update` 送 agent；但 render_json **三面共用**（CLI `update_cmd:208`／agent `update_tool:112`／viewer `analysis.py:188`）⟹ report/viewer 面 cut、本刀 out（先例＝S5 scope_state）。 |
| render_json 三消費者（🟢 grep 釘） | `cli/update_cmd.py:208`／`mcp/tools/update_tool.py:112`／`core/ui/api/handlers/analysis.py:188` | 證實 render_json 非 agent-only ⟹ 共用 renderer 投影連動人類面（S5 C5 判準）。 |
| viewer JS 讀 bare diff_state | `core/ui/graph_view_model.py:288`／property test `:445`（sampled added/removed/modified） | 前端讀 `edge_diff["diff_state"]` 為 str ⟹ 投影 render_json 會連動 viewer（人類面 blast-radius）。 |
| input（無 diff_state） | `diff_tool.py:4-13` | input＝codebase_path/baseline/format/layer；**無 diff_state input。** |
| output schema（orphan、out） | `schemas/diff-result.schema.json:16,34` | node 5-val enum／edge 3-val enum；**🟢 全 repo 零引用、非 runtime 校驗、描述資料模型全欄**（emit 超集）⟹ 本刀不動（§0）。 |
| human 面（out） | `diff_renderer.py`（STATE_TO_CLASSDEF/DIFF_SYMBOLS）／`scope_renderer.py:410-430`／`report_renderer.py:417,714`／`cli/diff_cmd.py:147,161`／`ui/api/handlers/diff.py:82` | mermaid classDef／symbol／human 文字／CLI／viewer REST；保留。 |
| 樣板源 | `core/scope/scope_membrane.py`（S5 純 enum）／`core/reading/confidence_membrane.py`（S4） | 純 enum Signal（只 contrasts+gloss）＝node/edge_diff_signal 直接樣板。 |

**spike 結論**：diff_state＝**兩條純格內子軸（node 5-val＋edge 3-val）的 B 側整膜**——本刀 LLM-facing 改動＝**一個 emit 點兩處投影**（diff_tool json 的 node_diffs/edge_diffs）升 Signal；report/viewer 面（update_tool 經共用 render_json，連同 S4/S5 deferred 的 confidence/scope）標注 out 歸並行衍生軌 cut。無 A 側（無缺值/殘餘/input）、無本刀 schema 動作、無 reserved。**種子 §433/§444「值集不一致」經真實標的證偽：非不一致、是兩個不同實體（NodeDiff/EdgeDiff）各自閉集；S5 §7 對 diff 的其餘預判（純 enum 樣板、無缺值、C4 正交判準）全中。** 連貫律試金石功能再次兌現（種子假設被真實碼校正→收斂）。

---

## 3. 設計（exact code；落點標注）

### 3.1 diff 膜詞彙 `core/diff/diff_membrane.py`（新增）

> 慣例樣板（S1 §5／S5 §3.1）：一 through-line 一 `{domain}_membrane.py`。diff＝版本比對結構分類軸，產地 `core/diff`（同 diff_engine）。純 enum（categorical、無前件/後件）＝複用 `scope_signal` 形狀。**兩子軸（node/edge）各一 contrasts＋一 gloss＋兩工廠、不單源化（C4）。無 None 分支、無 schema_fragment（無消費者、防死碼）。**

```python
"""diff 線的膜詞彙：把 diff_state 兩條閉集 enum（node 5-值／edge 3-值）的每值意義
結構化為 SignalPosition。

diff_state＝版本快照比對的結構分類（diff_engine.compute_l1_diff/_compute_edge_diffs）：
- NodeDiff.diff_state（5 值）：feature/block 在 baseline↔current 的 presence＋屬性/依賴變更分類。
- EdgeDiff.diff_state（3 值）：feature 關係邊的 presence＋關係文字變更分類。
兩者**全覆蓋、恆指派、無格外殘餘、無缺值**（engine 對每筆恆得一值）⟹ 純格內 Signal、
無 None 分支、無 NoisePosition。

兩子軸正交（種子檔 §181 軸正交；S5 C4 判準）：node 與 edge 共享 'added'/'removed' 兩字串
但 contrasts 集不同（5 vs 3）＝同字串在兩集帶不同對比位置＝兩條正交子軸、各自 Signal、
不單源化（強綁不同 contrast 集才是同縫別名）。diff_state 與三主軸（confidence/scope/
provenance）正交（diff 面專屬）。

意義來源單一化（種子檔 §8.10）：NODE_/EDGE_DIFF_CONTRASTS＝emit 詞彙唯一來源；gloss＝
此處唯一手寫。承 S5 scope_membrane（純格內全覆蓋分類軸最小樣板）。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, SignalPosition

# 唯一來源：NodeDiff.diff_state 封閉 5 值（categorical、非全序——結構分類）。
NODE_DIFF_CONTRASTS: tuple[str, ...] = (
    "added",
    "removed",
    "attribute_changed",
    "dependency_changed",
    "unchanged",
)

# 唯一來源：EdgeDiff.diff_state 封閉 3 值（categorical）。
EDGE_DIFF_CONTRASTS: tuple[str, ...] = (
    "added",
    "removed",
    "modified",
)

# 唯一手寫處：每值極短 gloss（人類意圖殘餘，語法捕不到）。
_NODE_GLOSS = {
    "added": "本版新增（僅現版有此 node）",
    "removed": "本版移除（僅基線有此 node）",
    "attribute_changed": "標籤/描述變更（依賴邊未變）",
    "dependency_changed": "依賴邊變更（屬性變更併入 secondary_changes）",
    "unchanged": "無變更",
}
_EDGE_GLOSS = {
    "added": "新增關係邊（僅現版有）",
    "removed": "移除關係邊（僅基線有）",
    "modified": "關係文字變更（端點不變）",
}


def node_diff_signal(value: str) -> SignalPosition:
    """NodeDiff.diff_state（5 值 categorical enum）→ Signal（contrasts 5-set+gloss）。"""
    return SignalPosition(contrasts=NODE_DIFF_CONTRASTS, gloss=_NODE_GLOSS[value])


def edge_diff_signal(value: str) -> SignalPosition:
    """EdgeDiff.diff_state（3 值 categorical enum）→ Signal（contrasts 3-set+gloss）。"""
    return SignalPosition(contrasts=EDGE_DIFF_CONTRASTS, gloss=_EDGE_GLOSS[value])


def node_diff_element(value: str) -> MembraneElement:
    """單一 NodeDiff.diff_state 值 → MembraneElement（格內 Signal）。

    diff_state 恆有值（engine 恆指派）⟹ 無 None 分支、無 NoisePosition 退路。
    value ∉ NODE_DIFF_CONTRASTS → _NODE_GLOSS[value] KeyError（防呆；正常經 engine 守住）。
    """
    return MembraneElement(payload=value, position=node_diff_signal(value))


def edge_diff_element(value: str) -> MembraneElement:
    """單一 EdgeDiff.diff_state 值 → MembraneElement（格內 Signal）。"""
    return MembraneElement(payload=value, position=edge_diff_signal(value))
```

> **I4**：`node_diff_element`/`edge_diff_element` 永遠走 SignalPosition 分支、payload＝value ∈ 對應 CONTRASTS（emit 的 diff_state 恆來自 engine 閉集）⟹ I4（payload∈contrasts）恆滿足。

### 3.2 output 投影（唯一 LLM-facing 改動）`diff_tool.py:82,83`

```python
# from the_door.core.diff.diff_membrane import node_diff_element, edge_diff_element
"node_diffs": [
    {"node_id": nd.node_id, "diff_state": node_diff_element(nd.diff_state).to_json()}
    for nd in diff_result.node_diffs
],
"edge_diffs": [
    {"from_node": ed.from_node, "to_node": ed.to_node,
     "diff_state": edge_diff_element(ed.diff_state).to_json()}
    for ed in diff_result.edge_diffs
],
```
> `summary`（`:75-81`）＝各 state 計數直方圖（int）＝**保留不動**（事實量、非裸 enum）。`baseline_info`/`current_info`＝版本 metadata、非閉集＝保留。

### 3.3 emit 詞彙單一來源 ＋ producer 值域釘樁（C2，不強改 producer）

> **誠實界定（承 S5 concept-review warning）**：diff_state 無 `DoubtLifecycle` 等級的真權威單源可供 membrane 衍生。故 C2 ＝ **emit/投影詞彙的單一來源（`NODE_/EDGE_DIFF_CONTRASTS`，element 工廠唯一裁決）＋producer 值集的雙向釘樁**，非「全碼唯一宣告」。措辭不誇大為「全棧單源」。

`diff_engine` producer 字面（多處 assignment 分支、各指派一值＝inherent，同 scope_verifier 不被膜反寫）保留。C2 以 **characterization 雙向釘樁**（粒度＝**跨測案聯集**，非單一 fixture）：
- **⊆ 側**（抓 producer 冒未登錄值）：每個 diff characterization 案例的 `{nd.diff_state}` ⊆ `set(NODE_DIFF_CONTRASTS)`、`{ed.diff_state}` ⊆ `set(EDGE_DIFF_CONTRASTS)`。
- **⊇ 側**（抓 CONTRASTS 列死值）：**所有 characterization 案例產出值的聯集 == `set(...CONTRASTS)`**。**關鍵：`dependency_changed` 僅 L1 路徑產**（`compute_l1_diff` 經 `_upgrade_dependency_changed`）；🟢 spike 證 `compute_l1_5_diff:183-205` 無 edge diff、不呼 upgrade ⟹ **L1.5 node 值域只 4 值（無 dependency_changed）**。故 ⊇ 側的 dependency_changed 必由 **L1 fixtures** 取得（既有 `test_diff_engine.py:261` 已觸發）。

任一側漂移 → 測紅 → 強制同步。

---

## 4. 不變量清單（S6 強制；每條一個守衛或 characterization）

| # | 不變量 | 強制處 | 對應理論 |
|---|---|---|---|
| C1 | node diff_state ∈ `NODE_DIFF_CONTRASTS` → Signal(5-set+gloss)；edge diff_state ∈ `EDGE_DIFF_CONTRASTS` → Signal(3-set+gloss) | `node_/edge_diff_signal` ＋ `MembraneElement` I4 | §8.10 B 側／§8.13 per-value |
| C2 | emit 詞彙單一來源（兩 CONTRASTS，element 工廠唯一裁決）＋producer 值集**雙向 ==** 對應 CONTRASTS | characterization（diff_engine 值域雙向釘樁） | §8.10 單一來源 |
| C3 | LLM-facing emit（**diff_tool json**）node/edge diff_state 經膜投影、無裸 enum；report/viewer 面（render_json 三面共用）標注 out 歸並行衍生軌 cut | emit 走 `node_/edge_diff_element` ＋ characterization | §8.2 B 側送達／本刀核心 |
| C4 | node diff_state 與 edge diff_state 正交（共享 added/removed、contrasts 集 5≠3）、各自 Signal、不單源化；且與三主軸（confidence/scope/provenance）正交 | `diff_membrane` 兩工廠並列 ＋ test（兩 contrasts 集不等） | §181 軸正交不同縫別名 |

> **無 C(缺值)／C(NoisePosition)／C(reserved)／C(input 寫嚴)／C(schema parity)**——§0/§1 證實 diff_state 無此五面（同 S5 最小子集：純 Signal+單源+emit+正交；唯一比 S5 多者＝**兩條子軸**而非一條）。

---

## 5. 慣例萃取（交付 S7＋report/viewer 面 cut）＋ 本刀 findings

S1 立五律、S2 補 A 側、S3 補外部裁決、S4 補缺值通則＋全序、S5 補「純格內全覆蓋分類軸最小樣板＋面×軸交格＋C4 正交判準」。S6 補 **「一面多子軸（共享值字串）」樣板**：
1. **同一 emit 面含多條閉集子軸（contrast 集不同）＝一 `{domain}_membrane.py` 內並列多 CONTRASTS＋多工廠、不單源化**：判準＝S5 C4（contrasts 集相同才合一、不同則並列）。node/edge diff_state 是先例：共享 added/removed 但 5≠3 集 ⟹ 兩工廠。S7 若 provenance 亦多子實體照此。
2. **schema 是「資料模型契約」非「emit 契約」**（承 S4 釐清、S6 明文化）：膜＝emit 層投影（值仍 bare str 於 model），schema 描述 model 全欄（bare enum）。schema parity 只對**缺值 nullable**動（S4），不把 {value,position} 巢狀寫進 schema。無缺值的閉集軸（scope/diff_state）⟹ 無 schema 動作。orphan schema（零引用）尤其不動（防死碼）。
3. **render_json 共用面已累積三軸 deferred（confidence/scope/diff_state）⟹ 應一刀整膜該面**（S6 明確立「並行衍生軌＝report/viewer 面 cut」）：逐軸滲入共用 renderer 會（a）連動 viewer JS 多次（b）破壞 CLI／viewer 人類面讀 bare 的相容。正解＝該面獨立一刀，決定 agent 消費（update_tool）與人類消費（CLI/viewer）如何分流（拆 serializer，或 agent 走膜、人類走 bare）。此 cut 收編 S4 `current_confidence`＋S5 `scope_state`＋S6 diff_state＋重審 diff-result.schema.json。
4. **連貫律試金石可證偽種子框架**：種子 §433/§444「diff_state 值集不一致」經真實標的（NodeDiff/EdgeDiff 兩 dataclass 各自閉集）**證偽為「非不一致、是兩實體」**；S5 §7 對 diff 其餘預判全中。**框架被真實碼校正→收斂＝連貫律正常運作**（同 S5 校正種子 §181）。

**本刀 findings（記錄、交棒）：**
- **[F-report-viewer-面 cut]**（campaign 級，最高優先交棒；**排程＝S7 之後、campaign 收尾前的獨立刀，建議代號 S8-report**——理由：S7 provenance 為主軸最後一條、可能新增 position 變體；report/viewer 面 cut 不宜被 S7 的型別未知阻塞，且該面屆時已累積完整四軸 deferred〔confidence/scope/diff_state＋S7 provenance 若亦入 render_json〕，一刀整膜 viewer JS 最省）：`report_renderer.render_json`／`_diff_result_to_dict` 經 update_tool（agent）＋CLI（`update_cmd:208`）＋viewer（`analysis.py:188`）三面共用，承載 **confidence（S4 deferred current_confidence）＋scope（S5 deferred scope_state `:212,842`）＋diff_state（S6 deferred `:818,828`）** 三軸 bare emit。應獨立一刀整膜，連帶決策 viewer JS（`docs/frontend-local-version-viewer/viewer/` 唯一正式版）的 agent/人類消費分流，並重審 orphan `diff-result.schema.json`。**⚠ 本刀對 handoff §2 表「S6 含 S5 deferred report 面」的有意修正**（依 handoff §7.2 授權 spike 決定）：spike 證 render_json 三面共用＋viewer JS blast-radius ⟹ 拆出獨立 cut 比塞入 diff_state 軸刀更合「面×軸」紀律（S5 §5.5）。
- **[F-diff-human-面]** `diff_renderer`（mermaid classDef/symbol）／`scope_renderer:410-430`／`report_renderer:417,714`／`cli/diff_cmd`／`ui/api/handlers/diff.py`＝人類面 diff_state 字面副本（保留 out）；report/viewer 面 cut 時與 CONTRASTS 同源化。
- **[F-summary-counts]** `DiffSummary`／`summary`（`diff_tool:75-81`）＝diff_state 的計數直方圖（int、欄名為 state 名）＝事實量、非裸 enum ⟹ 不投影（同 S5 scope counts）。

---

## 6. 測試策略

- **單元**（`tests/unit/core/diff/test_diff_membrane.py`，新增）：C1（node 值→Signal、contrasts==NODE_DIFF_CONTRASTS 5-set+gloss；edge 值→Signal、contrasts==EDGE_DIFF_CONTRASTS 3-set+gloss）／`*_element(v).to_json()` 形狀（value+position.kind=="signal"）／C4（`set(NODE_DIFF_CONTRASTS) != set(EDGE_DIFF_CONTRASTS)`＝兩子軸 contrasts 集不等、正交；且共享 {added,removed} 之外各異）。
- **characterization 先行（§9.4）**：
  - **C2 值域雙向釘樁**（`tests/unit/core/diff/test_diff_engine.py` 既有或新增，粒度＝**跨測案聯集**見 §3.3）：⊆ 側每案例斷言、⊇ 側斷言**全案例聯集 == set(CONTRASTS)**。既有 `test_diff_engine.py` 已逐值斷言 added/removed/unchanged/attribute_changed/dependency_changed（L1）與 edge added/removed/modified——彙整為聯集斷言即雙向釘樁。**`dependency_changed` 須由 L1 fixture 取得（L1.5 不產，§3.3）。**
  - **C3 emit**（`diff_tool` 測，新增 happy-path——🟢 spike 證現無 diff_tool json 輸出測，僅 `_invocation_recipes._diff_recipe` 走無 snapshot 的 error 路徑）：構造兩 snapshot→呼 `diff_tool.execute(format="json")`→先釘現狀「diff_state＝裸 str」（pin）→ flip：經膜投影 `{value, position(signal)}`、node/edge 皆無裸 enum。**（report 面 update_tool render_json 不在本刀、不測投影。）**
- **連貫性回驗**：S0 `test_primitive.py`＋S1/S2/S3/S4/S5 全測仍綠（`diff_membrane` 純新檔；唯一既有改動＝diff_tool json emit 形狀，由其 characterization 圈住；`diff_engine`/`diff_renderer`/`graph_view_model`/`report_renderer` 既有測**不動**——本刀不碰其 emit）。
- **執行**：`cd the_door && PYTHONUTF8=1 python -m pytest -q`。驗收＝S5 基線 1525＋新測、零回歸（除 diff_tool emit characterization 有意更新）。

---

## 7. 對 S7（provenance）＋report/viewer 面 cut 的慣例外推回驗 ★（連貫律落點）

> 目的：拿後續刀真實標的當試金石，確認 S0-S6 慣例夠用、不返工。記取 S5/S6 教訓——預判前標注「待 spike 校正」。

**S7＝provenance 軸（種子 §8.13-O3，唯一淨新增軸）。** 逐點預判（**全帶「待 S7 spike 證實」保留**）：
- **唯一淨新增軸 ≠ 既有欄整膜**：S0-S6 皆「既有 bare enum 欄升 Signal」；provenance 是**加一條原不存在的版本戳維度**（§U3：單版退化常數 current、diff 才點亮）。⟹ S7 可能**不照 `{domain}_membrane.py` 純 enum 樣板**（provenance 非閉集 enum、是版本標記＋來源）⟹ 較可能用 **RelayedVerdict 風格的 provenance position 或新 position 變體**。**待 spike：provenance 是 SignalPosition（若閉集 enum 如 analyzed/inherited/...）或需新 position。**
- **缺值/殘餘**：provenance 單版可能無值（退化）→ 退 indeterminate（S2/S4 退路）或常數 current。**待 spike。**
- **正交**：provenance 與 confidence/scope/diff_state 正交（§181 第三主軸）；若與某軸共享值字串→ 照 S6/S5 C4 判準（contrasts 集異則正交）。✓
- **emit 面**：provenance 可能廣佈（snapshot/L1/L2/diff 皆需戳）⟹ blast-radius 大於 S4-S6 單點；**待 spike 盤點全 emit 面**（同 S6 grep 全 MCP 出口）。

**report/viewer 面 cut 預判**（[F-report-viewer-面 cut]）：
- **三軸（confidence/scope/diff_state）同住 render_json 共用面** ⟹ 一刀整膜、viewer JS 動一次。慣例＝S5 §5.5「共用 renderer 歸所屬面」＋S6 §5「累積多軸 deferred 應一刀」。
- **agent/人類消費分流**＝該 cut 核心設計題：拆 serializer（agent 走膜 element、CLI/viewer 走 bare），或 viewer JS 學讀 `{value, position}`。**待該 cut spike viewer JS 實際讀法（`graph_view_model.py:288` 等）。**
- 連帶重審 orphan `diff-result.schema.json`（是否反映膜形狀或拆 agent/human schema）。

**回驗結論**：S0-S6 慣例對「既有閉集 enum 軸整膜」已充分（純 enum Signal＝S5/S6、缺值退路＝S2/S4、單源收斂＝S4/S5/S6、正交判準＝S5/S6 C4、面×軸＝S5、多子軸＝S6）。**S7（provenance）是唯一淨新增軸、可能需新 position 或 RelayedVerdict 風格**＝campaign 最大未知，**S7 首步＝spike provenance 的型別（閉集 enum? 戳+來源?）與全 emit 面**。report/viewer 面 cut 為獨立並行軌、慣例已備。零預見返工。

---

## 8. spec 完成後 7 點審查（種子檔 §9.4；第 4 點 grep 已驗）

1. **單一職責**：`diff_membrane` 只管「node/edge diff_state 值→Signal＋兩單一來源」；emit 點只多一層膜投影。✓
2. **介面最小**：新增 1 模組（2 CONTRASTS＋4 工廠，**無 schema fragment、無 None 分支**＝比 S4 小、比 S5 多一條子軸）；無新增軸、無模型型別改（diff_state 仍 str、恆有值）。
3. **可測**：純值物件＋純函式；C1-C4 皆可斷言。✓
4. **API 名 grep 驗真**（§2）：`NodeDiff.diff_state`(`diff.py:14`)✓／`EdgeDiff.diff_state`(`:29`)✓／`diff_tool.py:82,83` emit✓／`diff_engine` 兩產地✓／render_json 三消費者✓／orphan schema✓／`MembraneElement`/`SignalPosition` 匯出✓。**無虛構 API。無循環 import**：`diff_membrane`→`core.membrane`（單向）；`diff_tool`→`diff_membrane`。
5. **錯誤路徑**：C1（值∉contrasts→`_*_GLOSS[value]` KeyError＝防呆，正常經 engine 閉集守住）；I4（payload∉contrasts→ValueError，恆不觸發）；**無缺值路徑**（diff_state 恆有值）。
6. **向後相容**：`diff_membrane` 純加法；diff_state 型別不變（仍 str）；**有意契約變更**＝diff_tool json emit 形狀（裸 enum→{value,position}）＝characterization 見證。report/viewer/human 面＝out、不動（相容）。
7. **文件**：結構化、exact code、file:line、零佔位符；plan 線性相依時引本 spec §3.x 不重貼。

---

## 9. 交付物（plan 階段拆 task 用）

> **plan task 結構**：S6＝薄刀、**單一課題（兩子軸純 Signal emit）**、無 A/B 雙側交纏（無 A 側），建議 3 task 線性：**(地基)** 交付物 1（diff_membrane 兩子軸）→ **(B 側 emit)** 交付物 2（diff_tool json 投影，characterization）→ **(C2 釘樁＋gate)** 交付物 3（diff_engine 值域雙向 characterization＋全測）。

1. `core/diff/diff_membrane.py`（`NODE_/EDGE_DIFF_CONTRASTS`＋`node_/edge_diff_signal`＋`node_/edge_diff_element`）＋`tests/unit/core/diff/test_diff_membrane.py`（C1/C4／to_json 形狀）。
2. emit 膜投影：`diff_tool.py:82,83`（node/edge diff_state 走對應 element）＋characterization（pin 裸 enum→flip 膜投影，含新增 diff_tool json happy-path 測）。
3. C2 值域雙向釘樁：`diff_engine` node/edge diff_state 值域 == 對應 set(CONTRASTS) characterization＋全測零回歸。
4. ~~input schema / output schema / NoisePosition / ReservedPassthrough / 缺值誠實化 / node-edge 單源化~~＝**無交付物**（§1 out、diff_state 無此面）。
5. ~~report/viewer 面（render_json diff_state）／mermaid／CLI／viewer REST／human 文字~~＝**無交付物**（out、保留；歸並行衍生軌 report/viewer 面 cut；plan 須 grep 確認 diff_tool 投影不誤動 render_json／diff_engine／diff_renderer／graph_view_model）。

**驗收**：全測零回歸（除 diff_tool emit characterization 有意更新）、node/edge diff_state 值→Signal（C1）、兩單一來源雙向釘樁（C2）、emit 無裸 enum（C3）、node/edge 正交（C4）、S0-S5 全測仍綠（既有 diff_engine/diff_renderer/graph_view_model/report_renderer 測不動）。

**S6 完成 → 進 S7（provenance）spec**：首步＝spike provenance 型別（閉集 enum？戳+來源？需新 position？）與全 emit 面（§7）。**並行＝report/viewer 面整膜 cut**（收編 confidence/scope/diff_state 三軸 deferred＋viewer JS 消費分流，[F-report-viewer-面 cut]）。
