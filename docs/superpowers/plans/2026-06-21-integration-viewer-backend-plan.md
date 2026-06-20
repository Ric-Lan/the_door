# 整合健檢 viewer — 後端 Plan（共用 core + /api/integration）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** 把 `integration_check` 判定邏輯抽到 `core/integration/checker.py`（MCP 工具與 viewer API 共用），並開 `GET /api/integration` 端點，回傳單一 payload（relations + per-feature 徽章聚合 + rollup）。

**Architecture:** 抽出純函式 + 一個 `run_integration_check(snapshot, codebase_path, max_hops)` 組裝函式到 core；MCP 工具 `execute` 改為「解析 snapshot → 呼叫 core」（行為不變、re-export 舊符號保既有測試綠）；新增 `IntegrationHandlers.get_integration`（比照 `graph.py get_l1`），掛進 `build_routes` 並在 `server.py` 與 `_gen_docs.py` 接線。

**Tech Stack:** Python 3.12、pytest。

**對應 spec：** [`docs/superpowers/specs/2026-06-21-integration-viewer-design.md`](../specs/2026-06-21-integration-viewer-design.md) §3.1–§3.2、§5。

## 環境
- pytest cwd ＝ `C:/Users/Ric/Desktop/the_door/the_door`；前置 `PYTHONUTF8=1`；測試走 `python -m pytest`（C4 hook 禁 `python -c`）。
- branch 護欄：commit 前 `git rev-parse --abbrev-ref HEAD` 須為 `feat/integration-viewer`；不切分支、不 cd 出 repo。
- commit 結尾 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。不 bump contract。

## File Structure
- Create: `the_door/src/the_door/core/integration/__init__.py`、`checker.py`
- Modify: `the_door/src/the_door/mcp/tools/integration_check_tool.py`（改 import core + 薄 execute）
- Create: `the_door/src/the_door/core/ui/api/handlers/integration.py`
- Modify: `the_door/src/the_door/core/ui/api/router.py`（`build_routes` 加 `ig` + 一條 Route）
- Modify: `the_door/src/the_door/core/ui/server.py`（建 `IntegrationHandlers` + 傳入）、`the_door/src/the_door/core/ui/api/_gen_docs.py`（同步加參數）
- Test: `the_door/tests/unit/core/integration/test_checker.py`、`the_door/tests/unit/core/ui/test_integration_handler.py`

---

### Task 1: 抽 checker 到 core + 聚合/組裝函式

**Files:**
- Create: `the_door/src/the_door/core/integration/__init__.py`（空）
- Create: `the_door/src/the_door/core/integration/checker.py`
- Modify: `the_door/src/the_door/mcp/tools/integration_check_tool.py`
- Test: `the_door/tests/unit/core/integration/test_checker.py`

- [ ] **Step 1: 寫失敗測試（聚合 + 組裝）**

Create `the_door/tests/unit/core/integration/test_checker.py`:
```python
"""core/integration/checker：per-feature 聚合 + run_integration_check 組裝。"""
import gzip
import json
import tempfile
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.integration import checker
from the_door.models import FeatureSummary, RelationSummary


def test_aggregate_features_precedence():
    rels = [
        {"from_feature": "a", "verdict": "backed"},
        {"from_feature": "a", "verdict": "gap"},       # a 有 gap → gap 優先
        {"from_feature": "b", "verdict": "backed"},
        {"from_feature": "c", "verdict": "undetermined"},
        {"from_feature": "d", "verdict": "conceptual"},  # 只有概念 → none
    ]
    out = checker.aggregate_features(rels)
    assert out == {"a": "gap", "b": "backed", "c": "undetermined", "d": "none"}


def _feat(fid, nodes):
    return FeatureSummary(feature_id=fid, label=fid, description="d",
                          source_node_count=len(nodes), confidence="high",
                          source_nodes=tuple(nodes))


def _write_structure(cp, nodes, edges):
    p = Path(cp) / ".the-door" / "structure-view"
    p.mkdir(parents=True, exist_ok=True)
    data = {"nodes": [{"node_id": n} for n in nodes],
            "edges": [{"from": f, "to": t} for f, t in edges]}
    with gzip.open(p / "structure.full.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(data, fh)


def test_run_integration_check_payload():
    cp = tempfile.mkdtemp()
    _write_structure(cp, ["U.save", "DB.q", "O.create"], [("O.create", "DB.q")])
    store = SnapshotStore(Path(cp))
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
    out = checker.run_integration_check(snap, cp, max_hops=2)
    assert out["features"]["feat-user"] == "gap"
    assert out["features"]["feat-order"] == "backed"
    assert out["rollup"]["gap"] == 1 and out["rollup"]["backed"] == 1
    assert {r["from_feature"] for r in out["relations"]} == {"feat-user", "feat-order"}


def test_run_integration_check_structure_missing():
    cp = tempfile.mkdtemp()
    store = SnapshotStore(Path(cp))
    snap = store.create_snapshot(l1_snapshot={"feat-a": _feat("feat-a", ["A.m"])},
                                 feature_relations=[], analyzed_files=[], commit_hash=None,
                                 git_tags=[], trigger="manual", label="v1")
    out = checker.run_integration_check(snap, cp, max_hops=2)
    assert out["structure_missing"] is True
    assert out["relations"] == [] and out["rollup"]["gap"] == 0
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/core/integration/test_checker.py -v`
Expected: FAIL（`the_door.core.integration` 不存在）。

- [ ] **Step 3: 建 core 模組（搬移 + 新增聚合/組裝）**

Create `the_door/src/the_door/core/integration/__init__.py`（空檔）。

Create `the_door/src/the_door/core/integration/checker.py`（把現有三個函式從 `mcp/tools/integration_check_tool.py` 原樣搬來，再加 `aggregate_features` 與 `run_integration_check`）:
```python
"""整合落差判定核心（MCP 工具與 viewer API 共用、純結構、零 agent）。"""
from __future__ import annotations

import gzip
import json
from collections import deque
from pathlib import Path

_VERDICTS = ("backed", "gap", "undetermined", "conceptual", "not_assessed")


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
    base = {"from_feature": rel.get("from_feature"), "to_feature": rel.get("to_feature")}
    rtype = rel.get("relation_type")
    if not rtype:
        return {**base, "verdict": "not_assessed"}
    if rtype == "inferred":
        return {**base, "verdict": "conceptual", "inferred_reason": rel.get("inferred_reason")}
    from_nodes = l1.get(rel.get("from_feature"), [])
    to_nodes = l1.get(rel.get("to_feature"), [])
    present_to = set(to_nodes) & set(graph_nodes)
    if not present_to:
        return {**base, "verdict": "undetermined",
                "evidence": "target feature has no nodes in the structure graph"}
    path = _path_within_hops(from_nodes, present_to, adjacency, max_hops)
    if path is not None:
        return {**base, "verdict": "backed", "evidence_path": path}
    return {**base, "verdict": "gap", "evidence": f"no edge path within {max_hops} hop(s)"}


def _load_structure(codebase_path):
    gz = Path(codebase_path) / ".the-door" / "structure-view" / "structure.full.json.gz"
    if not gz.is_file():
        return None
    with gzip.open(gz, "rt", encoding="utf-8") as f:
        data = json.load(f)
    nodes = {n["node_id"] for n in data.get("nodes", [])}
    adjacency = {}
    for e in data.get("edges", []):
        adjacency.setdefault(e["from"], set()).add(e["to"])
    return nodes, adjacency


def aggregate_features(relations):
    """per-feature 徽章：以 from_feature 聚合 outgoing 判定。
    優先序 gap > undetermined > backed > none（只剩 conceptual/not_assessed）。"""
    by_feat: dict[str, list[str]] = {}
    for r in relations:
        by_feat.setdefault(r["from_feature"], []).append(r["verdict"])
    out = {}
    for ff, verds in by_feat.items():
        if "gap" in verds:
            out[ff] = "gap"
        elif "undetermined" in verds:
            out[ff] = "undetermined"
        elif "backed" in verds:
            out[ff] = "backed"
        else:
            out[ff] = "none"
    return out


def run_integration_check(snapshot, codebase_path, max_hops=2):
    """組裝單一 payload：relations[] + features{} 聚合 + rollup。結構缺檔回 structure_missing。"""
    loaded = _load_structure(codebase_path)
    if loaded is None:
        return {"relations": [], "features": {},
                "rollup": {v: 0 for v in _VERDICTS}, "structure_missing": True}
    graph_nodes, adjacency = loaded
    l1 = {fid: list(fs.source_nodes) for fid, fs in snapshot.l1_snapshot.items()}
    relations = []
    for r in snapshot.feature_relations_snapshot:
        rel = {"from_feature": r.from_feature, "to_feature": r.to_feature,
               "relation_type": r.relation_type, "inferred_reason": r.inferred_reason}
        relations.append(classify_relation(rel, l1, graph_nodes, adjacency, max_hops))
    rollup = {v: sum(1 for r in relations if r["verdict"] == v) for v in _VERDICTS}
    return {"relations": relations, "features": aggregate_features(relations), "rollup": rollup}
```

- [ ] **Step 4: 工具改 import core（re-export 保既有測試）+ 薄 execute**

把 `the_door/src/the_door/mcp/tools/integration_check_tool.py` 的三個函式定義**刪除**，改為從 core import（re-export，讓既有 `ic.classify_relation` 等仍可用），並讓 `execute` 呼叫 core。完整新內容：
```python
"""MCP tool: integration_check — 驗證功能宣稱依賴 (static) 是否有結構連線支撐。

判定邏輯住在 the_door.core.integration.checker（與 viewer API 共用）；
本檔保留 MCP schema 與薄 execute（解析 snapshot ref → 呼叫 core）。
"""
from __future__ import annotations

from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.integration.checker import (  # re-export：保既有測試的 ic.* 可用
    _load_structure,
    _path_within_hops,
    aggregate_features,
    classify_relation,
    run_integration_check,
)

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


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    version_ref = arguments.get("version_ref")
    max_hops = arguments.get("max_hops", 2)
    if not codebase_path:
        return {"error": "codebase_path is required"}
    if not version_ref:
        return {"error": "version_ref is required"}
    store = SnapshotStore(Path(codebase_path))
    try:
        snap = store.resolve_baseline(version_ref)
    except Exception as e:
        return {"error": f"snapshot {version_ref!r} not found: {e}"}
    payload = run_integration_check(snap, codebase_path, max_hops)
    if payload.get("structure_missing"):
        return {"error": "no structure.full.json.gz found — run extract_structure first"}
    return {"version_ref": version_ref, "version_id": snap.version_id,
            "label": snap.label, "max_hops": max_hops, **payload}
```

- [ ] **Step 5: 跑新測試 + 既有工具測試回歸**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/core/integration/test_checker.py tests/unit/mcp/test_integration_check_tool.py -v`
Expected: PASS（新 4 + 既有 9 = 13 passed）。既有工具測試靠 re-export 仍綠；其 execute E2E 多了 `features` 鍵（additive、不影響既有斷言）。

- [ ] **Step 6: Commit**
```bash
git add the_door/src/the_door/core/integration/ the_door/src/the_door/mcp/tools/integration_check_tool.py the_door/tests/unit/core/integration/
git commit -m "refactor(integration): extract checker to core + feature aggregation/run helper" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: /api/integration 端點（handler + route + 接線）

**Files:**
- Create: `the_door/src/the_door/core/ui/api/handlers/integration.py`
- Modify: `the_door/src/the_door/core/ui/api/router.py`（`build_routes`）
- Modify: `the_door/src/the_door/core/ui/server.py`、`the_door/src/the_door/core/ui/api/_gen_docs.py`
- Test: `the_door/tests/unit/core/ui/test_integration_handler.py`

- [ ] **Step 1: 寫失敗測試**

Create `the_door/tests/unit/core/ui/test_integration_handler.py`:
```python
"""IntegrationHandlers.get_integration：有 gap 的 snapshot → 正確 payload；空狀態誠實。"""
import gzip
import json
import tempfile
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.integration import IntegrationHandlers
from the_door.models import FeatureSummary, RelationSummary


def _feat(fid, nodes):
    return FeatureSummary(feature_id=fid, label=fid, description="d",
                          source_node_count=len(nodes), confidence="high",
                          source_nodes=tuple(nodes))


def _ctx(root):
    return APIContext(lambda: Path(root), lambda *_a, **_k: None)


def _seed(cp):
    p = Path(cp) / ".the-door" / "structure-view"
    p.mkdir(parents=True, exist_ok=True)
    with gzip.open(p / "structure.full.json.gz", "wt", encoding="utf-8") as fh:
        json.dump({"nodes": [{"node_id": "U.save"}, {"node_id": "DB.q"}],
                   "edges": []}, fh)
    store = SnapshotStore(Path(cp))
    return store.create_snapshot(
        l1_snapshot={"feat-user": _feat("feat-user", ["U.save"]),
                     "feat-db": _feat("feat-db", ["DB.q"])},
        feature_relations=[RelationSummary("feat-user", "feat-db", "depends_on",
                                           relation_type="static")],
        analyzed_files=[], commit_hash=None, git_tags=[], trigger="manual", label="v1")


def test_get_integration_returns_payload():
    cp = tempfile.mkdtemp()
    snap = _seed(cp)
    status, body = IntegrationHandlers(_ctx(cp)).get_integration(version_id=snap.version_id)
    assert status == 200
    assert body["features"]["feat-user"] == "gap"
    assert body["rollup"]["gap"] == 1


def test_get_integration_latest_when_no_version():
    cp = tempfile.mkdtemp()
    _seed(cp)
    status, body = IntegrationHandlers(_ctx(cp)).get_integration()
    assert status == 200
    assert "rollup" in body
```

> 已驗證：`APIContext(_project_root_fn: Callable[[],Path], _switch_project_fn: Callable[[str,bool],Any])`（`context.py:16-30`），`.project_root` 是 property。測試的 `_ctx` 正確。

- [ ] **Step 2: 跑測試確認失敗**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/core/ui/test_integration_handler.py -v`
Expected: FAIL（handler 模組不存在）。

- [ ] **Step 3: 建 handler**

先讀 `the_door/src/the_door/core/ui/api/handlers/graph.py:33-95` 確認 `make_error_envelope`/`Remediation`/`NextAction` 的 import 與 404 envelope 寫法、以及 `self._ctx.project_root` / `store.get_latest()` 的用法（本 handler 比照它）。

Create `the_door/src/the_door/core/ui/api/handlers/integration.py`:
```python
"""IntegrationHandlers — GET /api/integration（純結構整合健檢、零 agent）。"""
from __future__ import annotations

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.guidance.remediation import Remediation, make_error_envelope
from the_door.core.integration.checker import run_integration_check
from the_door.core.ui.api.context import APIContext


class IntegrationHandlers:
    def __init__(self, ctx: APIContext) -> None:
        self._ctx = ctx

    def get_integration(self, ctx=None, *, version_id=None, **_) -> tuple[int, dict]:
        """GET /api/integration?version_id=<id> — per-relation 判定 + 徽章聚合 + rollup。"""
        store = SnapshotStore(self._ctx.project_root)
        snapshot = store.get_snapshot(version_id) if version_id else store.get_latest()
        if snapshot is None:
            msg = (f"Snapshot '{version_id}' not found." if version_id
                   else "尚未為這個專案產出 L1 分析")
            return 404, make_error_envelope(
                code="no_integration_data", message=msg,
                remediation=Remediation(code="no_integration_data", message=msg),
                source="get_integration",
            )
        payload = run_integration_check(snapshot, self._ctx.project_root, max_hops=2)
        return 200, payload
```

> 已驗證：`Remediation.next_action` 為選填（`= None`，`remediation.py:9`），故 `Remediation(code=, message=)` 合法；`make_error_envelope(code, message, remediation, source)` 對齊 graph.py 用法。上面 handler 程式碼可直接用。

- [ ] **Step 4: build_routes 加參數 + Route**

`the_door/src/the_door/core/ui/api/router.py` 的 `build_routes`（行 134）改簽名與表：
```python
def build_routes(p, c, g, d, n, gr, ig) -> list[Route]:
```
並在 return 清單適當位置（`/api/l1` 之後）加一行：
```python
        Route("GET",  "/api/integration",                         ig.get_integration, summary="當前版本的整合健檢（宣稱依賴 vs 結構連線）"),
```
同步更新 docstring 的 `p/c/g/d/n/gr` 說明補 `ig=Integration`。

- [ ] **Step 5: server.py 與 _gen_docs.py 接線**

`the_door/src/the_door/core/ui/server.py`：
- import 區加 `from the_door.core.ui.api.handlers.integration import IntegrationHandlers`（與其他 handler import 同處）。
- 行 54-61 的 `build_routes(...)` 末加一個引數：
```python
        routes = build_routes(
            ProjectHandlers(ctx),
            CatalogHandlers(ctx),
            GraphHandlers(ctx),
            DiffHandlers(ctx),
            AnnotationHandlers(ctx),
            GroupHandlers(ctx),
            IntegrationHandlers(ctx),
        )
```

`the_door/src/the_door/core/ui/api/_gen_docs.py`（已驗證：`main()` 在行 28-35 以 6 個 handler 呼叫 `build_routes`）：import 區加 `from the_door.core.ui.api.handlers.integration import IntegrationHandlers`，並在該 `build_routes(...)` 末加第 7 個引數 `IntegrationHandlers(ctx),`（否則 doc-gen 因參數數不符而壞）。

- [ ] **Step 6: 跑測試 + API 回歸**

Run: `PYTHONUTF8=1 python -m pytest tests/unit/core/ui/test_integration_handler.py -v`
Expected: PASS（2 passed）。
Run: `PYTHONUTF8=1 python -m pytest tests/unit/core/ui -q`
Expected: PASS（既有 router/handler 測試不受影響；若有「路由數」斷言，更新為 +1）。

- [ ] **Step 7: Commit**
```bash
git add the_door/src/the_door/core/ui/api/handlers/integration.py the_door/src/the_door/core/ui/api/router.py the_door/src/the_door/core/ui/server.py the_door/src/the_door/core/ui/api/_gen_docs.py the_door/tests/unit/core/ui/test_integration_handler.py
git commit -m "feat(ui-api): add GET /api/integration endpoint (shared core checker)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review
**1. Spec(§3.1-§3.2/§5) coverage：** 抽 core 共用 → Task 1；單一端點回 relations/features/rollup → Task 1(run_integration_check)+Task 2；空狀態誠實(structure_missing→面板未評估；handler 仍回 200 空 rollup) → Task 1/2 測試；純結構零 agent → checker 無 LLM 依賴 ✓。
**2. Placeholder scan：** 無 TBD。Plan-review 已逐一**查證**先前三個待讀點：APIContext 簽名（`context.py:16`）、Remediation.next_action 選填（`remediation.py:9`）、_gen_docs build_routes 6-handler 呼叫（`_gen_docs.py:28`）——皆已轉為確切程式碼、無 verify-later。
**3. Type 一致性：** `run_integration_check(snapshot, codebase_path, max_hops=2)->dict{relations,features,rollup[,structure_missing]}`；工具 re-export `classify_relation/_path_within_hops/_load_structure` 保既有測試；handler `get_integration(self, ctx=None, *, version_id=None, **_)` 對齊 `graph.py get_l1` 與 router dispatch（`route.handler(ctx, body=, **params, **query)`）。`build_routes` 7 參數同步更新 server.py + _gen_docs.py。

> **誠實邊界**：plan-review 後，後端三個待讀點（APIContext / Remediation / _gen_docs）皆已查證、程式碼可直接落地。剩餘唯一「先讀再接」＝前端 plan 的 `app.js` 載入/選取流程（見 frontend plan Task 4），那是必要的既有程式探查、非本後端 plan 範圍。
