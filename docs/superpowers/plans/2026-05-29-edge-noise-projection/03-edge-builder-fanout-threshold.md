# Task 03: EdgeBuilder Fanout Threshold

**Files:**
- Modify: `the_door/src/the_door/core/extraction/edge_builder.py` (Step 4 fallback in `_resolve`)
- Test: `the_door/tests/integration/extraction/test_edge_fanout_threshold.py` (new)

**Goal:** 在 `_resolve()` Step 4 fallback 加 `FANOUT_THRESHOLD` 檢查 — 候選數超過閾值時把 resolution 標 `name_match_ambiguous`。**自動同時涵蓋 calls 與 extends 邊**（`_detect_extends` 也呼叫同一個 `_resolve`）。

**Depends on:** Task 01。

---

## Design

```python
FANOUT_THRESHOLD = 3  # default; tuned by dogfood histogram (Task 06)

# inside _resolve(), Step 4 (current):
matches = self._name_to_ids.get(name, [])
return [(m, "name_match") for m in matches]

# becomes:
matches = self._name_to_ids.get(name, [])
if not matches:
    return []
res = "name_match_ambiguous" if len(matches) > FANOUT_THRESHOLD else "name_match"
return [(m, res) for m in matches]
```

**Important:** Step 1 (`skipped_dynamic` early-out at line 397) does NOT get the threshold — the projection layer (Task 02) handles dynamic fanout via aggregate hints.

---

- [ ] **Step 1: Write the failing integration test**

Create `the_door/tests/integration/extraction/test_edge_fanout_threshold.py`:

```python
"""EdgeBuilder marks high-fanout name_match edges as name_match_ambiguous."""
from the_door.core.extraction.edge_builder import EdgeBuilder, FANOUT_THRESHOLD
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS
from the_door.models import ASTNode


def _node(node_id: str, name: str, file: str, ntype: str = "function") -> ASTNode:
    return ASTNode(
        node_id=node_id,
        type=ntype,
        name=name,
        file=file,
        language="python",
        parameters=(),
    )


def test_low_fanout_keeps_name_match():
    """When candidates ≤ threshold, resolution stays name_match."""
    assert FANOUT_THRESHOLD == 3  # contract anchor for this test
    nodes = [
        _node("a.py::caller", "caller", "a.py"),
        _node("a.py::target1", "shared", "a.py"),
        _node("b.py::target2", "shared", "b.py"),
    ]
    # 2 candidates < threshold 3 → name_match
    builder = EdgeBuilder(nodes)
    matches = builder._name_to_ids.get("shared", [])
    assert len(matches) == 2
    # Direct probe of internal _resolve to isolate the threshold logic.
    from the_door.core.extraction.edge_builder import ScopeContext
    ctx = ScopeContext(
        current_file="external.py",  # forces Step 4 (scope_rule won't match)
        import_aliases={},
        caller_class=None,
        caller_name=None,
    )
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    resolved = builder._resolve("shared", ctx, rules)
    assert all(res == "name_match" for _nid, res in resolved)


def test_high_fanout_marks_ambiguous():
    """When candidates > threshold, resolution becomes name_match_ambiguous."""
    # Build 4 candidates (> threshold 3)
    nodes = [_node(f"f{i}.py::shared", "shared", f"f{i}.py") for i in range(4)]
    nodes.append(_node("caller.py::caller", "caller", "caller.py"))
    builder = EdgeBuilder(nodes)
    matches = builder._name_to_ids.get("shared", [])
    assert len(matches) == 4
    from the_door.core.extraction.edge_builder import ScopeContext
    ctx = ScopeContext(
        current_file="external.py",
        import_aliases={},
        caller_class=None,
        caller_name=None,
    )
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    resolved = builder._resolve("shared", ctx, rules)
    assert resolved  # 4 edges
    assert all(res == "name_match_ambiguous" for _nid, res in resolved)


def test_dynamic_dispatch_unaffected_by_threshold():
    """skipped_dynamic does NOT receive name_match_ambiguous — projection handles it."""
    nodes = [_node(f"f{i}.py::send", "send", f"f{i}.py") for i in range(10)]
    nodes.append(_node("caller.py::caller", "caller", "caller.py"))
    builder = EdgeBuilder(nodes)
    from the_door.core.extraction.edge_builder import ScopeContext
    ctx = ScopeContext(
        current_file="caller.py",
        import_aliases={},
        caller_class=None,
        caller_name=None,
    )
    # Use Ruby scope_rules → method_resolution == "dynamic_dispatch"
    rules = LANGUAGE_CONFIGS["ruby"].scope_rules
    resolved = builder._resolve("send", ctx, rules)
    assert all(res == "skipped_dynamic" for _nid, res in resolved)


def test_extends_path_also_gets_ambiguous():
    """_detect_extends calls _resolve too → threshold applies to extends edges."""
    # 4 classes named Base across files
    nodes = [_node(f"f{i}.py::Base", "Base", f"f{i}.py", ntype="class") for i in range(4)]
    nodes.append(_node("child.py::Child", "Child", "child.py", ntype="class"))
    builder = EdgeBuilder(nodes)
    from the_door.core.extraction.edge_builder import ScopeContext
    ctx = ScopeContext(
        current_file="child.py",
        import_aliases={},
        caller_class="Child",
        caller_name="Child",
    )
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    resolved = builder._resolve("Base", ctx, rules)
    assert all(res == "name_match_ambiguous" for _nid, res in resolved)


def test_no_candidates_returns_empty():
    """Step 4 with zero candidates returns empty list (no edge)."""
    nodes = [_node("a.py::caller", "caller", "a.py")]
    builder = EdgeBuilder(nodes)
    from the_door.core.extraction.edge_builder import ScopeContext
    ctx = ScopeContext(
        current_file="a.py",
        import_aliases={},
        caller_class=None,
        caller_name=None,
    )
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    assert builder._resolve("nonexistent_name", ctx, rules) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && python -m pytest tests/integration/extraction/test_edge_fanout_threshold.py -v`

Expected: FAIL on `from ... import FANOUT_THRESHOLD` (constant not defined yet) OR FAIL on `test_high_fanout_marks_ambiguous` (still emits `name_match`).

- [ ] **Step 3: Add FANOUT_THRESHOLD constant + modify `_resolve` Step 4**

Edit `the_door/src/the_door/core/extraction/edge_builder.py`:

1. Add module-level constant near the top of the file (after imports):

```python
# Fanout threshold for name_match → name_match_ambiguous escalation.
# When a bare name resolves to more than FANOUT_THRESHOLD candidates,
# the edges are marked name_match_ambiguous so the LLM prompt projection
# layer can drop them and fold the call into an aggregate hint instead.
# Default 3; tunable via dogfood histogram analysis (see plan task 06).
FANOUT_THRESHOLD = 3
```

2. Modify `_resolve` Step 4 fallback (current lines ~410-412):

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

3. Also modify the no-rules early branch (current line ~386-389):

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

- [ ] **Step 4: Run integration test to verify it passes**

Run: `cd the_door && python -m pytest tests/integration/extraction/test_edge_fanout_threshold.py -v`

Expected: all 5 tests PASS.

- [ ] **Step 5: Run edge_builder cov to confirm 100%**

Run:
```
cd the_door && python -m pytest tests/ \
  --cov=src/the_door/core/extraction/edge_builder \
  --cov-report=term-missing 2>&1 | tail -20
```

Expected: `edge_builder.py` 100% coverage maintained. If any uncovered lines belong to the new branches, add targeted tests inline.

- [ ] **Step 6: Run full suite — confirm no regressions**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected:
- Existing tests pass.
- ⚠ **Some pre-existing tests that assert edges have `resolution == "name_match"` may now see `name_match_ambiguous`** for high-fanout cases. If so, the test was relying on incidental fanout — update the assertion to accept either value, or restructure the fixture to produce only ≤ 3 candidates.
- Treat each such failure as a deliberate review point: was the test pinning resolution exact-match, or fanout count? Adjust accordingly. Do NOT lower `FANOUT_THRESHOLD` to avoid the failure.

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/extraction/edge_builder.py \
        the_door/tests/integration/extraction/test_edge_fanout_threshold.py
git commit -m "feat(edge): FANOUT_THRESHOLD escalates high-fanout name_match → ambiguous"
```
