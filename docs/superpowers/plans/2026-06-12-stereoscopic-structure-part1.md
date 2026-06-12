# 立體化結構實作計畫 Part 1／2：core/structure_view 套件（Task 1–4）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建 `core/structure_view/` 套件：區域分割（流向矩陣）、撥離膜、node 座標視圖、索引組裝與 artifact 落檔。

**Architecture:** 純函式管線 `partition → evaluate_peel → assemble_views → write_artifacts`，全部決定性、零 I/O 除了 `write_artifacts`。Part 2（同目錄 `2026-06-12-stereoscopic-structure-part2.md`）接 MCP 面。

**Tech Stack:** Python 3.11+ dataclasses、既有 `the_door.core.membrane`（SignalPosition/MembraneElement）、`structure_serializer.build_structure_dict` 複用、gzip+json。

**Spec:** `docs/superpowers/specs/2026-06-12-stereoscopic-structure-design.md`

**環境鐵則**（每個 task 都適用）：pytest 的 cwd＝內層 `the_door/`；指令一律 `PYTHONUTF8=1 python -m pytest ...`（Bash 的 `python -c`/`python x.py` 被 hook 擋）；commit 用 `git commit -F <檔>` 或單行 `-m`。

---

### Task 1: region_partition.py（區域分割＋流向矩陣）

**Files:**
- Create: `the_door/src/the_door/core/structure_view/__init__.py`
- Create: `the_door/src/the_door/core/structure_view/region_partition.py`
- Test: `the_door/tests/unit/core/structure_view/__init__.py`（空檔）
- Test: `the_door/tests/unit/core/structure_view/test_region_partition.py`

- [ ] **Step 1: 寫失敗測試**

```python
"""region_partition 單元測試：決定性、流向計數、退化案例。"""
from the_door.core.structure_view.region_partition import Region, partition
from the_door.models import ASTNode, Edge


def _node(node_id: str) -> ASTNode:
    return ASTNode(node_id=node_id, type="function", name=node_id.rsplit("::", 1)[-1],
                   file=node_id.split("::", 1)[0], language="python")


def _edges_fixture() -> tuple[list[ASTNode], list[Edge]]:
    nodes = [
        _node("src/a.py::f1"), _node("src/a.py::f2"),
        _node("tests/test_a.py::t1"), _node("tests/test_a.py::t2"),
    ]
    edges = [
        Edge(from_node="src/a.py::f1", to_node="src/a.py::f2", type="calls"),          # internal src
        Edge(from_node="tests/test_a.py::t1", to_node="src/a.py::f1", type="calls"),   # tests -> src
        Edge(from_node="tests/test_a.py::t2", to_node="src/a.py::f1", type="calls"),   # tests -> src
        Edge(from_node="tests/test_a.py::t1", to_node="tests/test_a.py::t2", type="calls"),  # internal tests
    ]
    return nodes, edges


def test_partition_flow_matrix_counts():
    nodes, edges = _edges_fixture()
    regions = {r.region_id: r for r in partition(nodes, edges)}
    assert set(regions) == {"src", "tests"}
    src, tests = regions["src"], regions["tests"]
    assert src.internal_edges == 1 and src.inbound_edges == 2 and src.outbound_edges == 0
    assert tests.internal_edges == 1 and tests.inbound_edges == 0 and tests.outbound_edges == 2
    assert tests.flow_to == {"src": 2} and src.flow_from == {"tests": 2}


def test_partition_is_deterministic():
    nodes, edges = _edges_fixture()
    a = partition(nodes, edges)
    b = partition(list(reversed(nodes)), list(reversed(edges)))
    assert a == b  # frozen dataclass 等值＝排序穩定


def test_partition_degenerate_single_root():
    nodes = [_node("src/a.py::f1"), _node("src/b.py::f2")]
    edges = [Edge(from_node="src/a.py::f1", to_node="src/b.py::f2", type="calls")]
    regions = partition(nodes, edges)
    assert len(regions) == 1 and regions[0].region_id == "src"
    assert regions[0].outbound_edges == 0 and regions[0].inbound_edges == 0


def test_partition_rootlevel_node_gets_safe_region_id():
    nodes = [_node("setup.py::main")]
    regions = partition(nodes, [])
    assert regions[0].region_id == "_root_"  # 無 "/" → fs-safe 桶名
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/structure_view/test_region_partition.py -v`
Expected: FAIL（ModuleNotFoundError: the_door.core.structure_view）

- [ ] **Step 3: 最小實作**

`the_door/src/the_door/core/structure_view/__init__.py`：
```python
"""structure_view — extract_structure 輸出的縱軸三層：撥離索引/區域切片/node 座標視圖。"""
```

`the_door/src/the_door/core/structure_view/region_partition.py`：
```python
"""區域分割：按 node_id 路徑頂層段聚類，計算跨區流向矩陣。

純結構計算、決定性、零路徑名寫死。退化案例（單一頂層段）＝1 區、
零撥離訊號＝誠實輸出（spec §4.1 明令不得自行加第二層聚類）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from the_door.models import ASTNode, Edge

_ROOT_BUCKET = "_root_"  # 無 "/" 的 node_id（root 層檔案）之 fs-safe 桶名


@dataclass(frozen=True)
class Region:
    """一個路徑頂層段區域與其邊界流量。"""

    region_id: str
    node_ids: tuple[str, ...]          # 已排序
    internal_edges: int
    inbound_edges: int                 # 他區 -> 本區 總計
    outbound_edges: int                # 本區 -> 他區 總計
    flow_to: dict[str, int] = field(default_factory=dict)    # 鄰區 -> 邊數（本區為 from）
    flow_from: dict[str, int] = field(default_factory=dict)  # 鄰區 -> 邊數（本區為 to）


def region_of(node_id: str) -> str:
    """node_id 的路徑頂層段；無 '/' → _ROOT_BUCKET。"""
    return node_id.split("/", 1)[0] if "/" in node_id else _ROOT_BUCKET


def partition(nodes: list[ASTNode], edges: list[Edge]) -> list[Region]:
    """分割節點為區域並計數三向邊流。輸出按 region_id 排序（決定性）。"""
    members: dict[str, list[str]] = {}
    for n in nodes:
        members.setdefault(region_of(n.node_id), []).append(n.node_id)

    internal: dict[str, int] = {}
    flow: dict[tuple[str, str], int] = {}  # (from_region, to_region) -> count，僅跨區
    for e in edges:
        fr, to = region_of(e.from_node), region_of(e.to_node)
        if fr == to:
            internal[fr] = internal.get(fr, 0) + 1
        else:
            flow[(fr, to)] = flow.get((fr, to), 0) + 1

    regions: list[Region] = []
    for rid in sorted(members):
        flow_to = {to: c for (fr, to), c in sorted(flow.items()) if fr == rid}
        flow_from = {fr: c for (fr, to), c in sorted(flow.items()) if to == rid}
        regions.append(Region(
            region_id=rid,
            node_ids=tuple(sorted(members[rid])),
            internal_edges=internal.get(rid, 0),
            inbound_edges=sum(flow_from.values()),
            outbound_edges=sum(flow_to.values()),
            flow_to=flow_to,
            flow_from=flow_from,
        ))
    return regions
```

注意：dataclass 生成的 `__eq__` 對 dict 欄位做值比較即正確，**不要**自訂 `__eq__`（含 dict 欄位的 frozen dataclass 不可 hash，本型別也不需要 hash）。

- [ ] **Step 4: 跑測試確認通過**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/structure_view/test_region_partition.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/ the_door/tests/unit/core/structure_view/
git commit -m "feat(structure-view): region_partition 區域分割+跨區流向矩陣"
```

---

### Task 2: peel_membrane.py（撥離理由膜＋判定）

**Files:**
- Create: `the_door/src/the_door/core/structure_view/peel_membrane.py`
- Test: `the_door/tests/unit/core/structure_view/test_peel_membrane.py`

- [ ] **Step 1: 寫失敗測試**

```python
"""peel_membrane：膜樣板（contrasts/gloss 同源）＋單向流動判定（含閾值邊界）。"""
from the_door.core.structure_view.peel_membrane import (
    PEEL_CONTRASTS, PEEL_FLOW_RATIO_THRESHOLD, PEEL_MIN_OUTBOUND,
    evaluate_peel, peel_element,
)
from the_door.core.structure_view.region_partition import Region


def _region(outbound: int, inbound: int) -> Region:
    return Region(region_id="tests", node_ids=("tests/t.py::t1",),
                  internal_edges=0, inbound_edges=inbound, outbound_edges=outbound,
                  flow_to={"src": outbound} if outbound else {},
                  flow_from={"src": inbound} if inbound else {})


def test_membrane_template_single_value():
    el = peel_element("one_way_consumer").to_json()
    assert el["value"] == "one_way_consumer"
    assert el["position"]["contrasts"] == list(PEEL_CONTRASTS)
    assert el["position"]["gloss"]  # 非空 gloss


def test_one_way_consumer_detected_above_threshold():
    verdict = evaluate_peel(_region(outbound=60, inbound=1))  # ratio 60 >= 50, outbound >= 50
    assert verdict is not None
    assert verdict["reason"]["value"] == "one_way_consumer"
    ev = verdict["evidence"]
    assert ev["outbound"] == 60 and ev["inbound"] == 1
    assert ev["ratio_threshold"] == PEEL_FLOW_RATIO_THRESHOLD
    assert ev["min_outbound"] == PEEL_MIN_OUTBOUND


def test_balanced_flow_not_peeled():
    assert evaluate_peel(_region(outbound=60, inbound=10)) is None  # ratio 6 < 50


def test_small_region_not_peeled_even_if_one_way():
    assert evaluate_peel(_region(outbound=10, inbound=0)) is None  # outbound 10 < 50


def test_zero_inbound_uses_max_one_denominator():
    verdict = evaluate_peel(_region(outbound=50, inbound=0))  # 50/max(0,1)=50 >= 50
    assert verdict is not None
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/structure_view/test_peel_membrane.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 最小實作**

`the_door/src/the_door/core/structure_view/peel_membrane.py`：
```python
"""撥離理由膜：照 confidence_membrane 樣板（CONTRASTS＋_GLOSS 單一來源）。

第一刀 enum 僅 one_way_consumer（2026-06-12 spike 實測 4362:9 成立的唯一訊號）。
禁止用可達性/isolation 當撥離訊號（project_t1_guidance_falsified 已證偽）。
判定＝決定性結構計算（surface 不 judge）；「要不要跳過該區」裁決留給消費端 LLM。
"""
from __future__ import annotations

from the_door.core.membrane import MembraneElement, SignalPosition
from the_door.core.structure_view.region_partition import Region

# 唯一來源：撥離理由 enum（低基數，遇真實新案例才擴值）。
PEEL_CONTRASTS: tuple[str, ...] = ("one_way_consumer",)

_GLOSS = {
    "one_way_consumer": "單向消費區：大量消費其他區、幾乎不被回頭消費（如測試碼之於主體）",
}

# 判定閾值（spike 實測 tests/ 流向 4362:9 ≈ 485:1，餘量充足）。寫進 evidence 供消費端稽核。
PEEL_FLOW_RATIO_THRESHOLD = 50   # outbound/inbound 比
PEEL_MIN_OUTBOUND = 50           # 避免小樣本誤標


def peel_signal(value: str) -> SignalPosition:
    return SignalPosition(contrasts=PEEL_CONTRASTS, gloss=_GLOSS[value])


def peel_element(value: str) -> MembraneElement:
    return MembraneElement(payload=value, position=peel_signal(value))


def evaluate_peel(region: Region) -> dict | None:
    """單向消費判定。回 {"reason": 膜元素 json, "evidence": 計數+閾值} 或 None（不標）。"""
    a, b = region.outbound_edges, region.inbound_edges
    ratio = a / max(b, 1)
    if a >= PEEL_MIN_OUTBOUND and ratio >= PEEL_FLOW_RATIO_THRESHOLD:
        return {
            "reason": peel_element("one_way_consumer").to_json(),
            "evidence": {
                "outbound": a, "inbound": b, "ratio": round(ratio, 1),
                "min_outbound": PEEL_MIN_OUTBOUND,
                "ratio_threshold": PEEL_FLOW_RATIO_THRESHOLD,
            },
        }
    return None
```

實作前先讀 `the_door/src/the_door/core/membrane.py` 確認 `SignalPosition`/`MembraneElement.to_json()` 的確切建構參數（參考用法＝`core/reading/confidence_membrane.py:25-39`）；若 `to_json()` 輸出鍵與測試假設（`value`/`position.contrasts`/`position.gloss`）不符，以 membrane.py 實際鍵為準改測試。

- [ ] **Step 4: 跑測試確認通過**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/structure_view/test_peel_membrane.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/peel_membrane.py the_door/tests/unit/core/structure_view/test_peel_membrane.py
git commit -m "feat(structure-view): peel_membrane 撥離理由膜+單向流動判定"
```

---

### Task 3: node_view.py（L2 node 座標視圖組裝）

**Files:**
- Create: `the_door/src/the_door/core/structure_view/node_view.py`
- Test: `the_door/tests/unit/core/structure_view/test_node_view.py`

- [ ] **Step 1: 寫失敗測試**

```python
"""node_view：單 node 多軸並置（屬性+出入邊+topology+殘餘基數），統一 node_id 定址。"""
from the_door.core.structure_view.node_view import assemble_views
from the_door.models import ASTNode, Edge, TopologyEntry


def _fixture():
    nodes = [
        ASTNode(node_id="src/a.py::f1", type="function", name="f1", file="src/a.py",
                language="python", docstring="calls f2"),
        ASTNode(node_id="src/b.py::f2", type="function", name="f2", file="src/b.py",
                language="python"),
    ]
    edges = [
        Edge(from_node="src/a.py::f1", to_node="src/b.py::f2", type="calls", resolution="scope_rule"),
        Edge(from_node="src/a.py::f1", to_node="src/b.py::f2", type="imports", resolution="import_alias"),
    ]
    topo = [
        TopologyEntry(node_id="src/a.py::f1", in_degree=0, out_degree=2,
                      topology_rank=1, is_entry_point=True, batch_assignment=1),
        TopologyEntry(node_id="src/b.py::f2", in_degree=2, out_degree=0,
                      topology_rank=2, is_entry_point=False, batch_assignment=2),
    ]
    residue = {
        "indeterminate": [],
        "low_confidence_ambiguous": [{"caller": "src/a.py::f1", "methods": {"py::x": 3}, "cardinality": 3}],
    }
    return nodes, edges, topo, residue


def test_view_unified_node_id_addressing():
    nodes, edges, topo, residue = _fixture()
    views = assemble_views(nodes, edges, topo, residue)
    v = views["src/a.py::f1"]
    assert v["node_id"] == "src/a.py::f1"
    assert v["out_edges"] == [
        {"to_node_id": "src/b.py::f2", "type": "calls", "resolution": "scope_rule"},
        {"to_node_id": "src/b.py::f2", "type": "imports", "resolution": "import_alias"},
    ]
    assert views["src/b.py::f2"]["in_edges"] == [
        {"from_node_id": "src/a.py::f1", "type": "calls", "resolution": "scope_rule"},
        {"from_node_id": "src/a.py::f1", "type": "imports", "resolution": "import_alias"},
    ]


def test_view_coalesces_topology_and_attrs():
    nodes, edges, topo, residue = _fixture()
    v = assemble_views(nodes, edges, topo, residue)["src/a.py::f1"]
    assert v["topology"] == {"in_degree": 0, "out_degree": 2, "topology_rank": 1,
                             "is_entry_point": True, "batch_assignment": 1}
    assert v["docstring"] == "calls f2"  # 屬性與拓撲並置＝跨軸矛盾可偵測（F-b 教訓）


def test_view_residue_cardinality_reference_not_copy():
    nodes, edges, topo, residue = _fixture()
    v = assemble_views(nodes, edges, topo, residue)["src/a.py::f1"]
    # 只存基數引用（座標+基數可下鑽），完整條目留在 .the-door/edge-residue.json
    assert v["residue_as_caller"] == {"low_confidence_ambiguous": 1, "indeterminate": 0}


def test_view_deterministic_edge_order():
    nodes, edges, topo, residue = _fixture()
    a = assemble_views(nodes, edges, topo, residue)
    b = assemble_views(nodes, list(reversed(edges)), topo, residue)
    assert a == b
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/structure_view/test_node_view.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 最小實作**

`the_door/src/the_door/core/structure_view/node_view.py`：
```python
"""L2 node 座標視圖：單 node 的多軸並置（屬性＋出入邊＋topology＋殘餘基數）。

定址欄位統一 node_id 詞彙（out_edges[].to_node_id / in_edges[].from_node_id）——
消滅 F-b 型手工 join 失誤。殘餘只存基數引用，完整條目在 edge-residue.json。
"""
from __future__ import annotations

from collections import Counter

from the_door.models import ASTNode, Edge, TopologyEntry


def assemble_views(
    nodes: list[ASTNode],
    edges: list[Edge],
    topology_entries: list[TopologyEntry],
    residue: dict,
) -> dict[str, dict]:
    """回 {node_id: 視圖 dict}。決定性：邊列表按 (對端 id, type) 排序。"""
    topo = {t.node_id: t for t in topology_entries}
    out_by: dict[str, list[dict]] = {}
    in_by: dict[str, list[dict]] = {}
    for e in edges:
        out_by.setdefault(e.from_node, []).append(
            {"to_node_id": e.to_node, "type": e.type, "resolution": e.resolution})
        in_by.setdefault(e.to_node, []).append(
            {"from_node_id": e.from_node, "type": e.type, "resolution": e.resolution})

    low_callers = Counter(ent.get("caller") for ent in residue.get("low_confidence_ambiguous", []))
    ind_callers = Counter(ent.get("caller") for ent in residue.get("indeterminate", []))

    views: dict[str, dict] = {}
    for n in nodes:
        t = topo.get(n.node_id)
        views[n.node_id] = {
            "node_id": n.node_id,
            "type": n.type, "name": n.name, "file": n.file, "language": n.language,
            "decorators": n.decorators, "parameters": n.parameters,
            "return_type": n.return_type, "docstring": n.docstring, "comments": n.comments,
            "topology": ({
                "in_degree": t.in_degree, "out_degree": t.out_degree,
                "topology_rank": t.topology_rank, "is_entry_point": t.is_entry_point,
                "batch_assignment": t.batch_assignment,
            } if t else None),
            "out_edges": sorted(out_by.get(n.node_id, []),
                                key=lambda d: (d["to_node_id"], d["type"])),
            "in_edges": sorted(in_by.get(n.node_id, []),
                               key=lambda d: (d["from_node_id"], d["type"])),
            "residue_as_caller": {
                "low_confidence_ambiguous": low_callers.get(n.node_id, 0),
                "indeterminate": ind_callers.get(n.node_id, 0),
            },
        }
    return views
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/structure_view/test_node_view.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/node_view.py the_door/tests/unit/core/structure_view/test_node_view.py
git commit -m "feat(structure-view): node_view L2 單元座標視圖（統一 node_id 定址）"
```

---

### Task 4: structure_index.py（L0 索引組裝＋artifact 落檔）

**Files:**
- Create: `the_door/src/the_door/core/structure_view/structure_index.py`
- Test: `the_door/tests/unit/core/structure_view/test_structure_index.py`

- [ ] **Step 1: 寫失敗測試**

```python
"""structure_index：索引完整性（基數/比例/位址/大小）、artifact round-trip、標註不過濾。"""
import gzip
import json

from the_door.core.structure_view.structure_index import write_artifacts
from the_door.models import ASTNode, Edge, StructureJSON, TopologyEntry


def _structure(n_tests: int = 60) -> StructureJSON:
    """src 2 nodes；tests n_tests nodes，全部單向打進 src（觸發撥離）。"""
    nodes = [
        ASTNode(node_id="src/a.py::f1", type="function", name="f1", file="src/a.py", language="python"),
        ASTNode(node_id="src/a.py::f2", type="function", name="f2", file="src/a.py", language="python"),
    ]
    edges = [Edge(from_node="src/a.py::f1", to_node="src/a.py::f2", type="calls")]
    topo = [
        TopologyEntry(node_id="src/a.py::f1", in_degree=n_tests, out_degree=1,
                      topology_rank=1, is_entry_point=True, batch_assignment=1),
        TopologyEntry(node_id="src/a.py::f2", in_degree=1, out_degree=0,
                      topology_rank=2, is_entry_point=False, batch_assignment=2),
    ]
    for i in range(n_tests):
        nid = f"tests/test_a.py::t{i}"
        nodes.append(ASTNode(node_id=nid, type="function", name=f"t{i}",
                             file="tests/test_a.py", language="python"))
        edges.append(Edge(from_node=nid, to_node="src/a.py::f1", type="calls"))
        topo.append(TopologyEntry(node_id=nid, in_degree=0, out_degree=1,
                                  topology_rank=10 + i, is_entry_point=True, batch_assignment=1))
    return StructureJSON(files=[], nodes=nodes, edges=edges, topology=topo)


_EMPTY_RESIDUE = {"indeterminate": [], "low_confidence_ambiguous": []}


def test_index_entries_complete(tmp_path):
    index = write_artifacts(str(tmp_path), _structure(), _EMPTY_RESIDUE)
    assert index["totals"] == {"files": 0, "nodes": 62, "edges": 61, "regions": 2}
    by_id = {r["region_id"]: r for r in index["regions"]}
    tests = by_id["tests"]
    assert tests["node_count"] == 60 and tests["share_pct"] == 96.8
    assert tests["edges"] == {"internal": 0, "inbound": 0, "outbound": 60}
    assert tests["batches"] == {"1": 60}
    assert tests["artifact_path"].endswith("tests.json.gz")
    assert tests["size_bytes"] > 0
    assert tests["peel"]["reason"]["value"] == "one_way_consumer"
    assert by_id["src"]["peel"] is None


def test_artifacts_roundtrip_and_no_filtering(tmp_path):
    write_artifacts(str(tmp_path), _structure(), _EMPTY_RESIDUE)
    view_dir = tmp_path / ".the-door" / "structure-view"
    assert (view_dir / "index.json").is_file()
    # 被撥離區資料完整在檔（標註不過濾的結構性證明）
    with gzip.open(view_dir / "regions" / "tests.json.gz", "rt", encoding="utf-8") as f:
        region = json.load(f)
    assert region["region_id"] == "tests" and len(region["nodes"]) == 60
    assert region["nodes"][0]["node_id"].startswith("tests/")
    # 全量 raw structure round-trip（供 validate_output 接縫）
    with gzip.open(view_dir / "structure.full.json.gz", "rt", encoding="utf-8") as f:
        full = json.load(f)
    assert len(full["nodes"]) == 62 and len(full["edges"]) == 61 and len(full["topology"]) == 62


def test_index_has_consumption_guide(tmp_path):
    index = write_artifacts(str(tmp_path), _structure(), _EMPTY_RESIDUE)
    guide = index["consumption_guide"]
    assert "batch" in guide["batch_semantics"]  # 批次語義必須被解釋（F-d 教訓）
    assert guide["addressing"] == "node_id"
    assert index["artifact_dir"].endswith("structure-view")
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/structure_view/test_structure_index.py -v`
Expected: FAIL（ImportError）

- [ ] **Step 3: 最小實作**

`the_door/src/the_door/core/structure_view/structure_index.py`：
```python
"""L0 撥離索引組裝＋artifact 落檔。

回應本體＝索引（索引尺寸）；bulk 落 .the-door/structure-view/：
  index.json                 — L0 索引（同回應內容，落檔供重讀）
  structure.full.json.gz     — 全量 raw structure（validate_output 接縫用；
                               複用 structure_serializer.build_structure_dict）
  regions/<region_id>.json.gz — 該區全部 L2 node 視圖
撥離≠刪除：被標示區資料完整在檔（加法不減法）。
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from the_door.core.extraction.structure_serializer import build_structure_dict
from the_door.core.structure_view.node_view import assemble_views
from the_door.core.structure_view.peel_membrane import evaluate_peel
from the_door.core.structure_view.region_partition import partition
from the_door.models import StructureJSON

STRUCTURE_VIEW_DIRNAME = "structure-view"

_CONSUMPTION_GUIDE = {
    "addressing": "node_id",
    "region_artifact_format": "gzip JSON: {region_id, nodes: [L2 view]}；view 鍵＝node_id/"
                              "out_edges[].to_node_id/in_edges[].from_node_id/topology/residue_as_caller",
    "batch_semantics": "topology-guided LLM reading: batch 1＝entry points，batch 2..5＝"
                       "其餘按 in_degree 降冪分配；建議按批次序消費",
    "full_structure": "structure.full.json.gz＝raw nodes/edges/topology 全量（edges 用 from/to 舊欄位名）",
    "edge_residue": "完整殘餘條目在 .the-door/edge-residue.json（先跑 edge_residue 工具）",
}


def view_dir(codebase_path: str | Path) -> Path:
    return Path(codebase_path) / ".the-door" / STRUCTURE_VIEW_DIRNAME


def write_artifacts(codebase_path: str | Path, structure: StructureJSON, residue: dict) -> dict:
    """落 artifact 並回傳 L0 索引 dict（即 MCP 回應本體）。"""
    base = view_dir(codebase_path)
    (base / "regions").mkdir(parents=True, exist_ok=True)

    views = assemble_views(structure.nodes, structure.edges, structure.topology, residue)
    regions = partition(structure.nodes, structure.edges)
    batch_of = {t.node_id: t.batch_assignment for t in structure.topology}
    total_nodes = len(structure.nodes)

    region_entries = []
    for r in regions:
        region_payload = {"region_id": r.region_id, "nodes": [views[nid] for nid in r.node_ids]}
        path = base / "regions" / f"{r.region_id}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(region_payload, f, ensure_ascii=False)

        batches: dict[str, int] = {}
        for nid in r.node_ids:
            b = str(batch_of.get(nid, 0))
            batches[b] = batches.get(b, 0) + 1

        region_entries.append({
            "region_id": r.region_id,
            "node_count": len(r.node_ids),
            "share_pct": round(len(r.node_ids) / total_nodes * 100, 1) if total_nodes else 0.0,
            "edges": {"internal": r.internal_edges, "inbound": r.inbound_edges,
                      "outbound": r.outbound_edges},
            "flow_to": r.flow_to,
            "batches": dict(sorted(batches.items())),
            "artifact_path": str(path),
            "size_bytes": path.stat().st_size,
            "peel": evaluate_peel(r),
        })

    full_path = base / "structure.full.json.gz"
    with gzip.open(full_path, "wt", encoding="utf-8") as f:
        json.dump(build_structure_dict(structure, None), f, ensure_ascii=False)

    index = {
        "totals": {"files": len(structure.files), "nodes": total_nodes,
                   "edges": len(structure.edges), "regions": len(regions)},
        "regions": region_entries,
        "artifact_dir": str(base),
        "full_structure_path": str(full_path),
        "consumption_guide": _CONSUMPTION_GUIDE,
    }
    (base / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/structure_view/test_structure_index.py -v`
Expected: 3 passed

- [ ] **Step 5: 跑整個 structure_view 測試群**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/structure_view/ -v`
Expected: 16 passed

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/structure_view/structure_index.py the_door/tests/unit/core/structure_view/test_structure_index.py
git commit -m "feat(structure-view): structure_index L0 索引組裝+artifact 落檔"
```

→ 繼續 Part 2：`docs/superpowers/plans/2026-06-12-stereoscopic-structure-part2.md`
