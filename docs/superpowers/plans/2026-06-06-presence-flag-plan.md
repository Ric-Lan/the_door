# presence-flag Implementation Plan（risk_flags 多選旗標整膜）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 補膜 primitive **第 5 變體 `PresenceFlagPosition`**（CWA 多選），把 `L1ChangeEntry.risk_flags`（封閉 3-詞彙多選）在 agent 邊界由裸 list 升膜投影——暴露封閉旗標全集（可能性空間），不碰 render_json/schema/前端。

**Architecture:** 三層純加法，承 S8 report applier 樣板。① primitive 加獨立 frozen dataclass 變體＋union＋to_json 分支＋element 子集不變量；② 新 `risk_flag_membrane.py` 持單一詞彙來源＋工廠；③ `report_membrane.project_report_for_agent` applier 多一行投影。投影只在 agent 讀邊界（`update_tool.py:113` 唯一消費），render_json 仍 emit 裸 list、schema 驗 pre-projection（同 S8 change_type 先例）。

**Tech Stack:** Python 3（frozen dataclass、union type）、pytest。雙層 repo：git 根＝`C:/Users/Ric/Desktop/the_door`、pytest cwd＝內層 `the_door/`、Windows 前置 `PYTHONUTF8=1`。

**權威來源 — 生產碼 exact code 在 spec，勿在本 plan 重貼（防雙源漂移）：**
- spec：`docs/superpowers/specs/2026-06-06-presence-flag-spec.md`
  - §3.1＝primitive 變體 exact code（Task 1 貼）
  - §3.2＝risk_flag_membrane exact code（Task 2 貼）
  - §3.3＝report_membrane 投影 exact code（Task 3 貼）
  - §0 fact-finder 守界＝**gloss/斷言只寫「未舉此旗標」、絕不寫「checked/verified clear」**
  - §4＝P1-P6 不變量表

**🔴 跨刀守界（雙審已釘，impl 務必守）：**
- **absence 語義**：vocabulary 是**可能性空間**、非逐旗驗核結論。生產者（`report_renderer.py:400-418`）對 out_of_scope/vulnerability 條件式檢查⟹「未舉旗」≠「已驗證 clear」。gloss 與測試斷言**禁**出現「checked／verified clear／已檢查未觸發」字樣。
- **hashability**：PresenceFlag element 的 payload 為 list ⟹ 該 element **不可 hash**。element 皆 transient 即 to_json，不依賴 hashable；**勿對 MembraneElement 做 set/dict-key**。

---

## File Structure

| 檔案 | 動作 | 職責 |
|---|---|---|
| `the_door/src/the_door/core/membrane/primitive.py` | Modify | 加 `PresenceFlagPosition` 變體＋union（`:114`）＋element 子集不變量（`:132`）＋`_position_to_json` 分支（`:147`） |
| `the_door/src/the_door/core/membrane/__init__.py` | Modify | 匯出 `PresenceFlagPosition`（import＋`__all__`） |
| `the_door/tests/unit/core/membrane/test_primitive.py` | Modify | 既有 `test_facade_exports` 的 `__all__` set 斷言加新符號 |
| `the_door/tests/unit/core/membrane/test_presence_flag.py` | Create | P1/P2/P6 primitive unit |
| `the_door/src/the_door/core/pipeline/risk_flag_membrane.py` | Create | `RISK_FLAG_VOCABULARY`＋`_GLOSS`＋`risk_flags_element` 工廠 |
| `the_door/tests/unit/core/pipeline/test_risk_flag_membrane.py` | Create | P3 詞彙＋工廠 unit |
| `the_door/tests/unit/core/pipeline/test_report_membrane.py` | Modify | P4 characterization：`_sample_report` 加 present 旗標筆＋投影斷言 |

**測試路徑命名**：membrane primitive 既有測在 `tests/unit/core/membrane/`；新變體單獨開 `test_presence_flag.py`（比照既有 `test_noise_position.py`／`test_relayed_verdict.py` 一變體一檔慣例）。

---

## Task 1: primitive 第 5 變體 `PresenceFlagPosition`

**Files:**
- Modify: `the_door/src/the_door/core/membrane/primitive.py`（union `:114`／element 不變量 `:132`／to_json `:147`）
- Modify: `the_door/src/the_door/core/membrane/__init__.py`
- Modify: `the_door/tests/unit/core/membrane/test_primitive.py`（`test_facade_exports` 的 `__all__` set）
- Test: `the_door/tests/unit/core/membrane/test_presence_flag.py`（新）

- [ ] **Step 1: 寫失敗測試（新檔 `test_presence_flag.py`）**

```python
"""presence-flag：第 5 變體 PresenceFlagPosition 不變量與投影（P1/P2/P6）。

fact-finder 守界（spec §0）：vocabulary＝可能性空間（封閉旗標全集），
未列入 present 的旗標＝「未舉此旗標」、絕非「已驗證 clear」。
"""
import pytest

from the_door.core.membrane.primitive import (
    MembraneElement,
    PresenceFlagPosition,
    SignalPosition,
)


# --- P1：PresenceFlagPosition 自身不變量 ---
def test_presence_flag_minimal():
    """vocabulary 必填、glosses 預設空 tuple。"""
    pf = PresenceFlagPosition(vocabulary=("a", "b", "c"))
    assert pf.vocabulary == ("a", "b", "c")
    assert pf.glosses == ()


def test_presence_flag_with_glosses():
    pf = PresenceFlagPosition(
        vocabulary=("a", "b"), glosses=(("a", "旗 a"), ("b", "旗 b"))
    )
    assert dict(pf.glosses) == {"a": "旗 a", "b": "旗 b"}


def test_presence_flag_empty_vocabulary_raises():
    """P1：vocabulary 非空（CWA 封閉詞彙集）。"""
    with pytest.raises(ValueError, match="非空"):
        PresenceFlagPosition(vocabulary=())


def test_presence_flag_gloss_outside_vocabulary_raises():
    """P1：glosses 的 flag 必須 ⊆ vocabulary。"""
    with pytest.raises(ValueError, match="vocabulary"):
        PresenceFlagPosition(vocabulary=("a",), glosses=(("b", "越界旗"),))


# --- P2：MembraneElement + PresenceFlag 子集不變量 ---
def test_element_present_subset_ok():
    """happy-path：present 子集 ⊆ vocabulary。"""
    el = MembraneElement(
        payload=["a", "c"],
        position=PresenceFlagPosition(vocabulary=("a", "b", "c")),
    )
    assert el.payload == ["a", "c"]


def test_element_empty_present_ok():
    """空 present（未舉任何旗）合法——vocabulary 仍全曝。"""
    el = MembraneElement(
        payload=[], position=PresenceFlagPosition(vocabulary=("a", "b"))
    )
    assert el.payload == []


def test_element_present_outside_vocabulary_raises():
    """P2：present 含 vocabulary 外旗標 → ValueError。"""
    with pytest.raises(ValueError, match="vocabulary 外旗標"):
        MembraneElement(
            payload=["x"],
            position=PresenceFlagPosition(vocabulary=("a", "b")),
        )


# --- to_json 形狀 ---
def test_to_json_presence_flag_shape():
    el = MembraneElement(
        payload=["a"],
        position=PresenceFlagPosition(
            vocabulary=("a", "b", "c"),
            glosses=(("a", "旗 a"), ("b", "旗 b"), ("c", "旗 c")),
        ),
    )
    assert el.to_json() == {
        "value": ["a"],
        "position": {
            "kind": "presence_flag",
            "vocabulary": ["a", "b", "c"],
            "glosses": {"a": "旗 a", "b": "旗 b", "c": "旗 c"},
        },
    }


# --- P6：既有變體不破（純加法回歸哨兵）---
def test_p6_signal_variant_unchanged():
    """加第 5 變體後，既有 SignalPosition 投影逐字不變。"""
    el = MembraneElement(
        payload="high",
        position=SignalPosition(contrasts=("high", "low"), gloss="x"),
    )
    assert el.to_json()["position"]["kind"] == "signal"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_presence_flag.py -q`
Expected: FAIL — `ImportError: cannot import name 'PresenceFlagPosition'`

- [ ] **Step 3: 實作（primitive.py）— 貼 spec §3.1 exact code**

依 spec §3.1：
1. 在 `RelayedVerdict` 之後、`Position = ...`（`:114`）之前，新增 `@dataclass(frozen=True) class PresenceFlagPosition`（spec §3.1 完整 class，含 `vocabulary`／`glosses` 欄與 `__post_init__` 兩道 ValueError）。
2. `Position` union（`:114`）末加 `| PresenceFlagPosition`，並把註解 `S3 階段 4 變體` 更新為 `5 變體`。
3. `MembraneElement.__post_init__`（`:132`，現有 `if isinstance(self.position, SignalPosition):` 區塊之後）加 spec §3.1 的 PresenceFlag 子集不變量區塊（`if isinstance(self.position, PresenceFlagPosition): ... ValueError("payload ... 含 vocabulary 外旗標 ...")`）。
4. `_position_to_json`（`:147`，`RelayedVerdict` 分支之後、`raise TypeError` 之前）加 spec §3.1 的 `if isinstance(position, PresenceFlagPosition): return {"kind": "presence_flag", "vocabulary": [...], "glosses": {...}}` 分支。

> exact code 見 spec §3.1，逐字貼入；ValueError 訊息含「非空」「vocabulary」「vocabulary 外旗標」字樣以對齊 Step 1 的 `match=`。

- [ ] **Step 4: 匯出（`__init__.py`）**

在 `the_door/src/the_door/core/membrane/__init__.py` 的 import 區與 `__all__` list 各加一行 `PresenceFlagPosition`（維持字母序——加在 `Position` 之前）：

```python
from the_door.core.membrane.primitive import (
    GAP_KIND_PRIORITY,
    MembraneElement,
    NoisePosition,
    Position,
    PresenceFlagPosition,
    RelayedVerdict,
    ReservedPassthrough,
    SignalPosition,
)

__all__ = [
    "GAP_KIND_PRIORITY",
    "MembraneElement",
    "NoisePosition",
    "Position",
    "PresenceFlagPosition",
    "RelayedVerdict",
    "ReservedPassthrough",
    "SignalPosition",
]
```

- [ ] **Step 5: 更新既有 facade 測試（`test_primitive.py`）**

`test_facade_exports`（約 `:119`）的 `set(membrane.__all__) == {...}` 斷言加 `"PresenceFlagPosition"`：

```python
    assert set(membrane.__all__) == {
        "GAP_KIND_PRIORITY",
        "MembraneElement",
        "NoisePosition",
        "Position",
        "PresenceFlagPosition",
        "RelayedVerdict",
        "ReservedPassthrough",
        "SignalPosition",
    }
```

- [ ] **Step 6: 跑測試確認通過（含既有 primitive 測全綠＝P6）**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/ -q`
Expected: PASS（新 `test_presence_flag.py` 全綠＋既有 `test_primitive.py`/`test_noise_position.py`/`test_relayed_verdict.py`/`test_s1_coherence.py` 不破）

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/membrane/primitive.py the_door/src/the_door/core/membrane/__init__.py the_door/tests/unit/core/membrane/test_presence_flag.py the_door/tests/unit/core/membrane/test_primitive.py
git commit -m "feat(membrane): PresenceFlagPosition 第 5 變體 — CWA 多選旗標 (P1)"
```

---

## Task 2: `risk_flag_membrane.py` 詞彙＋工廠

**Files:**
- Create: `the_door/src/the_door/core/pipeline/risk_flag_membrane.py`
- Test: `the_door/tests/unit/core/pipeline/test_risk_flag_membrane.py`（新）

- [ ] **Step 1: 寫失敗測試（新檔 `test_risk_flag_membrane.py`）**

```python
"""risk_flag_membrane：詞彙單一來源＋工廠（P3）。

詞彙＝封閉 3-set，對齊 update-report.schema.json risk_flags enum。
absence 守界（spec §0）：未舉旗標＝「未帶此旗標」、非「已驗證 clear」。
"""
import json
from pathlib import Path

import pytest

from the_door.core.pipeline.risk_flag_membrane import (
    RISK_FLAG_VOCABULARY,
    risk_flags_element,
)


def test_vocabulary_is_closed_3_set():
    assert RISK_FLAG_VOCABULARY == ("out_of_scope", "vulnerability", "semantic_drift")


def test_vocabulary_aligns_with_schema_enum():
    """詞彙單一來源對齊 schema risk_flags items enum（防漂移）。"""
    schema_path = (
        Path(__file__).resolve().parents[4] / "schemas" / "update-report.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    enum = (
        schema["properties"]["l1_changes"]["items"]["properties"]
        ["risk_flags"]["items"]["enum"]
    )
    assert set(enum) == set(RISK_FLAG_VOCABULARY)


def test_element_single_present_flag():
    j = risk_flags_element(["out_of_scope"]).to_json()
    assert j["value"] == ["out_of_scope"]
    assert j["position"]["kind"] == "presence_flag"
    assert j["position"]["vocabulary"] == list(RISK_FLAG_VOCABULARY)
    assert set(j["position"]["glosses"]) == set(RISK_FLAG_VOCABULARY)


def test_element_empty_present_exposes_full_vocabulary():
    """空 present（未舉任何旗）→ value:[]＋vocabulary 全曝（可能性空間）。"""
    j = risk_flags_element([]).to_json()
    assert j["value"] == []
    assert j["position"]["vocabulary"] == list(RISK_FLAG_VOCABULARY)


def test_element_multi_present_preserves_order():
    """多選共現、保序。"""
    j = risk_flags_element(["out_of_scope", "vulnerability"]).to_json()
    assert j["value"] == ["out_of_scope", "vulnerability"]


def test_element_out_of_vocabulary_raises():
    """防呆：present 含詞彙外值 → 子集不變量 ValueError。"""
    with pytest.raises(ValueError, match="vocabulary 外旗標"):
        risk_flags_element(["bogus_flag"])
```

> 註：`parents[4]` 從 `tests/unit/core/pipeline/test_risk_flag_membrane.py` 上溯 4 層到內層 repo 根（`the_door/`），再進 `schemas/`。已 `git ls-files` 驗：schema 在 `the_door/schemas/update-report.schema.json`（**非** `src/the_door/schemas/`）；JSON nesting `properties.l1_changes.items.properties.risk_flags.items.enum` 亦已驗。

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/pipeline/test_risk_flag_membrane.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'the_door.core.pipeline.risk_flag_membrane'`

- [ ] **Step 3: 實作 — 貼 spec §3.2 exact code**

新建 `the_door/src/the_door/core/pipeline/risk_flag_membrane.py`，逐字貼 spec §3.2 完整檔（module docstring＋`RISK_FLAG_VOCABULARY`＋`_GLOSS`＋`risk_flags_element`）。

> **守界檢查**：`_GLOSS` 三條的文字＝對旗標「意義」的極短指稱（如 spec §3.2 的「變更落在宣告 scope 之外」），**不得**寫成「已檢查未觸發／verified clear」。docstring 已含「未舉之旗標＝『未帶此旗標』、不斷言已驗證 clear」——保留。

- [ ] **Step 4: 跑測試確認通過**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/pipeline/test_risk_flag_membrane.py -q`
Expected: PASS（6 測全綠，含 schema 對齊）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/pipeline/risk_flag_membrane.py the_door/tests/unit/core/pipeline/test_risk_flag_membrane.py
git commit -m "feat(pipeline): risk_flag_membrane 詞彙＋工廠 — risk_flags→PresenceFlag (P3)"
```

---

## Task 3: report_membrane applier 投影 risk_flags（P4）

**Files:**
- Modify: `the_door/src/the_door/core/pipeline/report_membrane.py`（import＋`:24` l1_changes 迴圈內）
- Test: `the_door/tests/unit/core/pipeline/test_report_membrane.py`（擴充）

- [ ] **Step 1: 擴充 characterization 測試（`test_report_membrane.py`）**

把 `_sample_report` 的 l1_changes 改成兩筆——一筆含 present 旗標、一筆維持空 list（既有那筆）：

```python
        "l1_changes": [
            {"feature_id": "f1", "change_type": "added", "risk_flags": [], "current_label": "F1", "baseline_label": None},
            {"feature_id": "f2", "change_type": "attribute_changed", "risk_flags": ["out_of_scope", "vulnerability"], "current_label": "F2", "baseline_label": "F2"},
        ],
```

在檔末新增三個測試（沿用既有 `_is_membrane` helper）：

```python
def test_risk_flags_projected_present_subset():
    """P4：present 旗標升膜＝presence_flag、value＝present 子集、vocabulary 全曝。"""
    r = project_report_for_agent(_sample_report())
    rf = r["l1_changes"][1]["risk_flags"]
    assert _is_membrane(rf)
    assert rf["position"]["kind"] == "presence_flag"
    assert rf["value"] == ["out_of_scope", "vulnerability"]
    assert len(rf["position"]["vocabulary"]) == 3  # 封閉 3-詞彙全曝


def test_risk_flags_empty_still_exposes_vocabulary():
    """P4：空 risk_flags → value:[]＋vocabulary 全曝（agent 知封閉旗標全集；未舉旗 ≠ 已驗證 clear）。"""
    r = project_report_for_agent(_sample_report())
    rf = r["l1_changes"][0]["risk_flags"]
    assert _is_membrane(rf)
    assert rf["value"] == []
    assert len(rf["position"]["vocabulary"]) == 3


def test_risk_flags_input_not_mutated():
    """R5：入參 l1_changes[].risk_flags 仍裸 list（純函式）。"""
    original = _sample_report()
    project_report_for_agent(original)
    assert original["l1_changes"][1]["risk_flags"] == ["out_of_scope", "vulnerability"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/pipeline/test_report_membrane.py -q`
Expected: FAIL — `test_risk_flags_projected_present_subset` 與 `test_risk_flags_empty_still_exposes_vocabulary` 斷言失敗（`risk_flags` 仍裸 list、`_is_membrane` 為 False）。（`test_risk_flags_input_not_mutated` 此時即 PASS——投影未加、入參本就不變；它是 impl 後的非破壞哨兵，非 red 標的。）既有 6 測仍綠。

- [ ] **Step 3: 實作 — 貼 spec §3.3 exact code**

依 spec §3.3：
1. 檔頭 import 區（現有 `from the_door.core.scope.scope_membrane import ...` 之後）加：
   ```python
   from the_door.core.pipeline.risk_flag_membrane import risk_flags_element
   ```
2. `project_report_for_agent` 的 `for e in r.get("l1_changes", []):` 迴圈（`:24`）內，現有 `if "change_type" in e:` 區塊之後加：
   ```python
        if "risk_flags" in e:
            e["risk_flags"] = risk_flags_element(e["risk_flags"]).to_json()
   ```

> import 方向單向（report_membrane→risk_flag_membrane→membrane），無循環（spec §6 第 4 點已驗）。

- [ ] **Step 4: 跑測試確認通過**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/pipeline/test_report_membrane.py -q`
Expected: PASS（既有 6 測＋新 3 測全綠）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/pipeline/report_membrane.py the_door/tests/unit/core/pipeline/test_report_membrane.py
git commit -m "feat(pipeline): report applier 投影 risk_flags 升膜 (P4)"
```

---

## Task 4: Gate — 全測零回歸＋grep 確認人類面未動（P5/P6）

**Files:** 無新改（純驗證關卡）

- [ ] **Step 1: 全測零回歸**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest -q`
Expected: PASS，total＝**1593 + 新測筆數**（Task 1 新 9 ＋ Task 2 新 6 ＋ Task 3 新 3 ＝ 18 ⟹ **1611**），46 skipped、1 xfailed。**0 failed**。（`test_facade_exports` 為改既有、不計入新增。）

- [ ] **Step 2: grep gate — render_json 仍 emit 裸 risk_flags（P5）**

Run（從 git 根）：`git -C C:/Users/Ric/Desktop/the_door grep -n "risk_flags" -- the_door/src/the_door/core/pipeline/report_renderer.py`
Expected: 仍見 `"risk_flags": list(e.risk_flags)`（`:198` 附近）＝render_json **未改**。生產者邏輯（`:400-418`）未動。

- [ ] **Step 3: grep gate — schema/前端未動（P5）**

Run:
```bash
git -C C:/Users/Ric/Desktop/the_door status -s
git -C C:/Users/Ric/Desktop/the_door diff --name-only d87fa4e -- the_door/schemas/ docs/frontend-local-version-viewer/viewer/
```
Expected: 第二條輸出**為空**＝`update-report.schema.json` 與前端唯一正式版**零改動**。`status -s` 只見本刀 commit 後 clean。

- [ ] **Step 4: 確認觸碰面清單（P5 完整性）**

Run: `git -C C:/Users/Ric/Desktop/the_door diff --name-only d87fa4e`
Expected: 恰為——
```
docs/superpowers/plans/2026-06-06-presence-flag-plan.md
the_door/src/the_door/core/membrane/__init__.py
the_door/src/the_door/core/membrane/primitive.py
the_door/src/the_door/core/pipeline/report_membrane.py
the_door/src/the_door/core/pipeline/risk_flag_membrane.py
the_door/tests/unit/core/membrane/test_presence_flag.py
the_door/tests/unit/core/membrane/test_primitive.py
the_door/tests/unit/core/pipeline/test_report_membrane.py
the_door/tests/unit/core/pipeline/test_risk_flag_membrane.py
```
無 render_json/schema/viewer/persisted 檔。**若清單含其餘檔＝越界，回退檢查。**

- [ ] **Step 5: ff-merge main（不主動 push）**

```bash
git -C C:/Users/Ric/Desktop/the_door merge --ff-only <本刀 branch>
```
（`<本刀 branch>`＝當前 worktree branch；inline 執行時即當前分支，ff-merge 回 main。版本號/出版聽使用者，**不 push**。）

---

## 驗收（對應 spec §4 不變量表）

| # | 驗收 | 由哪測/關卡保證 |
|---|---|---|
| P1 | vocabulary 非空、glosses⊆vocabulary | Task 1 `test_presence_flag_empty_vocabulary_raises`／`test_presence_flag_gloss_outside_vocabulary_raises` |
| P2 | element payload（present 子集）⊆vocabulary | Task 1 `test_element_present_outside_vocabulary_raises`／`test_element_present_subset_ok` |
| P3 | `risk_flags_element` to_json 形狀＋詞彙對齊 schema | Task 2 全 6 測 |
| P4 | applier 升膜（空與非空皆全曝 vocabulary、未舉旗 ≠ 已驗證 clear） | Task 3 三測 |
| P5 | render_json/schema/viewer/前端未動 | Task 4 Step 2-4 grep gate |
| P6 | 既有 4 變體投影逐字不變 | Task 1 `test_p6_signal_variant_unchanged`＋membrane 既有測全綠 |
| — | 全測零回歸 | Task 4 Step 1 |

---

## Self-Review（寫畢回驗 spec）

- **spec §3.1/3.2/3.3 全覆蓋**：Task 1（§3.1）／Task 2（§3.2）／Task 3（§3.3）一一對應。✓
- **spec §0 fact-finder 守界**：Task 2 Step 3＋Task 3 新測的 docstring/斷言全寫「未舉旗 ≠ 已驗證 clear」、無「checked/verified clear」字樣。plan 頂部「跨刀守界」已釘。✓
- **spec §5 測試策略全覆蓋**：primitive unit（Task 1）／risk_flag_membrane unit（Task 2，含 schema 對齊）／report characterization（Task 3）／全測零回歸（Task 4）。✓
- **spec §6 第 5 點 hashability 備忘**：plan 頂部「跨刀守界」已釘「勿對 MembraneElement 做 set/dict-key」。✓
- **type 一致**：`PresenceFlagPosition(vocabulary, glosses)`／`RISK_FLAG_VOCABULARY`／`risk_flags_element`／`project_report_for_agent` 跨 task 命名一致。`kind=="presence_flag"`、`glosses` to_json 為 dict、`vocabulary` 為 list——Task 1 定義、Task 2/3 沿用，無漂移。✓
- **placeholder 掃描**：生產碼引 spec §3.x exact code（防雙源漂移、user 偏好覆寫 skill 預設）；測試碼全展開、無 TBD/TODO。✓
- **`test_facade_exports` 連動**：Task 1 Step 5 已處理既有 exact `__all__` set 斷言會破的問題。✓
