# S7 spec：provenance 主軸（版本戳持久化 ＋ produced_under/current/unknown Signal）

> **日期**：2026-06-06　**狀態**：spec（pre-plan，寫前已對真實碼 spike＋理論重錨＋目標/範圍/邊界對照理論釐清）　**性質**：乙案（膜模型）的**第三主軸**、且是**唯一淨新增軸**（§445：其餘皆 reshape 既有 bare enum；provenance 全棧缺席＝需新增版本戳）。承 S0 膜 primitive ＋ Finding A（`_write_snapshot` fail-closed 單一落盤口）＋ S5/S6/S8 慣例。
> **承接**：種子 §181（三主軸 provenance=current/legacy/unknown）／§283＋§U3（單版退化、**diff 才點亮**）／§390（unknown＝格內哨兵「格內對格外的命名橋」）／§5＋§398-O3（版本戳界線：既有快照 unknown、戳惠及未來）／§8.12（膜住 emission 邊界、持久化存事實）。
> **範圍性質**：本刀比 S4-S8 大——**唯一觸持久化的刀**（snapshot model + schema + write path = Finding A 地盤）＋衍生 ＋ 膜 ＋ 多 agent-facing emit 面。**一刀（不拆兩階段）**：plan 內部 task 排序處理風險（持久化→膜→emit）。

---

## 0. 理論重錨（種子 §9.2）＋ 目標/範圍/邊界對照原則

| 原則（出處） | 對 S7 約束 | 解消決策（spike 驗後） |
|---|---|---|
| **膜住 emission 邊界、非持久化**（§8.12/§352） | provenance 需持久化戳——違反否？ | **不違反**：戳＝**出生事實**（與 `commit_hash`/`timestamp`/`git_tags` 同類，snapshot 早已存出生事實）；膜＝emit 時**衍生** provenance 並投影。持久化存事實、膜在 emit 衍生投影。 |
| **三主軸格內、每值自帶意義**（§181/§390） | current/legacy/unknown 閉集 | → SignalPosition 3-val。**`unknown`＝格內哨兵真值（§390 命名橋）**，非 NoisePosition ⟹ **純 3-Signal、無 None 分支、無 NoisePosition**（缺戳直接映射到 `unknown` 真值——比 confidence/scope-nullable 更乾淨）。 |
| **fact-finder、禁自鑄裁決、上界**（§8.2A/O1） | 不可變裁決 | current/legacy/unknown ＝(戳 vs 常數) 機械事實比對；缺戳→unknown＝誠實缺席。**只報「produced_under vX vs current vY」、不說「baseline 過時/爛」**（後者＝越界裁決）。 |
| **寫嚴讀寬**（§8.13D/Finding A） | 戳寫 vs 讀 | 寫＝`create_snapshot` 蓋戳、`_write_snapshot` schema fail-closed（同 Finding A）；讀＝舊快照無戳→`unknown`、不拒。 |
| **O3 界線**（§5/§398） | 既有快照 unknown、戳惠及未來 | **邊界明文**：不承諾既有資料 current/legacy。**過渡緩解**：①S7 落地後**新舊立即可辨**（pre-S7 無戳=unknown vs post-S7=current＝diff 當天就點亮）②`extract --as-version` 回填戳。 |
| **§283/§U3：diff 才點亮、通用性＝處處良定義** | 單版退化、跨版承重 | **emit 面＝版本相會處（diff/incremental）＋ snapshot_list**。provenance 資訊量＝`SNAPSHOT_CONTRACT_VERSION` 維護紀律（契約不變→全 current＝真但低資訊；演進→點亮）；§5 前提＝基礎建設、契約演進時兌現（使用者已拍板接受）。 |
| **軸正交、不同縫別名**（§181/§197） | vs `inherited/affected`？ | **正交**：inherited/affected＝「本次增量有沒有重算」；provenance＝「在哪個契約出生」。inherited 可 current 亦可 legacy ⟹ provenance 是**疊加獨立軸**、不合併。 |
| **單一來源**（§8.10） | 契約錨點 | 專屬 `SNAPSHOT_CONTRACT_VERSION` 常數（**非** package 1.6.0＝噪音）；`PROVENANCE_CONTRASTS` 單一來源。 |
| **正做不窄做、亦不虛做**（Economy） | 別死碼、別窄做 | provenance 真實存在於 diff/incremental/snapshot_list ⟹ 一刀做全（戳有消費端、非死欄）。**不建新 audit MCP tool**（掛既有 listing）；**不碰人類面/前端/render_json**（OUT）。 |

**核心定位**：provenance＝**per-snapshot 出生契約 vs 當前契約**的事實信號，讓 The Door 的跨版本核心職能（diff/增量）不再**靜默跨契約邊界比較**。

---

## 1. 範圍（in / out）

### S7 做（in）
1. **持久化事實層（出生戳）**：
   - `VersionSnapshot` 加 `contract_version: str | None = None`（出生契約戳，與 commit_hash 同類事實）。
   - `SNAPSHOT_CONTRACT_VERSION: str` 常數（單一來源；初值 `"1"`）。
   - `create_snapshot` 蓋戳 `contract_version=SNAPSHOT_CONTRACT_VERSION`（出生點）。
   - `_serialize_snapshot`/`_deserialize_snapshot` round-trip（deserialize 缺鍵→None＝舊快照、O3）。
   - `snapshot.schema.json` 加 `"contract_version": {"type": ["string","null"]}`（additive optional；`additionalProperties:false` 故須加）。
2. **衍生（純事實）**：`derive_provenance(contract_version: str | None) -> str`：`==SNAPSHOT_CONTRACT_VERSION`→`"current"`／present 且 `!=`→`"legacy"`／None→`"unknown"`。
3. **膜詞彙**（新 `core/diff/provenance_membrane.py`）：`PROVENANCE_CONTRASTS=("current","legacy","unknown")`＋`provenance_signal`/`provenance_element`（純 3-Signal、unknown 真值、無 None 分支）。
4. **emit（agent-facing 跨版本，皆 inline 自建、非 render_json）**：
   - `diff_tool.py` json 分支 baseline_info/current_info 各加 `provenance`（從 baseline_snap/current.contract_version 衍生投影）。
   - `analyze_changes_tool.py` payload 加 baseline `provenance`（從 resolved baseline snapshot）。
   - `snapshot_list_tool.py` 每筆加 `provenance`。

### S7 不做（out）
- **render_json/report 面/viewer/CLI/前端 provenance**：render_json 目前無 provenance；加它＝S8 共用 renderer 領域＋人類面 ⟹ OUT（未來如需，走 S8 agent 邊界投影樣板）。
- **per-feature 戳**：戳是 per-snapshot（出生契約）；features 繼承所屬 snapshot ⟹ 不做 per-feature。
- **audit-conformance 違規明細**（種子 §80-83 底層）：Finding A `audit_conformance`（已存在、未接 MCP）＝獨立功能；S7 只做 provenance **頂層組織軸**。
- **package/git 版本當錨**：噪音/語義錯，OUT。
- **NoisePosition/缺值退路**：unknown 是格內真值（§390）⟹ 無 None 分支。
- **自動遷移既有快照**（種子 §87 剔除）：違寬讀；回填走既有 `extract --as-version`、不在本刀自動改人家資料。
- **F-severity-default／人類面整膜／presence-flag**（其他待排刀）。

---

## 2. Spike 事實（2026-06-06 對真實碼，file:line 已驗）

| 層 | 檔案:line | 事實 |
|---|---|---|
| 模型（無戳） | `models/snapshot.py:71-86` | `VersionSnapshot` 欄：version_id/timestamp/trigger/.../`codebase_path`；**無 contract/schema 版本戳**。加 `contract_version` 於 `:86` 後。 |
| 常數（無） | grep 全 src | 無 `SCHEMA_VERSION`/`contract_version`；package `1.6.0`（pyproject，噪音不用）。 |
| 落盤口（Finding A） | `snapshot_store.py:314 _write_snapshot`／`:89 create_snapshot`／`:110-130` | 單一落盤口 fail-closed 校 schema；create_snapshot＝出生點（蓋戳處）。 |
| serde | `_serialize_snapshot:365-398`（top dict）／`_deserialize_snapshot:400+`（建 VersionSnapshot） | 加 `contract_version` 於 serialize top dict ＋ deserialize `data.get("contract_version")`（缺→None＝O3）。 |
| schema | `snapshot.schema.json:6 additionalProperties:false`／`:7-14` props | 須加 `contract_version` optional 欄（否則 fail-closed 拒）。 |
| emit-diff（🟢 agent-only） | `diff_tool.py:33,38`（current/baseline_snap VersionSnapshot 可用）／`:73-74` json baseline_info/current_info | inline 自建 dict、不經 render_json ⟹ 直接投影（S4-S6 樣式）。 |
| emit-incremental | `analyze_changes_tool.py:103-107`（resolved baseline snapshot）／`:140` payload baseline_version_id | baseline VersionSnapshot 可得 contract_version；payload 加 baseline provenance。 |
| emit-list | `snapshot_list_tool.py:24-35`（每筆 VersionSnapshot） | 每筆加 provenance。 |
| 正交軸（疊加） | `analyze_changes_tool.py:142-143 inherited/affected` | inherited/affected＝重算與否；provenance＝出生契約＝**獨立疊加軸**（§0）。 |
| 樣板 | `core/scope/scope_membrane.py`（純 enum 最小）／`membrane/__init__` 匯出 SignalPosition | provenance_signal/element 直接樣板（純 3-Signal）。 |
| 回填路徑（O3 緩解） | `incremental_pipeline.py:128 the-door extract --as-version` | 既有 baseline 可經 extract 回填→重產時蓋戳。 |

**spike 結論**：provenance＝**唯一淨新增主軸**——全棧缺席、需建持久化戳（model+const+stamp+serde+schema）＋衍生＋膜（純 3-Signal）＋3 agent-facing emit（diff/incremental/list，皆 inline 非 render_json）。型別＝SignalPosition、無需新 variant（S6 §7 疑＝否）。O3：S7 落地當天 pre-S7(unknown) vs post-S7(current) 即可辨、價值不待遙遠。**膜「非持久化」與「需戳」的張力經理論解消＝戳是出生事實非膜元素**（§0）。

---

## 3. 設計（exact code；落點標注）

### 3.1 出生戳：model ＋ 常數 `models/snapshot.py`

```python
# 單一來源：當前 snapshot 契約版本（契約變更〔snapshot schema 或分析語義〕時 bump；
# 維護紀律＝provenance 資訊量前提，§0/§5）。
SNAPSHOT_CONTRACT_VERSION: str = "1"
```
```python
@dataclass(frozen=True)
class VersionSnapshot:
    ...
    codebase_path: Path | None = None
    contract_version: str | None = None  # 出生契約戳（O3：舊快照 None＝unknown）
```

### 3.2 蓋戳 `snapshot_store.py` create_snapshot（出生點）

```python
# from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION
snapshot = VersionSnapshot(
    ...,
    codebase_path=self._project_root,
    contract_version=SNAPSHOT_CONTRACT_VERSION,   # 出生蓋戳
)
```
> spike 須 grep 確認其他 VersionSnapshot 生產路徑（`snapshot_write_tool`/`snapshot_patch`）——若直建 VersionSnapshot 繞過 create_snapshot，亦須蓋戳或路由經此（plan task 處理；characterization 釘「新建快照 contract_version==SNAPSHOT_CONTRACT_VERSION」）。

### 3.3 serde round-trip `snapshot_store.py`

```python
# _serialize_snapshot top dict（:365）加：
"contract_version": snapshot.contract_version,
# _deserialize_snapshot 建 VersionSnapshot 加：
contract_version=data.get("contract_version"),   # 缺鍵→None＝O3 舊快照
```

### 3.4 schema `snapshot.schema.json`（additive optional）

```json
"contract_version": { "type": ["string", "null"] },
```
> 非 required（向後相容：舊快照無此鍵仍合法、deserialize→None）。

### 3.5 衍生 ＋ 膜 `core/diff/provenance_membrane.py`（新增）

```python
"""provenance 線的膜詞彙：snapshot 出生契約戳 vs 當前契約 → current/legacy/unknown Signal。

provenance＝乙案第三主軸（種子 §181）、唯一淨新增軸（§445）。per-snapshot 出生事實：
contract_version(出生戳) vs SNAPSHOT_CONTRACT_VERSION(當前) 的機械事實比對（fact-finder、
不裁決）。unknown＝格內哨兵真值（§390「格內對格外命名橋」：pre-stamp 快照）⟹ 純 3-Signal、
無 None 分支、無 NoisePosition。emit 面＝diff/incremental/list（§283「diff 才點亮」）。
與 inherited/affected 正交（§0：出生契約 ⊥ 本次重算與否）。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, SignalPosition
from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION

PROVENANCE_CONTRASTS: tuple[str, ...] = ("current", "legacy", "unknown")

_GLOSS = {
    "current": "出生於當前契約版本（與當前分析同 footing）",
    "legacy": "出生於非當前契約版本（跨契約邊界、語義可能漂移）",  # !=current，不假設方向
    "unknown": "無契約戳（pre-stamp 快照，出生契約不可知）",
}


def derive_provenance(contract_version: str | None) -> str:
    """戳 vs 當前契約 → provenance 值（純事實比對、不裁決）。

    None（pre-stamp）→ unknown；==當前 → current；present 且 != → legacy。
    """
    if contract_version is None:
        return "unknown"
    return "current" if contract_version == SNAPSHOT_CONTRACT_VERSION else "legacy"


def provenance_signal(value: str) -> SignalPosition:
    return SignalPosition(contrasts=PROVENANCE_CONTRASTS, gloss=_GLOSS[value])


def provenance_element(value: str) -> MembraneElement:
    """provenance 值 → MembraneElement（格內 Signal、unknown 是真值非缺值）。"""
    return MembraneElement(payload=value, position=provenance_signal(value))


def provenance_element_for(contract_version: str | None) -> MembraneElement:
    """便捷：直接由 snapshot 戳投影（衍生＋升膜）。"""
    return provenance_element(derive_provenance(contract_version))
```

### 3.6 emit 投影（3 agent-facing 面）

**diff_tool.py**（json 分支 `:73-74`，baseline_info/current_info）：
```python
# from the_door.core.diff.provenance_membrane import provenance_element_for
"baseline_info": {..., "provenance": provenance_element_for(baseline_snap.contract_version).to_json()},
"current_info": {..., "provenance": provenance_element_for(current.contract_version).to_json()},
```
**analyze_changes_tool.py**（payload `:139-149`）：
```python
# ⚠ concept-review 修：`snap` 僅在 else(無 source_path) 分支綁定（:100-105）；不可依賴。
# 由 diff.baseline_version_id 獨立穩健取 baseline snapshot（None-safe→unknown）。
_bsnap = SnapshotStore(codebase_path).get_snapshot(diff.baseline_version_id)
"baseline_provenance": provenance_element_for(
    getattr(_bsnap, "contract_version", None)
).to_json(),
```
> 不依賴條件 `snap`；baseline 取不到（None）→ `getattr(...,None)` → unknown（O3-safe）。

**snapshot_list_tool.py**（每筆 `:26-33`）：
```python
"provenance": provenance_element_for(s.contract_version).to_json(),
```

---

## 4. 不變量清單（S7 強制）

| # | 不變量 | 強制處 | 對應理論 |
|---|---|---|---|
| P1 | 新建快照 `contract_version == SNAPSHOT_CONTRACT_VERSION`（出生蓋戳） | create_snapshot ＋ characterization | §5 出生戳／寫嚴 |
| P2 | serde round-trip：戳寫入/讀回保真；舊快照缺鍵→None（O3） | serde ＋ characterization（round-trip＋legacy-load） | §8.13 持久化保真／O3 |
| P3 | `derive_provenance`：==→current／!=→legacy／None→unknown（純事實、不裁決） | provenance_membrane ＋ unit | fact-finder／O1 |
| P4 | provenance 值 ∈ PROVENANCE_CONTRASTS → SignalPosition；**unknown 是格內真值、無 NoisePosition/None 分支** | provenance_signal ＋ MembraneElement I4 | §181/§390 |
| P5 | agent-facing emit（diff/incremental/list）provenance 經膜、無裸值；皆 inline 非 render_json（人類面零改動） | 3 emit 點 ＋ characterization | §8.2 B 側／面×軸 |
| P6 | provenance ⊥ inherited/affected（疊加、不合併） | analyze_changes 兩者並存 ＋ test | §181 軸正交 |
| P7 | schema additive、向後相容（舊快照無 contract_version 仍 validate＋load→None） | schema optional ＋ characterization（legacy snapshot load） | 寫嚴讀寬／O3 |

> **無 NoisePosition/None 分支**（與 confidence/S8-scope 可空不同）：unknown＝格內哨兵真值。

---

## 5. 慣例萃取 ＋ findings

1. **淨新增軸＝膜 compose 持久化事實**：與 S4-S8「reshape 既有 bare」不同，provenance 需新增**出生事實戳**（持久化、Finding A 落盤口蓋戳）＋emit 時衍生升膜。**戳＝事實非膜元素**＝解消「膜非持久化 vs 需戳」張力的通則（未來任何需新事實的軸照此）。
2. **缺值映射到格內哨兵真值（非 NoisePosition）**：當「缺席」本身在閉集裡有命名（unknown/§390），缺席→該真值、非 NoisePosition。判準＝閉集是否含命名橋哨兵（provenance unknown 有；confidence 無→None→NoisePosition）。
3. **跨版本軸 emit 在「版本相會處」**（§283）：diff/incremental/list；單版退化仍良定義。
4. **資訊量綁維護紀律**（findings/誠實前提）：`SNAPSHOT_CONTRACT_VERSION` 須於契約變更時 bump（紀律），否則 provenance 全 current＝真但低資訊。**S7 落地即建立 pre/post-S7 邊界**（unknown vs current）＝首個非退化點。

**findings：**
- **[F-other-snapshot-producers]＝🟢 已查實（單一蓋戳點）**：grep 證全建立路由經 `create_snapshot`（cli/snapshot_cmd、snapshot_write_tool、snapshot_create_tool、analyze_pipeline）；`VersionSnapshot(` 僅 `snapshot_store.py:116`(create)/`:468`(deserialize) 構造 ⟹ 蓋戳一點全覆蓋。`snapshot_patch:247` 重寫 loaded snapshot＝**保原戳不 re-stamp**（plan 加 characterization）。
- **[F-render_json-provenance]** render_json 未來如要帶 provenance＝S8 agent 邊界投影樣板（人類面 OUT），本刀不做。
- **[F-contract-version-bump-discipline]** 文件化「契約變更 bump SNAPSHOT_CONTRACT_VERSION」入出版/契約流程（非本刀生產碼）。

---

## 6. 測試策略

- **單元**（`tests/unit/core/diff/test_provenance_membrane.py` 新增）：`PROVENANCE_CONTRASTS`＝3-set；`derive_provenance`（current 戳→current／舊戳→legacy／None→unknown）；`provenance_element(v).to_json()` 形狀（signal、contrasts 3-set、gloss）；**unknown 走 signal 非 noise**（P4）；`provenance_element_for(None)`→unknown signal。
- **characterization（持久化）**：
  - P1：`create_snapshot(...)` 產出 `.contract_version == SNAPSHOT_CONTRACT_VERSION`。
  - P2/P7：round-trip（serialize→deserialize 保真）；**legacy-load**：構造無 contract_version 鍵的舊 snapshot JSON → deserialize → `contract_version is None`、validate 通過（schema additive）、不炸（復用既有 `test_snapshot_store_roundtrip` legacy 樣式）。
- **emit characterization（P5，agent-facing flip）**：diff_tool/analyze_changes/snapshot_list——pin 現狀（無 provenance）→ flip：含 `provenance` 膜投影 `{value, position(signal)}`；diff 跨「pre-S7 baseline(unknown) vs 新 current(current)」案例驗點亮。**render_json 不動**（grep gate）。
- **P6 正交**：analyze_changes 同時含 inherited/affected ＋ baseline_provenance、互不干涉。
- **連貫性回驗**：S0-S8 全測綠；既有 snapshot serde 測（`test_snapshot_store_roundtrip` 等）綠（additive 欄）；既有 diff/analyze_changes/snapshot_list 測——provenance 為新增鍵、舊斷言不破（除非顯式全等 dict→更新）。
- **執行**：`cd the_door && PYTHONUTF8=1 python -m pytest -q`。驗收＝S8 基線 1557＋新測、零回歸（除 emit/serde characterization 有意更新）。

---

## 7. 對後續的連貫律回驗 ★

- **campaign 三主軸收齊**：confidence(S4)/scope(S5)/diff_state(S6,非主軸但 diff 面)/report(S8)＋**provenance(S7)** ⟹ §181 三主軸（confidence/scope/provenance）agent 面全上膜。
- **人類面整膜**（未來）：provenance 若要上 viewer/render_json＝S8 agent 邊界投影樣板＋前端連動（最大 blast-radius、OUT）。
- **新事實軸通則**（§5 慣例 1）：未來任何「需新增持久化事實才能算的軸」照「事實戳（落盤口）＋emit 衍生升膜」。
- **回驗結論**：S0-S8 詞彙＋Finding A 落盤口對 S7 充分；唯一新增＝出生戳持久化（model+serde+schema+const）＋provenance_membrane（純 3-Signal、unknown 真值）。零預見返工。

---

## 8. spec 完成後 7 點審查（種子 §9.4；第 4 點 grep 已驗）

1. **單一職責**：`provenance_membrane` 管「戳→provenance 值→Signal」；持久化只加一事實欄；emit 各多一膜鍵。✓
2. **介面最小**：model +1 欄、+1 常數、serde +1 鍵、schema +1 optional、+1 membrane（純 3-Signal+derive）、3 emit +1 鍵；**無新 position 變體、無新軸詞彙以外型別**。
3. **可測**：純函式＋純值＋serde round-trip；P1-P7 皆可斷言。✓
4. **API grep 驗真**（§2）：VersionSnapshot 欄`:71-86`✓／create_snapshot/_write_snapshot`:89,314`✓／serde`:365,400`✓／schema additionalProperties:false`:6`✓／diff_tool baseline_snap/current`:33,38,73`✓／analyze_changes baseline`:103,140`✓／snapshot_list`:24`✓／SignalPosition 匯出✓。**無虛構。無循環 import**：provenance_membrane→membrane＋models.snapshot（單向）。
5. **錯誤路徑**：derive None→unknown（非錯）；provenance_element 值∉contrasts→_GLOSS KeyError（防呆，正常經 derive 三值守住）；舊快照缺戳→None→unknown（O3、不炸）。
6. **向後相容**：純加法；contract_version optional（舊快照 load→None→unknown）；schema additive；emit 新增鍵（舊消費者不破）。**有意契約變更＝3 agent emit 新增 provenance 鍵＋snapshot 持久化新增 optional 欄**＝characterization 見證。
7. **文件**：結構化、exact code、file:line、零佔位符；plan 引本 spec §3.x。

---

## 9. 交付物（plan 階段拆 task；一刀、內部 4-task 排序處理持久化風險）

1. **持久化戳地基**：model `contract_version`＋`SNAPSHOT_CONTRACT_VERSION`＋create_snapshot 蓋戳＋serde round-trip＋schema additive＋characterization（P1/P2/P7：蓋戳、round-trip、legacy-load）。含 [F-other-snapshot-producers] grep＋補蓋。
2. **衍生＋膜**：`core/diff/provenance_membrane.py`（PROVENANCE_CONTRASTS＋derive_provenance＋signal/element/element_for）＋`test_provenance_membrane.py`（P3/P4）。
3. **emit 投影**：diff_tool＋analyze_changes＋snapshot_list 各加 provenance（P5/P6）＋characterization（flip emit、跨 pre/post-S7 點亮、P6 正交）。
4. **gate**：全測零回歸（除 emit/serde characterization 有意更新）；grep gate（render_json/人類面/前端未動）。

**驗收**：全測零回歸、新建快照蓋戳（P1）、serde 保真＋legacy-load（P2/P7）、derive 三值（P3）、unknown 格內真值（P4）、3 emit 無裸值＋render_json 未動（P5）、provenance⊥inherited/affected（P6）、S0-S8 全測綠。

**S7 完成 → 乙案三主軸（confidence/scope/provenance）agent 面整膜收齊。** 剩餘待排：人類面整膜（碰前端）／presence-flag 型／F-severity-default。
