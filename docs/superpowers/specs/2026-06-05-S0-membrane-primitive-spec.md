# S0 spec：膜 primitive（MembraneElement ＋ SignalPosition ＋ ReservedPassthrough）

> **日期**：2026-06-05　**狀態**：spec（pre-plan，經 review＋驗證收斂後定稿）　**性質**：乙案（膜模型）重塑 campaign 的**地基刀**（S0）。
> **承接**：種子檔 `docs/superpowers/specs/2026-06-04-yi-an-output-direction-seed.md`（理論定稿 §8.13；膜模型 §8.10；型別草圖 §8.12；**§8.13 勘誤表新增 4 條＝本 spec 驗證產出**）。
> **分刀**：S0＝本檔（base＋Signal＋Reserved）。S1＝doubt through-line（首個 retrofit）。S2＝NoisePosition 首落地。S3＝RelayedVerdict 首落地。順序 S0→S1→…。
> **連貫律（使用者 2026-06-05 立）**：階段 spec 寫完回驗與下一階段連貫性。本檔對 S1＝§5；對 S2/S3＝§3a（延後變體方向已定，避免鎖死地基後返工）。

---

## 0. 理論重錨（種子檔 §9.2 強制；每條對應一個 S0 設計決定，防漂移）

寫前已逐項回核種子檔（含本 spec 驗證後新增的 §8.13 勘誤）。下表把每條約束釘到具體決定：

| 理論約束（出處） | S0 如何遵守 |
|---|---|
| **膜不變量**（§8.10）：意義靠結構位置、非散文/prompt | `MembraneElement` 強制每個膜詞彙值攜帶 `position`；值＋它在結構空間的位置一起出。 |
| **per-value 切法**（§8.13 勘誤新增）：膜的格內/格外界線切在**值**、非欄位 | `position` 是 per-element：同欄位的閉集值出 `SignalPosition`，格外殘餘出 `NoisePosition`（後者 S2 才建）。S0 只處理格內 Signal＋reserved 窗。 |
| **寫嚴讀寬分側**（§8.12 修正②）：B 側 CWA 嚴格封閉 enum | `SignalPosition.contrasts`＝封閉兄弟集（B 側嚴）。A 側讀寬律屬 NoisePosition（S2）。 |
| **fact-finder**（§8.2 A；§8.13-O1）：禁自鑄裁決 | base `MembraneElement` **無** score/risk 欄位 → 自鑄裁決在 S0 型別上無處可放。轉述裁決（RelayedVerdict）＋其 evidence 守衛屬 S3（§3a 記方向）。**無處方變體**（§8.13 勘誤）。 |
| **B 操作位置**（§8.10）：暴露前件/後件/對比/共依，優先用內部單一來源 | `SignalPosition` 四欄＝`contrasts`(對比)＋`preconditions`(前件)＋`consequences`(後件)＋`co_requires`(共依)＋極短 `gloss`。皆 optional（純 enum 如 confidence 只填 contrasts+gloss；doubt state 才填滿，源自 `DoubtLifecycle`，§5 驗）。 |
| **reserved 窗**（§8.10 接點②） | `ReservedPassthrough` 變體＝free-text、不要求結構。 |
| **provenance＝唯一淨新增軸**（§8.13-O3） | S0 **不**碰版本戳（S7）。provenance 作為 Signal 值（current/legacy/unknown）由各面 emit，S0 不假裝它已有來源。 |
| **生成性／型驅動**（§8.11）：make illegal states unrepresentable | S0 段：base 無 score 欄（禁自鑄裁決）＋`SignalPosition.contrasts` 非空（B 側 CWA）。Noise/Verdict 的型別守衛隨各自試點落地（§3a）。 |

**誠實界線（§8.11）**：S0 型別只強制**結構**合規，管不到**語意**正確（gloss 寫爛、confidence 填錯仍靠生產端判斷＋test）。型管形狀、管不到判斷。

**對前一版的修正（review＋驗證收斂）**：上一版 §0 宣稱「RelayedVerdict 強制外部 provenance → F6 型別上不可構造」——**驗證為假**（`vulnerability_scanner.py:167,177,189`：scanner 鑄中點、丟真 vector、卻蓋同一 `source="osv-scanner"`，非空 source 零鑑別力）。正解＝evidence-bearing（帶 CVSS vector 方可構造），且 RelayedVerdict 延 S3 對真實 OSV 形狀定型，**不在 S0 鎖死**。

---

## 1. 範圍（in / out）

### S0 做（in）
1. 新增 peer 子套件 `core/membrane/`（旁路風格，比照 `core/datamodel/`、`core/vulnerability/`）。
2. 立 **base ＋ 2 變體**：`MembraneElement`、`SignalPosition`（B/格內/閉集訊號）、`ReservedPassthrough`（reserved 窗）。`Position` union 型別**現階段只含這 2 變體**（S2 加 Noise、S3 加 Verdict 時擴 union）。
3. base 不變量：`MembraneElement` **無** score/risk 欄位（禁自鑄裁決的型別體現，I2）＋跨欄 `payload ∈ contrasts`（I4，膜脊椎「意義靠關係定位」）。
4. `SignalPosition` 不變量：`contrasts` 非空（B 側 CWA，I1）。
5. 單一 `MembraneElement.to_json()` 投影（§8.11「唯一受祝福的輸出構造路徑」雛形）。
6. 完整單元測試＋**對 S1 的連貫性回驗測試**（§5）：用真實 `DoubtLifecycle` 資料證 primitive 接得住 doubt 三欄，**不改任何生產碼**。

### S0 不做（out）
- **不建 `NoisePosition` / `RelayedVerdict`**——兩者 S1 doubt 零消費者（§5 驗），首落地 S2/S3。方向已定、記於 §3a，避免鎖死地基後返工（連貫律）。
- **不碰 24 個 MCP 工具**的 payload 建構碼。
- **不改 `core/ui/serializers.py` 生產輸出**（`serialize_doubt` 等逐字維持）→ S0 **零輸出契約改動**，故**不需** characterization test 前置。production wiring＝S1。
  - **收窄（已定案）**：上一版「serializers 示範一次」改為 §5 連貫性回驗**測試**（非改 production serializer）。理由＝原則上嚴格更優：保 S0 純加法地基、不在地基刀觸發輸出契約改動；真正的 serializer wiring 落 S1，屆時由 characterization test 正確把關（動 `serialize_doubt` 輸出前先釘現狀）。
- **不**新增版本戳/provenance 來源（S7）、**不**改任何 schema 檔。
- **不**收編 doubt 三份重複 builder（`serialize_doubt`／`doubt_transition_tool.py:75-94`／`doubt_list_tool.py:40-65`）＝S1。

---

## 2. Spike 事實（2026-06-05 對真實碼，file:line 已驗）

- **MCP envelope 非值級咽喉**：`mcp/tools/_response_envelope.py:14 wrap()` 只注入 `next_actions`；enum 值在抵達前已塌成 bare str。
- **doubt 形狀手搓 3 份、鍵名不一致**：`serializers.serialize_doubt`（`"state"`、無 resolution）／`doubt_transition_tool.py:75-94`（`"current_state"`＋resolution）／`doubt_list_tool.py:40-65`（逐字重複）。收編＝S1。
- **B 側操作位置內部單一來源**：`core/scope/doubt_lifecycle.py:29 DoubtLifecycle`——`VALID_TRANSITIONS:32`（6 狀態封閉集）／`TERMINAL_STATES:40`／`_RESOLVING_STATES:41`／`is_terminal:43`／`check_transition:46`（強制合法轉換）。→ §5 資料源。**狀態集封閉、store 強制合法 → doubt 全程無 off-grid 殘餘**（故 S1 不需 NoisePosition，§5）。
- **驗證 RelayedVerdict（延 S3，方向已定）**：`vulnerability_scanner.py:167` 鑄 `CVSS_MIDPOINTS` 中點；`:174-177` OSV 給真 vector 時 `pass` **丟棄**、保留中點；`:189` 一律蓋 `source="osv-scanner"`。→ 非空 source 零鑑別力；evidence(vector) 在 `:171` 可得。
- **驗證「無處方變體」**：`vulnerability_renderer.py:131-136 _get_action`（severity→「立即更新」）＝自鑄處方、越界裁決。S3 移除。
- **既有 dataclass 慣例**：`models/*.py` 全 `@dataclass`；`doubt_lifecycle.py:20 TransitionPlan` 用 `@dataclass(frozen=True)` → S0 沿用 frozen。

---

## 3. 型別設計（exact code；落點 `core/membrane/primitive.py`）

> S0 只建 base＋Signal＋Reserved。`Position` union 現含 2 變體，S2/S3 擴。所有變體 `frozen=True`（值物件，比照 `TransitionPlan`）。不變量在 `__post_init__` 強制。

```python
"""膜 primitive：意義經結構位置送達消費端 LLM 的單一 emit 原語。

非持久化層——住 emission/呈現邊界（種子檔 §8.12）。snapshot 等照舊存 bare 值，
本原語在 emit 時把「值 + 它在結構空間的位置」一起投影出去。

per-value 切法（種子檔 §8.13 勘誤）：膜的格內/格外界線切在「值」、非「欄位」。
落在閉集的值 → 格內 Signal（本檔建）；格外殘餘 → 格外 Noise（S2 建）。

設計鐵律（型驅動 make-illegal-states-unrepresentable，§8.11）：
  - base MembraneElement 無 score/risk 欄位 → 自鑄裁決無處可放。
  - SignalPosition.contrasts 為封閉兄弟集 → B 側 CWA 嚴格。
  （NoisePosition「聚合必帶基數」與 RelayedVerdict「必帶外部證據」的守衛
    隨各自試點 S2/S3 落地，方向見本檔 §3a。）
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalPosition:
    """B 側（CWA／格內／封閉訊號）：值的意義＝它在封閉兄弟集中的對比位置。

    四個操作位置欄位皆 optional：
      - 純 enum（如 confidence high/medium/low）只填 contrasts + gloss。
      - 帶轉換文法的 enum（如 doubt current_state）填滿，源自內部單一來源
        （DoubtLifecycle，種子檔 §8.10、本檔 §5 驗）。
    contrasts 是 tuple（有序）：doubt states＝圖（無全序，順序僅列舉）；
    severity＝全序（critical>high>medium>low）——同型別容兩者。
    gloss＝極短指稱注解（非散文，面對遞迴必須短）。
    """
    contrasts: tuple[str, ...]              # 對比：完整封閉兄弟集（含本值）
    gloss: str                             # 極短指稱注解
    preconditions: tuple[str, ...] = ()    # 前件：可轉入本值的條件
    consequences: tuple[str, ...] = ()     # 後件：本值產生的效果
    co_requires: tuple[str, ...] = ()      # 共依：本值必填的伴隨欄位

    def __post_init__(self) -> None:
        if not self.contrasts:
            raise ValueError(
                "SignalPosition.contrasts 必須是非空的封閉兄弟集（B 側 CWA）"
            )


@dataclass(frozen=True)
class ReservedPassthrough:
    """reserved 窗：CWA 世界裡明文宣告的 OWA 窗。free-text，不要求結構。

    標記型別——free-text 內容住 MembraneElement.payload，本變體只宣告
    「此處刻意永久開放」。
    """
    pass


# Position union——S0 階段 2 變體；S2 加 NoisePosition、S3 加 RelayedVerdict（§3a）。
Position = SignalPosition | ReservedPassthrough


@dataclass(frozen=True)
class MembraneElement:
    """一個輸出元素＝它的值（payload）＋它在結構空間的位置（position）。

    base 型刻意無 score/risk/severity 欄位：裁決只能經（未來的）RelayedVerdict
    position，且該變體強制外部證據——自鑄裁決在型別上無處可放。

    payload 語意 per-variant：
      - SignalPosition → payload＝該閉集的某個值（str），且**型別強制 payload ∈ contrasts**（I4）。
      - ReservedPassthrough → payload＝free-text 字串（無約束）。
    payload 寬型 object 是為未來 RelayedVerdict（S3）預留；Signal/Reserved 的 str
    約束由 I4（payload 必在 str 兄弟集）間接保證。
    """
    payload: object
    position: Position

    def __post_init__(self) -> None:
        # 核心膜保證（意義靠關係定位）：Signal 值必須真的在它宣稱的封閉兄弟集裡。
        # 跨欄不變量必須放 element 層——SignalPosition 自身拿不到 payload。
        if isinstance(self.position, SignalPosition):
            if self.payload not in self.position.contrasts:
                raise ValueError(
                    f"payload {self.payload!r} 不在其 SignalPosition.contrasts "
                    f"{self.position.contrasts!r} 中——值必須定位於自己的封閉兄弟集"
                )

    def to_json(self) -> dict:
        """唯一受祝福的投影路徑（§8.11 affordance）。意義不靠 prompt。"""
        return {"value": self.payload, "position": _position_to_json(self.position)}


def _position_to_json(position: Position) -> dict:
    if isinstance(position, SignalPosition):
        return {
            "kind": "signal",
            "contrasts": list(position.contrasts),
            "gloss": position.gloss,
            "preconditions": list(position.preconditions),
            "consequences": list(position.consequences),
            "co_requires": list(position.co_requires),
        }
    if isinstance(position, ReservedPassthrough):
        return {"kind": "reserved"}
    raise TypeError(f"未知 position 變體：{type(position).__name__}")
```

`core/membrane/__init__.py` 門面：

```python
"""膜 primitive 公開門面（peer 子套件，旁路風格比照 core/datamodel）。"""
from the_door.core.membrane.primitive import (
    MembraneElement,
    Position,
    ReservedPassthrough,
    SignalPosition,
)

__all__ = [
    "MembraneElement",
    "Position",
    "ReservedPassthrough",
    "SignalPosition",
]
```

---

## 3a. 延後變體（方向已定，**不在 S0 建**；對 S2/S3 的連貫性記錄）

> 連貫律對「再下一階段」的落點：這兩變體已對真實消費者驗過、方向鎖定，**S0 不建是為了讓它們在各自試點對真實形狀定型，而非開放未知**。

**`NoisePosition`（首落地 S2：edge_projection F5 殘餘桶／audit gap-kinds）** — per-value 切法後縮成**純殘餘描述子**（吻合 §8.3「殘餘格恆帶 性質+基數+比例」）：
```python
# S2 落地形狀（此處僅記錄方向，不在 S0 實作）
@dataclass(frozen=True)
class NoisePosition:
    gap_kind: str | None = None      # 優先序 corrupt>indeterminate>evolutionary>reserved
    cardinality: int | None = None
    proportion: float | None = None
    is_flag: bool = False
    aggregated: bool = False
    # 不變量（S2 強制）：aggregated ⟹ cardinality AND proportion（壓縮不偷渡減法）；
    #                    gap_kind ∈ 優先序集；cardinality ≥ 0。
```
confidence/provenance/scope **不在** NoisePosition——它們是 Signal 值（閉集）。enum 的 off-grid 哨兵值（unknown/unrecognized）出現時才附帶 Noise 描述子。

**`RelayedVerdict`（首落地 S3：vulnerability cvss）** — evidence-bearing（驗證結論，§2）：
```python
# S3 落地形狀（此處僅記錄方向，不在 S0 實作）
@dataclass(frozen=True)
class RelayedVerdict:
    score: float
    authority: str       # 發布者，如 "CVSS v3.1 (NVD via OSV)"
    evidence: str        # 外部證據本體（CVSS vector 字串），非來源標籤
    # 不變量（S3 強制）：evidence 非空 → 無 vector 不可構造 → 退 NoisePosition(indeterminate)。
    #   通則：凡來源沒實際給的值，一律退 Noise，不出成「看似有來源」的值。
```
**無第 5「處方」變體**：`_get_action` 自鑄處方越界裁決，膜內無家＝正確（§8.13 勘誤）。S3 移除。

---

## 4. 不變量清單（S0 強制；每條一個「非法即拋」測試）

| # | 不變量 | 強制處 | 對應理論 |
|---|---|---|---|
| I1 | `SignalPosition.contrasts` 非空 | `SignalPosition.__post_init__` | B 側 CWA 封閉集 |
| I2 | base `MembraneElement` 無 score/risk 欄位 | 型別**缺**該欄位（結構性保證） | 禁自鑄裁決（fact-finder 上界） |
| I3 | `to_json` 對未知 position 變體拋 `TypeError` | `_position_to_json` 末行 | 顯式失敗、不靜默 |
| **I4** | **Signal 的 `payload ∈ position.contrasts`** | **`MembraneElement.__post_init__`（跨欄）** | **膜脊椎：意義靠關係定位（值必在自己的封閉兄弟集）** |

> Noise/Verdict 的不變量（聚合必帶基數比例、verdict 必帶 evidence）隨 S2/S3 落地，記於 §3a。

---

## 5. 對 S1（doubt through-line）的連貫性回驗 ★（連貫律落點）

> **目的**：證 S0 的 base+Signal+Reserved **覆蓋 S1 doubt 全部膜詞彙、零未驗變體**。本節對應 S0 測試，用真實 `DoubtLifecycle` 資料，**不改生產碼**。

S1 要把 doubt 三欄經 primitive 出。逐欄驗：

| doubt 欄位（模型層根） | 膜側 → 變體 | primitive 怎麼承載（資料源） |
|---|---|---|
| `current_state`（`models/doubt.py:35`，6 值閉集） | 格內 → `SignalPosition` | `contrasts`＝`VALID_TRANSITIONS.keys()`；`preconditions`＝反查（哪些 from→本值）；`consequences`＝`TERMINAL_STATES`/可達 targets；`co_requires`＝`_RESOLVING_STATES ⟹ reason` |
| `resolution.type`（`models/doubt.py:41`，3 值閉集） | 格內 → `SignalPosition` | `contrasts`＝`{explained,fixed,accepted_risk}`（＝`_RESOLVING_STATES`）；同源 lifecycle |
| `reason`（free-text，schema `oneOf null\|string`） | reserved → `ReservedPassthrough` | payload＝reason 字串 |

**S1 無 off-grid 殘餘（故不需 NoisePosition）**：doubt 狀態集封閉、`DoubtStore` 經 `check_transition` 強制合法 → 永無「unrecognized 狀態」；`doubt_list` 的 `total` 是完整計數（非有損聚合殘餘）→ 不觸發「聚合必帶基數」。**S1 emit ＝ Signal＋Reserved＋裸標量，零 Noise/Verdict。**

**回驗測試骨架**（屬 S0）：
```python
def test_s1_doubt_coherence_current_state():
    from the_door.core.scope.doubt_lifecycle import DoubtLifecycle
    from the_door.core.membrane import MembraneElement, SignalPosition

    lc = DoubtLifecycle()
    states = tuple(lc.VALID_TRANSITIONS.keys())          # 6 值封閉兄弟集
    value = "explained"
    preconds = tuple(s for s, tos in lc.VALID_TRANSITIONS.items() if value in tos)
    el = MembraneElement(
        payload=value,
        position=SignalPosition(
            contrasts=states,
            gloss="已查證為預期行為，非缺陷",
            preconditions=preconds,                      # ("investigating", "escalated")
            consequences=("terminal",) if lc.is_terminal(value) else (),  # 從 is_terminal 導出、非寫死
            co_requires=("reason",),                     # explained ∈ _RESOLVING_STATES
        ),
    )
    j = el.to_json()
    assert j["value"] == "explained"
    assert set(j["position"]["contrasts"]) == set(states)
    assert "investigating" in j["position"]["preconditions"]


def test_s1_doubt_coherence_reason_reserved():
    from the_door.core.membrane import MembraneElement, ReservedPassthrough
    el = MembraneElement(payload="使用者確認為框架慣例", position=ReservedPassthrough())
    assert el.to_json() == {"value": "使用者確認為框架慣例", "position": {"kind": "reserved"}}
```

**連貫性結論（spec 階段已可斷言）**：primitive 四操作位置欄位與 `DoubtLifecycle` 三結構一一對得上；reserved 承 `reason`；S1 無 off-grid → S0 兩變體**充分且無剩**。**零未驗變體、零預見返工。** 若 S1 實作發現缺欄 → 回本節修 S0 再續（連貫律明確回驗點）。

---

## 6. 測試策略
- **無 characterization 前置**：S0 零輸出契約改動（§1 out）。
- **單元測試**（`tests/unit/core/membrane/test_primitive.py`）：
  - `SignalPosition`（純 enum＋帶文法兩型）、`ReservedPassthrough` happy-path × 各 1，含 `to_json` 鍵集斷言。
  - I1 非法即拋（`pytest.raises(ValueError, match="非空")`，空 contrasts）。
  - I2 結構性記錄：斷言 `MembraneElement` 無 `score` 屬性。
  - I3：`_position_to_json` 對 mock 未知變體拋 `TypeError`。
  - I4 非法即拋（`pytest.raises(ValueError, match="不在")`，payload 不在 contrasts）＋ happy-path（payload ∈ contrasts 可構造）。
- **連貫性回驗**（`tests/unit/core/membrane/test_s1_coherence.py`）：§5 兩測試 × 真實 `DoubtLifecycle`。
- **執行**：`cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/ -q`（Windows cp950 前置）。全綠＋零回歸（純加法，既有 1447 passed 不受影響）。

---

## 7. spec 完成後 7 點審查（種子檔 §9.4；第 4 點 grep 已驗，含本輪驗證）
1. **單一職責**：primitive 只管「值＋結構位置」承載與投影。✓
2. **介面最小**：對外＝1 門面 4 符號（`MembraneElement`＋2 變體＋`Position`）。
3. **可測**：純值物件、`to_json` 純函式。✓
4. **API 名 grep 驗真**（file:line 在 §2）：`wrap`✓／`serialize_doubt`✓／`DoubtLifecycle`/`VALID_TRANSITIONS`/`TERMINAL_STATES`/`_RESOLVING_STATES`/`check_transition`✓／`vulnerability_scanner`/`CVSS_MIDPOINTS`(`:167,177,189`)✓／`vulnerability_renderer._get_action`(`:131-136`)✓／`doubt_transition_tool`/`doubt_list_tool`✓。**無虛構 API。**
5. **錯誤路徑**：I1（空 contrasts→ValueError）、I3（未知變體→TypeError）、I4（payload∉contrasts→ValueError）皆有對應測試。
6. **向後相容**：純新增子套件、零既有碼改動 → 零回歸。
7. **文件**：結構化、exact code、零佔位符。

---

## 8. 交付物（plan 階段拆 task 用）
1. `src/the_door/core/membrane/__init__.py`（門面，4 符號）
2. `src/the_door/core/membrane/primitive.py`（base＋Signal＋Reserved＋`to_json`＋I1/I3/I4 守衛）
3. `tests/unit/core/membrane/test_primitive.py`（變體 happy-path＋I1/I2/I3）
4. `tests/unit/core/membrane/test_s1_coherence.py`（§5 兩欄回驗）

**驗收**：全綠、零回歸、`MembraneElement` 無法承載自鑄裁決（I2）、Signal 值無法脫離兄弟集（I4）、§5 doubt 三欄回驗通過。

**S0 完成 → 進 S1（doubt through-line）spec**：起 S1 前重跑種子檔 §9.2 理論重錨、讀本檔 §5＋§3a 確認連貫性回驗點與延後變體方向。
