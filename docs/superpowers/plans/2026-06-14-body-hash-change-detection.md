# Body Hash Change Detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 `compute_affected_features` 偵測純 body 改動（bugfix、邏輯重構），使 LLM 能正確重譯受影響的 feature。

**Architecture:** 三個獨立 pipeline 層：(1) extraction — `NodeBuilder` 在建構 `ASTNode` 時用 MD5 hash 對應行範圍，透過 per-file line cache 避免重複讀檔；(2) serialization — `structure_serializer` 以 `.get()` 向下相容方式讀寫 `body_hash`；(3) diff — `feature_attribution` 在既有 `_signature` Layer 1 後加 Layer 2 body dict 比對，OR-union 結果。

**Tech Stack:** Python stdlib only（`hashlib`, `pathlib`）；不新增依賴；TDD with `pytest`；所有 tests 在 `the_door/tests/unit/`。

**Spec:** `docs/superpowers/specs/2026-06-14-body-hash-change-detection-design.md`

---

## 異動檔案總覽

| 檔案 | 異動類型 | 說明 |
|---|---|---|
| `the_door/src/the_door/models/extraction.py` | modify | `ASTNode` 加 `body_hash: str \| None = None` |
| `the_door/src/the_door/core/extraction/node_builder.py` | modify | `build_nodes` 加 `codebase_root` 參數；新增 `_compute_body_hash` + `_body_file_cache`；8 個建構點加 `body_hash=` |
| `the_door/src/the_door/core/extraction/ast_extractor.py` | modify | `build_nodes(tree, file_info, root)` 呼叫處補 `root` |
| `the_door/src/the_door/core/extraction/structure_serializer.py` | modify | `build_structure_dict` 輸出 `body_hash`；`parse_structure_dict` 用 `.get("body_hash")` |
| `the_door/src/the_door/core/diff/feature_attribution.py` | modify | `compute_affected_features` 加 Layer 2 body dict |
| `the_door/tests/unit/core/extraction/test_extraction.py` | modify | 加 4 個 test（TestNodeBuilder 內） |
| `the_door/tests/unit/core/extraction/test_structure_serializer.py` | modify | 加 4 個 test |
| `the_door/tests/unit/core/diff/test_feature_attribution.py` | modify | 加 3 個 test + 1 個 helper |

**不動：** `node_view.py`、`SNAPSHOT_CONTRACT_VERSION`、MCP 工具介面、`_signature` 函數。

---

### Task 1: ASTNode — 加 `body_hash` 欄位

**Files:**
- Modify: `the_door/src/the_door/models/extraction.py`
- Test: `the_door/tests/unit/core/extraction/test_extraction.py`

- [ ] **Step 1: 寫 failing test**

在 `test_extraction.py` 的 `TestNodeBuilder` class 末尾加：

```python
def test_astnode_body_hash_defaults_to_none(self):
    node = ASTNode(
        node_id="foo.py::bar", type="function", name="bar",
        file="foo.py", language="python",
    )
    assert node.body_hash is None
```

- [ ] **Step 2: 跑確認 fail**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/extraction/test_extraction.py::TestNodeBuilder::test_astnode_body_hash_defaults_to_none -v
```

Expected: `FAILED` — `TypeError: ASTNode.__init__() got an unexpected keyword argument 'body_hash'`（或 `AttributeError`）

- [ ] **Step 3: 加 `body_hash` 欄位**

在 `the_door/src/the_door/models/extraction.py`，把 `ASTNode` dataclass 改成（在 `end_line` 之後、`decorators` 之前插入一行）：

```python
@dataclass(frozen=True)
class ASTNode:
    """An extracted AST node (function, class, or method)."""

    node_id: str
    type: str  # "function" | "class" | "method"
    name: str
    file: str
    language: str
    start_line: int | None = None   # 1-indexed, inclusive; None = not available
    end_line: int | None = None     # 1-indexed, inclusive; None = not available
    body_hash: str | None = None    # MD5 hex of body lines; None = not computed or unavailable
    decorators: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    return_type: str | None = None
    docstring: str | None = None
    comments: list[str] = field(default_factory=list)
```

- [ ] **Step 4: 跑確認 pass**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/extraction/test_extraction.py::TestNodeBuilder::test_astnode_body_hash_defaults_to_none -v
```

Expected: `PASSED`

- [ ] **Step 5: 確認無 regression**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/extraction/test_extraction.py -v
```

Expected: 所有既有 tests pass。

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/models/extraction.py the_door/tests/unit/core/extraction/test_extraction.py
git commit -m "feat(models): add body_hash to ASTNode"
```

---

### Task 2: NodeBuilder — 在提取時計算 body_hash

**Files:**
- Modify: `the_door/src/the_door/core/extraction/node_builder.py`
- Modify: `the_door/src/the_door/core/extraction/ast_extractor.py`
- Test: `the_door/tests/unit/core/extraction/test_extraction.py`

> **背景：** 現有的 `build_nodes(self, tree, file_info)` 沒有 `codebase_root`，但讀檔需要絕對路徑。
> 解法：`build_nodes` 加 `codebase_root: Path` 參數，入口存為 `self._codebase_root`；
> `ASTExtractor.extract()` 呼叫處補 `root`（已在 line 131 存在）。

- [ ] **Step 1: 寫 3 個 failing tests**

在 `test_extraction.py` 的 `TestNodeBuilder` class 末尾加：

```python
def test_function_node_body_hash_is_populated(self, tmp_path):
    source = "def hello():\n    return 42\n"
    (tmp_path / "test.py").write_text(source, encoding="utf-8")
    result = ASTExtractor().extract(str(tmp_path))
    node = next(n for n in result.nodes if n.name == "hello")
    assert node.body_hash is not None
    assert isinstance(node.body_hash, str)
    assert len(node.body_hash) == 32  # MD5 hex digest

def test_function_body_hash_changes_when_body_changes(self, tmp_path):
    src_v1 = "def hello():\n    return 42\n"
    src_v2 = "def hello():\n    return 99\n"
    (tmp_path / "test.py").write_text(src_v1, encoding="utf-8")
    n1 = next(n for n in ASTExtractor().extract(str(tmp_path)).nodes if n.name == "hello")
    (tmp_path / "test.py").write_text(src_v2, encoding="utf-8")
    n2 = next(n for n in ASTExtractor().extract(str(tmp_path)).nodes if n.name == "hello")
    assert n1.body_hash != n2.body_hash

def test_function_body_hash_stable_when_source_unchanged(self, tmp_path):
    src = "def hello():\n    return 42\n"
    (tmp_path / "test.py").write_text(src, encoding="utf-8")
    n1 = next(n for n in ASTExtractor().extract(str(tmp_path)).nodes if n.name == "hello")
    n2 = next(n for n in ASTExtractor().extract(str(tmp_path)).nodes if n.name == "hello")
    assert n1.body_hash == n2.body_hash
```

- [ ] **Step 2: 跑確認 fail**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/extraction/test_extraction.py::TestNodeBuilder::test_function_node_body_hash_is_populated -v
```

Expected: `FAILED` — `AssertionError: assert None is not None`

- [ ] **Step 3: 在 `node_builder.py` 頂部加 import**

`node_builder.py` 目前 imports：
```python
from __future__ import annotations
from tree_sitter import Node as TSNode
from the_door.models import ASTNode, FileInfo
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS
```

改成：
```python
from __future__ import annotations

import hashlib
from pathlib import Path

from tree_sitter import Node as TSNode

from the_door.models import ASTNode, FileInfo
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS
```

- [ ] **Step 4: 修改 `build_nodes` 簽名**

把 `NodeBuilder.build_nodes` 方法（目前第 13 行）整個替換：

```python
def build_nodes(self, tree, file_info: FileInfo, codebase_root: Path) -> list[ASTNode]:
    """Extract function/class/method nodes from a parsed tree-sitter tree."""
    self._codebase_root = codebase_root
    self._body_file_cache: dict[str, list[str]] = {}
    nodes: list[ASTNode] = []
    self._walk(tree.root_node, file_info, nodes, parent_class=None)
    return nodes
```

docstring 及 Parameters/Returns 部分可保留，只要函式簽名和前兩行（`self._codebase_root = ...` 和 `self._body_file_cache = ...`）正確即可。

- [ ] **Step 5: 修改 `ast_extractor.py` 呼叫處**

在 `the_door/src/the_door/core/extraction/ast_extractor.py` 第 183 行：

```python
# 改前：
nodes = self._node_builder.build_nodes(tree, file_info)

# 改後：
nodes = self._node_builder.build_nodes(tree, file_info, root)
```

`root` 已在同函式 line 131 定義（`root = Path(codebase_path)`），不需要額外計算。

- [ ] **Step 6: 加 `_compute_body_hash` 方法**

在 `node_builder.py`，在 `_walk` 方法之前加入：

```python
def _compute_body_hash(self, file_path: str, start_line: int | None, end_line: int | None) -> str | None:
    if start_line is None or end_line is None:
        return None
    if file_path not in self._body_file_cache:
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                self._body_file_cache[file_path] = f.readlines()
        except OSError:
            self._body_file_cache[file_path] = []
    lines = self._body_file_cache[file_path]
    if not lines:
        return None
    body = "".join(lines[start_line - 1 : end_line])
    return hashlib.md5(body.encode("utf-8")).hexdigest()
```

- [ ] **Step 7: 更新 8 個 ASTNode 建構點**

以下逐一列出每個建構點的完整替換。全部改動都在 `node_builder.py`。

**7a. `_handle_python_class` — 替換 `results.append(ASTNode(...))` 呼叫（目前 line ~124）：**

```python
_start = outer_start_line if outer_start_line is not None else node.start_point[0] + 1
_end = node.end_point[0] + 1
results.append(
    ASTNode(
        node_id=f"{file_info.path}::{name}",
        type="class",
        name=name,
        file=file_info.path,
        language=file_info.language,
        start_line=_start,
        end_line=_end,
        body_hash=self._compute_body_hash(
            str(self._codebase_root / file_info.path), _start, _end
        ),
        decorators=decorators,
        parameters=[],
        return_type=None,
        docstring=docstring,
        comments=comments,
    )
)
```

**7b. `_build_python_function` — 替換 `return ASTNode(...)` 呼叫（目前 line ~163）：**

```python
_start = outer_start_line if outer_start_line is not None else node.start_point[0] + 1
_end = node.end_point[0] + 1
return ASTNode(
    node_id=f"{file_info.path}::{name}",
    type=node_type,
    name=name,
    file=file_info.path,
    language=file_info.language,
    start_line=_start,
    end_line=_end,
    body_hash=self._compute_body_hash(
        str(self._codebase_root / file_info.path), _start, _end
    ),
    decorators=decorators,
    parameters=params,
    return_type=return_type,
    docstring=docstring,
    comments=comments,
)
```

**7c. `_handle_ts_class` — 替換 `results.append(ASTNode(...))` 呼叫（目前 line ~316）：**

```python
results.append(
    ASTNode(
        node_id=f"{file_info.path}::{name}",
        type="class",
        name=name,
        file=file_info.path,
        language=file_info.language,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        body_hash=self._compute_body_hash(
            str(self._codebase_root / file_info.path),
            node.start_point[0] + 1,
            node.end_point[0] + 1,
        ),
        decorators=[],
        parameters=[],
        return_type=None,
        docstring=docstring,
        comments=[],
    )
)
```

**7d. `_build_ts_function` — 替換 `return ASTNode(...)` 呼叫（目前 line ~341）：**

```python
return ASTNode(
    node_id=f"{file_info.path}::{name}",
    type="method" if parent_class else "function",
    name=name,
    file=file_info.path,
    language=file_info.language,
    start_line=node.start_point[0] + 1,
    end_line=node.end_point[0] + 1,
    body_hash=self._compute_body_hash(
        str(self._codebase_root / file_info.path),
        node.start_point[0] + 1,
        node.end_point[0] + 1,
    ),
    decorators=[],
    parameters=[],
    return_type=None,
    docstring=docstring,
    comments=[],
)
```

**7e. `_build_ts_method` — 替換 `return ASTNode(...)` 呼叫（目前 line ~360）：**

```python
return ASTNode(
    node_id=f"{file_info.path}::{name}",
    type="method",
    name=name,
    file=file_info.path,
    language=file_info.language,
    start_line=node.start_point[0] + 1,
    end_line=node.end_point[0] + 1,
    body_hash=self._compute_body_hash(
        str(self._codebase_root / file_info.path),
        node.start_point[0] + 1,
        node.end_point[0] + 1,
    ),
    decorators=[],
    parameters=[],
    return_type=None,
    docstring=docstring,
    comments=[],
)
```

**7f. `_walk_config_driven` fallback — function 分支（目前 line ~401-412）：**

```python
if "function_definition" in node.type or "function_declaration" in node.type:
    name = self._child_text(node, "identifier")
    if name:
        results.append(ASTNode(
            node_id=f"{file_info.path}::{name}",
            type="method" if parent_class else "function",
            name=name,
            file=file_info.path,
            language=file_info.language,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            body_hash=self._compute_body_hash(
                str(self._codebase_root / file_info.path),
                node.start_point[0] + 1,
                node.end_point[0] + 1,
            ),
        ))
    return
```

**7g. `_walk_config_driven` fallback — class 分支（目前 line ~413-428）：**

```python
if "class_definition" in node.type or "class_declaration" in node.type:
    name = self._child_text(node, "identifier") or self._child_text(node, "type_identifier")
    if name:
        results.append(ASTNode(
            node_id=f"{file_info.path}::{name}",
            type="class",
            name=name,
            file=file_info.path,
            language=file_info.language,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            body_hash=self._compute_body_hash(
                str(self._codebase_root / file_info.path),
                node.start_point[0] + 1,
                node.end_point[0] + 1,
            ),
        ))
    return
```

**7h. `_build_enriched_node` — 替換 `return ASTNode(...)` 呼叫（目前 line ~513）：**

```python
return ASTNode(
    node_id=f"{file_info.path}::{name}",
    type=kind,
    name=name,
    file=file_info.path,
    language=file_info.language,
    start_line=node.start_point[0] + 1,
    end_line=node.end_point[0] + 1,
    body_hash=self._compute_body_hash(
        str(self._codebase_root / file_info.path),
        node.start_point[0] + 1,
        node.end_point[0] + 1,
    ),
    parameters=self._extract_parameters(node, cfg.parameters_field),
    return_type=self._extract_return_type(node, cfg.return_type_field),
    decorators=self._extract_decorators(node, cfg.decorator_types),
    docstring=self._extract_doc_comment(
        node,
        cfg.doc_comment_strategy,
        cfg.doc_comment_types,
        cfg.doc_comment_markers,
        skip_types=cfg.decorator_types,
    ),
    comments=[],
)
```

- [ ] **Step 8: 跑 3 個新 tests**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/extraction/test_extraction.py::TestNodeBuilder::test_function_node_body_hash_is_populated tests/unit/core/extraction/test_extraction.py::TestNodeBuilder::test_function_body_hash_changes_when_body_changes tests/unit/core/extraction/test_extraction.py::TestNodeBuilder::test_function_body_hash_stable_when_source_unchanged -v
```

Expected: 3 個全 `PASSED`。

- [ ] **Step 9: 跑 extraction 模組全套**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/extraction/ -v
```

Expected: 所有既有 tests pass（含 multilang、go/rust、ts/java 等）。

- [ ] **Step 10: Commit**

```bash
git add the_door/src/the_door/core/extraction/node_builder.py the_door/src/the_door/core/extraction/ast_extractor.py the_door/tests/unit/core/extraction/test_extraction.py
git commit -m "feat(extraction): compute body_hash in NodeBuilder; thread codebase_root through build_nodes"
```

---

### Task 3: Serializer — body_hash 寫入和讀回 structure.json

**Files:**
- Modify: `the_door/src/the_door/core/extraction/structure_serializer.py`
- Test: `the_door/tests/unit/core/extraction/test_structure_serializer.py`

- [ ] **Step 1: 寫 4 個 failing tests**

**先在 `test_structure_serializer.py` 頂部的 import block 補 `parse_structure_dict`**（現有 import 只有 `build_structure_dict` / `default_structure_path` / `write_structure_json`）：

```python
from the_door.core.extraction.structure_serializer import (
    build_structure_dict,
    default_structure_path,
    parse_structure_dict,
    write_structure_json,
)
```

然後在 `test_structure_serializer.py` 末尾加（在所有現有 test 之後）：

```python
# ── body_hash serialization tests ──────────────────────────────────────

def test_build_structure_dict_includes_body_hash():
    node = ASTNode(
        node_id="src/a.py::foo", type="function", name="foo",
        file="src/a.py", language="python",
        start_line=1, end_line=3,
        body_hash="abc123def456abc123def456abc123de",
    )
    structure = StructureJSON(nodes=[node])
    result = build_structure_dict(structure, scan_result=None)
    assert result["nodes"][0]["body_hash"] == "abc123def456abc123def456abc123de"


def test_build_structure_dict_body_hash_none_is_serialized():
    node = ASTNode(
        node_id="src/a.py::foo", type="function", name="foo",
        file="src/a.py", language="python",
    )
    structure = StructureJSON(nodes=[node])
    result = build_structure_dict(structure, scan_result=None)
    assert "body_hash" in result["nodes"][0]
    assert result["nodes"][0]["body_hash"] is None


def test_parse_structure_dict_round_trips_body_hash():
    node = ASTNode(
        node_id="src/a.py::foo", type="function", name="foo",
        file="src/a.py", language="python",
        start_line=1, end_line=3,
        body_hash="abc123def456abc123def456abc123de",
    )
    structure = StructureJSON(
        nodes=[node],
        files=[FileInfo(path="src/a.py", language="python")],
    )
    data = build_structure_dict(structure, scan_result=None)
    restored = parse_structure_dict(data)
    assert restored.nodes[0].body_hash == "abc123def456abc123def456abc123de"


def test_parse_structure_dict_missing_body_hash_key_returns_none():
    # 模擬舊 structure.json（無 body_hash key）
    data = {
        "files": [{"path": "src/a.py", "language": "python"}],
        "nodes": [{
            "node_id": "src/a.py::foo", "type": "function", "name": "foo",
            "file": "src/a.py", "language": "python",
        }],
        "edges": [],
        "topology": [],
    }
    restored = parse_structure_dict(data)
    assert restored.nodes[0].body_hash is None
```

- [ ] **Step 2: 跑確認 fail**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/extraction/test_structure_serializer.py::test_build_structure_dict_includes_body_hash -v
```

Expected: `FAILED` — `KeyError: 'body_hash'`（key 不存在）

- [ ] **Step 3: 修改 `build_structure_dict`**

在 `structure_serializer.py`，`"nodes"` 列表推導式的 dict 中，在 `"end_line"` 之後加 `"body_hash"`：

```python
"nodes": [
    {
        "node_id": n.node_id, "type": n.type, "name": n.name,
        "file": n.file, "language": n.language,
        "decorators": n.decorators, "parameters": n.parameters,
        "return_type": n.return_type, "docstring": n.docstring,
        "comments": n.comments,
        "start_line": n.start_line, "end_line": n.end_line,
        "body_hash": n.body_hash,
    }
    for n in structure.nodes
],
```

- [ ] **Step 4: 修改 `parse_structure_dict`**

在 `parse_structure_dict` 的 `ASTNode(...)` 建構子中，在 `end_line=n.get("end_line"),` 之後加：

```python
nodes = [
    ASTNode(
        node_id=n["node_id"],
        type=n["type"],
        name=n["name"],
        file=n["file"],
        language=n["language"],
        decorators=n.get("decorators", []),
        parameters=n.get("parameters", []),
        return_type=n.get("return_type"),
        docstring=n.get("docstring"),
        comments=n.get("comments", []),
        start_line=n.get("start_line"),
        end_line=n.get("end_line"),
        body_hash=n.get("body_hash"),
    )
    for n in data["nodes"]
]
```

- [ ] **Step 5: 跑 serializer 全套**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/extraction/test_structure_serializer.py -v
```

Expected: 所有 tests pass（含新增 4 個）。

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/extraction/structure_serializer.py the_door/tests/unit/core/extraction/test_structure_serializer.py
git commit -m "feat(serializer): persist body_hash in structure.json; backward-compat parse"
```

---

### Task 4: feature_attribution — Layer 2 body diff

**Files:**
- Modify: `the_door/src/the_door/core/diff/feature_attribution.py`
- Test: `the_door/tests/unit/core/diff/test_feature_attribution.py`

> **背景：** 目前 `compute_affected_features` line 79-85 只做 `_signature` 比對（Layer 1）。
> 加 Layer 2：對 common node 中兩邊都有 non-None `body_hash` 的，比對 hash；OR-union 進 `modified`。

- [ ] **Step 1: 寫 3 個 failing tests + 1 個 helper**

在 `test_feature_attribution.py` 末尾加（在所有現有 test 之後）：

```python
# ── body_hash Layer 2 tests ─────────────────────────────────────────────

def _structure_with_body_hash(specs):
    """Build StructureJSON with body_hash. Each spec = (node_id, body_hash_or_none)."""
    nodes = []
    for node_id, body_hash in specs:
        name = node_id.split("::", 1)[-1] if "::" in node_id else node_id
        file_ = node_id.split("::", 1)[0] if "::" in node_id else "anon.py"
        nodes.append(ASTNode(
            node_id=node_id, type="function", name=name,
            file=file_, language="python",
            body_hash=body_hash,
        ))
    return StructureJSON(nodes=nodes)


def test_pure_body_change_marks_feature_affected():
    """Signature unchanged, body_hash differs → feature listed in affected (Layer 2)."""
    from the_door.core.diff.feature_attribution import compute_affected_features

    baseline_structure = _structure_with_body_hash([
        ("file.py::foo", "aaaa1111aaaa1111aaaa1111aaaa1111"),
    ])
    current_structure = _structure_with_body_hash([
        ("file.py::foo", "bbbb2222bbbb2222bbbb2222bbbb2222"),
    ])
    baseline = _baseline_with_feature("feat-x", source_nodes=("file.py::foo",))
    result = compute_affected_features(baseline_structure, current_structure, baseline)

    assert len(result.affected_features) == 1
    assert result.affected_features[0].feature_id == "feat-x"
    assert result.inherited_features == ()


def test_same_body_hash_feature_stays_inherited():
    """Signature unchanged, body_hash identical → feature inherited (not affected)."""
    from the_door.core.diff.feature_attribution import compute_affected_features

    both = _structure_with_body_hash([
        ("file.py::foo", "cccc3333cccc3333cccc3333cccc3333"),
    ])
    baseline = _baseline_with_feature("feat-y", source_nodes=("file.py::foo",))
    result = compute_affected_features(both, both, baseline)

    assert result.affected_features == ()
    assert len(result.inherited_features) == 1


def test_old_baseline_none_body_hash_no_false_positive():
    """Baseline body_hash=None (old snapshot) → Layer 2 skipped, zero false positives."""
    from the_door.core.diff.feature_attribution import compute_affected_features

    baseline_structure = _structure_with_body_hash([
        ("file.py::foo", None),   # old snapshot: body_hash not computed
    ])
    current_structure = _structure_with_body_hash([
        ("file.py::foo", "dddd4444dddd4444dddd4444dddd4444"),
    ])
    baseline = _baseline_with_feature("feat-z", source_nodes=("file.py::foo",))
    result = compute_affected_features(baseline_structure, current_structure, baseline)

    assert result.affected_features == ()
    assert len(result.inherited_features) == 1
```

`_baseline_with_feature` 已在 `test_feature_attribution.py` line ~46 定義，直接複用。

- [ ] **Step 2: 跑確認 fail**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_feature_attribution.py::test_pure_body_change_marks_feature_affected -v
```

Expected: `FAILED` — `AssertionError: assert 0 == 1`（body 改動在 Layer 1 不可見，feature 留在 inherited）

- [ ] **Step 3: 加 Layer 2 body diff**

在 `the_door/src/the_door/core/diff/feature_attribution.py`，把 `compute_affected_features` 函式內 lines 79-85 整段替換：

```python
    baseline_sig  = {n.node_id: _signature(n) for n in baseline_structure.nodes}
    current_sig   = {n.node_id: _signature(n) for n in current_structure.nodes}
    baseline_body = {n.node_id: n.body_hash   for n in baseline_structure.nodes}
    current_body  = {n.node_id: n.body_hash   for n in current_structure.nodes}

    added   = set(current_sig.keys()) - set(baseline_sig.keys())
    removed = set(baseline_sig.keys()) - set(current_sig.keys())
    common  = set(baseline_sig.keys()) & set(current_sig.keys())

    # Layer 1: structural signature diff (existing behavior, unchanged)
    modified_structural = {k for k in common if baseline_sig[k] != current_sig[k]}

    # Layer 2: body-content diff (only when BOTH sides have a non-None body_hash)
    body_changed = {
        k for k in common
        if (bl := baseline_body.get(k)) is not None
        and (cu := current_body.get(k)) is not None
        and bl != cu
    }

    modified = modified_structural | body_changed
```

（此後 `inherited`、`affected`、`unmapped` 邏輯完全不動，`modified` 直接使用即可。）

- [ ] **Step 4: 跑 3 個新 tests**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_feature_attribution.py::test_pure_body_change_marks_feature_affected tests/unit/core/diff/test_feature_attribution.py::test_same_body_hash_feature_stays_inherited tests/unit/core/diff/test_feature_attribution.py::test_old_baseline_none_body_hash_no_false_positive -v
```

Expected: 3 個全 `PASSED`。

- [ ] **Step 5: 跑 diff 模組全套**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/core/diff/ -v
```

Expected: 所有既有 tests pass。

- [ ] **Step 6: 跑全套確認無 regression**

```bash
cd the_door && PYTHONUTF8=1 python -m pytest -v
```

Expected: 1538 passed（基準 1527 + 新增 11：Task 1: 1, Task 2: 3, Task 3: 4, Task 4: 3）, 43 skipped, 1 xfailed。

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/diff/feature_attribution.py the_door/tests/unit/core/diff/test_feature_attribution.py
git commit -m "feat(diff): Layer 2 body_hash change detection in compute_affected_features"
```

---

## Self-Review

**1. Spec coverage 對照：**

| Spec 章節 | Plan 任務 |
|---|---|
| §3.1 `ASTNode.body_hash` | Task 1 ✓ |
| §3.2 MD5 算法 | Task 2 Step 6 `_compute_body_hash` ✓ |
| §3.3.1 `codebase_root` 傳遞機制 | Task 2 Step 3（簽名）+ Step 4（呼叫處）✓ |
| §3.3.2 `_compute_body_hash` + `_body_file_cache` | Task 2 Step 5-6 ✓ |
| §3.3.3 8 個建構點 | Task 2 Step 7a-7h ✓ |
| §3.4 serializer `body_hash` 讀寫 | Task 3 ✓ |
| §3.5 Layer 2 body diff | Task 4 ✓ |
| §3.6 `node_view.py` 不動 | 無對應任務（by absence）✓ |
| §7 backward compat（None → 無假陽性）| Task 4 test 3 ✓ |

**2. Placeholder scan：** 無 TBD/TODO/placeholder 出現在任何 code block 中。

**3. Type consistency：**
- `body_hash: str | None = None`：Task 1 model、Task 2 `_compute_body_hash` 回傳值、Task 3 serializer `.get("body_hash")`、Task 4 walrus 運算子 `is not None` — 全部一致。
- `build_nodes(self, tree, file_info: FileInfo, codebase_root: Path)`：Task 2 Step 3（定義）和 Step 4（呼叫處 `build_nodes(tree, file_info, root)`）— 一致。
- `_compute_body_hash(self, file_path: str, start_line: int | None, end_line: int | None) -> str | None`：Task 2 Step 5（定義）和 7a-7h 所有呼叫 — 一致。
