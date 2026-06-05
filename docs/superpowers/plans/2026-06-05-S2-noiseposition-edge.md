# S2 NoisePosition / edge F5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** NoisePosition（A 側殘餘描述子）首落地——把 edge_projection F5 的兩處偷渡減法（`set` 去重丟基數、兩 gap-kind 併桶丟座標）修正為「skipped_dynamic→NoisePosition(indeterminate,基數,比例)、name_match_ambiguous 座標分流且基數保留」，並同步重塑 L1 prompt 對該殘餘的教學。乙案膜 campaign 的 NoisePosition 首實例（S2）。

**Architecture:** 純加法擴 `core/membrane/primitive.py`（加 `NoisePosition`＋`GAP_KIND_PRIORITY`、擴 union 與 `_position_to_json`）＋ 新 `core/llm/edge_membrane.py`（resolution→gap_kind 單一來源＋殘餘工廠）＋ `edge_projection.py` F5 retrofit ＋ `batch_reader.py` payload 鍵 ＋ `prompts.py` 教學同步。**LLM-facing 兩面**：結構 payload ＋ prompt 教學。

**Tech Stack:** Python、S0 `core/membrane`、`collections.Counter`、pytest、hypothesis（property）。

**理論錨（spec `docs/superpowers/specs/2026-06-05-S2-noiseposition-edge-spec.md`；種子檔 §8.3/§8.8/§8.13/§8.14）：**
- 殘餘格恆帶三件（§8.3）：gap_kind＋cardinality＋proportion → `NoisePosition` 型強制（N1）。
- gap-kind 單值優先序（§8.8 F1）：`GAP_KIND_PRIORITY` 膜核心單一來源（N2）。
- 加法不減法（§8.12/§8.14）：修 F5 去重（N3）＋併桶（N4）兩偷渡減法。
- per-value 切法（§8.13）：skipped_dynamic＝格外殘餘（Noise）；name_match_ambiguous＝格內低信心（confidence 軸＝S4，本刀只保基數、不建 Signal）。
- fact-finder（§8.2）：NoisePosition 無裁決欄（N5，承 S0 I2）。

**檔案數量判斷（使用者問）：**
- **plan＝單檔**：6 task 線性相依（NoisePosition→edge_membrane→edge_projection→prompt），拆檔斷敘事/增幻覺（S1 審查已立此則）。
- **NoisePosition 留 `primitive.py`**：與 S0 的 `SignalPosition`/`ReservedPassthrough`/`MembraneElement` 同屬 `Position` union 一族，`_position_to_json` 集中分派；拆出會割裂同一概念族。4 dataclass + 函式仍是聚焦單檔。
- **`edge_membrane.py` 獨立檔**：照 S1 `{domain}_membrane.py` 慣例（域詞彙單一來源）。

**Preconditions（執行前確認，非 task）：**
- 換 worktree 後先 `pip install -e ./the_door`（本 worktree s2-noise-edge 已裝）。
- pytest cwd＝內層 `the_door/`；Windows cp950 前置 `PYTHONUTF8=1`。
- 基線＝S1 merged 後 **1477 passed**。本 plan：primitive＋edge_membrane 純加法；edge_projection/batch_reader/prompt 形狀變更由 characterization＋既有測試有意更新見證。

**已驗事實（寫 plan 前 spike，2026-06-05）：**
- resolution 閉集 5 值（`edge_builder.py:46-49,401,411,427`）：scope_rule/import_alias/name_match（kept）＋name_match_ambiguous＋skipped_dynamic（aggregated）。
- F5 病灶在既有測試直接見證：`test_edge_projection.py:50-58`（去重）、`:61-71`（併桶）；property `test_edge_projection_properties.py:49-55`（斷言去重＝編碼病灶①）。
- 消費者：`batch_reader.py:301,307`（payload `aggregate_call_hints`）→`:312 json.dumps`→`provider.complete`；prompt 教學 `prompts.py:45-65`。
- `audit_conformance`（`snapshot_store.py:260`）零消費者＝OUT。
- 無循環 import：`edge_membrane`→`core.membrane`；`edge_projection`→`edge_membrane`；`batch_reader`→`edge_projection`；`core.membrane` 不反向依賴。

---

## File Structure

| 檔案 | 職責 | 動作 |
|---|---|---|
| `src/the_door/core/membrane/primitive.py` | 加 `GAP_KIND_PRIORITY`＋`NoisePosition`＋union＋`_position_to_json` noise 分支 | Modify |
| `src/the_door/core/membrane/__init__.py` | 門面加 `NoisePosition`、`GAP_KIND_PRIORITY` | Modify |
| `tests/unit/core/membrane/test_noise_position.py` | N1/N2＋基數比例邊界＋to_json | Create |
| `src/the_door/core/llm/edge_membrane.py` | resolution→gap_kind 單一來源＋`is_residue`＋`indeterminate_residue_element` | Create |
| `tests/unit/core/llm/test_edge_membrane.py` | 工廠計數/proportion/排序決定性/to_json | Create |
| `tests/unit/core/llm/test_edge_projection_membrane.py` | characterization：先釘併桶+去重現狀 → Task 4 改新 residue | Create |
| `src/the_door/core/llm/edge_projection.py` | F5 retrofit（座標分流＋基數保留＋NoisePosition） | Modify |
| `src/the_door/core/reading/batch_reader.py` | `:301,307` 解包/payload 鍵改名 | Modify |
| `tests/unit/core/llm/test_edge_projection.py` | 既有 9 測改新 residue 形狀 | Modify |
| `tests/property/test_edge_projection_properties.py` | 移除去重 property、idempotent 改空殘餘、加基數反向 property | Modify |
| `tests/integration/test_batch_reader_projection.py` | payload 鍵改名＋形狀 | Modify |
| `src/the_door/core/llm/prompts.py` | `L1_SYSTEM_PROMPT` aggregate 段重塑（§3.4） | Modify |
| `tests/unit/core/llm/test_prompt_resolution_section.py`、`test_prompts_resolution.py` | 2 處 `aggregate_call_hints`→`aggregate_call_residue` | Modify |

---

### Task 1: 膜 primitive 擴 `NoisePosition`（＋`GAP_KIND_PRIORITY`）

**理論錨：** 殘餘三件（§8.3）＋gap-kind 優先序單一來源（§8.8 F1）＋型驅動「不帶基數不能 emit 聚合殘餘」（N1/N2）。**純加法、零既有碼改動（S0 2 變體與 I1-I4 不動）。**

**Files:**
- Modify: `src/the_door/core/membrane/primitive.py`、`src/the_door/core/membrane/__init__.py`
- Test: `tests/unit/core/membrane/test_noise_position.py`

- [ ] **Step 1: Write the failing test**

建立 `tests/unit/core/membrane/test_noise_position.py`：

```python
"""S2 NoisePosition：A 側殘餘描述子 + N1/N2 型驅動守衛。"""
import pytest

from the_door.core.membrane import GAP_KIND_PRIORITY, MembraneElement, NoisePosition


def test_priority_order_is_canonical():
    assert GAP_KIND_PRIORITY == ("corrupt", "indeterminate", "evolutionary", "reserved")


def test_aggregated_requires_cardinality_and_proportion():
    with pytest.raises(ValueError, match="必帶"):
        NoisePosition(gap_kind="indeterminate", aggregated=True)            # 兩者皆缺
    with pytest.raises(ValueError, match="必帶"):
        NoisePosition(gap_kind="indeterminate", cardinality=3, aggregated=True)  # 缺 proportion


def test_aggregated_happy_path():
    np = NoisePosition(gap_kind="indeterminate", cardinality=3, proportion=0.5, aggregated=True)
    assert np.cardinality == 3 and np.proportion == 0.5


def test_gap_kind_must_be_in_priority():
    with pytest.raises(ValueError, match="GAP_KIND_PRIORITY"):
        NoisePosition(gap_kind="banana")
    for k in GAP_KIND_PRIORITY:
        NoisePosition(gap_kind=k)                # 4 合法值皆可構造


def test_cardinality_nonnegative():
    with pytest.raises(ValueError, match="不可為負"):
        NoisePosition(gap_kind="indeterminate", cardinality=-1)


def test_proportion_in_range():
    with pytest.raises(ValueError, match="必須在"):
        NoisePosition(gap_kind="indeterminate", proportion=1.5)


def test_non_aggregated_single_residue_ok():
    """單筆殘餘＝aggregated=False、不要求基數（presence 情境，取代舊 is_flag）。"""
    np = NoisePosition(gap_kind="indeterminate")
    assert np.aggregated is False and np.cardinality is None


def test_to_json_noise_shape():
    el = MembraneElement(
        payload={"caller": "c", "methods": {"send": 2}},
        position=NoisePosition(gap_kind="indeterminate", cardinality=2, proportion=0.4, aggregated=True),
    )
    j = el.to_json()
    assert j["position"] == {
        "kind": "noise", "gap_kind": "indeterminate",
        "cardinality": 2, "proportion": 0.4, "aggregated": True,
    }
    assert j["value"] == {"caller": "c", "methods": {"send": 2}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_noise_position.py -q`
Expected: FAIL — `ImportError: cannot import name 'NoisePosition'`（或 `GAP_KIND_PRIORITY`）。

- [ ] **Step 3: Write minimal implementation**

`src/the_door/core/membrane/primitive.py`：在 `ReservedPassthrough` 之後、`Position = ...` 之前，貼入 **spec §3.1 的 exact code**（`GAP_KIND_PRIORITY` 常數 ＋ `NoisePosition` dataclass 含 `__post_init__` 四守衛）。然後：
- 改 `Position` union 為 `SignalPosition | ReservedPassthrough | NoisePosition`。
- 在 `_position_to_json` 的 `ReservedPassthrough` 分支後、`raise TypeError` 前，加 spec §3.1 的 `NoisePosition` 分支（回 `{"kind":"noise", gap_kind, cardinality, proportion, aggregated}`）。

`src/the_door/core/membrane/__init__.py`：`from ...primitive import (... NoisePosition, GAP_KIND_PRIORITY ...)` 並加入 `__all__`。

> 不在此重貼（避免雙源漂移）；spec §3.1 是唯一 code 來源。關鍵不變式：`aggregated and (cardinality is None or proportion is None)` → ValueError「必帶」；`gap_kind not in GAP_KIND_PRIORITY` → ValueError；cardinality<0 / proportion∉[0,1] → ValueError。**不動 I1-I4 與既有 2 變體。**

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/test_noise_position.py tests/unit/core/membrane/ -q`
Expected: PASS（8 passed）＋既有 `test_primitive.py`/`test_s1_coherence.py` 仍綠（純加法）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/core/membrane/primitive.py src/the_door/core/membrane/__init__.py tests/unit/core/membrane/test_noise_position.py
git commit -m "feat(membrane): NoisePosition residue descriptor + GAP_KIND_PRIORITY (N1/N2)

S2 地基：A 側殘餘描述子（性質+基數+比例），聚合必帶基數比例＝型強制；
gap_kind 單一來源 GAP_KIND_PRIORITY。承 S0 §3a 形狀、純加法不動 I1-I4。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: edge 膜詞彙單一來源 `edge_membrane.py`

**理論錨：** `{domain}_membrane.py` 慣例（S1 §5）；resolution→gap_kind 域內單一來源；聚合殘餘帶基數比例＋**決定性排序**。**純加法。**

**Files:**
- Create: `src/the_door/core/llm/edge_membrane.py`
- Test: `tests/unit/core/llm/test_edge_membrane.py`

- [ ] **Step 1: Write the failing test**

建立 `tests/unit/core/llm/test_edge_membrane.py`：

```python
"""S2 edge 膜詞彙：殘餘工廠 + 決定性。"""
from the_door.core.llm import edge_membrane as em


def test_is_residue():
    assert em.is_residue("skipped_dynamic") is True
    assert em.is_residue("name_match_ambiguous") is False     # 格內低信心、非殘餘
    assert em.is_residue("scope_rule") is False


def test_indeterminate_element_counts_and_proportion():
    el = em.indeterminate_residue_element("caller", {"send": 3, "recv": 1}, total_edges=8)
    j = el.to_json()
    assert j["value"]["caller"] == "caller"
    assert j["value"]["methods"] == {"recv": 1, "send": 3}    # 排序（a→z）
    assert j["position"]["kind"] == "noise"
    assert j["position"]["gap_kind"] == "indeterminate"
    assert j["position"]["cardinality"] == 4
    assert j["position"]["proportion"] == 0.5                 # 4/8
    assert j["position"]["aggregated"] is True


def test_methods_sorted_deterministic():
    a = em.indeterminate_residue_element("c", {"z": 1, "a": 1, "m": 1}, total_edges=3)
    b = em.indeterminate_residue_element("c", {"m": 1, "z": 1, "a": 1}, total_edges=3)
    assert a.to_json() == b.to_json()
    assert list(a.to_json()["value"]["methods"].keys()) == ["a", "m", "z"]


def test_zero_total_no_zero_division():
    el = em.indeterminate_residue_element("c", {"x": 1}, total_edges=0)
    assert el.to_json()["position"]["proportion"] == 0.0      # 防呆（實務 total≥1）
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/llm/test_edge_membrane.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'the_door.core.llm.edge_membrane'`。

- [ ] **Step 3: Write minimal implementation**

建立 `src/the_door/core/llm/edge_membrane.py`＝**spec §3.2 的 exact code 全文**（`_RESIDUE_GAP_KIND={"skipped_dynamic":"indeterminate"}`＋`is_residue`＋`indeterminate_residue_element`）。

> 不重貼（spec §3.2 唯一來源）。關鍵：`methods` 經 `dict(sorted(method_counts.items()))`＝決定性；`cardinality=sum(counts.values())`；`proportion=cardinality/total_edges if total_edges else 0.0`；payload **不**含 gloss（意義由 gap_kind＋prompt 承載）。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/llm/test_edge_membrane.py -q`
Expected: PASS（4 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/core/llm/edge_membrane.py tests/unit/core/llm/test_edge_membrane.py
git commit -m "feat(edge-membrane): residue vocabulary — skipped_dynamic -> NoisePosition(indeterminate)

resolution->gap_kind 單一來源；殘餘工廠帶真實基數+比例+決定性排序。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: characterization — 先釘 F5 併桶+去重現狀

**理論錨：** characterization 先行（§9.4）——動契約前釘現狀（含病灶）。**本 task 不改生產碼。**

**Files:**
- Test: `tests/unit/core/llm/test_edge_projection_membrane.py`（Create）

- [ ] **Step 1: Write characterization test pinning CURRENT (buggy) shape**

建立 `tests/unit/core/llm/test_edge_projection_membrane.py`：

```python
"""S2 characterization + 膜投影：先釘 F5 併桶+去重現狀（Task 3），
Task 4 retrofit 後改為座標分流+真實基數的 residue（見證契約變更）。"""
from the_door.core.llm.edge_projection import project_edges_for_prompt


def _edge(from_, to, res):
    return {"from": from_, "to": to, "type": "calls", "resolution": res}


def test_f5_current_conflates_and_dedups():
    """CHARACTERIZATION（Task 3 現狀＝F5 病灶）：兩 gap-kind 併一桶 + 同名去重。"""
    edges = [
        _edge("a", "Bus.send", "skipped_dynamic"),
        _edge("a", "F.write", "name_match_ambiguous"),
        _edge("a", "G.write", "name_match_ambiguous"),     # 同名 write → 去重成 1
    ]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"a": ["send", "write"]}   # send(dynamic)+write(ambiguous) 混桶、write 去重
```

- [ ] **Step 2: Run test to verify it PASSES (pins current behavior)**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/llm/test_edge_projection_membrane.py -q`
Expected: PASS（1 passed）——釘住病灶現狀。Task 4 將此斷言改為新 residue＝見證契約變更。

- [ ] **Step 3: Commit**

```bash
git add tests/unit/core/llm/test_edge_projection_membrane.py
git commit -m "test(edge-projection): characterize F5 conflation+dedup before retrofit

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: F5 retrofit（座標分流＋基數保留＋NoisePosition）＋更新結構側測試

**理論錨：** 加法不減法修兩偷渡減法（N3 基數、N4 座標）；殘餘走 NoisePosition（N1）。

**Files:**
- Modify: `src/the_door/core/llm/edge_projection.py`、`src/the_door/core/reading/batch_reader.py`
- Modify(test): `tests/unit/core/llm/test_edge_projection_membrane.py`（flip）、`tests/unit/core/llm/test_edge_projection.py`、`tests/property/test_edge_projection_properties.py`、`tests/integration/test_batch_reader_projection.py`

- [ ] **Step 1: Flip characterization + update structural tests to NEW shape (now failing)**

把 Task 3 的 `test_f5_current_conflates_and_dedups` 改為（同檔）：

```python
def test_f5_retrofit_splits_and_counts():
    """retrofit 後：座標分流（N4）+ 真實基數（N3）。"""
    edges = [
        _edge("a", "Bus.send", "skipped_dynamic"),
        _edge("a", "Bus.send", "skipped_dynamic"),     # 同名 2 筆 → cardinality=2
        _edge("a", "F.write", "name_match_ambiguous"),
        _edge("a", "G.write", "name_match_ambiguous"),
        _edge("a", "b", "scope_rule"),
    ]
    kept, residue = project_edges_for_prompt(edges)
    assert [e["to"] for e in kept] == ["b"]
    ind = residue["indeterminate"]
    assert len(ind) == 1 and ind[0]["value"]["caller"] == "a"
    assert ind[0]["value"]["methods"] == {"send": 2}        # 真實基數、不去重
    assert ind[0]["position"]["gap_kind"] == "indeterminate"
    assert ind[0]["position"]["cardinality"] == 2
    assert ind[0]["position"]["proportion"] == 2 / 5
    assert residue["low_confidence_ambiguous"] == {"a": {"write": 2}}   # 座標分流、基數保留
```

把 `tests/unit/core/llm/test_edge_projection.py` **整檔替換**為新 residue 形狀：

```python
"""Edge projection pure-function behavior (membrane residue shape)."""
from the_door.core.llm.edge_projection import project_edges_for_prompt

_EMPTY = {"indeterminate": [], "low_confidence_ambiguous": {}}


def _edge(from_, to, res):
    return {"from": from_, "to": to, "type": "calls", "resolution": res}


def test_scope_rule_edges_kept():
    edges = [_edge("a", "b", "scope_rule")]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == edges
    assert residue == _EMPTY


def test_import_alias_edges_kept():
    edges = [_edge("a", "b", "import_alias")]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == edges
    assert residue == _EMPTY


def test_name_match_edges_kept():
    edges = [_edge("a", "b", "name_match")]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == edges
    assert residue == _EMPTY


def test_ambiguous_dropped_into_low_confidence_with_count():
    edges = [_edge("caller", "pkg.Foo.write", "name_match_ambiguous")]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == []
    assert residue["low_confidence_ambiguous"] == {"caller": {"write": 1}}
    assert residue["indeterminate"] == []


def test_dynamic_dropped_into_indeterminate_noise():
    edges = [_edge("caller", "Bus.send", "skipped_dynamic")]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == []
    ind = residue["indeterminate"]
    assert len(ind) == 1
    assert ind[0]["value"] == {"caller": "caller", "methods": {"send": 1}}
    assert ind[0]["position"]["kind"] == "noise"
    assert ind[0]["position"]["gap_kind"] == "indeterminate"
    assert ind[0]["position"]["cardinality"] == 1
    assert ind[0]["position"]["proportion"] == 1.0
    assert residue["low_confidence_ambiguous"] == {}


def test_dynamic_same_method_counted_not_deduped():
    """N3: 同名 method 多筆 → cardinality 真實計數（修 F5 病灶①）。"""
    edges = [_edge("caller", f"M{i}.send", "skipped_dynamic") for i in range(50)]
    _kept, residue = project_edges_for_prompt(edges)
    ind = residue["indeterminate"]
    assert ind[0]["value"]["methods"] == {"send": 50}
    assert ind[0]["position"]["cardinality"] == 50


def test_two_gap_kinds_split_not_conflated():
    """N4: skipped_dynamic 與 name_match_ambiguous 座標分流（修 F5 病灶②）。"""
    edges = [
        _edge("a", "Bus.send", "skipped_dynamic"),
        _edge("a", "F.write", "name_match_ambiguous"),
    ]
    _kept, residue = project_edges_for_prompt(edges)
    assert residue["indeterminate"][0]["value"]["methods"] == {"send": 1}
    assert residue["low_confidence_ambiguous"] == {"a": {"write": 1}}


def test_mixed_resolutions_partial_drop():
    edges = [
        _edge("a", "b", "scope_rule"),
        _edge("a", "c", "name_match"),
        _edge("a", "F.write",  "name_match_ambiguous"),
        _edge("a", "Bus.send", "skipped_dynamic"),
        _edge("a", "f", "import_alias"),
    ]
    kept, residue = project_edges_for_prompt(edges)
    assert {e["to"] for e in kept} == {"b", "c", "f"}
    assert residue["indeterminate"][0]["value"]["methods"] == {"send": 1}
    assert residue["low_confidence_ambiguous"] == {"a": {"write": 1}}


def test_to_node_without_dot_uses_whole_id_as_method_name():
    edges = [_edge("caller", "bare", "name_match_ambiguous")]
    _kept, residue = project_edges_for_prompt(edges)
    assert residue["low_confidence_ambiguous"] == {"caller": {"bare": 1}}


def test_indeterminate_list_sorted_by_caller_deterministic():
    """清單順序依 caller 排序＝prompt 跨次穩定（亂序輸入→相同順序輸出）。"""
    edges = [
        _edge("zeta", "B.f", "skipped_dynamic"),
        _edge("alpha", "B.g", "skipped_dynamic"),
        _edge("mu", "B.h", "skipped_dynamic"),
    ]
    _kept, residue = project_edges_for_prompt(edges)
    callers = [el["value"]["caller"] for el in residue["indeterminate"]]
    assert callers == ["alpha", "mu", "zeta"]


def test_empty_edges_returns_empty():
    kept, residue = project_edges_for_prompt([])
    assert kept == []
    assert residue == _EMPTY


def test_unknown_resolution_kept_defensively():
    edges = [{"from": "a", "to": "b", "type": "calls", "resolution": "future_value"}]
    kept, residue = project_edges_for_prompt(edges)
    assert kept == edges
    assert residue == _EMPTY
```

把 `tests/property/test_edge_projection_properties.py` **整檔替換**（移除去重 property、idempotent 改空殘餘、加基數反向 property）：

```python
"""Property tests for edge_projection invariants (membrane residue shape)."""
from collections import Counter

from hypothesis import given, strategies as st

from the_door.core.llm.edge_projection import project_edges_for_prompt

KNOWN_RESOLUTIONS = st.sampled_from([
    "scope_rule", "import_alias", "name_match",
    "name_match_ambiguous", "skipped_dynamic",
])
EDGE = st.fixed_dictionaries({
    "from": st.text(min_size=1, max_size=10),
    "to": st.text(min_size=1, max_size=10),
    "type": st.just("calls"),
    "resolution": KNOWN_RESOLUTIONS,
})
EDGES = st.lists(EDGE, max_size=30)
_EMPTY = {"indeterminate": [], "low_confidence_ambiguous": {}}


@given(edges=EDGES)
def test_high_confidence_always_kept(edges):
    high_conf = [e for e in edges if e["resolution"] in ("scope_rule", "import_alias")]
    kept, _residue = project_edges_for_prompt(edges)
    for e in high_conf:
        assert e in kept


@given(edges=EDGES)
def test_ambiguous_and_dynamic_never_in_kept(edges):
    kept, _residue = project_edges_for_prompt(edges)
    for e in kept:
        assert e["resolution"] not in ("name_match_ambiguous", "skipped_dynamic")


@given(edges=EDGES)
def test_idempotent(edges):
    """Re-projecting kept_edges is a no-op (kept edges produce no residue)."""
    kept1, _r1 = project_edges_for_prompt(edges)
    kept2, residue2 = project_edges_for_prompt(kept1)
    assert kept2 == kept1
    assert residue2 == _EMPTY


@given(edges=EDGES)
def test_indeterminate_cardinality_equals_skipped_dynamic_count(edges):
    """N3 反向 property：每 caller 的 indeterminate cardinality
    ＝該 caller 的 skipped_dynamic 邊真實筆數（不去重）。"""
    _kept, residue = project_edges_for_prompt(edges)
    expected = Counter(e["from"] for e in edges if e["resolution"] == "skipped_dynamic")
    got = {el["value"]["caller"]: el["position"]["cardinality"]
           for el in residue["indeterminate"]}
    assert got == dict(expected)
```

把 `tests/integration/test_batch_reader_projection.py` 的 5 個 test **改鍵名＋形狀**（其餘 helper 不動）：
- `test_detail_payload_includes_aggregate_call_hints_key` → 改名 `..._residue_key`；`assert "aggregate_call_residue" in payload`；`assert payload["aggregate_call_residue"] == {"indeterminate": [], "low_confidence_ambiguous": {}}`。
- `test_ambiguous_edges_dropped_and_hint_populated`：`assert payload["aggregate_call_residue"]["low_confidence_ambiguous"] == {"caller": {"write": 4}}`（4 筆同名→計數 4）＋`["indeterminate"] == []`。
- `test_dynamic_edges_aggregated_into_hints`：`assert payload["edges"] == []`；`ind = payload["aggregate_call_residue"]["indeterminate"]; assert ind[0]["value"] == {"caller": "caller", "methods": {"send": 1}}; assert ind[0]["position"]["gap_kind"] == "indeterminate"`。
- `test_minimal_mode_has_no_aggregate_call_hints_key` → 改名 `..._residue_key`；`assert "aggregate_call_residue" not in payload`；末斷言 `payload == {"batch": 0, "context_mode": "minimal", "nodes": ["a", "b"]}`（不變）。
- `test_batch_local_filter_applied_before_projection`：`assert payload["aggregate_call_residue"]["low_confidence_ambiguous"] == {"caller": {"x": 1}}`。

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/llm/test_edge_projection.py tests/unit/core/llm/test_edge_projection_membrane.py tests/property/test_edge_projection_properties.py tests/integration/test_batch_reader_projection.py -q`
Expected: FAIL（`project_edges_for_prompt` 仍回舊 `(kept, hints)`、`residue` 鍵不存在 → KeyError/AssertionError；batch_reader payload 仍 `aggregate_call_hints`）。

- [ ] **Step 3: Write minimal implementation**

`src/the_door/core/llm/edge_projection.py` **整檔替換**＝**spec §3.3 的 exact code**（`from collections import Counter`＋`from ...edge_membrane import indeterminate_residue_element, is_residue`＋`_AMBIGUOUS`＋新 `project_edges_for_prompt` 回 `(kept, residue)`＋`_method_name_from_to` 不變）。

`src/the_door/core/reading/batch_reader.py`：
- `:301` `kept_edges, aggregate_hints = project_edges_for_prompt(edge_dicts)` → `kept_edges, aggregate_residue = project_edges_for_prompt(edge_dicts)`。
- `:307` `"aggregate_call_hints": aggregate_hints,` → `"aggregate_call_residue": aggregate_residue,`。

> 不重貼 edge_projection（spec §3.3 唯一來源）。關鍵：`is_residue(res)`→`indeterminate_counts`；`res==_AMBIGUOUS`→`ambiguous_counts`；其餘→`kept`；residue 兩鍵內層皆 `sorted`（決定性，§3.3）。

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/llm/ tests/property/test_edge_projection_properties.py tests/integration/test_batch_reader_projection.py -q`
Expected: PASS（含 flip 後的 characterization）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/core/llm/edge_projection.py src/the_door/core/reading/batch_reader.py tests/unit/core/llm/test_edge_projection.py tests/unit/core/llm/test_edge_projection_membrane.py tests/property/test_edge_projection_properties.py tests/integration/test_batch_reader_projection.py
git commit -m "feat(edge-projection): F5 retrofit — split coordinates, keep cardinality, NoisePosition (N3/N4)

Output contract change (witnessed): (kept, hints:dict[str,list]) -> (kept, residue)
where skipped_dynamic -> NoisePosition(indeterminate, real-count, proportion) and
name_match_ambiguous kept as counted bucket (confidence Signal deferred to S4).
batch_reader payload key aggregate_call_hints -> aggregate_call_residue.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: prompt 教學同步重塑（`L1_SYSTEM_PROMPT`）

**理論錨：** 膜論旨——結構變、教 LLM 怎麼讀的話也要變（§8.14 病灶②下傳 prompt）。

**Files:**
- Modify: `src/the_door/core/llm/prompts.py`
- Modify(test): `tests/unit/core/llm/test_prompt_resolution_section.py`、`tests/unit/core/llm/test_prompts_resolution.py`

- [ ] **Step 1: Update prompt tests to NEW field name (now failing)**

- `test_prompt_resolution_section.py:17`：`assert "aggregate_call_hints" in text` → `assert "aggregate_call_residue" in text`。
- `test_prompts_resolution.py:24`：`assert "aggregate_call_hints" in L1_SYSTEM_PROMPT` → `assert "aggregate_call_residue" in L1_SYSTEM_PROMPT`。
- （其餘斷言不動：禁 `` `name_match_ambiguous` ``/`` `skipped_dynamic` `` backtick、含 `高信心`/`低信心`/`依賴`/`寧可不提`/三 label——下一步 prompt 改寫須保這些成立。）

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/llm/test_prompt_resolution_section.py tests/unit/core/llm/test_prompts_resolution.py -q`
Expected: FAIL — prompt 仍含舊詞 `aggregate_call_hints`、新詞 `aggregate_call_residue` 不存在（兩 flip 測試 fail；其餘綠）。

- [ ] **Step 3: Write minimal implementation**

`src/the_door/core/llm/prompts.py`：把 `:45-65`（「你不會在 `edges` 內看到…」起、整個 `## aggregate_call_hints 欄位` 段，到 `對 aggregate_call_hints 不寫成依賴。` 止）**整段替換**為下方四反引號區塊內的文字（外層用四反引號是為了讓內含的三反引號 JSON 範例乾淨巢狀——**貼入 prompt 時不含最外層四反引號**）。**保留 `:39-43` 的三 label 段不動**（高信心/低信心/per-edge label 在那）。**禁** 在新段使用 `` `skipped_dynamic` ``/`` `name_match_ambiguous` `` backtick：

````text
你不會在 `edges` 內看到「高候選量裸名匹配」或「動態 dispatch」邊 — 它們已在輸入端被聚合成 `aggregate_call_residue` 欄位。

## `aggregate_call_residue` 欄位

payload 內額外提供「無法精確定位的呼叫殘餘」，**按性質分成兩座標**（不混為一桶）：

```
"aggregate_call_residue": {
  "indeterminate": [
    {
      "value": {"caller": "feat-x-caller-node-id", "methods": {"send": 12, "write": 3}},
      "position": {"kind": "noise", "gap_kind": "indeterminate",
                   "cardinality": 15, "proportion": 0.21, "aggregated": true}
    }
  ],
  "low_confidence_ambiguous": {
    "feat-x-caller-node-id": {"handle": 2, "get": 1}
  }
}
```

- `indeterminate`：**動態 dispatch、靜態無法解析**的呼叫，**刻意保留為不確定（非遺漏）**。每筆是某 caller 的殘餘聚合：`methods` 列各方法名與**真實次數**（不去重）；`cardinality` 是該 caller 殘餘總筆數、`proportion` 是佔本批呼叫的比例。基數／比例供你判斷「殘餘是否顯著」（如 cardinality=50 vs 1），但**不放寬下列紀律**。
- `low_confidence_ambiguous`：**高候選量裸名匹配**（低信心），結構為 `{caller: {方法名: 次數}}`。

撰寫 description 時的紀律（對上述兩者皆適用）：
- **不可** 把殘餘內的方法名當成「呼叫了某 feature」的依據
- **不可** 因為殘餘內有某方法名，就在 `feature_relations` 加上 `depends_on`
- 若 description 必須提到，限定為「執行了一些（寫入 / 讀取 / 處理）動作」這種泛稱
- 寧可不提，不要勉強寫出帶有不確定性的依賴敘述

撰寫 description 時，優先以 `scope_rule` / `import_alias` 高信心邊為依據；對 `name_match` 持保守態度；對 `aggregate_call_residue`（兩座標）不寫成依賴。
````

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/llm/test_prompt_resolution_section.py tests/unit/core/llm/test_prompts_resolution.py -q`
Expected: PASS（含未動的 backtick-absence／高低信心／依賴／寧可不提 斷言仍綠）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/core/llm/prompts.py tests/unit/core/llm/test_prompt_resolution_section.py tests/unit/core/llm/test_prompts_resolution.py
git commit -m "feat(prompt): teach L1 the split residue (indeterminate vs low-confidence) with cardinality

Membrane payoff: structure + teaching reshaped together. Replaces the lumped
aggregate_call_hints teaching; conservatism discipline preserved verbatim.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 全套件回歸驗收 ＋ 連貫性

**Files:** （無；驗收 gate）

- [ ] **Step 1: membrane + edge + reading 相關全測**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/membrane/ tests/unit/core/llm/ tests/property/ tests/integration/test_batch_reader_projection.py tests/unit/core/scope/ -q`
Expected: 全綠（含 S0 `test_s1_coherence.py`、S1 doubt 全測仍綠＝S0/S1 地基未鬆動）。

- [ ] **Step 2: 全測零回歸**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest -q`
Expected: 1477（S1 基線）＋新增測試、零 fail。**唯一「變更」＝Task 4/5 的 edge_projection/property/integration/prompt 斷言有意更新（契約變更見證）**；其餘純加法。若有非預期 fail（例如某處仍讀 `aggregate_call_hints`）→ 停下檢查是否有未盤點的消費者。

- [ ] **Step 3:（無新 commit；驗收通過即 S2 完成）**

S2 完成 → 進 S3（RelayedVerdict／vulnerability cvss）spec。起 S3 前重跑種子檔 §9.2 理論重錨、讀 S0 §3a（RelayedVerdict＝evidence-bearing、無 evidence 退 NoisePosition）＋S2 spec §5（A 側慣例）＋§7（對 S3 回驗點）。

---

## Self-Review

**1. Spec coverage：**
- spec §3.1 NoisePosition＋GAP_KIND_PRIORITY → Task 1 ✓
- spec §3.2 edge_membrane → Task 2 ✓
- spec §3.3 F5 retrofit → Task 4 ✓
- spec §3.4 prompt 教學 → Task 5 ✓
- spec §4 不變量 N1(T1)/N2(T1)/N3(T4)/N4(T4)/N5(T1 型別缺欄) ✓
- spec §6 characterization 先行 → Task 3（釘）+ Task 4（flip）✓
- spec §9 交付物 1-8 → Task 1-5 全覆蓋（交付物 8 既有測試更新＝Task 4/5）✓
- out（audit_conformance／name_match_ambiguous confidence Signal／provenance）→ 正確不在本 plan ✓

**2. Placeholder scan：** 無 TBD；每 step 含完整 test code＋exact 指令＋預期輸出；impl code 引 spec §3.x（線性相依、單一 code 來源，仿 S1）。

**3. Type consistency：** `NoisePosition(gap_kind,cardinality,proportion,aggregated)`／`GAP_KIND_PRIORITY`／`_position_to_json`→`{kind:"noise",...}`／`is_residue`/`indeterminate_residue_element(caller,method_counts,total_edges)`／`project_edges_for_prompt(edges)->(kept, residue{indeterminate:[...], low_confidence_ambiguous:{...}})`／batch_reader payload `aggregate_call_residue`／prompt 同名——跨 Task 1-5 一致 ✓。resolution 5 值對齊 `edge_builder.py:46-49` ✓。

**4. 依賴順序：** Task 1（NoisePosition）→ Task 2（edge_membrane 用之）→ Task 4（edge_projection 用 edge_membrane）；Task 3（釘現狀）→ Task 4（flip）；Task 4（結構+鍵改名）→ Task 5（prompt 教新鍵）。無逆序 ✓。

**5. characterization-first（契約變更安全網）：** Task 3 釘 F5 病灶現狀（green）→ Task 4 flip 為新 residue＝有意變更見證；prompt 側 Task 5 step1 先 flip 測試（red）再改 prompt（green）。動輸出/教學契約前皆先釘。
