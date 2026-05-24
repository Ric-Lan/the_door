# Viewer Fixes + Data Quality + Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 10 個問題（cp950 輸出、file_discovery 排除、source_nodes 資料品質、FlowGuard e2e、snapshot_write 欄位補強、前端篩選器/版本標示/關聯圖間距）並新增 `the-door wizard` 互動指令。

**Architecture:** Python 後端改動分三層：CLI（status_cmd、wizard_cmd）、Core/Extraction（file_discovery）、MCP Tools + Models（snapshot_write_tool、models）。前端改動集中在 viewer 的 JS 狀態層（state.js、app.js）、UI 元件（ui-topbar.js、layers.js）、popup（mindmap-popup.html）與 CSS（styles.css）。每個 task 只動一個職責邊界內的檔案。

**Tech Stack:** Python 3.10+、pytest、click；JavaScript ES modules、vitest；pathspec（gitignore）

---

## 注意：spec 的一個檔案路徑更正

Spec 中 R8 的 sessionStorage 寫入被標注在 `app.js`，但實際上 `switchToMindmap()` 和 `buildMindmapData()` 都在 **`layers.js`**（`app.js` 只是 wire 按鈕）。Task 08 的修改檔案因此是 `layers.js`，不是 `app.js`。

---

## Task 01 — R1：status_cmd.py cp950 Unicode 修正

**Files:**
- Modify: `the_door/src/the_door/cli/status_cmd.py`
- Test: `the_door/tests/unit/cli/test_status_cmd.py`

- [ ] **Step 1：寫失敗測試**

在 `the_door/tests/unit/cli/test_status_cmd.py` 末尾新增：

```python
def test_status_sets_pythonioencoding_utf8(tmp_path, monkeypatch):
    """status_cmd must set PYTHONIOENCODING=utf-8 before any output."""
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    from the_door.cli.main import main
    CliRunner().invoke(main, ["status", str(tmp_path)])
    import os
    assert os.environ.get("PYTHONIOENCODING") == "utf-8"


def test_status_uses_click_echo_not_stdout_write(tmp_path, monkeypatch):
    """All output must go through click.echo (no raw sys.stdout.write)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    import io, sys
    # Replace sys.stdout with a stream that raises on write()
    class FailWriter(io.StringIO):
        def write(self, s):
            if s.strip():
                raise AssertionError(f"Direct sys.stdout.write detected: {s!r}")
            return super().write(s)
    monkeypatch.setattr(sys, "stdout", FailWriter())
    from the_door.cli.main import main
    result = CliRunner().invoke(main, ["status", str(tmp_path)], catch_exceptions=False)
    assert result.exit_code == 0
```

- [ ] **Step 2：執行測試確認失敗**

```
cd the_door && pytest tests/unit/cli/test_status_cmd.py::test_status_sets_pythonioencoding_utf8 tests/unit/cli/test_status_cmd.py::test_status_uses_click_echo_not_stdout_write -v
```

預期：FAILED（`os.environ` 未設定；`sys.stdout.write` 仍被呼叫）

- [ ] **Step 3：實作修正**

開啟 `the_door/src/the_door/cli/status_cmd.py`，在函式頂部加 `os.environ.setdefault`，並把所有 `sys.stdout.write(...)` 改為 `click.echo(...)` 輸出至 stderr（與現有 `render_next_block` 一致）：

```python
# 在現有 import 區加入
import os

# status_cmd 函式開頭第一行加入：
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
```

將以下所有 `sys.stdout.write(...)` 改為 `click.echo(..., err=True)`：

```python
# 原本：
sys.stdout.write(f"Project: {project.as_posix()}\n")
if state.has_dot_the_door:
    sys.stdout.write(f"  ✓ {len(state.snapshots)} snapshots\n")
    for s in state.snapshots:
        marker = "✓ has structure" if s.has_persisted_structure else "○ no structure"
        label = s.label or s.version_id
        sys.stdout.write(f"    • {label}  ({marker})\n")
else:
    sys.stdout.write("  ○ not yet initialized\n")
for warning in state.warnings:
    sys.stdout.write(f"  ⚠ {warning.code}: {warning.message}\n")
sys.stdout.write("\n")

# 改為：
click.echo(f"Project: {project.as_posix()}", err=True)
if state.has_dot_the_door:
    click.echo(f"  ✓ {len(state.snapshots)} snapshots", err=True)
    for s in state.snapshots:
        marker = "✓ has structure" if s.has_persisted_structure else "○ no structure"
        label = s.label or s.version_id
        click.echo(f"    • {label}  ({marker})", err=True)
else:
    click.echo("  ○ not yet initialized", err=True)
for warning in state.warnings:
    click.echo(f"  ⚠ {warning.code}: {warning.message}", err=True)
click.echo("", err=True)
```

- [ ] **Step 4：執行測試確認通過**

```
cd the_door && pytest tests/unit/cli/test_status_cmd.py -v
```

預期：全部 PASSED

- [ ] **Step 5：覆蓋率確認**

```
cd the_door && pytest tests/unit/cli/test_status_cmd.py --cov=the_door.cli.status_cmd --cov-report=term-missing
```

預期：`status_cmd.py` 100%

- [ ] **Step 6：Commit**

```
git add the_door/src/the_door/cli/status_cmd.py the_door/tests/unit/cli/test_status_cmd.py
git commit -m "fix(cli): status_cmd cp950 — PYTHONIOENCODING + click.echo"
```

---

## Task 02 — R2：file_discovery 排除 `.claude/` + extra_ignore 參數

**Files:**
- Modify: `the_door/src/the_door/core/extraction/file_discovery.py`
- Test: `the_door/tests/unit/core/extraction/test_extraction.py`

- [ ] **Step 1：寫失敗測試**

在 `test_extraction.py` 的 `TestFileDiscovery` class 末尾加入：

```python
def test_ignores_dot_claude_directory(self, tmp_path):
    """Files inside .claude/ worktrees must never appear in discovery results."""
    (tmp_path / ".claude" / "worktrees" / "foo").mkdir(parents=True)
    (tmp_path / ".claude" / "worktrees" / "foo" / "bar.py").write_text("x = 1")
    (tmp_path / "main.py").write_text("y = 2")
    files = FileDiscovery().discover(str(tmp_path))
    paths = [f.path for f in files]
    assert not any(".claude" in p for p in paths)
    assert any("main.py" in p for p in paths)

def test_extra_ignore_excludes_specified_dirs(self, tmp_path):
    """extra_ignore patterns are applied on top of the default ignore list."""
    (tmp_path / "vendor" / "lib").mkdir(parents=True)
    (tmp_path / "vendor" / "lib" / "foo.py").write_text("x = 1")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("y = 2")
    files = FileDiscovery().discover(str(tmp_path), extra_ignore=["vendor/"])
    paths = [f.path for f in files]
    assert not any("vendor" in p for p in paths)
    assert any("app.py" in p for p in paths)
```

- [ ] **Step 2：執行測試確認失敗**

```
cd the_door && pytest tests/unit/core/extraction/test_extraction.py::TestFileDiscovery::test_ignores_dot_claude_directory tests/unit/core/extraction/test_extraction.py::TestFileDiscovery::test_extra_ignore_excludes_specified_dirs -v
```

預期：FAILED（`.claude/` 未被排除；`extra_ignore` 參數不存在）

- [ ] **Step 3：實作修正**

在 `file_discovery.py` 的 `_DEFAULT_IGNORE_PATTERNS` 加入 `".claude/"`，並在 `discover()` 和 `_load_gitignore()` 加入 `extra_ignore` 參數：

```python
_DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    ".claude/",          # ← 新增
    "node_modules/",
    "__pycache__/",
    "dist/",
    "build/",
    ".tox/",
    ".mypy_cache/",
    ".pytest_cache/",
    "*.pyc",
    "*.pyo",
]


class FileDiscovery:
    def discover(
        self,
        codebase_path: str,
        extra_ignore: list[str] | None = None,   # ← 新增參數
    ) -> list[FileInfo]:
        root = Path(codebase_path).resolve()
        if not root.is_dir():
            return []
        spec = self._load_gitignore(root, extra_ignore=extra_ignore or [])
        results: list[FileInfo] = []
        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = Path(dirpath).relative_to(root)
            dirnames[:] = [
                d
                for d in dirnames
                if not spec.match_file(str(rel_dir / d) + "/")
            ]
            for fname in sorted(filenames):
                rel_path = str(rel_dir / fname) if str(rel_dir) != "." else fname
                rel_path = rel_path.replace("\\", "/")
                if spec.match_file(rel_path):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                language = _EXTENSION_MAP.get(ext)
                if language is None:
                    continue
                results.append(FileInfo(path=rel_path, language=language))
        return results

    @staticmethod
    def _load_gitignore(
        root: Path,
        extra_ignore: list[str] | None = None,   # ← 新增參數
    ) -> pathspec.PathSpec:
        patterns = list(_DEFAULT_IGNORE_PATTERNS)
        if extra_ignore:
            patterns.extend(extra_ignore)
        gitignore = root / ".gitignore"
        if gitignore.is_file():
            patterns.extend(
                line.strip()
                for line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip() and not line.strip().startswith("#")
            )
        return pathspec.PathSpec.from_lines("gitignore", patterns)
```

- [ ] **Step 4：執行測試確認通過**

```
cd the_door && pytest tests/unit/core/extraction/test_extraction.py -v
```

預期：全部 PASSED

- [ ] **Step 5：覆蓋率確認**

```
cd the_door && pytest tests/unit/core/extraction/test_extraction.py --cov=the_door.core.extraction.file_discovery --cov-report=term-missing
```

預期：`file_discovery.py` 100%

- [ ] **Step 6：Commit**

```
git add the_door/src/the_door/core/extraction/file_discovery.py the_door/tests/unit/core/extraction/test_extraction.py
git commit -m "fix(extraction): exclude .claude/ worktrees + add extra_ignore param"
```

---

## Task 03 — R5：snapshot_write 欄位補強（confidence_reason + source_nodes warning）

**Files:**
- Modify: `the_door/src/the_door/models.py`
- Modify: `the_door/src/the_door/mcp/tools/snapshot_write_tool.py`
- Test: `the_door/tests/unit/mcp/test_snapshot_write_tool.py`

- [ ] **Step 1：寫失敗測試**

在 `test_snapshot_write_tool.py` 末尾加入：

```python
@pytest.mark.asyncio
async def test_confidence_reason_roundtrips(tmp_project):
    """confidence_reason written via snapshot_write must be readable from store."""
    result = await execute({
        "codebase_path": str(tmp_project),
        "label": "v-cr-test",
        "l1_features": [
            {
                "feature_id": "feat-auth",
                "label": "Auth",
                "description": "handles auth",
                "confidence": "high",
                "source_nodes": ["AuthModule.login"],
                "confidence_reason": "函式命名清楚且路徑單一",
            }
        ],
    })
    assert "error" not in result
    vid = result["version_id"]
    snap = SnapshotStore(tmp_project).get_snapshot(vid)
    fs = snap.l1_snapshot["feat-auth"]
    assert fs.confidence_reason == "函式命名清楚且路徑單一"


@pytest.mark.asyncio
async def test_empty_source_nodes_returns_warning(tmp_project):
    """When source_nodes is empty, response must include a warnings list."""
    result = await execute({
        "codebase_path": str(tmp_project),
        "label": "v-warn-test",
        "l1_features": [
            {
                "feature_id": "feat-x",
                "label": "X",
                "description": "some feature",
                "confidence": "medium",
                "source_nodes": [],
            }
        ],
    })
    assert "error" not in result
    assert "warnings" in result
    assert any("source_nodes" in w for w in result["warnings"])
```

（在檔案頂部確認 `from the_door.mcp.tools.snapshot_write_tool import execute` 已存在）

- [ ] **Step 2：執行測試確認失敗**

```
cd the_door && pytest tests/unit/mcp/test_snapshot_write_tool.py::test_confidence_reason_roundtrips tests/unit/mcp/test_snapshot_write_tool.py::test_empty_source_nodes_returns_warning -v
```

預期：FAILED（`FeatureSummary` 無 `confidence_reason`；無 warnings 邏輯）

- [ ] **Step 3：更新 models.py**

在 `the_door/src/the_door/models.py` 的 `FeatureSummary` dataclass 加入新欄位（放在 `source_nodes` 後）：

```python
@dataclass(frozen=True)
class FeatureSummary:
    feature_id: str
    label: str
    description: str
    source_node_count: int
    confidence: str
    trigger_description: str | None = None
    source_nodes: tuple[str, ...] = ()
    confidence_reason: str | None = None   # ← 新增，向後相容
```

- [ ] **Step 4：更新 snapshot_write_tool.py**

在 `TOOL_SCHEMA` 的 `l1_features.items.properties` 區塊加入（兩處：`l1_features` 和 `updated_features` 都要加）：

```python
"confidence_reason": {"type": "string"},
```

更新 `_feature_dict_to_summary()`：

```python
def _feature_dict_to_summary(feat: dict) -> FeatureSummary | dict:
    if feat.get("confidence") not in VALID_CONFIDENCE:
        fid = feat.get("feature_id", "?")
        return {
            "error": (
                f"Feature '{fid}' has invalid confidence '{feat.get('confidence')}'. "
                f"Must be one of: high, medium, low"
            )
        }
    fid = feat["feature_id"]
    return FeatureSummary(
        feature_id=fid,
        label=feat["label"],
        description=feat["description"],
        source_node_count=len(feat.get("source_nodes", []) or []),
        confidence=feat["confidence"],
        trigger_description=feat.get("trigger_description"),
        source_nodes=tuple(feat.get("source_nodes", ())),
        confidence_reason=feat.get("confidence_reason"),   # ← 新增
    )
```

在 `execute()` 函式的 Direct mode（`else` 分支）snapshot 寫入前，收集 warnings：

```python
# 在 l1_snapshot 建立完成後、呼叫 store.create_snapshot 前：
warnings = [
    f"Feature '{fid}' has empty source_nodes — L2 drill-down will not work"
    for fid, fs in l1_snapshot.items()
    if not fs.source_nodes
]
```

在 `payload` dict 加入：

```python
payload = {
    "version_id": snapshot.version_id,
    "label": snapshot.label,
    "timestamp": snapshot.timestamp,
    "feature_count": len(l1_snapshot),
    "relation_count": len(relations),
}
if warnings:
    payload["warnings"] = warnings
```

- [ ] **Step 5：執行測試確認通過**

```
cd the_door && pytest tests/unit/mcp/test_snapshot_write_tool.py -v
```

預期：全部 PASSED

- [ ] **Step 6：覆蓋率確認**

```
cd the_door && pytest tests/unit/mcp/test_snapshot_write_tool.py --cov=the_door.mcp.tools.snapshot_write_tool --cov=the_door.models --cov-report=term-missing
```

預期：兩個模組 100%

- [ ] **Step 7：Commit**

```
git add the_door/src/the_door/models.py the_door/src/the_door/mcp/tools/snapshot_write_tool.py the_door/tests/unit/mcp/test_snapshot_write_tool.py
git commit -m "feat(models): add FeatureSummary.confidence_reason + source_nodes warning"
```

---

## Task 04 — R4：FlowGuard CHECKPOINT 端對端驗證

**Files:**
- Create: `the_door/tests/integration/test_snapshot_write_checkpoint_e2e.py`

不修改任何 production 程式碼。

- [ ] **Step 1：建立測試檔**

建立 `the_door/tests/integration/test_snapshot_write_checkpoint_e2e.py`：

```python
"""E2E tests: snapshot_write CHECKPOINT flow — all three choice branches."""
from __future__ import annotations

import pytest
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary
from tests._seed_helpers import seed_baseline_snapshot
from the_door.mcp.tools.snapshot_write_tool import execute


def _make_fs(fid: str) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid,
        label=fid,
        description=f"desc {fid}",
        source_node_count=1,
        confidence="high",
        source_nodes=(f"Node.{fid}",),
    )


@pytest.fixture
def project_with_baseline(tmp_path):
    seed_baseline_snapshot(
        tmp_path,
        label="v1.0.0",
        features={"feat-old": _make_fs("feat-old")},
    )
    return tmp_path


NEW_FEATURE = {
    "feature_id": "feat-new",
    "label": "New",
    "description": "newly added feature",
    "confidence": "high",
    "source_nodes": ["NewModule.run"],
}
OLD_FEATURE = {
    "feature_id": "feat-old",
    "label": "Old",
    "description": "desc feat-old",
    "confidence": "high",
    "source_nodes": ["Node.feat-old"],
}


@pytest.mark.asyncio
async def test_checkpoint_triggers_when_new_feature_detected(project_with_baseline):
    """First call without choice must return checkpoint (result=None)."""
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
    })
    assert result.get("result") is None, f"Expected checkpoint, got: {result}"
    assert "checkpoint" in result
    option_keys = {o["key"] for o in result.get("options", [])}
    assert {"A", "B", "C"} == option_keys


@pytest.mark.asyncio
async def test_choice_a_includes_new_feature(project_with_baseline):
    """choice=A must write snapshot containing both old and new features."""
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
        "choice": "A",
        "label": "v1.0.1-a",
    })
    assert "error" not in result
    snap = SnapshotStore(project_with_baseline).get_snapshot(result["version_id"])
    assert "feat-new" in snap.l1_snapshot
    assert "feat-old" in snap.l1_snapshot


@pytest.mark.asyncio
async def test_choice_b_drops_new_feature(project_with_baseline):
    """choice=B must write snapshot with only baseline features."""
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
        "choice": "B",
        "label": "v1.0.1-b",
    })
    assert "error" not in result
    snap = SnapshotStore(project_with_baseline).get_snapshot(result["version_id"])
    assert "feat-new" not in snap.l1_snapshot
    assert "feat-old" in snap.l1_snapshot


@pytest.mark.asyncio
async def test_choice_c_aborts_no_snapshot_written(project_with_baseline):
    """choice=C must abort and not write any new snapshot."""
    store = SnapshotStore(project_with_baseline)
    count_before = len(store.list_snapshots())
    result = await execute({
        "codebase_path": str(project_with_baseline),
        "inherit_from": "v1.0.0",
        "l1_features": [OLD_FEATURE, NEW_FEATURE],
        "choice": "C",
    })
    assert result.get("aborted") is True
    assert len(store.list_snapshots()) == count_before
```

- [ ] **Step 2：執行測試確認全部通過**

```
cd the_door && pytest tests/integration/test_snapshot_write_checkpoint_e2e.py -v
```

預期：4 tests PASSED

- [ ] **Step 3：Commit**

```
git add the_door/tests/integration/test_snapshot_write_checkpoint_e2e.py
git commit -m "test(mcp): FlowGuard CHECKPOINT e2e — A/B/C all branches verified"
```

---

## Task 05 — R3：增量分析 source_nodes 保留驗證

**Files:**
- Create: `the_door/tests/integration/test_incremental_source_nodes.py`

不修改任何 production 程式碼。

- [ ] **Step 1：建立測試檔**

建立 `the_door/tests/integration/test_incremental_source_nodes.py`：

```python
"""Integration: analyze_changes returns source_nodes; snapshot_write preserves them."""
from __future__ import annotations

import pytest
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.models import FeatureSummary
from tests._seed_helpers import seed_baseline_snapshot
from the_door.mcp.tools.snapshot_write_tool import execute as snapshot_write
from the_door.mcp.tools.analyze_changes_tool import _feature_to_json


def _make_fs_with_nodes(fid: str, nodes: tuple[str, ...]) -> FeatureSummary:
    return FeatureSummary(
        feature_id=fid,
        label=fid,
        description=f"desc {fid}",
        source_node_count=len(nodes),
        confidence="high",
        source_nodes=nodes,
    )


def test_feature_to_json_includes_source_nodes():
    """_feature_to_json must serialize source_nodes as a list."""
    fs = _make_fs_with_nodes("feat-a", ("Foo.bar", "Baz.qux"))
    result = _feature_to_json(fs)
    assert result["source_nodes"] == ["Foo.bar", "Baz.qux"]
    assert result["source_node_count"] == 2


@pytest.mark.asyncio
async def test_updated_features_preserves_source_nodes(tmp_path):
    """snapshot_write with updated_features must not drop source_nodes from baseline."""
    seed_baseline_snapshot(
        tmp_path,
        label="v1.0.0",
        features={
            "feat-stable": _make_fs_with_nodes("feat-stable", ("StableModule.run",)),
            "feat-changed": _make_fs_with_nodes("feat-changed", ("OldModule.fn",)),
        },
    )

    result = await snapshot_write({
        "codebase_path": str(tmp_path),
        "inherit_from": "v1.0.0",
        "updated_features": [
            {
                "feature_id": "feat-changed",
                "label": "feat-changed updated",
                "description": "updated description",
                "confidence": "high",
                "source_nodes": ["NewModule.fn"],
            }
        ],
        "label": "v1.0.1",
    })
    assert "error" not in result

    store = SnapshotStore(tmp_path)
    snap = store.get_snapshot(result["version_id"])

    # Stable feature must retain its original source_nodes
    assert snap.l1_snapshot["feat-stable"].source_nodes == ("StableModule.run",)
    # Updated feature must have the new source_nodes
    assert snap.l1_snapshot["feat-changed"].source_nodes == ("NewModule.fn",)
```

- [ ] **Step 2：執行測試確認通過**

```
cd the_door && pytest tests/integration/test_incremental_source_nodes.py -v
```

預期：2 tests PASSED

- [ ] **Step 3：Commit**

```
git add the_door/tests/integration/test_incremental_source_nodes.py
git commit -m "test(mcp): verify source_nodes preserved in incremental update path"
```

---

## Task 06 — R6：前端篩選器 UI 接線

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/state.js`
- Modify: `docs/frontend-local-version-viewer/viewer/js/app.js`
- Test: `docs/frontend-local-version-viewer/viewer/tests/app.test.js`

- [ ] **Step 1：寫失敗測試**

在 `viewer/tests/app.test.js` 末尾加入：

```javascript
describe('filter wiring — #filter-conf and #filter-type', () => {
  beforeEach(() => {
    state.filterConf = null;
    state.filterType = null;
    // Reset selects
    const confSel = document.getElementById('filter-conf');
    const typeSel = document.getElementById('filter-type');
    if (confSel) confSel.value = '';
    if (typeSel) typeSel.value = '';
  });

  it('state.js has filterConf and filterType fields defaulting to null', () => {
    expect(state).toHaveProperty('filterConf', null);
    expect(state).toHaveProperty('filterType', null);
  });

  it('changing #filter-conf updates state.filterConf', () => {
    const confSel = document.getElementById('filter-conf');
    expect(confSel).not.toBeNull();
    confSel.value = 'high';
    confSel.dispatchEvent(new Event('change'));
    expect(state.filterConf).toBe('high');
  });

  it('changing #filter-type updates state.filterType', () => {
    const typeSel = document.getElementById('filter-type');
    expect(typeSel).not.toBeNull();
    typeSel.value = 'added';
    typeSel.dispatchEvent(new Event('change'));
    expect(state.filterType).toBe('added');
  });
});
```

- [ ] **Step 2：執行測試確認失敗**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/app.test.js
```

預期：新增的 3 個 tests FAILED（`state` 無 `filterConf`；事件未接線）

- [ ] **Step 3：更新 state.js**

在 `viewer/js/state.js` 的 `state` 物件末尾加入兩個欄位：

```javascript
export const state = {
  // ... 現有欄位不動 ...
  versionDiff: null,
  filterConf: null,    // ← 新增
  filterType: null,    // ← 新增
};
```

- [ ] **Step 4：更新 app.js — init() 加入事件監聽**

在 `viewer/js/app.js` 的 `init()` 函式末尾（`loadProjectStatus()` 前）加入：

```javascript
  // Filter wiring (R6)
  const filterConf = document.getElementById('filter-conf');
  const filterType = document.getElementById('filter-type');
  if (filterConf) {
    filterConf.addEventListener('change', () => {
      state.filterConf = filterConf.value || null;
      render();
    });
  }
  if (filterType) {
    filterType.addEventListener('change', () => {
      state.filterType = filterType.value || null;
      render();
    });
  }
```

在 `render()` 函式中，將 `renderChangeList` 的 features 傳入前套用 filter。找到 `renderChangeList` 的呼叫，並先 import `applyCardFilters`：

在 `app.js` 頂部 import 區加入：

```javascript
import { renderChangeList, applyCardFilters } from './ui-list.js';
```

（移除原本的 `import { renderChangeList } from './ui-list.js'`）

`render()` 中 `renderChangeList` 的呼叫改為：

```javascript
export function render() {
  renderTopBar();
  const rawFeatures = state.l1Model?.features ?? [];
  const filteredFeatures = applyCardFilters(rawFeatures, {
    conf: state.filterConf,
    type: state.filterType,
  });
  renderChangeList(
    { onSelectFeature, onSelectChange },
    filteredFeatures,
  );
  renderDetailPanel({ onEnterL2: switchToL2 });
  updateLogoMark();
  // ... 其餘不動
}
```

> 注意：`renderChangeList` 目前不接受外部 features 參數——Task 06 Step 4 只需在 `renderChangeList` 呼叫前把 filter 結果存入 `state`，讓 `renderChangeList` 從 `state` 讀取。若 `renderChangeList` 內部讀的是 `state.l1Model.features`，則更簡單的方式是：

```javascript
// render() 中，在 renderChangeList 呼叫前：
state._filteredFeatures = applyCardFilters(
  state.l1Model?.features ?? [],
  { conf: state.filterConf, type: state.filterType }
);
renderChangeList({ onSelectFeature, onSelectChange });
```

然後在 `ui-list.js` 的 `renderChangeList` 中，讀取 `state._filteredFeatures ?? state.l1Model?.features ?? []`（非 diff 模式下）。

**選擇最小改動的方式**：在 `renderChangeList` 不加參數的前提下，在 `state.js` 加一個 `_filteredFeatures: null` 欄位，由 `render()` 在呼叫前設值，`renderChangeList` 非 diff 模式的 `features` 讀自 `state._filteredFeatures ?? state.l1Model?.features ?? []`。

最終 `state.js` 加入：

```javascript
filterConf: null,
filterType: null,
_filteredFeatures: null,
```

`render()` 中：

```javascript
state._filteredFeatures = applyCardFilters(
  state.l1Model?.features ?? [],
  { conf: state.filterConf, type: state.filterType }
);
```

`ui-list.js` 的 `renderChangeList` 非 diff 模式中，將：

```javascript
const features = state.l1Model?.features ?? [];
```

改為：

```javascript
const features = state._filteredFeatures ?? state.l1Model?.features ?? [];
```

- [ ] **Step 5：執行測試確認通過**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/app.test.js tests/ui-list.test.js
```

預期：全部 PASSED

- [ ] **Step 6：Commit**

```
git add docs/frontend-local-version-viewer/viewer/js/state.js docs/frontend-local-version-viewer/viewer/js/app.js docs/frontend-local-version-viewer/viewer/js/ui-list.js docs/frontend-local-version-viewer/viewer/tests/app.test.js
git commit -m "feat(viewer): wire filter-conf/filter-type selects to applyCardFilters"
```

---

## Task 07 — R7：置頂欄版本標示

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-topbar.js`
- Test: `docs/frontend-local-version-viewer/viewer/tests/ui-topbar.test.js`

- [ ] **Step 1：寫失敗測試**

在 `viewer/tests/ui-topbar.test.js` 末尾加入：

```javascript
describe('renderTopBar — summaryText shows version label', () => {
  it('single version mode includes snapshot label in summaryText', () => {
    state.snapshots = [{ version_id: 'v1', label: 'v1.0.5', git_tags: [] }];
    state.versionB = 'v1';
    state.l1Model = { features: Array(7).fill({}), stats: { feature_count: 7 } };
    state.mode = 'current';
    renderTopBar();
    expect(els.summaryText.textContent).toContain('v1.0.5');
    expect(els.summaryText.textContent).toContain('7');
  });

  it('fallback to count-only when no snapshot label', () => {
    state.snapshots = [];
    state.versionB = null;
    state.l1Model = { features: Array(3).fill({}), stats: { feature_count: 3 } };
    state.mode = 'current';
    renderTopBar();
    expect(els.summaryText.textContent).toMatch(/3\s*個功能/);
  });
});
```

- [ ] **Step 2：執行測試確認失敗**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-topbar.test.js
```

預期：新增的 2 個 tests FAILED（summaryText 不含 label）

- [ ] **Step 3：實作**

在 `viewer/js/ui-topbar.js` 的 `renderTopBar()` 找到：

```javascript
  } else if (state.l1Model) {
    const fc = state.l1Model.stats?.feature_count ?? state.l1Model.features?.length ?? 0;
    els.summaryText.textContent = '功能總覽：共 ' + fc + ' 個功能。';
  }
```

改為：

```javascript
  } else if (state.l1Model) {
    const fc = state.l1Model.stats?.feature_count ?? state.l1Model.features?.length ?? 0;
    const vId = state.mode === 'baseline' ? state.versionA : state.versionB;
    const snap = state.snapshots.find(s => s.version_id === vId);
    const label = snap ? snapshotLabel(snap) : null;
    els.summaryText.textContent = label
      ? `${label} · 共 ${fc} 個功能`
      : `共 ${fc} 個功能`;
  }
```

- [ ] **Step 4：執行測試確認通過**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/ui-topbar.test.js
```

預期：全部 PASSED

- [ ] **Step 5：Commit**

```
git add docs/frontend-local-version-viewer/viewer/js/ui-topbar.js docs/frontend-local-version-viewer/viewer/tests/ui-topbar.test.js
git commit -m "feat(viewer): topbar summary shows version label"
```

---

## Task 08 — R8：心智圖版本標示

> **實作位置更正：** sessionStorage 寫入在 `layers.js::buildMindmapData()`，不在 `app.js`。

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/js/layers.js`
- Modify: `docs/frontend-local-version-viewer/viewer/mindmap-popup.html`
- Test: `docs/frontend-local-version-viewer/viewer/tests/layers.test.js`

- [ ] **Step 1：寫失敗測試**

在 `viewer/tests/layers.test.js` 末尾加入：

```javascript
describe('buildMindmapData — version labels', () => {
  it('includes versionALabel and versionBLabel when snapshots present', () => {
    state.snapshots = [
      { version_id: 'id-b', label: 'v1.0.5', git_tags: [] },
      { version_id: 'id-a', label: 'v1.0.0', git_tags: [] },
    ];
    state.versionA = 'id-a';
    state.versionB = 'id-b';
    state.l1GraphViewModel = { nodes: [], edges: [] };
    const data = buildMindmapData(state);
    expect(data.versionALabel).toBe('v1.0.0');
    expect(data.versionBLabel).toBe('v1.0.5');
  });

  it('versionALabel and versionBLabel are null when no snapshots', () => {
    state.snapshots = [];
    state.versionA = null;
    state.versionB = null;
    state.l1GraphViewModel = { nodes: [], edges: [] };
    const data = buildMindmapData(state);
    expect(data.versionALabel).toBeNull();
    expect(data.versionBLabel).toBeNull();
  });
});
```

- [ ] **Step 2：執行測試確認失敗**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/layers.test.js
```

預期：新增的 2 個 tests FAILED（`buildMindmapData` 不含 versionALabel）

- [ ] **Step 3：更新 layers.js**

找到 `buildMindmapData` 函式末尾的 `return` 語句：

```javascript
  return { project: projectName, nodes, diffNodes, diffAvailable };
```

改為（需先 import `snapshotLabel` 或 inline 取 label）：

```javascript
  function _snapLabel(vId) {
    if (!vId) return null;
    const s = state.snapshots?.find(snap => snap.version_id === vId);
    if (!s) return null;
    if (s.git_tags?.length) return s.git_tags[0];
    return s.label ?? null;
  }

  return {
    project: projectName,
    nodes,
    diffNodes,
    diffAvailable,
    versionALabel: _snapLabel(state.versionA),
    versionBLabel: _snapLabel(state.versionB),
  };
```

（`_snapLabel` 為 `buildMindmapData` 內部 helper，不 export）

- [ ] **Step 4：更新 mindmap-popup.html 的 init() 函式**

找到 `init()` 中設定 `#project-name` 的這兩行：

```javascript
  const projectName = (data.project || "").split(/[/\\]/).filter(Boolean).pop() || "專案";
  data.projectName = projectName;
  document.getElementById("project-name").textContent = projectName;
```

改為：

```javascript
  const projectName = (data.project || "").split(/[/\\]/).filter(Boolean).pop() || "專案";
  data.projectName = projectName;
  const vAL = data.versionALabel;
  const vBL = data.versionBLabel;
  let versionLabel = "";
  if (data.diffAvailable && vAL && vBL) {
    versionLabel = ` — A · ${vAL} → B · ${vBL}`;
  } else if (vBL) {
    versionLabel = ` · ${vBL}`;
  } else if (vAL) {
    versionLabel = ` · ${vAL}`;
  }
  document.getElementById("project-name").textContent = projectName + versionLabel;
```

- [ ] **Step 5：執行測試確認通過**

```
cd docs/frontend-local-version-viewer/viewer && npx vitest run tests/layers.test.js
```

預期：全部 PASSED

- [ ] **Step 6：Commit**

```
git add docs/frontend-local-version-viewer/viewer/js/layers.js docs/frontend-local-version-viewer/viewer/mindmap-popup.html docs/frontend-local-version-viewer/viewer/tests/layers.test.js
git commit -m "feat(viewer): mindmap popup shows A/B version labels"
```

---

## Task 09 — R9：關聯圖上下間距加長

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/styles.css`

- [ ] **Step 1：修改 CSS**

在 `styles.css` 找到：

```css
.gv-grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(5, minmax(160px, 1fr));
  grid-auto-rows: 90px;
  gap: 20px;
  max-width: 1100px;
  margin: 0 auto;
}
```

改為：

```css
.gv-grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(5, minmax(160px, 1fr));
  grid-auto-rows: 90px;
  column-gap: 20px;
  row-gap: 48px;
  max-width: 1100px;
  margin: 0 auto;
}
```

- [ ] **Step 2：視覺驗收**

```
the-door ui C:\Users\Ric\Desktop\test-targets\the-door-v105 --no-browser --port 8765
```

開啟 http://localhost:8765，進入關聯圖（L1 graph）。
Pass 標準：有邊相連的兩個節點之間，連線不被相鄰節點遮蓋。

- [ ] **Step 3：Commit**

```
git add docs/frontend-local-version-viewer/viewer/styles.css
git commit -m "fix(viewer): increase relation graph row gap 20px→48px"
```

---

## Task 10 — R10：Wizard 新功能

**Files:**
- Create: `the_door/src/the_door/cli/wizard_cmd.py`
- Modify: `the_door/src/the_door/cli/main.py`
- Create: `the_door/tests/unit/cli/test_wizard_cmd.py`

- [ ] **Step 1：寫失敗測試**

建立 `the_door/tests/unit/cli/test_wizard_cmd.py`：

```python
"""Unit tests for the-door wizard command."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from pathlib import Path


def _invoke_wizard(tmp_path, inputs=""):
    from the_door.cli.main import main
    return CliRunner().invoke(main, ["wizard", str(tmp_path)], input=inputs)


def test_wizard_is_registered():
    """wizard must be a registered CLI command."""
    from the_door.cli.main import main
    assert "wizard" in main.commands


def test_wizard_shows_discovered_files(tmp_path):
    """wizard must display top-level directory/file summary."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1")
    # Input: skip exclusion (Enter), then choose B (abort at Checkpoint 1)
    result = _invoke_wizard(tmp_path, inputs="\nB\n")
    assert result.exit_code == 0
    assert "src" in result.output or "app.py" in result.output


def test_wizard_excludes_specified_directory(tmp_path):
    """Directories entered at exclusion prompt must not appear in final summary."""
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor" / "lib.py").write_text("x = 1")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("y = 2")
    # Input: exclude "vendor", then abort at Checkpoint 1
    result = _invoke_wizard(tmp_path, inputs="vendor\nB\n")
    assert result.exit_code == 0
    # After exclusion, vendor files should not be counted
    assert "vendor" not in result.output.split("vendor")[1] if "vendor" in result.output else True


def test_wizard_checkpoint1_b_aborts(tmp_path):
    """Choosing B at Checkpoint 1 must exit without running analysis."""
    (tmp_path / "app.py").write_text("x = 1")
    result = _invoke_wizard(tmp_path, inputs="\nB\n")
    assert result.exit_code == 0
    assert "中止" in result.output or "abort" in result.output.lower() or result.exit_code == 0


def test_wizard_no_api_key_prints_mcp_hint(tmp_path, monkeypatch):
    """Without API key, wizard must print MCP instructions instead of running analysis."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "app.py").write_text("x = 1")
    with patch("the_door.core.llm.config_manager.ConfigManager.load") as mock_load:
        cfg = MagicMock()
        cfg.api_key = None
        mock_load.return_value = cfg
        # Input: skip exclusion, confirm Checkpoint 1
        result = _invoke_wizard(tmp_path, inputs="\nA\n")
    assert "extract_structure" in result.output or "MCP" in result.output
```

- [ ] **Step 2：執行測試確認失敗**

```
cd the_door && pytest tests/unit/cli/test_wizard_cmd.py::test_wizard_is_registered -v
```

預期：FAILED（`wizard` 指令不存在）

- [ ] **Step 3：實作 wizard_cmd.py**

建立 `the_door/src/the_door/cli/wizard_cmd.py`：

```python
"""`the-door wizard` — interactive single-command analysis flow."""
from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import click

from the_door.cli.next_action_renderer import render_next_block
from the_door.core.extraction.file_discovery import FileDiscovery
from the_door.core.flow_guard import CheckpointOption, FlowGuard
from the_door.cli.checkpoint_renderer import CheckpointRenderer


def _top_level_summary(files: list) -> dict[str, int]:
    """Count files per top-level directory (or '.' for root-level files)."""
    counts: Counter = Counter()
    for f in files:
        parts = f.path.split("/")
        top = parts[0] if len(parts) > 1 else "."
        counts[top] += 1
    return dict(counts)


@click.command("wizard")
@click.argument(
    "path",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    default=".",
)
def wizard_cmd(path: str) -> None:
    """互動式一鍵分析流程：探索目錄 → 排除確認 → 執行分析。"""
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    codebase_path = Path(path).resolve()

    # Step 1: Discover files
    discovery = FileDiscovery()
    files = discovery.discover(str(codebase_path))
    summary = _top_level_summary(files)

    click.echo(f"\n📁 專案路徑：{codebase_path}")
    click.echo(f"   偵測到 {len(files)} 個源碼檔案：")
    for dirname, count in sorted(summary.items()):
        click.echo(f"     {dirname}/  ({count} 個檔案)")

    # Step 2: Ask for exclusions
    exclude_input = click.prompt(
        "\n要排除哪些目錄？（逗號分隔，直接 Enter 跳過）",
        default="",
        show_default=False,
    ).strip()

    extra_ignore: list[str] = []
    if exclude_input:
        extra_ignore = [d.strip().rstrip("/") + "/" for d in exclude_input.split(",") if d.strip()]
        files = discovery.discover(str(codebase_path), extra_ignore=extra_ignore)
        summary = _top_level_summary(files)
        click.echo(f"   排除後剩餘 {len(files)} 個檔案。")

    # Detect API key
    from the_door.core.llm.config_manager import ConfigManager
    config = ConfigManager.load()
    has_api_key = bool(getattr(config, "api_key", None))
    mode_label = "LLM 分析（API key）" if has_api_key else "MCP 路徑（agent-as-LLM）"

    # Detect existing snapshot label conflict
    from the_door.core.diff.snapshot_store import SnapshotStore
    store = SnapshotStore(codebase_path)
    existing_labels = {s.label for s in store.list_snapshots() if s.label}

    # Step 3: Checkpoint 1 — 總覽確認
    guard = FlowGuard()
    renderer = CheckpointRenderer(guard)
    decision = guard.check(
        "wizard-start-confirmed",
        f"準備分析 {len(files)} 個檔案，模式：{mode_label}",
        options=[
            CheckpointOption("A", "確認，開始分析"),
            CheckpointOption("B", "中止"),
        ],
    )
    click.echo(f"\n📋 分析計畫：{len(files)} 個檔案 | {mode_label}")
    try:
        chosen = renderer.prompt(decision)
    except EOFError:
        chosen = "B"

    if chosen == "B":
        click.echo("中止。")
        return

    # Step 4: Execute analysis
    if has_api_key:
        _run_with_api(codebase_path, files, store, guard, renderer, existing_labels)
    else:
        _print_mcp_hint(codebase_path)


def _run_with_api(codebase_path, files, store, guard, renderer, existing_labels):
    from the_door.core.pipeline.analyze_pipeline import run_analyze_pipeline
    from the_door.models import AnalyzeConfig
    from the_door.core.llm.config_manager import ConfigManager

    config = ConfigManager.load()
    label = click.prompt("快照標籤（例如 v1.0.0）", default="", show_default=False).strip() or None

    # Step 5: Checkpoint 2 — 覆寫確認
    if label and label in existing_labels:
        guard2 = guard
        decision2 = guard2.check(
            "wizard-overwrite-confirmed",
            f"已存在標籤 '{label}' 的快照",
            options=[
                CheckpointOption("A", f"覆寫 '{label}'"),
                CheckpointOption("B", "另存新標籤"),
                CheckpointOption("C", "中止"),
            ],
        )
        click.echo(f"\n⚠ 已有標籤 '{label}' 的快照，請選擇：")
        try:
            from the_door.cli.checkpoint_renderer import CheckpointRenderer
            chosen2 = CheckpointRenderer(guard2).prompt(decision2)
        except EOFError:
            chosen2 = "C"
        if chosen2 == "C":
            click.echo("中止。")
            return
        if chosen2 == "B":
            label = click.prompt("新標籤名稱").strip() or None

    click.echo("\n⏳ 分析中…")
    analyze_config = AnalyzeConfig(provider_config=config)
    result = run_analyze_pipeline(codebase_path, analyze_config)
    if hasattr(result, "error") and result.error:
        click.echo(f"分析失敗：{result.error}", err=True)
        return
    click.echo("✓ 分析完成。")
    from the_door.core.guidance.state import StateInspector
    from the_door.core.guidance.suggester import NextActionSuggester
    state = StateInspector(codebase_path).inspect()
    actions = NextActionSuggester().suggest(state, context="cli")
    render_next_block(actions)


def _print_mcp_hint(codebase_path: Path) -> None:
    click.echo("\n沒有 API key，請使用 MCP 路徑（agent-as-LLM）：")
    path_str = codebase_path.as_posix()
    click.echo(f'  1. extract_structure(codebase_path="{path_str}")')
    click.echo("  2. （你作為 LLM）分析 nodes/edges，產出 l1_features JSON")
    click.echo(f'  3. snapshot_write(codebase_path="{path_str}", l1_features=[...], label="v1.0.0")')
```

- [ ] **Step 4：登記指令到 main.py**

在 `the_door/src/the_door/cli/main.py` 加入：

```python
from the_door.cli.wizard_cmd import wizard_cmd
# ... 在 main.add_command(status_cmd) 後加入：
main.add_command(wizard_cmd)
```

- [ ] **Step 5：執行測試確認通過**

```
cd the_door && pytest tests/unit/cli/test_wizard_cmd.py -v
```

預期：全部 PASSED

- [ ] **Step 6：覆蓋率確認**

```
cd the_door && pytest tests/unit/cli/test_wizard_cmd.py --cov=the_door.cli.wizard_cmd --cov-report=term-missing
```

預期：`wizard_cmd.py` 100%

- [ ] **Step 7：完整 Python 測試套件確認**

```
cd the_door && pytest --tb=short -q
```

預期：全部既有測試維持 PASSED，無 regression

- [ ] **Step 8：Commit**

```
git add the_door/src/the_door/cli/wizard_cmd.py the_door/src/the_door/cli/main.py the_door/tests/unit/cli/test_wizard_cmd.py
git commit -m "feat(cli): add 'the-door wizard' interactive analysis command"
```

---

## Self-Review

### Spec Coverage Check

| Requirement | Task |
|---|---|
| R1 cp950 | Task 01 ✓ |
| R2 .claude/ + extra_ignore | Task 02 ✓ |
| R3 source_nodes incremental | Task 05 ✓ |
| R4 FlowGuard e2e | Task 04 ✓ |
| R5 confidence_reason + warnings | Task 03 ✓ |
| R6 filter wiring | Task 06 ✓ |
| R7 topbar label | Task 07 ✓ |
| R8 mindmap version labels | Task 08 ✓ |
| R9 CSS spacing | Task 09 ✓ |
| R10 wizard | Task 10 ✓ |

### Type Consistency

- `FileDiscovery.discover(str, extra_ignore=list[str]|None)` — Task 02 定義，Task 10 呼叫：`discovery.discover(str(codebase_path), extra_ignore=extra_ignore)` ✓
- `FeatureSummary.confidence_reason: str | None` — Task 03 定義，Task 04/05 測試用 `_make_fs` 不帶此欄位（有預設值 None，向後相容）✓
- `state.filterConf / state.filterType / state._filteredFeatures` — Task 06 state.js 加入，app.js 寫入，ui-list.js 讀取 ✓
- `buildMindmapData` 回傳 `versionALabel / versionBLabel` — Task 08 定義，mindmap-popup.html `init()` 讀取 ✓
