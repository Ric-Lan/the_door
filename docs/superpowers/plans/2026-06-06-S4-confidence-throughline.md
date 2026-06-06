# S4 confidence 主軸整膜 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** confidence 主軸（§181 三主軸之一）LLM-facing 整膜——①B 側 Signal 投影（confidence 值經 `SignalPosition` 攜全序對比位置送達消費端 LLM、不靠 prompt）＋②A 側「閉集 enum 缺值誠實化」通則（生產端 `.get("confidence","medium")` 靜默自鑄 → 缺值退 `NoisePosition(indeterminate)`、消 dataclass 自鑄假值）＋③`name_match_ambiguous`（S2 留的 edge 低信心桶）升 confidence Signal。乙案膜 campaign 的 confidence 軸落地刀（S4），承 S1 doubt（B 側樣板）＋S2 NoisePosition（A 側退路）＋S3 缺值退 indeterminate 先例。

**Architecture:** 新 `core/reading/confidence_membrane.py`（`CONFIDENCE_CONTRASTS` 全序唯一來源＋`confidence_signal`/`confidence_element`/`confidence_reason_element`/`confidence_schema_fragment`）＋ 模型 `confidence: str|None`（消自鑄假 medium）＋ 生產端缺值誠實化（batch_reader/l2_generator/snapshot_store）＋ 3 output schema nullable+per-value desc ＋ input schema per-value desc（snapshot_write/patch）＋ emit 膜投影（analyze_tool/analyze_changes）＋ edge name_match_ambiguous 升巢狀 confidence Signal。**LLM-facing 面＝2 input schema＋2 output emit＋edge 桶；人類面（viewer/report_renderer/CLI/confidence_marker）out。**

**Tech Stack:** Python、S0 `core/membrane`、dataclass、jsonschema（fail-closed 寫入）、pytest。

**理論錨（spec `docs/superpowers/specs/2026-06-06-S4-confidence-throughline-spec.md`；種子檔 §181/§235/§291/§357/§442/§443/§8.13）：**
- confidence＝三主軸之一、B 側格內 Signal 全序（§181）→ C1/C2。
- 缺值退 NoisePosition(indeterminate)、不自鑄 default（§8.13 通則、復用 S2/S3）→ C3/C4（S4 立「閉集 enum 缺值誠實化」通則，供 severity 等照抄）。
- confidence_reason＝reserved 窗現成（§443）→ C5。
- B 側送達 emit 無裸 enum（§8.2/§8.10）→ C6。
- name_match_ambiguous＝edge 面 confidence=low（§291/§357 U1），升巢狀 Signal（I4 約束＝payload 必∈contrasts→confidence 作巢狀欄）→ C7。

**檔案數量判斷：**
- **plan＝單檔**：6 task 線性相依（地基→A 側 foundation→A 側缺值→B 側 emit→B 側 edge→gate），拆檔斷敘事（S1/S2/S3 已立此則）。
- **`confidence_membrane.py` 獨立檔**：照 `{domain}_membrane.py` 慣例（S1/S2/S3）；安置 `core/reading`（confidence 最權威產地＝L1）。
- **confidence Signal 留 primitive.py 不動**：S4 純復用 S0 `SignalPosition`/`NoisePosition`，不擴 primitive。

**Preconditions（執行前確認，非 task）：**
- 換 worktree 後先 `pip install -e ./the_door`（本 worktree 已裝）。
- pytest cwd＝內層 `the_door/`；Windows cp950 前置 `PYTHONUTF8=1`。
- 基線＝S3 merged 後 **1509 passed**。本 plan：confidence_membrane 純加法；model 型別放寬；schema nullable+desc＝放寬；缺值/emit/edge 形狀變更由 characterization＋既有測試見證。

**已驗事實（寫 plan 前 spike，2026-06-06；file:line 見 spec §2）：**
- confidence 軸值集散落：`VALID_CONFIDENCE` set（`snapshot_write_tool:15`、**無序**）＋ 3 schema enum（`l1-output:62`/`snapshot:25,42`/`l2-output:44,125`）＋ ~6 行註解 → S4 收斂為 `CONFIDENCE_CONTRASTS`（全序）。
- **缺值自鑄點**（病灶）：`batch_reader:190,345`（L1）／`l2_generator:165,186`＋`260,281`（L2 兩 parse 路徑，🟢 驗）／`snapshot_store:432`（BlockSummary 反序列化向後相容）皆 `.get("confidence","medium")`。
- **欄序**（🟢 驗）：`Feature.confidence`(`analysis.py:16`，在 source_nodes 前)／`FeatureSummary.confidence`(`snapshot.py:32`，在 trigger_description 前)＝**required-position**→純放寬型別無 default；`L2Module`(`:137`，在 source_nodes 後)／`Anomaly`(`:159`，在 explanation 後)／`BlockSummary`(`snapshot.py:45`，末欄)＝**defaulted-position**→`default=None`（誠實未評估、非自鑄 medium）。
- **emit 點**（LLM-facing）：`analyze_tool:82`（L1 features，含 `confidence_marker:84`＝mermaid 視覺、**保留**）／`analyze_changes_tool:61`（`_feature_to_json`，含 confidence_reason）。
- **edge**：`edge_projection:58` `low_confidence_ambiguous` raw `{caller:{method:count}}` 未升 Signal；I4（`primitive.py:108`）強制 SignalPosition payload∈contrasts → confidence 作**巢狀欄**（payload="low"）、caller/methods/cardinality 留載體 dict。
- **既有測試附帶影響**（🟢 grep）：
  - edge 形狀：`tests/unit/core/llm/test_edge_projection.py:36,51,71,85,91`／`test_edge_projection_membrane.py:27`／`tests/integration/test_batch_reader_projection.py:57,106` 斷言 `low_confidence_ambiguous == {caller:{method:count}}`（raw dict）→ **Task 5 flip 為 list-of-巢狀 confidence**（有意契約變更）。
  - 缺值：無既有「缺 confidence→medium」pin 測 → **Task 3 新建** characterization pin→flip。
  - 構造點顯式傳 confidence（`test_e2e_ui_server:94`／`test_snapshot_contract:43`／`test_snapshot_patch:39`／`test_pipeline_orchestrator_cache:116`／`test_batch_reader:97`）→ default 改 None **不破**（皆顯式）。
  - emit：plan 執行時 grep `analyze_tool`/`analyze_changes` 既有測有無斷言裸 confidence，有則 Task 4 同步。
- 無循環 import：`confidence_membrane`→`core.membrane`（單向）；consumers→`confidence_membrane`。

---

## File Structure

| 檔案 | 職責 | 動作 |
|---|---|---|
| `src/the_door/core/reading/confidence_membrane.py` | `CONFIDENCE_CONTRASTS`＋4 工廠＋schema fragment | Create |
| `tests/unit/core/reading/test_confidence_membrane.py` | C1/C3/C5＋fragment＋C2-set | Create |
| `src/the_door/mcp/tools/snapshot_write_tool.py` | `VALID_CONFIDENCE` 衍生＋input enum per-value desc | Modify |
| `src/the_door/mcp/tools/snapshot_patch_tool.py` | input confidence per-value desc（若有 confidence input） | Modify |
| `src/the_door/models/analysis.py`、`src/the_door/models/snapshot.py` | confidence `str→str\|None`（型別/​default per §3.4） | Modify |
| `schemas/l1-output.schema.json`、`schemas/snapshot.schema.json`、`schemas/l2-output.schema.json` | confidence → `confidence_schema_fragment`（nullable+per-value desc） | Modify |
| `src/the_door/core/diff/snapshot_store.py`、`src/the_door/core/extraction/structure_serializer.py`、`src/the_door/core/pipeline/analyze_pipeline.py` | confidence read/write None-容忍 | Modify |
| `tests/unit/core/diff/test_snapshot_contract.py` | confidence=None round-trip＋schema parity（C2） | Modify |
| `src/the_door/core/reading/batch_reader.py`、`src/the_door/core/ui/l2_generator.py` | parse `.get("confidence")`（移 `,"medium"`） | Modify |
| `tests/unit/core/reading/test_batch_reader.py` | characterization：缺 confidence→None（pin→flip） | Modify |
| `src/the_door/mcp/tools/analyze_tool.py`、`src/the_door/mcp/tools/analyze_changes_tool.py` | confidence 經 `confidence_element` 投影 | Modify |
| `tests/unit/mcp/test_analyze_*` | emit 膜投影 characterization | Modify/Create |
| `src/the_door/core/llm/edge_projection.py`、`src/the_door/core/llm/prompts.py` | name_match_ambiguous 升巢狀 confidence Signal＋教學同步 | Modify |
| `tests/unit/core/llm/test_edge_projection*.py`、`tests/integration/test_batch_reader_projection.py` | edge 形狀 flip（巢狀 confidence） | Modify |

---

### Task 1: confidence 膜詞彙＋有序單一來源（地基）

**理論錨：** confidence＝B 側全序 Signal（§181）＋缺值退 indeterminate（§8.13）＝C1/C3/C5。**純加法＋1 consumer 衍生（`VALID_CONFIDENCE`）。**

**Files:**
- Create: `src/the_door/core/reading/confidence_membrane.py`、`tests/unit/core/reading/test_confidence_membrane.py`
- Modify: `src/the_door/mcp/tools/snapshot_write_tool.py`（`VALID_CONFIDENCE = set(CONFIDENCE_CONTRASTS)`）

- [ ] **Step 1: Write the failing test**

建立 `tests/unit/core/reading/test_confidence_membrane.py`（必要時建 `tests/unit/core/reading/__init__.py`）：

```python
"""S4 confidence 膜：全序 Signal / 缺值退 Noise / reserved。"""
from the_door.core.reading.confidence_membrane import (
    CONFIDENCE_CONTRASTS, confidence_element, confidence_reason_element,
    confidence_schema_fragment, confidence_signal,
)


def test_contrasts_full_order():
    assert CONFIDENCE_CONTRASTS == ("high", "medium", "low")   # C2 全序


def test_value_to_signal():
    sig = confidence_signal("low")
    assert sig.contrasts == ("high", "medium", "low") and sig.gloss      # C1


def test_element_value_is_signal():
    j = confidence_element("high").to_json()
    assert j["value"] == "high" and j["position"]["kind"] == "signal"
    assert j["position"]["contrasts"] == ["high", "medium", "low"]


def test_element_none_retreats_to_noise_indeterminate():
    j = confidence_element(None).to_json()                                # C3
    assert j["position"]["kind"] == "noise"
    assert j["position"]["gap_kind"] == "indeterminate"
    assert j["position"]["aggregated"] is False


def test_reason_is_reserved():
    j = confidence_reason_element("節點明確").to_json()                    # C5
    assert j["position"] == {"kind": "reserved"} and j["value"] == "節點明確"


def test_schema_fragment_oneof_const_plus_null():
    frag = confidence_schema_fragment()
    consts = [o["const"] for o in frag["oneOf"] if "const" in o]
    assert consts == ["high", "medium", "low"]                            # C2 parity 基礎
    assert any(o.get("type") == "null" for o in frag["oneOf"])            # nullable
```

並加 `tests/unit/core/reading/test_confidence_membrane.py` 的 C2-set 斷言：
```python
def test_valid_confidence_derived_from_single_source():
    from the_door.mcp.tools.snapshot_write_tool import VALID_CONFIDENCE
    assert VALID_CONFIDENCE == set(CONFIDENCE_CONTRASTS)                  # C2 單一來源
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/reading/test_confidence_membrane.py -q`
Expected: FAIL — `ModuleNotFoundError: ... confidence_membrane`。

- [ ] **Step 3: Write minimal implementation**

建立 `src/the_door/core/reading/confidence_membrane.py`＝**spec §3.1 的 exact code 全文**（`CONFIDENCE_CONTRASTS`＋`confidence_signal`/`confidence_element`/`confidence_reason_element`/`confidence_schema_fragment`）。
`snapshot_write_tool.py:15`：`VALID_CONFIDENCE = set(CONFIDENCE_CONTRASTS)`（import from `the_door.core.reading.confidence_membrane`）。

> 不重貼（spec §3.1 唯一來源）。關鍵不變式：None→NoisePosition(indeterminate)；值→SignalPosition(contrasts 全序)。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/reading/ tests/unit/mcp/ -q`
Expected: PASS（confidence_membrane 全綠＋snapshot_write_tool 仍綠）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/core/reading/confidence_membrane.py tests/unit/core/reading/ src/the_door/mcp/tools/snapshot_write_tool.py
git commit -m "feat(confidence-membrane): confidence axis vocab + ordered single source (C1/C2/C3/C5)

CONFIDENCE_CONTRASTS 全序唯一來源；值->SignalPosition、缺值->NoisePosition(indeterminate)、
reason->Reserved。VALID_CONFIDENCE 衍生（消無序 set 副本）。承 S1 樣板、純加法。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 模型誠實 ＋ schema 就緒（confidence nullable、單一來源 parity）

**理論錨：** 缺值須能誠實落盤（spec §3.4/§3.7）；消「自鑄假 medium」（§0/C3）。**型別放寬/widening。** 本 task 不改 parse（Task 3）、不改 emit（Task 4/5），故 confidence 暫仍由現行 `.get(...,"medium")` 填（Task 3 才改），既有測試僅需 default 改 None 的構造點同步（grep 驗皆顯式、不破）。

**Files:**
- Modify: `models/analysis.py`、`models/snapshot.py`、`schemas/l1-output.schema.json`、`schemas/snapshot.schema.json`、`schemas/l2-output.schema.json`、`core/diff/snapshot_store.py`、`core/extraction/structure_serializer.py`、`core/pipeline/analyze_pipeline.py`、`mcp/tools/snapshot_write_tool.py`、`mcp/tools/snapshot_patch_tool.py`
- Test: `tests/unit/core/diff/test_snapshot_contract.py`（confidence=None round-trip＋schema const parity）

- [ ] **Step 1: Write the failing test**

在 `tests/unit/core/diff/test_snapshot_contract.py` 加（沿用既有 helper）：

```python
def test_confidence_nullable_roundtrip_and_schema_parity(tmp_path):
    """confidence=None（未評估）通過 fail-closed schema 並 round-trip；schema const 與單一來源 parity。"""
    from dataclasses import replace
    from the_door.core.reading.confidence_membrane import CONFIDENCE_CONTRASTS
    from the_door.models import FeatureSummary

    store = _store(tmp_path)
    snap = replace(_minimal_snapshot(), l1_snapshot={"feat-x": FeatureSummary(
        feature_id="feat-x", label="L", description="D",
        source_node_count=0, confidence=None)})       # 未評估
    data = store._serialize_snapshot(snap)
    jsonschema.validate(data, _get_snapshot_schema(), cls=_V)         # confidence=null 須過
    back = store._deserialize_snapshot(data)
    assert back.l1_snapshot["feat-x"].confidence is None
    # schema const == 單一來源（C2 schema parity）
    feat_schema = _get_snapshot_schema()["properties"]["l1_snapshot"]["additionalProperties"]["properties"]
    consts = [o["const"] for o in feat_schema["confidence"]["oneOf"] if "const" in o]
    assert consts == list(CONFIDENCE_CONTRASTS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_contract.py::test_confidence_nullable_roundtrip_and_schema_parity -q`
Expected: FAIL — confidence=None 不符 `enum`（無 null）／schema 仍是 enum 無 oneOf const。

- [ ] **Step 3: Write minimal implementation**

- `models/analysis.py`／`models/snapshot.py`＝**spec §3.4 exact**：`Feature`/`FeatureSummary.confidence: str|None`（required-position 無 default）；`L2Module`/`Anomaly`/`BlockSummary.confidence: str|None = None`（defaulted-position）。
- 3 schema（`l1-output:62`/`snapshot:25,42`/`l2-output:44,125`）confidence → `confidence_schema_fragment()` 的內容（oneOf+const+description+null）。**nullable＝向後相容**（舊 enum 值仍過）。
- `snapshot_write_tool:46,89`／`snapshot_patch_tool` input confidence → per-value desc（**非 null 子集**＝input 寫嚴必填，spec §3.3）；保留 `required`／`:128` 校驗。
- `snapshot_store`（read confidence None-容忍：FeatureSummary `fdata["confidence"]` 已容 null 值；BlockSummary `:432` 見 Task 3）／`structure_serializer`／`analyze_pipeline`：confidence 序列化容 None。

> 不重貼（spec §3.4/§3.7 唯一來源）。schema const 與 `CONFIDENCE_CONTRASTS` 同源＝parity test 把關。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/diff/ tests/unit/core/extraction/ tests/unit/mcp/ tests/unit/core/reading/ -q`
Expected: PASS（confidence=None round-trip＋parity 綠；既有構造點顯式傳值不破）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/models/analysis.py src/the_door/models/snapshot.py schemas/l1-output.schema.json schemas/snapshot.schema.json schemas/l2-output.schema.json src/the_door/core/diff/snapshot_store.py src/the_door/core/extraction/structure_serializer.py src/the_door/core/pipeline/analyze_pipeline.py src/the_door/mcp/tools/snapshot_write_tool.py src/the_door/mcp/tools/snapshot_patch_tool.py tests/unit/core/diff/test_snapshot_contract.py
git commit -m "feat(confidence-model): confidence nullable + schema single-source parity (foundation for honest missing)

confidence: str|None（None=未評估、不自鑄 medium）；3 schema -> confidence_schema_fragment
（oneOf+const+desc+null、向後相容）；input schema per-value desc（寫嚴必填）；persistence None-容忍。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 閉集 enum 缺值誠實化（A 側、生產端、S4 通則）

**理論錨：** 缺值不自鑄 default（§8.13 通則）＝C4；S4 立通則供 severity 等照抄。characterization 先行（§9.4）——**新建** pin 現狀「缺→medium」→ flip。依賴 Task2（schema 容 None，否則 parse None 落盤撞 fail-closed）。

**Files:**
- Modify: `core/reading/batch_reader.py`、`core/ui/l2_generator.py`、`core/diff/snapshot_store.py`
- Test: `tests/unit/core/reading/test_batch_reader.py`（characterization）

- [ ] **Step 1: Write characterization test pinning CURRENT (minting) behavior**

在 `tests/unit/core/reading/test_batch_reader.py` 加（沿用該檔既有 `mock_llm_with_responses`＋`make_structure` fixture，🟢 驗 `:61,79`；feature dict **省略 `confidence` 鍵**）：

```python
def test_missing_confidence_currently_mints_medium(self, mock_llm_with_responses):
    """CHARACTERIZATION（現狀＝病灶）：LLM 省略 confidence → 靜默自鑄 medium。"""
    mock = mock_llm_with_responses({
        "features": [{
            "feature_id": "feat-x", "label": "X", "description": "D",
            "trigger": "user_action", "trigger_description": "T",
            # confidence 鍵刻意省略
            "confidence_reason": "R", "source_nodes": ["app.py::f"],
        }],
        "feature_relations": [], "unclassified_nodes": [], "infrastructure_nodes": [],
    })
    structure = make_structure({1: ["app.py::f"]})
    result = asyncio.run(BatchReader(llm_provider=mock, structure=structure).read())
    assert result.l1_output.features[0].confidence == "medium"   # 現狀＝自鑄
```

- [ ] **Step 2: Run characterization to verify it PASSES (pins current)**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/reading/test_batch_reader.py -q`
Expected: PASS（釘住現狀＝缺→medium）。

- [ ] **Step 3: Flip to honest assertion (now failing)**

把上面測試 flip：最後一行改 `assert result.l1_output.features[0].confidence is None`（缺值不自鑄）。Run → Expected: FAIL（現行仍鑄 medium）。

- [ ] **Step 4: Write minimal implementation**（spec §3.5）

- `batch_reader.py:190,345`：`confidence=feat_data.get("confidence")`（移 `, "medium"`）。
- `l2_generator.py:165,186`＋`260,281`：`m.get("confidence")`／`a.get("confidence")`（移 `, "medium"`；**grep 全 `.get("confidence",` 點**確認無遺）。
- `snapshot_store.py:432`：`confidence=bdata.get("confidence")`（移 `, "medium"`＝舊快照無 confidence→None 誠實）。

> 不重貼（spec §3.5 唯一來源）。缺值→None＝事實層誠實，emit（Task 4）None→Noise。

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/reading/ tests/unit/core/ui/ tests/unit/core/diff/ -q`
Expected: PASS（缺值→None＋既有給值路徑不變）。

- [ ] **Step 6: Commit**

```bash
git add src/the_door/core/reading/batch_reader.py src/the_door/core/ui/l2_generator.py src/the_door/core/diff/snapshot_store.py tests/unit/core/reading/test_batch_reader.py
git commit -m "feat(confidence-honesty): missing confidence -> None, not minted medium (C4, closed-enum 通則)

生產端缺值不自鑄 default（batch_reader L1 / l2_generator L2 x2 / snapshot_store 反序列化）；
S4 立『閉集 enum 缺值誠實化』通則，severity 等照抄。characterization-witnessed.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: emit 膜投影（B 側送達：analyze_tool / analyze_changes）

**理論錨：** B 側送達 emit 無裸 enum（§8.2/§8.10）＝C6；None→Noise（§8.13）。characterization 先行。依賴 Task1（confidence_element）＋Task3（confidence 可能 None）。

**Files:**
- Modify: `mcp/tools/analyze_tool.py`、`mcp/tools/analyze_changes_tool.py`
- Test: `tests/unit/mcp/test_analyze_tool*`／`test_analyze_changes_tool*`（既有更新或新建 emit 膜投影測）

- [ ] **Step 1: Write the failing test**

新建/更新 emit 測（monkeypatch reader → 受控 features，含一筆 confidence=None）：

```python
def test_analyze_tool_confidence_membrane_projection(monkeypatch, tmp_path):
    """C6：analyze_tool features confidence 經膜投影（值→signal、None→noise）、無裸 enum。"""
    # monkeypatch BatchReader.read → L1Output(features=[Feature(confidence="high"...), Feature(confidence=None...)])
    out = asyncio.run(analyze_tool.execute({"codebase_path": "."}))
    feats = out["l1"]["features"]
    kinds = {f["confidence"]["position"]["kind"] for f in feats}
    assert kinds == {"signal", "noise"}                 # 值→signal、None→noise
    assert all(not isinstance(f["confidence"], str) for f in feats)   # 無裸 enum
```

（`analyze_changes_tool` 同型：`_feature_to_json` confidence 走膜。）

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_analyze_tool.py -q`（或對應檔）
Expected: FAIL（confidence 仍裸 enum/None）。

- [ ] **Step 3: Write minimal implementation**（spec §3.6）

- `analyze_tool.py:82`：`"confidence": confidence_element(f.confidence).to_json()`；`confidence_marker`（mermaid 視覺）**保留不動**（人類面 out）。
- `analyze_changes_tool.py:61`（`_feature_to_json`）：`"confidence": confidence_element(fs.confidence).to_json()`；`confidence_reason` 走 `confidence_reason_element(...).to_json()`（reserved）或維持既有 defensive 字串（至少 confidence 走膜）。
- import `from the_door.core.reading.confidence_membrane import confidence_element[, confidence_reason_element]`。

> 不重貼（spec §3.6 唯一來源）。

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/ -q`
Expected: PASS（emit 膜投影＋其餘 mcp 測仍綠）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/mcp/tools/analyze_tool.py src/the_door/mcp/tools/analyze_changes_tool.py tests/unit/mcp/
git commit -m "feat(confidence-emit): membrane projection at analyze_tool/analyze_changes (C6)

L1/diff feature confidence -> confidence_element（值=signal、None=noise indeterminate）；
無裸 enum。confidence_marker（mermaid 視覺）保留=人類面。characterization-witnessed.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: edge name_match_ambiguous 升巢狀 confidence Signal（B 側 edge 面）

**理論錨：** edge 面 confidence＝§291/§357 U1；I4（`primitive.py:108`）強制 SignalPosition payload∈contrasts → confidence 作**巢狀欄**（payload="low"）、caller/methods/cardinality 留載體＝C7。characterization 先行（flip S2 既有 raw 桶測）。依賴 Task1。

**Files:**
- Modify: `core/llm/edge_projection.py`、`core/llm/prompts.py`
- Test: `tests/unit/core/llm/test_edge_projection.py`、`test_edge_projection_membrane.py`、`tests/integration/test_batch_reader_projection.py`（flip）

- [ ] **Step 1: Flip the failing test**

把既有 `low_confidence_ambiguous == {caller:{method:count}}` 斷言（`test_edge_projection.py:36,71,85,91`／`test_edge_projection_membrane.py:27`／`test_batch_reader_projection.py:57,106`）改為巢狀 confidence list 形狀：

```python
# 例（test_edge_projection_membrane.py:27 區，輸入 a→write ×2 ambiguous）：
assert residue["low_confidence_ambiguous"] == [
    {
        "caller": "a",
        "methods": {"write": 2},                 # 基數保留
        "cardinality": 2,
        "confidence": {"value": "low", "position": {
            "kind": "signal",
            "contrasts": ["high", "medium", "low"],
            "gloss": <gloss>, "preconditions": [], "consequences": [], "co_requires": [],
        }},
    }
]
```
（空桶 `{}`→`[]`；exact gloss 由 `confidence_signal("low").gloss`。）

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/llm/test_edge_projection.py tests/unit/core/llm/test_edge_projection_membrane.py tests/integration/test_batch_reader_projection.py -q`
Expected: FAIL（現行 raw dict、非巢狀 list）。

- [ ] **Step 3: Write minimal implementation**（spec §3.6 edge 區）

`edge_projection.py:53-62` residue 的 `low_confidence_ambiguous` 由 raw dict 改 **spec §3.6 的 list comprehension**（每 caller 一 dict：caller/methods〔排序、基數保留〕/cardinality/`confidence: confidence_element("low").to_json()`）。import `confidence_element`。
`prompts.py:60,67` 教學同步：`low_confidence_ambiguous` 描述改「list of {caller, methods, cardinality, confidence(signal)}」（confidence 軸結構化巢狀欄、非 raw 桶）。

> 不重貼（spec §3.6 唯一來源）。**復用 S2 座標、基數保留、confidence "low" 巢狀欄 I4 合法。**

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/llm/ tests/integration/test_batch_reader_projection.py -q`
Expected: PASS（edge 升巢狀 confidence Signal＋S2 indeterminate 殘餘仍綠）。

- [ ] **Step 5: Commit**

```bash
git add src/the_door/core/llm/edge_projection.py src/the_door/core/llm/prompts.py tests/unit/core/llm/test_edge_projection.py tests/unit/core/llm/test_edge_projection_membrane.py tests/integration/test_batch_reader_projection.py
git commit -m "feat(confidence-edge): name_match_ambiguous -> nested confidence Signal (C7)

edge 面 confidence=low 升巢狀 Signal（payload=low I4 合法）+caller/methods/cardinality 載體；
復用 S2 座標、基數保留。prompt 教學同步。承 §291/§357 U1（命名拆分碼裡長出的軸）。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 全套件回歸驗收 ＋ 連貫性

**Files:** （無；驗收 gate）

- [ ] **Step 1: confidence + membrane + 持久化 + mcp/cli/llm 相關全測**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/reading/ tests/unit/core/membrane/ tests/unit/core/diff/ tests/unit/core/extraction/ tests/unit/core/llm/ tests/unit/core/ui/ tests/unit/mcp/ tests/integration/ -q`
Expected: 全綠（含 S0/S1/S2/S3 membrane 連貫＝地基未鬆動）。

- [ ] **Step 2: 全測零回歸**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest -q`
Expected: 1509（S3 基線）＋新測、零 fail。**唯一「變更」＝Task 3 缺值 characterization＋Task 4/5 emit/edge 形狀有意更新＋Task 2 schema nullable+desc**；其餘純加法。若非預期 fail（如某處仍讀裸 confidence 或假設非 None）→ 停下檢查未盤點消費者。

- [ ] **Step 3:（無新 commit；驗收通過即 S4 完成）**

S4 完成 → ff-merge main（逐刀本地 merge、不主動 push）→ 進 S5（scope）spec。起前重跑種子檔 §9.2 理論重錨、讀 S1 spec §5＋S2 spec §3.3＋本刀 spec §3.1（全序 Signal 樣板）／§5（缺值通則）／§7（對 S5 回驗）。

---

## Self-Review

**1. Spec coverage：**
- spec §3.1 confidence_membrane（CONTRASTS+4 工廠+fragment）→ Task 1 ✓
- spec §3.2 單一來源收斂（VALID_CONFIDENCE+schema parity）→ Task 1（set）+Task 2（schema）✓
- spec §3.3 input schema 寫嚴 → Task 2 ✓
- spec §3.4 模型 nullable（欄序 default per §3.4）→ Task 2 ✓
- spec §3.5 缺值誠實化（4 parse 點）→ Task 3 ✓
- spec §3.6 emit 投影（analyze）+ edge 升 Signal → Task 4（analyze）+Task 5（edge）✓
- spec §3.7 schema 補完+persistence → Task 2 ✓
- spec §4 不變量 C1/C2(T1)、C3(T1)、C4(T3)、C5(T1)、C6(T4)、C7(T5) ✓
- spec §6 characterization 先行 → Task 3（pin→flip）+Task 5（flip edge）✓
- out（severity-default→vulnerability／人類面／provenance/scope/diff_state）→ 正確不在本 plan ✓

**2. Placeholder scan：** Task 3 Step1/Task 4 Step1 的 fixture「exact 沿用既有」非佔位＝明確指向既有 helper（`test_batch_reader.py` parse fixture／analyze monkeypatch），plan 執行時對齊（與 S3 plan「exact 由實作者依現有行格式落」同精度）。其餘 step 含完整 test code/骨架＋exact 指令＋預期輸出；impl 引 spec §3.x。

**3. Type consistency：** `CONFIDENCE_CONTRASTS:tuple`／`confidence_signal(str)->SignalPosition`／`confidence_element(str|None)->MembraneElement`／`confidence: str|None`／emit→`confidence_element(...).to_json()`／edge confidence 巢狀欄 payload="low"——跨 Task 1-5 一致 ✓。

**4. 依賴順序：** Task1（membrane）→ Task4/5（emit 用 confidence_element）；Task2（schema 容 None）→ Task3（parse 產 None，schema 就緒不撞 fail-closed）；Task3（confidence 可能 None）→ Task4（emit 投影 None）。**schema 就緒（T2）先於 parse 產 None（T3）＝無 fail-closed 撞牆**（同 S3 T2 先於 T4）。Task5（edge）獨立於 T3/T4、僅依 T1。無逆序 ✓。

**5. characterization-first（契約變更安全網）：** Task 3 新建 pin 缺值→medium 現狀（green）→ flip None（red）→ impl（green）；Task 5 flip S2 既有 raw 桶測（red）→ impl 巢狀 confidence（green）；Task 4 新建 emit 測（red：裸 enum）→ 投影（green）。動 parse/emit/edge 契約前皆先釘。**既有測試附帶影響（grep 證）：edge 6+ 處斷言 flip（Task 5 有意契約變更）；構造點顯式傳 confidence（default→None 不破）。**

**6. 理論對照（使用者要求「對照理論原則」）：** 每 task 理論錨已標；核心對照——C1/C2 全序 Signal＝§181 三主軸；C3/C4 缺值退 indeterminate＝§8.13 通則（S4 立閉集 enum 缺值通則、severity 照抄）；C5 reason reserved＝§443；C6 emit 無裸 enum＝§8.2/§8.10 B 側送達；C7 edge 升巢狀 Signal＝§291/§357 U1（I4 約束下 confidence 作巢狀欄）。**severity-default 軸正交剔除（§181）＝守一刀一軸。**
