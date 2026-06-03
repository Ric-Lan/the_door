# Snapshot 持久化契約對賬 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 snapshot 落盤契約只有一個誠實、被強制的真相——修正過時/太鬆的 `snapshot.schema.json`、在落盤時用 jsonschema 校驗（mirror doubt_store）、用雙向欄位雙射測試守住不再漂移，並提供唯讀合規稽核。

**Architecture:** 修 schema 為 strict（補 4 欄 + `additionalProperties:false`）；抽單一落盤口 `_write_snapshot` 在 persist 時 `jsonschema.validate`（fail-closed）；讀取路徑不動（向後相容）；雙向雙射 + round-trip + 負向測試 + on-demand 稽核守住契約。

**Tech Stack:** Python 3.12、`jsonschema`（**既有依賴**，`doubt_store` 已用 `Draft202012Validator`）、pytest。

**設計依據（並讀）：** `docs/superpowers/specs/2026-06-03-snapshot-contract-reconciliation-design.md`（schema 全文 §5.1、強制點 §5.2、稽核 §5.3、測試 §6、陷阱 §7、可行性 spike §4）。

---

## 關鍵事實（執行前必讀）

- **測試 cwd**：所有 pytest/git 在**內層** `the_door/` 執行（`testpaths=["tests"]`）。Windows console cp950，跑測試前置 `PYTHONUTF8=1`。docs 在**外層** repo root 的 `docs/`（git 操作用 `git -C <worktree-root>`）。
- **目標檔**：`the_door/schemas/snapshot.schema.json`、`the_door/src/the_door/core/diff/snapshot_store.py`、新測試 `the_door/tests/unit/core/diff/test_snapshot_contract.py`。
- **⚠️ 順序鐵則**：schema 必須**先**修對（Task 1），**才**接上落盤校驗（Task 2）。若先對舊 schema（`label:{type:string}`）接校驗，commit-trigger snapshot（label=null）會全爆。
- **⚠️ 護欄**：`additionalProperties:false` 是防線核心，**任何時候不得為了讓測試/寫入通過改回 `true`**；落盤校驗失敗**讓它拋**（fail-closed），不得 try/except 吞。schema 只「補既有 serialize 已吐欄位 + 收緊」，不增不減欄位。不動讀取路徑、不碰 `core/datamodel/`、不改 `VersionSnapshot` 模型。
- **已驗證事實（spike，無須重驗）**：修正後 schema 對 maximal/manual + minimal/commit 兩 fixture 皆 validate PASS、round-trip True、雙射 True、負向被擋。`json`/`Path` 已在 `snapshot_store.py` import（line 10/17），`jsonschema` 需新增 import。`_SCHEMAS_DIR` 用 5 個 `.parent`（與 `core/scope/doubt_store.py` line 32 同深度）。

---

## File Structure

| 檔案 | 職責 | 本計畫動作 |
|---|---|---|
| `the_door/schemas/snapshot.schema.json` | snapshot 落盤格式的宣告式契約（單一真相） | 修正（Task 1） |
| `the_door/src/the_door/core/diff/snapshot_store.py` | snapshot 建立/持久化/讀取 | 加 schema 載入器 + `_write_snapshot` 落盤口 + 稽核方法（Task 1/2/3） |
| `the_door/tests/unit/core/diff/test_snapshot_contract.py` | 契約不變量測試（雙射/驗證/round-trip/負向/稽核） | 新建，逐 task 追加（Task 1/2/3） |
| `docs/superpowers/specs/2026-06-03-...-design.md` | 設計 | 收尾標記已實作（Task 4） |

---

## Task 1: 修 schema 為 strict + 加 schema 載入器 + 契約測試

**Files:**
- Modify: `the_door/schemas/snapshot.schema.json`（全檔替換為下方內容）
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py`（頂部加 import + 模組級 schema 載入器）
- Create: `the_door/tests/unit/core/diff/test_snapshot_contract.py`

- [ ] **Step 1: 寫失敗測試（契約測試 + 共用 fixtures）**

建立 `the_door/tests/unit/core/diff/test_snapshot_contract.py`，完整內容：

```python
"""Contract tests for the snapshot persistence schema.

Pins snapshot.schema.json as a living contract bound to _serialize_snapshot:
  - both a maximal (manual, all optional present) and a minimal (commit,
    label=null, no optional fields) snapshot must validate;
  - field-name BIJECTION: every object level's declared schema properties
    equal the keys serialize actually emits (catches phantom + missing fields);
  - serialize/deserialize round-trip equivalence;
  - strict mode (additionalProperties:false) rejects unknown fields.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from the_door.core.diff.snapshot_store import SnapshotStore, _get_snapshot_schema
from the_door.models import (
    BlockSummary, DatabaseFreshness, FeatureSummary, RelationSummary,
    VersionSnapshot, VulnerabilityEntry,
)

_V = jsonschema.Draft202012Validator


def _store(tmp_path) -> SnapshotStore:
    return SnapshotStore(tmp_path, store_root=tmp_path)


def _maximal_snapshot() -> VersionSnapshot:
    """trigger=manual, every optional field populated (union of emittable keys)."""
    return VersionSnapshot(
        version_id="v-max", timestamp="2026-06-03T00:00:00+00:00", trigger="manual",
        l1_snapshot={"feat-x": FeatureSummary(
            feature_id="feat-x", label="L", description="D", source_node_count=2,
            confidence="high", trigger_description="because",
            source_nodes=("A.m", "B.n"), confidence_reason="reason")},
        analyzed_files=["a.py"], commit_hash="abc1234", git_tags=["v1.0.0"],
        label="manual-label",
        l1_5_snapshot={"blk-1": BlockSummary(
            block_id="blk-1", label="BL", responsibility="R", confidence="medium")},
        feature_relations_snapshot=[RelationSummary(
            from_feature="feat-x", to_feature="feat-y", relation="depends_on")],
        vulnerabilities_snapshot=[VulnerabilityEntry(
            cve_id="CVE-1", package="p", version="1", severity="high",
            cvss=7.5, source="osv")],
        vulnerability_db_freshness=DatabaseFreshness(
            timestamp="2026-06-03T00:00:00+00:00", mode="online", stale_warning=None),
        codebase_path=Path("/proj"),
    )


def _minimal_snapshot() -> VersionSnapshot:
    """trigger=commit, label=None, no optional L1 fields, empty collections."""
    return VersionSnapshot(
        version_id="v-min", timestamp="2026-06-03T00:00:00+00:00", trigger="commit",
        l1_snapshot={"feat-x": FeatureSummary(
            feature_id="feat-x", label="L", description="D",
            source_node_count=0, confidence="low")},
        analyzed_files=[], commit_hash=None, git_tags=[], label=None,
        l1_5_snapshot={}, feature_relations_snapshot=[],
        vulnerabilities_snapshot=[], vulnerability_db_freshness=None,
        codebase_path=None,
    )


@pytest.mark.parametrize("builder", [_maximal_snapshot, _minimal_snapshot])
def test_serialized_snapshot_validates_against_schema(tmp_path, builder):
    store = _store(tmp_path)
    data = store._serialize_snapshot(builder())
    jsonschema.validate(data, _get_snapshot_schema(), cls=_V)  # must not raise


def test_schema_serialize_field_bijection(tmp_path):
    """Every object level: declared schema properties == emitted keys (both ways).

    Uses the MAXIMAL snapshot as the union of emittable keys (serialize emits
    some L1 fields conditionally — see spec §7.1)."""
    store = _store(tmp_path)
    data = store._serialize_snapshot(_maximal_snapshot())
    schema = _get_snapshot_schema()

    top = schema["properties"]
    l1 = top["l1_snapshot"]["additionalProperties"]["properties"]
    l15 = top["l1_5_snapshot"]["additionalProperties"]["properties"]
    rel = top["feature_relations_snapshot"]["items"]["properties"]
    vuln = top["vulnerabilities_snapshot"]["items"]["properties"]
    fresh = top["vulnerability_db_freshness"]["properties"]

    assert set(top) == set(data)
    assert set(l1) == set(data["l1_snapshot"]["feat-x"])
    assert set(l15) == set(data["l1_5_snapshot"]["blk-1"])
    assert set(rel) == set(data["feature_relations_snapshot"][0])
    assert set(vuln) == set(data["vulnerabilities_snapshot"][0])
    assert set(fresh) == set(data["vulnerability_db_freshness"])


@pytest.mark.parametrize("builder", [_maximal_snapshot, _minimal_snapshot])
def test_snapshot_round_trip_equivalence(tmp_path, builder):
    store = _store(tmp_path)
    data = store._serialize_snapshot(builder())
    assert store._serialize_snapshot(store._deserialize_snapshot(data)) == data


def test_strict_schema_rejects_unknown_field(tmp_path):
    store = _store(tmp_path)
    data = store._serialize_snapshot(_maximal_snapshot())
    data["junk_field"] = "x"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, _get_snapshot_schema(), cls=_V)
```

- [ ] **Step 2: 跑測試，確認失敗（loader 未存在）**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_contract.py -q
```
Expected: **ImportError / collection error**（`cannot import name '_get_snapshot_schema'`）——loader 尚未存在。

- [ ] **Step 3: 修 schema 為 strict（全檔替換）**

把 `the_door/schemas/snapshot.schema.json` **整檔**替換為（注意 `label` 為 `["string","null"]`、6 處 `additionalProperties:false`）：

```json
{
  "title": "The Door Version Snapshot",
  "description": "A persisted record of L1/L1.5 analysis output at a specific point in time",
  "type": "object",
  "required": ["version_id", "timestamp", "trigger", "l1_snapshot", "analyzed_files"],
  "additionalProperties": false,
  "properties": {
    "version_id": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "trigger": { "type": "string", "enum": ["commit", "manual"] },
    "commit_hash": { "type": ["string", "null"] },
    "git_tags": { "type": "array", "items": { "type": "string" } },
    "label": { "type": ["string", "null"] },
    "codebase_path": { "type": ["string", "null"] },
    "l1_snapshot": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["label", "description", "source_node_count", "confidence"],
        "additionalProperties": false,
        "properties": {
          "label": { "type": "string" },
          "description": { "type": "string" },
          "source_node_count": { "type": "integer", "minimum": 0 },
          "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
          "trigger_description": { "type": ["string", "null"] },
          "source_nodes": { "type": "array", "items": { "type": "string" } },
          "confidence_reason": { "type": ["string", "null"] }
        }
      }
    },
    "analyzed_files": { "type": "array", "items": { "type": "string" } },
    "l1_5_snapshot": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["label", "responsibility"],
        "additionalProperties": false,
        "properties": {
          "label": { "type": "string" },
          "responsibility": { "type": "string" },
          "confidence": { "type": "string", "enum": ["high", "medium", "low"] }
        }
      }
    },
    "feature_relations_snapshot": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["from_feature", "to_feature", "relation"],
        "additionalProperties": false,
        "properties": {
          "from_feature": { "type": "string" },
          "to_feature": { "type": "string" },
          "relation": { "type": "string" }
        }
      }
    },
    "vulnerabilities_snapshot": {
      "type": "array",
      "default": [],
      "items": {
        "type": "object",
        "required": ["cve_id", "package", "version", "severity", "cvss", "source"],
        "additionalProperties": false,
        "properties": {
          "cve_id": { "type": "string" },
          "package": { "type": "string" },
          "version": { "type": "string" },
          "severity": { "type": "string", "enum": ["critical", "high", "medium", "low"] },
          "cvss": { "type": "number", "minimum": 0.0, "maximum": 10.0 },
          "source": { "type": "string" }
        }
      }
    },
    "vulnerability_db_freshness": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "properties": {
        "timestamp": { "type": "string", "format": "date-time" },
        "mode": { "type": "string", "enum": ["online", "offline"] },
        "stale_warning": { "type": ["string", "null"] }
      }
    }
  },
  "if": { "properties": { "trigger": { "const": "manual" } } },
  "then": { "required": ["label"] }
}
```

- [ ] **Step 4: 加 schema 載入器到 `snapshot_store.py`**

在 `the_door/src/the_door/core/diff/snapshot_store.py` 頂部 import 區（現有 import 之後、`logger = ...` 之前）加：

```python
import jsonschema
```

在 `logger = logging.getLogger(__name__)` 之後、第一個 class 之前，加模組級 schema 載入器（比照 `core/scope/doubt_store.py` line 32–48）：

```python
# ---------------------------------------------------------------------------
# Schema loading — same pattern as core/scope/doubt_store.py
# ---------------------------------------------------------------------------
_SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent.parent / "schemas"
_SNAPSHOT_SCHEMA_PATH = _SCHEMAS_DIR / "snapshot.schema.json"
_snapshot_schema: dict | None = None


def _load_snapshot_schema() -> dict:
    """Load the snapshot JSON schema."""
    with open(_SNAPSHOT_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _get_snapshot_schema() -> dict:
    """Return the cached snapshot schema, loading on first access."""
    global _snapshot_schema  # noqa: PLW0603
    if _snapshot_schema is None:
        _snapshot_schema = _load_snapshot_schema()
    return _snapshot_schema
```

- [ ] **Step 5: 跑測試，確認通過**

Run：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_contract.py -q
```
Expected: **全 PASS**（2 validate-參數化 ×2 + bijection + round-trip ×2 + negative = 6 個）。
若 `test_schema_serialize_field_bijection` 報差集非空 → schema 與 serialize 欄位不符，對照 spec §4.1 修 schema（不可改 serialize）。

- [ ] **Step 6: Commit**

```
git add the_door/schemas/snapshot.schema.json the_door/src/the_door/core/diff/snapshot_store.py the_door/tests/unit/core/diff/test_snapshot_contract.py
git commit -m "fix(snapshot): correct + tighten snapshot schema, add loader + contract tests"
```

---

## Task 2: 落盤時運行期校驗（`_write_snapshot` + rewire create/patch）

**Files:**
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py`（加 `_write_snapshot` 方法；改 `create_snapshot` line 109–114、`patch_snapshot` line 248–250）
- Modify: `the_door/tests/unit/core/diff/test_snapshot_contract.py`（追加強制測試）

- [ ] **Step 1: 寫失敗測試（強制 + 正常路徑）**

在 `test_snapshot_contract.py` **末尾追加**：

```python
def test_create_snapshot_rejects_out_of_contract_value(tmp_path):
    """Persist-time validation is wired & fail-closed: an out-of-enum
    confidence makes the serialized snapshot violate the schema, so the
    write must raise (not silently persist invalid data)."""
    store = _store(tmp_path)
    with pytest.raises(jsonschema.ValidationError):
        store.create_snapshot(
            l1_snapshot={"f": FeatureSummary(
                feature_id="f", label="L", description="D",
                source_node_count=0, confidence="BOGUS")},  # not in enum
            feature_relations=[], analyzed_files=[], trigger="commit",
        )


def test_create_snapshot_normal_commit_path_unaffected(tmp_path):
    """A normal commit snapshot (label=None) still persists & reloads."""
    store = _store(tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={"f": FeatureSummary(
            feature_id="f", label="L", description="D",
            source_node_count=0, confidence="low")},
        feature_relations=[], analyzed_files=["a.py"], trigger="commit",
    )
    assert snap.label is None
    assert store.get_snapshot(snap.version_id) is not None
```

- [ ] **Step 2: 跑測試，確認失敗**

Run：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_contract.py::test_create_snapshot_rejects_out_of_contract_value -q
```
Expected: **FAIL**（目前 `create_snapshot` 不校驗，bogus confidence 被靜默寫入、不拋）。

- [ ] **Step 3: 加 `_write_snapshot` 方法**

在 `SnapshotStore` 內、`_serialize_snapshot` 方法**之前**（緊接在最後一個 public 方法之後、private 區開頭即可），加：

```python
    def _write_snapshot(self, snapshot: VersionSnapshot) -> None:
        """Serialize, validate against the schema (fail-closed), then write.

        The single chokepoint for persisting a snapshot to disk. Validation
        is intentionally on persist only — the read path stays tolerant of
        legacy snapshots (see spec §7.2)."""
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        data = self._serialize_snapshot(snapshot)
        jsonschema.validate(
            data, _get_snapshot_schema(), cls=jsonschema.Draft202012Validator
        )
        file_path = self._snapshots_dir / f"{snapshot.version_id}.json"
        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
```

- [ ] **Step 4: 改 `create_snapshot` 用 `_write_snapshot`**

在 `create_snapshot` 中，把現有的：
```python
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._snapshots_dir / f"{version_id}.json"
        data = self._serialize_snapshot(snapshot)
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        return snapshot
```
替換為：
```python
        self._write_snapshot(snapshot)

        return snapshot
```

- [ ] **Step 5: 改 `patch_snapshot` 用 `_write_snapshot`**

在 `patch_snapshot` 中，把現有的：
```python
        data = self._serialize_snapshot(snap)
        file_path = self._snapshots_dir / f"{snap.version_id}.json"
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        return snap, skipped
```
替換為：
```python
        self._write_snapshot(snap)

        return snap, skipped
```

- [ ] **Step 6: 跑契約 + store 測試，確認通過**

Run：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_contract.py -q
```
Expected: **全 PASS**（含新的 2 個強制測試）。

- [ ] **Step 7: 跑全套件（零回歸 + §7.6 enum 逃生閥檢查）**

Run：
```
PYTHONUTF8=1 python -m pytest
```
Expected: 全 PASS（基準以當下 main 為準，無新 fail/error）。
**⚠️ 若有既有測試因 `jsonschema.ValidationError` 失敗**（多半是某既有路徑吐出 enum 外的 `confidence`/`severity`/`mode`/`trigger`，或缺必填欄）：**停下回報（BLOCKED）**——依 spec §7.3 逃生閥評估「碼該修」或「enum 該放寬」，**不得**為了過關把 `additionalProperties` 改回 `true` 或拿掉 enum。

- [ ] **Step 8: Commit**

```
git add the_door/src/the_door/core/diff/snapshot_store.py the_door/tests/unit/core/diff/test_snapshot_contract.py
git commit -m "feat(snapshot): validate at persist via single _write_snapshot chokepoint"
```

---

## Task 3: 唯讀合規稽核 `audit_conformance()`

**Files:**
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py`（加 public 方法 `audit_conformance`）
- Modify: `the_door/tests/unit/core/diff/test_snapshot_contract.py`（追加稽核測試）

- [ ] **Step 1: 寫失敗測試**

在 `test_snapshot_contract.py` 末尾追加：

```python
def test_audit_conformance_reports_only_nonconforming(tmp_path):
    """Read-only audit: lists on-disk snapshots that fail the current schema,
    leaves everything untouched. (Tests the tool's logic via fixtures — never
    asserts on a machine's real .the-door/ data; see spec §7.5.)"""
    store = _store(tmp_path)
    # one conforming snapshot, written through the validated path
    good = store.create_snapshot(
        l1_snapshot={"f": FeatureSummary(
            feature_id="f", label="L", description="D",
            source_node_count=0, confidence="low")},
        feature_relations=[], analyzed_files=["a.py"], trigger="commit",
    )
    # one non-conforming file written directly (bypasses validation)
    bad_path = store._snapshots_dir / "bad.json"
    bad_path.write_text(json.dumps({
        "version_id": "bad-id", "timestamp": "2026-06-03T00:00:00+00:00",
        "trigger": "commit", "l1_snapshot": {}, "analyzed_files": [],
        "junk_field": 1,  # violates additionalProperties:false
    }), encoding="utf-8")

    report = store.audit_conformance()

    assert {r["version_id"] for r in report} == {"bad-id"}
    assert store.get_snapshot(good.version_id) is not None  # untouched
    assert bad_path.exists()  # not deleted
```

- [ ] **Step 2: 跑測試，確認失敗**

Run：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_contract.py::test_audit_conformance_reports_only_nonconforming -q
```
Expected: **FAIL**（`AttributeError: 'SnapshotStore' object has no attribute 'audit_conformance'`）。

- [ ] **Step 3: 加 `audit_conformance` 方法**

在 `SnapshotStore` 內（與其他 public 方法並列，例如放在 `delete_snapshot` 之後、private `_load_all_snapshots` 之前），加：

```python
    def audit_conformance(self) -> list[dict]:
        """Read-only: validate every on-disk snapshot against the current schema.

        Returns a list of {"version_id", "file", "error"} for NON-conforming
        snapshots (empty list = all conform). Does not modify, reject, or
        delete anything. Intended for on-demand use (not the hot path; not a
        CI assertion — see spec §7.5)."""
        schema = _get_snapshot_schema()
        report: list[dict] = []
        if not self._snapshots_dir.is_dir():
            return report
        for path in sorted(self._snapshots_dir.glob("*.json")):
            version_id = None
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                version_id = data.get("version_id")
                jsonschema.validate(
                    data, schema, cls=jsonschema.Draft202012Validator
                )
            except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
                report.append({
                    "version_id": version_id,
                    "file": str(path),
                    "error": str(exc),
                })
        return report
```

- [ ] **Step 4: 跑測試，確認通過**

Run：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_contract.py -q
```
Expected: **全 PASS**。

- [ ] **Step 5: Commit**

```
git add the_door/src/the_door/core/diff/snapshot_store.py the_door/tests/unit/core/diff/test_snapshot_contract.py
git commit -m "feat(snapshot): add read-only audit_conformance() for legacy snapshots"
```

---

## Task 4: 收尾 — 標記 spec 已實作 + 覆蓋驗收

**Files:**
- Modify: `docs/superpowers/specs/2026-06-03-snapshot-contract-reconciliation-design.md`（標頭狀態）

- [ ] **Step 1: 全套件 + 覆蓋驗收**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest --cov=the_door.core.diff.snapshot_store --cov-report=term-missing tests/
```
Expected: 全 PASS；`snapshot_store.py` 覆蓋率不低於改前（新增的 `_write_snapshot`/`audit_conformance`/loader 由新測試覆蓋）。記下數字。

- [ ] **Step 2: 確認改動面**

Run（cwd = worktree root）：
```
git diff --stat <task1之前的commit>..HEAD
```
Expected：僅 `the_door/schemas/snapshot.schema.json`、`the_door/src/the_door/core/diff/snapshot_store.py`、`the_door/tests/unit/core/diff/test_snapshot_contract.py`。**不得有其他 `.py` 被改**（讀取路徑、`core/datamodel/`、`VersionSnapshot` 模型皆未動）。若有他檔變更 → 回報。

- [ ] **Step 3: 標記 spec 已實作**

編輯 `docs/superpowers/specs/2026-06-03-snapshot-contract-reconciliation-design.md` 標頭，把：
```
> **日期**：2026-06-03　**狀態**：設計核准、待寫 plan
```
改為：
```
> **日期**：2026-06-03　**狀態**：已實作（plan: docs/superpowers/plans/2026-06-03-snapshot-contract-reconciliation.md）
```

- [ ] **Step 4: Commit**

```
git -C <worktree-root> add docs/superpowers/specs/2026-06-03-snapshot-contract-reconciliation-design.md
git -C <worktree-root> commit -m "docs: mark snapshot contract reconciliation implemented"
```

- [ ] **Step 5: 收尾回報**

回報：schema 修正為 strict（補 codebase_path + 3 L1 選填欄 + label→[string,null] + 6 處 additionalProperties:false）；落盤經單一 `_write_snapshot` 口運行期校驗（fail-closed）；雙向雙射 + round-trip（maximal+minimal）+ 負向 + 稽核測試全綠；全套件零回歸；改動面僅 schema + snapshot_store + 1 新測試檔；讀取路徑/模型/datamodel 未動。等使用者決定 merge（本地 merge、不主動 push）。

---

## Self-Review（已執行）

- **Spec coverage**：§5.1 schema→Task1 Step3；§5.2 載入器+`_write_snapshot`+rewire→Task1 Step4 + Task2；§5.3 稽核→Task3；§6 測試 1–5→Task1/2/3（test 1 含 maximal+minimal 參數化、test 2 雙射六層、test 3 round-trip 兩 fixture、test 4 負向、test 5 稽核）；§7.3 逃生閥→Task2 Step7；§7.6 enum→Task2 Step7；§9 驗收→Task4。全覆蓋。
- **Placeholder scan**：無 TBD；所有 step 有完整碼/指令/預期輸出。`<task1之前的commit>`/`<worktree-root>` 是執行期實值佔位（指令說明），非邏輯佔位。
- **Type/簽名一致**：`_get_snapshot_schema()`、`_write_snapshot(self, snapshot)`、`audit_conformance(self) -> list[dict]`、`jsonschema.Draft202012Validator`、`SnapshotStore(tmp_path, store_root=tmp_path)`、`create_snapshot(l1_snapshot=, feature_relations=, analyzed_files=, trigger=)`——跨 task 一致，且與 §4 spike 實際呼叫一致。
