# Phase 2 — 圖工具

> 父計畫：[../2026-06-22-chunk-split-plan.md](../2026-06-22-chunk-split-plan.md)。前置：Phase 1 完成（`chunk_planner.py` 已存在）。
> 同 Phase 1 環境規則（pytest 從 repo root、hook 限制、commit -F）。

由 node views 建無向圖、取連通分量。**只遍歷 `out_edges` 即涵蓋所有邊**；`to_node_id` 不在 views 內者略過。全程決定性（穩定排序）。

---

### Task 2: `_in_degree` + `build_adjacency`

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_planner.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_graph.py`

- [ ] **Step 1: 寫失敗測試**

建 `the_door/tests/unit/core/structure_view/test_chunk_graph.py`：

```python
from the_door.core.structure_view import chunk_planner as cp


def _v(node_id, out=(), indeg=0):
    return {
        "node_id": node_id, "name": node_id.split("::")[-1],
        "topology": {"in_degree": indeg, "out_degree": len(out)},
        "in_edges": [], "out_edges": [{"to_node_id": t, "type": "calls"} for t in out],
    }


def test_in_degree_handles_none_topology():
    assert cp._in_degree({"topology": None}) == 0
    assert cp._in_degree({"topology": {"in_degree": 5}}) == 5
    assert cp._in_degree({}) == 0


def test_build_adjacency_is_undirected_and_skips_external():
    views = {
        "a::f": _v("a::f", out=("b::g", "ext::x")),   # ext::x 不在 views → 略過
        "b::g": _v("b::g"),
    }
    adj = cp.build_adjacency(views)
    assert adj["a::f"] == {"b::g"}
    assert adj["b::g"] == {"a::f"}        # 無向：反向也有
    assert "ext::x" not in adj
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_graph.py -v`
Expected: FAIL（`_in_degree`/`build_adjacency` 未定義）

- [ ] **Step 3: 實作**

加到 `chunk_planner.py`：

```python
def _in_degree(view: dict) -> int:
    topo = view.get("topology")
    return topo.get("in_degree", 0) if isinstance(topo, dict) else 0


def build_adjacency(views: dict) -> dict:
    """無向鄰接表。只遍歷 out_edges（涵蓋所有邊一次）；外部 to_node_id 略過。"""
    adj: dict = {nid: set() for nid in views}
    for nid, view in views.items():
        for e in view.get("out_edges", []):
            tid = e.get("to_node_id")
            if tid in adj and tid != nid:
                adj[nid].add(tid)
                adj[tid].add(nid)
    return adj
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_graph.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_planner.py the_door/tests/unit/core/structure_view/test_chunk_graph.py
git commit -F - <<'EOF'
feat(chunk-planner): add in_degree + undirected adjacency builder

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### Task 3: `connected_components`

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_planner.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_graph.py`

- [ ] **Step 1: 寫失敗測試**

加到 `test_chunk_graph.py`：

```python
def test_connected_components_groups_and_isolates():
    views = {
        "a::f": _v("a::f", out=("b::g",)),
        "b::g": _v("b::g"),
        "z::lone": _v("z::lone"),          # 零邊 → 自成一分量
    }
    adj = cp.build_adjacency(views)
    comps = cp.connected_components(adj, views.keys())
    # 每分量已排序、分量間按首元素排序（決定性）
    assert comps == [["a::f", "b::g"], ["z::lone"]]


def test_connected_components_deterministic():
    views = {f"m::n{i}": _v(f"m::n{i}") for i in range(20)}
    adj = cp.build_adjacency(views)
    assert cp.connected_components(adj, views.keys()) == \
           cp.connected_components(adj, views.keys())
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_graph.py -k connected -v`
Expected: FAIL（`connected_components` 未定義）

- [ ] **Step 3: 實作**

加到 `chunk_planner.py`：

```python
def connected_components(adjacency: dict, node_ids) -> list:
    """回連通分量列表；每分量內按 node_id 排序、分量間按首元素排序（決定性）。"""
    seen: set = set()
    comps: list = []
    for start in sorted(node_ids):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        comp = []
        while stack:
            n = stack.pop()
            comp.append(n)
            for nb in adjacency.get(n, ()):
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        comps.append(sorted(comp))
    comps.sort(key=lambda c: c[0])
    return comps
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_graph.py -v`
Expected: PASS（4 個測試）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_planner.py the_door/tests/unit/core/structure_view/test_chunk_graph.py
git commit -F - <<'EOF'
feat(chunk-planner): add deterministic connected_components

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Phase 2 自審
- spec §3 建圖前置（無向、out_edges 涵蓋、外部略過）→ Task 2；連通分量（Tier 1 輸入、零邊→singleton 分量）→ Task 3。✓
- 決定性測試明確（sorted comp + sorted by first）。✓
- 型別：`build_adjacency(views)->dict[str,set]`、`connected_components(adj, node_ids)->list[list[str]]`、`_in_degree(view)->int`，Phase 3/4 依此。✓
