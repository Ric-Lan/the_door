# Phase 2 — chunk_merge 核心

> 父計畫：[../2026-06-23-chunk-dispatch-merge-plan.md](../2026-06-23-chunk-dispatch-merge-plan.md)。前置：Phase 1 完成。
> 同前環境規則（pytest 從 repo root、hook 限制、commit -F）。

新模組 `core/structure_view/chunk_merge.py`：收齊各 chunk features（驗 id 唯一）、建 `node→feature` 映射（決定性、雙重認領→warning）、從結構邊**決定性推導 static relations**（聚合）、組裝 payload + rollup。唯讀（讀 structure-view）、不寫 snapshot。

---

### Task 2: `_collect_features`（union + id 唯一）

**Files:**
- Create: `the_door/src/the_door/core/structure_view/chunk_merge.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_merge.py`

- [ ] **Step 1: 寫失敗測試**

建 `the_door/tests/unit/core/structure_view/test_chunk_merge.py`：

```python
import pytest
from the_door.core.structure_view import chunk_merge as cm


def _feat(fid, nodes):
    return {"feature_id": fid, "label": fid, "description": "d",
            "confidence": "high", "source_nodes": list(nodes)}


def test_collect_features_unions_across_chunks():
    chunks = [
        {"chunk_id": "c001", "features": [_feat("feat-c001-a", ["x.py::a"])]},
        {"chunk_id": "c002", "features": [_feat("feat-c002-b", ["y.py::b"])]},
    ]
    feats = cm._collect_features(chunks)
    assert {f["feature_id"] for f in feats} == {"feat-c001-a", "feat-c002-b"}


def test_collect_features_duplicate_id_raises():
    chunks = [
        {"chunk_id": "c001", "features": [_feat("feat-dup", ["x.py::a"])]},
        {"chunk_id": "c002", "features": [_feat("feat-dup", ["y.py::b"])]},
    ]
    with pytest.raises(cm.ChunkMergeError, match="duplicate feature_id"):
        cm._collect_features(chunks)


def test_collect_features_missing_feature_id_raises():
    chunks = [{"chunk_id": "c001", "features": [{"label": "no id"}]}]
    with pytest.raises(cm.ChunkMergeError, match="feature_id"):
        cm._collect_features(chunks)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_merge.py -k collect -v`
Expected: FAIL（模組/函式不存在）

- [ ] **Step 3: 實作模組骨架 + `_collect_features`**

建 `the_door/src/the_door/core/structure_view/chunk_merge.py`：

```python
"""Chunk Merge: 收齊各 chunk 的 features，從結構邊決定性推導 static relations，
組裝成可寫入 snapshot_write 的 payload。唯讀（讀 structure-view）、不寫 snapshot。

subagent 只產 features；relations 全由本模組從結構邊推導（CLAUDE.md 閘門：
結構性分析走純程式）。spec: docs/superpowers/specs/2026-06-23-chunk-dispatch-merge-design.md
"""
from __future__ import annotations

from the_door.core.structure_view.locator import load_views  # noqa: F401 (used in merge)


class ChunkMergeError(Exception):
    """合併的可預期錯誤（重複 feature_id、缺欄位、空 chunks）。"""


def _collect_features(chunks: list) -> list:
    """Union 所有 chunk 的 features；feature_id 跨塊重複 → ChunkMergeError。"""
    features: list = []
    seen: dict = {}
    for ch in chunks:
        cid = ch.get("chunk_id")
        for f in ch.get("features", []) or []:
            fid = f.get("feature_id")
            if not fid:
                raise ChunkMergeError(
                    f"feature missing feature_id (chunk {cid!r})")
            if fid in seen:
                raise ChunkMergeError(
                    f"duplicate feature_id {fid!r} (chunks {seen[fid]!r} and {cid!r}); "
                    f"feature_id must be chunk-namespaced and globally unique")
            seen[fid] = cid
            features.append(f)
    return features
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_merge.py -k collect -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_merge.py the_door/tests/unit/core/structure_view/test_chunk_merge.py
git commit -F - <<'EOF'
feat(chunk-merge): add _collect_features with global feature_id uniqueness

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### Task 3: `_node_to_feature`（決定性映射）

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_merge.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_merge.py`

- [ ] **Step 1: 寫失敗測試**

加到 `test_chunk_merge.py`：

```python
def test_node_to_feature_maps_each_node():
    feats = [_feat("feat-a", ["x.py::a", "x.py::b"]), _feat("feat-b", ["y.py::c"])]
    mapping, warns = cm._node_to_feature(feats)
    assert mapping == {"x.py::a": "feat-a", "x.py::b": "feat-a", "y.py::c": "feat-b"}
    assert warns == []


def test_node_to_feature_double_claim_lexicographic_first_plus_warning():
    # 同一 node 被兩 feature 認領 → 取字典序首者 (feat-a < feat-z)、記 warning
    feats = [_feat("feat-z", ["x.py::n"]), _feat("feat-a", ["x.py::n"])]
    mapping, warns = cm._node_to_feature(feats)
    assert mapping["x.py::n"] == "feat-a"
    assert warns == ["x.py::n"]
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_merge.py -k node_to_feature -v`
Expected: FAIL（`_node_to_feature` 未定義）

- [ ] **Step 3: 實作**

加到 `chunk_merge.py`：

```python
def _node_to_feature(features: list) -> tuple[dict, list]:
    """{node_id: feature_id}。一節點被多 feature 認領 → 取 feature_id 字典序首者
    （決定性）並記 warning。回 (mapping, sorted_warnings)。"""
    mapping: dict = {}
    warnings: set = set()
    # 按 feature_id 升冪迭代 → 先到先得＝字典序首者得標
    for f in sorted(features, key=lambda x: x["feature_id"]):
        fid = f["feature_id"]
        for nid in f.get("source_nodes", []) or []:
            if nid in mapping:
                if mapping[nid] != fid:
                    warnings.add(nid)
                continue
            mapping[nid] = fid
    return mapping, sorted(warnings)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_merge.py -k node_to_feature -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_merge.py the_door/tests/unit/core/structure_view/test_chunk_merge.py
git commit -F - <<'EOF'
feat(chunk-merge): add deterministic node->feature mapping (lexicographic-first)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### Task 4: `_derive_relations`（結構邊 → static relations）

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_merge.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_merge.py`

- [ ] **Step 1: 寫失敗測試**

加到 `test_chunk_merge.py`：

```python
def _view(node_id, out=()):
    return {"node_id": node_id, "name": node_id.split("::")[-1],
            "out_edges": [{"to_node_id": t, "type": ty} for (t, ty) in out],
            "in_edges": []}


def test_derive_relations_crosses_feature_boundary():
    views = {
        "x.py::a": _view("x.py::a", out=[("y.py::c", "calls")]),
        "y.py::c": _view("y.py::c"),
    }
    n2f = {"x.py::a": "feat-a", "y.py::c": "feat-b"}
    rels, skipped = cm._derive_relations(views, n2f)
    assert rels == [{"from_feature": "feat-a", "to_feature": "feat-b",
                     "relation": "calls", "relation_type": "static"}]
    assert skipped == 0


def test_derive_relations_aggregates_duplicate_pairs():
    views = {
        "x.py::a": _view("x.py::a", out=[("y.py::c", "calls")]),
        "x.py::b": _view("x.py::b", out=[("y.py::d", "calls")]),
        "y.py::c": _view("y.py::c"), "y.py::d": _view("y.py::d"),
    }
    n2f = {"x.py::a": "feat-a", "x.py::b": "feat-a", "y.py::c": "feat-b", "y.py::d": "feat-b"}
    rels, _ = cm._derive_relations(views, n2f)
    assert rels == [{"from_feature": "feat-a", "to_feature": "feat-b",
                     "relation": "calls", "relation_type": "static"}]  # 聚合成一條


def test_derive_relations_skips_intrafeature_and_no_feature():
    views = {
        "x.py::a": _view("x.py::a", out=[("x.py::b", "calls"),   # 同 feature → 不產
                                          ("ext::z", "calls")]),  # 端點無 feature → skip+計數
        "x.py::b": _view("x.py::b"),
    }
    n2f = {"x.py::a": "feat-a", "x.py::b": "feat-a"}
    rels, skipped = cm._derive_relations(views, n2f)
    assert rels == []
    assert skipped == 1   # ext::z 那條


def test_derive_relations_keeps_edge_type():
    views = {"x.py::a": _view("x.py::a", out=[("y.py::c", "imports")]), "y.py::c": _view("y.py::c")}
    n2f = {"x.py::a": "feat-a", "y.py::c": "feat-b"}
    rels, _ = cm._derive_relations(views, n2f)
    assert rels[0]["relation"] == "imports"
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_merge.py -k derive -v`
Expected: FAIL（`_derive_relations` 未定義）

- [ ] **Step 3: 實作**

加到 `chunk_merge.py`：

```python
def _derive_relations(views: dict, node_to_feature: dict) -> tuple[list, int]:
    """從結構邊推導 feature 層 static relations。
    對每條 out_edge u→v：兩端皆有 feature 且不同 → relation(邊型別, static)。
    按 (from,to,relation) 聚合去重。端點缺 feature 的邊 → skip + 計數。
    回 (sorted_relations, skipped_count)。"""
    seen: set = set()
    relations: list = []
    skipped = 0
    for nid, view in views.items():
        ffrom = node_to_feature.get(nid)
        for e in view.get("out_edges", []) or []:
            fto = node_to_feature.get(e.get("to_node_id"))
            if ffrom is None or fto is None:
                skipped += 1
                continue
            if ffrom == fto:
                continue  # intra-feature，非 feature relation
            rel = e.get("type", "calls")
            key = (ffrom, fto, rel)
            if key in seen:
                continue
            seen.add(key)
            relations.append({"from_feature": ffrom, "to_feature": fto,
                              "relation": rel, "relation_type": "static"})
    relations.sort(key=lambda r: (r["from_feature"], r["to_feature"], r["relation"]))
    return relations, skipped
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_merge.py -k derive -v`
Expected: PASS（4 個）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_merge.py the_door/tests/unit/core/structure_view/test_chunk_merge.py
git commit -F - <<'EOF'
feat(chunk-merge): derive aggregated static relations from structural edges

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### Task 5: `merge()` compose + 真實 fixture 整合測試

**Files:**
- Modify: `the_door/src/the_door/core/structure_view/chunk_merge.py`
- Test: `the_door/tests/unit/core/structure_view/test_chunk_merge.py`

- [ ] **Step 1: 實作 `merge()`**

加到 `chunk_merge.py`：

```python
def merge(codebase_path, chunks: list) -> dict:
    """收齊 features → node→feature 映射 → 從 structure-view 邊推導 relations → 組裝。
    structure-view 缺失 → load_views 拋 LocateError（自然向上拋）。"""
    if not chunks:
        raise ChunkMergeError("chunks must not be empty")
    features = _collect_features(chunks)               # 驗 id 唯一
    node_to_feature, double_warn = _node_to_feature(features)
    views = load_views(codebase_path)
    relations, skipped = _derive_relations(views, node_to_feature)
    return {
        "l1_features": features,
        "relations": relations,
        "rollup": {
            "feature_count": len(features),
            "relation_count": len(relations),
            "skipped_edges_no_feature": skipped,
            "double_assigned_warnings": double_warn,
        },
    }
```

- [ ] **Step 2: 寫整合測試（真實 fixture 真值）**

加到 `test_chunk_merge.py`。python_simple：`app.py::login` calls `auth.py::authenticate_user`；後者 calls `auth.py::generate_token`；把它們分成兩個假 chunk/feature 驗跨 feature relation 被推出：

```python
@pytest.fixture()
def simple(fixtures_dir):
    return fixtures_dir / "sample_codebases" / "python_simple"


def test_merge_real_fixture_derives_cross_feature_calls(simple):
    chunks = [
        {"chunk_id": "c001", "features": [_feat("feat-c001-login", ["app.py::login"])]},
        {"chunk_id": "c002", "features": [
            _feat("feat-c002-auth", ["auth.py::authenticate_user", "auth.py::generate_token"])]},
    ]
    out = cm.merge(simple, chunks)
    assert out["rollup"]["feature_count"] == 2
    # login → authenticate_user 是跨 feature calls → 推出 c001→c002 static relation
    assert {"from_feature": "feat-c001-login", "to_feature": "feat-c002-auth",
            "relation": "calls", "relation_type": "static"} in out["relations"]
    # authenticate_user → generate_token 同 feature(c002) → 不產
    assert all(not (r["from_feature"] == r["to_feature"]) for r in out["relations"])


def test_merge_empty_chunks_raises(simple):
    with pytest.raises(cm.ChunkMergeError, match="must not be empty"):
        cm.merge(simple, [])


def test_merge_missing_structure_view_raises(tmp_path):
    from the_door.core.structure_view.locator import LocateError
    chunks = [{"chunk_id": "c001", "features": [_feat("feat-a", ["x::a"])]}]
    with pytest.raises(LocateError):
        cm.merge(tmp_path, chunks)
```

- [ ] **Step 3: 跑測試確認通過**

Run: `python -m pytest the_door/tests/unit/core/structure_view/test_chunk_merge.py -v`
Expected: 全 PASS

> 若 fixture 重生致行為不符，**以實際 fixture 為準**修期望值（先 `-v` 觀察 `out["relations"]`），不要改 fixture。

- [ ] **Step 4: Commit**

```bash
git add the_door/src/the_door/core/structure_view/chunk_merge.py the_door/tests/unit/core/structure_view/test_chunk_merge.py
git commit -F - <<'EOF'
feat(chunk-merge): add merge() compose + real-fixture integration test

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

## Phase 2 自審
- spec §4：id 唯一（Task2）/ node→feature 決定性映射+雙重認領 warning（Task3）/ 結構邊推導 static + 聚合 + skip 計數 + 邊型別（Task4）/ merge compose + rollup 欄位 + LocateError 上拋（Task5）。✓
- 型別一致：`_collect_features(chunks)->list`、`_node_to_feature(features)->(dict,list)`、`_derive_relations(views,n2f)->(list,int)`、`merge(codebase_path,chunks)->dict`；`ChunkMergeError` 全程同型別。✓
- relation 全由結構推導、subagent 不產（符合 §4 設計選擇）。`relation_type` 一律 `static`。✓
- 決定性：`_node_to_feature` sorted 迭代、`_derive_relations` sorted 輸出 + seen 去重。✓
- 無 placeholder；真實 fixture 用真值斷言。✓
