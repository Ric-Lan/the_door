# Phase 4 — Triage + 組裝（plan 入口）

> 父計畫：[../2026-06-22-chunk-split-plan.md](../2026-06-22-chunk-split-plan.md)。前置：Phase 1–3 完成（estimator/graph/三原語齊備）。
> 同前環境規則。

把前三階段組成入口 `plan()`：triage 決定 regime/要不要切 → small 短路回單 chunk；否則連通分量 → Tier 1 打包 + Tier 2 切 → 組裝輸出 + rollup（`cross_chunk_edges`）。資料來源複用 `locator.load_views`。

---

### Task 7: `triage`

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_planner.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_planner.py`

- [ ] **Step 1: 寫失敗測試**

建 `the_door/tests/unit/core/structure_view/test_chunk_planner.py`：

```python
from the_door.core.structure_view import chunk_planner as cp


def test_triage_small_no_split():
    assert cp.triage(50, target=100, large_ratio=8) == ("small", False)
    assert cp.triage(100, target=100, large_ratio=8) == ("small", False)  # 邊界 ≤


def test_triage_medium():
    assert cp.triage(101, target=100, large_ratio=8) == ("medium", True)
    assert cp.triage(800, target=100, large_ratio=8) == ("medium", True)  # 邊界 ≤ ratio×


def test_triage_large():
    assert cp.triage(801, target=100, large_ratio=8) == ("large", True)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_planner.py -k triage -v`
Expected: FAIL（`triage` 未定義）

- [ ] **Step 3: 實作**

在 `chunk_planner.py` 加常數（頂部 import 後）與函式：

```python
DEFAULT_TARGET_TOKENS = 100_000
DEFAULT_LARGE_RATIO = 8


def triage(total_est: int, target: int, large_ratio: int) -> tuple:
    """粗分 regime：small(≤target,不切) / medium(≤ratio×target) / large(>)。"""
    if total_est <= target:
        return "small", False
    if total_est <= large_ratio * target:
        return "medium", True
    return "large", True
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_planner.py -k triage -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_planner.py the_door/tests/unit/core/structure_view/test_chunk_planner.py
git commit -F - <<'EOF'
feat(chunk-planner): add triage (small/medium/large regime)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### Task 8: `_cross_chunk_edges` + `_assemble`

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_planner.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_planner.py`

- [ ] **Step 1: 寫失敗測試**

加到 `test_chunk_planner.py`：

```python
def test_cross_chunk_edges_counts_cut_edges_once():
    # 邊 a-b（同塊）、b-c（跨塊）。無向各存兩向，但只算一次。
    adj = {"a": {"b"}, "b": {"a", "c"}, "c": {"b"}}
    chunks = [{"node_ids": ["a", "b"]}, {"node_ids": ["c"]}]
    assert cp._cross_chunk_edges(adj, chunks) == 1


def test_assemble_shape_and_chunk_ids():
    chunks = [
        {"node_ids": ["a::1"], "est_tokens": 10, "oversized": False, "tier": "cohesion"},
        {"node_ids": ["b::2"], "est_tokens": 999, "oversized": True, "tier": "oversized"},
    ]
    out = cp._assemble(target=100, regime="medium", needs_split=True,
                       total=1009, chunks=chunks, cross=0, warnings=["b::2"])
    assert out["target_tokens"] == 100
    assert out["regime"] == "medium" and out["needs_split"] is True
    assert out["total_est_tokens"] == 1009
    assert [c["chunk_id"] for c in out["chunks"]] == ["chunk-001", "chunk-002"]
    assert out["chunks"][0]["tier"] == "cohesion"
    assert out["rollup"]["chunk_count"] == 2
    assert out["rollup"]["oversized_node_warnings"] == ["b::2"]
    # oversized 內部旗標不外洩到輸出 chunk
    assert "oversized" not in out["chunks"][0]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_planner.py -k "cross or assemble" -v`
Expected: FAIL（`_cross_chunk_edges`/`_assemble` 未定義）

- [ ] **Step 3: 實作**

加到 `chunk_planner.py`：

```python
def _cross_chunk_edges(adjacency: dict, chunks: list) -> int:
    """原圖中兩端點落在不同 chunk 的邊數（無向、每邊算一次）。"""
    loc: dict = {}
    for i, c in enumerate(chunks):
        for nid in c["node_ids"]:
            loc[nid] = i
    count = 0
    for u, nbrs in adjacency.items():
        for v in nbrs:
            if u < v and loc.get(u) != loc.get(v):
                count += 1
    return count


def _assemble(target: int, regime: str, needs_split: bool, total: int,
              chunks: list, cross: int, warnings: list) -> dict:
    """組裝最終輸出：指派 chunk_id、剝除內部 oversized 旗標、附 rollup。"""
    out_chunks = [
        {"chunk_id": f"chunk-{i:03d}", "node_ids": c["node_ids"],
         "est_tokens": c["est_tokens"], "tier": c.get("tier", "whole")}
        for i, c in enumerate(chunks, 1)
    ]
    return {
        "target_tokens": target,
        "regime": regime,
        "needs_split": needs_split,
        "total_est_tokens": total,
        "chunks": out_chunks,
        "rollup": {
            "chunk_count": len(out_chunks),
            "cross_chunk_edges": cross,
            "oversized_node_warnings": sorted(set(warnings)),
        },
    }
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_planner.py -k "cross or assemble" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_planner.py the_door/tests/unit/core/structure_view/test_chunk_planner.py
git commit -F - <<'EOF'
feat(chunk-planner): add cross_chunk_edges metric + output assembler

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### Task 9: `plan`（入口 compose）+ 真實 fixture 整合測試

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_planner.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_planner.py`

- [ ] **Step 1: 實作 `plan`**

在 `chunk_planner.py` 頂部 import 區加：

```python
from the_door.core.structure_view.locator import load_views
```

並加入口函式 `plan`（薄 IO 殼）+ 純核心 `_plan_from_views`（可用合成 views 測，不依賴磁碟）：

```python
def plan(codebase_path, target_tokens: int = DEFAULT_TARGET_TOKENS,
         large_ratio: int = DEFAULT_LARGE_RATIO) -> dict:
    """讀既有 structure-view，triage 後切成 ≤ target_tokens 的 chunk 計畫。
    structure-view 缺失 → load_views 拋 LocateError（自然向上拋）。"""
    return _plan_from_views(load_views(codebase_path), target_tokens, large_ratio)


def _plan_from_views(views: dict, target_tokens: int = DEFAULT_TARGET_TOKENS,
                     large_ratio: int = DEFAULT_LARGE_RATIO) -> dict:
    """純核心：吃 {node_id: view}，回 chunk 計畫。無 IO，便於合成測試。"""
    est = {nid: estimate_tokens(v) for nid, v in views.items()}
    total = sum(est.values())
    regime, needs_split = triage(total, target_tokens, large_ratio)

    if not needs_split:
        whole = {"node_ids": sorted(views), "est_tokens": total, "tier": "whole"}
        return _assemble(target_tokens, regime, needs_split, total, [whole], 0, [])

    adj = build_adjacency(views)
    indeg = {nid: _in_degree(views[nid]) for nid in views}
    fitting: list = []
    sliced: list = []
    warnings: list = []
    for comp in connected_components(adj, views.keys()):
        comp_est = sum(est[n] for n in comp)
        if comp_est <= target_tokens:
            fitting.append((comp, comp_est))            # Tier 1 候選
        else:
            for sub in _slice_by_order(_bfs_order(comp, adj, indeg), est, target_tokens):
                sub["tier"] = "oversized" if sub["oversized"] else "bisect"  # Tier 2/退化
                sliced.append(sub)
                if sub["oversized"]:
                    warnings.append(sub["node_ids"][0])
    packed = _pack(fitting, target_tokens)              # Tier 1
    for b in packed:
        b["tier"] = "cohesion"

    all_chunks = packed + sliced
    for c in all_chunks:                                # 統一輸出：塊內 node_ids 排序
        c["node_ids"] = sorted(c["node_ids"])           # （packed 已排序、sliced 原為 BFS 序）
    all_chunks.sort(key=lambda c: c["node_ids"][0])     # 決定性順序（按塊內最小 node_id）
    cross = _cross_chunk_edges(adj, all_chunks)
    return _assemble(target_tokens, regime, needs_split, total, all_chunks, cross, warnings)
```

- [ ] **Step 2: 寫整合測試（真實 fixture，控制 target_tokens 觸發切分）**

加到 `test_chunk_planner.py`：

```python
import pytest


@pytest.fixture()
def simple(fixtures_dir):
    return fixtures_dir / "sample_codebases" / "python_simple"


def _all_node_ids(out):
    ids = []
    for c in out["chunks"]:
        ids.extend(c["node_ids"])
    return ids


def _node(node_id, out=(), indeg=0, pad=""):
    return {
        "node_id": node_id, "name": node_id.split("::")[-1],
        "language": "python", "file": node_id.split("::")[0],
        "start_line": 1, "end_line": 2,
        "topology": {"in_degree": indeg, "out_degree": len(out),
                     "topology_rank": 0.0, "is_entry_point": False},
        "in_edges": [],
        "out_edges": [{"to_node_id": t, "type": "calls", "resolution": "scope_rule"} for t in out],
        "docstring": pad,
    }


# --- 合成 views 精確測各 tier（不依賴磁碟、估值由估計器推導不寫死） ---

def test_plan_from_views_cohesion_two_components_cut_free():
    views = {
        "m/a.py::a": _node("m/a.py::a", out=("m/a.py::b",)),
        "m/a.py::b": _node("m/a.py::b"),
        "n/x.py::x": _node("n/x.py::x", out=("n/x.py::y",)),
        "n/x.py::y": _node("n/x.py::y"),
    }
    est = {k: cp.estimate_tokens(v) for k, v in views.items()}
    comp1 = est["m/a.py::a"] + est["m/a.py::b"]
    total = sum(est.values())
    target = max(comp1, total - comp1)   # 各分量塞得下、兩者併不下 → 兩塊、cut-free
    out = cp._plan_from_views(views, target_tokens=target)
    assert out["needs_split"] is True
    assert out["rollup"]["cross_chunk_edges"] == 0
    assert all(c["tier"] == "cohesion" for c in out["chunks"])


def test_plan_from_views_zero_edge_packing_cut_free():
    views = {f"f.py::n{i}": _node(f"f.py::n{i}") for i in range(6)}
    est = {k: cp.estimate_tokens(v) for k, v in views.items()}
    total = sum(est.values())
    out = cp._plan_from_views(views, target_tokens=total // 2)  # 強制 >1 塊
    assert out["needs_split"] is True
    assert out["rollup"]["cross_chunk_edges"] == 0
    ids = [n for c in out["chunks"] for n in c["node_ids"]]
    assert sorted(ids) == sorted(views)


def test_plan_from_views_bisect_single_oversized_component():
    views = {
        "c.py::a": _node("c.py::a", out=("c.py::b",), indeg=0),
        "c.py::b": _node("c.py::b", out=("c.py::c",), indeg=1),
        "c.py::c": _node("c.py::c", indeg=1),
    }
    est = {k: cp.estimate_tokens(v) for k, v in views.items()}
    total = sum(est.values())
    out = cp._plan_from_views(views, target_tokens=total - 1)   # 容不下整條 → 切
    assert out["needs_split"] is True
    assert len(out["chunks"]) >= 2
    assert any(c["tier"] == "bisect" for c in out["chunks"])
    ids = [n for c in out["chunks"] for n in c["node_ids"]]
    assert sorted(ids) == sorted(views)


def test_plan_from_views_oversized_single_node():
    views = {
        "big.py::huge": _node("big.py::huge", pad="說" * 500),  # 大 docstring → 高估值
        "s.py::s": _node("s.py::s"),
    }
    est = {k: cp.estimate_tokens(v) for k, v in views.items()}
    target = est["s.py::s"] + 1     # 容得下 small、容不下 huge
    out = cp._plan_from_views(views, target_tokens=target)
    assert out["needs_split"] is True
    huge = [c for c in out["chunks"] if c["node_ids"] == ["big.py::huge"]]
    assert len(huge) == 1 and huge[0]["tier"] == "oversized"
    assert "big.py::huge" in out["rollup"]["oversized_node_warnings"]


def test_plan_small_regime_single_chunk(simple):
    # 預設大預算 → 整個 6 節點專案 ≤ 預算 → 不切
    out = cp.plan(simple)   # 預設 target=100_000
    assert out["regime"] == "small"
    assert out["needs_split"] is False
    assert len(out["chunks"]) == 1
    assert out["chunks"][0]["tier"] == "whole"
    assert len(out["chunks"][0]["node_ids"]) == 6


def test_plan_split_covers_all_nodes_and_respects_budget(simple):
    # 極小預算強制切分
    out = cp.plan(simple, target_tokens=80)
    assert out["needs_split"] is True
    assert out["regime"] in ("medium", "large")
    # 窮盡且不重：所有節點恰好出現一次
    ids = _all_node_ids(out)
    assert sorted(ids) == sorted(set(ids))          # 不重
    assert set(ids) == set(cp.load_views(simple))   # 窮盡（= 全部 6 節點）
    # 預算遵守：每塊 ≤ 預算，除非該塊是 oversized 單節點
    for c in out["chunks"]:
        assert c["est_tokens"] <= 80 or (c["tier"] == "oversized" and len(c["node_ids"]) == 1)
    # rollup 欄位齊
    assert out["rollup"]["chunk_count"] == len(out["chunks"])
    assert out["rollup"]["cross_chunk_edges"] >= 0


def test_plan_deterministic(simple):
    assert cp.plan(simple, target_tokens=80) == cp.plan(simple, target_tokens=80)


def test_plan_missing_structure_view_raises(tmp_path):
    from the_door.core.structure_view.locator import LocateError
    with pytest.raises(LocateError):
        cp.plan(tmp_path)
```

> 若 fixture 重生導致 `len == 6` 或某斷言因實際 token 估值不符，**以實際 fixture 為準**調整期望值（先 `-v` 觀察 `total_est_tokens` 再對齊 `target_tokens`），**不要改 fixture**。`target_tokens=80` 是為了在 6 節點小 fixture 上強制觸發 split；若該值未觸發 split（total ≤ 80），把它調更小（如 40）。

- [ ] **Step 3: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_planner.py -v`
Expected: PASS（triage + cross/assemble + 4 整合測試全綠）

- [ ] **Step 4: 跑整個 chunk_planner 測試套確認無回歸**

Run: `python -m pytest the_door/tests/unit/core/structure_view/ -q`
Expected: 全 PASS（estimator + graph + tiers + planner + 既有 locator 測試）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_planner.py the_door/tests/unit/core/structure_view/test_chunk_planner.py
git commit -F - <<'EOF'
feat(chunk-planner): add plan() entry composing triage + tiered chunking

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### 收尾：禁區守恆檢查

- [ ] **Step 1: 確認純加法、未動禁區**

Run: `git diff --stat main`
Expected: 只含 `core/structure_view/chunk_planner.py` + 4 個新測試檔。**不應**出現 `models/`、`extract_structure`、契約版號、gate hook、前端 viewer、`region_partition.py`、`locator.py`（只 import 複用、不改）。

---

## Phase 4 自審
- spec §2 triage（small/medium/large + needs_split + large_ratio 參數）→ Task 7。✓
- spec §5 輸出形態（target_tokens/regime/needs_split/total_est_tokens/chunks{chunk_id,node_ids,est_tokens,tier}/rollup{chunk_count,cross_chunk_edges,oversized_node_warnings}）→ Task 8 `_assemble`；cross_chunk_edges 定義（跨塊邊、算一次）→ Task 8。✓
- spec §3 階梯組裝（small 短路、Tier1 `_pack`、Tier2 `_bfs_order`+`_slice_by_order`、oversized 退化、決定性排序）→ Task 9 `plan`。✓
- spec §5 複用 `load_views`（不重寫讀取、LocateError 上拋）→ Task 9。✓
- spec §9 測試全覆蓋：triage 分流（Task7）、cross 計數/組裝（Task8）、決定性/預算遵守/窮盡不重/真實資料/缺 artifact 拋錯（Task9 fixture 測）、**Tier1 cohesion cut-free + 零邊打包 + Tier2 bisect + oversized**（Task9 用純核心 `_plan_from_views` 合成 views 精確測，估值由估計器推導不寫死、不依賴磁碟）。✓
- 型別一致：`plan`/`triage`/`_assemble`/`_cross_chunk_edges` 簽章與前述呼叫相符；chunk 內部 `{node_ids,est_tokens,oversized,tier}` 與 Phase 3 原語產物一致。✓
- 無 placeholder；禁區守恆檢查列為收尾步驟。✓
