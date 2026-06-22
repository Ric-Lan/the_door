# Phase 3 — 三層原語

> 父計畫：[../2026-06-22-chunk-split-plan.md](../2026-06-22-chunk-split-plan.md)。前置：Phase 1、2 完成。
> 同前環境規則。

三個切分原語（純函式）：`_slice_by_order`（Tier 3 保底、總定義域）、`_bfs_order`（Tier 2 的 cohesion-aware 排序）、`_pack`（Tier 1 連通分量 bin-packing）。chunk 內部表示＝dict `{"node_ids":[...], "est_tokens":int, "oversized":bool}`（`tier` 標籤由 Phase 4 組裝時加）。

---

### Task 4: `_slice_by_order`（Tier 3 原語）

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_planner.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_tiers.py`

- [ ] **Step 1: 寫失敗測試**

建 `the_door/tests/unit/core/structure_view/test_chunk_tiers.py`：

```python
from the_door.core.structure_view import chunk_planner as cp


def test_slice_by_order_fills_to_budget():
    est = {"a": 40, "b": 40, "c": 40}
    chunks = cp._slice_by_order(["a", "b", "c"], est, target=100)
    # a+b=80 ≤100；加 c=120>100 → 斷。第二塊 c。
    assert [c["node_ids"] for c in chunks] == [["a", "b"], ["c"]]
    assert chunks[0]["est_tokens"] == 80
    assert all(c["oversized"] is False for c in chunks)


def test_slice_by_order_oversized_node_own_chunk():
    est = {"a": 10, "big": 500, "b": 10}
    chunks = cp._slice_by_order(["a", "big", "b"], est, target=100)
    # a(10) 一塊；big 超標自成 oversized 塊；b(10) 一塊
    assert chunks[0]["node_ids"] == ["a"]
    assert chunks[1]["node_ids"] == ["big"] and chunks[1]["oversized"] is True
    assert chunks[2]["node_ids"] == ["b"]


def test_slice_by_order_empty():
    assert cp._slice_by_order([], {}, target=100) == []
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_tiers.py -k slice -v`
Expected: FAIL（`_slice_by_order` 未定義）

- [ ] **Step 3: 實作**

加到 `chunk_planner.py`：

```python
def _slice_by_order(ordered: list, est: dict, target: int) -> list:
    """沿給定序貪婪填滿 target 就斷（Tier 3 原語，總定義域）。
    單節點 est > target → 自成 chunk 並標 oversized。"""
    chunks: list = []
    cur: list = []
    cur_est = 0
    for nid in ordered:
        e = est[nid]
        if e > target:
            if cur:
                chunks.append({"node_ids": cur, "est_tokens": cur_est, "oversized": False})
                cur, cur_est = [], 0
            chunks.append({"node_ids": [nid], "est_tokens": e, "oversized": True})
            continue
        if cur and cur_est + e > target:
            chunks.append({"node_ids": cur, "est_tokens": cur_est, "oversized": False})
            cur, cur_est = [], 0
        cur.append(nid)
        cur_est += e
    if cur:
        chunks.append({"node_ids": cur, "est_tokens": cur_est, "oversized": False})
    return chunks
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_tiers.py -k slice -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_planner.py the_door/tests/unit/core/structure_view/test_chunk_tiers.py
git commit -F - <<'EOF'
feat(chunk-planner): add _slice_by_order size-slicing primitive (Tier 3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### Task 5: `_bfs_order`（Tier 2 排序）

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_planner.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_tiers.py`

- [ ] **Step 1: 寫失敗測試**

加到 `test_chunk_tiers.py`：

```python
def test_bfs_order_starts_at_highest_indegree_and_covers_component():
    # 鏈 a-b-c-d；indeg 設成 c 最高 → 從 c 起 BFS
    adj = {"a": {"b"}, "b": {"a", "c"}, "c": {"b", "d"}, "d": {"c"}}
    indeg = {"a": 0, "b": 1, "c": 9, "d": 0}
    order = cp._bfs_order(["a", "b", "c", "d"], adj, indeg)
    assert order[0] == "c"                 # 從最高 in_degree 起
    assert sorted(order) == ["a", "b", "c", "d"]   # 涵蓋整個分量
    assert len(order) == 4                 # 不重複


def test_bfs_order_deterministic():
    adj = {"a": {"b", "c"}, "b": {"a"}, "c": {"a"}}
    indeg = {"a": 5, "b": 0, "c": 0}
    assert cp._bfs_order(["a", "b", "c"], adj, indeg) == \
           cp._bfs_order(["a", "b", "c"], adj, indeg)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_tiers.py -k bfs -v`
Expected: FAIL（`_bfs_order` 未定義）

- [ ] **Step 3: 實作**

在 `chunk_planner.py` 頂部 import 區加 `from collections import deque`，並加函式：

```python
def _bfs_order(component: list, adjacency: dict, indeg: dict) -> list:
    """從分量內最高 in_degree 節點起 BFS（鄰居按 (-in_degree, node_id) 序入列）。
    圖鄰近者在序列中相鄰 → 之後依序切時切口落在較稀疏處。決定性。"""
    start = sorted(component, key=lambda n: (-indeg.get(n, 0), n))[0]
    seen = {start}
    queue = deque([start])
    order: list = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for nb in sorted(adjacency.get(n, ()), key=lambda x: (-indeg.get(x, 0), x)):
            if nb not in seen:
                seen.add(nb)
                queue.append(nb)
    return order
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_tiers.py -k bfs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_planner.py the_door/tests/unit/core/structure_view/test_chunk_tiers.py
git commit -F - <<'EOF'
feat(chunk-planner): add _bfs_order for cohesion-aware Tier 2 slicing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### Task 6: `_pack`（Tier 1 連通分量 bin-packing）

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_planner.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_tiers.py`

- [ ] **Step 1: 寫失敗測試**

加到 `test_chunk_tiers.py`：

```python
def test_pack_combines_components_under_budget():
    # 三個分量 60/30/30，target=100：first-fit-decreasing → [60+30], [30]
    fitting = [(["a"], 60), (["b"], 30), (["c"], 30)]
    bins = cp._pack(fitting, target=100)
    assert len(bins) == 2
    assert bins[0]["est_tokens"] == 90 and sorted(bins[0]["node_ids"]) == ["a", "b"]
    assert bins[1]["est_tokens"] == 30 and bins[1]["node_ids"] == ["c"]
    assert all(b["oversized"] is False for b in bins)


def test_pack_node_ids_sorted_and_deterministic():
    fitting = [(["z::2", "a::1"], 50), (["m::3"], 50)]
    bins = cp._pack(fitting, target=100)
    assert bins[0]["node_ids"] == ["a::1", "m::3", "z::2"]   # 合併後排序
    assert cp._pack(fitting, 100) == cp._pack(fitting, 100)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_tiers.py -k pack -v`
Expected: FAIL（`_pack` 未定義）

- [ ] **Step 3: 實作**

加到 `chunk_planner.py`：

```python
def _pack(fitting: list, target: int) -> list:
    """把「各自 ≤ target 的連通分量」first-fit-decreasing 打包進 chunk（Tier 1）。
    fitting: list of (component_node_ids, comp_est)。決定性。"""
    items = sorted(fitting, key=lambda ce: (-ce[1], ce[0][0]))
    bins: list = []
    for comp, comp_est in items:
        placed = False
        for b in bins:
            if b["est_tokens"] + comp_est <= target:
                b["node_ids"].extend(comp)
                b["est_tokens"] += comp_est
                placed = True
                break
        if not placed:
            bins.append({"node_ids": list(comp), "est_tokens": comp_est})
    for b in bins:
        b["node_ids"] = sorted(b["node_ids"])
        b["oversized"] = False
    return bins
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_tiers.py -v`
Expected: PASS（7 個測試）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_planner.py the_door/tests/unit/core/structure_view/test_chunk_tiers.py
git commit -F - <<'EOF'
feat(chunk-planner): add _pack first-fit-decreasing component packing (Tier 1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Phase 3 自審
- spec §3 Tier 3（`_slice_by_order`，含 oversized 退化）→ Task 4；Tier 2 排序（`_bfs_order` 從最高 in_degree BFS）→ Task 5；Tier 1（`_pack` FFD、cut-free 合併分量）→ Task 6。✓
- chunk 內部表示 `{node_ids, est_tokens, oversized}` 三原語一致；`tier` 標籤留 Phase 4 加。✓
- 決定性測試齊（slice 順序、bfs、pack）。stdlib only（deque）。無 placeholder。✓
