# S0 膜 primitive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立膜 primitive 地基型別（`MembraneElement` ＋ `SignalPosition` ＋ `ReservedPassthrough`），讓輸出值攜帶其結構位置、意義不靠 prompt——乙案重塑 campaign 的 S0 地基刀。

**Architecture:** 純加法 peer 子套件 `core/membrane/`（旁路風格，比照 `core/datamodel`）。全 `frozen=True` 值物件、無 I/O、住 emission 邊界非持久化層。S0 只建 base＋2 變體；`NoisePosition`(S2)／`RelayedVerdict`(S3) 延後。零既有碼改動、零輸出契約改動 → 零回歸。

**Tech Stack:** Python `@dataclass(frozen=True)`、discriminated union（`Position = SignalPosition | ReservedPassthrough`）、pytest。

**理論錨（種子檔 `docs/superpowers/specs/2026-06-04-yi-an-output-direction-seed.md`；spec `docs/superpowers/specs/2026-06-05-S0-membrane-primitive-spec.md`）：**
- 膜不變量（§8.10）：意義靠結構位置。→ 每值帶 `position`。
- per-value 切法（§8.13 勘誤）：閉集值＝Signal；S0 只做格內 Signal＋reserved 窗。
- 寫嚴讀寬分側（§8.12 修正②）：B 側 CWA 封閉 enum。→ `contrasts` 封閉集（I1）。
- fact-finder（§8.2 A、§8.13-O1）：禁自鑄裁決。→ base 無 score 欄（I2）。
- 膜脊椎「意義靠關係定位」。→ `payload ∈ contrasts`（I4）。

**Preconditions（執行前確認，非 task）：**
- 換 worktree 後先 `pip install -e ./the_door`。
- pytest cwd＝內層 `the_door/`；Windows cp950 前置 `PYTHONUTF8=1`。
- 既有測試基線 1447 passed；本 plan 純加法，驗收須維持零回歸。

---

## File Structure

| 檔案 | 職責 | S0 行數估 |
|---|---|---|
| `the_door/src/the_door/core/membrane/primitive.py` | base＋2 變體＋`to_json`＋I1/I3/I4 守衛 | ~90（單檔即焦點，無需拆；拆點在 S2/S3） |
| `the_door/src/the_door/core/membrane/__init__.py` | 公開門面（4 符號） | ~12 |
| `the_door/tests/unit/core/membrane/test_primitive.py` | I1/I2/I3/I4＋變體 happy-path＋`to_json` | ~70 |
| `the_door/tests/unit/core/membrane/test_s1_coherence.py` | §5 對 S1 doubt 三欄連貫性回驗 | ~40 |

＋兩個空 `__init__.py` 套件標記（`src/the_door/core/membrane/`＝Task 1 空殼→Task 4 填門面；`tests/unit/core/membrane/`＝空）。理由＝對齊既有套件式測試目錄慣例。

---

### Task 1: `SignalPosition`（B 側閉集訊號＋I1 非空 contrasts）

**理論錨：** B 側 CWA 封閉集（§8.12 修正②）；操作位置欄位 optional（純 enum 只填 contrasts+gloss，doubt state 才填滿）。

**Files:**
- Create: `the_door/src/the_door/core/membrane/__init__.py`（本 task 建**空殼**；Task 4 填門面）
- Create: `the_door/src/the_door/core/membrane/primitive.py`
- Create: `the_door/tests/unit/core/membrane/__init__.py`（空套件標記，比照 `tests/unit/core/scope/__init__.py` 慣例）
- Test: `the_door/tests/unit/core/membrane/test_primitive.py`

> ⚠️ **套件骨架先行**：本 repo 測試目錄為**套件式**（既有 `tests/unit/core/*/` 皆含 `__init__.py`）。`core/membrane/` 亦須 `__init__.py` 才是 regular package，否則 Task 1-3 的 `from the_door.core.membrane.primitive import …` 在 import 時不穩。故本 task 先建兩個 `__init__.py`（src 端空殼，避免 import 尚未存在的符號）。

- [ ] **Step 1: Write the failing test**

先建空套件骨架（兩個 `__init__.py`）：

```bash
# src 端：空殼，Task 4 才填門面（此時 primitive.py 尚未建，不可在此 import）
# the_door/src/the_door/core/membrane/__init__.py  → 空檔
# 測試端：空套件標記
# the_door/tests/unit/core/membrane/__init__.py     → 空檔
```

兩個 `__init__.py` 內容皆為空（0 bytes）。

再建立 `the_door/tests/unit/core/membrane/test_primitive.py`：

```python
"""S0 膜 primitive 不變量與投影測試。"""
import pytest

from the_door.core.membrane.primitive import SignalPosition


def test_signal_position_minimal_enum():
    """純 enum 只需 contrasts + gloss，操作位置欄位預設空 tuple。"""
    sp = SignalPosition(contrasts=("high", "medium", "low"), gloss="信心三級")
    assert sp.contrasts == ("high", "medium", "low")
    assert sp.preconditions == ()
    assert sp.consequences == ()
    assert sp.co_requires == ()


def test_signal_position_full_grammar():
    """帶轉換文法的 enum 填滿四欄。"""
    sp = SignalPosition(
        contrasts=("discovered", "investigating", "explained"),
        gloss="已查證為預期行為",
        preconditions=("investigating",),
        consequences=("terminal",),
        co_requires=("reason",),
    )
    assert sp.preconditions == ("investigating",)


def test_signal_position_empty_contrasts_raises():
    """I1：contrasts 非空（B 側 CWA 封閉集）。"""
    with pytest.raises(ValueError, match="非空"):
        SignalPosition(contrasts=(), gloss="x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_primitive.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'the_door.core.membrane.primitive'`（空 `__init__` 已使 `membrane` 套件存在，但 `primitive.py` 尚未建）

- [ ] **Step 3: Write minimal implementation**

建立 `the_door/src/the_door/core/membrane/primitive.py`：

```python
"""膜 primitive：意義經結構位置送達消費端 LLM 的單一 emit 原語。

非持久化層——住 emission/呈現邊界（種子檔 §8.12）。snapshot 等照舊存 bare 值，
本原語在 emit 時把「值 + 它在結構空間的位置」一起投影出去。

per-value 切法（種子檔 §8.13 勘誤）：膜的格內/格外界線切在「值」、非「欄位」。
落在閉集的值 → 格內 Signal（本檔建）；格外殘餘 → 格外 Noise（S2 建）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalPosition:
    """B 側（CWA／格內／封閉訊號）：值的意義＝它在封閉兄弟集中的對比位置。

    四個操作位置欄位皆 optional：純 enum 只填 contrasts + gloss；帶轉換文法的
    enum（如 doubt current_state）填滿，源自內部單一來源（DoubtLifecycle）。
    contrasts 是 tuple（有序）：doubt states＝圖；severity＝全序——同型別容兩者。
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_primitive.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/membrane/__init__.py the_door/src/the_door/core/membrane/primitive.py the_door/tests/unit/core/membrane/__init__.py the_door/tests/unit/core/membrane/test_primitive.py
git commit -m "feat(membrane): package skeleton + SignalPosition with non-empty contrasts (I1)

S0 地基刀第一塊：套件骨架（空 __init__）＋ B 側閉集訊號變體。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `ReservedPassthrough` ＋ `Position` ＋ `MembraneElement`（含 I4 跨欄不變量）

**理論錨：** reserved 窗（§8.10 接點②）；膜脊椎「意義靠關係定位」→ I4 `payload ∈ contrasts`；fact-finder → base 無 score 欄（I2，由型別缺欄保證）。

**Files:**
- Modify: `the_door/src/the_door/core/membrane/primitive.py`（append）
- Test: `the_door/tests/unit/core/membrane/test_primitive.py`（append）

- [ ] **Step 1: Write the failing test**

在 `test_primitive.py` 末尾 append（先補 import：把頂部 import 改為下行）：

```python
from the_door.core.membrane.primitive import (
    MembraneElement,
    ReservedPassthrough,
    SignalPosition,
)
```

append 測試：

```python
def test_reserved_passthrough_is_marker():
    rp = ReservedPassthrough()
    assert isinstance(rp, ReservedPassthrough)


def test_membrane_element_signal_payload_in_contrasts():
    """happy-path：Signal 值在自己的兄弟集裡。"""
    el = MembraneElement(
        payload="high",
        position=SignalPosition(contrasts=("high", "medium", "low"), gloss="信心三級"),
    )
    assert el.payload == "high"


def test_membrane_element_reserved_free_text():
    """reserved 窗：free-text payload 無約束。"""
    el = MembraneElement(payload="任意自由文字", position=ReservedPassthrough())
    assert el.payload == "任意自由文字"


def test_i4_payload_not_in_contrasts_raises():
    """I4：Signal 值必須定位於自己的封閉兄弟集。"""
    with pytest.raises(ValueError, match="不在"):
        MembraneElement(
            payload="banana",
            position=SignalPosition(contrasts=("high", "low"), gloss="x"),
        )


def test_i2_membrane_element_has_no_score_field():
    """I2：base 型無 score 欄位（禁自鑄裁決的結構性保證）。"""
    el = MembraneElement(payload="high",
                         position=SignalPosition(contrasts=("high",), gloss="x"))
    assert not hasattr(el, "score")
    assert not hasattr(el, "risk")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_primitive.py -v`
Expected: FAIL — `ImportError: cannot import name 'MembraneElement'`

- [ ] **Step 3: Write minimal implementation**

在 `primitive.py` 末尾 append：

```python
@dataclass(frozen=True)
class ReservedPassthrough:
    """reserved 窗：CWA 世界裡明文宣告的 OWA 窗。free-text，不要求結構。

    標記型別——free-text 內容住 MembraneElement.payload，本變體只宣告
    「此處刻意永久開放」。
    """
    pass


# Position union——S0 階段 2 變體；S2 加 NoisePosition、S3 加 RelayedVerdict。
Position = SignalPosition | ReservedPassthrough


@dataclass(frozen=True)
class MembraneElement:
    """一個輸出元素＝它的值（payload）＋它在結構空間的位置（position）。

    base 型刻意無 score/risk/severity 欄位：裁決只能經（未來的）RelayedVerdict
    position，且該變體強制外部證據——自鑄裁決在型別上無處可放（I2）。

    payload 語意 per-variant：
      - SignalPosition → payload＝該閉集的某個值（str），型別強制 payload ∈ contrasts（I4）。
      - ReservedPassthrough → payload＝free-text 字串（無約束）。
    payload 寬型 object 是為未來 RelayedVerdict（S3）預留。
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_primitive.py -v`
Expected: PASS（8 passed）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/membrane/primitive.py the_door/tests/unit/core/membrane/test_primitive.py
git commit -m "feat(membrane): ReservedPassthrough + MembraneElement with payload-in-contrasts (I2/I4)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `to_json` 投影 ＋ `_position_to_json`（含 I3 未知變體拋錯）

**理論錨：** 唯一受祝福的投影路徑（§8.11 affordance）；顯式失敗、不靜默（未知變體拋 `TypeError`，I3）。

**Files:**
- Modify: `the_door/src/the_door/core/membrane/primitive.py`（加 `to_json` 方法＋module helper）
- Test: `the_door/tests/unit/core/membrane/test_primitive.py`（append）

- [ ] **Step 1: Write the failing test**

append 測試：

```python
def test_to_json_signal_full_shape():
    el = MembraneElement(
        payload="explained",
        position=SignalPosition(
            contrasts=("discovered", "investigating", "explained"),
            gloss="已查證為預期行為",
            preconditions=("investigating",),
            consequences=("terminal",),
            co_requires=("reason",),
        ),
    )
    assert el.to_json() == {
        "value": "explained",
        "position": {
            "kind": "signal",
            "contrasts": ["discovered", "investigating", "explained"],
            "gloss": "已查證為預期行為",
            "preconditions": ["investigating"],
            "consequences": ["terminal"],
            "co_requires": ["reason"],
        },
    }


def test_to_json_reserved_shape():
    el = MembraneElement(payload="自由文字", position=ReservedPassthrough())
    assert el.to_json() == {"value": "自由文字", "position": {"kind": "reserved"}}


def test_i3_unknown_position_variant_raises():
    """I3：未知 position 變體顯式拋 TypeError（防 S2/S3 擴 union 漏更新投影）。"""
    from the_door.core.membrane.primitive import _position_to_json

    class _Fake:
        pass

    with pytest.raises(TypeError, match="未知 position"):
        _position_to_json(_Fake())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_primitive.py -v`
Expected: FAIL — `AttributeError: 'MembraneElement' object has no attribute 'to_json'`

- [ ] **Step 3: Write minimal implementation**

在 `MembraneElement` 類別內（`__post_init__` 之後）加方法：

```python
    def to_json(self) -> dict:
        """唯一受祝福的投影路徑（§8.11 affordance）。意義不靠 prompt。"""
        return {"value": self.payload, "position": _position_to_json(self.position)}
```

在 `primitive.py` module 末尾 append helper：

```python
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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_primitive.py -v`
Expected: PASS（11 passed）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/membrane/primitive.py the_door/tests/unit/core/membrane/test_primitive.py
git commit -m "feat(membrane): to_json projection with explicit unknown-variant guard (I3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `__init__.py` 公開門面

**理論錨：** 介面最小（7 點審查第 2 點）；peer 子套件旁路風格比照 `core/datamodel`。

**Files:**
- Modify: `the_door/src/the_door/core/membrane/__init__.py`（Task 1 建的空殼 → 填入門面）
- Test: `the_door/tests/unit/core/membrane/test_primitive.py`（append）

- [ ] **Step 1: Write the failing test**

append 測試：

```python
def test_facade_exports():
    """門面匯出 4 符號，從套件根可直接 import。"""
    from the_door.core import membrane

    assert set(membrane.__all__) == {
        "MembraneElement",
        "Position",
        "ReservedPassthrough",
        "SignalPosition",
    }
    # 確認可從門面取用（非僅 primitive 模組）
    el = membrane.MembraneElement(
        payload="high",
        position=membrane.SignalPosition(contrasts=("high", "low"), gloss="x"),
    )
    assert el.to_json()["value"] == "high"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_primitive.py::test_facade_exports -v`
Expected: FAIL — `AttributeError: module 'the_door.core.membrane' has no attribute 'MembraneElement'`（`__init__.py` 尚空/不存在）

- [ ] **Step 3: Write minimal implementation**

把 Task 1 建的空殼 `the_door/src/the_door/core/membrane/__init__.py` 填入門面：

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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_primitive.py -v`
Expected: PASS（12 passed）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/membrane/__init__.py the_door/tests/unit/core/membrane/test_primitive.py
git commit -m "feat(membrane): public facade (__init__) exporting 4 symbols

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 對 S1（doubt）連貫性回驗測試（§5）

**理論錨：** 連貫律——證 S0 兩變體覆蓋 S1 doubt 全部膜詞彙、零未驗變體；資料源＝真實 `DoubtLifecycle`（spec §5）。**此 task 純測試、不改生產碼。**

**Files:**
- Create: `the_door/tests/unit/core/membrane/test_s1_coherence.py`

- [ ] **Step 1: Write the failing test**

建立 `the_door/tests/unit/core/membrane/test_s1_coherence.py`：

```python
"""S0→S1 連貫性回驗：膜 primitive 接得住 doubt 三欄（current_state / resolution.type / reason）。

用真實 DoubtLifecycle 資料當輸入，證 S0 的 base+Signal+Reserved 對 S1 充分且無剩。
不改任何生產碼。
"""
from the_door.core.membrane import MembraneElement, ReservedPassthrough, SignalPosition
from the_door.core.scope.doubt_lifecycle import DoubtLifecycle


def test_coherence_current_state_signal():
    """current_state（6 值閉集）→ SignalPosition；前件/後件源自 DoubtLifecycle。"""
    lc = DoubtLifecycle()
    states = tuple(lc.VALID_TRANSITIONS.keys())          # 封閉兄弟集
    value = "explained"
    preconds = tuple(s for s, tos in lc.VALID_TRANSITIONS.items() if value in tos)
    el = MembraneElement(
        payload=value,
        position=SignalPosition(
            contrasts=states,
            gloss="已查證為預期行為，非缺陷",
            preconditions=preconds,                       # 反查 VALID_TRANSITIONS
            consequences=("terminal",) if lc.is_terminal(value) else (),  # 從 is_terminal 導出
            co_requires=("reason",),
        ),
    )
    j = el.to_json()
    assert j["value"] == "explained"
    assert set(j["position"]["contrasts"]) == set(states)
    assert "investigating" in j["position"]["preconditions"]
    assert "escalated" in j["position"]["preconditions"]
    assert j["position"]["consequences"] == ["terminal"]


def test_coherence_resolution_type_signal():
    """resolution.type（3 值閉集）→ SignalPosition；contrasts＝_RESOLVING_STATES。"""
    lc = DoubtLifecycle()
    contrasts = tuple(sorted(lc._RESOLVING_STATES))       # {explained, fixed, accepted_risk}
    el = MembraneElement(
        payload="fixed",
        position=SignalPosition(contrasts=contrasts, gloss="已修復"),
    )
    assert el.to_json()["value"] == "fixed"
    assert "fixed" in el.to_json()["position"]["contrasts"]


def test_coherence_reason_reserved():
    """reason（free-text）→ ReservedPassthrough。"""
    el = MembraneElement(payload="使用者確認為框架慣例", position=ReservedPassthrough())
    assert el.to_json() == {"value": "使用者確認為框架慣例", "position": {"kind": "reserved"}}
```

- [ ] **Step 2: Run test to verify it fails (then passes)**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_s1_coherence.py -v`
Expected: 因 S0 已實作，預期直接 PASS（3 passed）。**此 task 是回驗、非 red-green**——若任一斷言失敗，代表 S0 型別對 S1 不充分 → 停下回 spec §5 修地基（連貫律回驗點），不可硬改測試繞過。

> 註：`DoubtLifecycle._RESOLVING_STATES` 為現有屬性（`core/scope/doubt_lifecycle.py:41`，本輪 grep 已驗）。測試讀它取 resolution 閉集＝單一來源，不另寫死 3 值。

- [ ] **Step 3: Commit**

```bash
git add the_door/tests/unit/core/membrane/test_s1_coherence.py
git commit -m "test(membrane): S0->S1 coherence — primitive holds doubt's 3 fields

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 全套件回歸驗收

**Files:** （無；驗收 gate）

- [ ] **Step 1: 跑 membrane 子套件全測**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/ -v`
Expected: PASS（15 passed：test_primitive 12＋test_s1_coherence 3）

- [ ] **Step 2: 跑全測確認零回歸**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest -q`
Expected: 既有 1447 passed ＋ 新增 15 ＝ 1462 passed，零 fail（純加法、零既有碼改動）。

- [ ] **Step 3:（無新 commit；驗收通過即 S0 完成）**

S0 完成 → 進 S1（doubt through-line）spec。起 S1 前重跑種子檔 §9.2 理論重錨、讀 spec §5＋§3a。

---

## Self-Review

**1. Spec coverage：**
- spec §3 型別（SignalPosition/ReservedPassthrough/Position/MembraneElement/to_json/_position_to_json）→ Task 1-4 ✓
- spec §4 不變量 I1（Task 1）/I2（Task 2）/I3（Task 3）/I4（Task 2）✓
- spec §5 連貫性回驗 → Task 5 ✓
- spec §6 測試策略（各變體 happy-path＋I1-I4＋to_json＋coherence）→ Task 1-5 ✓
- spec §8 交付物 4 檔 → Task 1-5 全覆蓋 ✓
- 延後變體（§3a NoisePosition/RelayedVerdict）→ 正確**不**在本 plan（S2/S3）✓

**2. Placeholder scan：** 無 TBD/TODO；每 step 含完整 code＋exact 指令＋預期輸出 ✓

**3. Type consistency：** `SignalPosition(contrasts,gloss,preconditions,consequences,co_requires)`／`MembraneElement(payload,position)`／`to_json()→{"value","position":{"kind",...}}`／`_position_to_json`／門面 4 符號——跨 Task 1-5 一致 ✓。`DoubtLifecycle.VALID_TRANSITIONS`/`is_terminal`/`_RESOLVING_STATES` 對齊 `core/scope/doubt_lifecycle.py:32/43/41` ✓
