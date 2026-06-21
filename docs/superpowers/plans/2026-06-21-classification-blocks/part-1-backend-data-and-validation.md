# 功能分類層 — Part 1：後端資料層 + 驗證 + 寫入

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 喚醒 L1.5 區塊層的資料載體——`BlockSummary` 擴充三欄位、序列化、schema、結構驗證、`snapshot_patch` 寫入路徑。

**Architecture:** 純加法擴充既有 `BlockSummary` / `l1_5_snapshot`（不 bump 契約）；新增純函式驗證模組 `core/classification/block_validator.py`；寫入沿用既有 `snapshot_patch`（加 `blocks` 參數，整批取代）。不新增 MCP 工具。

**Tech Stack:** Python 3、dataclasses、jsonschema、pytest

**Spec:** `docs/superpowers/specs/2026-06-21-feature-classification-blocks-design.md`（§4、§5）

---

## 環境速查

| 項目 | 路徑 |
|---|---|
| 內層 repo（pytest cwd） | `the_door/` |
| 測試前置（Windows） | `PYTHONUTF8=1` |
| 跑測試 | `python -m pytest`（C4 hook 擋 `python -c` 與臨時 .py） |

---

## Task 1：BlockSummary 加三欄位

**Files:**
- Modify: `the_door/src/the_door/models/snapshot.py:43-50`
- Test: `the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py`

- [ ] **Step 1：寫 failing test（欄位與預設值）**

加到 `test_snapshot_store_roundtrip.py` 末尾：

```python
from the_door.models import BlockSummary


class TestBlockSummaryDefaults:
    def test_classification_fields_default_empty(self):
        b = BlockSummary(block_id="blk-x", label="X 功能群組說明", responsibility="處理 X 類工作")
        assert b.related_features == ()
        assert b.parent_block_id is None
        assert b.is_new_this_version is False

    def test_classification_fields_settable(self):
        b = BlockSummary(
            block_id="blk-x", label="X 功能群組說明", responsibility="處理 X",
            related_features=("feat-a", "feat-b"),
            parent_block_id="blk-parent",
            is_new_this_version=True,
        )
        assert b.related_features == ("feat-a", "feat-b")
        assert b.parent_block_id == "blk-parent"
        assert b.is_new_this_version is True
```

- [ ] **Step 2：跑測試確認 fail**

Run: `python -m pytest tests/unit/core/diff/test_snapshot_store_roundtrip.py::TestBlockSummaryDefaults -v`
Expected: FAIL（`TypeError: unexpected keyword argument 'related_features'`）

- [ ] **Step 3：擴充 dataclass**

`models/snapshot.py` 的 `BlockSummary` 改為：

```python
@dataclass(frozen=True)
class BlockSummary:
    """Summarized block data stored in a version snapshot (L1.5)."""

    block_id: str
    label: str
    responsibility: str
    confidence: str | None = None
    related_features: tuple[str, ...] = ()      # 成員 feature_id（tuple 維持 frozen 可雜湊）
    parent_block_id: str | None = None          # None=頂層；有值=子區塊
    is_new_this_version: bool = False            # 跨版本自動開新類的標記
```

- [ ] **Step 4：跑測試確認 pass**

Run: `python -m pytest tests/unit/core/diff/test_snapshot_store_roundtrip.py::TestBlockSummaryDefaults -v`
Expected: PASS

- [ ] **Step 5：Commit**

```bash
git add the_door/src/the_door/models/snapshot.py the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py
git commit -m "feat(models): add classification fields to BlockSummary"
```

---

## Task 2：序列化 / 反序列化（含 omit 慣例）

**Files:**
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py:365-371`（_serialize）、`448-455`（_deserialize）
- Test: `the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py`

既有慣例（`test_minimal_summary_omits_optional_keys`）：空 / 預設的 optional 欄位**不寫進 JSON**，保持檔案小。新欄位遵守此慣例。

- [ ] **Step 1：寫 failing test（round-trip + omit）**

加到 `test_snapshot_store_roundtrip.py`：

```python
class TestBlockSummaryOnDisk:
    def _block_snap(self, store, blocks):
        snap = store.create_snapshot(
            l1_snapshot={}, feature_relations=[], analyzed_files=[],
            trigger="manual", label="blk", l1_5_snapshot=blocks,
        )
        return snap.version_id

    def test_block_round_trips(self, store):
        blocks = {
            "blk-core": BlockSummary(
                block_id="blk-core", label="核心分析引擎群組", responsibility="抽取與分析",
                related_features=("feat-a",), is_new_this_version=True,
            ),
        }
        vid = self._block_snap(store, blocks)
        loaded = store.get_snapshot(vid)
        b = loaded.l1_5_snapshot["blk-core"]
        assert b.related_features == ("feat-a",)
        assert b.is_new_this_version is True
        assert b.parent_block_id is None

    def test_empty_block_fields_omitted(self, store, tmp_path):
        blocks = {
            "blk-core": BlockSummary(
                block_id="blk-core", label="核心分析引擎群組", responsibility="抽取與分析",
            ),
        }
        vid = self._block_snap(store, blocks)
        raw = json.loads((tmp_path / ".the-door" / "snapshots" / f"{vid}.json").read_text(encoding="utf-8"))
        entry = raw["l1_5_snapshot"]["blk-core"]
        assert "related_features" not in entry
        assert "parent_block_id" not in entry
        assert "is_new_this_version" not in entry

    def test_legacy_block_deserializes_with_defaults(self, store, tmp_path):
        vid = self._block_snap(store, {})
        path = tmp_path / ".the-door" / "snapshots" / f"{vid}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["l1_5_snapshot"] = {"blk-old": {"label": "舊區塊群組說明", "responsibility": "舊職責"}}
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = store.get_snapshot(vid)
        b = loaded.l1_5_snapshot["blk-old"]
        assert b.related_features == ()
        assert b.parent_block_id is None
        assert b.is_new_this_version is False
```

- [ ] **Step 2：跑測試確認 fail**

Run: `python -m pytest tests/unit/core/diff/test_snapshot_store_roundtrip.py::TestBlockSummaryOnDisk -v`
Expected: FAIL（round-trip 取不到新欄位 / omit 斷言失敗）

- [ ] **Step 3：改 _serialize（365-371）**

把現有：

```python
        l1_5_data = {}
        for bid, bs in snapshot.l1_5_snapshot.items():
            l1_5_data[bid] = {
                "label": bs.label,
                "responsibility": bs.responsibility,
                "confidence": bs.confidence,
            }
```

改為（新欄位條件序列化、空值 omit）：

```python
        l1_5_data = {}
        for bid, bs in snapshot.l1_5_snapshot.items():
            entry = {
                "label": bs.label,
                "responsibility": bs.responsibility,
                "confidence": bs.confidence,
            }
            if bs.related_features:
                entry["related_features"] = list(bs.related_features)
            if bs.parent_block_id is not None:
                entry["parent_block_id"] = bs.parent_block_id
            if bs.is_new_this_version:
                entry["is_new_this_version"] = True
            l1_5_data[bid] = entry
```

- [ ] **Step 4：改 _deserialize（448-455）**

把現有：

```python
        l1_5_snapshot = {}
        for bid, bdata in data.get("l1_5_snapshot", {}).items():
            l1_5_snapshot[bid] = BlockSummary(
                block_id=bid,
                label=bdata["label"],
                responsibility=bdata["responsibility"],
                confidence=bdata.get("confidence"),
            )
```

改為（`.get()` 容錯舊資料）：

```python
        l1_5_snapshot = {}
        for bid, bdata in data.get("l1_5_snapshot", {}).items():
            l1_5_snapshot[bid] = BlockSummary(
                block_id=bid,
                label=bdata["label"],
                responsibility=bdata["responsibility"],
                confidence=bdata.get("confidence"),
                related_features=tuple(bdata.get("related_features", ()) or ()),
                parent_block_id=bdata.get("parent_block_id"),
                is_new_this_version=bdata.get("is_new_this_version", False),
            )
```

- [ ] **Step 5：跑測試確認 pass**

Run: `python -m pytest tests/unit/core/diff/test_snapshot_store_roundtrip.py -v`
Expected: PASS（全檔，含既有 FeatureSummary 測試）

- [ ] **Step 6：Commit**

```bash
git add the_door/src/the_door/core/diff/snapshot_store.py the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py
git commit -m "feat(snapshot): serialize BlockSummary classification fields (omit empty)"
```

---

## Task 3：更新 snapshot schema（避免 audit 誤標）

**Files:**
- Modify: `the_door/src/the_door/schemas/snapshot.schema.json:52-61`（l1_5_snapshot block properties）
- Test: `the_door/tests/unit/core/diff/test_snapshot_contract.py`

block 物件是 `additionalProperties: false`，不加欄位會讓 `audit_conformance` 把新快照標 non-conforming。

- [ ] **Step 1：寫 failing test（audit 通過）**

加到 `test_snapshot_contract.py`：

```python
def test_block_with_classification_fields_conforms(tmp_path):
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.models import BlockSummary
    store = SnapshotStore(tmp_path)
    store.create_snapshot(
        l1_snapshot={}, feature_relations=[], analyzed_files=[],
        trigger="manual", label="blk",
        l1_5_snapshot={"blk-core": BlockSummary(
            block_id="blk-core", label="核心分析引擎群組", responsibility="抽取與分析",
            related_features=("feat-a",), parent_block_id=None, is_new_this_version=True,
        )},
    )
    report = store.audit_conformance()
    assert report == [], f"expected conforming, got {report}"
```

- [ ] **Step 2：跑測試確認 fail**

Run: `python -m pytest tests/unit/core/diff/test_snapshot_contract.py::test_block_with_classification_fields_conforms -v`
Expected: FAIL（audit 回報 `additionalProperties` 違規）

- [ ] **Step 3：加 schema 欄位**

`snapshot.schema.json` 的 `l1_5_snapshot` block `properties`（52-61）加三個 optional 欄位，`required` 維持 `["label", "responsibility"]`：

```json
        "properties": {
          "label": { "type": "string" },
          "responsibility": { "type": "string" },
          "confidence": { "oneOf": [
            { "const": "high", "description": "抽取信心高" },
            { "const": "medium", "description": "抽取信心中" },
            { "const": "low", "description": "抽取信心低" },
            { "type": "null", "description": "未評估（來源未給信心）" }
          ] },
          "related_features": { "type": "array", "items": { "type": "string" } },
          "parent_block_id": { "type": ["string", "null"] },
          "is_new_this_version": { "type": "boolean" }
        }
```

- [ ] **Step 4：跑測試確認 pass**

Run: `python -m pytest tests/unit/core/diff/test_snapshot_contract.py -v`
Expected: PASS

- [ ] **Step 5：Commit**

```bash
git add the_door/src/the_door/schemas/snapshot.schema.json the_door/tests/unit/core/diff/test_snapshot_contract.py
git commit -m "feat(schema): allow classification fields on l1_5 blocks"
```

---

## Task 4：block_validator（五項結構不變量）

**Files:**
- Create: `the_door/src/the_door/core/classification/block_validator.py`
- Test: `the_door/tests/unit/core/classification/test_block_validator.py`（新檔，需建目錄）

只驗**純結構**（兩層、單一歸屬、功能只掛葉、窮盡、交叉引用）。命名規範**不**在此硬驗
（屬語意 + `language_check` 中文行為未實測），改由 prompt 軟約束（Part 2）。

- [ ] **Step 1：寫 failing tests**

建 `the_door/tests/unit/core/classification/test_block_validator.py`：

```python
import pytest

from the_door.core.classification.block_validator import (
    BlockValidationError,
    validate_blocks,
)
from the_door.models import BlockSummary


def _b(bid, feats=(), parent=None):
    return BlockSummary(
        block_id=bid, label=bid + " 群組功能說明", responsibility="職責說明",
        related_features=tuple(feats), parent_block_id=parent,
    )


def test_valid_two_level_tree_passes():
    blocks = {
        "blk-top": _b("blk-top"),
        "blk-leaf": _b("blk-leaf", ["feat-a", "feat-b"], parent="blk-top"),
        "blk-solo": _b("blk-solo", ["feat-c"]),
    }
    validate_blocks(blocks, {"feat-a", "feat-b", "feat-c"})


def test_three_levels_rejected():
    blocks = {
        "blk-top": _b("blk-top"),
        "blk-mid": _b("blk-mid", parent="blk-top"),
        "blk-leaf": _b("blk-leaf", ["feat-a"], parent="blk-mid"),
    }
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a"})
    assert e.value.code == "block.too_deep"


def test_dangling_parent_rejected():
    blocks = {"blk-leaf": _b("blk-leaf", ["feat-a"], parent="blk-missing")}
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a"})
    assert e.value.code == "block.dangling_parent"


def test_parent_with_features_rejected():
    blocks = {
        "blk-top": _b("blk-top", ["feat-a"]),
        "blk-leaf": _b("blk-leaf", ["feat-b"], parent="blk-top"),
    }
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a", "feat-b"})
    assert e.value.code == "block.parent_has_features"


def test_duplicate_membership_rejected():
    blocks = {
        "blk-1": _b("blk-1", ["feat-a"]),
        "blk-2": _b("blk-2", ["feat-a"]),
    }
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a"})
    assert e.value.code == "block.duplicate_membership"


def test_unknown_feature_rejected():
    blocks = {"blk-1": _b("blk-1", ["feat-ghost"])}
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a"})
    assert e.value.code == "block.unknown_feature"


def test_unclassified_feature_rejected():
    blocks = {"blk-1": _b("blk-1", ["feat-a"])}
    with pytest.raises(BlockValidationError) as e:
        validate_blocks(blocks, {"feat-a", "feat-b"})
    assert e.value.code == "block.unclassified"
```

- [ ] **Step 2：跑測試確認 fail**

Run: `python -m pytest tests/unit/core/classification/test_block_validator.py -v`
Expected: FAIL（`ModuleNotFoundError: block_validator`）

- [ ] **Step 3：建驗證模組**

建 `the_door/src/the_door/core/classification/block_validator.py`：

```python
"""Structural validation of an L1.5 block tree (max two levels).

Pure functions, no I/O. Called by snapshot_store.patch_snapshot before
persisting blocks. Enforces the STRUCTURAL invariants from
docs/superpowers/specs/2026-06-21-feature-classification-blocks-design.md §5.
Semantic correctness (歸得準不準) and naming are NOT checked here (C7 boundary;
naming is a prompt-level soft constraint).
"""
from __future__ import annotations

from the_door.models import BlockSummary

UNCLASSIFIED_BLOCK_ID = "blk-unclassified"


class BlockValidationError(Exception):
    """Raised when a block tree violates a structural invariant."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def validate_blocks(
    blocks: dict[str, BlockSummary],
    feature_ids: set[str],
) -> None:
    """Validate a block tree. Raises BlockValidationError on first violation.

    feature_ids = the current snapshot's l1_snapshot keys (the universe that
    must be exhaustively classified).
    """
    # 1. two-level cap: a child's parent must exist and be top-level
    for bid, b in blocks.items():
        if b.parent_block_id is not None:
            parent = blocks.get(b.parent_block_id)
            if parent is None:
                raise BlockValidationError(
                    "block.dangling_parent",
                    f"block {bid!r} parent {b.parent_block_id!r} not found",
                )
            if parent.parent_block_id is not None:
                raise BlockValidationError(
                    "block.too_deep",
                    f"block {bid!r} is nested 3+ levels (max two)",
                )

    # 2. features only on leaf blocks
    parents = {b.parent_block_id for b in blocks.values() if b.parent_block_id}
    for bid, b in blocks.items():
        if bid in parents and b.related_features:
            raise BlockValidationError(
                "block.parent_has_features",
                f"block {bid!r} has children, so related_features must be empty",
            )

    # 3. single membership + cross-ref existence
    seen: dict[str, str] = {}
    for bid, b in blocks.items():
        for fid in b.related_features:
            if fid not in feature_ids:
                raise BlockValidationError(
                    "block.unknown_feature",
                    f"block {bid!r} references unknown feature {fid!r}",
                )
            if fid in seen:
                raise BlockValidationError(
                    "block.duplicate_membership",
                    f"feature {fid!r} in both {seen[fid]!r} and {bid!r}",
                )
            seen[fid] = bid

    # 4. exhaustiveness
    missing = feature_ids - set(seen)
    if missing:
        raise BlockValidationError(
            "block.unclassified",
            f"{len(missing)} feature(s) not in any block: {sorted(missing)}; "
            f"put them in {UNCLASSIFIED_BLOCK_ID!r}",
        )
```

- [ ] **Step 4：跑測試確認 pass**

Run: `python -m pytest tests/unit/core/classification/test_block_validator.py -v`
Expected: PASS（7 passed）

- [ ] **Step 5：Commit**

```bash
git add the_door/src/the_door/core/classification/block_validator.py the_door/tests/unit/core/classification/test_block_validator.py
git commit -m "feat(classification): add structural block-tree validator"
```

---

## Task 5：snapshot_patch 加 blocks 參數

**Files:**
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py:203-266`（patch_snapshot）
- Modify: `the_door/src/the_door/mcp/tools/snapshot_patch_tool.py`
- Test: `the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py`

- [ ] **Step 1：寫 failing test（patch 寫入 + 驗證拒絕）**

加到 `test_snapshot_store_roundtrip.py`：

```python
class TestPatchBlocks:
    def _seed(self, store):
        from the_door.models import FeatureSummary
        snap = store.create_snapshot(
            l1_snapshot={
                "feat-a": FeatureSummary("feat-a", "A", "...", 1, "high"),
                "feat-b": FeatureSummary("feat-b", "B", "...", 1, "high"),
            },
            feature_relations=[], analyzed_files=[], trigger="manual", label="seed",
        )
        return snap

    def test_patch_writes_blocks(self, store):
        snap = self._seed(store)
        store.patch_snapshot(
            version_ref=snap.version_id,
            blocks={"blk-1": {
                "label": "全部功能群組說明", "responsibility": "處理全部",
                "related_features": ["feat-a", "feat-b"],
            }},
        )
        loaded = store.get_snapshot(snap.version_id)
        assert set(loaded.l1_5_snapshot["blk-1"].related_features) == {"feat-a", "feat-b"}

    def test_patch_rejects_unclassified(self, store):
        from the_door.core.classification.block_validator import BlockValidationError
        snap = self._seed(store)
        with pytest.raises(BlockValidationError):
            store.patch_snapshot(
                version_ref=snap.version_id,
                blocks={"blk-1": {
                    "label": "只有 A 的群組說明", "responsibility": "處理 A",
                    "related_features": ["feat-a"],
                }},
            )
```

- [ ] **Step 2：跑測試確認 fail**

Run: `python -m pytest tests/unit/core/diff/test_snapshot_store_roundtrip.py::TestPatchBlocks -v`
Expected: FAIL（`patch_snapshot` 不接受 `blocks`）

- [ ] **Step 3：patch_snapshot 加 blocks 參數**

簽名（203-211）加 `blocks`：

```python
    def patch_snapshot(
        self,
        version_ref: str,
        source_nodes_by_feature: dict[str, list[str]] | None = None,
        analyzed_files: list[str] | None = None,
        feature_metadata_by_feature: dict[str, dict] | None = None,
        project_summary: str | None = None,
        version_narratives: dict[str, str] | None = None,
        blocks: dict[str, dict] | None = None,
    ) -> tuple["VersionSnapshot", list[str]]:
```

在 `snap = dataclasses.replace(snap, **snap_kwargs)`（262）**之前**插入（建 BlockSummary、驗證、整批取代）：

```python
        if blocks is not None:
            from the_door.core.classification.block_validator import validate_blocks
            from the_door.models import BlockSummary
            block_objs = {
                bid: BlockSummary(
                    block_id=bid,
                    label=bd["label"],
                    responsibility=bd.get("responsibility", ""),
                    confidence=bd.get("confidence"),
                    related_features=tuple(bd.get("related_features", ()) or ()),
                    parent_block_id=bd.get("parent_block_id"),
                    is_new_this_version=bd.get("is_new_this_version", False),
                )
                for bid, bd in blocks.items()
            }
            validate_blocks(block_objs, set(new_l1.keys()))
            snap_kwargs["l1_5_snapshot"] = block_objs
```

（`new_l1` 即 patch 後的 l1_snapshot dict，於 228 建立；keys 不變，當作 feature 全集。）

- [ ] **Step 4：跑測試確認 pass**

Run: `python -m pytest tests/unit/core/diff/test_snapshot_store_roundtrip.py::TestPatchBlocks -v`
Expected: PASS

- [ ] **Step 5：snapshot_patch_tool 加 blocks**

`snapshot_patch_tool.py` 的 `TOOL_SCHEMA["properties"]` 加：

```python
        "blocks": {
            "type": "object",
            "description": (
                "Optional. 整批取代 l1_5 區塊。block_id → "
                "{label, responsibility, related_features[], parent_block_id?, "
                "is_new_this_version?}。寫入前做結構驗證（兩層上限/單一歸屬/窮盡/"
                "功能只掛葉/交叉引用），不過則整批拒絕。"
            ),
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "responsibility": {"type": "string"},
                    "related_features": {"type": "array", "items": {"type": "string"}},
                    "parent_block_id": {"type": ["string", "null"]},
                    "is_new_this_version": {"type": "boolean"},
                },
            },
        },
```

`execute` 把 `blocks` 傳入 `patch_snapshot`，並用 try/except 捕 `BlockValidationError` 回錯誤封包。把 `store.patch_snapshot(...)` 呼叫改為包含 `blocks=arguments.get("blocks")`，並在外層加：

```python
    from the_door.core.classification.block_validator import BlockValidationError
    try:
        snap, skipped = store.patch_snapshot(
            version_ref=arguments["version_ref"],
            source_nodes_by_feature=arguments.get("source_nodes_by_feature") or {},
            analyzed_files=arguments.get("analyzed_files"),
            feature_metadata_by_feature=arguments.get("feature_metadata_by_feature"),
            project_summary=arguments.get("project_summary"),
            version_narratives=version_narratives,
            blocks=arguments.get("blocks"),
        )
    except SnapshotNotFoundError as e:
        return make_error_envelope(
            code="snapshot_not_found", message=str(e), remediation=None,
            source="snapshot_patch_tool.execute",
        )
    except BlockValidationError as e:
        return make_error_envelope(
            code=e.code, message=e.message, remediation=None,
            source="snapshot_patch_tool.execute",
        )
```

**保留既有 `payload` 全部欄位**（version_id / label / patched_features / skipped_features /
project_summary / version_narratives），只新增 `"blocks_written": sorted((arguments.get("blocks") or {}).keys())`。

- [ ] **Step 6：跑回歸 + commit**

Run: `python -m pytest tests/unit/core/diff/ -v`
Expected: PASS（全綠）

```bash
git add the_door/src/the_door/core/diff/snapshot_store.py the_door/src/the_door/mcp/tools/snapshot_patch_tool.py the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py
git commit -m "feat(snapshot): snapshot_patch accepts validated blocks"
```

---

## Part 1 Self-Review

- [x] **Spec coverage**：§4 資料模型(T1)/序列化(T2)/schema(T3)；§5 validator(T4)/patch(T5)。
  命名規範(§5.6)刻意降為 prompt 軟約束（Part 2），理由：language_check 中文行為未實測，
  不寫幻覺 code。此為與 spec 的**明示差異**，待 review 確認。
- [x] **Placeholder scan**：無 TBD/TODO；每步含完整 code。
- [x] **Type consistency**：`validate_blocks(blocks, feature_ids)`、`BlockValidationError(code,message)`、
  `BlockSummary` 欄位名跨 task 一致。
