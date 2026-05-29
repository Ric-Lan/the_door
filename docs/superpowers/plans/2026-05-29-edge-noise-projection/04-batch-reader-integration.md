# Task 04: BatchReader Projection Integration

**Files:**
- Modify: `the_door/src/the_door/core/reading/batch_reader.py` (`_build_payload` detail mode)
- Test: `the_door/tests/integration/reading/test_batch_reader_projection.py` (new)

**Goal:** 在 `BatchReader._build_payload` detail mode 出口呼叫 `project_edges_for_prompt`，把 ambiguous + dynamic 邊聚合成 `aggregate_call_hints` payload 欄位。minimal mode 不變。

**Depends on:** Task 02（`project_edges_for_prompt` 必須存在）+ Task 03（high fanout 才會產生 ambiguous 邊以驗收）。

---

## Design — 順序紀律

```
detail mode _build_payload:
  1. batch-local edge filter（既有）
  2. project_edges_for_prompt(batch_edges)
  3. payload["edges"] = kept_edges
  4. payload["aggregate_call_hints"] = hints
```

`aggregate_call_hints` 永遠是 dict（可能為空 `{}`，但 key 一定存在）。
minimal mode payload 不變 — 不含 `aggregate_call_hints` key。

---

- [ ] **Step 1: Write the failing integration test**

Create `the_door/tests/integration/reading/test_batch_reader_projection.py`:

```python
"""BatchReader detail mode applies edge_projection at payload boundary."""
from the_door.core.reading.batch_reader import BatchReader
from the_door.models import ASTNode, Edge, Structure


def _node(node_id: str, name: str, file: str = "x.py") -> ASTNode:
    return ASTNode(
        node_id=node_id, type="function", name=name, file=file,
        language="python", parameters=(),
    )


def _make_structure(nodes: list[ASTNode], edges: list[Edge]) -> Structure:
    return Structure(
        nodes=tuple(nodes),
        edges=tuple(edges),
        topology=(),
        files=(),
        analyzed_files=(),
    )


def test_detail_payload_includes_aggregate_call_hints_key():
    """Even when no edges trigger aggregation, the key exists as empty dict."""
    nodes = [_node("caller", "caller"), _node("target", "target")]
    edges = [Edge(from_node="caller", to_node="target",
                  type="calls", resolution="scope_rule")]
    reader = BatchReader(_make_structure(nodes, edges), context_mode="detail")
    payload = reader._build_payload(["caller", "target"], batch_num=0)

    assert "aggregate_call_hints" in payload
    assert payload["aggregate_call_hints"] == {}
    # scope_rule edge survives
    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["resolution"] == "scope_rule"


def test_ambiguous_edges_dropped_and_hint_populated():
    nodes = [_node("caller", "caller")] + [
        _node(f"target{i}", "write") for i in range(4)
    ]
    edges = [
        Edge(from_node="caller", to_node=f"target{i}",
             type="calls", resolution="name_match_ambiguous")
        for i in range(4)
    ]
    reader = BatchReader(_make_structure(nodes, edges), context_mode="detail")
    node_ids = ["caller"] + [f"target{i}" for i in range(4)]
    payload = reader._build_payload(node_ids, batch_num=0)

    # No ambiguous edges leaked through
    assert all(e["resolution"] != "name_match_ambiguous"
               for e in payload["edges"])
    # Caller has a hint
    assert "caller" in payload["aggregate_call_hints"]


def test_dynamic_edges_aggregated_into_hints():
    nodes = [_node("caller", "caller"), _node("target", "send")]
    edges = [Edge(from_node="caller", to_node="target",
                  type="calls", resolution="skipped_dynamic")]
    reader = BatchReader(_make_structure(nodes, edges), context_mode="detail")
    payload = reader._build_payload(["caller", "target"], batch_num=0)

    assert payload["edges"] == []
    assert "caller" in payload["aggregate_call_hints"]
    assert "send" in payload["aggregate_call_hints"]["caller"]


def test_minimal_mode_has_no_aggregate_call_hints_key():
    """minimal mode payload must NOT contain aggregate_call_hints."""
    nodes = [_node("a", "a"), _node("b", "b")]
    edges = [Edge(from_node="a", to_node="b",
                  type="calls", resolution="name_match_ambiguous")]
    reader = BatchReader(_make_structure(nodes, edges), context_mode="minimal")
    payload = reader._build_payload(["a", "b"], batch_num=0)

    assert "aggregate_call_hints" not in payload
    assert payload == {"batch": 0, "context_mode": "minimal", "nodes": ["a", "b"]}


def test_batch_local_filter_applied_before_projection():
    """Edges to nodes outside the batch are dropped first; projection
    only sees in-batch edges, so its hints only reference in-batch callers."""
    nodes = [_node("caller", "caller"),
             _node("in_batch_tgt", "x"),
             _node("out_of_batch_tgt", "y")]
    edges = [
        Edge(from_node="caller", to_node="in_batch_tgt",
             type="calls", resolution="name_match_ambiguous"),
        Edge(from_node="caller", to_node="out_of_batch_tgt",
             type="calls", resolution="name_match_ambiguous"),
    ]
    reader = BatchReader(_make_structure(nodes, edges), context_mode="detail")
    # Batch excludes "out_of_batch_tgt"
    payload = reader._build_payload(["caller", "in_batch_tgt"], batch_num=0)

    # Only the in-batch edge fed projection → only that one method name in hint
    hint = payload["aggregate_call_hints"].get("caller", [])
    assert len(hint) == 1  # not 2 — out-of-batch edge filtered first
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd the_door && python -m pytest tests/integration/reading/test_batch_reader_projection.py -v`

Expected: FAIL — `aggregate_call_hints` key missing from payload.

- [ ] **Step 3: Modify `_build_payload` to apply projection**

Edit `the_door/src/the_door/core/reading/batch_reader.py`:

1. Add import at the top of the file:

```python
from the_door.core.llm.edge_projection import project_edges_for_prompt
```

2. Modify `_build_payload` — find the existing return block (around line 280-297):

Find:
```python
        # Filter edges to those fully within this batch to bound payload size.
        batch_node_set = set(node_ids)
        edge_dicts = [
            {
                "from": e.from_node,
                "to": e.to_node,
                "type": e.type,
                "resolution": e.resolution,
            }
            for e in self._structure.edges
            if e.from_node in batch_node_set and e.to_node in batch_node_set
        ]
        return {
            "batch": batch_num,
            "context_mode": "detail",
            "nodes": node_dicts,
            "edges": edge_dicts,
        }
```

Replace with:
```python
        # Step 1: batch-local edge filter — bound payload size.
        batch_node_set = set(node_ids)
        edge_dicts = [
            {
                "from": e.from_node,
                "to": e.to_node,
                "type": e.type,
                "resolution": e.resolution,
                # method_name fallback uses to_node's bare segment in projection.
            }
            for e in self._structure.edges
            if e.from_node in batch_node_set and e.to_node in batch_node_set
        ]
        # Step 2: projection layer — drop ambiguous, aggregate dynamic into hints.
        kept_edges, aggregate_hints = project_edges_for_prompt(edge_dicts)
        return {
            "batch": batch_num,
            "context_mode": "detail",
            "nodes": node_dicts,
            "edges": kept_edges,
            "aggregate_call_hints": aggregate_hints,
        }
```

- [ ] **Step 4: Run integration tests to verify pass**

Run: `cd the_door && python -m pytest tests/integration/reading/test_batch_reader_projection.py -v`

Expected: all 5 tests PASS.

- [ ] **Step 5: Run batch_reader cov to confirm no regression**

Run:
```
cd the_door && python -m pytest tests/ \
  --cov=src/the_door/core/reading/batch_reader \
  --cov-report=term-missing 2>&1 | tail -10
```

Expected: cov ≥ previous level (no untested lines added).

- [ ] **Step 6: Run full suite**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected:
- All previous tests pass.
- ⚠ **Tests that assert `payload["edges"]` length/content for batches with ambiguous edges may fail.** Each such failure means projection now correctly filters them — update the test fixture or assertion. Do NOT bypass projection.
- ⚠ Tests that assert exact payload dict equality in detail mode will see new `aggregate_call_hints` key — update expected dicts to include it.

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/reading/batch_reader.py \
        the_door/tests/integration/reading/test_batch_reader_projection.py
git commit -m "feat(reading): apply edge projection at detail-mode payload boundary"
```
