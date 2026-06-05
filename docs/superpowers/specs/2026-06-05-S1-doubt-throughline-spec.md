# S1 spec：doubt through-line（LLM-facing 膜 retrofit — 首個整膜試點）

> **日期**：2026-06-05　**狀態**：spec（pre-plan，寫前已對真實五層碼 spike）　**性質**：乙案（膜模型）重塑 campaign 的**首個 retrofit 試點**（S1），承 S0 膜 primitive。
> **承接**：S0 spec `docs/superpowers/specs/2026-06-05-S0-membrane-primitive-spec.md`（base＋Signal＋Reserved 已實作、merged）；理論定稿＝種子檔 §8.13；寫 spec 流程＝種子檔 §9。
> **分刀**：S1＝本檔（doubt LLM-facing 膜）。S2＝NoisePosition 首落地（edge/audit）。S3＝RelayedVerdict 首落地（vulnerability cvss）。順序 S0→S1→S2…。
> **連貫律（使用者 2026-06-05 立）**：對前階段＝§0 回核 S0；對後階段＝§7 對 S2 的慣例外推回驗（拿 NoisePosition 真實標的當試金石，確認 S1 萃取的慣例夠 S2 用）。

---

## 0. 理論重錨（種子檔 §9.2 強制；每條釘到一個 S1 決定，防漂移）

寫前已逐項回核種子檔 §8.10/§8.13/§8.2/§8.4 ＋ S0 spec §5/§3a。下表把每條約束釘到具體決定：

| 理論約束（出處） | S1 如何遵守 |
|---|---|
| **膜不變量**（§8.10）：意義靠結構位置、非散文/prompt | doubt 三 enum（current_state/doubt_type/resolution.type）每值意義從**行註解**移進結構：emit 時經 `MembraneElement` 攜 `SignalPosition`；input schema 補 `oneOf+const+description` per value。 |
| **doubt＝整張膜典範試點**（§8.10 翻轉③） | S1 同時驗 B-enum（三 enum→Signal）＋reserved（reason→Reserved）。**S1 無 A-noise**（§3 證：狀態集封閉＋store 強制合法→零 off-grid 殘餘）→ 不觸 NoisePosition（S2）。 |
| **寫嚴讀寬分側**（§8.12 修正②）：B 側 CWA 嚴格封閉 enum | input schema 補 enum＝B 側寫嚴（即使「減掉」原本可接受的任意 target_state 字串，正確）。output 投影＝把封閉集隨值送出。 |
| **fact-finder**（§8.2 A；§8.13-O1） | S1 全程不引入 score/risk/裁決欄；doubt 無外部裁決（非 RelayedVerdict 場）。primitive base 已無裁決欄（I2 結構保證）。 |
| **B 操作位置優先用內部單一來源**（§8.10） | `DoubtLifecycle`（`VALID_TRANSITIONS`/`TERMINAL_STATES`/`_RESOLVING_STATES`）＝current_state 的 preconditions/consequences/co_requires 來源。S1 不另寫死文法，從 lifecycle 導出。 |
| **provenance＝唯一淨新增軸**（§8.13-O3／§8.15） | S1 **不**碰 provenance/版本戳（S7）。doubt 線無 provenance 需求。 |
| **per-value 切法**（§8.13 勘誤） | doubt 三 enum 的值**全落閉集**（store 強制）→ 全格內 Signal；無格外殘餘→無 Noise。reason＝reserved 窗（明文開放，非殘餘）。 |
| **生成性／型驅動**（§8.11） | emit 唯一受祝福路徑＝`MembraneElement.to_json()`（S0 已立）；S1 讓 doubt emit 走它。**單一膜詞彙來源**使 illegal（漂移詞彙、缺意義）難構造。 |
| **剔除紀錄**（§8.4） | 不把量子塌縮/Dither/生產端熔斷搬回；S1 不在生產端關閘、不聚合（doubt_list `total`＝完整計數非有損）。 |

**誠實界線（§8.11）**：S1 只強制**結構**合規（每值帶 position、input 帶 enum）；gloss 文字是否寫得好、狀態語意是否正確仍靠人＋test。型管形狀、管不到判斷。

**LLM-facing 界定（本 spec 範圍的決定性依據，§8.14／todo_output_direction_assessment）**：campaign＝全部 **LLM-facing** 輸出面。doubt 線的 LLM-facing 面＝**兩個 MCP 工具的 input schema（`server.py:137,142` 註冊為 `inputSchema`，consuming LLM 直讀）＋其 output（`wrap` 回應）**。`serialize_doubt`→viewer browser、CLI `doubt_cmd`、`doubt_store` 落盤＝**人類面/持久層、非 LLM-facing → 本刀 out**（§1）。

---

## 1. 範圍（in / out）

### S1 做（in）— doubt 的 LLM-facing 膜
1. **膜詞彙單一來源**：新增 `core/scope/doubt_membrane.py`，為 doubt 三 enum 各提供「值→`SignalPosition`」的工廠，**current_state 的文法從 `DoubtLifecycle` 導出**（不重寫死）。此模組＝S2–S7 照抄的慣例樣板（`{domain}_membrane.py`）。
2. **input schema 寫嚴（B 側 CWA）**：
   - `doubt_transition_tool.TOOL_SCHEMA.target_state`：bare string → `enum`(5 合法 target) ＋ per-value `description`（從詞彙來源）。
   - `doubt_list_tool.TOOL_SCHEMA.state`：→ `enum`(6 狀態) ＋ per-value `description`。
   - `doubt_list_tool.TOOL_SCHEMA.type`：→ `enum`(4 類型) ＋ per-value `description`。
3. **output 投影（B 側送達）**：`doubt_transition_tool` ＋ `doubt_list_tool` 的回應，把 `current_state`/`doubt_type`/`resolution.type` 三欄**經 `MembraneElement.to_json()` 投影**為 `{value, position}`；`reason`（在 resolution.description 之外，若出現於 state_history）走 `ReservedPassthrough`。**契約改動 → characterization 先行**（§6）。
4. **膜層補完（半膜→全膜）**：`schemas/doubt-record.schema.json` 三 enum 補 per-value 意義（`oneOf`+`const`+`description` 或 enum 並列 + `$comment` 對應），**與詞彙來源同源、parity test 把關**（§6）。
5. **連貫性回驗測試**：S1 emit 形狀對 S0 primitive 充分（已於 S0 §5 spec 階段斷言，S1 落地驗證）。

### S1 不做（out）
- **人類面 emit（留作後續「向人類面傳播」）**：`serialize_doubt`（→`annotation.py:131`→viewer browser）、CLI `doubt_cmd.py`、`doubt_store._serialize_doubt`（落盤，照 S0「snapshot 存 bare 值」原則維持 bare）。理由＝非 LLM-facing；S1 立的投影慣例足供它們日後照抄。
- **viewer `ui-doubt.js`**（漂移詞彙 open/assigned/resolved，§8.16）＝人類顯示層，隨人類面 emit 一起後做。
- **NoisePosition / RelayedVerdict**：doubt 線無 off-grid 殘餘、無外部裁決（§0、§3）→ 不需；首落地 S2/S3。
- **provenance / 版本戳**（S7）。
- **doubt 三手搓 builder 的「合一」重構**：S1 只把三欄投影插入既有 builder；builder 去重（甲案式）非本刀目的（若投影自然收斂出共用 helper 則順手，不強求）。

---

## 2. Spike 事實（2026-06-05 對真實五層碼，file:line 已驗）

| 層 | 檔案:line | 事實 |
|---|---|---|
| 模型 | `models/doubt.py:34/35`、`:22` | `doubt_type`(4 值)／`current_state`(6 值)／`Resolution.type`(3 值) 全 bare `str`、valid set 住**行註解**。`DoubtRecord` 非 frozen（狀態轉換需改）。 |
| 膜(schema) | `schemas/doubt-record.schema.json:27-48,113-150` | 三 enum 閉集在 schema（CWA✓）但僅**欄位級 description**、零每值意義；`resolution.type`(`:129-133`) **連 description 都無**。`reason`(`:98-107`)＝`oneOf null\|string`＝reserved 窗。 |
| lifecycle | `core/scope/doubt_lifecycle.py:32/40/41/43` | **操作位置單一來源**：`VALID_TRANSITIONS`(6 狀態圖)／`TERMINAL_STATES`／`_RESOLVING_STATES`／`is_terminal`／`check_transition`(`:46` store 強制合法)。**狀態集封閉＋store 強制→doubt 全程無 off-grid 殘餘。** |
| emission(LLM) | `mcp/tools/doubt_transition_tool.py:12-15,75-94`；`doubt_list_tool.py:11-18,40-65`；`mcp/server.py:137,142` | 兩工具 output 手搓 bare；`target_state`(`:12`)/`state`(`:11`)/`type`(`:15`) input schema **無 enum**；TOOL_SCHEMA 經 `server.py` 註冊為 LLM `inputSchema`。`_response_envelope.wrap` 只注 `next_actions`、非值級咽喉。 |
| emission(人類) | `core/ui/serializers.py:27`→`api/handlers/annotation.py:131`；`cli/doubt_cmd.py:252` | `serialize_doubt`(key `state`、無 resolution)→viewer browser；CLI `_serialize_doubt_brief`→終端。**皆非 LLM-facing→out。** |
| 顯示 | `viewer/js/ui-doubt.js:3-8` | `MAP{open/assigned/resolved/escalated}`＝**自成一套且與後端 6 狀態漂移**的詞彙（重複且對不上）。人類顯示層→out。 |

**spike 結論**：doubt 線 LLM-facing 面＝2 MCP 工具（input+output）；三 enum 全閉集→全 Signal、reason→Reserved、零 Noise/Verdict；操作位置來源現成（lifecycle）。**S1 用 S0 兩變體足夠、無預見返工。**

---

## 3. 設計（exact code 草圖；落點標注）

### 3.1 膜詞彙單一來源 `core/scope/doubt_membrane.py`（新增）

> 慣例樣板：一個 through-line 一個 `{domain}_membrane.py`，把該域 enum 的「值→SignalPosition」集中。current_state 的文法**從 `DoubtLifecycle` 導出**（單一來源、不重寫死）；gloss 是此處唯一手寫的人類意圖殘餘（極短）。

```python
"""doubt 線的膜詞彙：把 doubt 三 enum 的每值意義結構化為 SignalPosition。

意義來源單一化（種子檔 §8.10）：current_state 的前件/後件/共依從 DoubtLifecycle
導出（不重寫死文法）；gloss＝極短指稱注解（此處唯一手寫處）。
S2–S7 照此樣板各建 {domain}_membrane.py。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, ReservedPassthrough, SignalPosition
from the_door.core.scope.doubt_lifecycle import DoubtLifecycle

_LC = DoubtLifecycle()

# 唯一手寫處：每值極短 gloss（人類意圖殘餘，語法捕不到）。
_STATE_GLOSS = {
    "discovered": "剛發現、未調查",
    "investigating": "調查中（已指派）",
    "escalated": "已升級待裁決",
    "explained": "已查證為預期行為、非缺陷（終態）",
    "fixed": "已修復（終態）",
    "accepted_risk": "風險已接受（終態）",
}
_TYPE_GLOSS = {
    "out_of_scope": "超出已宣告範圍",
    "in_scope_incomplete": "範圍內但不完整",
    "anomaly": "異常、與預期不符",
    "low_confidence": "抽取信心低",
}
_RESOLUTION_GLOSS = {  # ＝ _RESOLVING_STATES，終態裁決方式
    "explained": "查證為預期行為",
    "fixed": "已修復",
    "accepted_risk": "風險已接受",
}


def current_state_signal(value: str) -> SignalPosition:
    """current_state（6 值圖）→ Signal；文法從 DoubtLifecycle 導出。"""
    states = tuple(_LC.VALID_TRANSITIONS.keys())
    preconds = tuple(s for s, tos in _LC.VALID_TRANSITIONS.items() if value in tos)
    return SignalPosition(
        contrasts=states,
        gloss=_STATE_GLOSS[value],
        preconditions=preconds,                                  # 反查圖
        consequences=("terminal",) if _LC.is_terminal(value) else
                     tuple(sorted(_LC.VALID_TRANSITIONS[value])),  # 可達 targets
        co_requires=("reason",) if value in _LC._RESOLVING_STATES else (),
    )


def doubt_type_signal(value: str) -> SignalPosition:
    """doubt_type（4 值純 enum）→ Signal（只 contrasts+gloss）。"""
    return SignalPosition(contrasts=tuple(_TYPE_GLOSS.keys()), gloss=_TYPE_GLOSS[value])


def resolution_type_signal(value: str) -> SignalPosition:
    """resolution.type（3 值純 enum）→ Signal；contrasts＝_RESOLVING_STATES。"""
    return SignalPosition(
        contrasts=tuple(sorted(_LC._RESOLVING_STATES)), gloss=_RESOLUTION_GLOSS[value]
    )


def current_state_element(value: str) -> MembraneElement:
    return MembraneElement(payload=value, position=current_state_signal(value))


def doubt_type_element(value: str) -> MembraneElement:
    return MembraneElement(payload=value, position=doubt_type_signal(value))


def resolution_type_element(value: str) -> MembraneElement:
    return MembraneElement(payload=value, position=resolution_type_signal(value))


def free_text_element(text: str) -> MembraneElement:
    """doubt 線的 free-text（reason／resolution.description）＝reserved 窗。"""
    return MembraneElement(payload=text, position=ReservedPassthrough())


# === input schema 衍生（零副本：input 的 enum+description 從 gloss 建構，非手抄）===
_TARGET_STATES = ("investigating", "explained", "fixed", "escalated", "accepted_risk")  # discovered 非 target


def _enum_schema(keys: tuple[str, ...], gloss: dict[str, str], lead: str) -> dict:
    """enum＝contrasts（結構化封閉集）；description＝lead＋gloss 串接（§8.10：contrasts+gloss）。"""
    return {
        "type": "string",
        "enum": list(keys),
        "description": lead + "；".join(f"{k}={gloss[k]}" for k in keys) + "。",
    }


def target_state_schema() -> dict:
    return _enum_schema(_TARGET_STATES, _STATE_GLOSS, "目標狀態。")


def state_filter_schema() -> dict:
    return _enum_schema(tuple(_STATE_GLOSS.keys()), _STATE_GLOSS, "依狀態篩選。")


def type_filter_schema() -> dict:
    return _enum_schema(tuple(_TYPE_GLOSS.keys()), _TYPE_GLOSS, "依類型篩選。")
```

> **單一來源（零副本，非「副本+測試」）**：`_*_GLOSS` 是每值意義的**唯一**來源。input schema（§3.2）由上面三個 builder **在 import 時從 gloss 建構**——無手抄、無漂移可能。`enum`＝結構化 contrasts、`description`＝gloss（§8.10：contrasts+gloss 正是 B 操作位置）。唯一不可衍生者＝靜態 `doubt-record.schema.json`（§3.4，不能 import Python）→ 維持**一份** parity-test 守護的副本。

### 3.2 input schema 寫嚴（B 側 CWA）— 由 gloss 衍生、零副本

input schema **不手寫**，從 §3.1 builder 建構（單一來源）。

`doubt_transition_tool.py` TOOL_SCHEMA：
```python
from the_door.core.scope import doubt_membrane
...
    "properties": {
        "doubt_id": {...},
        "target_state": doubt_membrane.target_state_schema(),   # 衍生：enum=5 target + gloss desc
        "actor": {...},
        ...
    },
```
`doubt_list_tool.py`：`"state": doubt_membrane.state_filter_schema()`（6 狀態）、`"type": doubt_membrane.type_filter_schema()`（4 類型）。

> 註：`target_state` 合法值＝**可被轉入的狀態**＝`{investigating, explained, fixed, escalated, accepted_risk}`（`discovered` 是初態、不可為 target；與 `:60` 既有守衛集一致，grep 已驗）。先例：既有 5 工具 inputSchema 皆用 `enum`（grep 驗），本刀一致。

### 3.3 output 投影（兩 MCP 工具）

emit 形狀改動（**契約變更、characterization 先行**）：三 enum 欄 bare → `{value, position}`。

`doubt_transition_tool.py` 回應（差異部分）：
```python
    from the_door.core.scope.doubt_membrane import (
        current_state_element, doubt_type_element, resolution_type_element,
    )
    return wrap({
        ...
        "doubt_type": doubt_type_element(doubt.doubt_type).to_json(),
        "current_state": current_state_element(doubt.current_state).to_json(),
        ...
        "resolution": (
            {
                "type": resolution_type_element(doubt.resolution.type).to_json(),
                "description": free_text_element(doubt.resolution.description).to_json(),  # reserved 窗：真正驗 Reserved
                "resolved_by": doubt.resolution.resolved_by,
                "resolved_at": doubt.resolution.resolved_at,
            }
            if doubt.resolution is not None else None
        ),
    }, project_path=project_root, context="mcp")
```
`doubt_list_tool.py`：同樣三欄投影；`total` 維持裸 int（完整計數、非有損聚合，§0）。

> **真驗整膜**：`resolution.description` 經 `free_text_element` 出 `{value, position:{kind:"reserved"}}`——告訴消費端 LLM「此處刻意 free-text、非封閉詞彙」。S1 因此在**真實 emit**（非僅 §6 連貫性測試）同時驗 Signal（三 enum）＋Reserved（description），坐實 §0「doubt＝整張膜試點」。

> **投影 helper 順手收斂（非強求）**：若 transition/list 兩處 per-doubt dict 構造在投影後自然抽出共用 `_project_doubt(d) -> dict`，順手抽（消重複）；但**不**為消重大改 builder 結構（§1 out）。

### 3.4 膜層補完 `schemas/doubt-record.schema.json`

三 enum 的 per-value 意義填入膜。形式＝**JSON Schema 原生 `oneOf` of `const`+`description`**（§8.16「機制已在、未用」；Draft 2020-12 標準、驗證語意與 `enum` 等價）：

```jsonc
"current_state": {
  "type": "string",
  "oneOf": [
    { "const": "discovered",     "description": "剛發現、未調查" },
    { "const": "investigating",  "description": "調查中（已指派）" },
    { "const": "escalated",      "description": "已升級待裁決" },
    { "const": "explained",      "description": "已查證為預期行為、非缺陷（終態）" },
    { "const": "fixed",          "description": "已修復（終態）" },
    { "const": "accepted_risk",  "description": "風險已接受（終態）" }
  ],
  "description": "當前狀態"
}
```

意義字串**＝`doubt_membrane._*_GLOSS` 對應值**（此靜態 schema 是 J3 唯一副本、parity test 逐字守 vs gloss）。

> **已驗（2026-06-05，非待辦）**：`doubt_store.py:39-48` 用 `jsonschema` 驗證持久化 doubt record。實測 `oneOf`+`const`（Draft 2020-12）驗證語意與 `enum` 等價——合法值通過、非法值（如 `banana`）照拒。故換形式**不破壞既有 doubt-record 驗證**；既有 schema 測試仍綠。

---

## 4. 不變量清單（S1 強制；每條一個「非法即拋」或 parity 測試）

| # | 不變量 | 強制處 | 對應理論 |
|---|---|---|---|
| J1 | doubt 三 enum 的 emit 必經 `MembraneElement`（不再 bare） | 兩工具 output ＋ characterization 對照新形狀 | 膜不變量：意義靠結構 |
| J2 | input `target_state`/`state`/`type` 帶 `enum`（封閉集） | TOOL_SCHEMA ＋ schema 斷言測試 | B 側 CWA 寫嚴 |
| J3 | **per-value 意義單一來源（零副本）**：input schema 由 `_*_GLOSS` builder **衍生**（無副本）；record schema＝唯一副本、經 parity test == `_*_GLOSS` | builder 衍生（input）＋ parity test（record schema vs gloss） | 杜絕第 N 份 copy（§8.16）——且不靠「副本+測試」自我違反 |
| J4 | current_state 的 preconditions/consequences/co_requires **從 `DoubtLifecycle` 導出**（改 lifecycle 自動跟動） | `doubt_membrane` 不寫死＋測試改 lifecycle 驗連動 | B 操作位置用內部單一來源 |
| J5 | doubt emit **零 NoisePosition/RelayedVerdict**（只 Signal＋Reserved＋裸標量） | emit 路徑型別 ＋ 測試 | per-value 切法：doubt 無 off-grid（§0/§3） |

> J3/J4 是 S1 最關鍵的兩條：J3 證「單一來源」（膜的核心價值），J4 證「操作位置不重寫死」。S2–S7 照抄此兩律。

---

## 5. 慣例萃取（S1 交付給 S2–S7 的可複用樣板）

S1 完成後，後續 through-line 照抄：
1. **`{domain}_membrane.py`**：值→`SignalPosition` 工廠＋input schema builder，文法從該域既有單一來源導出（doubt＝Lifecycle；severity＝？S3 查），gloss dict 唯一手寫。
2. **input schema 衍生**：bare string → `domain_membrane.X_schema()`（enum+desc 從 gloss 建構、零副本）。
3. **output 投影**：emit 欄經 `MembraneElement.to_json()`，characterization 先行。
4. **schema 補完**：靜態 schema per-value 意義填膜、parity test 守唯一副本。
5. **衍生鎖（input）＋ parity（schema，J3）＋ 導出測試（J4）** 三條保護網照搬。

---

## 6. 測試策略

- **characterization 先行（動契約前的安全網，§9.4）**：寫 J1/J3 改動前，先對兩 MCP 工具現狀 output 寫 characterization test（釘 `current_state:"explained"` 等 bare 現狀），紅燈確認捕捉到既有形狀；reshape 後更新斷言為 `{value,position}` 新形狀＝**有意契約變更的見證**，非靜默破壞。
- **單元**（`tests/unit/core/scope/test_doubt_membrane.py`）：三工廠各 happy-path＋current_state 的 preconditions 反查正確（explained→{investigating,escalated}）＋co_requires（_RESOLVING→reason）。
- **input schema 衍生鎖**（`tests/unit/mcp/`）：三欄含 `enum`、enum 集＝builder 從 gloss 取的 key 集（`target_state`=5、`state`=6、`type`=4）；各 gloss 片語 ∈ 對應 description（鎖衍生契約、非比對副本）。
- **J3 parity（唯一副本）**：`doubt-record.schema.json` 三 enum 的 `oneOf const→description` == `_*_GLOSS`（逐字）。input 側因衍生、無需 parity（無副本可漂）。
- **J4 導出連動**：monkeypatch/擴 `VALID_TRANSITIONS` 加一狀態，`current_state_signal` 的 contrasts 自動含新狀態（證非寫死）。
- **J5**：投影 emit 的 position kind ∈ {signal, reserved}，無 noise/verdict。
- **連貫性回驗**：S0 `test_s1_coherence.py` 已綠；S1 落地後該檔仍綠（S0 地基未鬆動）。
- **零回歸**：除 characterization 既有斷言的**有意更新**外，全測維持綠（純加法於詞彙/schema；emit 形狀變更由 characterization 圈住）。執行 `cd the_door && PYTHONUTF8=1 python -m pytest -q`。

---

## 7. 對 S2（NoisePosition）的慣例外推回驗 ★（連貫律落點）

> 目的：拿 S2 真實標的當試金石，確認 S1 萃取的慣例（§5）夠 S2 用、不返工。

S2＝edge_projection F5 殘餘桶／audit gap-kinds 首落地 NoisePosition。逐點驗：
- **`{domain}_membrane.py` 樣板**：S2 建 `edge_membrane.py`，同樣「值→position 工廠」——但 S2 的值含**格外殘餘**（unrecognized/skipped_dynamic）→ 產 `NoisePosition`（S2 建型）而非 Signal。**S1 樣板的形狀（工廠函式＋gloss dict＋從單一來源導出）對 S2 適用**；差別只在 position 變體，不在樣板結構。✓
- **characterization 先行**：S2 動 `edge_projection` output（F5 併桶/丟基數）＝契約變更→同 S1 用 characterization 圈住。✓
- **parity（J3）/導出（J4）**：S2 的 gap_kind 優先序（`corrupt>indeterminate>evolutionary>reserved`）亦有單一來源（§8.8 F1）→ J4 導出律適用；gloss parity 適用。✓
- **唯一需 S2 補的新慣例**：NoisePosition「聚合必帶基數比例」不變量（§3a），S1 無此（doubt total 非有損）→ **S1 不預建、S2 自帶**，符合「不鎖死地基」。✓

**回驗結論**：S1 的五點慣例（§5）對 S2 充分；S2 只需新增 NoisePosition 型別與其聚合不變量，**樣板/characterization/parity/導出四律照抄**。零預見返工。

---

## 8. spec 完成後 7 點審查（種子檔 §9.4；第 4 點 grep 已驗）

1. **單一職責**：`doubt_membrane` 只管「doubt 值→position」；工具只多一層投影。✓
2. **介面最小**：詞彙模組對外＝3 signal 工廠＋3 element 工廠＋1 free_text；無多餘。
3. **可測**：純函式工廠、parity/導出皆可斷言。✓
4. **API 名 grep 驗真**（file:line 在 §2）：`VALID_TRANSITIONS`/`TERMINAL_STATES`/`_RESOLVING_STATES`/`is_terminal`✓／`doubt_transition_tool.TOOL_SCHEMA`/`doubt_list_tool.TOOL_SCHEMA`✓／`server.py:137,142` 註冊✓／`serialize_doubt`→`annotation.py:131`✓／`ui-doubt.js` MAP✓／`MembraneElement`/`SignalPosition`/`ReservedPassthrough`/`to_json`（S0 已實作）✓。**無虛構 API。**
5. **錯誤路徑**：input enum 拒非法 target（既有 `:60` 守衛保留為深度防禦）；`_*_GLOSS` 缺鍵會 KeyError＝顯式失敗（非法值早爆）。
6. **向後相容**：input schema 純加 enum（既有合法呼叫不受影響、非法呼叫本就該拒）；**output 投影＝有意契約變更**，由 characterization 見證、非靜默 → 對 LLM 消費端是「資訊增加」（多了 position）。人類面 emit 不動（out）→ viewer/CLI 零影響。
7. **文件**：結構化、exact code 草圖、零佔位符。

---

## 9. 交付物（plan 階段拆 task 用）

1. `tests/unit/mcp/test_doubt_tools_characterization.py`（**先行**：釘兩工具 output bare 現狀）
2. `src/the_door/core/scope/doubt_membrane.py`（詞彙單一來源＋3 signal/element 工廠＋free_text＋3 input schema builder）
3. `tests/unit/core/scope/test_doubt_membrane.py`（工廠＋J4 導出連動）
4. `src/the_door/mcp/tools/doubt_transition_tool.py`（input enum＋output 投影）
5. `src/the_door/mcp/tools/doubt_list_tool.py`（input enum×2＋output 投影）
6. `schemas/doubt-record.schema.json`（三 enum per-value 意義補完）
7. `tests/unit/.../test_doubt_membrane_parity.py`（J3：record schema `oneOf const→description` == gloss 逐字；input 衍生鎖在 deliverable 4 的 mcp 測）
8. characterization 斷言更新為 `{value,position}` 新形狀（見證契約變更）

**驗收**：全測零回歸（除 characterization 有意更新）、三 enum emit 帶 position、input 帶 enum（builder 衍生）、J3 input 零副本＋record schema parity 逐字守、J4 改 lifecycle 自動連動、J5 doubt emit 零 noise/verdict、S0 連貫性測試仍綠。

**S1 完成 → 進 S2（NoisePosition／edge）spec**：起 S2 前重跑種子檔 §9.2 理論重錨、讀本檔 §5（慣例樣板）＋§7（對 S2 連貫性回驗點）＋S0 §3a（NoisePosition 方向）。
