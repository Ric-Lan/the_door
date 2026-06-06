# S4 spec：confidence 主軸整膜（B 側 Signal 投影 ＋ 閉集 enum 缺值誠實化）

> **日期**：2026-06-06　**狀態**：spec（pre-plan，寫前已對真實碼 spike＋理論重錨＋連貫律回核）　**性質**：乙案（膜模型）重塑 campaign 的 **confidence 主軸整膜刀**（S4），承 S0 膜 primitive ＋ S1 doubt（B 側 Signal 樣板）＋ S2 NoisePosition（A 側退路）＋ S3 RelayedVerdict（缺值退 indeterminate 先例）。
> **承接**：S1 spec §5（B 側 Signal 樣板：`{domain}_membrane.py`＋值→SignalPosition 工廠＋gloss dict＋input schema 衍生＋schema parity）；S2 spec §3.3（`low_confidence_ambiguous` 座標，明標 "confidence Signal deferred to S4"）；S3 spec §3.3/§5（cvss `float|None` 缺值退 NoisePosition(indeterminate) 先例＋F-severity-default 交棒）；理論定稿＝種子檔 §8.13（§181 三主軸 confidence/provenance/scope、§235 confidence＝生產端自身認識狀態不可漂 severity、§291/§357 confidence 被超載進 edge resolution、§442 confidence 遍佈模型層、§443 confidence_reason＝reserved 窗現成）。
> **分刀**：S4＝本檔（confidence 主軸 LLM-facing 整膜）。S5＝scope（`scope.py:32 scope_state`）。S6＝diff_state。S7＝provenance（唯一淨新增軸）。順序 S0→S1→S2→S3→S4→…。
> **連貫律（使用者 2026-06-05 立）**：對前階段＝§0 回核 S0/S1/S2/S3＋驗 S3 §7 對 S4 外推成立；對後階段＝§7 對 S5（scope）的慣例外推回驗。

---

## 0. 理論重錨（種子檔 §9.2 強制；每條釘到一個 S4 決定，防漂移）

寫前已逐項回核種子檔 §181/§235/§291/§357/§442/§443/§8.12/§8.13 ＋ S1 spec §5 ＋ S2 spec §3.3 ＋ S3 spec §3.3/§5/§7。下表把每條約束釘到具體決定：

| 理論約束（出處） | S4 如何遵守 |
|---|---|
| **三主軸之一**（§181：`confidence`/`provenance`/`scope`，格內古典，每值自帶意義守 B；軸須正交不可同縫別名） | confidence＝B 側格內 Signal（high/medium/low 封閉**全序**）；每值意義從行註解移進 `SignalPosition`。**與 doubt（S1）同構。** |
| **confidence＝生產端自身認識狀態，不可漂成 severity/importance**（§235） | S4 守 confidence 只表「抽取信心」。**severity-default 經軸正交檢驗不屬 confidence 軸→剔除（§1 out）**；severity 是 vulnerability 專屬軸（只在 `models/vulnerability.py`）。 |
| **U1：confidence 被超載進 edge `resolution` 字串**（§291/§357；edge 面 confidence＝主軸 resolution tier） | `name_match_ambiguous`（edge fanout 低信心）＝edge 面 confidence=low 的承載；S4 把 S2 留的 `low_confidence_ambiguous` raw 桶**升為 confidence Signal**（命名並拆分碼裡已長出的軸＝discovered 非 imposed）。 |
| **凡來源沒給的值退 NoisePosition(indeterminate)**（§8.13 通則） | confidence 生產端缺值自鑄（`batch_reader:190,345`／`l2_generator:165,186` `.get(...,"medium")`）＝靜默自鑄 default＝病灶。**修法＝缺值退 NoisePosition(indeterminate)**（復用 S2/S3 退路，零預建）。S4 立「**閉集 enum 缺值誠實化**」通則。 |
| **生成性／型驅動：make illegal states unrepresentable**（§8.11/§8.12） | `confidence: str → str \| None`（None＝LLM 未評估）；emit 時 None→NoisePosition、值→SignalPosition＝**「靜默自鑄 medium」結構性不可構造**（仿 S3 cvss `float\|None`/F6）。 |
| **provenance＝唯一淨新增軸**（§8.13-O3） | S4 **不**碰 provenance/版本戳（S7）。`confidence_reason`＝**既有**成對欄（§443 reserved 窗現成）→ `ReservedPassthrough`，非新增軸。 |
| **per-value 切法**（§8.13 勘誤） | confidence 值全落閉集（high/medium/low）→ 全格內 Signal；缺值（None）＝格外殘餘→ NoisePosition(indeterminate)。`confidence_reason`＝reserved 窗（明文開放、非殘餘）。 |
| **單一來源**（§8.10 B 操作位置優先用內部單一來源） | 建 confidence **有序單一來源**（現只有無序 `VALID_CONFIDENCE` set〔`snapshot_write_tool:15`〕＋ ~3 schema enum 副本 ＋ ~6 行註解）→ 收斂為 `core/reading/confidence_membrane.CONFIDENCE_CONTRASTS`（全序 tuple），consumers 衍生。 |
| **誠實界線**（§8.11） | S4 只強制**結構**合規（每值帶 position、缺值退 Noise、input 帶 enum+desc）；gloss 文字、信心判斷對錯仍靠人＋test。型管形狀、管不到判斷。 |

**LLM-facing 界定（本 spec 範圍的決定性依據，🟢 grep/read 驗）**：confidence 的 agent-as-LLM 直讀面＝
- **input schema（消費端 LLM 直讀＝寫嚴）**：`snapshot_write_tool.py:46,89`（已有 `enum:[high,medium,low]`、**缺 per-value description**＝半膜）、`snapshot_patch_tool.py`。
- **output emit（送達消費端 LLM）**：`analyze_tool.py:82`（L1 features）、`analyze_changes_tool.py:61`（FeatureSummary）。
- **生產端缺值自鑄（事實層誠實）**：`batch_reader.py:190,345`（L1 parse）、`l2_generator.py:165,186`（L2 parse）。
- **edge 面 confidence**：`edge_projection.py:58` `low_confidence_ambiguous` 桶（S2 留、未升 Signal）。
- **schema 半膜**：`l1-output.schema.json:62`／`snapshot.schema.json:25,42`／`l2-output.schema.json:44,125`（enum 多副本、無每值意義）。

**非 LLM-facing→out**：viewer JS（`ui-list`/`ui-detail` confidence 顯示）、`report_renderer`、CLI 人類行、`build_confidence_marker`（mermaid 視覺）＝人類面，S4 立的慣例供日後照抄（同 S1）。`diff.py:19 current_confidence`＝diff 面（S6 鄰域），本刀只確保 None-safe、不投影。

---

## 1. 範圍（in / out）

### S4 做（in）— confidence 主軸的 LLM-facing 整膜
1. **膜詞彙單一來源＋有序來源**（新增 `core/reading/confidence_membrane.py`，慣例＝`{domain}_membrane.py`）：
   - `CONFIDENCE_CONTRASTS: tuple = ("high", "medium", "low")`＝**confidence 全序唯一來源**（high>medium>low）。
   - `confidence_signal(value) -> SignalPosition`（contrasts＝全序、gloss＝每值極短注解）。
   - `confidence_element(value) -> MembraneElement`；`confidence_reason_element(text) -> MembraneElement`（reserved 窗）。
   - `confidence_schema_fragment() -> dict`（input/output schema 的 `oneOf+const+description`，從 gloss 衍生、零副本）。
2. **單一來源收斂**：`snapshot_write_tool.VALID_CONFIDENCE`（`:15` set）改 `set(CONFIDENCE_CONTRASTS)` 衍生；3 schema enum 改與 `confidence_schema_fragment()` parity（per-value description 同源）。
3. **input schema 寫嚴（B 側 CWA）**：`snapshot_write_tool`（`:46,89`）／`snapshot_patch_tool` 的 confidence enum 補 per-value `description`（從詞彙來源）。
4. **output 投影（B 側送達）**：`analyze_tool`（`:82`）／`analyze_changes_tool`（`:61`）的 confidence 欄經 `MembraneElement.to_json()` 投影為 `{value, position}`（SignalPosition 或 None→NoisePosition）；`confidence_reason` 走 `ReservedPassthrough`。**契約改動→characterization 先行**（§6）。
5. **閉集 enum 缺值誠實化（A 側、S4 立通則）**：`Feature.confidence`／`FeatureSummary.confidence`／`L2Module.confidence`／`Anomaly.confidence`／`BlockSummary.confidence` 改 `str → str | None`；生產端 `batch_reader:190,345`／`l2_generator:165,186` 的 `.get("confidence","medium")` 改 `.get("confidence")`（缺→None，**不自鑄 medium**）；emit 時 None→`NoisePosition(indeterminate)`（復用 S2/S3 退路）。
6. **name_match_ambiguous 升 confidence Signal**（`edge_projection.py:58`）：`low_confidence_ambiguous` raw `{caller:{method:count}}` 桶 → 每筆經 `confidence_element("low")`-attached 投影（復用 S2 座標、基數保留）。**契約改動→characterization 先行**。
7. **schema 補完（半膜→全膜）**：`l1-output`／`snapshot`／`l2-output` 三 schema 的 confidence enum 補 per-value 意義（與詞彙來源同源、parity test 把關）；confidence nullable（缺值＝null，向後相容＝舊資料 enum 值仍合法）。
8. **下游 None-容忍（機械）**：confidence 排序/比較點 None-安全；`diff.py:19 current_confidence` 既已 nullable，確認不炸。

### S4 不做（out）
- **severity-default（`scanner:149,156`）**：經軸正交檢驗（§181）**不屬 confidence 軸**——severity 是 vulnerability 專屬軸（只在 `models/vulnerability.py:14,46`），與 confidence（遍佈 analysis/snapshot/pipeline/diff）正交。它與 S3 已修的 cvss 捏中點**同一支 scanner、同類缺值自鑄**→ 歸 **vulnerability 補完**（S3 的尾巴/獨立小刀），**照抄 S4 本刀立的「閉集 enum 缺值誠實化」通則**（§5 finding）。混入 confidence 刀＝同縫別名。
- **人類面 emit**：viewer JS／`report_renderer`／CLI 人類行／`build_confidence_marker`＝非 LLM-facing；S4 立的投影慣例供日後照抄（同 S1 out）。
- **provenance / 版本戳（S7）**、**scope（S5）**、**diff_state（S6）**、**diff confidence 投影**（`current_confidence` 屬 diff 面，本刀只 None-safe）。

---

## 2. Spike 事實（2026-06-06 對真實碼，file:line 已驗）

| 層 | 檔案:line | 事實 |
|---|---|---|
| 模型（必填） | `models/analysis.py:16`（Feature）／`models/snapshot.py:32`（FeatureSummary） | confidence bare `str`、valid set 住**行註解** `# "high"\|"medium"\|"low"`；無 default（dataclass 必填）。 |
| 模型（有 default） | `models/analysis.py:137`（L2Module）／`:159`（Anomaly）／`models/snapshot.py:45`（BlockSummary）／`models/pipeline.py:149` | confidence `str = "medium"`／`="low"`＝dataclass default。 |
| 模型（reserved 窗） | `models/analysis.py:17,138`／`snapshot.py:35` | `confidence_reason` 與 confidence **成對存在**＝reserved 窗模型層現成（§443）。 |
| 缺值自鑄①（L1） | `core/reading/batch_reader.py:190,345` | `confidence=feat_data.get("confidence", "medium")`＝**LLM 沒給就靜默自鑄 medium**（病灶）。 |
| 缺值自鑄②（L2） | `core/ui/l2_generator.py:165,186` | `confidence=m.get("confidence", "medium")`／`a.get("confidence", "medium")`＝同病。 |
| 單一來源（無序） | `mcp/tools/snapshot_write_tool.py:15` | `VALID_CONFIDENCE = {"high","medium","low"}`＝**無序 set**（contrasts 需全序 tuple）；`:128` 寫入校驗。 |
| input schema（半膜） | `snapshot_write_tool.py:46,89` | confidence `enum:[high,medium,low]` **無 per-value description**；`server.py` 註冊為 LLM `inputSchema`。 |
| output emit①（L1） | `mcp/tools/analyze_tool.py:82,84` | emit `"confidence": f.confidence`＋`"confidence_marker"`（後者 mermaid 視覺）。**agent 直讀✓。** |
| output emit②（diff feature） | `mcp/tools/analyze_changes_tool.py:61,62` | `_feature_to_json` emit `confidence`＋`confidence_reason`（defensive getattr）。**agent 直讀✓。** |
| edge 面（S2 留） | `core/llm/edge_projection.py:58`／`edge_membrane.py:4-5` | `low_confidence_ambiguous` raw `{caller:{method:count}}`**未升 Signal**；註明「格內低信心、confidence 軸 S4、不歸 gap_kind」。 |
| schema 半膜（3 副本） | `l1-output.schema.json:62-68`／`snapshot.schema.json:25,42`／`l2-output.schema.json:44,125` | confidence `enum:[high,medium,low]` 各重一份、無每值意義。 |
| severity（OUT 證·軸正交） | `models/vulnerability.py:14,46`；`scanner:149,156` | severity 只在 vulnerability domain；scanner OSV 未給→鑄 medium＝**vulnerability 軸缺值自鑄**（與 confidence 正交、與 cvss 同 scanner）。 |
| diff（None-safe 證） | `models/diff.py:19` | `current_confidence: str \| None = None` 已 nullable＝diff 面本就容缺；本刀只確認不炸。 |
| primitive 預示 | `core/membrane/primitive.py:20` | 「contrasts 是 tuple（有序）：doubt states＝圖；**severity＝全序**——同型別容兩者」＝S0 已預期 confidence/severity 走全序 Signal。 |

**spike 結論**：confidence＝遍佈模型層的 B 側主軸（§442），LLM-facing 面＝2 input schema＋2 output emit＋edge 桶＋3 schema；**病灶兩類**：①B 側半膜（enum 有、每值意義無＝同 doubt 前態）→ Signal 投影＋schema 補完；②A 側缺值自鑄（`.get(...,"medium")` 4 處）→ 缺值退 NoisePosition(indeterminate)。**S3 §7 對 S4 外推（S1 樣板適用、S2 座標復用、缺值退 indeterminate 退路現成）實證成立。** severity-default 經軸正交確證不屬本軸。

---

## 3. 設計（exact code；落點標注）

### 3.1 confidence 膜詞彙＋有序單一來源 `core/reading/confidence_membrane.py`（新增）

> 慣例樣板（S1 §5）：一 through-line 一 `{domain}_membrane.py`。confidence＝橫切主軸，產地以 L1（`core/reading`）最權威，故安置於此；S5 scope/S7 provenance 各依其主產地建對應 membrane。全序 contrasts（high>medium>low）＝唯一手寫有序來源；gloss 為唯一手寫人類意圖殘餘（極短）。

```python
"""confidence 線的膜詞彙：把 confidence enum 的每值意義結構化為 SignalPosition。

意義來源單一化（種子檔 §8.10）：CONFIDENCE_CONTRASTS＝全序唯一來源（high>medium>low）；
gloss＝極短指稱注解（此處唯一手寫處）。缺值（None＝來源未評估信心）退
NoisePosition(indeterminate)（§8.13 通則、復用 S2/S3 退路），不靜默自鑄 default。
S5–S7 照此樣板各建 {domain}_membrane.py。
"""
from __future__ import annotations

from the_door.core.membrane import (
    MembraneElement, NoisePosition, ReservedPassthrough, SignalPosition,
)

# 唯一有序來源（全序：high 最強信心 → low 最弱）。consumers 一律衍生、不另列副本。
CONFIDENCE_CONTRASTS: tuple[str, ...] = ("high", "medium", "low")

# 唯一手寫處：每值極短 gloss（人類意圖殘餘，語法捕不到）。
_GLOSS = {
    "high": "抽取信心高",
    "medium": "抽取信心中",
    "low": "抽取信心低",
}


def confidence_signal(value: str) -> SignalPosition:
    """confidence（3 值全序 enum）→ Signal（contrasts 全序＋gloss）。"""
    return SignalPosition(contrasts=CONFIDENCE_CONTRASTS, gloss=_GLOSS[value])


def confidence_element(value: str | None) -> MembraneElement:
    """單一 confidence 值 → MembraneElement。

    value ∈ contrasts → SignalPosition（格內）；
    value is None（來源未評估信心）→ NoisePosition(indeterminate)（格外殘餘、
    aggregated=False＝單筆 presence 殘餘，承 S2／S3 缺值退路）。
    """
    if value is None:
        return MembraneElement(payload=None, position=NoisePosition(gap_kind="indeterminate"))
    return MembraneElement(payload=value, position=confidence_signal(value))


def confidence_reason_element(text: str) -> MembraneElement:
    """confidence_reason＝reserved 窗（明文開放、自由文字，§443）。"""
    return MembraneElement(payload=text, position=ReservedPassthrough())


def confidence_schema_fragment() -> dict:
    """input/output schema 的 confidence 片段（oneOf+const+description、缺值容 null）。

    與 _GLOSS 同源（零副本）；nullable＝缺值＝未評估（向後相容：舊資料 enum 值仍合法）。
    """
    return {
        "oneOf": [{"const": v, "description": _GLOSS[v]} for v in CONFIDENCE_CONTRASTS]
                 + [{"type": "null", "description": "未評估（來源未給信心）"}],
    }
```

> **I4 不適用 None payload**：`MembraneElement.__post_init__` 只對 `SignalPosition` 查 `payload ∈ contrasts`；None→NoisePosition 分支不觸發（S0 既有守衛無需改）。比照 S2/S3 NoisePosition payload 寬型。

### 3.2 單一來源收斂（消除 set/schema/註解多副本）

- `mcp/tools/snapshot_write_tool.py:15`：`VALID_CONFIDENCE = set(CONFIDENCE_CONTRASTS)`（import from `confidence_membrane`）。`:46,89` input schema confidence 改用 `confidence_schema_fragment()`（或其 oneOf 的非 null 子集，視 input 是否允許 null＝**input 不允 null**＝B 側寫嚴必填，見 §3.3）。
- 3 schema（`l1-output`/`snapshot`/`l2-output`）confidence 改 `oneOf+const+description`（與 `confidence_schema_fragment()` parity test 同源）；nullable（output/persist 容缺值）。
- 模型行註解 `# "high"|"medium"|"low"` 不再是唯一意義來源（仍可留作 IDE 提示，但真理在 `CONFIDENCE_CONTRASTS`）。

### 3.3 input schema 寫嚴（B 側 CWA、per-value desc）

> input＝消費端 LLM 寫進來的（snapshot_write/patch）＝**寫嚴、必填、不允 null**（缺值是 output/事實層的誠實課題，非允許 LLM 不填）。input 用 `confidence_schema_fragment()` 的**非 null oneOf 子集**（3 const+description）＋保留在 `required`。

`snapshot_write_tool.py:46,89`：`"confidence": {oneOf:[{const:"high",description:...},{const:"medium",...},{const:"low",...}]}`；`:128` 校驗沿用 `VALID_CONFIDENCE`。`snapshot_patch_tool.py` 同步。

### 3.4 資料模型誠實 `models/analysis.py`／`models/snapshot.py`（缺值容 None）

```python
# analysis.py
class Feature:        ... ; confidence: str | None   # None＝LLM 未評估（不自鑄 medium）
class L2Module:       ... ; confidence: str | None    # default 移除（見下註）
class Anomaly:        ... ; confidence: str | None
# snapshot.py
class FeatureSummary: ... ; confidence: str | None
class BlockSummary:   ... ; confidence: str | None    # default "medium" 移除
```

> **default 取捨（concept-review warning 修）**：原 `= "medium"`/`="low"` dataclass default＝「構造省略時靜默得 medium」＝**殘留自鑄路徑**，與 §0「自鑄不可構造」＋C3/C4 牴觸。故 **nullable 欄一律移除 dataclass default**（構造必須顯式傳值或 None）——「構造省略→自鑄」結構性消除。🟢 grep 驗全構造點皆顯式傳 confidence（`snapshot_store:428`／`l2_generator:162,182,257,277`），移 default 安全（plan 須處理 dataclass 欄序：無 default 欄須在有 default 欄前）。`pending_low_confidence`（`analysis.py:195`）＝既有 narrative 欄、與本軸無關，不動。

### 3.5 閉集 enum 缺值誠實化（A 側、生產端、S4 通則）

> **通則（S4 立、供 severity 等照抄）**：閉集 enum 在**來源（LLM/外部）未給**時，**不靜默自鑄 default**——parse 缺值→None，emit 時 None→`NoisePosition(indeterminate)`（§8.13 通則、復用 S2/S3）。**契約變更、characterization 先行。**

- **LLM-source parse 自鑄（病灶核心）**：`batch_reader.py:190,345`（L1）／`l2_generator.py:165,186`＋`257,277` 鄰近（L2 兩生成路徑，plan grep 全 `.get("confidence",...)` 點）：移除 `, "medium"`→缺值得 None。
- **反序列化向後相容**：`snapshot_store.py:432`（BlockSummary）`confidence=bdata.get("confidence")`（移 `, "medium"`）——舊快照無 confidence→None（誠實標「未評估」，非偽 medium；與 §3.7 nullable schema 一致）。
- emit 端（§3.6）None→NoisePosition(indeterminate)。

### 3.6 emit 膜投影（LLM-facing 核心）

**`analyze_tool.py:74-94`**（L1 features）：`"confidence": f.confidence` → `"confidence": confidence_element(f.confidence).to_json()`（值→Signal、None→Noise）；`confidence_marker`（mermaid 視覺）＝人類面、**保留不動**（out）。

**`analyze_changes_tool.py:50-65`**（`_feature_to_json`）：`"confidence": confidence_element(fs.confidence).to_json()`；`"confidence_reason": confidence_reason_element(...).to_json()`（reserved 窗）或維持既有 defensive 字串（plan 定；至少 confidence 走膜）。

**`edge_projection.py:48-60`**（name_match_ambiguous 升 confidence Signal）：
> **I4 約束（concept-review critical 修）**：`SignalPosition` 強制 `payload ∈ contrasts`（`primitive.py:108`）且**無 cardinality 欄**。故 confidence Signal element 的 `payload` 必須＝信心值本身（"low"），**不能**＝aggregate dict（dict ∉ contrasts→I4 拋）。正解＝confidence 作為**巢狀投影欄**（與 analyze_tool 把 feature.confidence 當欄位投影同模式），caller/methods/cardinality 留**載體 dict**（純事實、非 Signal payload）：
```python
"low_confidence_ambiguous": [
    {
        "caller": caller,
        "methods": dict(sorted(counts.items())),             # 基數保留（method→count）
        "cardinality": sum(counts.values()),                  # 此 caller 低信心邊總數
        "confidence": confidence_element("low").to_json(),    # value="low"（∈contrasts、I4 合法）＋position=signal
    }
    for caller, counts in sorted(ambiguous_counts.items())
]
```
> 要點：**confidence "low" 經 `confidence_element` 投影為巢狀欄（payload="low" I4 合法）；caller/methods/cardinality＝載體事實、非 Signal payload；復用 S2 座標、基數保留**。`prompts.py:60,67` 教學同步（confidence 軸結構化巢狀欄、非 raw 桶）。

### 3.7 schema 補完＋persistence（機械 additive）

- `l1-output.schema.json:62`／`snapshot.schema.json:25,42`／`l2-output.schema.json:44,125`：confidence enum → `confidence_schema_fragment()`（oneOf+const+description+null）。**nullable＝向後相容**（舊資料 enum 值仍過、缺值＝null 亦過）。
- `snapshot_store` confidence 序列化：read 容 None（`v.get("confidence")`）；write 照存（None→json null）。`structure_serializer`／`analyze_pipeline` 同步 None-容忍。
- fail-closed 寫入（`_write_snapshot`）隨新 schema 過；`audit_conformance` 對 nullable confidence 不誤報。

---

## 4. 不變量清單（S4 強制；每條一個「非法即拋」或 characterization 測試）

| # | 不變量 | 強制處 | 對應理論 |
|---|---|---|---|
| C1 | confidence 值 ∈ `CONFIDENCE_CONTRASTS` → SignalPosition(contrasts 全序) | `confidence_signal` ＋ `MembraneElement` I4（payload∈contrasts） | §181 三主軸／§8.10 B 側 |
| C2 | confidence 單一有序來源（high>medium>low）；consumers 衍生、零副本 | `CONFIDENCE_CONTRASTS` ＋ parity test（set/3 schema 同源） | §8.10 單一來源 |
| C3 | confidence 缺值（None）→ emit `NoisePosition(indeterminate)`、**非**自鑄 medium | `confidence_element` ＋ characterization（缺值→noise，非 medium） | §8.13 通則／F6 同構 |
| C4 | 生產端 parse 缺值不自鑄（`.get` 無 default fallback） | `batch_reader`/`l2_generator` ＋ characterization（缺 confidence→None） | §8.12 加法不減法（不偽造認識狀態） |
| C5 | confidence_reason＝reserved 窗（自由文字、非閉集） | `confidence_reason_element`→ReservedPassthrough | §443 reserved 現成／§8.13 |
| C6 | LLM-facing emit（analyze_tool/analyze_changes）confidence 經膜投影、無裸 enum | emit 走 `confidence_element` ＋ characterization | §8.2 B 側送達／本刀核心 |
| C7 | name_match_ambiguous 帶 confidence=low Signal **巢狀欄**（payload="low" I4 合法）＋caller/methods/cardinality 載體（基數保留、復用 S2 座標） | `edge_projection` ＋ characterization | §291/§357 U1（命名拆分碼裡長出的軸） |

> C3/C4 是 S4 立的「閉集 enum 缺值誠實化」通則核心（severity 照抄）；C1/C2 是 confidence Signal 地基；C5/C6/C7 是 B 側送達＋edge 面兌現。

---

## 5. 慣例萃取（S4 交付給 S5–S7 的可複用樣板補充）＋ 本刀 findings

S1 立五律（B 側）、S2 補 A 側、S3 補外部裁決。S4 補 **閉集 enum 缺值誠實化**慣例：
1. **閉集 enum 缺值退 NoisePosition(indeterminate)**：凡「B 側閉集 enum 在來源未給」→ 不自鑄 default、parse 缺值→None、emit None→NoisePosition(indeterminate)。**通則**：適用任何閉集 enum 面（severity/scope_state/diff_state…）。
2. **橫切主軸的 membrane 安置**：confidence/scope/provenance 等橫切主軸，membrane 安置於其**最權威產地**目錄（confidence→core/reading）；contrasts 全序唯一來源、consumers 衍生。
3. **input 寫嚴必填 vs output/persist 容缺**：input schema（消費端寫）不允 null（寫嚴）；output/persist schema 容 null（事實層誠實＝可缺）。同 fragment 的 null/非-null 子集分用。
4. **全序 contrasts**：confidence/severity＝全序（tuple 順序即序）；doubt＝圖。`SignalPosition.contrasts` 同型別容兩者（S0 primitive.py:20 已預示）。
5. **characterization 先行**：動既有 emit/缺值行為前先釘現狀（同 S1/S2/S3）。

**本刀 findings（記錄、交棒）：**
- **[F-severity-default（S3 交棒·本刀確證再交棒）]** `scanner:149,156` OSV 未給 severity→鑄 medium＝**vulnerability 軸**（非 confidence 軸，軸正交 §181）缺值自鑄，與 S3 已修 cvss 同 scanner 同類。**正解＝照抄 S4 本刀 C3/C4 通則**（severity `str|None`、缺值退 indeterminate）。**歸 vulnerability 補完**（S3 尾巴/獨立小刀），不進 confidence 刀。S4 立通則為其鋪樣板（連貫律正向，如 S2 為 S3 鋪退路）。
- **[F-confidence-marker]** `analyze_tool:84`/`analyze_pipeline:236` `build_confidence_marker`＝mermaid 視覺標記（人類面）；本刀保留（out）。若日後人類面整膜，與 confidence Signal 同源化。
- **[F-pending-low-confidence]** `analysis.py:195 pending_low_confidence`＝narrative 既有欄、與 confidence Signal 軸正交（是「待複核清單」非信心值），不動。

---

## 6. 測試策略

- **單元**（`tests/unit/core/reading/test_confidence_membrane.py`，新增）：C1（值→Signal contrasts 全序＋gloss）／C3（None→NoisePosition indeterminate、aggregated=False）／C5（reason→Reserved）／`confidence_element(v).to_json()` 形狀／`confidence_schema_fragment` oneOf+null／C2（`VALID_CONFIDENCE == set(CONFIDENCE_CONTRASTS)`、3 schema enum const 集 == CONFIDENCE_CONTRASTS parity）。
- **characterization 先行（§9.4）**：
  - **生產端缺值**（`batch_reader`/`l2_generator` 既有測更新＋新 case）：先釘現狀「缺 confidence→medium」（red baseline）→ flip：C4「缺 confidence→None」。
  - **emit**（`analyze_tool`/`analyze_changes_tool` 測）：confidence 經膜投影（值→signal、None→noise）、無裸 enum＝C6。
  - **edge**（`edge_projection` 既有 S2 測更新）：`low_confidence_ambiguous` 升 confidence=low Signal、基數保留＝C7。
- **schema/persistence**：confidence=None＋enum 值皆過 fail-closed schema 並 round-trip（向後相容）；`audit_conformance` 對 nullable confidence 不誤報；舊快照（confidence=enum、無 null）仍可讀。
- **連貫性回驗**：S0 `test_primitive.py`＋S1 doubt 全測＋S2 `test_noise_position.py`/`test_edge_*`＋S3 vulnerability 全測仍綠（純加法於 primitive＋新檔；既有改動＝confidence emit/缺值/schema 形狀，由其自身 characterization 圈住）。
- **執行**：`cd the_door && PYTHONUTF8=1 python -m pytest -q`。驗收＝S3 基線 1509＋新測、零回歸（除 §6 列舉 characterization/schema 有意更新）。

---

## 7. 對 S5（scope）的慣例外推回驗 ★（連貫律落點）

> 目的：拿 S5 真實標的（`scope.py:32 scope_state`）當試金石，確認 S0+S1+S2+S3+S4 萃取的慣例夠 S5 用、不返工。

S5＝scope 軸（三主軸之一，§181：in/out/unrecognized）。逐點驗：
- **`{domain}_membrane.py` 樣板**：S5 建 `scope_membrane.py`（安置於 scope 產地 `core/scope`，同 doubt）。scope_state 走 B 側 Signal（in/out 封閉）——**S1 doubt 樣板＋S4 confidence 全序樣板直接適用**。✓
- **格外殘餘（unrecognized）**：scope 有 `unrecognized`＝**格外殘餘**（§278 表 scope「out/unrecognized」）→ 走 NoisePosition——**S2 A 側慣例＋S4 缺值退路復用**。scope 同時有格內（in/out Signal）＋格外（unrecognized Noise）＝S1（全 Signal）與 S2（全 Noise）的合體，兩慣例皆已備。✓
- **閉集 enum 缺值（C3/C4 通則）**：scope_state 若有「未判定」缺值→ 照抄 S4 C3/C4（缺值退 indeterminate、不自鑄）。✓
- **單一來源**：scope_state 值集若散落→ 照 S4 C2 收斂為 `SCOPE_CONTRASTS`。✓
- **fact-finder**：scope＝Signal（操作位置）非裁決，無處方欄（S3 V5/S0 I2 延續）。✓

**回驗結論**：S0+S1+S2+S3+S4 慣例對 S5 充分；S5 只需把 scope enum 走 Signal 樣板（格內 in/out）＋unrecognized 走 NoisePosition（格外、復用 S2）＋缺值照 S4 通則。**零預見返工。**

---

## 8. spec 完成後 7 點審查（種子檔 §9.4；第 4 點 grep 已驗）

1. **單一職責**：`confidence_membrane` 只管「confidence 值→position＋有序來源」；emit 各點只多一層膜投影；生產端只多「缺值不自鑄」。✓
2. **介面最小**：新增 1 模組（`CONFIDENCE_CONTRASTS`＋4 工廠＋1 schema fragment）；模型放寬 1 軸型別（str→str|None）、無新增軸（confidence_reason 既有）。
3. **可測**：純值物件＋純函式＋parse 可餵缺值 dict；C1-C7 皆可斷言。✓
4. **API 名 grep 驗真**（file:line 在 §2）：`VALID_CONFIDENCE`/`snapshot_write_tool` enum✓／`analyze_tool:82`/`analyze_changes_tool:61`✓／`batch_reader:190,345`/`l2_generator:165,186` `.get`✓／`edge_projection:58 low_confidence_ambiguous`✓／`l1-output`/`snapshot`/`l2-output` schema confidence✓／`MembraneElement`/`SignalPosition`/`NoisePosition`/`ReservedPassthrough`/`to_json`✓。**無虛構 API。** **無循環 import**：`confidence_membrane`→`core.membrane`（單向，core.membrane 不反向依賴）；consumers→`confidence_membrane`。
5. **錯誤路徑**：C1（值∉contrasts→`_GLOSS[value]` KeyError＝防呆，正常經 input enum 守住）；I4（payload∉contrasts→ValueError，S0 沿用）；缺值→None→Noise（非 error）。
6. **向後相容**：`confidence_membrane` 純加法；confidence `str→str|None`＝放寬（舊必填值仍合法）；schema nullable＋per-value desc＝放寬約束（舊 enum 值仍過、缺值 null 亦過）。**有意契約變更**＝emit 形狀（裸 enum→{value,position}）＋生產端缺值（medium→None）＋edge 桶升 Signal＝characterization 見證。viewer 前端＝**人類面 out**（confidence_marker 保留）。
7. **文件**：結構化、exact code、file:line、零佔位符；plan 線性相依時引本 spec §3.x 不重貼。

---

## 9. 交付物（plan 階段拆 task 用）

> **plan task 結構（concept-review Feasibility 修）**：S4 涵蓋兩正交課題＋大 blast radius，plan 須讓兩課題 task **各自 red→green、不交纏**，建議依賴序：
> **(地基)** 交付物 1（confidence_membrane＋有序來源）→ **(A 側·事實層)** 交付物 2+4+7-persist（模型 nullable＋生產端/反序列化缺值誠實化＋schema nullable，characterization 圈缺值）→ **(B 側·emit 層)** 交付物 3+5+6（input desc＋output 投影＋edge 升 Signal，characterization 圈 emit 形狀）。**A 側先（模型/schema 就緒容 None）於 B 側投影前**，否則 emit None 撞未放寬型別/schema（同 S3 Task2 先於 Task4 之理）。

1. `core/reading/confidence_membrane.py`（`CONFIDENCE_CONTRASTS`＋`confidence_signal`/`confidence_element`/`confidence_reason_element`/`confidence_schema_fragment`）＋`tests/unit/core/reading/test_confidence_membrane.py`。
2. `models/analysis.py`／`models/snapshot.py`（confidence `str→str|None`，**移除 dataclass default**＝消自鑄路徑）。
3. 單一來源收斂：`snapshot_write_tool.py:15`（`VALID_CONFIDENCE` 衍生）＋`:46,89`／`snapshot_patch_tool` input schema per-value desc。
4. 生產端缺值誠實化：`batch_reader.py:190,345`／`l2_generator.py:165,186`＋`257,277` 鄰近（plan grep 全 `.get("confidence",...)`）／`snapshot_store.py:432`（反序列化向後相容）（移 `, "medium"`）＋characterization 更新。
5. emit 膜投影：`analyze_tool.py:82`／`analyze_changes_tool.py:61`（confidence 走 `confidence_element`）＋characterization。
6. edge：`edge_projection.py:58`（`low_confidence_ambiguous` 升 confidence Signal）＋`prompts.py:60,67` 教學同步＋characterization（更新 S2 既有測）。
7. schema 補完：`l1-output`/`snapshot`/`l2-output`.schema.json（confidence oneOf+const+desc+null）＋parity test＋`snapshot_store`/`structure_serializer`/`analyze_pipeline` None-容忍＋既有測更新。
8. ~~viewer 前端~~＝**無交付物**（人類面 out、confidence_marker 保留；plan 須 grep 前端 confidence 用點確認零必要隨動）。

**驗收**：全測零回歸（除 §6 列舉 characterization/schema 有意更新）、confidence 值→Signal 全序（C1）、單一來源 parity（C2）、缺值→NoisePosition 非自鑄（C3/C4）、reason→Reserved（C5）、emit 無裸 enum（C6）、name_match_ambiguous 升 Signal（C7）、S0/S1/S2/S3 全測仍綠。

**S4 完成 → 進 S5（scope）spec**：起前重跑種子檔 §9.2 理論重錨、讀 S1 spec §5（B 側樣板）＋S2 spec §3.3（A 側殘餘）＋本檔 §3.1（全序 Signal 樣板）／§5（缺值通則）／§7（對 S5 回驗點）。
