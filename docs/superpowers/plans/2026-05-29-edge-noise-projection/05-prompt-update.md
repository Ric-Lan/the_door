# Task 05: L1 Prompt Update

**Files:**
- Modify: `the_door/src/the_door/core/llm/prompts.py` (lines 37-46 resolution section)
- Test: `the_door/tests/unit/core/llm/test_prompt_resolution_section.py` (new)

**Goal:** 把既有「resolution 標籤」說明區塊改成新版四項說明 + 教 LLM 看 `aggregate_call_hints` 欄位且不可寫成依賴關係。

**Depends on:** Task 04（payload shape 已固定為含 `aggregate_call_hints`）。

---

- [ ] **Step 1: Write the failing prompt-content test**

Create `the_door/tests/unit/core/llm/test_prompt_resolution_section.py`:

```python
"""L1 prompt teaches LLM about resolution labels + aggregate_call_hints."""
from the_door.core.llm.prompts import L1_FEATURE_EXTRACTION_PROMPT


def test_prompt_does_not_list_ambiguous_as_per_edge_label():
    """The prompt may explain ambiguous-edges-are-aggregated in prose,
    but must NOT include name_match_ambiguous as a bulleted per-edge label
    the LLM is told to interpret. Heuristic: it shouldn't appear with
    backtick formatting like other per-edge labels (`scope_rule` etc.)."""
    text = L1_FEATURE_EXTRACTION_PROMPT
    assert "`name_match_ambiguous`" not in text


def test_prompt_explains_aggregate_call_hints():
    """Prompt teaches LLM what aggregate_call_hints means."""
    text = L1_FEATURE_EXTRACTION_PROMPT
    assert "aggregate_call_hints" in text


def test_prompt_forbids_dependency_inference_from_hints():
    """Prompt explicitly forbids treating hint method names as dependencies."""
    text = L1_FEATURE_EXTRACTION_PROMPT
    # Loose contract — exact wording can evolve, but the prohibition must be present.
    assert "不可" in text or "禁止" in text or "不要" in text
    assert "依賴" in text


def test_prompt_still_lists_three_resolution_labels_llm_sees():
    """LLM-facing resolutions after projection are exactly:
    scope_rule, import_alias, name_match."""
    text = L1_FEATURE_EXTRACTION_PROMPT
    for label in ("scope_rule", "import_alias", "name_match"):
        assert label in text


def test_prompt_no_longer_lists_skipped_dynamic_as_per_edge_label():
    """skipped_dynamic edges are also folded into hints — should not appear
    as a per-edge label in the prompt's resolution explanation section."""
    text = L1_FEATURE_EXTRACTION_PROMPT
    # skipped_dynamic may still be mentioned in passing (e.g. in the hints
    # explanation), but should not appear as a standalone bulleted resolution
    # label the LLM is told to interpret per-edge.
    # Heuristic: it should not appear with backticks like `skipped_dynamic`
    # which is the existing per-label formatting.
    assert "`skipped_dynamic`" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && python -m pytest tests/unit/core/llm/test_prompt_resolution_section.py -v`

Expected: most FAIL — current prompt still describes `skipped_dynamic` per-edge and has no `aggregate_call_hints` section.

- [ ] **Step 3: Update the prompt resolution section**

Edit `the_door/src/the_door/core/llm/prompts.py`. Find the section (lines 37-46):

```
## 關聯邊 (edges) 的 resolution 標籤

你會收到的節點之間有 `edges`，每條邊都帶 `resolution` 標籤，用來告訴你這條邊的信心等級：

- `scope_rule`：透過 scope 規則明確解到（同檔 / 同套件）。**高信心**，可以放心採用為事實依據撰寫 description。
- `import_alias`：透過 import 別名解到目標。**高信心**，同上可採用。
- `name_match`：純粹靠裸名匹配找到，可能是程式內多個同名節點之一。**低信心，僅供參考**。若描述會因為這條邊的不確定性而產生分歧，**寧可不提**這條關聯。
- `skipped_dynamic`：偵測到動態 dispatch context（例如 Ruby method_missing、Python __getattr__、reflection）。目的端候選來自裸名匹配，**不可作為事實依據**。**不要對這條邊的目標做任何斷言**。

撰寫 description 時，優先以 `scope_rule` / `import_alias` 高信心邊為依據；對 `name_match` 持保守態度；對 `skipped_dynamic` 不提即可。
```

Replace with:

```
## 關聯邊 (edges) 的 resolution 標籤

你會收到的節點之間有 `edges`，每條邊都帶 `resolution` 標籤，用來告訴你這條邊的信心等級：

- `scope_rule`：透過 scope 規則明確解到（同檔 / 同套件）。**高信心**，可以放心採用為事實依據撰寫 description。
- `import_alias`：透過 import 別名解到目標。**高信心**，同上可採用。
- `name_match`：裸名匹配找到，候選數已在低門檻內。**低信心**，撰寫 description 時持保守態度，若會造成模糊就不要提。

你不會在 `edges` 內看到「高候選量裸名匹配」或「動態 dispatch」邊 — 它們已在輸入端被聚合成 `aggregate_call_hints` 欄位。

## `aggregate_call_hints` 欄位

payload 內額外提供：

```
"aggregate_call_hints": {
  "feat-x-caller-node-id": ["write", "get", "handle"]
}
```

這代表 caller 端呼叫了若干「無法精確定位的方法名」（包含高 fanout 與動態 dispatch 來源）。

撰寫 description 時的紀律：
- **不可** 把 hint 內的方法名當成「呼叫了某 feature」的依據
- **不可** 因為 hint 內有某方法名，就在 `feature_relations` 加上 `depends_on`
- 若 description 必須提到，限定為「執行了一些（寫入 / 讀取 / 處理）動作」這種泛稱
- 寧可不提，不要勉強寫出帶有不確定性的依賴敘述

撰寫 description 時，優先以 `scope_rule` / `import_alias` 高信心邊為依據；對 `name_match` 持保守態度；對 `aggregate_call_hints` 不寫成依賴。
```

- [ ] **Step 4: Run prompt tests to verify pass**

Run: `cd the_door && python -m pytest tests/unit/core/llm/test_prompt_resolution_section.py -v`

Expected: all 5 tests PASS.

- [ ] **Step 5: Run full suite**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected:
- All previous tests pass.
- ⚠ If any pre-existing test asserts the old prompt text verbatim, update those assertions.

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/llm/prompts.py \
        the_door/tests/unit/core/llm/test_prompt_resolution_section.py
git commit -m "feat(llm): teach L1 prompt about aggregate_call_hints + projected edges"
```
