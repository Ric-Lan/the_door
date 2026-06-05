# S2 spec：NoisePosition 首落地（edge_projection F5 殘餘桶 retrofit）

> **日期**：2026-06-05　**狀態**：spec（pre-plan，寫前已對真實碼 spike）　**性質**：乙案（膜模型）重塑 campaign 的 **NoisePosition 首落地刀**（S2），承 S0 膜 primitive ＋ S1 doubt 慣例。
> **承接**：S0 spec `docs/superpowers/specs/2026-06-05-S0-membrane-primitive-spec.md`（base＋Signal＋Reserved 已實作 merged；§3a 已定 NoisePosition 方向＝純殘餘描述子）；S1 spec `docs/superpowers/specs/2026-06-05-S1-doubt-throughline-spec.md`（§5 慣例樣板、§7 對 S2 回驗）；理論定稿＝種子檔 §8.13（§8.3 殘餘格三件、§8.8 F1 gap-kind 優先序、§8.14 F5 病灶診斷）。
> **分刀**：S2＝本檔（NoisePosition 型別＋edge F5 retrofit）。S3＝RelayedVerdict 首落地（vulnerability cvss）。S4＝confidence（含本刀延後的 `name_match_ambiguous` 信心位置）。順序 S0→S1→S2→…。
> **連貫律（使用者 2026-06-05 立）**：對前階段＝§0 回核 S0/S1＋驗 S1 §7 對 S2 的外推成立；對後階段＝§7 對 S3（RelayedVerdict）的慣例外推回驗。

---

## 0. 理論重錨（種子檔 §9.2 強制；每條釘到一個 S2 決定，防漂移）

寫前已逐項回核種子檔 §8.3/§8.8/§8.10/§8.13/§8.14 ＋ S0 spec §3a ＋ S1 spec §5/§7。下表把每條約束釘到具體決定：

| 理論約束（出處） | S2 如何遵守 |
|---|---|
| **per-value 切法**（§8.13 勘誤）：格內/格外界線切在「值」 | edge `resolution` 5 值**逐值分類**：`scope_rule`/`import_alias`/`name_match`＝格內保留；`skipped_dynamic`＝**格外殘餘**（→NoisePosition）；`name_match_ambiguous`＝**格內低信心**（confidence 軸，非 gap-kind→S4，§8.14 line 285）。 |
| **殘餘格恆帶三件**（§8.3）：`性質(gap_kind)＋基數(cardinality)＋比例(proportion)` | `skipped_dynamic` 殘餘經 `NoisePosition(gap_kind="indeterminate", cardinality, proportion, aggregated=True)` emit。S0 §3a 不變量「aggregated ⟹ cardinality ∧ proportion」型別強制。 |
| **加法不減法（A 側／OWA 讀寬）**（§8.12 修正②、§8.14 line 271/273）：讀出殘餘永不減法 | **修 F5 兩處偷渡減法**：①`set` 去重丟基數 → 改帶**真實計數**（不去重）；②兩 gap-kind 併一桶丟座標 → 改**按 resolution-kind 分流**（座標分明）。純加法：輸出資訊量只增。 |
| **gap-kind＝單值優先序**（§8.8 F1）：`corrupt>indeterminate>evolutionary>reserved`、知識上被迫 | gap_kind 優先序集＝**膜核心單一來源** `GAP_KIND_PRIORITY`（住 `core/membrane/primitive.py`）；`NoisePosition` 型別驗 `gap_kind ∈` 之。edge 域只觸發 `indeterminate` 一種（`skipped_dynamic`）；多 gap-kind 共現的優先序解析 edge 不觸發、留 S3+ 首觸發者實例化（不預建死碼）。 |
| **fact-finder**（§8.2 A；§8.13-O1）：禁自鑄裁決 | NoisePosition **無** score/risk/處方欄（純殘餘描述子）；S2 不引入任何裁決。base `MembraneElement` 已無裁決欄（I2）。 |
| **生成性／型驅動**（§8.11）：make illegal states unrepresentable | `NoisePosition.__post_init__` 強制 `aggregated ⟹ cardinality∧proportion`、`gap_kind ∈ GAP_KIND_PRIORITY`、`cardinality ≥ 0`、`0 ≤ proportion ≤ 1` → **「不帶基數不能 emit 殘餘」**（§8.13-T）結構性成立。 |
| **provenance＝唯一淨新增軸**（§8.13-O3） | S2 **不**碰 provenance/版本戳（S7）。edge 殘餘無 provenance 需求。 |
| **B 操作位置 vs A 殘餘**（§8.10）：膜兩側 | S1 走 B 側（Signal 操作位置）；**S2 首次走 A 側**（NoisePosition 殘餘描述子）。慣例樣板（S1 §5）形狀沿用，差別只在 position 變體（Signal→Noise）＋新增「聚合必帶基數比例」不變量——**坐實 S1 §7 對 S2 的外推**。 |
| **誠實界線**（§8.11） | S2 只強制**結構**合規（殘餘帶基數比例、gap_kind 合法）；gap_kind 歸類是否語意正確（skipped_dynamic 真是 indeterminate）仍靠人＋test。型管形狀、管不到判斷。 |

**LLM-facing 界定（本 spec 範圍的決定性依據，§8.14／todo_output_direction_assessment）**：campaign＝全部 **LLM-facing** 輸出面。edge 殘餘的 LLM-facing 面**兩處**（🟢 grep/read 驗）：
- **① 結構（payload）**：`project_edges_for_prompt` → `batch_reader._build_payload`（`:301,307`）→ payload 欄位 → `:312 json.dumps` → `provider.complete`（`:330-332`）＝LLM 直讀。
- **② 教學（prompt）**：`core/llm/prompts.py:45-65 L1_SYSTEM_PROMPT` **明文教 LLM 如何讀 `aggregate_call_hints`**——且現行教學**自己把兩 gap-kind 講成一桶**（`:57`「無法精確定位的方法名（包含高 fanout 與動態 dispatch 來源）」）＝F5 病灶②**下傳到 prompt 層**。膜論旨（意義靠結構、送達消費端 LLM）要求**結構與教學同步重塑**：分流後 prompt 須教 LLM 讀新殘餘（indeterminate vs low_confidence_ambiguous、基數、佔比）。**故 prompt 教學在 IN。**

**`audit_conformance`（`snapshot_store.py:260`）＝OUT**：grep 全 src **零消費者**（未接任何 MCP 工具/CLI），非 LLM-facing emit 面、且其 corrupt 在 store 三處理不一致（§8.14 line 292）是更大的獨立關切 → 不在本刀。

---

## 1. 範圍（in / out）

### S2 做（in）— NoisePosition 型別 ＋ edge F5 LLM-facing 殘餘 retrofit
1. **膜 primitive 擴 NoisePosition 變體**：`core/membrane/primitive.py` 加 `NoisePosition`（S0 §3a 形狀）＋膜核心單一來源 `GAP_KIND_PRIORITY`；擴 `Position` union（3 變體）＋ `_position_to_json`（noise 分支）。純加法、不動既有 2 變體與 I1-I4。
2. **edge 膜詞彙單一來源**：新增 `core/llm/edge_membrane.py`（慣例＝`{domain}_membrane.py`，S1 §5）。提供：resolution-kind→gap_kind 單一來源映射、`indeterminate` 的極短 gloss、`skipped_dynamic` 殘餘→`NoisePosition` element 工廠。
3. **F5 retrofit（修兩偷渡減法）**：`project_edges_for_prompt` 回傳的殘餘改：
   - `skipped_dynamic` →**按 caller 聚合、帶真實計數**，經 `MembraneElement(payload={"caller",..,"methods":{m:count}}, NoisePosition(indeterminate,cardinality,proportion,aggregated))` 投影。
   - `name_match_ambiguous` →**與上者座標分流**（不再併桶）、**基數保留**（不去重）；但**不**包 position（格內低信心、其 confidence Signal＝S4）。
   - `kept`（三格內 resolution）＝不變。
4. **prompt 教學同步重塑**：`core/llm/prompts.py L1_SYSTEM_PROMPT` 的 `aggregate_call_hints` 教學段（`:45-65`）改教新殘餘——把現行「一桶」敘述拆為 `indeterminate`（動態派發、帶基數佔比）與 `low_confidence_ambiguous`（高 fanout 裸名、低信心）兩座標，保留「不寫成依賴」紀律。**這是 S2 膜論旨的核心兌現**（結構＋教學同步）。
5. **契約變更 → characterization 先行**（§6）：`project_edges_for_prompt` 回傳形狀變更（殘餘桶 `dict[str,list]` → 結構化），由 characterization test 見證；`batch_reader` payload 鍵 `aggregate_call_hints`→`aggregate_call_residue`（形狀＋語意變、LLM 資訊增益）。

### S2 不做（out）
- **`audit_conformance` gap-kinds（corrupt/evolutionary）**：未接任何消費者＝非 LLM-facing emit 面（§0 證）；corrupt 在 store 三處理不一致是獨立關切。留作後續（其首個 LLM-facing 接點出現時，或專屬「store corrupt 統一」刀）。
- **`name_match_ambiguous` 的 confidence Signal**：S2 只**保其基數、分其座標**（A 側殘餘忠實度）；其「high/medium/low 信心位置」＝**S4（confidence 軸）**。S2 不建 confidence Signal（不越 S4 軸）。
- **kept 邊的 confidence/scope Signal**（§8.14：F4 `_resolve` 主軸＝confidence＋scope）＝S4/S5。S2 不碰 kept 邊的 position（維持 bare dict）。
- **多 gap-kind 共現的優先序解析**：edge 域只 `indeterminate` 一種、不觸發。`GAP_KIND_PRIORITY` 立為單一來源供 S3+ 用，但解析邏輯由**首個真觸發共現的試點**實例化（不預建死碼，§8.4 剔除過頭設計）。
- **provenance / 版本戳（S7）**、**任何 schema 檔**（edge prompt 殘餘無持久化 per-value schema）。

---

## 2. Spike 事實（2026-06-05 對真實碼，file:line 已驗）

| 層 | 檔案:line | 事實 |
|---|---|---|
| resolution 來源 | `core/extraction/edge_builder.py:46-49,401,411,427` | resolution 閉集＝`scope_rule`/`import_alias`/`name_match`/`name_match_ambiguous`(>`FANOUT_THRESHOLD`)/`skipped_dynamic`(dynamic dispatch)。docstring＝單一權威列舉。 |
| F5 病灶 | `core/llm/edge_projection.py:15,26,31,37` | `_AGGREGATED_RESOLUTIONS={name_match_ambiguous, skipped_dynamic}` **併一桶**；`hint_sets[caller]=set()` **去重丟基數**；回傳 `(kept, hints:dict[str,list[str]])`。 |
| 消費①結構 | `core/reading/batch_reader.py:290-301,307,312,330-332` | edge_dicts 取 `{from,to,type,resolution}`；`project_edges_for_prompt` 結果塞 payload `edges`＋`aggregate_call_hints`；`json.dumps`→`provider.complete` 送 LLM。**LLM-facing✓。** |
| 消費②教學 | `core/llm/prompts.py:45-65` | `L1_SYSTEM_PROMPT` 教 LLM 讀 `aggregate_call_hints`；`:57` **明文把兩 gap-kind 講成一桶**＝病灶②下傳 prompt。**IN（同步重塑）。** |
| 既有測試 | `tests/unit/core/llm/test_edge_projection.py:30-71`（9 測）、`tests/property/test_edge_projection_properties.py`（4 測）、`tests/integration/test_batch_reader_projection.py`（釘 payload 鍵`aggregate_call_hints`+形狀）、`tests/unit/core/llm/test_prompt{s_resolution,_resolution_section}.py`（釘 prompt 含該詞） | unit `test_mixed_resolutions_partial_drop:61-71` **直接見證併桶**（`{"a":["send","write"]}`）；property `test_hint_method_lists_sorted_and_unique:50-55` **直接編碼病灶①去重**（`len(names)==len(set(names))`）→ 此 property 須**移除/改寫**（去重正是要修的）；`test_idempotent:46` `hints2=={}` → 改空殘餘。**全為 characterization 標的、隨契約有意更新。** |
| audit（OUT 證） | `core/diff/snapshot_store.py:260-285` | `audit_conformance()->list[dict]` 唯讀；grep 全 src **零外部呼叫**＝未接 LLM-facing 面 → out。 |
| S0 primitive | `core/membrane/primitive.py:14-92` | `SignalPosition`/`ReservedPassthrough`/`MembraneElement`/`to_json`/`_position_to_json`／I4（Signal payload∈contrasts）。`Position` union 待擴。 |

**spike 結論**：edge 殘餘 LLM-facing 面＝1 純函式（`project_edges_for_prompt`）＋其 1 消費者（batch_reader）；off-grid 殘餘只 `skipped_dynamic`(→indeterminate)；NoisePosition（S0 §3a 形狀）足夠承載、無預見返工。**S1 §7 對 S2 的外推（樣板適用、唯一新增＝聚合帶基數比例不變量）實證成立。**

---

## 3. 設計（exact code；落點標注）

### 3.1 膜 primitive 擴 `NoisePosition`（`core/membrane/primitive.py`，純加法）

> 加在 `ReservedPassthrough` 之後、`Position` union 之前。S0 §3a 形狀逐字落地＋型驅動守衛。

```python
# === gap-kind 優先序：膜核心單一來源（種子檔 §8.8 F1）===
# 知識上被迫的偏序：corrupt 讀不出 → 無法得知是否也 evolutionary，故 corrupt 優先。
# 多 gap-kind 共現時取最高優先者（單值、非子集）。edge 域只觸發 indeterminate；
# 共現解析由首個真觸發的試點實例化（S3+），此處只立來源 + 合法集。
GAP_KIND_PRIORITY: tuple[str, ...] = ("corrupt", "indeterminate", "evolutionary", "reserved")


@dataclass(frozen=True)
class NoisePosition:
    """A 側（OWA／格外／殘餘）：值落在契約閉集之外的純殘餘描述子。

    非裁決、非分數——只報「殘餘的性質(gap_kind)＋量(cardinality)＋佔比(proportion)」
    （種子檔 §8.3：殘餘格恆帶三件）。聚合殘餘（多筆併報）必帶基數與比例，
    否則就是偷渡減法（§8.12／§8.14）——型別強制，不帶基數不能 emit 聚合殘餘。

    is_flag＝presence-only 殘餘（僅標記存在、無基數語意，如單筆 off-grid 哨兵）。
    """
    gap_kind: str | None = None          # ∈ GAP_KIND_PRIORITY（或 None＝未分類旗標）
    cardinality: int | None = None       # 殘餘筆數（真實計數、不去重）
    proportion: float | None = None      # 佔全體比例 [0,1]
    is_flag: bool = False                # presence-only（無基數語意）
    aggregated: bool = False             # 是否為多筆聚合殘餘

    def __post_init__(self) -> None:
        if self.gap_kind is not None and self.gap_kind not in GAP_KIND_PRIORITY:
            raise ValueError(
                f"NoisePosition.gap_kind {self.gap_kind!r} 不在 GAP_KIND_PRIORITY "
                f"{GAP_KIND_PRIORITY!r}（種子檔 §8.8 F1 單一來源）"
            )
        if self.cardinality is not None and self.cardinality < 0:
            raise ValueError("NoisePosition.cardinality 不可為負")
        if self.proportion is not None and not (0.0 <= self.proportion <= 1.0):
            raise ValueError("NoisePosition.proportion 必須在 [0,1]")
        if self.aggregated and (self.cardinality is None or self.proportion is None):
            raise ValueError(
                "聚合殘餘必帶 cardinality 與 proportion（不偷渡減法，§8.3/§8.12）"
            )
```

`Position` union 與 `_position_to_json` 擴（差異部分）：
```python
# Position union——S2 階段 3 變體；S3 加 RelayedVerdict。
Position = SignalPosition | ReservedPassthrough | NoisePosition
```
```python
def _position_to_json(position: Position) -> dict:
    if isinstance(position, SignalPosition):
        ...                                  # 不變
    if isinstance(position, ReservedPassthrough):
        return {"kind": "reserved"}
    if isinstance(position, NoisePosition):
        return {
            "kind": "noise",
            "gap_kind": position.gap_kind,
            "cardinality": position.cardinality,
            "proportion": position.proportion,
            "is_flag": position.is_flag,
            "aggregated": position.aggregated,
        }
    raise TypeError(f"未知 position 變體：{type(position).__name__}")
```
門面 `core/membrane/__init__.py` 加 `NoisePosition`、`GAP_KIND_PRIORITY` 至 import 與 `__all__`。

> **I4 不適用 Noise**（`MembraneElement.__post_init__` 只對 SignalPosition 查 payload∈contrasts）＝正確：殘餘 payload 非閉集值。S0 既有守衛無需改。

### 3.2 edge 膜詞彙單一來源 `core/llm/edge_membrane.py`（新增）

> 慣例樣板（S1 §5）：一個 through-line 一個 `{domain}_membrane.py`。edge 域走 A 側（Noise）。resolution→gap_kind 是**域內單一來源**（S1 doubt 走 `DoubtLifecycle`；edge 走本檔映射，源自 `edge_builder` resolution 語意）。

```python
"""edge 線的膜詞彙：把 edge resolution 的「格外殘餘」結構化為 NoisePosition。

per-value 切法（種子檔 §8.13）：edge resolution 5 值中，skipped_dynamic 是唯一
格外殘餘（dynamic dispatch → 知識上 indeterminate）；name_match_ambiguous 是格內
低信心（confidence 軸，S4），不在此（不歸 gap_kind）。

聚合殘餘必帶基數比例（§8.3）：殘餘按 caller 聚合，cardinality＝真實計數（不去重、
修 F5 病灶①），proportion＝佔全體 edge 比例。S2-S7 照此樣板各建 {domain}_membrane.py。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, NoisePosition

# resolution → gap_kind 單一來源（只列格外殘餘；格內/低信心 resolution 不在此）。
# skipped_dynamic＝dynamic dispatch context（edge_builder.py:49）→ 知識上 indeterminate。
_RESIDUE_GAP_KIND = {
    "skipped_dynamic": "indeterminate",
}

# indeterminate 殘餘的極短 gloss（人類意圖殘餘，語法捕不到）。
_GAP_KIND_GLOSS = {
    "indeterminate": "動態派發、無法靜態解析的呼叫（保留為不確定，非遺漏）",
}


def is_residue(resolution: str) -> bool:
    """此 resolution 是否為格外殘餘（→NoisePosition）。"""
    return resolution in _RESIDUE_GAP_KIND


def indeterminate_residue_element(
    caller: str, method_counts: dict[str, int], total_edges: int
) -> MembraneElement:
    """skipped_dynamic 殘餘（單一 caller、聚合）→ NoisePosition element。

    payload＝殘餘本體（caller＋逐 method 計數，基數保留）；
    position＝NoisePosition（gap_kind=indeterminate, cardinality=Σcount, proportion）。
    """
    cardinality = sum(method_counts.values())
    proportion = (cardinality / total_edges) if total_edges else 0.0
    return MembraneElement(
        payload={"caller": caller, "methods": dict(method_counts), "gloss": _GAP_KIND_GLOSS["indeterminate"]},
        position=NoisePosition(
            gap_kind="indeterminate",
            cardinality=cardinality,
            proportion=proportion,
            aggregated=True,
        ),
    )
```

### 3.3 F5 retrofit `core/llm/edge_projection.py`（修兩偷渡減法）

emit 形狀改動（**契約變更、characterization 先行**）：殘餘桶 `dict[str,list[str]]`（併桶、去重）→ 座標分流＋基數保留的結構化殘餘。

```python
from __future__ import annotations

from collections import Counter

from the_door.core.llm.edge_membrane import indeterminate_residue_element, is_residue

_AMBIGUOUS = "name_match_ambiguous"   # 格內低信心（confidence 軸＝S4）


def project_edges_for_prompt(
    edges: list[dict],
) -> tuple[list[dict], dict]:
    """投影 edges 供 prompt 消費（膜化殘餘）。

    回傳 (kept, residue)：
      kept＝格內 resolution 邊（不變）。
      residue＝座標分明的格外/低信心殘餘（修 F5：基數保留、不併桶）：
        {
          "indeterminate": [<NoisePosition element .to_json()>, ...],  # skipped_dynamic
          "low_confidence_ambiguous": {caller: {method: count}},       # name_match_ambiguous（S4 升 Signal）
        }
    """
    kept: list[dict] = []
    indeterminate_counts: dict[str, Counter] = {}      # caller -> Counter(method)
    ambiguous_counts: dict[str, Counter] = {}          # caller -> Counter(method)
    total = len(edges)

    for edge in edges:
        res = edge.get("resolution")
        if is_residue(res):                            # skipped_dynamic（格外殘餘）
            caller = edge["from"]
            indeterminate_counts.setdefault(caller, Counter())[_method_name_from_to(edge["to"])] += 1
        elif res == _AMBIGUOUS:                         # 格內低信心
            caller = edge["from"]
            ambiguous_counts.setdefault(caller, Counter())[_method_name_from_to(edge["to"])] += 1
        else:
            kept.append(edge)

    residue = {
        "indeterminate": [
            indeterminate_residue_element(caller, dict(counts), total).to_json()
            for caller, counts in sorted(indeterminate_counts.items())
        ],
        "low_confidence_ambiguous": {
            caller: dict(counts) for caller, counts in sorted(ambiguous_counts.items())
        },
    }
    return kept, residue


def _method_name_from_to(to_node: str) -> str:
    """Extract bare method name from a node_id like 'Class.method'."""
    if "." in to_node:
        return to_node.rsplit(".", 1)[-1]
    return to_node
```

`batch_reader.py:307` payload 鍵 `aggregate_call_hints` → 改名 `aggregate_call_residue`（值＝新 residue dict；鍵改名見證契約變更，LLM 資訊增益＝基數＋座標＋gap_kind）。`:301` 解包 `kept_edges, residue`。

> **真驗 A 側整膜**：`indeterminate` 殘餘經 `NoisePosition` 出 `{value, position:{kind:"noise", gap_kind, cardinality, proportion, aggregated}}`——告訴消費端 LLM「這是 N 筆動態派發殘餘、佔比 p、刻意保留為不確定」。對照 F5 舊輸出（一桶去重字串、看不出量與性質）＝**坐實 §8.14「修兩偷渡減法」**。

### 3.4 prompt 教學同步重塑 `core/llm/prompts.py`（`L1_SYSTEM_PROMPT`）

> 結構變了，教 LLM 怎麼讀的話也要變（膜論旨：意義靠結構送達消費端）。改寫 `:45-65` 的 `aggregate_call_hints` 段——把現行「一桶」敘述（`:57`「無法精確定位的方法名（包含高 fanout 與動態 dispatch 來源）」）拆為兩座標：

教學要點（散文由實作者依風格落筆，要點固定）：
- 欄位改名 `aggregate_call_residue`，含兩鍵：
  - `indeterminate`：每筆＝`{value:{caller,methods:{方法:次數},gloss}, position:{kind:"noise", gap_kind:"indeterminate", cardinality:N, proportion:p, aggregated:true}}`。語意＝「動態派發、靜態無法解析的呼叫，**保留為不確定（非遺漏）**；caller 共 N 筆、佔本批 edge 比例 p」。
- `low_confidence_ambiguous`：`{caller:{方法:次數}}`。語意＝「裸名高 fanout 匹配、低信心」。
- **保留既有紀律**（逐字搬，不鬆動）：兩者皆**不可**當「呼叫了某 feature」依據、**不可**據以加 `depends_on`；description 必須提時限泛稱、寧可不提。
- LLM 可用基數/佔比判斷「殘餘是否顯著」（如 50 筆 indeterminate vs 1 筆），但仍不寫成依賴——**資訊增益用於更準的保守判斷，非放寬紀律**（§8.2 fact-finder：結構化讓判斷更準、不替它預先裁決）。

> 對應測試：`test_prompt{s_resolution,_resolution_section}.py` 斷言由「prompt 含 `aggregate_call_hints`」更新為含 `aggregate_call_residue` ＋ 兩座標詞（characterization 式：見證教學契約同步變更）。

---

## 4. 不變量清單（S2 強制；每條一個「非法即拋」或 characterization 測試）

| # | 不變量 | 強制處 | 對應理論 |
|---|---|---|---|
| N1 | 聚合殘餘必帶 `cardinality` ∧ `proportion`（不偷渡減法） | `NoisePosition.__post_init__` | §8.3 殘餘三件／§8.12 加法不減法 |
| N2 | `gap_kind ∈ GAP_KIND_PRIORITY`（單一來源、非法即拋） | `NoisePosition.__post_init__` | §8.8 F1 優先序單一來源 |
| N3 | `cardinality` 真實計數（不去重）、`proportion=cardinality/total` | `edge_membrane.indeterminate_residue_element` ＋ characterization（50 筆同名不折成 1） | §8.14 F5 病灶①修方 |
| N4 | 兩殘餘 resolution-kind **座標分流**（不併桶） | `project_edges_for_prompt` residue 兩鍵 ＋ characterization | §8.14 F5 病灶②修方 |
| N5 | NoisePosition **無** score/risk/處方欄（純殘餘描述子） | 型別**缺**該欄（結構性，承 S0 I2） | fact-finder：禁自鑄裁決 |

> N3/N4 是 S2 最關鍵兩條（直接修 F5 兩偷渡減法）；N1/N2 是 NoisePosition 型別地基（S3+ 共用）。

---

## 5. 慣例萃取（S2 交付給 S3–S7 的可複用樣板補充）

S1 已立五律（`{domain}_membrane.py`／input 衍生／output 投影／schema parity／導出鎖）。S2 補 **A 側**慣例：
1. **A 側殘餘走 NoisePosition**：格外值（off-grid）→ `NoisePosition`，**必帶基數比例**（聚合時 `aggregated=True` 觸發型別強制）。
2. **gap_kind 單一來源**＝`GAP_KIND_PRIORITY`（膜核心）；各域 `{domain}_membrane.py` 提供 `resolution→gap_kind` 映射（域內單一來源）＋極短 gloss。
3. **per-value 分側分流**：同一欄的值按「格內 Signal／格外 Noise／低信心（confidence 軸）」分流，**座標分明、不併桶**。
4. **characterization 先行**：動既有 prompt/emit 形狀前先釘現狀（同 S1）。
5. （S3 將補 **RelayedVerdict** 慣例：evidence-bearing、無 evidence 退 `NoisePosition(indeterminate)`，見 §7。）

---

## 6. 測試策略

- **characterization 先行（§9.4）**：動 `project_edges_for_prompt` 契約前，先確認既有測試釘住併桶/去重現狀；retrofit 後更新為新 residue 形狀（基數＋座標＋gap_kind）＝**有意契約變更見證**。逐檔：
  - `tests/unit/core/llm/test_edge_projection.py`（9 測）：`test_mixed_resolutions_partial_drop` 等改讀新 residue 兩鍵；新增 N3（同名 50 筆→cardinality=50 非 1）、N4（同 caller skipped+ambiguous 分落兩鍵）case。
  - `tests/property/test_edge_projection_properties.py`（4 測）：`test_high_confidence_always_kept`/`test_ambiguous_and_dynamic_never_in_kept` **不變**（kept 語意未動）；`test_idempotent` 的 `hints2=={}` → 改「空殘餘」（`indeterminate==[] and low_confidence_ambiguous=={}`）；**`test_hint_method_lists_sorted_and_unique` 移除/改寫**——它直接斷言去重（`len==len(set)`），正是病灶①、不可保留；改為「indeterminate cardinality＝該 caller skipped_dynamic 真實筆數」的反向 property。
  - `tests/integration/test_batch_reader_projection.py`：payload 鍵 `aggregate_call_hints`→`aggregate_call_residue`＋形狀斷言更新（含 minimal mode 無此鍵的負斷言改鍵名）。
  - `tests/unit/core/llm/test_prompt{s_resolution,_resolution_section}.py`：斷言 prompt 含 `aggregate_call_residue` ＋兩座標詞（取代 `aggregate_call_hints`）。
- **單元**（`tests/unit/core/membrane/test_noise_position.py`）：N1（aggregated 缺 cardinality/proportion→ValueError）／N2（gap_kind 非法→ValueError、合法 4 值可構造）／cardinality 負→ValueError／proportion 越界→ValueError／`to_json` noise 鍵集；`is_flag` happy-path。
- **單元**（`tests/unit/core/llm/test_edge_membrane.py`）：`is_residue`（skipped_dynamic True、其餘 False）／`indeterminate_residue_element` 計數正確（同名不折）＋proportion＝cardinality/total＋`to_json` 形狀。
- **F5 修正 characterization**（`tests/unit/core/llm/test_edge_projection.py` 更新＋新 case）：
  - N3：同一 caller 同名 method 50 筆 skipped_dynamic → cardinality=50（**非 1**）。
  - N4：caller 同時有 skipped_dynamic＋name_match_ambiguous → 分落 `indeterminate`／`low_confidence_ambiguous` 兩鍵（不混）。
  - kept 三格內 resolution 不變；空輸入 → 兩鍵皆空。
- **連貫性回驗**：S0 `test_primitive.py`/`test_s1_coherence.py`＋S1 doubt 全測仍綠（純加法於 primitive＋新檔；唯一既有改動＝edge_projection 形狀，由其自身 characterization 圈住）。
- **執行**：`cd the_door && PYTHONUTF8=1 python -m pytest -q`。驗收＝S1 基線 1477＋新測、零回歸（除 edge_projection/property characterization 有意更新）。

---

## 7. 對 S3（RelayedVerdict）的慣例外推回驗 ★（連貫律落點）

> 目的：拿 S3 真實標的（vulnerability cvss）當試金石，確認 S0+S1+S2 萃取的慣例夠 S3 用、不返工。

S3＝`vulnerability_scanner.py` cvss → RelayedVerdict（evidence-bearing，S0 §3a／§2）。逐點驗：
- **`{domain}_membrane.py` 樣板**：S3 建 `vulnerability_membrane.py`，同「值→position 工廠」——position 變體＝RelayedVerdict（S3 建型，承 S0 §3a 形狀）。**S1 樣板結構＋S2 A 側慣例對 S3 適用**；差別只在 position 變體。✓
- **NoisePosition 退路復用**：S0 §3a 定「RelayedVerdict 無 evidence(vector) → 退 `NoisePosition(indeterminate)`」。**S2 已落地 NoisePosition(indeterminate)＝S3 退路現成可復用**，零預建。✓（S2 為 S3 鋪好退路，連貫律正向兌現）
- **gap_kind 單一來源**：S3 若觸發新 gap_kind（如 corrupt）已在 `GAP_KIND_PRIORITY`；多 gap-kind 共現的優先序解析若 S3 首觸發，則由 S3 實例化（S2 已立來源、未預建邏輯）。✓
- **characterization 先行**：S3 動 `vulnerability_scanner`/renderer emit＝契約變更→同 S2 用 characterization 圈住。✓
- **fact-finder（N5 復用）**：S3 移除 `_get_action` 自鑄處方（§8.13 勘誤「無處方變體」）；RelayedVerdict 帶 evidence＝轉述非自鑄。**S0 I2＋S2 N5「無裁決欄」對 RelayedVerdict 的 evidence 守衛是同源延伸**。✓

**回驗結論**：S0+S1+S2 慣例對 S3 充分；S3 只需新增 RelayedVerdict 型別（+evidence 守衛）並復用 S2 的 NoisePosition(indeterminate) 退路。**零預見返工。**

---

## 8. spec 完成後 7 點審查（種子檔 §9.4；第 4 點 grep 已驗）

1. **單一職責**：`NoisePosition` 只描述殘餘；`edge_membrane` 只管「edge 殘餘值→Noise」；`project_edges_for_prompt` 只多一層膜化投影。✓
2. **介面最小**：primitive 加 1 型別＋1 常數；`edge_membrane` 對外＝`is_residue`＋`indeterminate_residue_element`＋（內部 gloss/映射）。無多餘。
3. **可測**：純值物件＋純函式；N1-N5 皆可斷言。✓
4. **API 名 grep 驗真**（file:line 在 §2）：`project_edges_for_prompt`/`_AGGREGATED_RESOLUTIONS`/`_method_name_from_to`✓／`batch_reader._build_payload`(`:290-307`)/`provider.complete`✓／`edge_builder` resolution 5 值（`:46-49,401,411,427`）✓／`prompts.L1_SYSTEM_PROMPT` `aggregate_call_hints` 段(`:45-65`)✓／`audit_conformance`(`:260`、零消費者)✓／`MembraneElement`/`NoisePosition`(S0 §3a)/`SignalPosition`/`to_json`✓。**無虛構 API。** 另：**無循環 import**（🟢 驗）——`edge_membrane`→`core.membrane`；`edge_projection`→`edge_membrane`；`batch_reader`→`edge_projection`；`core.membrane` 不反向依賴 edge/llm。單向。
5. **錯誤路徑**：N1（聚合缺基數→ValueError）／N2（gap_kind 非法→ValueError）／cardinality 負・proportion 越界→ValueError／`_position_to_json` 未知變體→TypeError（S0 I3 沿用）。
6. **向後相容**：primitive＋edge_membrane 純加法（零既有碼改動、S0 2 變體與 I1-I4 不動）；`project_edges_for_prompt`＋payload 鍵＋prompt 教學＝**有意契約變更（三者同步）**，characterization/prompt-test 見證；唯一結構消費者＝batch_reader、唯一教學消費者＝L1 prompt，皆同步更新（grep 驗無第三方）。對 LLM＝資訊增益（基數＋座標＋gap_kind）＋教學同步，非靜默。
7. **文件**：結構化、exact code、file:line、零佔位符。

---

## 9. 交付物（plan 階段拆 task 用）

1. `src/the_door/core/membrane/primitive.py`（加 `GAP_KIND_PRIORITY`＋`NoisePosition`＋union＋`_position_to_json` noise 分支）＋`__init__.py` 門面擴。
2. `tests/unit/core/membrane/test_noise_position.py`（N1/N2＋cardinality/proportion 邊界＋to_json）。
3. `src/the_door/core/llm/edge_membrane.py`（resolution→gap_kind 單一來源＋gloss＋`is_residue`＋`indeterminate_residue_element`）。
4. `tests/unit/core/llm/test_edge_membrane.py`（工廠計數/proportion/to_json）。
5. `tests/unit/core/llm/test_edge_projection.py`（characterization：先釘併桶現狀 → 後改新 residue 形狀，N3/N4）＋`tests/property/test_edge_projection_properties.py` 斷言隨形狀更新。
6. `src/the_door/core/llm/edge_projection.py`（F5 retrofit）＋`src/the_door/core/reading/batch_reader.py`（`:301,307` 解包/payload 鍵改名）。
7. `src/the_door/core/llm/prompts.py`（`L1_SYSTEM_PROMPT` `aggregate_call_hints` 段→新殘餘教學，§3.4）。
8. 既有測試更新（characterization 見證契約/教學變更，§6）：`test_edge_projection.py`／`test_edge_projection_properties.py`（移除去重 property）／`test_batch_reader_projection.py`／`test_prompts_resolution.py`／`test_prompt_resolution_section.py`。

**驗收**：全測零回歸（除 §6 列舉的 characterization/property/prompt 斷言**有意更新**）、NoisePosition 聚合無基數不可構造（N1）、gap_kind 非法即拋（N2）、F5 殘餘帶真實基數（N3）、兩 gap-kind 座標分流（N4）、prompt 教學與結構同步（無「一桶」殘留）、S0/S1 全測仍綠。

**S2 完成 → 進 S3（RelayedVerdict／vulnerability cvss）spec**：起 S3 前重跑種子檔 §9.2 理論重錨、讀 S0 §3a（RelayedVerdict 方向＝evidence-bearing、無 evidence 退 NoisePosition）＋本檔 §5（A 側慣例）＋§7（對 S3 回驗點）。
