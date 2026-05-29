# Task 03: EdgeBuilder Fanout Threshold

**Files:**
- Modify: `the_door/src/the_door/core/extraction/edge_builder.py`（加 `FANOUT_THRESHOLD` 常數；改 `_resolve()` 兩處 fallback）
- Test: `the_door/tests/integration/extraction/test_edge_fanout_threshold.py` (new)

**Goal:** 在 `_resolve()` Step 4 fallback 加 `FANOUT_THRESHOLD` 檢查 — 候選數超過閾值時把 resolution 標 `name_match_ambiguous`。**自動同時涵蓋 calls 與 extends 邊**（`_detect_extends` 也呼叫同一個 `_resolve`）。

**Depends on:** Task 01。

---

## EdgeBuilder lifecycle 重要說明（必讀）

`EdgeBuilder.__init__(self)` **不收任何參數**。`_name_to_ids` 與 `_node_map` 是空 dict，**只在 `build_edges(nodes, trees, configs)` 被呼叫時才填入**（見 `edge_builder.py:69-72`）。

故測試 `_resolve()` 行為必須**手動 inject** lookup state，不可只 `EdgeBuilder(nodes)`（會 TypeError）也不可只 `EdgeBuilder()` 就呼 `_resolve`（lookup 空，永遠回 `[]`）。

---

## Design

```python
FANOUT_THRESHOLD = 3  # default; tuned by dogfood histogram (Task 06)

# _resolve() Step 4 (current ~line 410):
matches = self._name_to_ids.get(name, [])
return [(m, "name_match") for m in matches]

# becomes:
matches = self._name_to_ids.get(name, [])
if not matches:
    return []
res = "name_match_ambiguous" if len(matches) > FANOUT_THRESHOLD else "name_match"
return [(m, res) for m in matches]
```

**Important:** Step 1 (`skipped_dynamic` early-out) does NOT get the threshold — projection layer (Task 02) handles dynamic fanout via aggregate hints.

---

- [ ] **Step 1: Write the failing integration test**

Create `the_door/tests/integration/extraction/test_edge_fanout_threshold.py`:

```python
"""EdgeBuilder marks high-fanout name_match edges as name_match_ambiguous.

These tests probe `_resolve()` directly by hand-injecting the lookup
state that `build_edges()` would normally populate. This isolates the
threshold logic from tree-sitter parsing.
"""
from the_door.core.extraction.edge_builder import (
    EdgeBuilder, FANOUT_THRESHOLD, ScopeContext,
)
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS
from the_door.models import ASTNode


def _node(node_id: str, name: str, file: str = "x.py",
          ntype: str = "function") -> ASTNode:
    return ASTNode(node_id=node_id, type=ntype, name=name, file=file,
                   language="python")


def _builder_with(nodes: list[ASTNode]) -> EdgeBuilder:
    """Construct an EdgeBuilder and hand-populate its lookup state.

    Mirrors what `build_edges()` does at lines 69-72.
    """
    builder = EdgeBuilder()
    builder._name_to_ids = {}
    builder._node_map = {}
    for n in nodes:
        builder._name_to_ids.setdefault(n.name, []).append(n.node_id)
        builder._node_map[n.node_id] = n
    return builder


def _ctx(current_file: str = "external.py") -> ScopeContext:
    """Context that forces Step 4 fallback (scope_rule won't apply)."""
    return ScopeContext(
        current_file=current_file,
        import_aliases={},
        caller_class=None,
    )


def test_threshold_default_is_three():
    """Anchor test: dogfood (Task 06) may tune this — keep test in sync."""
    assert FANOUT_THRESHOLD == 3


def test_low_fanout_keeps_name_match():
    """When candidates ≤ threshold, resolution stays name_match."""
    nodes = [
        _node("a.py::shared", "shared", "a.py"),
        _node("b.py::shared", "shared", "b.py"),
    ]  # 2 candidates < threshold 3
    builder = _builder_with(nodes)
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    resolved = builder._resolve("shared", _ctx(), rules)
    assert len(resolved) == 2
    assert all(res == "name_match" for _nid, res in resolved)


def test_high_fanout_marks_ambiguous():
    """When candidates > threshold, resolution becomes name_match_ambiguous."""
    nodes = [_node(f"f{i}.py::shared", "shared", f"f{i}.py")
             for i in range(4)]  # 4 > threshold 3
    builder = _builder_with(nodes)
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    resolved = builder._resolve("shared", _ctx(), rules)
    assert len(resolved) == 4
    assert all(res == "name_match_ambiguous" for _nid, res in resolved)


def test_dynamic_dispatch_unaffected_by_threshold():
    """skipped_dynamic does NOT receive ambiguous — projection handles it."""
    nodes = [_node(f"f{i}.py::send", "send", f"f{i}.py") for i in range(10)]
    builder = _builder_with(nodes)
    # Ruby's scope_rules has method_resolution == "dynamic_dispatch"
    rules = LANGUAGE_CONFIGS["ruby"].scope_rules
    resolved = builder._resolve("send", _ctx("caller.rb"), rules)
    assert all(res == "skipped_dynamic" for _nid, res in resolved)


def test_extends_path_also_gets_ambiguous():
    """_detect_extends calls _resolve too → threshold applies to extends edges."""
    nodes = [_node(f"f{i}.py::Base", "Base", f"f{i}.py", ntype="class")
             for i in range(4)]
    builder = _builder_with(nodes)
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    ctx = ScopeContext(current_file="child.py", import_aliases={},
                       caller_class="Child", caller_name="Child")
    resolved = builder._resolve("Base", ctx, rules)
    assert all(res == "name_match_ambiguous" for _nid, res in resolved)


def test_no_candidates_returns_empty():
    """Step 4 with zero candidates returns empty list (no edge)."""
    builder = _builder_with([])
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    assert builder._resolve("nonexistent_name", _ctx(), rules) == []


def test_no_rules_path_also_escalates():
    """rules=None early branch (line ~386) also escalates on high fanout."""
    nodes = [_node(f"f{i}.py::shared", "shared", f"f{i}.py") for i in range(4)]
    builder = _builder_with(nodes)
    resolved = builder._resolve("shared", _ctx(), rules=None)
    assert all(res == "name_match_ambiguous" for _nid, res in resolved)
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd the_door && python -m pytest tests/integration/extraction/test_edge_fanout_threshold.py -v`

Expected: FAIL on `ImportError: cannot import name 'FANOUT_THRESHOLD'`.

- [ ] **Step 3: Add FANOUT_THRESHOLD + modify `_resolve` two fallback branches**

Edit `the_door/src/the_door/core/extraction/edge_builder.py`:

1. **Add module-level constant** near the top of the file (after imports):

```python
# Fanout threshold for name_match → name_match_ambiguous escalation.
# When a bare name resolves to more than FANOUT_THRESHOLD candidates,
# edges are marked name_match_ambiguous so the prompt projection layer
# can drop them and fold the call into a caller-level aggregate hint.
# Default 3; tunable via dogfood histogram analysis (plan task 06).
FANOUT_THRESHOLD = 3
```

2. **Modify `_resolve` Step 4 fallback** (current lines ~410-412):

Find:
```python
        # Step 4: Fallback — name_match (keep all candidates, low confidence)
        matches = self._name_to_ids.get(name, [])
        return [(m, "name_match") for m in matches]
```

Replace with:
```python
        # Step 4: Fallback — name_match, escalated to ambiguous on high fanout.
        matches = self._name_to_ids.get(name, [])
        if not matches:
            return []
        res = "name_match_ambiguous" if len(matches) > FANOUT_THRESHOLD else "name_match"
        return [(m, res) for m in matches]
```

3. **Modify the no-rules early branch** (current lines ~386-389):

Find:
```python
        if rules is None:
            # No scope rules configured → pure name_match fallback
            matches = self._name_to_ids.get(name, [])
            return [(m, "name_match") for m in matches]
```

Replace with:
```python
        if rules is None:
            # No scope rules configured → pure name_match fallback (with fanout escalation)
            matches = self._name_to_ids.get(name, [])
            if not matches:
                return []
            res = "name_match_ambiguous" if len(matches) > FANOUT_THRESHOLD else "name_match"
            return [(m, res) for m in matches]
```

- [ ] **Step 4: Run integration tests to verify pass**

Run: `cd the_door && python -m pytest tests/integration/extraction/test_edge_fanout_threshold.py -v`

Expected: all 7 tests PASS.

- [ ] **Step 5: Run edge_builder coverage**

Run:
```
cd the_door && python -m pytest tests/ \
  --cov=src/the_door/core/extraction/edge_builder \
  --cov-report=term-missing 2>&1 | tail -20
```

Expected: `edge_builder.py` 100% coverage maintained.

- [ ] **Step 6: Run full suite**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected:
- 既有測試全 PASS。
- ⚠ **某些 pre-existing 測試若 assert edges 為 `name_match` 而其 fixture 候選數 > 3**，現在會看到 `name_match_ambiguous`。每次失敗都當作 review point：測試是否在驗證 resolution exact-match 或在驗證 fanout 計數？更新 assertion 或縮小 fixture，**不要降低 `FANOUT_THRESHOLD`**。

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/extraction/edge_builder.py \
        the_door/tests/integration/extraction/test_edge_fanout_threshold.py
git commit -m "feat(edge): FANOUT_THRESHOLD escalates high-fanout name_match → ambiguous"
```
