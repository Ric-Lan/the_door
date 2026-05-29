# Task 04: BatchReader Projection Integration

**Files:**
- Modify: `the_door/src/the_door/core/reading/batch_reader.py` (`_build_payload` detail mode)
- Test: `the_door/tests/integration/test_batch_reader_projection.py` (new)

**Goal:** 在 `BatchReader._build_payload` detail mode 出口呼叫 `project_edges_for_prompt`，把 ambiguous + dynamic 邊聚合成 `aggregate_call_hints` payload 欄位。minimal mode 不變。

**Depends on:** Task 02（`project_edges_for_prompt` 必須存在）+ Task 03（high fanout 才會產生 ambiguous 邊以驗收）。

---

## BatchReader 構造簽名重要說明（必讀）

`BatchReader.__init__(llm_provider, structure: StructureJSON, *, max_context_tokens=None, context_mode="detail")`

- 第一個 positional 是 `llm_provider`（測試中可用 `object()` 或最小 stub）
- 第二個是 `StructureJSON`（**不是 `Structure`，沒有 `analyzed_files` 欄位**）
- `context_mode` 是 keyword-only

`StructureJSON` 真實欄位：`files / nodes / edges / topology`，僅此 4 個。

---

## Design — 順序紀律

```
detail mode _build_payload:
  1. batch-local edge filter（既有，line 280-291）
  2. project_edges_for_prompt(batch_edges)
  3. payload["edges"] = kept_edges
  4. payload["aggregate_call_hints"] = hints
```

`aggregate_call_hints` 永遠是 dict（可能為空 `{}`，但 key 一定存在）。
minimal mode payload 不變 — 不含 `aggregate_call_hints` key。

---

- [ ] **Step 1: Write the failing integration test**

Create `the_door/tests/integration/test_batch_reader_projection.py`:

```python
"""BatchReader detail mode applies edge_projection at payload boundary."""
from the_door.core.reading.batch_reader import BatchReader
from the_door.models import ASTNode, Edge, StructureJSON


class _StubProvider:
    """Minimal LLM provider stub — _build_payload doesn't use it."""
    pass


def _node(node_id: str, name: str, file: str = "x.py") -> ASTNode:
    return ASTNode(node_id=node_id, type="function", name=name, file=file,
                   language="python")


def _make_structure(nodes: list[ASTNode], edges: list[Edge]) -> StructureJSON:
    return StructureJSON(nodes=list(nodes), edges=list(edges))


def _reader(structure: StructureJSON, mode: str = "detail") -> BatchReader:
    return BatchReader(_StubProvider(), structure, context_mode=mode)


def test_detail_payload_includes_aggregate_call_hints_key():
    """Even when no edges trigger aggregation, the key exists as empty dict."""
    nodes = [_node("caller", "caller"), _node("target", "target")]
    edges = [Edge(from_node="caller", to_node="target",
                  type="calls", resolution="scope_rule")]
    payload = _reader(_make_structure(nodes, edges))._build_payload(
        ["caller", "target"], batch_num=0
    )
    assert "aggregate_call_hints" in payload
    assert payload["aggregate_call_hints"] == {}
    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["resolution"] == "scope_rule"


def test_ambiguous_edges_dropped_and_hint_populated():
    nodes = [_node("caller", "caller")] + [
        _node(f"M{i}.write", "write") for i in range(4)
    ]
    edges = [
        Edge(from_node="caller", to_node=f"M{i}.write",
             type="calls", resolution="name_match_ambiguous")
        for i in range(4)
    ]
    node_ids = ["caller"] + [f"M{i}.write" for i in range(4)]
    payload = _reader(_make_structure(nodes, edges))._build_payload(
        node_ids, batch_num=0
    )
    # No ambiguous edges leaked through
    assert all(e["resolution"] != "name_match_ambiguous"
               for e in payload["edges"])
    # Caller has a hint
    assert payload["aggregate_call_hints"] == {"caller": ["write"]}


def test_dynamic_edges_aggregated_into_hints():
    nodes = [_node("caller", "caller"), _node("Bus.send", "send")]
    edges = [Edge(from_node="caller", to_node="Bus.send",
                  type="calls", resolution="skipped_dynamic")]
    payload = _reader(_make_structure(nodes, edges))._build_payload(
        ["caller", "Bus.send"], batch_num=0
    )
    assert payload["edges"] == []
    assert payload["aggregate_call_hints"] == {"caller": ["send"]}


def test_minimal_mode_has_no_aggregate_call_hints_key():
    """minimal mode payload must NOT contain aggregate_call_hints."""
    nodes = [_node("a", "a"), _node("b", "b")]
    edges = [Edge(from_node="a", to_node="b",
                  type="calls", resolution="name_match_ambiguous")]
    payload = _reader(_make_structure(nodes, edges), mode="minimal")._build_payload(
        ["a", "b"], batch_num=0
    )
    assert "aggregate_call_hints" not in payload
    assert payload == {"batch": 0, "context_mode": "minimal",
                       "nodes": ["a", "b"]}


def test_batch_local_filter_applied_before_projection():
    """Edges to nodes outside the batch are dropped first; projection
    only sees in-batch edges, so its hints only reference in-batch callers."""
    nodes = [_node("caller", "caller"),
             _node("In.x", "x"),
             _node("Out.y", "y")]
    edges = [
        Edge(from_node="caller", to_node="In.x",
             type="calls", resolution="name_match_ambiguous"),
        Edge(from_node="caller", to_node="Out.y",
             type="calls", resolution="name_match_ambiguous"),
    ]
    # Batch excludes "Out.y"
    payload = _reader(_make_structure(nodes, edges))._build_payload(
        ["caller", "In.x"], batch_num=0
    )
    # Only the in-batch edge fed projection → only 'x' in hint, not 'y'
    assert payload["aggregate_call_hints"] == {"caller": ["x"]}
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd the_door && python -m pytest tests/integration/test_batch_reader_projection.py -v`

Expected: FAIL — `aggregate_call_hints` key missing from payload.

- [ ] **Step 3: Modify `_build_payload` to apply projection**

Edit `the_door/src/the_door/core/reading/batch_reader.py`:

1. Add import at the top of the file:

```python
from the_door.core.llm.edge_projection import project_edges_for_prompt
```

2. Modify the detail mode return block (around line 280-297). Find:

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
            }
            for e in self._structure.edges
            if e.from_node in batch_node_set and e.to_node in batch_node_set
        ]
        # Step 2: projection — drop ambiguous, aggregate dynamic into hints.
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

Run: `cd the_door && python -m pytest tests/integration/test_batch_reader_projection.py -v`

Expected: all 5 tests PASS.

- [ ] **Step 5: Run batch_reader coverage**

Run:
```
cd the_door && python -m pytest tests/ \
  --cov=src/the_door/core/reading/batch_reader \
  --cov-report=term-missing 2>&1 | tail -10
```

Expected: coverage 不退步。

- [ ] **Step 6: Run full suite**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected:
- 既有測試全 PASS。
- ⚠ **Tests that assert `payload["edges"]` exact content for batches with ambiguous/dynamic edges may fail.** Each such failure = projection correctly filtered — update fixture or assertion. **Do NOT bypass projection.**
- ⚠ Tests that assert exact payload dict equality in detail mode will see new `aggregate_call_hints` key — update expected dicts.

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/reading/batch_reader.py \
        the_door/tests/integration/test_batch_reader_projection.py
git commit -m "feat(reading): apply edge projection at detail-mode payload boundary"
```
