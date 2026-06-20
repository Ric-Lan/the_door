# integration_check 工具化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「功能宣稱依賴 vs 結構真有連線」做成一個 MCP 工具 `integration_check`，並加法持久化 `relation_type`/`inferred_reason` 讓判定可跨版本 diff。

**Architecture:** 兩半——(1) **加法持久化**：`RelationSummary` 新增選填 `relation_type`(static|inferred)+`inferred_reason`，貫穿 snapshot_write 入參、snapshot_store 序列化/反序列化（純加法、不 bump contract、舊資料相容）。(2) **新工具**：`integration_check(codebase_path, version_ref, max_hops=2)` 讀持久化 typed relations + `structure.full.json.gz` 的 edges，對每條 `static` 關係用有限跳數 BFS 查 backing，回傳 per-relation 三態判定（backed/gap/undetermined）+ inferred(conceptual)/未typed(not_assessed) + rollup。沿用既有工具模式（`TOOL_SCHEMA`+`async execute`）。

**Tech Stack:** Python 3.12、pytest、既有 `the_door.core.diff.snapshot_store.SnapshotStore`、`the_door.models.snapshot.RelationSummary`、MCP server (`the_door.mcp.server`)。

**對應 spec：** [`docs/superpowers/specs/2026-06-19-integration-gap-verification-design.md`](../specs/2026-06-19-integration-gap-verification-design.md) §9（核可的工具化設計）。

---

## 環境須知（每個 Task 適用）
- pytest cwd ＝內層 `C:/Users/Ric/Desktop/the_door/the_door`；指令前置 `PYTHONUTF8=1`。
- ⚠ **C4 hook**：禁 `python -c` 與臨時 `.py`；執行走 `python -m pytest`。
- ⚠ **branch 護欄**：每次 commit 前 `git rev-parse --abbrev-ref HEAD` 須為 `feat/integration-check-tool`；不切分支、不 cd 出主 repo。
- commit 訊息結尾：`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- **不 bump** `SNAPSHOT_CONTRACT_VERSION`（純加法）。

## File Structure
- Modify: `the_door/src/the_door/models/snapshot.py` — `RelationSummary` 加兩欄
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py` — 序列化/反序列化帶兩欄
- Modify: `the_door/src/the_door/mcp/tools/snapshot_write_tool.py` — 入參 schema + 解析帶兩欄
- Create: `the_door/src/the_door/mcp/tools/integration_check_tool.py` — 新工具（classifier + execute）
- Modify: `the_door/src/the_door/mcp/server.py` — 註冊 + dispatch
- Modify: `CLAUDE.md` — 工具表 + relations 寫法 + 非循環守則
- Test: `the_door/tests/unit/models/test_relation_summary_fields.py`、`the_door/tests/unit/mcp/test_integration_check_tool.py`、`the_door/tests/unit/mcp/test_snapshot_write_relation_type.py`

---

### Task 1: RelationSummary 加 relation_type / inferred_reason（model + 持久化往返）

**Files:**
- Modify: `the_door/src/the_door/models/snapshot.py:53-59`
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py:373-380`（序列化）、`456-461`（反序列化）
- Test: `the_door/tests/unit/models/test_relation_summary_fields.py`

- [ ] **Step 1: 寫失敗測試（往返保真 + 舊資料相容）**

Create `the_door/tests/unit/models/test_relation_summary_fields.py`:
```python
"""RelationSummary 新增 relation_type / inferred_reason 的往返與相容測試。"""
import tempfile
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary, RelationSummary


def _store():
    d = tempfile.mkdtemp()
    return SnapshotStore(d), d


def _feat(fid):
    return FeatureSummary(
        feature_id=fid, label=fid, description="d",
        source_node_count=1, confidence="high", source_nodes=("X.m",),
    )


def test_relation_type_fields_default_none():
    r = RelationSummary(from_feature="a", to_feature="b", relation="depends_on")
    assert r.relation_type is None
    assert r.inferred_reason is None


def test_typed_relation_roundtrips_through_store():
    store, _ = _store()
    rels = [RelationSummary("feat-a", "feat-b", "depends_on",
                            relation_type="static"),
            RelationSummary("feat-a", "feat-c", "feeds_into",
                            relation_type="inferred", inferred_reason="概念先後")]
    snap = store.create_snapshot(
        l1_snapshot={"feat-a": _feat("feat-a"), "feat-b": _feat("feat-b"), "feat-c": _feat("feat-c")},
        feature_relations=rels, analyzed_files=[], commit_hash=None,
        git_tags=[], trigger="manual", label="v-typed",
    )
    got = store.get_snapshot(snap.version_id).feature_relations_snapshot
    by = {(r.from_feature, r.to_feature): r for r in got}
    assert by[("feat-a", "feat-b")].relation_type == "static"
    assert by[("feat-a", "feat-b")].inferred_reason is None
    assert by[("feat-a", "feat-c")].relation_type == "inferred"
    assert by[("feat-a", "feat-c")].inferred_reason == "概念先後"


def test_legacy_relation_without_type_still_loads():
    """反序列化舊 JSON（無 relation_type 鍵）→ 兩欄為 None，不報錯。"""
    store, _ = _store()
    snap = store.create_snapshot(
        l1_snapshot={"feat-a": _feat("feat-a"), "feat-b": _feat("feat-b")},
        feature_relations=[RelationSummary("feat-a", "feat-b", "depends_on")],
        analyzed_files=[], commit_hash=None, git_tags=[], trigger="manual", label="v-legacy",
    )
    got = store.get_snapshot(snap.version_id).feature_relations_snapshot[0]
    assert got.relation_type is None and got.inferred_reason is None
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/models/test_relation_summary_fields.py -v`
Expected: FAIL（`RelationSummary` 不接受 `relation_type` → TypeError）。

- [ ] **Step 3: model 加兩欄**

`the_door/src/the_door/models/snapshot.py`，把 `RelationSummary`（行 53-59）改成：
```python
@dataclass(frozen=True)
class RelationSummary:
    """Summarized feature relation stored in a version snapshot."""

    from_feature: str
    to_feature: str
    relation: str
    relation_type: str | None = None  # "static" | "inferred" | None(舊資料/未分型)
    inferred_reason: str | None = None  # inferred 時的一句理由
```

- [ ] **Step 4: 序列化帶兩欄**

`the_door/src/the_door/core/diff/snapshot_store.py` 序列化區（行 373-380）改成：
```python
        relations_data = [
            {
                "from_feature": r.from_feature,
                "to_feature": r.to_feature,
                "relation": r.relation,
                "relation_type": r.relation_type,
                "inferred_reason": r.inferred_reason,
            }
            for r in snapshot.feature_relations_snapshot
        ]
```

- [ ] **Step 5: 反序列化帶兩欄（用 .get 容忍舊 JSON）**

同檔反序列化區（行 456-461）改成：
```python
            RelationSummary(
                from_feature=r["from_feature"],
                to_feature=r["to_feature"],
                relation=r["relation"],
                relation_type=r.get("relation_type"),
                inferred_reason=r.get("inferred_reason"),
            )
            for r in data.get("feature_relations_snapshot", [])
```

- [ ] **Step 6: 跑測試確認通過**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/models/test_relation_summary_fields.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 7: 回歸既有 snapshot 測試**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/core/diff -q`
Expected: PASS（既有 snapshot 測試不受純加法影響）。

- [ ] **Step 8: Commit**
```bash
git add the_door/src/the_door/models/snapshot.py the_door/src/the_door/core/diff/snapshot_store.py the_door/tests/unit/models/test_relation_summary_fields.py
git commit -m "feat(snapshot): persist relation_type/inferred_reason on RelationSummary (additive)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: snapshot_write 接受並持久化 relation_type / inferred_reason

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/snapshot_write_tool.py:74-85`（schema）、`321-328`（解析）
- Test: `the_door/tests/unit/mcp/test_snapshot_write_relation_type.py`

- [ ] **Step 1: 寫失敗測試**

Create `the_door/tests/unit/mcp/test_snapshot_write_relation_type.py`:
```python
"""snapshot_write 接受 relation_type/inferred_reason 並持久化；舊 payload 仍相容。"""
import tempfile

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.mcp.tools import snapshot_write_tool


def _args(relations):
    return {
        "codebase_path": tempfile.mkdtemp(),
        "l1_features": [
            {"feature_id": "feat-a", "label": "A", "description": "d",
             "confidence": "high", "source_nodes": ["X.m"]},
            {"feature_id": "feat-b", "label": "B", "description": "d",
             "confidence": "high", "source_nodes": ["Y.n"]},
        ],
        "relations": relations,
        "label": "v1",
    }


@pytest.mark.asyncio
async def test_snapshot_write_persists_relation_type():
    args = _args([{"from_feature": "feat-a", "to_feature": "feat-b",
                   "relation": "depends_on", "relation_type": "static"}])
    result = await snapshot_write_tool.execute(args)
    assert "error" not in result, result
    snap = SnapshotStore(args["codebase_path"]).get_snapshot(result["version_id"])
    rel = snap.feature_relations_snapshot[0]
    assert rel.relation_type == "static"


@pytest.mark.asyncio
async def test_snapshot_write_legacy_relation_without_type_ok():
    args = _args([{"from_feature": "feat-a", "to_feature": "feat-b",
                   "relation": "depends_on"}])
    result = await snapshot_write_tool.execute(args)
    assert "error" not in result, result
    snap = SnapshotStore(args["codebase_path"]).get_snapshot(result["version_id"])
    assert snap.feature_relations_snapshot[0].relation_type is None
```

> 註：C2/C3 gate（需先 `edge_residue` 蓋章）是**外部 Claude Code PreToolUse hook**、攔的是 MCP「工具呼叫」，**不在** `execute()` 函式內（已查證 `snapshot_write_tool.execute` 開頭無 checklist 檢查）。本測試**直接呼叫 `execute()`**，故繞過該 hook、不受 gate 影響、可正常通過。

- [ ] **Step 2: 跑測試確認失敗**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_write_relation_type.py -v`
Expected: FAIL（持久化的 `relation_type` 為 None，因解析未帶該欄）。

- [ ] **Step 3: schema 加兩欄**

`the_door/src/the_door/mcp/tools/snapshot_write_tool.py` 的 relations schema（行 74-85）改成：
```python
        "relations": {
            "type": "array",
            "description": "Feature-level dependency relations. Each item: from_feature, to_feature, relation (str), 選填 relation_type ('static'|'inferred') 與 inferred_reason。relation_type='static'＝期待此依賴在程式碼有實連（integration_check 會驗證）；'inferred'＝概念/流程關係、附 inferred_reason、不查邊。",
            "items": {
                "type": "object",
                "required": ["from_feature", "to_feature", "relation"],
                "properties": {
                    "from_feature": {"type": "string"},
                    "to_feature": {"type": "string"},
                    "relation": {"type": "string"},
                    "relation_type": {"type": "string", "enum": ["static", "inferred"]},
                    "inferred_reason": {"type": "string"},
                },
            },
        },
```

- [ ] **Step 4: 解析帶兩欄**

同檔解析區（行 321-328）改成：
```python
        relations = [
            RelationSummary(
                from_feature=r["from_feature"],
                to_feature=r["to_feature"],
                relation=r["relation"],
                relation_type=r.get("relation_type"),
                inferred_reason=r.get("inferred_reason"),
            )
            for r in raw_relations
        ]
```

- [ ] **Step 5: 跑測試確認通過**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_write_relation_type.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 6: Commit**
```bash
git add the_door/src/the_door/mcp/tools/snapshot_write_tool.py the_door/tests/unit/mcp/test_snapshot_write_relation_type.py
git commit -m "feat(snapshot_write): accept+persist relation_type/inferred_reason" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: integration_check 工具（classifier + execute）

**Files:**
- Create: `the_door/src/the_door/mcp/tools/integration_check_tool.py`
- Test: `the_door/tests/unit/mcp/test_integration_check_tool.py`

- [ ] **Step 1: 寫失敗測試（涵蓋五類判定 + max_hops 邊界）**

Create `the_door/tests/unit/mcp/test_integration_check_tool.py`:
```python
"""integration_check 分類器與 execute 測試。"""
import gzip
import json
import tempfile
from pathlib import Path

import pytest

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.mcp.tools import integration_check_tool as ic
from the_door.models import FeatureSummary, RelationSummary


# ---- 純函式：分類器（不碰磁碟）----
def _adj(edges):
    a = {}
    for e in edges:
        a.setdefault(e["from"], set()).add(e["to"])
    return a


def test_static_backed_direct_edge():
    l1 = {"a": ["A.m"], "b": ["B.n"]}
    edges = [{"from": "A.m", "to": "B.n"}]
    rel = {"from_feature": "a", "to_feature": "b", "relation_type": "static"}
    out = ic.classify_relation(rel, l1, {"A.m", "B.n"}, _adj(edges), max_hops=2)
    assert out["verdict"] == "backed"
    assert out["evidence_path"] == ["A.m", "B.n"]


def test_static_gap_no_path():
    l1 = {"a": ["A.m"], "b": ["B.n"]}
    rel = {"from_feature": "a", "to_feature": "b", "relation_type": "static"}
    out = ic.classify_relation(rel, l1, {"A.m", "B.n"}, _adj([]), max_hops=2)
    assert out["verdict"] == "gap"


def test_static_gap_when_beyond_max_hops():
    # A.m -> M.x -> B.n 需 2 跳；max_hops=1 時應為 gap
    l1 = {"a": ["A.m"], "b": ["B.n"]}
    edges = [{"from": "A.m", "to": "M.x"}, {"from": "M.x", "to": "B.n"}]
    rel = {"from_feature": "a", "to_feature": "b", "relation_type": "static"}
    nodes = {"A.m", "M.x", "B.n"}
    assert ic.classify_relation(rel, l1, nodes, _adj(edges), max_hops=1)["verdict"] == "gap"
    assert ic.classify_relation(rel, l1, nodes, _adj(edges), max_hops=2)["verdict"] == "backed"


def test_static_undetermined_target_not_in_graph():
    l1 = {"a": ["A.m"], "b": ["B.n"]}  # B.n 不在 graph_nodes
    rel = {"from_feature": "a", "to_feature": "b", "relation_type": "static"}
    out = ic.classify_relation(rel, l1, {"A.m"}, _adj([]), max_hops=2)
    assert out["verdict"] == "undetermined"


def test_inferred_is_conceptual_not_edge_checked():
    l1 = {"a": ["A.m"], "b": ["B.n"]}
    rel = {"from_feature": "a", "to_feature": "b",
           "relation_type": "inferred", "inferred_reason": "概念先後"}
    out = ic.classify_relation(rel, l1, {"A.m", "B.n"}, _adj([]), max_hops=2)
    assert out["verdict"] == "conceptual"
    assert out["inferred_reason"] == "概念先後"


def test_untyped_is_not_assessed():
    l1 = {"a": ["A.m"], "b": ["B.n"]}
    rel = {"from_feature": "a", "to_feature": "b"}  # 無 relation_type
    out = ic.classify_relation(rel, l1, {"A.m", "B.n"}, _adj([]), max_hops=2)
    assert out["verdict"] == "not_assessed"


# ---- execute：整合（建一個有 structure 與 snapshot 的暫時 codebase）----
def _feat(fid, nodes):
    return FeatureSummary(feature_id=fid, label=fid, description="d",
                          source_node_count=len(nodes), confidence="high",
                          source_nodes=tuple(nodes))


def _write_structure(cp, nodes, edges):
    p = Path(cp) / ".the-door" / "structure-view"
    p.mkdir(parents=True, exist_ok=True)
    data = {"nodes": [{"node_id": n} for n in nodes],
            "edges": [{"from": f, "to": t, "type": "calls", "resolution": "scope_rule"}
                      for f, t in edges]}
    with gzip.open(p / "structure.full.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(data, fh)


@pytest.mark.asyncio
async def test_execute_end_to_end_rollup():
    cp = tempfile.mkdtemp()
    _write_structure(cp, nodes=["U.save", "DB.q", "O.create"],
                     edges=[("O.create", "DB.q")])
    store = SnapshotStore(cp)
    snap = store.create_snapshot(
        l1_snapshot={"feat-user": _feat("feat-user", ["U.save"]),
                     "feat-db": _feat("feat-db", ["DB.q"]),
                     "feat-order": _feat("feat-order", ["O.create"])},
        feature_relations=[
            RelationSummary("feat-user", "feat-db", "depends_on", relation_type="static"),
            RelationSummary("feat-order", "feat-db", "depends_on", relation_type="static"),
        ],
        analyzed_files=[], commit_hash=None, git_tags=[], trigger="manual", label="v1",
    )
    out = await ic.execute({"codebase_path": cp, "version_ref": "v1"})
    assert "error" not in out, out
    verdicts = {(r["from_feature"], r["to_feature"]): r["verdict"] for r in out["relations"]}
    assert verdicts[("feat-user", "feat-db")] == "gap"
    assert verdicts[("feat-order", "feat-db")] == "backed"
    assert out["rollup"]["gap"] == 1
    assert out["rollup"]["backed"] == 1


@pytest.mark.asyncio
async def test_execute_errors_without_structure():
    cp = tempfile.mkdtemp()
    store = SnapshotStore(cp)
    store.create_snapshot(l1_snapshot={"feat-a": _feat("feat-a", ["A.m"])},
                          feature_relations=[], analyzed_files=[], commit_hash=None,
                          git_tags=[], trigger="manual", label="v1")
    out = await ic.execute({"codebase_path": cp, "version_ref": "v1"})
    assert "error" in out
    assert "structure" in out["error"].lower()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_integration_check_tool.py -v`
Expected: FAIL（`integration_check_tool` 模組/函式不存在）。

- [ ] **Step 3: 實作工具**

Create `the_door/src/the_door/mcp/tools/integration_check_tool.py`:
```python
"""MCP tool: integration_check — 驗證功能宣稱依賴 (static) 是否有結構連線支撐。

判定（per relation）：
- static + 有 ≤max_hops 跳 edge path → "backed"（附 evidence_path）
- static + 無路徑                     → "gap"
- static + 目標 feature 節點不在結構圖 → "undetermined"
- inferred                            → "conceptual"（回報 inferred_reason，不查邊）
- 無 relation_type（舊資料）           → "not_assessed"
"""
from __future__ import annotations

import gzip
import json
from collections import deque
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "version_ref"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root."},
        "version_ref": {"type": "string",
                        "description": "Snapshot ref: label / git tag / date / commit SHA / version_id."},
        "max_hops": {"type": "integer", "minimum": 1, "default": 2,
                     "description": "static 關係的 edge path 最大跳數（1=只認直接邊）。"},
    },
}


def _path_within_hops(from_nodes, to_nodes, adjacency, max_hops):
    """回傳第一條 ≤max_hops 跳（邊數）的路徑 node 列表；找不到回 None。"""
    if not from_nodes or not to_nodes:
        return None
    to_set = set(to_nodes)
    visited = set(from_nodes)
    queue = deque((n, [n]) for n in from_nodes)
    while queue:
        cur, path = queue.popleft()
        if cur in to_set:
            return path
        if len(path) - 1 >= max_hops:
            continue
        for nxt in adjacency.get(cur, ()):
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [nxt]))
    return None


def classify_relation(rel, l1, graph_nodes, adjacency, max_hops):
    """rel: {from_feature,to_feature,relation_type?,inferred_reason?}；l1: feature_id->list(node_id)。"""
    base = {"from_feature": rel.get("from_feature"), "to_feature": rel.get("to_feature")}
    rtype = rel.get("relation_type")
    if not rtype:
        return {**base, "verdict": "not_assessed"}
    if rtype == "inferred":
        return {**base, "verdict": "conceptual", "inferred_reason": rel.get("inferred_reason")}
    # static
    from_nodes = l1.get(rel.get("from_feature"), [])
    to_nodes = l1.get(rel.get("to_feature"), [])
    present_to = set(to_nodes) & set(graph_nodes)
    if not present_to:
        return {**base, "verdict": "undetermined",
                "evidence": "target feature has no nodes in the structure graph"}
    path = _path_within_hops(from_nodes, present_to, adjacency, max_hops)
    if path is not None:
        return {**base, "verdict": "backed", "evidence_path": path}
    return {**base, "verdict": "gap",
            "evidence": f"no edge path within {max_hops} hop(s)"}


def _load_structure(codebase_path):
    gz = Path(codebase_path) / ".the-door" / "structure-view" / "structure.full.json.gz"
    if not gz.is_file():
        return None
    with gzip.open(gz, "rt", encoding="utf-8") as f:
        data = json.load(f)
    edges = data.get("edges", [])
    nodes = {n["node_id"] for n in data.get("nodes", [])}
    adjacency = {}
    for e in edges:
        adjacency.setdefault(e["from"], set()).add(e["to"])
    return nodes, adjacency


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    version_ref = arguments.get("version_ref")
    max_hops = arguments.get("max_hops", 2)
    if not codebase_path:
        return {"error": "codebase_path is required"}
    if not version_ref:
        return {"error": "version_ref is required"}

    store = SnapshotStore(codebase_path)
    try:
        snap = store.resolve_baseline(version_ref)
    except Exception:
        try:
            snap = store.get_snapshot(version_ref)
        except Exception as e:
            return {"error": f"snapshot {version_ref!r} not found: {e}"}

    loaded = _load_structure(codebase_path)
    if loaded is None:
        return {"error": "no structure.full.json.gz found — run extract_structure first"}
    graph_nodes, adjacency = loaded

    l1 = {fid: list(fs.source_nodes) for fid, fs in snap.l1_snapshot.items()}
    relations = []
    for r in snap.feature_relations_snapshot:
        rel = {"from_feature": r.from_feature, "to_feature": r.to_feature,
               "relation_type": r.relation_type, "inferred_reason": r.inferred_reason}
        relations.append(classify_relation(rel, l1, graph_nodes, adjacency, max_hops))

    rollup = {}
    for v in ("backed", "gap", "undetermined", "conceptual", "not_assessed"):
        rollup[v] = sum(1 for r in relations if r["verdict"] == v)

    return {
        "version_ref": version_ref,
        "version_id": snap.version_id,
        "label": snap.label,
        "max_hops": max_hops,
        "relations": relations,
        "rollup": rollup,
    }
```

- [ ] **Step 4: 跑測試確認通過**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_integration_check_tool.py -v`
Expected: PASS（8 passed）。

- [ ] **Step 5: Commit**
```bash
git add the_door/src/the_door/mcp/tools/integration_check_tool.py the_door/tests/unit/mcp/test_integration_check_tool.py
git commit -m "feat(mcp): add integration_check tool (claimed-vs-actual dependency verdict)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 在 MCP server 註冊 integration_check

**Files:**
- Modify: `the_door/src/the_door/mcp/server.py`（import、`_build_tools()` 行 ~185、dispatch 行 ~248-251）
- Test: `the_door/tests/unit/mcp/test_integration_check_tool.py`（加註冊測試）

- [ ] **Step 1: 寫失敗測試（工具已註冊）**

在 `the_door/tests/unit/mcp/test_integration_check_tool.py` 末端追加：
```python
def test_integration_check_registered():
    from the_door.mcp.server import REGISTERED_TOOL_NAMES
    assert "integration_check" in REGISTERED_TOOL_NAMES
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_integration_check_tool.py::test_integration_check_registered -v`
Expected: FAIL（未註冊）。

- [ ] **Step 3: import 工具模組**

`the_door/src/the_door/mcp/server.py`，在既有 `from the_door.mcp.tools import (...)` 群組（與 `edge_residue_tool` 同處）加入 `integration_check_tool`。若 import 是逐行式，新增一行：
```python
from the_door.mcp.tools import integration_check_tool
```
（放在其他 `*_tool` import 旁，維持風格。）

- [ ] **Step 4: 在 _build_tools() 註冊 Tool**

在 `_build_tools()` 的 tools 清單（`the_door/src/the_door/mcp/server.py` 行 ~185 的 `]` 之前），與其他 `Tool(...)` 並列，新增：
```python
        Tool(
            name="integration_check",
            description="Verify each feature's claimed 'static' dependency against the actual structure graph; returns backed/gap/undetermined per relation + rollup.",
            inputSchema=integration_check_tool.TOOL_SCHEMA,
        ),
```

- [ ] **Step 5: 在 call_tool dispatch 加分支**

同檔 dispatch（行 ~248-250，`edge_residue` 分支之後、`else` 之前）新增：
```python
            elif name == "integration_check":
                return await self._dispatch_tool(integration_check_tool, arguments)
```

- [ ] **Step 6: 跑測試確認通過 + MCP 測試回歸**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_integration_check_tool.py -v`
Expected: PASS（9 passed）。
Run: `PYTHONUTF8=1 python -m pytest tests/unit/mcp -q`
Expected: PASS（既有 MCP 測試不受影響）。

- [ ] **Step 7: Commit**
```bash
git add the_door/src/the_door/mcp/server.py the_door/tests/unit/mcp/test_integration_check_tool.py
git commit -m "feat(mcp): register integration_check in server tool table + dispatch" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 文件——CLAUDE.md 工具表 + relations 寫法 + 非循環守則

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 工具參考表加一列**

在 `CLAUDE.md` 的「Commands & MCP tool reference」表格（`snapshot_patch` / `analyze_changes` 那幾列附近）新增：
```markdown
| `integration_check` MCP | 驗證每條功能宣稱依賴（標 `static` 者）是否有結構連線支撐 → 逐條回 backed/gap/undetermined + rollup。讀持久化 typed relations + structure-view edges、現算、`max_hops` 預設 2。 |
```

- [ ] **Step 2: relations 寫法補 relation_type**

在 agent-as-LLM chain 的 `relations` 說明（"`relations`" 物件範例附近，single-version chain 第 2 步）補一段：
```markdown
   `relations` 每筆可選帶 `relation_type`（`static`|`inferred`）：
   - `static`＝你**期待**這條依賴在程式碼裡有實連（之後 `integration_check` 會去驗證它有沒有真的接上）。**期待來自功能語意/意圖，不是「你看到有邊才標」**——落差正是「期待 static 但結構沒有」時才有意義。
   - `inferred`＝概念/流程關係（未必有直接呼叫邊），須附 `inferred_reason` 一句話；`integration_check` 不對它查邊、不喊狼。
   - 不標＝`integration_check` 標 `not_assessed`。
```

- [ ] **Step 3: 驗證文件無壞連結/格式**

Run（cwd 主 repo `C:/Users/Ric/Desktop/the_door`）：
```bash
grep -n "integration_check" CLAUDE.md
```
Expected: 至少 2 處命中（工具表 + relations 說明）。

- [ ] **Step 4: Commit**
```bash
git add CLAUDE.md
git commit -m "docs(claude): document integration_check tool + relation_type usage + non-circularity rule" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec(§9) coverage：**
- §9.1 加法持久化（model+序列化+不 bump contract+舊資料相容）→ Task 1 ✓
- §9.1 snapshot_write 接受 relation_type → Task 2 ✓
- §9.2 工具五態判定 + max_hops + 證據 + rollup → Task 3 ✓
- §9.3 非循環守則（guide 級）→ Task 5 Step 2（relation_type=期待、非讀邊）✓
- §9.4 註冊 + 文件 → Task 4（server）+ Task 5（CLAUDE.md）✓
- §9.5 測試（static/inferred/untyped/非程式碼節點 + max_hops 邊界 + snapshot_write 回歸）→ Task 3 Step 1 六個分類器測試 + Task 1/2 回歸 ✓
- §9.6 前端 UX → 明列範圍外、不在本計畫 ✓

**2. Placeholder scan：** 無 TBD/TODO；每個 code step 有完整程式碼、確切預期輸出。

**3. Type/簽名一致性：**
- `RelationSummary(from_feature, to_feature, relation, relation_type=None, inferred_reason=None)` — Task 1 定義，Task 2 解析、Task 3 讀取一致。✓
- `classify_relation(rel, l1, graph_nodes, adjacency, max_hops)` 與 `_path_within_hops(from_nodes, to_nodes, adjacency, max_hops)` — Task 3 定義與測試呼叫一致。✓
- verdict 字串 `backed/gap/undetermined/conceptual/not_assessed` — Task 3 實作、測試、rollup 五者一致。✓
- 工具模組契約 `TOOL_SCHEMA` + `async def execute(arguments)->dict`，server 用 `_dispatch_tool` — 對齊 `edge_residue_tool` 既有模式。✓
- `SnapshotStore(cp).resolve_baseline(ref)` / `.get_snapshot(ref)` / `.create_snapshot(...)` — 對齊 `analyze_changes_tool` 與 `snapshot_store` 既有 API。✓

> **誠實邊界**：C2/C3 gate 是外部 PreToolUse hook、攔 MCP 工具呼叫，**不在** `execute()` 內（已查證），故所有單元測試直接呼叫 `execute()` 不受 gate 影響。實機（透過 MCP）跑 `snapshot_write` 時仍需先 `edge_residue` 蓋章——這是既有行為、與本計畫無關。
