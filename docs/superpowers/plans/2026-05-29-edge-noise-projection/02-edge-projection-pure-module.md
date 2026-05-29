# Task 02: Edge Projection Pure Module

**Files:**
- Create: `the_door/src/the_door/core/llm/edge_projection.py`
- Test: `the_door/tests/unit/core/llm/test_edge_projection.py` (new)
- Test: `the_door/tests/property/test_edge_projection_properties.py` (new)

**Goal:** 建一個純函式模組，把一批 edges 投影成「給 prompt 看的乾淨 edge list」+「aggregate hint dict」。**純函式、零 I/O、零 logging、零全域狀態、零旗標。**

**Depends on:** Task 01（`name_match_ambiguous` 是合法值）。

---

## Design Contract（純函式，無旗標）

```python
def project_edges_for_prompt(
    edges: list[dict],
) -> tuple[list[dict], dict[str, list[str]]]:
    """Apply projection rules for LLM prompt input.

    Input edges are dicts with at least:
        {"from": str, "to": str, "type": str, "resolution": str}

    Returns:
        (kept_edges, aggregate_hints)
        - kept_edges: subset of input, same dict shape
        - aggregate_hints: {caller_node_id: [method_name, ...]}
          method_name list is deduplicated and sorted.
          Method name extracted from to_node (last segment after '.').
    """
```

**Projection rules（無旗標，行為固定）：**

| resolution | result |
|---|---|
| `scope_rule` | kept |
| `import_alias` | kept |
| `name_match` | kept |
| `name_match_ambiguous` | drop + add to hint |
| `skipped_dynamic` | drop + add to hint |
| 未知值 | kept（防禦性） |

需要切換時再加旗標 — 目前沒有 caller 需要。

---

- [ ] **Step 1: Write the failing unit tests**

Create `the_door/tests/unit/core/llm/test_edge_projection.py`:

```python
"""Edge projection pure-function behavior."""
from the_door.core.llm.edge_projection import project_edges_for_prompt


def _edge(from_, to, res):
    return {"from": from_, "to": to, "type": "calls", "resolution": res}


def test_scope_rule_edges_kept():
    edges = [_edge("a", "b", "scope_rule")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}


def test_import_alias_edges_kept():
    edges = [_edge("a", "b", "import_alias")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}


def test_name_match_edges_kept():
    edges = [_edge("a", "b", "name_match")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}


def test_ambiguous_dropped_and_hinted_with_class_dot_method():
    edges = [_edge("caller", "pkg.Foo.write", "name_match_ambiguous")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"caller": ["write"]}


def test_dynamic_dropped_and_hinted():
    edges = [_edge("caller", "Bus.send", "skipped_dynamic")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"caller": ["send"]}


def test_to_node_without_dot_uses_whole_id_as_method_name():
    edges = [_edge("caller", "bare", "name_match_ambiguous")]
    kept, hints = project_edges_for_prompt(edges)
    assert hints == {"caller": ["bare"]}


def test_multiple_ambiguous_same_caller_deduped_sorted():
    edges = [
        _edge("caller", "F.write", "name_match_ambiguous"),
        _edge("caller", "G.get",   "name_match_ambiguous"),
        _edge("caller", "H.write", "name_match_ambiguous"),  # dup method name
    ]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"caller": ["get", "write"]}


def test_mixed_resolutions_partial_drop():
    edges = [
        _edge("a", "b", "scope_rule"),
        _edge("a", "c", "name_match"),
        _edge("a", "F.write",  "name_match_ambiguous"),
        _edge("a", "Bus.send", "skipped_dynamic"),
        _edge("a", "f", "import_alias"),
    ]
    kept, hints = project_edges_for_prompt(edges)
    assert {e["to"] for e in kept} == {"b", "c", "f"}
    assert hints == {"a": ["send", "write"]}


def test_empty_edges_returns_empty():
    kept, hints = project_edges_for_prompt([])
    assert kept == []
    assert hints == {}


def test_unknown_resolution_kept_defensively():
    """Unknown resolution doesn't crash, edge stays in kept."""
    edges = [{"from": "a", "to": "b", "type": "calls",
              "resolution": "future_value"}]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}
```

- [ ] **Step 2: Run tests to verify failing**

Run: `cd the_door && python -m pytest tests/unit/core/llm/test_edge_projection.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create the projection module**

Create `the_door/src/the_door/core/llm/edge_projection.py`:

```python
"""Edge projection layer for L1 prompt input.

Filters and aggregates raw graph edges into a form suitable for LLM
consumption: high-confidence and bounded-fanout edges pass through;
ambiguous and dynamic-dispatch edges are folded into a per-caller
"aggregate hint" dict the prompt can describe as imprecise call hints.

This module is pure: no I/O, no logging, no global state, no flags.
Same input always produces same output. Tests live in
tests/unit/core/llm/test_edge_projection.py and
tests/property/test_edge_projection_properties.py.
"""
from __future__ import annotations

_AGGREGATED_RESOLUTIONS = frozenset({"name_match_ambiguous", "skipped_dynamic"})


def project_edges_for_prompt(
    edges: list[dict],
) -> tuple[list[dict], dict[str, list[str]]]:
    """Project edges for prompt consumption.

    See module docstring + plan task 02 for contract.
    """
    kept: list[dict] = []
    hint_sets: dict[str, set[str]] = {}

    for edge in edges:
        if edge.get("resolution") in _AGGREGATED_RESOLUTIONS:
            caller = edge["from"]
            hint_sets.setdefault(caller, set()).add(
                _method_name_from_to(edge["to"])
            )
        else:
            kept.append(edge)

    hints = {caller: sorted(names) for caller, names in hint_sets.items()}
    return kept, hints


def _method_name_from_to(to_node: str) -> str:
    """Extract bare method name from a node_id like 'Class.method'."""
    if "." in to_node:
        return to_node.rsplit(".", 1)[-1]
    return to_node
```

- [ ] **Step 4: Run unit tests to verify pass**

Run: `cd the_door && python -m pytest tests/unit/core/llm/test_edge_projection.py -v`

Expected: all 10 tests PASS.

- [ ] **Step 5: Write property tests**

Create `the_door/tests/property/test_edge_projection_properties.py`:

```python
"""Property tests for edge_projection invariants."""
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


@given(edges=EDGES)
def test_high_confidence_always_kept(edges):
    """scope_rule and import_alias edges always survive projection."""
    high_conf = [e for e in edges
                 if e["resolution"] in ("scope_rule", "import_alias")]
    kept, _hints = project_edges_for_prompt(edges)
    for e in high_conf:
        assert e in kept


@given(edges=EDGES)
def test_ambiguous_and_dynamic_never_in_kept(edges):
    """ambiguous + dynamic must NOT appear in kept_edges."""
    kept, _hints = project_edges_for_prompt(edges)
    for e in kept:
        assert e["resolution"] not in ("name_match_ambiguous", "skipped_dynamic")


@given(edges=EDGES)
def test_idempotent(edges):
    """Re-projecting kept_edges is a no-op (kept edges produce no new hints)."""
    kept1, _hints1 = project_edges_for_prompt(edges)
    kept2, hints2 = project_edges_for_prompt(kept1)
    assert kept2 == kept1
    assert hints2 == {}


@given(edges=EDGES)
def test_hint_method_lists_sorted_and_unique(edges):
    """Hint method-name lists are deduplicated and sorted."""
    _kept, hints = project_edges_for_prompt(edges)
    for _caller, names in hints.items():
        assert names == sorted(names)
        assert len(names) == len(set(names))
```

- [ ] **Step 6: Run property tests**

Run: `cd the_door && python -m pytest tests/property/test_edge_projection_properties.py -v`

Expected: all 4 tests PASS.

- [ ] **Step 7: Verify 100% coverage on new module**

Run:
```
cd the_door && python -m pytest \
  tests/unit/core/llm/test_edge_projection.py \
  tests/property/test_edge_projection_properties.py \
  --cov=src/the_door/core/llm/edge_projection \
  --cov-report=term-missing
```

Expected: `edge_projection.py` 100% coverage.

- [ ] **Step 8: Run full suite — no regressions**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected: 既有 + 14 new passed (10 unit + 4 property).

- [ ] **Step 9: Commit**

```bash
git add the_door/src/the_door/core/llm/edge_projection.py \
        the_door/tests/unit/core/llm/test_edge_projection.py \
        the_door/tests/property/test_edge_projection_properties.py
git commit -m "feat(llm): edge_projection pure module + unit + property tests"
```
