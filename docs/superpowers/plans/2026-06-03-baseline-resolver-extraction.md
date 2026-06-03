# BaselineResolver 抽出 + UUID 文法收編 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 snapshot baseline 參照解析抽成具名純 class `BaselineResolver`（能指→所指唯一轉譯器），收編第 5 種文法 version_id，使 5 文法收斂一處、消費者去重，且公開契約逐字不變。

**Architecture:** 新檔 `core/diff/baseline_resolver.py` 持純 `resolve(reference, snapshots)`（零 I/O）；`SnapshotStore.resolve_baseline` 變委派薄殼（`_load_all_snapshots()` 留 store＝I/O 末端），刪 store 內 4 私有方法；3 個消費者移除冗餘 get_snapshot 後援。

**Tech Stack:** Python 3.12、pytest。無新依賴（`re`/`datetime` stdlib）。

**設計依據（並讀）：** `docs/superpowers/specs/2026-06-03-baseline-resolver-extraction-design.md`（命題 §1、驗證事實 §2、理論剔除 §3、設計 §4、契約 §5、測試 §6、陷阱 §7）。

---

## 關鍵事實（執行前必讀）

- **測試 cwd**：所有 pytest/git 在**內層** `the_door/` 執行（`testpaths=["tests"]`）。Windows console cp950，跑測試前置 `PYTHONUTF8=1`。docs 在**外層** repo root（涉及 `docs/` 的 git 從 worktree 根目錄＝`git rev-parse --show-toplevel` 輸出執行）。
- **目標檔**：新 `the_door/src/the_door/core/diff/baseline_resolver.py`；改 `the_door/src/the_door/core/diff/snapshot_store.py`、`core/ui/api/handlers/diff.py`、`mcp/tools/snapshot_write_tool.py`、`core/pipeline/incremental_pipeline.py`；新測試 `the_door/tests/unit/core/diff/test_baseline_resolver.py`；改測試 `tests/unit/core/ui/api/handlers/test_diff.py`、`tests/scenario/test_v105_incremental_flow.py`。
- **⚠️ 順序鐵則**：version_id 分支（Task 1，在 resolver 內）必須**先**落地，才能（Task 2）移除消費者的 get_snapshot 後援。否則 `inherit_from=<version_id>` 那組安全網測試（spec §4.4）會紅。Task 1 → Task 2 的順序即滿足。
- **⚠️ 護欄**：`_build_available_list` **逐字搬**（含 `sorted(reverse=True)` 與選填欄位），不得順手優化（`e.available` 被 `diff_cmd` 渲染）。version_id 分支**置 label 之後**（保留行為序）。resolver **零 I/O**（不 import json/Path）。不碰讀取路徑、`VersionSnapshot` 模型、`core/datamodel/`、B-2。
- **已驗證事實（spec §2，無須重驗）**：`VersionSnapshot` 僅 `version_id`/`timestamp`/`trigger` 必填，其餘有 default。`SnapshotNotFoundError(reference, available)` 設 `.reference`/`.available`。store 內 4 私有方法零外部呼叫、零測試直接呼叫。`import re` 在 snapshot_store 僅 `resolve_baseline` 用（line 167）→ 移走後變死 import，須刪；`datetime`/`timezone` 仍用於 `create_snapshot:109`，保留。

---

## File Structure

| 檔案 | 職責 | 本計畫動作 |
|---|---|---|
| `core/diff/baseline_resolver.py` | 5 文法 → snapshot 的純轉譯器 | 新建（Task 1） |
| `core/diff/snapshot_store.py` | snapshot 建立/持久化/讀取 | 加 resolver 實例 + 委派 resolve_baseline + 刪 4 私有方法 + 刪 `import re`（Task 1） |
| `tests/unit/core/diff/test_baseline_resolver.py` | resolver 純單元 + 一個 store 整合 | 新建（Task 1） |
| `core/ui/api/handlers/diff.py` | /api/diff handler | `_resolve_snapshot` 收斂（Task 2） |
| `mcp/tools/snapshot_write_tool.py` | snapshot_write MCP | 移除 get_snapshot 後援（Task 2） |
| `core/pipeline/incremental_pipeline.py` | 增量 pipeline | `_resolve_baseline` 收窄例外 + 補 import（Task 2） |
| `tests/unit/core/ui/api/handlers/test_diff.py` | diff handler 測試 | 刪 fallback 測試（Task 2） |
| `tests/scenario/test_v105_incremental_flow.py` | 端對端 scenario | 更新 stale 註解（Task 2） |
| spec 檔 | 設計 | 標已實作（Task 3） |

---

## Task 1: 抽出 `BaselineResolver` + store 委派 + 刪私有方法（原子）

**Files:**
- Create: `the_door/src/the_door/core/diff/baseline_resolver.py`
- Create: `the_door/tests/unit/core/diff/test_baseline_resolver.py`
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py`

- [ ] **Step 1: 寫 resolver 純單元測試（失敗）**

建立 `the_door/tests/unit/core/diff/test_baseline_resolver.py`，完整內容：

```python
"""Unit tests for BaselineResolver — pure reference resolution, no file I/O."""
from __future__ import annotations

import pytest

from the_door.core.diff.baseline_resolver import BaselineResolver
from the_door.models import SnapshotNotFoundError, VersionSnapshot


def _snap(version_id, timestamp, *, label=None, git_tags=None, commit_hash=None):
    return VersionSnapshot(
        version_id=version_id, timestamp=timestamp, trigger="manual",
        label=label, git_tags=git_tags or [], commit_hash=commit_hash,
    )


def test_resolve_by_date_returns_most_recent_on_or_before():
    r = BaselineResolver()
    snaps = [
        _snap("a", "2026-05-01T00:00:00+00:00"),
        _snap("b", "2026-05-05T00:00:00+00:00"),
        _snap("c", "2026-05-10T00:00:00+00:00"),
    ]
    assert r.resolve("2026-05-06", snaps).version_id == "b"


def test_resolve_by_git_tag_exact():
    r = BaselineResolver()
    snaps = [_snap("a", "2026-05-01T00:00:00+00:00", git_tags=["v1.0.0"])]
    assert r.resolve("v1.0.0", snaps).version_id == "a"


def test_resolve_by_commit_sha_prefix():
    r = BaselineResolver()
    snaps = [_snap("a", "2026-05-01T00:00:00+00:00", commit_hash="8de9b18abc123")]
    assert r.resolve("8de9b18", snaps).version_id == "a"


def test_resolve_by_label_exact():
    r = BaselineResolver()
    snaps = [_snap("a", "2026-05-01T00:00:00+00:00", label="my-label")]
    assert r.resolve("my-label", snaps).version_id == "a"


def test_resolve_by_version_id_exact():
    r = BaselineResolver()
    snaps = [_snap("uuid-xyz", "2026-05-01T00:00:00+00:00")]
    assert r.resolve("uuid-xyz", snaps).version_id == "uuid-xyz"


def test_tie_break_most_recent_wins_for_label():
    r = BaselineResolver()
    snaps = [
        _snap("old", "2026-05-01T00:00:00+00:00", label="dup"),
        _snap("new", "2026-05-09T00:00:00+00:00", label="dup"),
    ]
    assert r.resolve("dup", snaps).version_id == "new"


def test_label_wins_over_version_id_when_string_collides():
    """version_id grammar is placed AFTER label (behaviour-preserving)."""
    r = BaselineResolver()
    snaps = [
        _snap("collide", "2026-05-01T00:00:00+00:00"),                  # version_id == "collide"
        _snap("other", "2026-05-02T00:00:00+00:00", label="collide"),  # label == "collide"
    ]
    assert r.resolve("collide", snaps).version_id == "other"  # label branch first


def test_no_match_raises_with_available_list():
    r = BaselineResolver()
    snaps = [_snap("a", "2026-05-01T00:00:00+00:00", label="x")]
    with pytest.raises(SnapshotNotFoundError) as exc:
        r.resolve("nope", snaps)
    assert exc.value.reference == "nope"
    assert any(e["version_id"] == "a" for e in exc.value.available)


def test_store_resolve_baseline_accepts_version_id(tmp_path):
    """B expansion: a raw version_id now resolves through the unified resolver
    (proves the 4 previously-UUID-rejecting entry points are fixed)."""
    from the_door.core.diff.snapshot_store import SnapshotStore
    from the_door.models import FeatureSummary
    store = SnapshotStore(tmp_path, store_root=tmp_path)
    snap = store.create_snapshot(
        l1_snapshot={"f": FeatureSummary(
            feature_id="f", label="L", description="D",
            source_node_count=0, confidence="low")},
        feature_relations=[], analyzed_files=[], trigger="commit",
    )
    assert store.resolve_baseline(snap.version_id).version_id == snap.version_id
```

- [ ] **Step 2: 跑測試，確認失敗**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_baseline_resolver.py -q
```
Expected: **collection error / ImportError**（`cannot import name 'BaselineResolver'`）。

- [ ] **Step 3: 建立 `baseline_resolver.py`**

建立 `the_door/src/the_door/core/diff/baseline_resolver.py`，完整內容（`_resolve_by_date`/`_resolve_by_git_ref`/`_resolve_by_label`/`_build_available_list` 逐字取自 snapshot_store.py 504–582；`resolve` 與 `_resolve_by_version_id` 為新）：

```python
"""Resolve a human baseline reference (the 5 grammars) to a concrete snapshot.

Pure: no file I/O. The store loads snapshots and feeds them in; this class only
interprets the reference and matches. Single home of all reference grammars:
date / git tag / commit SHA / manual label / version_id (UUID).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from the_door.models import SnapshotNotFoundError, VersionSnapshot


class BaselineResolver:
    """Maps a signifier (human reference string) to a signified (VersionSnapshot)."""

    def resolve(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot:
        """Resolve ``reference`` against an already-loaded snapshot list.

        Priority cascade (order is behaviour-preserving — see spec §7.1):
          1. ISO date (YYYY-MM-DD)  -> most recent on or before that date
          2. git tag exact / commit SHA prefix (>=7 chars)
          3. manual label exact
          4. version_id exact (UUID)            # new in B; placed AFTER label
        Raises SnapshotNotFoundError(reference, available) if nothing matches.
        """
        if re.match(r"^\d{4}-\d{2}-\d{2}$", reference):
            return self._resolve_by_date(reference, snapshots)

        result = self._resolve_by_git_ref(reference, snapshots)
        if result is not None:
            return result

        result = self._resolve_by_label(reference, snapshots)
        if result is not None:
            return result

        result = self._resolve_by_version_id(reference, snapshots)
        if result is not None:
            return result

        raise SnapshotNotFoundError(reference, self._build_available_list(snapshots))

    def _resolve_by_date(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot:
        """Find the most recent snapshot on or before the given date."""
        try:
            query_date = datetime.strptime(reference, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError:
            available = self._build_available_list(snapshots)
            raise SnapshotNotFoundError(reference, available)

        candidates = []
        for s in snapshots:
            try:
                ts = datetime.fromisoformat(s.timestamp)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts <= query_date:
                    candidates.append((ts, s))
            except ValueError:
                continue

        if not candidates:
            available = self._build_available_list(snapshots)
            raise SnapshotNotFoundError(reference, available)

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _resolve_by_git_ref(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot | None:
        """Find snapshot by git tag or commit SHA match."""
        candidates: list[VersionSnapshot] = []
        for s in snapshots:
            # Check git tags
            if reference in (s.git_tags or []):
                candidates.append(s)
                continue
            # Check commit SHA (full or abbreviated ≥7 chars)
            if (
                s.commit_hash is not None
                and len(reference) >= 7
                and s.commit_hash.startswith(reference)
            ):
                candidates.append(s)

        if not candidates:
            return None

        return max(candidates, key=lambda s: s.timestamp)

    def _resolve_by_label(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot | None:
        """Find snapshot by exact label match."""
        candidates = [s for s in snapshots if s.label == reference]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.timestamp)

    def _resolve_by_version_id(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot | None:
        """Find snapshot by exact version_id match."""
        for s in snapshots:
            if s.version_id == reference:
                return s
        return None

    def _build_available_list(self, snapshots: list[VersionSnapshot]) -> list[dict]:
        """Build a list of available snapshot summaries for error messages."""
        available = []
        for s in sorted(snapshots, key=lambda x: x.timestamp, reverse=True):
            entry: dict = {
                "version_id": s.version_id,
                "timestamp": s.timestamp,
                "trigger": s.trigger,
            }
            if s.commit_hash:
                entry["commit_hash"] = s.commit_hash
            if s.git_tags:
                entry["git_tags"] = s.git_tags
            if s.label:
                entry["label"] = s.label
            available.append(entry)
        return available
```

- [ ] **Step 4: rewire `snapshot_store.py`（加 import + 實例 + 委派 + 刪 4 私有 + 刪 `import re`）**

4a. 頂部 import 區（現有 `from the_door.core.project_identity import ProjectIdentity`＝line 21 之後）新增：
```python
from the_door.core.diff.baseline_resolver import BaselineResolver
```

4b. 刪除 `import re`（line 12，移走後變死 import）。

4c. `__init__` 中，在 `self._structures_dir = resolved_root / "structures"`（line 86）之後新增一行：
```python
        self._baseline_resolver = BaselineResolver()
```

4d. 把 `resolve_baseline` 整個方法 body（line 154–182）替換為委派（簽名與 docstring 摘要保留、刪掉原 cascade 與 `_load_all_snapshots` 取得後直接傳入）：
```python
    def resolve_baseline(self, reference: str) -> VersionSnapshot:
        """Resolve a baseline reference to a snapshot (all 5 grammars).

        Delegates to BaselineResolver; loads snapshots here so the resolver
        stays pure (I/O lives at the store boundary). Raises
        SnapshotNotFoundError if nothing matches.
        """
        return self._baseline_resolver.resolve(reference, self._load_all_snapshots())
```

4e. **刪除** snapshot_store.py 中已搬走的 4 個方法：`_resolve_by_date`（504–532）、`_resolve_by_git_ref`（534–555）、`_resolve_by_label`（557–564）、`_build_available_list`（566–582）。

- [ ] **Step 5: 跑 resolver 測試 + snapshot_store 相關測試**

Run：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_baseline_resolver.py tests/unit/core/diff/ -q
```
Expected: **全 PASS**（9 個 resolver + 既有 diff 測試）。若 `import re` 殘留致 lint/未使用，確認已刪。

- [ ] **Step 6: 跑全套件，確認零回歸**

Run：
```
PYTHONUTF8=1 python -m pytest -q
```
Expected: 全 PASS（基準＝當下 main，無新 fail）。此時消費者仍有 get_snapshot 後援（冗餘但無害），故全綠。

- [ ] **Step 7: 記下改動面基準，然後 Commit**

先記「動工前」HEAD（供 Task 3 改動面驗收）：
```
git rev-parse HEAD
```
把輸出 SHA 記為 `BASELINE_SHA`（本計畫第一個程式變更之前的 commit）。然後（從 worktree 根目錄）：
```
git add the_door/src/the_door/core/diff/baseline_resolver.py the_door/src/the_door/core/diff/snapshot_store.py the_door/tests/unit/core/diff/test_baseline_resolver.py
git commit -m "refactor(snapshot): extract BaselineResolver, consolidate 5 reference grammars (version_id)"
```
commit message 末尾加：
```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

---

## Task 2: 消費者收斂 + 測試遷移

**Files:**
- Modify: `the_door/src/the_door/core/ui/api/handlers/diff.py`（`_resolve_snapshot`）
- Modify: `the_door/src/the_door/mcp/tools/snapshot_write_tool.py`（移除 get_snapshot 後援）
- Modify: `the_door/src/the_door/core/pipeline/incremental_pipeline.py`（收窄例外 + 補 import）
- Modify: `the_door/tests/unit/core/ui/api/handlers/test_diff.py`（刪 fallback 測試）
- Modify: `the_door/tests/scenario/test_v105_incremental_flow.py`（更新註解）

- [ ] **Step 1: 收斂 `handlers/diff.py` `_resolve_snapshot`**

把現有（約 line 133–140）：
```python
    def _resolve_snapshot(self, store: SnapshotStore, ref: str):
        try:
            result = store.resolve_baseline(ref)
            if result is not None:
                return result
        except SnapshotNotFoundError:
            pass
        return store.get_snapshot(ref)
```
替換為：
```python
    def _resolve_snapshot(self, store: SnapshotStore, ref: str):
        try:
            return store.resolve_baseline(ref)
        except SnapshotNotFoundError:
            return None
```

- [ ] **Step 2: 移除 `snapshot_write_tool.py` 的 get_snapshot 後援**

刪除這兩行（約 line 176–177）：
```python
        if baseline_snap is None:
            baseline_snap = store.get_snapshot(inherit_from)
```
（保留其上的 `try/except SnapshotNotFoundError: baseline_snap = None` 與其下的 `if baseline_snap is None: rem = Remediation(...)` remediation。）

- [ ] **Step 3: 收窄 `incremental_pipeline.py` 例外 + 補 import**

3a. line 23 的 import 由：
```python
from the_door.models import StructureJSON, VersionSnapshot
```
改為：
```python
from the_door.models import SnapshotNotFoundError, StructureJSON, VersionSnapshot
```

3b. 把 `_resolve_baseline`（約 line 47–56）替換為：
```python
def _resolve_baseline(store: SnapshotStore, baseline_ref: str) -> VersionSnapshot | None:
    """Resolve ``baseline_ref`` (all 5 grammars). None if no snapshot matches.

    The orchestrator turns None into the ``baseline_not_found`` remediation.
    """
    try:
        return store.resolve_baseline(baseline_ref)
    except SnapshotNotFoundError:
        return None
```

- [ ] **Step 4: 刪除過時測試 `test_resolve_falls_back_to_get_snapshot`**

在 `tests/unit/core/ui/api/handlers/test_diff.py` 刪除整個方法（約 line 86–95）：
```python
    def test_resolve_falls_back_to_get_snapshot(self, tmp_path):
        from the_door.models import SnapshotNotFoundError
        h = DiffHandlers(_ctx(tmp_path))
        snap = MagicMock()
        with patch("the_door.core.ui.api.handlers.diff.SnapshotStore") as mock_ss:
            store = mock_ss.return_value
            store.resolve_baseline.side_effect = SnapshotNotFoundError("nope", [])
            store.get_snapshot.return_value = snap
            result = h._resolve_snapshot(store, "v1")
        assert result is snap
```
（它測的消費者層後援已移除；version_id 解析改由 `test_baseline_resolver.py::test_store_resolve_baseline_accepts_version_id` 覆蓋。`test_baseline_not_found_returns_404`/`test_current_not_found_returns_404` **不動**——mock `resolve_baseline` 回 None，新 adapter 對 None 回 None → 404。）

- [ ] **Step 5: 更新 scenario stale 註解**

在 `tests/scenario/test_v105_incremental_flow.py` 把（約 line 135）：
```
    the O2 resolve_baseline → get_snapshot fallback). Baseline uses the
```
改為：
```
    the O2 unified BaselineResolver via the version_id grammar). Baseline uses the
```
（僅註解，斷言不動。）

- [ ] **Step 6: 跑安全網 + 全套件**

先單獨跑 §4.4 點名的 snapshot_write 安全網（證 (b) 收斂正確）：
```
PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_write_inherit.py tests/integration/test_mcp_flow_guard.py tests/contract/test_flow_guard_contract.py -q
```
Expected: 全 PASS（這些傳 `inherit_from=<version_id>`，現靠 resolver 的 version_id 分支解）。

再跑全套件：
```
PYTHONUTF8=1 python -m pytest -q
```
Expected: 全 PASS、零回歸（含改後的 test_diff.py、scenario）。
**⚠️ 若有非預期紅**：停下回報 BLOCKED，附失敗測試與錯誤；**不得**為過關把後援加回或改 resolver 行為序。

- [ ] **Step 7: Commit**

```
git add the_door/src/the_door/core/ui/api/handlers/diff.py the_door/src/the_door/mcp/tools/snapshot_write_tool.py the_door/src/the_door/core/pipeline/incremental_pipeline.py the_door/tests/unit/core/ui/api/handlers/test_diff.py the_door/tests/scenario/test_v105_incremental_flow.py
git commit -m "refactor(snapshot): collapse duplicated get_snapshot stitching into BaselineResolver"
```
末尾加：
```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

---

## Task 3: 收尾 — 覆蓋/改動面驗收 + 標 spec 已實作

**Files:**
- Modify: `docs/superpowers/specs/2026-06-03-baseline-resolver-extraction-design.md`（標頭狀態）

- [ ] **Step 1: 覆蓋驗收**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest --cov=the_door.core.diff.baseline_resolver --cov-report=term-missing tests/unit/core/diff/test_baseline_resolver.py tests/
```
Expected: 全 PASS；`baseline_resolver.py` 由 resolver 單元測涵蓋（5 文法 + 序 + 失敗）。記下數字。

- [ ] **Step 2: 確認改動面**

Run（cwd = worktree root；`BASELINE_SHA` = Task 1 Step 7 記下的 SHA。若無記錄，此計畫為線性 2 程式 commit，此刻 HEAD=Task 2 commit，則 `BASELINE_SHA` 即 `HEAD~2`）：
```
git diff --stat <BASELINE_SHA>..HEAD
```
Expected：僅 `core/diff/baseline_resolver.py`（新）、`core/diff/snapshot_store.py`、`core/ui/api/handlers/diff.py`、`mcp/tools/snapshot_write_tool.py`、`core/pipeline/incremental_pipeline.py`、`tests/unit/core/diff/test_baseline_resolver.py`（新）、`tests/unit/core/ui/api/handlers/test_diff.py`、`tests/scenario/test_v105_incremental_flow.py`。**不得有其他檔被改**（讀取路徑、`VersionSnapshot` 模型、`core/datamodel/` 皆未動）。若有他檔變更 → 回報。

- [ ] **Step 3: 標記 spec 已實作**

編輯 `docs/superpowers/specs/2026-06-03-baseline-resolver-extraction-design.md` 標頭，把：
```
> **日期**：2026-06-03　**狀態**：設計核准、待寫 plan
```
改為：
```
> **日期**：2026-06-03　**狀態**：已實作（plan: docs/superpowers/plans/2026-06-03-baseline-resolver-extraction.md）
```

- [ ] **Step 4: Commit**

`docs/` 在**外層** repo root。從 worktree 根目錄（`git rev-parse --show-toplevel` 輸出）執行：
```
git add docs/superpowers/specs/2026-06-03-baseline-resolver-extraction-design.md
git commit -m "docs: mark baseline resolver extraction implemented"
```
末尾加：
```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

- [ ] **Step 5: 收尾回報**

回報：`BaselineResolver` 抽出為純 class（零 I/O、5 文法收斂含 version_id）；`SnapshotStore.resolve_baseline` 委派薄殼、公開契約逐字不變、store 4 私有方法已刪、`import re` 已刪；3 消費者去除冗餘 get_snapshot 後援、4 消費者自動支援 UUID；過時測試已刪、scenario 註解已更；resolver 單元 9 測 + store 整合 1 測全綠；全套件零回歸；改動面僅 spec 列檔。等使用者決定 merge（本地 merge、不主動 push）。

---

## Self-Review（已執行）

- **Spec coverage**：§4.1 resolver→Task1 Step3；§4.2 store 委派+刪私有→Task1 Step4；§4.3(a)(b)(c) 消費者→Task2 Step1-3；§4.3(d)(e) 不改碼者→無動作（驗收於 Task2 Step6/Task3 Step2）；§4.4 測試遷移→Task2 Step4-5 + 安全網 Step6；§6 測試→Task1 Step1 + Task3 Step1；§7 陷阱（version_id 序/逐字搬/單一實例/刪 re）→Task1 Step3-4 護欄。全覆蓋。
- **Placeholder scan**：無 TBD；所有 step 有完整碼/指令/預期輸出。改動面基準用記錄式 `BASELINE_SHA`（後備 `HEAD~2`）、docs commit「從 worktree 根目錄執行」——皆可機械解析。
- **Type/簽名一致**：`BaselineResolver().resolve(reference, snapshots)`、`resolve_baseline(self, reference: str) -> VersionSnapshot`、`_resolve_by_version_id(self, reference, snapshots) -> VersionSnapshot | None`、`SnapshotNotFoundError(reference, available)`、`SnapshotStore(tmp_path, store_root=tmp_path)`、`create_snapshot(l1_snapshot=, feature_relations=, analyzed_files=, trigger=)`——跨 task 一致，與 spec §4 + 真實碼一致。
- **順序鐵則**：version_id 分支（Task1）先於消費者後援移除（Task2），滿足 spec §4.4。
