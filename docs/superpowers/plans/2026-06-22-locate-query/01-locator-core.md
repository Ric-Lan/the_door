# Phase 1 — 核心 locator

> 父計畫：[../2026-06-22-locate-query-plan.md](../2026-06-22-locate-query-plan.md)
> 先讀父計畫的「關鍵事實」再動手。所有路徑相對 repo root；pytest 的 cwd 是內層 `the_door/`。

> **測試路徑慣例（已對齊 repo）**：此 repo 的測試鏡像原始碼結構。本 phase 的測試落點：
> 純函式 → `the_door/tests/unit/core/structure_view/test_locator.py`、
> freshness → `the_door/tests/unit/core/structure_view/test_locator_freshness.py`、
> 真實 fixture 整合 → `the_door/tests/integration/test_locator_fixture.py`。

核心模組 `the_door/src/the_door/core/structure_view/locator.py` 拆成可獨立測試的純函式：
`load_views`（IO）、`search_views` / `node_detail`（純）、`compute_freshness`（IO）、
`search` / `node`（compose）。純函式吃 synthetic views 測排序/邊界，IO 函式用真實 fixture 測。

---

### Task 1: `load_views` — 讀 region artifact 成記憶體表

**Files:**
- Create: `the_door/src/the_door/core/structure_view/locator.py`
- Test: `the_door/tests/unit/core/structure_view/test_locator.py`

- [ ] **Step 1: 先寫模組骨架（含錯誤型別與常數）**

建 `locator.py`：

```python
"""Locate Query: 對既有 structure-view artifact 做 symbol 定位點查。

輔助便利功能（secondary）。零重抽取——只讀持久化 artifact，不呼叫 ASTExtractor。
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from the_door.core.checklist import read_checklist
from the_door.core.structure_view.structure_index import view_dir

SEARCH_DEFAULT_LIMIT = 20
FRESHNESS_CHANGED_CAP = 20

_NO_ARTIFACTS_MSG = (
    "no structure-view artifacts; run extract_structure(codebase_path=...) first"
)


class LocateError(Exception):
    """定位查詢的可預期錯誤（artifact 缺、node 不存在、query 空）。"""


def load_views(codebase_path: str | Path) -> dict[str, dict]:
    """讀所有 regions/*.json.gz，回 {node_id: view}。缺 artifact → LocateError。"""
    regions_dir = view_dir(codebase_path) / "regions"
    if not regions_dir.is_dir():
        raise LocateError(_NO_ARTIFACTS_MSG)
    views: dict[str, dict] = {}
    for gz_path in sorted(regions_dir.glob("*.json.gz")):
        with gzip.open(gz_path, "rt", encoding="utf-8") as f:
            payload = json.load(f)
        for view in payload.get("nodes", []):
            views[view["node_id"]] = view
    if not views:
        raise LocateError(_NO_ARTIFACTS_MSG)
    return views
```

- [ ] **Step 2: 寫失敗測試（artifact 不存在）**

建 `the_door/tests/unit/core/structure_view/test_locator.py`：

```python
import pytest

from the_door.core.structure_view import locator


def test_load_views_missing_artifacts_raises(tmp_path):
    with pytest.raises(locator.LocateError, match="extract_structure"):
        locator.load_views(tmp_path)
```

- [ ] **Step 3: 跑測試確認通過（骨架已實作 load_views）**

Run: `python -m pytest tests/unit/core/structure_view/test_locator.py::test_load_views_missing_artifacts_raises -v`
Expected: PASS（tmp_path 無 structure-view → LocateError）

- [ ] **Step 4: Commit**

```bash
git add the_door/src/the_door/core/structure_view/locator.py the_door/tests/unit/core/structure_view/test_locator.py
git commit -m "feat(locator): add load_views over structure-view region artifacts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `search_views` — 純排序查詢

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/locator.py`
- Test: `the_door/tests/unit/core/structure_view/test_locator.py`

- [ ] **Step 1: 寫失敗測試（排序：name 命中優先於 path 命中，且壓過 in_degree）**

加到 `test_locator.py`。synthetic views 刻意讓 path 命中有較高 in_degree，驗證 name 仍排前：

```python
def _view(node_id, name, in_degree):
    return {
        "node_id": node_id, "name": name, "type": "function",
        "file": node_id.split("::")[0], "start_line": 1, "end_line": 2,
        "topology": {"in_degree": in_degree, "out_degree": 0,
                     "topology_rank": 0.0, "is_entry_point": False},
        "in_edges": [], "out_edges": [],
    }


def test_search_views_name_match_ranks_before_path_match():
    views = {
        # path 命中（檔名含 user）且 in_degree 高
        "user_service.py::handle": _view("user_service.py::handle", "handle", 99),
        # name 命中（叫 user）但 in_degree 低
        "x.py::user": _view("x.py::user", "user", 1),
    }
    out = locator.search_views(views, "user")
    assert [r["node_id"] for r in out["results"]] == ["x.py::user", "user_service.py::handle"]
    assert out["results"][0]["match_kind"] == "name"
    assert out["results"][1]["match_kind"] == "path"


def test_search_views_empty_query_raises():
    with pytest.raises(locator.LocateError, match="query is required"):
        locator.search_views({}, "   ")


def test_search_views_limit_truncates():
    views = {f"f.py::n{i}": _view(f"f.py::n{i}", f"n{i}", i) for i in range(5)}
    out = locator.search_views(views, "n", limit=2)
    assert out["total_matched"] == 5
    assert out["returned"] == 2
    assert len(out["results"]) == 2


def test_search_views_no_match_returns_empty():
    out = locator.search_views({"f.py::a": _view("f.py::a", "a", 0)}, "zzz")
    assert out["results"] == []
    assert out["total_matched"] == 0


def test_in_degree_handles_none_topology():
    v = {"node_id": "f.py::a", "name": "a", "type": "function", "file": "f.py",
         "start_line": 1, "end_line": 2, "topology": None, "in_edges": [], "out_edges": []}
    out = locator.search_views({"f.py::a": v}, "a")
    assert out["results"][0]["in_degree"] == 0
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/unit/core/structure_view/test_locator.py -k search_views -v`
Expected: FAIL（`search_views` 尚未定義 → AttributeError）

- [ ] **Step 3: 實作 `search_views` 與 `_in_degree`**

加到 `locator.py`：

```python
def _in_degree(view: dict) -> int:
    topo = view.get("topology")
    return topo.get("in_degree", 0) if isinstance(topo, dict) else 0


_KIND_RANK = {"name": 0, "path": 1}


def search_views(views: dict[str, dict], query: str,
                 limit: int = SEARCH_DEFAULT_LIMIT) -> dict:
    q = query.strip()
    if not q:
        raise LocateError("query is required")
    ql = q.lower()
    matched: list[tuple[str, dict, str]] = []
    for node_id, view in views.items():
        in_name = ql in (view.get("name") or "").lower()
        in_path = ql in node_id.lower()
        if not (in_name or in_path):
            continue
        matched.append(("name" if in_name else "path", view, node_id))
    matched.sort(key=lambda t: (_KIND_RANK[t[0]], -_in_degree(t[1]), t[2]))
    total = len(matched)
    results = [
        {
            "node_id": nid, "name": v.get("name"), "type": v.get("type"),
            "file": v.get("file"), "start_line": v.get("start_line"),
            "end_line": v.get("end_line"), "in_degree": _in_degree(v),
            "match_kind": mk,
        }
        for (mk, v, nid) in matched[:limit]
    ]
    return {"query": q, "total_matched": total,
            "returned": len(results), "results": results}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/unit/core/structure_view/test_locator.py -k search_views -v`
Expected: PASS（5 個測試全綠）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/locator.py the_door/tests/unit/core/structure_view/test_locator.py
git commit -m "feat(locator): add search_views with name>path>in_degree ranking

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `node_detail` — 單節點 callers/callees

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/locator.py`
- Test: `the_door/tests/unit/core/structure_view/test_locator.py`

- [ ] **Step 1: 寫失敗測試**

加到 `test_locator.py`：

```python
def test_node_detail_maps_callers_and_callees():
    views = {
        "a.py::caller": _view("a.py::caller", "caller", 0),
        "a.py::target": {
            "node_id": "a.py::target", "name": "target", "type": "function",
            "file": "a.py", "language": "python", "start_line": 5, "end_line": 9,
            "topology": {"in_degree": 1, "out_degree": 1, "topology_rank": 0.5,
                         "is_entry_point": False},
            "in_edges": [{"from_node_id": "a.py::caller", "type": "calls",
                          "resolution": "scope_rule"}],
            "out_edges": [{"to_node_id": "b.py::callee", "type": "calls",
                           "resolution": "scope_rule"}],
        },
        "b.py::callee": _view("b.py::callee", "callee", 1),
    }
    out = locator.node_detail(views, "a.py::target")
    assert out["node_id"] == "a.py::target"
    assert out["callers"][0]["node_id"] == "a.py::caller"
    assert out["callers"][0]["file"] == "a.py"        # 對端可解析 → 附 file
    assert out["callees"][0]["node_id"] == "b.py::callee"


def test_node_detail_unresolved_edge_target_is_fail_soft():
    views = {
        "a.py::t": {
            "node_id": "a.py::t", "name": "t", "type": "function", "file": "a.py",
            "language": "python", "start_line": 1, "end_line": 2, "topology": None,
            "in_edges": [], "out_edges": [{"to_node_id": "ghost::x", "type": "calls",
                                           "resolution": "scope_rule"}],
        },
    }
    out = locator.node_detail(views, "a.py::t")
    assert out["callees"][0]["node_id"] == "ghost::x"
    assert "file" not in out["callees"][0]            # 無法解析 → 只回 node_id


def test_node_detail_missing_raises():
    with pytest.raises(locator.LocateError, match="not found"):
        locator.node_detail({}, "nope::x")
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/unit/core/structure_view/test_locator.py -k node_detail -v`
Expected: FAIL（`node_detail` 未定義）

- [ ] **Step 3: 實作 `node_detail`**

加到 `locator.py`：

```python
def node_detail(views: dict[str, dict], node_id: str) -> dict:
    view = views.get(node_id)
    if view is None:
        raise LocateError(f"node_id not found: {node_id}")

    def _ref(other_id: str, edge_type) -> dict:
        ref = {"node_id": other_id, "type": edge_type}
        ov = views.get(other_id)
        if ov is not None:
            ref["file"] = ov.get("file")
            ref["start_line"] = ov.get("start_line")
        return ref

    callers = [_ref(e["from_node_id"], e.get("type")) for e in view.get("in_edges", [])]
    callees = [_ref(e["to_node_id"], e.get("type")) for e in view.get("out_edges", [])]
    return {
        "node_id": node_id, "name": view.get("name"), "type": view.get("type"),
        "file": view.get("file"), "start_line": view.get("start_line"),
        "end_line": view.get("end_line"), "language": view.get("language"),
        "topology": view.get("topology"), "callers": callers, "callees": callees,
    }
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/unit/core/structure_view/test_locator.py -k node_detail -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/locator.py the_door/tests/unit/core/structure_view/test_locator.py
git commit -m "feat(locator): add node_detail with caller/callee resolution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `compute_freshness` — 三態軟訊號

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/locator.py`
- Test: `the_door/tests/unit/core/structure_view/test_locator_freshness.py`

- [ ] **Step 1: 寫失敗測試（fresh / stale / unknown 三態，自建 tmp checklist）**

建 `the_door/tests/unit/core/structure_view/test_locator_freshness.py`：

```python
import json
from pathlib import Path

from the_door.core.structure_view import locator


def _write_checklist(root: Path, source_files: dict) -> None:
    door = root / ".the-door"
    door.mkdir(parents=True, exist_ok=True)
    (door / "checklist.json").write_text(
        json.dumps({"stages": {"edge_residue": {"source_files": source_files}}}),
        encoding="utf-8",
    )


def test_freshness_unknown_when_no_checklist(tmp_path):
    assert locator.compute_freshness(tmp_path)["status"] == "unknown"


def test_freshness_fresh_when_fingerprint_matches(tmp_path):
    src = tmp_path / "a.py"
    src.write_text("print(1)\n", encoding="utf-8")
    st = src.stat()
    _write_checklist(tmp_path, {"a.py": [st.st_mtime_ns, st.st_size]})
    assert locator.compute_freshness(tmp_path)["status"] == "fresh"


def test_freshness_stale_when_file_changed(tmp_path):
    src = tmp_path / "a.py"
    src.write_text("print(1)\n", encoding="utf-8")
    # 蓋一個不可能相符的 fingerprint → 視為已變動
    _write_checklist(tmp_path, {"a.py": [1, 999]})
    out = locator.compute_freshness(tmp_path)
    assert out["status"] == "stale"
    assert "a.py" in out["changed_files"]
    assert out["changed_count"] == 1


def test_freshness_stale_when_file_deleted(tmp_path):
    _write_checklist(tmp_path, {"gone.py": [1, 1]})
    out = locator.compute_freshness(tmp_path)
    assert out["status"] == "stale"
    assert "gone.py" in out["changed_files"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest tests/unit/core/structure_view/test_locator_freshness.py -v`
Expected: FAIL（`compute_freshness` 未定義）

- [ ] **Step 3: 實作 `compute_freshness`**

加到 `locator.py`：

```python
def compute_freshness(codebase_path: str | Path) -> dict:
    checklist = read_checklist(codebase_path)
    source_files = None
    if isinstance(checklist, dict):
        stages = checklist.get("stages")
        if isinstance(stages, dict):
            entry = stages.get("edge_residue")
            if isinstance(entry, dict):
                source_files = entry.get("source_files")
    if not isinstance(source_files, dict):
        return {"status": "unknown", "reason": "no edge_residue fingerprint"}

    root = Path(codebase_path)
    changed: list[str] = []
    for relpath, fingerprint in source_files.items():
        try:
            st = (root / relpath).stat()
        except OSError:
            changed.append(relpath)
            continue
        try:
            mtime_ns, size = fingerprint
        except (ValueError, TypeError):
            continue  # 壞 fingerprint → 略過（fail-soft）
        if st.st_mtime_ns != mtime_ns or st.st_size != size:
            changed.append(relpath)
    changed.sort()
    return {
        "status": "stale" if changed else "fresh",
        "changed_files": changed[:FRESHNESS_CHANGED_CAP],
        "changed_count": len(changed),
    }
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/unit/core/structure_view/test_locator_freshness.py -v`
Expected: PASS（4 個測試全綠）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/locator.py the_door/tests/unit/core/structure_view/test_locator_freshness.py
git commit -m "feat(locator): add compute_freshness three-state soft signal

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `search` / `node` public compose + 真實 fixture 整合測試

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/locator.py`
- Test: `the_door/tests/integration/test_locator_fixture.py`

- [ ] **Step 1: 實作 compose 函式**

加到 `locator.py`（compose load + 純查詢 + freshness）：

```python
def search(codebase_path: str | Path, query: str,
           limit: int = SEARCH_DEFAULT_LIMIT) -> dict:
    result = search_views(load_views(codebase_path), query, limit)
    result["freshness"] = compute_freshness(codebase_path)
    return result


def node(codebase_path: str | Path, node_id: str) -> dict:
    result = node_detail(load_views(codebase_path), node_id)
    result["freshness"] = compute_freshness(codebase_path)
    return result
```

- [ ] **Step 2: 寫整合測試（真實 fixture 真值）**

建 `the_door/tests/integration/test_locator_fixture.py`。真值來自 fixture
`sample_codebases/python_simple`（6 nodes；`app.py::login` 呼叫
`auth.py::authenticate_user`，後者再呼叫 `auth.py::generate_token`）：

```python
import pytest

from the_door.core.structure_view import locator


@pytest.fixture()
def simple(fixtures_dir):
    return fixtures_dir / "sample_codebases" / "python_simple"


def test_load_views_real_fixture(simple):
    views = locator.load_views(simple)
    assert "app.py::login" in views
    assert len(views) == 6


def test_search_real_fixture_name_before_path(simple):
    # "auth": authenticate_user 為 name 命中、generate_token 為 path 命中（檔名 auth.py）
    out = locator.search(simple, "auth")
    ids = [r["node_id"] for r in out["results"]]
    assert ids.index("auth.py::authenticate_user") < ids.index("auth.py::generate_token")
    kinds = {r["node_id"]: r["match_kind"] for r in out["results"]}
    assert kinds["auth.py::authenticate_user"] == "name"
    assert kinds["auth.py::generate_token"] == "path"
    assert out["freshness"]["status"] == "unknown"   # fixture 無 checklist.json


def test_node_real_fixture_callers_callees(simple):
    out = locator.node(simple, "auth.py::authenticate_user")
    caller_ids = {c["node_id"] for c in out["callers"]}
    callee_ids = {c["node_id"] for c in out["callees"]}
    assert "app.py::login" in caller_ids
    assert "auth.py::generate_token" in callee_ids
    assert out["file"] == "auth.py"
    assert out["start_line"] == 4
```

- [ ] **Step 3: 跑測試確認通過**

Run: `python -m pytest tests/integration/test_locator_fixture.py -v`
Expected: PASS

> 若 `len(views) == 6` 或行號斷言因 fixture 重生而不符，**以實際 fixture 為準**修正期望值，
> 不要改 fixture。可先 `python -m pytest ... -v` 觀察實際回傳再對齊。

- [ ] **Step 4: 跑整個 locator 測試套確認無回歸**

Run: `python -m pytest tests/unit/core/structure_view/test_locator.py tests/unit/core/structure_view/test_locator_freshness.py tests/integration/test_locator_fixture.py -v`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/locator.py the_door/tests/integration/test_locator_fixture.py
git commit -m "feat(locator): add public search/node compose + fixture integration tests

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 1 自審

- **spec §3 載入**：Task 1（view_dir + regions/*.json.gz、缺則 LocateError）。✓
- **spec §4.1 search**：Task 2（name>path>in_degree 三層鍵、空 query、limit、match_kind、None topology fail-soft）。✓
- **spec §4.2 node**：Task 3（in_edges→callers、out_edges→callees、對端可解析附 file、不可解析 fail-soft、缺 node 報錯）。✓
- **spec §5 freshness**：Task 4（三態、checklist 缺/壞→unknown、刪檔→stale、截斷 20）。✓
- **型別一致**：`search_views`/`node_detail`/`compute_freshness` 簽章在 Task 5 compose 中被呼叫的方式與定義一致；`LocateError` 全程同一型別。✓
- **無 placeholder**：每個 code step 都有完整可貼上的程式碼。✓
- **零重抽取**：locator 只 import gzip/json/Path/checklist/structure_index，**未** import ASTExtractor。✓
