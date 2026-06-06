# S5 spec：scope 主軸整膜（scope_state B 側 Signal 投影）

> **日期**：2026-06-06　**狀態**：spec（pre-plan，寫前已對真實碼 spike＋理論重錨＋連貫律回核）　**性質**：乙案（膜模型）重塑 campaign 的 **scope 主軸整膜刀**（S5），承 S0 膜 primitive ＋ S1 doubt（B 側 Signal 樣板、`doubt_type` 純 enum 樣板）＋ S2 NoisePosition ＋ S3 RelayedVerdict ＋ S4 confidence（全序 Signal＋缺值通則）。
> **承接**：S1 spec §5（B 側 Signal 樣板：`{domain}_membrane.py`＋值→SignalPosition 工廠＋gloss dict）；S1 `doubt_membrane.doubt_type_signal`（**純 enum＝只 contrasts+gloss、無前件/後件**＝scope 直接樣板）；S4 spec §3.1（Signal 工廠）／§5（慣例）／§7（對 S5 預判——**本 spec §0 修正之**）。
> **分刀**：S5＝本檔（scope_state LLM-facing 整膜）。S6＝diff_state。S7＝provenance（唯一淨新增軸）。順序 S0→…→S4→**S5**→S6→S7。
> **連貫律（使用者 2026-06-05 立）**：對前階段＝§0 回核 S0-S4＋**驗 S4 §7 對 S5 外推之真偽**（spike 證實「unrecognized 格外殘餘」預判**不成立**、scope_state＝純格內 3-state）；對後階段＝§7 對 S6（diff_state）的慣例外推回驗。

---

## 0. 理論重錨（種子檔 §9.2 強制）＋ S4 §7 預判校正

寫前已逐項回核種子檔 §181/§278/§282/§291/§357/§389/§390/§8.10/§8.13 ＋ S1 `doubt_membrane.py` ＋ S4 spec §7。**本刀最重要的理論動作＝拿真實標的校正 S4 §7 對 scope 的預判**（連貫律的試金石功能）：

| 理論約束（出處） | spike 對真實碼的校正 ＋ S5 如何遵守 |
|---|---|
| **三主軸之一**（§181：`confidence`/`provenance`/`scope`，格內古典，每值自帶意義守 B；軸須正交不可同縫別名） | ✅ scope＝B 側格內 Signal。但 §181 寫的值集 **`scope`(in/out/unrecognized) 與真實 `scope_state` 不符**——見下。 |
| **§181 假設值集＝`in/out/unrecognized`**（含一 off-grid 哨兵 `unrecognized`＝§389/§390「格內對格外命名橋」） | 🔴 **spike 證偽（以真實標的值域為準，非改寫種子原意）**：真實 `scope_state`（`models/scope.py:32`，`scope_verifier.verify()` 產）＝**`in_scope_complete` / `in_scope_incomplete` / `out_of_scope`** 三值，由 (在 ScopeDefinition?) × (在 L1Output?) 的 **2×2 presence 比對**產生（第四格「皆不在」＝universe complement、不 emit）。**無 `unrecognized` 哨兵、無格外殘餘**。**⟹ 本刀標的（scope_verifier 的 feature-level scope_state）為純格內 3-state**。**【本刀詮釋，非種子明證】**§181 抽象值集 `in/out/unrecognized` 不直接對應本標的；其 off-grid 哨兵想像**較可能**對的是 **edge `_resolve` 的 scope-status 面**（§282/§284 表、§291 U1，scope_rule binding）——該面已由 S2（edge 殘餘）覆蓋、method 留事實層（§357）。此詮釋為佐證、非排除 unrecognized 的唯一依據；**排除的硬依據＝真實 verify() 值域窮舉無第四類**。 |
| **per-value 切法**（§8.13 勘誤：閉集值→格內 Signal、格外殘餘→Noise） | scope_state **三值全落閉集、全覆蓋**（total partition）→ **純格內 Signal、零格外殘餘**。⟹ **S5 不建 NoisePosition、不退 indeterminate**（與 S4 §7「S1+S2 合體」預判相反；scope 實為**純 S1 樣板**、且比 confidence 更簡——無全序、無缺值）。 |
| **缺值退 indeterminate**（§8.13 通則、S4 立） | 🔵 **不適用**：`scope_verifier.verify()` 是純函式、對每個 feature_id **恆指派**三值之一（`:94-124` 三迴圈窮盡 `scope_ids ∪ l1_ids`）；emit（`scope_verify_tool:63`）恆有值。**無 LLM/外部缺值來源**（scope_state 是內部 derived、非 LLM 產）⟹ C4 缺值通則無觸發面、`scope_element` 不需 None 分支。 |
| **軸正交、不可同縫別名**（§181/§197 三檢） | ⚠ **真實重疊點**：S1 `doubt_membrane._TYPE_GLOSS` 已含 `out_of_scope`＋`in_scope_incomplete`（為 **doubt_type** 4 值之二）；`scope_verifier.verify_and_create_doubts:172` 以 `doubt_type=entry.scope_state` 餵入。**判定＝非同縫別名**：scope_state 的 contrasts＝**3-set**{complete,incomplete,out}、doubt_type 的 contrasts＝**4-set**{out,incomplete,anomaly,low_confidence}——**同一字串在兩軸帶不同對比位置（意義載體＝contrast 位置、兩軸不同）**⟹ 是兩條正交軸、各自 Signal；`verify_and_create_doubts` 的 `scope_state→doubt_type` 是**生產端跨軸翻譯**（一軸餵另一軸的合法接點，§8.10 接點通則），非別名。S5 建獨立 `SCOPE_CONTRASTS`、**不與 doubt `_TYPE_GLOSS` 單一來源化**（強制單源會把兩個不同 contrast 集綁死＝才是同縫別名）。 |
| **單一來源**（§8.10 B 操作位置優先用內部單一來源） | scope_state 值集散落：model 行註解（`scope.py:32`）＋producer 字面（`scope_verifier:98,109,120`）＋human 面（`scope_renderer.SCOPE_BADGES`／`report_renderer` scope_labels／`scope_cmd`）。S5 建 `SCOPE_CONTRASTS` 為**有意義單一來源**：LLM-facing emit 衍生、producer 以 characterization 釘其值域 ⊆ SCOPE_CONTRASTS。human 面字面同 S4＝**保留（out）**、慣例供日後照抄。 |
| **B 側送達 emit 無裸 enum**（§8.2/§8.10） | `scope_verify_tool:63` `"scope_state": e.scope_state`（裸 enum）→ 經 `scope_element(...).to_json()` 投影。**唯一 LLM-facing emit 點。** |
| **provenance＝唯一淨新增軸**（§8.13-O3） | S5 **不**碰 provenance（S7）。scope_state 無 reserved 自由文字欄（無 scope_reason 成對欄）⟹ **本刀無 ReservedPassthrough 面**（與 S4 confidence_reason 不同）。 |

**LLM-facing 界定（決定性依據，🟢 grep/read 驗全 MCP 出口 `scope_state`/`scope_result_json`）**：scope_state 的 agent-as-LLM 直讀面＝**兩條 MCP 路徑**（concept-review critical 修：原誤宣「唯一一點」，grep `mcp/tools/` 證實 update 工具亦轉送）：
- **本刀投影點（in）**：`mcp/tools/scope_verify_tool.py:63`（`scope_result.entries[].scope_state`，bare enum）。此處 dict **inline 自建、不經 render_json**（不與 viewer 共用）⟹ 投影隔離、agent-only。同檔 `:69-73` `counts`＝計數直方圖（int、非 enum 值）⟹ 保留。
- **report 面（out，標注不漏，歸 S6 鄰域）**：`mcp/tools/update_tool.py:112` `wrap(render_json(result), context="mcp")` → `report_renderer.render_json` 內 `l2_details[].scope_state`（`:212`）＋`_scope_result_to_dict`（`:842`，進 l3_appendix `scope_result_json`）亦 bare scope_state、經 MCP `update` 送 agent。**但 `render_json` 由 update_tool（agent）與 `ui/api/handlers/analysis.py:188`（viewer 人類面）共用**——投影它會連動 viewer JS（人類面）⟹ 屬 **report/viewer 面整膜（S6 diff_state 同住 report_renderer）**，本刀**不投影、明確 out**。**直接先例＝S4 spec §1 將 `diff.py:19 current_confidence` 列「diff 面（S6 鄰域）、本刀只 None-safe、不投影」**：軸出現在 diff/report 面＝該面整膜時連動，非本軸刀強行擴入共用 renderer。
- **input schema**：🔵 **無**——`scope_verify_tool` input＝`scope_file`+`codebase_path`；`scope_create_tool`／`scope-definition.schema.json` 是 ScopeDefinition（不含 scope_state）⟹ **無 input 寫嚴面**。
- **output schema**：🔵 **無**——scope verify 結果無 JSON schema 檔 ⟹ **無 schema parity 面、不建 `scope_schema_fragment`（否則死碼）**。

**非 LLM-facing→out**：`render_json`-via-viewer（`analysis.py:188`，persist 給瀏覽器前端）＋`scope_renderer.SCOPE_BADGES`＋`report_renderer` scope_labels（`:577-584` 人類報告行）＋`cli/scope_cmd.py`＝人類面，S5 立慣例供日後照抄（同 S1/S4）。`scope_verifier` producer 字面（`:98,109,120`）＝生產端內部、characterization 釘值域、不投影（同 doubt lifecycle 不被膜反向改寫）。

---

## 1. 範圍（in / out）

### S5 做（in）— scope 主軸的 LLM-facing 整膜（極薄刀）
1. **膜詞彙單一來源**（新增 `core/scope/scope_membrane.py`，慣例＝`{domain}_membrane.py`，安置 scope 產地 `core/scope`，同 doubt）：
   - `SCOPE_CONTRASTS: tuple = ("in_scope_complete", "in_scope_incomplete", "out_of_scope")`＝scope_state 封閉值唯一來源（**categorical、非全序**——三值是 2×2 presence 分類、無磁量序）。
   - `scope_signal(value) -> SignalPosition`（純 enum 樣板：只 contrasts+gloss，**承 `doubt_type_signal`**，無前件/後件/共依）。
   - `scope_element(value) -> MembraneElement`（**無 None 分支**——scope_state 恆有值）。
2. **output 投影（B 側送達、唯一 LLM-facing 改動）**：`scope_verify_tool.py:63` `scope_state` 經 `scope_element(...).to_json()` 投影為 `{value, position(signal)}`。**契約改動→characterization 先行**（§6）。
3. **單一來源釘樁**：characterization 釘 `scope_verifier.verify()` 產出值域 ⊆ `SCOPE_CONTRASTS`（C2 單一來源的真實守衛，不強改 producer 字面）。

### S5 不做（out）
- **NoisePosition / 缺值退路 / 格外殘餘**：scope_state 純格內全覆蓋、恆有值 ⟹ 無觸發面（§0 校正 S4 §7）。
- **input schema 寫嚴**：scope_state 非 input（derived）⟹ 無面。
- **output schema parity / `scope_schema_fragment`**：無 scope-result schema 檔 ⟹ 不建（防死碼）。
- **ReservedPassthrough**：scope 無成對自由文字欄 ⟹ 無面。
- **與 doubt `_TYPE_GLOSS` 單一來源化**：兩軸 contrast 集不同（3 vs 4）、強綁＝同縫別名 ⟹ 獨立（§0）。
- **人類面 emit**：`scope_renderer`／`report_renderer`／`cli/scope_cmd`＝人類面（同 S1/S4 out）。
- **edge scope-status 面**（§282/§284 `_resolve`）：屬 edge 軸、已由 S2 覆蓋、method 留事實層（§357）⟹ 非本刀（本刀＝scope_verifier 的 feature-level scope_state）。
- **report 面 scope_state（`update_tool`→`render_json`→`report_renderer:212,842`）**：經 MCP `update` 雖 agent-facing，但 render_json 與 viewer（`analysis.py:188`）共用、投影連動人類面 ⟹ 歸 **report/viewer 面整膜（S6 鄰域、diff_state 同住 report_renderer）**、本刀 out（先例＝S4 §1 `diff.py current_confidence`）。**本刀標注不漏、不強行擴入共用 renderer。**
- **provenance（S7）／diff_state（S6）／counts 投影**（counts＝int 直方圖、非 enum）。

---

## 2. Spike 事實（2026-06-06 對真實碼，file:line 已驗）

| 層 | 檔案:line | 事實 |
|---|---|---|
| 模型 | `models/scope.py:32`（ScopeEntry） | `scope_state: str`、valid set 住行註解 `# "in_scope_complete"\|"out_of_scope"\|"in_scope_incomplete"`；無 default（必填、恆由 verifier 填）。 |
| 模型（counts） | `models/scope.py:41-43`（ScopeCounts） | `in_scope_complete/out_of_scope/in_scope_incomplete: int`＝**欄名**為 state 名、值為計數（非 enum 值）。 |
| 生產端（恆指派） | `core/scope/scope_verifier.py:94-124` | `verify()` 純函式：`scope_ids & l1_ids`→complete、`l1_ids - scope_ids`→out_of_scope、`scope_ids - l1_ids`→incomplete。**三迴圈窮盡、每 feature 恆得一值、無缺值、無第四類。** |
| 跨軸翻譯 | `scope_verifier.py:164,172` | `verify_and_create_doubts`：對 `out_of_scope`/`in_scope_incomplete` 兩 state 以 `doubt_type=entry.scope_state` 建 doubt（scope→doubt 生產端翻譯）。 |
| **LLM-facing emit（本刀投影）** | `mcp/tools/scope_verify_tool.py:63` | `"scope_state": e.scope_state`（bare enum，inline dict、不經 render_json）。`:69-73` counts＝int 直方圖。**agent 直讀✓、投影隔離。** |
| **LLM-facing emit（report 面、out 標注）** | `update_tool.py:112`→`report_renderer.render_json:212,842` | bare scope_state 經 MCP `update` 送 agent；但 render_json **與 viewer（`analysis.py:188`）共用**⟹ report/viewer 面整膜（S6 鄰域）、本刀 out（先例＝S4 diff.py current_confidence）。 |
| input（無 scope_state） | `scope_verify_tool.py:4-17`／`scope_create_tool.py`／`schemas/scope-definition.schema.json` | input＝scope_file/codebase_path／ScopeDefinition；**無 scope_state input、無 scope-result output schema**。 |
| doubt 重疊（正交證） | `core/scope/doubt_membrane.py:_TYPE_GLOSS` | doubt_type＝4-set{out_of_scope,in_scope_incomplete,anomaly,low_confidence}；scope_state＝3-set。**共享 2 字串、contrast 集不同**＝正交軸（§0）。 |
| human 面（out） | `scope_renderer.py:33 SCOPE_BADGES`／`report_renderer.py:577-584`／`cli/scope_cmd.py:265,294,303` | badge/label/CLI 人類行；保留。 |
| 樣板源 | `doubt_membrane.py:doubt_type_signal` | 純 enum Signal（只 contrasts+gloss）＝scope_signal 直接樣板。 |

**spike 結論**：scope_state＝**最薄的 B 側主軸**——本刀 LLM-facing 改動＝**一個 emit 點**（scope_verify_tool）升 Signal；report 面（update_tool 經共用 render_json）標注 out 歸 S6。無 A 側（無缺值/殘餘/input）、無 schema、無 reserved。**S4 §7「S1+S2 合體」預判經真實標的證偽：scope 實為純 S1 `doubt_type` 樣板（純 enum Signal）的最小實例。** 連貫律的試金石功能兌現（預判過頭、spike 收斂）。

---

## 3. 設計（exact code；落點標注）

### 3.1 scope 膜詞彙 `core/scope/scope_membrane.py`（新增）

> 慣例樣板（S1 §5）：一 through-line 一 `{domain}_membrane.py`。scope＝feature 範圍分類主軸，產地 `core/scope`（同 doubt）。純 enum（categorical、無前件/後件）＝直接複用 `doubt_type_signal` 形狀。**無 None 分支、無 schema_fragment（無消費者、防死碼）。**

```python
"""scope 線的膜詞彙：把 scope_state 3-值 enum 的每值意義結構化為 SignalPosition。

scope_state＝feature 對 ScopeDefinition 的範圍驗核分類（scope_verifier.verify）：由
(在 scope定義?) × (在 L1?) 的 2×2 presence 比對產生三值，**全覆蓋、恆指派、無格外殘餘、
無缺值**（verify 對每 feature 恆得一值）⟹ 純格內 Signal、無 None 分支、無 NoisePosition。

意義來源單一化（種子檔 §8.10）：SCOPE_CONTRASTS＝唯一來源；gloss＝此處唯一手寫。
承 S1 doubt_type 樣板（純 enum：只 contrasts+gloss）。scope_state 與 doubt_type 共享
'out_of_scope'/'in_scope_incomplete' 兩字串但 contrasts 集不同（3 vs 4）＝正交軸、不單源化
（種子檔 §181 軸正交；強綁不同 contrast 集才是同縫別名）。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, SignalPosition

# 唯一來源：scope_state 封閉 3 值（categorical、非全序——2×2 presence 分類）。
SCOPE_CONTRASTS: tuple[str, ...] = (
    "in_scope_complete",
    "in_scope_incomplete",
    "out_of_scope",
)

# 唯一手寫處：每值極短 gloss（人類意圖殘餘，語法捕不到）。
_GLOSS = {
    "in_scope_complete": "範圍內且已實作（scope 定義 ∩ L1）",
    "in_scope_incomplete": "範圍內但未見實作（僅 scope 定義）",
    "out_of_scope": "已實作但不在宣告範圍（僅 L1）",
}


def scope_signal(value: str) -> SignalPosition:
    """scope_state（3 值 categorical enum）→ Signal（只 contrasts+gloss，承 doubt_type 樣板）。"""
    return SignalPosition(contrasts=SCOPE_CONTRASTS, gloss=_GLOSS[value])


def scope_element(value: str) -> MembraneElement:
    """單一 scope_state 值 → MembraneElement（格內 Signal）。

    scope_state 恆有值（verify 恆指派）⟹ 無 None 分支、無 NoisePosition 退路。
    value ∉ SCOPE_CONTRASTS → _GLOSS[value] KeyError（防呆；正常經 verify 守住）。
    """
    return MembraneElement(payload=value, position=scope_signal(value))
```

> **I4**：`scope_element` 永遠走 SignalPosition 分支、payload＝value ∈ SCOPE_CONTRASTS（emit 的 e.scope_state 恆來自 verify 三值）⟹ I4（payload∈contrasts）恆滿足。

### 3.2 output 投影（唯一 LLM-facing 改動）`scope_verify_tool.py:63`

```python
# from the_door.core.scope.scope_membrane import scope_element
"scope_state": scope_element(e.scope_state).to_json(),   # 值→signal（contrasts 3-set+gloss）
```
> `counts`（`:69-73`）＝各 state 計數直方圖（int）＝**保留不動**（事實量、非裸 enum）。`feature_label`/`expected_label`＝自由文字、非閉集＝保留。

### 3.3 emit 詞彙單一來源 ＋ producer 值域釘樁（C2，不強改 producer）

> **誠實界定（concept-review warning 修）**：scope **無 S1 `DoubtLifecycle` 等級的真權威單源**可供 membrane 衍生。故 C2 ＝ **emit/投影詞彙的單一來源（`SCOPE_CONTRASTS`，scope_element 唯一裁決）＋producer 值集的雙向釘樁**，而非「全碼唯一宣告」。措辭不誇大為「全棧單源」。

scope_verifier producer 字面（`:98,109,120`）保留（assignment 分支、各指派一值＝inherent，同 doubt lifecycle 不被膜反寫）。C2 以 **characterization 雙向釘樁**：斷言 `verify()` 對涵蓋三分類的 (scope_def, l1_output) 產出 `{e.scope_state}` **== `set(SCOPE_CONTRASTS)`**（雙向：⊆ 抓 producer 冒出未登錄值、⊇ 抓 SCOPE_CONTRASTS 列了 producer 不產的死值）。任一側漂移 → 測紅 → 強制同步。

---

## 4. 不變量清單（S5 強制；每條一個守衛或 characterization）

| # | 不變量 | 強制處 | 對應理論 |
|---|---|---|---|
| C1 | scope_state 值 ∈ `SCOPE_CONTRASTS` → SignalPosition(contrasts 3-set+gloss) | `scope_signal` ＋ `MembraneElement` I4 | §181 三主軸／§8.10 B 側 |
| C2 | emit 詞彙單一來源（`SCOPE_CONTRASTS`，scope_element 唯一裁決）＋producer 值集**雙向 ==** SCOPE_CONTRASTS | characterization（verify 值域雙向釘樁） | §8.10 單一來源 |
| C3 | LLM-facing emit（**scope_verify_tool**）scope_state 經膜投影、無裸 enum；report 面（render_json 共用 viewer）標注 out 歸 S6 | emit 走 `scope_element` ＋ characterization | §8.2 B 側送達／本刀核心 |
| C4 | scope_state 與 doubt_type 正交（共享字串、contrasts 集不同）、各自 Signal、不單源化 | `scope_membrane` 獨立於 `doubt_membrane` ＋ test（兩 contrasts 集不等） | §181 軸正交不同縫別名 |

> **無 C(缺值)／C(NoisePosition)／C(reserved)／C(input 寫嚴)／C(schema parity)**——§0/§1 證實 scope 無此五面（與 S4 七不變量相比，scope 是最小子集：純 Signal+單源+emit+正交）。

---

## 5. 慣例萃取（交付 S6-S7）＋ 本刀 findings

S1 立五律、S2 補 A 側、S3 補外部裁決、S4 補缺值通則＋全序。S5 補 **「純格內全覆蓋分類軸」最小樣板**：
1. **純 enum 分類軸（無缺值/殘餘/input/schema）＝最小膜**：`{domain}_membrane.py` 只需 CONTRASTS+signal+element（無 None 分支、無 fragment）；唯一 LLM-facing 動作＝emit 點升 Signal。S6 diff_state 若同型（閉集、恆有值）照此最小樣板。
2. **正交軸共享值字串≠同縫別名**：判準＝**contrasts 集是否相同**。集不同＝不同位置＝不同意義載體＝正交（各自 membrane、不單源化）；集相同才是別名（合一）。跨軸生產端翻譯（一軸值餵另一軸）＝合法接點。
3. **連貫律試金石可證偽前刀預判**：S4 §7 對 scope 的「S1+S2 合體（含 unrecognized 殘餘）」預判經真實標的（`scope_state` 3-state 全覆蓋）**證偽**；spike 校正為純 S1 樣板。**預判過頭→spike 收斂＝連貫律正常運作**（非返工，是試金石設計目的）。
4. **無 schema 的 emit 面**：scope-result 無 JSON schema 檔 ⟹ 不建 `*_schema_fragment`（防死碼）；emit 投影仍照走。S6 若亦無 result schema 同辦。
5. **共用 renderer 的軸＝歸該 renderer 所屬面整膜**（concept-review critical 萃取）：某軸值出現在被 agent 與 viewer **共用**的 renderer（如 `report_renderer.render_json` 經 update_tool＋viewer 雙消費），投影它會連動人類面 ⟹ **不在本軸刀做、歸該 renderer 所屬面（report/diff＝S6）整膜時連動**。判準＝emit 點是否 inline 自建（隔離、可投影）或經共用 renderer（連動、deferred）。先例＝S4 `diff.py current_confidence`。**刀的邊界是「面 × 軸」交格、非單純「軸」**——同軸跨面時各面分別整膜。

**本刀 findings（記錄、交棒）：**
- **[F-scope-human-面]** `scope_renderer.SCOPE_BADGES`／`report_renderer` scope_labels／`cli/scope_cmd`＝人類面 scope_state 字面副本（保留 out）；日後人類面整膜時與 `SCOPE_CONTRASTS` 同源化。
- **[F-scope-doubt-翻譯]** `verify_and_create_doubts:172` `doubt_type=scope_state`＝scope→doubt 生產端跨軸翻譯（正交軸合法接點）；doubt 面已由 S1 membrane（`doubt_type_signal`）覆蓋，本刀不重複投影（emit 在 doubt tools、非 scope_verify_tool）。
- **[F-edge-scope-status]** §282/§284 `_resolve` 的 scope-status（scope_rule binding）＝edge 軸、已 S2 覆蓋、method 留事實層（§357），非本刀（本刀＝feature-level scope_state）。

---

## 6. 測試策略

- **單元**（`tests/unit/core/scope/test_scope_membrane.py`，新增）：C1（值→Signal、contrasts==SCOPE_CONTRASTS 3-set+gloss）／`scope_element(v).to_json()` 形狀（value+position.kind=="signal"）／C4（`set(SCOPE_CONTRASTS) != set(doubt_membrane._TYPE_GLOSS)`＝兩軸 contrasts 集不等、正交）。
- **characterization 先行（§9.4）**：
  - **C2 值域雙向釘樁**（`tests/unit/core/scope/test_scope_verifier*.py` 既有或新增）：構造涵蓋三分類的 (scope_def, l1_output)，斷言 `{e.scope_state for e in verify().entries} == set(SCOPE_CONTRASTS)`（雙向：抓 producer 冒新值＋抓 SCOPE_CONTRASTS 死值）。
  - **C3 emit**（`scope_verify_tool` 測）：先釘現狀「scope_state＝裸 str」（pin）→ flip：經膜投影 `{value, position(signal)}`、無裸 enum。**（report 面 update_tool render_json 不在本刀、不測投影。）**
- **連貫性回驗**：S0 `test_primitive.py`＋S1 doubt 全測（**doubt_membrane 不動**）＋S2/S3/S4 全測仍綠（scope_membrane 純新檔；唯一既有改動＝scope_verify_tool emit 形狀，由其 characterization 圈住）。
- **執行**：`cd the_door && PYTHONUTF8=1 python -m pytest -q`。驗收＝S4 基線 1519＋新測、零回歸（除 emit characterization 有意更新）。

---

## 7. 對 S6（diff_state）的慣例外推回驗 ★（連貫律落點）

> 目的：拿 S6 真實標的當試金石，確認 S0-S5 慣例夠 S6 用、不返工。**並記取 S5 教訓——預判前先標注「待 spike 校正」**。

S6＝diff_state 軸。**種子檔 §433/§444 標 `diff_state`「:14 五值 vs :29 三值不一致」**＝S6 須先 spike 校正真實值集（同 S5 校正 §181 的 scope 值集）。逐點預判（**全帶「待 S6 spike 證實」保留**）：
- **`{domain}_membrane.py` 樣板**：S6 建 `diff_membrane.py`（安置 diff 產地）。diff_state 若閉集 enum→Signal（純 enum 樣板＝S5 `scope_signal`／S1 `doubt_type_signal`）。✓（待驗值集）
- **值集不一致（:14 五值 vs :29 三值）**：S6 首要動作＝spike 哪份是真實 emit 值域、收斂為 `DIFF_STATE_CONTRASTS` 單一來源（同 S4 confidence 收斂散落 enum、同 S5 SCOPE_CONTRASTS 釘樁）。**S5 教訓：以真實 emit 點的值域為準、非註解/模型宣告。**
- **缺值/殘餘**：diff_state 若恆有值（diff engine 恆分類）→ 純格內、無 NoisePosition（同 scope）；若有「未知/未比對」殘餘→ 退 indeterminate（S2/S4 退路）。**待 spike。**
- **正交**：diff_state 與 scope_state/confidence/doubt 正交（diff 面專屬）；若與某軸共享值字串→ 照 S5 C4 判準（contrasts 集異則正交、不單源化）。✓

**回驗結論**：S0-S5 慣例對 S6 充分（純 enum Signal 樣板＝S5、缺值退路＝S2/S4、單一來源收斂＝S4/S5、正交判準＝S5 C4）。**S6 首步＝spike 校正值集不一致**（S5 已示範「拿真實標的校正前刀/種子假設」）。零預見返工。

---

## 8. spec 完成後 7 點審查（種子檔 §9.4；第 4 點 grep 已驗）

1. **單一職責**：`scope_membrane` 只管「scope_state 值→Signal＋有序來源」；emit 點只多一層膜投影。✓
2. **介面最小**：新增 1 模組（`SCOPE_CONTRASTS`＋2 工廠，**無 schema fragment、無 None 分支**＝比 S4 更小）；無新增軸、無模型型別改（scope_state 仍 str、恆有值）。
3. **可測**：純值物件＋純函式；C1-C4 皆可斷言。✓
4. **API 名 grep 驗真**（§2）：`scope_state`(`scope.py:32`)✓／`scope_verify_tool:63` emit✓／`scope_verifier.verify:94-124` 三分類✓／`doubt_membrane._TYPE_GLOSS` 重疊✓／無 scope-result schema✓／`MembraneElement`/`SignalPosition`✓。**無虛構 API。無循環 import**：`scope_membrane`→`core.membrane`（單向）；`scope_verify_tool`→`scope_membrane`。
5. **錯誤路徑**：C1（值∉contrasts→`_GLOSS[value]` KeyError＝防呆，正常經 verify 三值守住）；I4（payload∉contrasts→ValueError，恆不觸發）；**無缺值路徑**（scope_state 恆有值）。
6. **向後相容**：`scope_membrane` 純加法；scope_state 型別不變（仍 str）；**有意契約變更**＝scope_verify_tool emit 形狀（裸 enum→{value,position}）＝characterization 見證。human 面（badge/label/CLI）＝out、不動。
7. **文件**：結構化、exact code、file:line、零佔位符；plan 線性相依時引本 spec §3.x 不重貼。

---

## 9. 交付物（plan 階段拆 task 用）

> **plan task 結構**：S5 極薄、**單一課題（純 Signal emit）**、無 A/B 雙側交纏（無 A 側），建議 2-3 task 線性：**(地基)** 交付物 1（scope_membrane）→ **(B 側 emit)** 交付物 2（scope_verify_tool 投影，characterization）→ **(C2 釘樁＋gate)** 交付物 3（verify 值域 characterization＋全測）。

1. `core/scope/scope_membrane.py`（`SCOPE_CONTRASTS`＋`scope_signal`＋`scope_element`）＋`tests/unit/core/scope/test_scope_membrane.py`（C1/C4／to_json 形狀）。
2. emit 膜投影：`scope_verify_tool.py:63`（scope_state 走 `scope_element`）＋characterization（pin 裸 enum→flip 膜投影）。
3. C2 值域雙向釘樁：`scope_verifier` verify 值域 == set(SCOPE_CONTRASTS) characterization＋全測零回歸。
4. ~~input schema / output schema / NoisePosition / ReservedPassthrough / 缺值誠實化~~＝**無交付物**（§1 out、scope 無此五面）。
5. ~~human 面（badge/label/CLI）／report 面（update_tool render_json scope_state）~~＝**無交付物**（out、保留；report 面歸 S6/report-面整膜＝render_json 與 viewer 共用；plan 須 grep 確認 scope_verify_tool 投影不誤動 render_json／viewer）。

**驗收**：全測零回歸（除 emit characterization 有意更新）、scope_state 值→Signal（C1）、單一來源釘樁（C2）、emit 無裸 enum（C3）、scope/doubt 正交（C4）、S0-S4 全測仍綠（doubt_membrane 不動）。

**S5 完成 → 進 S6（diff_state）spec**：首步＝spike 校正 `diff_state` 值集不一致（:14 五值 vs :29 三值），以真實 emit 值域為準收斂 `DIFF_STATE_CONTRASTS`（S5 已示範「拿真實標的校正種子/前刀假設」）。
