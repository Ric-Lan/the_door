# S5 scope 主軸整膜 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** scope_state 主軸（§181 三主軸之一）LLM-facing 整膜——把 `scope_verify_tool` emit 的裸 scope_state enum 經 `SignalPosition` 攜 3-state 對比位置送達消費端 LLM（不靠 prompt）。**乙案膜 campaign 最薄刀（S5）**：純格內 3-state Signal、**無 A 側**（無缺值/殘餘/input schema/output schema/reserved——spike 證實 scope_state 恆指派、無第四類）。承 S1 `doubt_type_signal`（純 enum 樣板）＋ S4 confidence（Signal 工廠樣板）。

**Architecture:** 新 `core/scope/scope_membrane.py`（`SCOPE_CONTRASTS` 3 值唯一來源＋`scope_signal`/`scope_element`，**無 schema_fragment、無 None 分支**）＋ emit 膜投影（`scope_verify_tool:63`）＋ producer 值域雙向釘樁（characterization）。**LLM-facing 面＝1 emit 點（scope_verify_tool）；report 面（update_tool→render_json，與 viewer 共用）＝out 歸 S6；human 面（badge/label/CLI）out。**

**Tech Stack:** Python、S0 `core/membrane`、dataclass、pytest。

**理論錨（spec `docs/superpowers/specs/2026-06-06-S5-scope-throughline-spec.md`；種子檔 §181/§278/§8.10/§8.13）：**
- scope＝三主軸之一、B 側格內 Signal（§181）→ C1。
- scope_state 3 值全覆蓋、恆指派 → 純格內、**無 NoisePosition/缺值**（spike 校正 §181「unrecognized」＝非本標的，真實 verify 窮舉無第四類）→ C3。
- 單一來源（§8.10）→ C2（emit 詞彙單源＋producer 值域雙向 ==）。
- scope_state 與 doubt_type 共享 2 字串但 contrasts 集不同（3 vs 4）＝正交軸、不單源化（§181 軸正交）→ C4。
- emit 無裸 enum（§8.2）→ C3。

**檔案數量判斷：**
- **plan＝單檔**：3 task 線性相依（地基→emit→釘樁+gate），拆檔斷敘事（S1-S4 已立此則）。
- **`scope_membrane.py` 獨立檔**：照 `{domain}_membrane.py` 慣例；安置 `core/scope`（scope 最權威產地，同 doubt）。
- **無擴 primitive**：純復用 S0 `SignalPosition`。

**Preconditions（執行前確認，非 task）：**
- 換 worktree 後先 `pip install -e ./the_door`（本 worktree 已裝）。
- pytest cwd＝內層 `the_door/`；Windows cp950 前置 `PYTHONUTF8=1`。
- 基線＝S4 merged 後 **1519 passed**。本 plan：scope_membrane 純加法；emit 形狀變更由 characterization 見證；無模型/schema 改。

**已驗事實（寫 plan 前 spike，2026-06-06；file:line 見 spec §2）：**
- scope_state 值集＝`in_scope_complete`/`in_scope_incomplete`/`out_of_scope`（`models/scope.py:32` 行註解；`scope_verifier.verify:94-124` 三迴圈窮盡、恆指派、無第四類、無缺值）。
- **唯一本刀 emit**：`scope_verify_tool.py:63` `"scope_state": e.scope_state`（inline dict、不經 render_json）。`:69-73` counts＝int 直方圖（保留）。
- **report 面（out）**：`update_tool:112`→`render_json:212,842` 亦 bare scope_state，但 render_json 與 viewer（`analysis.py:188`）共用 → 歸 S6/report 面、本刀不動（spec §1 out、先例 S4 diff.py）。
- **doubt 重疊（正交）**：`doubt_membrane._TYPE_GLOSS`＝4-set{out_of_scope,in_scope_incomplete,anomaly,low_confidence}；scope＝3-set → contrasts 集不等＝正交、獨立 membrane（不單源化）。
- 無循環 import：`scope_membrane`→`core.membrane`（單向）；`scope_verify_tool`→`scope_membrane`。
- **既有測試附帶影響**（plan 執行時 grep 確認）：`scope_verify_tool` 既有測若斷言 `entries[].scope_state == "..."` 裸字串 → Task 2 flip 為膜投影形狀。`scope_verifier` 既有測斷言 scope_state 值＝**不受影響**（producer 不變）。

---

## File Structure

| 檔案 | 職責 | 動作 |
|---|---|---|
| `src/the_door/core/scope/scope_membrane.py` | `SCOPE_CONTRASTS`＋`scope_signal`＋`scope_element` | Create |
| `tests/unit/core/scope/test_scope_membrane.py` | C1（值→Signal）＋to_json 形狀＋C4（與 doubt 正交） | Create |
| `src/the_door/mcp/tools/scope_verify_tool.py` | 抽純 `_entry_to_json`（仿 `_feature_to_json`）；`:63` 改用之、scope_state 經 `scope_element` 投影 | Modify |
| `tests/unit/mcp/test_scope_verify_tool.py`（新建） | 直接測 `_entry_to_json` emit 膜投影 | Create |
| `tests/unit/core/scope/test_scope_verifier*.py`（既有或新建） | C2 值域雙向釘樁（== SCOPE_CONTRASTS） | Modify/Create |

---

### Task 1: scope 膜詞彙＋單一來源（地基）

**理論錨：** scope＝B 側 3-state Signal（§181）＝C1；與 doubt 正交（§181 軸正交）＝C4。**純加法、純 enum 樣板（承 `doubt_type_signal`）。**

**Files:**
- Create: `src/the_door/core/scope/scope_membrane.py`、`tests/unit/core/scope/test_scope_membrane.py`（必要時建 `tests/unit/core/scope/__init__.py`）

- [ ] **Step 1: Write the failing test**

建立 `tests/unit/core/scope/test_scope_membrane.py`：

```python
"""S5 scope 膜：3-state 格內 Signal / 與 doubt_type 正交。"""
from the_door.core.scope.scope_membrane import (
    SCOPE_CONTRASTS, scope_element, scope_signal,
)


def test_contrasts_three_state():
    assert SCOPE_CONTRASTS == ("in_scope_complete", "in_scope_incomplete", "out_of_scope")  # C1


def test_value_to_signal():
    sig = scope_signal("out_of_scope")
    assert sig.contrasts == SCOPE_CONTRASTS and sig.gloss      # C1（純 enum：contrasts+gloss）
    assert sig.preconditions == () and sig.consequences == ()  # 無前件/後件（categorical）


def test_element_value_is_signal():
    j = scope_element("in_scope_complete").to_json()
    assert j["value"] == "in_scope_complete" and j["position"]["kind"] == "signal"
    assert j["position"]["contrasts"] == list(SCOPE_CONTRASTS)


def test_orthogonal_to_doubt_type():
    """C4：scope_state 與 doubt_type 共享字串但 contrasts 集不同（3 vs 4）＝正交、不單源化。"""
    from the_door.core.scope.doubt_membrane import _TYPE_GLOSS
    assert set(SCOPE_CONTRASTS) != set(_TYPE_GLOSS)                       # 集不等
    assert {"out_of_scope", "in_scope_incomplete"} <= set(SCOPE_CONTRASTS) & set(_TYPE_GLOSS)  # 共享 2 字串
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/scope/test_scope_membrane.py -q`
Expected: FAIL — `ModuleNotFoundError: ... scope_membrane`。

- [ ] **Step 3: Write minimal implementation**

建立 `src/the_door/core/scope/scope_membrane.py`＝**spec §3.1 的 exact code 全文**（`SCOPE_CONTRASTS`＋`scope_signal`＋`scope_element`）。
> 不重貼（spec §3.1 唯一來源）。關鍵不變式：值→SignalPosition(contrasts=SCOPE_CONTRASTS 純 enum)；**無 None 分支、無 schema_fragment**。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/scope/ -q`
Expected: PASS（scope_membrane 全綠＋既有 scope 測仍綠）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/core/scope/scope_membrane.py tests/unit/core/scope/test_scope_membrane.py
git commit -m "feat(scope-membrane): scope_state 3-state vocab + ordered single source (C1/C4)

SCOPE_CONTRASTS 唯一來源（in_scope_complete/incomplete/out_of_scope）；值->SignalPosition
（純 enum：contrasts+gloss、無前件後件、無 None 分支、無格外殘餘）。與 doubt_type 正交
（contrasts 集 3 vs 4、不單源化）。承 S1 doubt_type 樣板、純加法。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: emit 膜投影（B 側送達：scope_verify_tool）

**理論錨：** B 側送達 emit 無裸 enum（§8.2）＝C3。依賴 Task1（scope_element）。

> **測試可行性（plan concept-review warning 修）**：**無**既有 `test_scope_verify_tool.py`；既有 `_scope_verify_recipe`（`tests/unit/mcp/_invocation_recipes.py:241`）只覆蓋「無 snapshot→error」路徑、**不達 emit**。`execute()` 達 emit 需重設定（scope file＋snapshot＋doubt store）。故照**碼庫既有慣例**（`analyze_changes_tool._feature_to_json`／`report_renderer._scope_result_to_dict`）：**抽純投影 helper `_entry_to_json` 並直接單元測**（hand-built `ScopeEntry`、零檔案/snapshot 設定）＝可投影 seam＋可測。

**Files:**
- Modify: `src/the_door/mcp/tools/scope_verify_tool.py`（抽 `_entry_to_json`、`:63` 改用之）
- Test: `tests/unit/mcp/test_scope_verify_tool.py`（新建，直接測 `_entry_to_json`）

- [ ] **Step 1: Write the failing test（直接測抽出的純 helper）**

新建 `tests/unit/mcp/test_scope_verify_tool.py`：

```python
"""S5 C3：scope_verify_tool entry 投影 scope_state 經膜（值→signal、無裸 enum）。"""
from the_door.mcp.tools.scope_verify_tool import _entry_to_json
from the_door.models import ScopeEntry


def test_entry_scope_state_membrane_projection():
    e = ScopeEntry(feature_id="feat-x", scope_state="out_of_scope",
                   feature_label="L", expected_label="E")
    j = _entry_to_json(e)
    assert isinstance(j["scope_state"], dict)                              # C3 無裸 enum
    assert j["scope_state"]["value"] == "out_of_scope"
    assert j["scope_state"]["position"]["kind"] == "signal"
    assert j["scope_state"]["position"]["contrasts"] == [
        "in_scope_complete", "in_scope_incomplete", "out_of_scope"]
    assert j["feature_id"] == "feat-x"                                     # 載體欄保留
    assert j["feature_label"] == "L" and j["expected_label"] == "E"
```

> 此為**新函式 TDD**（無既有 unit 測 pin 工具 emit；契約變更＝裸→膜由本測見證）。red＝`_entry_to_json` 未存在（ImportError）。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_scope_verify_tool.py -q`
Expected: FAIL — `ImportError: cannot import name '_entry_to_json'`。

- [ ] **Step 3: Write minimal implementation**（spec §3.2）

- 抽 `_entry_to_json(e) -> dict`（module-level，仿 `analyze_changes_tool._feature_to_json`）：`feature_id`／`scope_state`: `scope_element(e.scope_state).to_json()`／`feature_label`／`expected_label`。
- `execute():63` 區 `"entries"` 改 `[_entry_to_json(e) for e in scope_result.entries]`。
- import `from the_door.core.scope.scope_membrane import scope_element`。
- `counts`（`:69-73`）＝**不動**（int 直方圖）。

> 不重貼（spec §3.2 唯一來源）。**不碰 render_json／update_tool／viewer（report 面 out、spec §1）。**

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/ -q`
Expected: PASS（`_entry_to_json` 投影綠＋其餘 mcp 測〔含 `_scope_verify_recipe` error 路徑〕仍綠）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/mcp/tools/scope_verify_tool.py tests/unit/mcp/test_scope_verify_tool.py
git commit -m "feat(scope-emit): membrane projection at scope_verify_tool (C3)

抽純 _entry_to_json（仿 _feature_to_json）；scope_state -> scope_element（值=signal、
3-state contrasts）、無裸 enum。counts（int 直方圖）保留；report 面（update_tool render_json
與 viewer 共用）=out 歸 S6。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: C2 producer 值域雙向釘樁 ＋ 全套件回歸驗收

**理論錨：** 單一來源（§8.10）＝C2；emit 詞彙單源＋producer 值集雙向 == SCOPE_CONTRASTS（spec §3.3 誠實界定）。

**Files:**
- Test: `tests/unit/core/scope/test_scope_verifier*.py`（既有或新建 C2 釘樁）

- [ ] **Step 1: Write the C2 value-domain pinning test**

`grep -rn 'class.*ScopeVerifier\|def test' tests/unit/core/scope/test_scope_verifier*.py` 定位既有 verify 測；加（或新建）：

```python
def test_verify_state_domain_equals_single_source():
    """C2：verify 對涵蓋三分類的輸入產出 scope_state 值集 == SCOPE_CONTRASTS（雙向釘樁）。"""
    from the_door.core.scope.scope_membrane import SCOPE_CONTRASTS
    from the_door.core.scope.scope_verifier import ScopeVerifier
    from the_door.models import (
        L1Output, Feature, ScopeDefinition, ScopeFeatureEntry,
    )
    # feat-both（complete）／feat-l1（out_of_scope）／feat-scope（in_scope_incomplete）
    scope_def = ScopeDefinition(scope_name="s", features=[
        ScopeFeatureEntry(feature_id="feat-both"),
        ScopeFeatureEntry(feature_id="feat-scope"),
    ])
    l1 = L1Output(features=[
        Feature(feature_id="feat-both", label="B", description="", trigger="user_action",
                trigger_description="", confidence="high", confidence_reason=""),
        Feature(feature_id="feat-l1", label="L", description="", trigger="user_action",
                trigger_description="", confidence="high", confidence_reason=""),
    ])
    result = ScopeVerifier().verify(scope_def, l1)
    assert {e.scope_state for e in result.entries} == set(SCOPE_CONTRASTS)   # 雙向 ==
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/scope/ -q`
Expected: PASS（verify 三迴圈恰產三 state；雙向 == 成立）。**這是釘樁測（驗已成立的單一來源契約、非 flip）**——若失敗代表 producer 或 SCOPE_CONTRASTS 漂移。

> 註：本 task 無 impl（Task1 已建 SCOPE_CONTRASTS、producer 已產三值）；Step 1 測**直接綠**＝釘樁。若紅→Task1 SCOPE_CONTRASTS 與 producer 不符、回頭對齊。

- [ ] **Step 3: Commit the pinning test**

```bash
git add tests/unit/core/scope/test_scope_verifier_domain.py   # 或既有檔
git commit -m "test(scope-c2): pin verify scope_state domain == SCOPE_CONTRASTS (two-way single-source guard)

雙向釘樁：⊆ 抓 producer 冒新值、⊇ 抓 SCOPE_CONTRASTS 死值。任一漂移即紅。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: 全套件回歸驗收**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/scope/ tests/unit/core/membrane/ tests/unit/mcp/ -q`
然後全測：`cd the_door && PYTHONUTF8=1 python -m pytest -q`
Expected: 1519（S4 基線）＋新測、零回歸。**唯一「變更」＝Task 2 emit 形狀（scope_state 裸→{value,position}）有意更新**；其餘純加法。**特別確認**：S1 doubt 全測仍綠（`doubt_membrane` 不動）；`update_tool`/`render_json`/viewer 相關測不受影響（本刀未動 render_json）。

- [ ] **Step 5:（無新 commit；驗收通過即 S5 完成）**

S5 完成 → ff-merge main（逐刀本地 merge、不主動 push）→ 進 S6（diff_state）spec。S6 首步＝spike 校正 `diff_state` 值集不一致（種子 §433/§444 標 :14 五值 vs :29 三值），以真實 emit 值域為準收斂 `DIFF_STATE_CONTRASTS`（S5 已示範「拿真實標的校正種子/前刀假設」）；讀 spec §5 慣例 5（共用 renderer 軸＝歸該面整膜）＋§7（對 S6 回驗）。

---

## Self-Review

**1. Spec coverage：**
- spec §3.1 scope_membrane（SCOPE_CONTRASTS+2 工廠）→ Task 1 ✓
- spec §3.2 emit 投影（scope_verify_tool）→ Task 2 ✓
- spec §3.3 C2 雙向釘樁 → Task 3 ✓
- spec §4 不變量 C1/C4(T1)、C3(T2)、C2(T3) ✓
- spec §6 characterization 先行 → Task 2（emit pin→flip）✓
- out（report 面 render_json／NoisePosition／缺值／input/output schema／reserved／human 面）→ 正確不在本 plan ✓

**2. Placeholder scan：** Task 2 改為**直接測抽出的純 `_entry_to_json`**（hand-built `ScopeEntry`、零佔位、零檔案/snapshot 設定）；Task 3 fixture 為具體 hand-built `ScopeDefinition`/`L1Output`。全 step 含完整 test code＋exact 指令＋預期輸出；impl 引 spec §3.x。

**3. Type consistency：** `SCOPE_CONTRASTS:tuple`／`scope_signal(str)->SignalPosition`／`scope_element(str)->MembraneElement`（無 None）／emit→`scope_element(...).to_json()`——跨 Task 1-2 一致 ✓。

**4. 依賴順序：** Task1（membrane）→ Task2（emit 用 scope_element）；Task3（C2 釘樁）僅依 Task1 的 SCOPE_CONTRASTS、與 Task2 獨立。無逆序 ✓。**無 schema/缺值 task ⟹ 無 S3/S4 式「schema 先於產 None」依賴**（scope 無缺值、無 schema）。

**5. 契約變更安全網：** Task 2＝**新函式 TDD**（抽 `_entry_to_json`、red＝ImportError→green＝膜投影；無既有 unit 測 pin 工具 emit、故非 pin→flip 而是新測見證裸→膜契約變更）。Task 3＝釘樁測（驗既成單源契約、直接綠）。**唯一契約變更＝scope_verify_tool entries[].scope_state 形狀（新測圈住）；report 面/viewer 未動（render_json 不碰）⟹ 零附帶破壞。** 執行時 Step4 全 mcp 測確認既有 `_scope_verify_recipe`（error 路徑）等不受抽 helper 影響。

**6. 理論對照（使用者要求「對照理論原則」）：** 每 task 理論錨已標；核心對照——C1/C4＝§181 三主軸 Signal＋軸正交；C3＝§8.2 B 側送達無裸 enum；C2＝§8.10 單一來源（誠實降為 emit 單源＋producer 雙向釘樁）。**無 A 側（缺值/殘餘/input/schema/reserved）＝spike 證實 scope 無此面、守一刀只做該軸該面有的（正做不窄做、亦不虛做）。report 面＝面×軸交格、歸 S6（spec §5 慣例 5）。**
