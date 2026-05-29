# Task 02: Edge Projection Pure Module

**Files:**
- Create: `the_door/src/the_door/core/llm/edge_projection.py`
- Test: `the_door/tests/unit/core/llm/test_edge_projection.py` (new)
- Test: `the_door/tests/property/test_edge_projection_properties.py` (new)

**Goal:** 建一個純函式模組，把一批 edges 投影成「給 prompt 看的乾淨 edge list」+「aggregate hint dict」。**純函式、零 I/O、零 logging、零全域狀態。**

**Depends on:** Task 01（`name_match_ambiguous` 是合法值）。

---

## Design Contract（純函式）

```python
def project_edges_for_prompt(
    edges: list[dict],
    *,
    drop_ambiguous: bool = True,
    aggregate_dynamic: bool = True,
) -> tuple[list[dict], dict[str, list[str]]]:
    """Apply projection rules for LLM prompt input.

    Input edges are dicts with at least:
        {"from": str, "to": str, "type": str, "resolution": str}
    Optional "method_name" key carries the called name for aggregate hints;
    if absent, aggregate hint uses the to-node's bare segment as fallback.

    Returns:
        (kept_edges, aggregate_hints)
        - kept_edges: subset of input, same dict shape
        - aggregate_hints: {caller_node_id: [method_name, ...]}
          method_name list is deduplicated and sorted
    """
```

**Projection rules:**

| resolution | drop_ambiguous=True | aggregate_dynamic=True | result |
|---|---|---|---|
| `scope_rule` | — | — | kept |
| `import_alias` | — | — | kept |
| `name_match` | — | — | kept |
| `name_match_ambiguous` | drop + add to hint | — | aggregated |
| `skipped_dynamic` | — | drop + add to hint | aggregated |

When both flags are False: identity function (return all edges, empty hints).

---

- [ ] **Step 1: Write the failing unit tests**

Create `the_door/tests/unit/core/llm/test_edge_projection.py`:

```python
"""Edge projection pure-function behavior."""
from the_door.core.llm.edge_projection import project_edges_for_prompt


def _edge(from_, to, res, method=None):
    e = {"from": from_, "to": to, "type": "calls", "resolution": res}
    if method is not None:
        e["method_name"] = method
    return e


def test_scope_rule_edges_always_kept():
    edges = [_edge("a", "b", "scope_rule")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}


def test_import_alias_edges_always_kept():
    edges = [_edge("a", "b", "import_alias")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}


def test_name_match_edges_kept_by_default():
    edges = [_edge("a", "b", "name_match")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}


def test_ambiguous_dropped_and_hinted():
    edges = [_edge("caller", "target", "name_match_ambiguous", method="write")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"caller": ["write"]}


def test_dynamic_dropped_and_hinted():
    edges = [_edge("caller", "target", "skipped_dynamic", method="send")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"caller": ["send"]}


def test_multiple_ambiguous_same_caller_deduped_sorted():
    edges = [
        _edge("caller", "t1", "name_match_ambiguous", method="write"),
        _edge("caller", "t2", "name_match_ambiguous", method="get"),
        _edge("caller", "t3", "name_match_ambiguous", method="write"),  # dup
    ]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == []
    assert hints == {"caller": ["get", "write"]}


def test_method_name_fallback_to_to_segment():
    """When edge has no method_name, use last segment of to_node."""
    edges = [_edge("caller", "pkg.Foo.bar", "name_match_ambiguous")]
    kept, hints = project_edges_for_prompt(edges)
    assert hints == {"caller": ["bar"]}


def test_method_name_fallback_no_dot():
    """to_node without dot uses whole id as method name."""
    edges = [_edge("caller", "bare", "name_match_ambiguous")]
    kept, hints = project_edges_for_prompt(edges)
    assert hints == {"caller": ["bare"]}


def test_drop_ambiguous_false_keeps_ambiguous():
    edges = [_edge("caller", "target", "name_match_ambiguous", method="x")]
    kept, hints = project_edges_for_prompt(edges, drop_ambiguous=False)
    assert kept == edges
    assert hints == {}


def test_aggregate_dynamic_false_keeps_dynamic():
    edges = [_edge("caller", "target", "skipped_dynamic", method="x")]
    kept, hints = project_edges_for_prompt(edges, aggregate_dynamic=False)
    assert kept == edges
    assert hints == {}


def test_both_flags_false_is_identity():
    edges = [
        _edge("a", "b", "name_match_ambiguous"),
        _edge("a", "c", "skipped_dynamic"),
    ]
    kept, hints = project_edges_for_prompt(
        edges, drop_ambiguous=False, aggregate_dynamic=False
    )
    assert kept == edges
    assert hints == {}


def test_mixed_resolutions_partial_drop():
    edges = [
        _edge("a", "b", "scope_rule"),
        _edge("a", "c", "name_match"),
        _edge("a", "d", "name_match_ambiguous", method="write"),
        _edge("a", "e", "skipped_dynamic", method="send"),
        _edge("a", "f", "import_alias"),
    ]
    kept, hints = project_edges_for_prompt(edges)
    assert {e["to"] for e in kept} == {"b", "c", "f"}
    assert hints == {"a": ["send", "write"]}


def test_empty_edges_returns_empty():
    kept, hints = project_edges_for_prompt([])
    assert kept == []
    assert hints == {}


def test_unknown_resolution_kept_as_unknown():
    """Defensive: unknown resolution doesn't crash, edge stays."""
    edges = [_edge("a", "b", "future_value_we_dont_know")]
    kept, hints = project_edges_for_prompt(edges)
    assert kept == edges
    assert hints == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd the_door && python -m pytest tests/unit/core/llm/test_edge_projection.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'the_door.core.llm.edge_projection'`

- [ ] **Step 3: Create the projection module**

Create `the_door/src/the_door/core/llm/edge_projection.py`:

```python
"""Edge projection layer for L1 prompt input.

Filters and aggregates raw graph edges into a form suitable for LLM
consumption: high-confidence and bounded-fanout edges pass through;
ambiguous and dynamic-dispatch edges are folded into a per-caller
"aggregate hint" dict the prompt can describe as imprecise call hints.

This module is pure: no I/O, no logging, no global state. Same input
always produces same output. Tests live in
tests/unit/core/llm/test_edge_projection.py and
tests/property/test_edge_projection_properties.py.
"""
from __future__ import annotations


def project_edges_for_prompt(
    edges: list[dict],
    *,
    drop_ambiguous: bool = True,
    aggregate_dynamic: bool = True,
) -> tuple[list[dict], dict[str, list[str]]]:
    """Project edges for prompt consumption.

    See module docstring + project plan task 02 for contract.
    """
    kept: list[dict] = []
    hint_sets: dict[str, set[str]] = {}

    for edge in edges:
        resolution = edge.get("resolution")
        if resolution == "name_match_ambiguous" and drop_ambiguous:
            _record_hint(edge, hint_sets)
        elif resolution == "skipped_dynamic" and aggregate_dynamic:
            _record_hint(edge, hint_sets)
        else:
            kept.append(edge)

    hints = {caller: sorted(names) for caller, names in hint_sets.items()}
    return kept, hints


def _record_hint(edge: dict, hint_sets: dict[str, set[str]]) -> None:
    """Add the edge's method name to its caller's hint set."""
    caller = edge["from"]
    method_name = edge.get("method_name") or _method_name_from_to(edge["to"])
    hint_sets.setdefault(caller, set()).add(method_name)


def _method_name_from_to(to_node: str) -> str:
    """Fallback: extract bare method name from a node_id like 'Class.method'."""
    if "." in to_node:
        return to_node.rsplit(".", 1)[-1]
    return to_node
```

- [ ] **Step 4: Run unit tests to verify pass**

Run: `cd the_door && python -m pytest tests/unit/core/llm/test_edge_projection.py -v`

Expected: all 14 tests PASS.

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
    """scope_rule and import_alias edges must always survive projection."""
    high_conf = [e for e in edges
                 if e["resolution"] in ("scope_rule", "import_alias")]
    kept, _hints = project_edges_for_prompt(edges)
    for e in high_conf:
        assert e in kept


@given(edges=EDGES)
def test_ambiguous_and_dynamic_never_in_kept(edges):
    """With default flags, ambiguous + dynamic must NOT appear in kept_edges."""
    kept, _hints = project_edges_for_prompt(edges)
    for e in kept:
        assert e["resolution"] not in ("name_match_ambiguous", "skipped_dynamic")


@given(edges=EDGES)
def test_idempotent(edges):
    """Re-projecting kept_edges (with same flags) is a no-op."""
    kept1, hints1 = project_edges_for_prompt(edges)
    kept2, hints2 = project_edges_for_prompt(kept1)
    assert kept2 == kept1
    assert hints2 == {}


@given(edges=EDGES)
def test_hint_callers_subset_of_input_callers(edges):
    """Every caller in the hint dict must be a 'from' value somewhere in input."""
    input_callers = {e["from"] for e in edges}
    _kept, hints = project_edges_for_prompt(edges)
    assert set(hints.keys()).issubset(input_callers)


@given(edges=EDGES)
def test_hint_method_lists_sorted_and_unique(edges):
    """Hint method-name lists are deduplicated and sorted."""
    _kept, hints = project_edges_for_prompt(edges)
    for caller, names in hints.items():
        assert names == sorted(names)
        assert len(names) == len(set(names))
```

- [ ] **Step 6: Run property tests**

Run: `cd the_door && python -m pytest tests/property/test_edge_projection_properties.py -v`

Expected: all 5 tests PASS (200+ examples each).

- [ ] **Step 7: Verify 100% coverage on new module**

Run:
```
cd the_door && python -m pytest \
  tests/unit/core/llm/test_edge_projection.py \
  tests/property/test_edge_projection_properties.py \
  --cov=src/the_door/core/llm/edge_projection \
  --cov-report=term-missing
```

Expected: `edge_projection.py` 100% coverage. If not, examine `Missing` lines and add tests inline before commit.

- [ ] **Step 8: Run full suite to confirm no regressions**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected: all prior tests still pass + 14 unit + 5 property = +19 passed.

- [ ] **Step 9: Commit**

```bash
git add the_door/src/the_door/core/llm/edge_projection.py \
        the_door/tests/unit/core/llm/test_edge_projection.py \
        the_door/tests/property/test_edge_projection_properties.py
git commit -m "feat(llm): edge_projection pure module + unit + property tests"
```
