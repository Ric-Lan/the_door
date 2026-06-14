# Body Hash Change Detection — Design Spec

**Date:** 2026-06-14  
**Prerequisite:** `start_line`/`end_line` in `ASTNode` (landed v1.7.5+, commit `0dc0ce6`)  
**Scope:** 精度修正。不新增 MCP 工具、不動 MCP 介面、不 bump `SNAPSHOT_CONTRACT_VERSION`。

---

## 1. 問題陳述

`compute_affected_features`（`feature_attribution.py`）用 `_signature` 判斷節點是否變動：

```python
payload = (name, parameters, return_type, decorators, docstring)
```

**body 不在 `_signature` 裡。** 純實作改動（bugfix、邏輯重構、輸出行為改變）在簽名不動的情況下完全不可見：節點被歸入 `inherited_features`，LLM 不會重譯對應 feature，翻譯描述與實際行為脫節。

此缺口**在任何通用型專案的每次開發迭代都必定出現**，非偶發。

---

## 2. 設計目標

| 目標 | 說明 |
|---|---|
| 偵測純 body 改動 | method body 改變 → feature 正確列入 `affected_features` |
| 向下相容 | 舊 snapshot（body_hash=None）不產生假陽性 |
| 不擴大 MCP 介面 | `analyze_changes` 輸出格式不變，僅準確度提升 |
| 不 bump 契約版號 | body_hash 是加法欄位，不改變 snapshot 語義 |
| 不引入新依賴 | 純 Python 標準庫（hashlib、pathlib） |

---

## 3. 架構

### 3.1 新增欄位：`ASTNode.body_hash`

```python
@dataclass(frozen=True)
class ASTNode:
    ...
    start_line: int | None = None   # 已有
    end_line: int | None = None     # 已有
    body_hash: str | None = None    # 新增：None = 未填或不可用
```

位置：在 `end_line` 之後、`decorators` 之前（與 `start_line`/`end_line` 相鄰，語義一組）。

Default `None`，確保所有現有 `ASTNode(...)` 建構不受影響。

### 3.2 雜湊演算法

MD5，與 `_signature` 現有用法一致。body_hash 用途是**變動偵測**，非安全需求，無碰撞風險疑慮。

### 3.3 雜湊計算：`node_builder.py`

計算時機：`ASTNode` 建構時，從 `file_info` 讀對應行範圍。

#### 3.3.1 `codebase_root` 傳遞機制（重要，現有代碼尚無）

`file_info.path` 在 NodeBuilder 裡是 codebase-relative 路徑（例如 `the_door/src/foo.py`）；
`_compute_body_hash` 需要**絕對路徑**才能讀檔。

**現況**（`ast_extractor.py:183`）：
```python
nodes = self._node_builder.build_nodes(tree, file_info)  # root 沒有傳入
```

**修改方式**：在 `build_nodes()` 加 `codebase_root: Path` 參數，在方法入口存為 `self._codebase_root`，
讓所有 8 個建構點可透過 `self._codebase_root / file_info.path` 取得絕對路徑。

`NodeBuilder.build_nodes()` 新簽名：
```python
def build_nodes(self, tree, file_info: FileInfo, codebase_root: Path) -> list[ASTNode]:
    self._codebase_root = codebase_root
    nodes: list[ASTNode] = []
    self._walk(tree.root_node, file_info, nodes, parent_class=None)
    return nodes
```

對應修改 `ASTExtractor.extract()` 的呼叫處（`ast_extractor.py:183`）：
```python
nodes = self._node_builder.build_nodes(tree, file_info, root)
```

`root` 已在 `ast_extractor.py:131` 存在（`root = Path(codebase_path)`），零額外計算。

#### 3.3.2 `_compute_body_hash` 實作

```python
def _compute_body_hash(self, file_path: str, start_line: int | None, end_line: int | None) -> str | None:
    """Read file lines [start_line-1 : end_line] and return MD5 hex digest.
    Returns None if start_line is None, end_line is None, or file is unreadable.
    """
    if start_line is None or end_line is None:
        return None
    # File-level cache: avoid re-reading the same file for every node it contains.
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

`_body_file_cache: dict[str, list[str]]` 在 `build_nodes()` 入口清空，確保跨檔案不殘留：
```python
def build_nodes(self, tree, file_info: FileInfo, codebase_root: Path) -> list[ASTNode]:
    self._codebase_root = codebase_root
    self._body_file_cache: dict[str, list[str]] = {}   # reset per file set
    nodes: list[ASTNode] = []
    self._walk(tree.root_node, file_info, nodes, parent_class=None)
    return nodes
```

> **注意**：`build_nodes()` 每次呼叫只處理一個檔案，cache 在單檔內有效（同檔多 node 複用）。
> 跨檔 cache 不需要，因為 ASTExtractor 逐檔呼叫 `build_nodes()`。

#### 3.3.3 建構點呼叫

**所有 8 個 `ASTNode(...)` 建構點**（Python、TypeScript、config-driven、fallback）均加入：
```python
body_hash=self._compute_body_hash(
    str(self._codebase_root / file_info.path),
    start_line,
    end_line,
),
```

`start_line` / `end_line` 在各建構點的 local variable（已由 tree-sitter 行號計算完畢），直接傳入即可。

### 3.4 序列化：`structure_serializer.py`

**`build_structure_dict`**（寫出）：
```python
"body_hash": n.body_hash,   # None 或 MD5 hex string
```
位於 `"end_line"` 之後。

**`parse_structure_dict`**（讀回，向下相容）：
```python
body_hash=n.get("body_hash"),   # 舊檔無此 key → None
```

### 3.5 變動偵測：`feature_attribution.py`

**`_signature` 完全不動**（向下相容核心原則）。

在 `compute_affected_features` 加第二道 body 比對：

```python
def compute_affected_features(
    baseline_structure: StructureJSON,
    current_structure: StructureJSON,
    baseline: VersionSnapshot,
) -> IncrementalDiff:
    baseline_sig  = {n.node_id: _signature(n) for n in baseline_structure.nodes}
    current_sig   = {n.node_id: _signature(n) for n in current_structure.nodes}
    baseline_body = {n.node_id: n.body_hash  for n in baseline_structure.nodes}
    current_body  = {n.node_id: n.body_hash  for n in current_structure.nodes}

    added   = set(current_sig)  - set(baseline_sig)
    removed = set(baseline_sig) - set(current_sig)
    common  = set(baseline_sig) & set(current_sig)

    # Layer 1: structural signature diff (existing behavior, unchanged)
    modified_structural = {k for k in common if baseline_sig[k] != current_sig[k]}

    # Layer 2: body-content diff (new; only when BOTH sides have body_hash)
    body_changed = {
        k for k in common
        if (bl := baseline_body.get(k)) is not None
        and (cu := current_body.get(k)) is not None
        and bl != cu
    }

    modified = modified_structural | body_changed
    ...
```

**向下相容保證**：
- 舊 baseline（body_hash=None） → `bl` 為 None → 跳過 body 比對 → 零假陽性
- 新 baseline + 新 current → 兩邊都有值 → body 改動正確偵測
- 兩層 OR 合并：任一層偵測到改動即列入 `modified`

### 3.6 Node View：不加入

`body_hash` 是 pipeline 內部偵測訊號。LLM 讀 node_view 不需要看到雜湊值本身，`node_view.py` 不修改。

---

## 4. 資訊定位閉環

```
start_line / end_line  →  知道節點在哪幾行
body_hash              →  知道那幾行有沒有改
affected_features      →  LLM 知道要重寫哪些 feature
```

三層合一，`analyze_changes` 對 LLM 提供的翻譯範圍**對 Python 節點從此完整正確**。
TypeScript / config-driven 語言的 body 偵測仍為 best-effort（受 `start_line` 填入品質限制，見 §6）；
body 改動在這些語言中仍不可見，此為已知缺口而非 regression。

---

## 5. 異動檔案清單

**生產檔（5 個）**：

| 檔案 | 改動 |
|---|---|
| `the_door/src/the_door/models/extraction.py` | `ASTNode` 加 `body_hash: str \| None = None` |
| `the_door/src/the_door/core/extraction/node_builder.py` | `build_nodes()` 加 `codebase_root: Path` 參數；新增 `_compute_body_hash()` instance method（含 file cache）；8 個建構點帶入 `body_hash=` |
| `the_door/src/the_door/core/extraction/ast_extractor.py` | `build_nodes(tree, file_info, root)` 呼叫處補 `root`（line 183） |
| `the_door/src/the_door/core/extraction/structure_serializer.py` | `build_structure_dict` 加 `"body_hash"`；`parse_structure_dict` 用 `.get("body_hash")` |
| `the_door/src/the_door/core/diff/feature_attribution.py` | `compute_affected_features` 加 body 比對 Layer 2 |

**測試檔（3 個，純新增）**：

| 檔案 | 測試內容 |
|---|---|
| `the_door/tests/unit/core/extraction/test_extraction.py` | `body_hash` 填入非 None（Python function） |
| `the_door/tests/unit/core/extraction/test_structure_serializer.py` | round-trip + 舊 dict 無 body_hash key → None |
| `the_door/tests/unit/core/diff/test_feature_attribution.py` | 純 body 改 → affected；簽名不變 + body 不變 → inherited；舊 baseline (None) → 無假陽性 |

---

## 6. 不在本次範圍

- `node_view.py`（body_hash 不進 L2 視圖）
- `SNAPSHOT_CONTRACT_VERSION` bump（加法欄位，不改 snapshot 語義）
- MCP 工具新增或介面修改（`analyze_changes` 輸出格式不變）
- `_signature` 修改（Layer 1 完全不動）
- TypeScript / config-driven 語言的 decorator-inclusive body hash（`start_line` 本身已是 best-effort）
- delta 欄位區分「structural vs body modified」（未來需求）

---

## 7. 向下相容保證

| 情境 | 行為 |
|---|---|
| 舊 snapshot（無 body_hash）+ 新 extraction（有 body_hash） | body 比對跳過，Zero 假陽性 |
| 新 snapshot + 新 extraction（兩邊都有） | body 改動正確偵測 |
| `ASTNode` 無 start_line/end_line（不可解析語言） | `_compute_body_hash` 回傳 None，行為退化至 Layer 1 |
| 舊 structure.json 無 `body_hash` key | `.get("body_hash")` 回傳 None，無 KeyError |
