# presence-flag spec：risk_flags 多選旗標整膜（新 PresenceFlagPosition 變體）

> **日期**：2026-06-06　**狀態**：spec（pre-plan，寫前已對真實碼 spike＋理論重錨）　**性質**：補膜 primitive **第 5 變體**（S0 §3a 曾草擬 `is_flag`、S2 暫緩「待首個 presence 生產者落地再加」）＋agent 邊界投影。承 S8-report applier 樣板（agent 邊界、不碰 render_json/前端）。
> **一句話**：`risk_flags`（`L1ChangeEntry.risk_flags: list[str]`，封閉 3-詞彙 `{out_of_scope, vulnerability, semantic_drift}` 的**多選**）目前 emit 為裸 list。裸 list 讓 agent 無法分辨「檢查過未觸發」vs「未知」，也不知**封閉詞彙全集**。補 `PresenceFlagPosition`（CWA 多選）投影：payload＝present 子集、position 載完整詞彙＋per-flag gloss ⟹ absence＝詞彙−present＝有意義。

---

## 0. 理論錨點 ＋ 型別決策（核心）

| 原則 | 對本刀約束 |
|---|---|
| **意義靠關係定位、封閉集自帶意義**（§8.11/§181） | risk_flags 是封閉詞彙（schema enum 3 值）⟹ CWA。但**多選**（旗標可共現：一 feature 可同時 out_of_scope＋vulnerability）⟹ 非 SignalPosition 的單選。 |
| **暴露封閉詞彙（§390 命名橋的多選版）** | 膜對閉集的價值＝暴露**全詞彙**，使 agent 知道「可能出現的封閉旗標全集」。裸 list 只見 present、不知全集。**⚠ absence 語義守界（fact-finder）**：生產者（`report_renderer.py:403-413`）對 out_of_scope/vulnerability **條件式**檢查（node 不在 scope_map/vuln_features 時旗標不舉）⟹ 「未舉某旗標」**不等同**「已驗證 clear」（可能＝未評估）。故膜**只報「未舉此旗標」、不自鑄「已檢查未觸發」**（否則＝自鑄生產者未保證的事實）。vocabulary 暴露的是**可能性空間**、非逐旗驗核結論。 |
| **正做不窄做、亦不虛做**（Economy） | presence-flag 是**真實存在**的面（risk_flags 是它的首個生產者，非投機）⟹ 建型別＝正做。primitive.py:61-63 明文「待首個 presence 生產者落地再加」＝now。 |
| **fact-finder、不自鑄**（§8.2A） | 投影只忠實轉述「哪些旗標 present／全詞彙為何」，不加權不裁決。 |
| **膜住 emission 邊界**（§8.12/S8 applier） | 投影在 agent 讀邊界（report_membrane applier）、不動 render_json/persisted/viewer（§1 out）。 |

### 型別決策：為何新 `PresenceFlagPosition`、而非複用既有

| 候選 | 做法 | 否決理由 |
|---|---|---|
| **A：list-of-SignalPosition(contrasts=3-詞彙)** | 每 present 旗標→Signal、contrasts=全詞彙（承 S4 edge nested Signal list） | **語義錯**：SignalPosition contrasts＝「互斥兄弟集、payload 是其中**那一個**」。但 risk flags **共現**（非互斥）⟹ 用單選 contrasts 表多選＝misrepresent 為互斥單選。且 absent 旗標僅能推、不顯式。 |
| **B：per-flag binary present/absent Signal** | 全 3 旗標各 emit 一 `SignalPosition(contrasts=("present","absent"))` | 複用 primitive 可行，但 **①每 entry 炸成 3 物件（含恆常的 absent，verbose）②丟失「present 子集是一個集合」的框架 ③list→map 形變**。over-emit、非最簡。 |
| **C（選用）：新 `PresenceFlagPosition`（CWA 多選）** | 單一 element：payload＝present 子集、position 載 vocabulary＋per-flag gloss；vocabulary−present＝未舉的旗標（可能性空間，非驗核結論） | 語義正確（多選 ≠ 單選）、單 element 不炸、封閉詞彙顯式、忠於資料本形（共現旗標集）。**＝S0 §3a 預留、S2 deferred 的型別的首個真實落地**。 |

> **spike 校正種子**：S2 的 `is_flag` 設想是 **presence-only**（只 present 可表）；risk_flags 實為 **multi-select over closed vocabulary**（vocabulary 暴露＝agent 知封閉旗標全集）⟹ 比原 is_flag 草案更richer，型別名取 `PresenceFlagPosition`、載 vocabulary（非單純 bool 旗標）。**注**：vocabulary 是**可能性空間**、非「逐旗已驗核」——absence 只表「未舉旗」（§0 fact-finder 守界）。

---

## 1. 範圍（in / out）

### 做（in）
1. **膜 primitive 第 5 變體**（`core/membrane/primitive.py`）：`PresenceFlagPosition(vocabulary, glosses)`＋併入 `Position` union＋`_position_to_json`（kind="presence_flag"）＋`MembraneElement.__post_init__` 加「payload（present 子集）⊆ vocabulary」element-層不變量＋`core/membrane/__init__` 匯出。
2. **新 `core/pipeline/risk_flag_membrane.py`**：`RISK_FLAG_VOCABULARY=("out_of_scope","vulnerability","semantic_drift")`（單一來源、對齊 schema enum）＋`_GLOSS`＋`risk_flags_element(present: list[str]) -> MembraneElement`。
3. **emit 投影**（`report_membrane.project_report_for_agent` applier）：`l1_changes[].risk_flags` 經 `risk_flags_element` 升膜（agent 邊界、S8 樣板）。

### 不做（out）
- **render_json/persisted/`update-report.schema.json`/viewer/前端 risk_flags**：投影在 agent 邊界（applier 後置）；render_json 仍 emit 裸 list（schema 驗 pre-projection、不變）。承 S8 「change_type 同在 schema 為 bare enum、agent 邊界投影不違 schema」之先例。**人類面 risk_flags 呈現整膜＝獨立人類面刀（碰前端）、OUT。**
- **l2_details/其他面的 presence 旗標**：risk_flags 只在 l1_changes（spike 證 `report_renderer.py:198`）；不預建他面。
- **改 risk_flags 生產邏輯／詞彙**（report_renderer.py:400-418）：詞彙閉集不動。
- **其他既有 4 變體行為**：純加法、不改。

---

## 2. Spike 事實（2026-06-06 對真實碼，file:line 已驗）

| 層 | 檔案:line | 事實 |
|---|---|---|
| model | `models/pipeline.py:100,105` | `L1ChangeEntry.risk_flags: list[str] = []`。 |
| 生產者（詞彙權威之一） | `report_renderer.py:400-418` | 只 append `out_of_scope`／`vulnerability`／`semantic_drift` 三者；多選（可同時多個）。 |
| schema 詞彙（權威） | `update-report.schema.json:106-115` | `risk_flags` items enum＝**恰 3 值**＝封閉詞彙單一權威。 |
| render_json emit | `report_renderer.py:198` `"risk_flags": list(e.risk_flags)` | 裸 list；在 l1_changes。 |
| agent 邊界 applier | `report_membrane.py:24` `for e in r.get("l1_changes",[])` | S8 已在此投影 change_type；risk_flags 同點加投影。 |
| applier 唯一消費端 | `update_tool.py:113` | 唯一呼 `project_report_for_agent`（agent MCP）；render_json 先驗 schema、投影後不再驗 ⟹ 形變安全（同 change_type 先例）。 |
| primitive 預留 | `membrane/primitive.py:61-63` | 「presence-only 旗標 S0 §3a 曾草擬 is_flag、不在 S2 建、待首個 presence 生產者落地再加」＝本刀觸發。 |
| 既有變體 | `primitive.py:114` `Position = Signal\|Reserved\|Noise\|Relayed` | 加第 5：`\| PresenceFlagPosition`。 |
| element 不變量樣板 | `primitive.py:132-140` | SignalPosition payload∈contrasts＝樣板；PresenceFlag＝payload⊆vocabulary。 |

**spike 結論**：risk_flags＝真實多選 presence 面、封閉 3-詞彙（schema 權威）；既有 SignalPosition 無法忠實表多選（候選 A/B 否決，§0）⟹ 建第 5 變體 `PresenceFlagPosition`（payload⊆vocabulary）＋risk_flag_membrane 詞彙＋report_membrane agent 邊界投影。render_json/schema/前端不動（S8 先例）。

---

## 3. 設計（exact code；落點標注）

### 3.1 `core/membrane/primitive.py` 新增變體
```python
@dataclass(frozen=True)
class PresenceFlagPosition:
    """CWA 多選旗標：封閉詞彙集中的獨立 presence 旗標（非單選互斥）。

    與 SignalPosition 區別：Signal＝單選（payload 是兄弟集中的『那一個』）；
    PresenceFlag＝多選（payload 是詞彙集的『子集』、旗標可共現）。vocabulary 暴露
    封閉旗標全集（agent 知可能性空間）；未列入 present 的旗標＝**未舉此旗標**
    （fact-finder 守界：不自鑄「已驗證 clear」——生產者只條件式檢查）。
    glosses＝per-flag 極短意義（tuple of (flag, gloss) pairs，frozen-hashable）。
    """
    vocabulary: tuple[str, ...]                 # 全部可能旗標（CWA 封閉詞彙）
    glosses: tuple[tuple[str, str], ...] = ()   # per-flag (flag, 極短意義)

    def __post_init__(self) -> None:
        if not self.vocabulary:
            raise ValueError("PresenceFlagPosition.vocabulary 必須非空（封閉詞彙集）")
        gloss_keys = {k for k, _ in self.glosses}
        if not gloss_keys <= set(self.vocabulary):
            raise ValueError("PresenceFlagPosition.glosses 的 flag 必須 ⊆ vocabulary")
```
`Position` union 加 `| PresenceFlagPosition`（`:114`）。
`MembraneElement.__post_init__`（`:132`）加多選子集不變量：
```python
        if isinstance(self.position, PresenceFlagPosition):
            if not set(self.payload) <= set(self.position.vocabulary):
                raise ValueError(
                    f"payload {self.payload!r} 含 vocabulary 外旗標——"
                    f"present 子集必須 ⊆ {self.position.vocabulary!r}"
                )
```
`_position_to_json`（`:147`）加分支：
```python
    if isinstance(position, PresenceFlagPosition):
        return {
            "kind": "presence_flag",
            "vocabulary": list(position.vocabulary),
            "glosses": {k: v for k, v in position.glosses},
        }
```
`core/membrane/__init__.py`：匯出 `PresenceFlagPosition`（加入 import＋`__all__`）。

### 3.2 新 `core/pipeline/risk_flag_membrane.py`
```python
"""risk_flags 線的膜詞彙：L1 變更的多選風險旗標 → PresenceFlagPosition。

risk_flags＝封閉 3-詞彙（對齊 update-report.schema enum）的多選 presence 旗標；
膜暴露完整詞彙使 agent 知封閉旗標全集（可能性空間）。未舉之旗標＝「未帶此旗標」、
**不**斷言已驗證 clear（生產者條件式檢查，fact-finder 守界）。emit 在 report_membrane
agent 邊界（§8.12）。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, PresenceFlagPosition

# 單一來源：risk_flags 封閉詞彙（對齊 update-report.schema.json risk_flags enum）。
RISK_FLAG_VOCABULARY: tuple[str, ...] = ("out_of_scope", "vulnerability", "semantic_drift")

_GLOSS: tuple[tuple[str, str], ...] = (
    ("out_of_scope", "變更落在宣告 scope 之外"),
    ("vulnerability", "關聯到已知漏洞"),
    ("semantic_drift", "時間軸偵測到語義漂移"),
)


def risk_flags_element(present: list[str]) -> MembraneElement:
    """present 旗標子集 → MembraneElement（多選格內、absence 經 vocabulary 顯式）。

    payload＝present 子集（保序）；position 載完整詞彙＋per-flag gloss。
    present 含 vocabulary 外值 → MembraneElement 子集不變量 ValueError（防呆）。
    """
    return MembraneElement(
        payload=list(present),
        position=PresenceFlagPosition(vocabulary=RISK_FLAG_VOCABULARY, glosses=_GLOSS),
    )
```

### 3.3 `report_membrane.project_report_for_agent` 投影（agent 邊界）
```python
# from the_door.core.pipeline.risk_flag_membrane import risk_flags_element
    for e in r.get("l1_changes", []):
        if "change_type" in e:
            e["change_type"] = change_type_element(e["change_type"]).to_json()
        if "risk_flags" in e:                                    # 新增
            e["risk_flags"] = risk_flags_element(e["risk_flags"]).to_json()
```

---

## 4. 不變量清單

| # | 不變量 | 強制處 | 理論 |
|---|---|---|---|
| P1 | `PresenceFlagPosition`：vocabulary 非空；glosses flag ⊆ vocabulary | primitive `__post_init__` ＋ unit | CWA 封閉詞彙 |
| P2 | `MembraneElement`＋PresenceFlag：payload（present 子集）⊆ vocabulary，否則 ValueError | MembraneElement `__post_init__` ＋ unit | 多選格內（Signal payload∈contrasts 的子集版） |
| P3 | `risk_flags_element(present).to_json()`＝`{value: present-list, position:{kind:"presence_flag", vocabulary:[3], glosses:{3}}}` | risk_flag_membrane ＋ unit | 暴露全詞彙、absence 有意義 |
| P4 | report applier 把 `l1_changes[].risk_flags` 升膜；空 list→`value:[]`＋vocabulary 全曝（agent 知封閉旗標全集；未舉旗 ≠ 已驗證 clear） | report_membrane ＋ characterization | §8.12 agent 邊界／fact-finder 守界 |
| P5 | render_json/`update-report.schema.json`/viewer/前端 **未動**（schema 驗 pre-projection 裸 list） | grep gate ＋ schema 不改 | S8 先例／人類面 out |
| P6 | 既有 4 變體（Signal/Noise/Reserved/Relayed）投影逐字不變（純加法） | primitive 既有測全綠 | 向後相容 |

---

## 5. 測試策略

- **primitive unit**（`tests/unit/core/membrane/` 既有檔擴充）：P1（vocabulary 空→raise；glosses 越界→raise）；P2（`MembraneElement(payload=["x"], position=PresenceFlagPosition(vocabulary=("a",)))`→raise；payload⊆vocab→OK）；to_json kind=="presence_flag"＋vocabulary＋glosses 形狀。
- **risk_flag_membrane unit**（新 `test_risk_flag_membrane.py`）：`RISK_FLAG_VOCABULARY`＝3-set 對齊 schema；`risk_flags_element(["out_of_scope"]).to_json()` value==["out_of_scope"]＋position vocabulary 3＋glosses 3；空 list→value==[]＋vocabulary 全曝；越界旗標→ValueError。
- **report_membrane characterization**（`test_report_membrane.py` 擴充）：`_sample_report` l1_changes[0] risk_flags（已有 `[]`，加一筆含 present 旗標）→投影後 `_is_presence_flag`（value+position.kind=="presence_flag"）；pure-function（入參裸 list 不變）。
- **回歸**：S8 既有 report_membrane 測（change_type/scope/diff）全綠；membrane primitive 既有測全綠（4 變體不破）；全測零回歸。
- **執行**：`cd the_door && PYTHONUTF8=1 python -m pytest -q`。基線 1593＋新測。

---

## 6. spec 完成後 7 點審查（第 4 點 grep 已驗）

1. **單一職責**：primitive 加一獨立變體；risk_flag_membrane 管詞彙＋工廠；applier 多一投影。✓
2. **介面最小**：+1 Position 變體（2 欄）、+1 union 項、+1 to_json 分支、+1 element 不變量、+1 membrane 模組、+1 applier 行。**無改既有變體**。
3. **可測**：純值＋純函式＋applier 投影；P1-P6 皆可斷言。✓
4. **API grep 驗真**（§2）：L1ChangeEntry.risk_flags`:105`✓／生產者`:400-418`✓／schema enum`:106-115`✓／emit`:198`✓／applier`:24`✓／唯一消費`update_tool:113`✓／primitive union`:114`/element`:132`/to_json`:147`✓／__init__ 匯出✓。**無虛構、無循環 import**（risk_flag_membrane→membrane 單向；report_membrane→risk_flag_membrane 單向）。
5. **錯誤路徑**：vocabulary 空/glosses 越界/payload 越界→ValueError（防呆，正常經 risk_flags_element 守住 3-詞彙）；report 缺 risk_flags 鍵→`if "risk_flags" in e` 跳過（不炸）。**hashability 備忘**：PresenceFlag element 的 payload 為 list ⟹ 該 element 不可 hash（其他變體 payload 為 str/tuple＝可 hash）；element 皆 transient 即 to_json，不依賴 hashable（plan 釘一句、不對 MembraneElement 做 set/dict-key）。
6. **向後相容**：純加法；Position union additive（既有 4 變體 isinstance 分支不變）；render_json/schema 不動 ⟹ 持久化/前端零影響。**有意契約變更＝agent 邊界 report 的 risk_flags 由裸 list 升 `{value,position}`**＝characterization 見證（同 S8 change_type 先例）。
7. **文件**：結構化、exact code、file:line、零佔位符；plan 引本 spec §3.x。

---

## 7. 連貫律回驗

- **補齊 primitive**：S0 §3a 預留、S2 deferred 的 presence 型別，於首個真實生產者（risk_flags）落地＝「不預建死碼、真有面才建」原則的正向兌現。
- **與既有軸正交**：presence-flag（多選）⊥ Signal（單選 confidence/scope/diff_state/provenance）⊥ Noise/Relayed；新變體不重疊既有語義。
- **agent 邊界一致**：投影複用 S8 report_membrane applier 樣板（人類面 out），與 change_type/scope_state 同點同模式。
- **未來人類面**：risk_flags 若要上 viewer＝獨立人類面整膜刀（碰前端、最大 blast-radius、OUT）。

---

## 8. 交付物（plan 拆 task）

1. primitive 第 5 變體 `PresenceFlagPosition`（union＋to_json＋element 子集不變量＋__init__ 匯出）＋unit（P1/P2/P6）。
2. `risk_flag_membrane.py`（詞彙＋工廠）＋unit（P3）。
3. report_membrane applier 投影 risk_flags（P4）＋characterization；grep gate（P5）。
4. gate：全測零回歸；grep 確認 render_json/schema/前端未動。

**驗收**：PresenceFlagPosition 不變量（P1/P2）、to_json presence_flag 形狀＋vocabulary 全曝（P3）、applier 投影空與非空（P4）、render_json/schema/前端未動（P5）、既有 4 變體不破（P6）、全測零回歸。
