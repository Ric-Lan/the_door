# 02 — Guidance Engine (F1 + F2 + F3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stand up the entire Foundation tier — `core/guidance/` package — providing SystemState (read-only project state model + inspector), NextAction (suggester decision tree), and Remediation (error envelope + code catalogue). After this file lands, every Surface (CLI, MCP, viewer) has one canonical place to ask "what state are we in / what should happen next / how to recover from this error."

**Skill profile:** Python — frozen dataclass design, pure-function decision-tree implementation, JSON serialization, deterministic ordering, golden-file test patterns, `time.perf_counter` performance assertion.

**Dependencies:** Requires [00-test-infrastructure.md](00-test-infrastructure.md) AND [01-core-data.md](01-core-data.md) — `SnapshotEntry` type, `SnapshotStore.list_analyzed_versions`, `SnapshotStore.get_structure`, and the P1 drift warning channel must exist.

Skip removals owned by this file:

- **Task 02.2** (`to_json_dict`) → producer side of `tests/contract/test_systemstate_json_contract.py` (consumer side blocked on 05.3).
- **Task 02.3** (`StateInspector.inspect`) → scenario step 2 AND consumer side of `tests/contract/test_snapshot_entry_contract.py` (which also requires 01.5 — if 01.5 has already landed, this commit removes the skip and the test goes GREEN).
- **Task 02.5** (`NextActionSuggester`) → scenario step 3.
- **Task 02.6** (Remediation + envelope) → producer side of `tests/contract/test_remediation_envelope_contract.py` (consumer sides blocked on 04.4 + 05.8).

Property-test candidate in this file: **Task 02.5** (suggester) — invariants "every state yields ≥1 action", "result is sorted by priority ascending", "result is deterministic over equal-by-value inputs". Copy the pattern from `tests/unit/_property_examples.py`.

**Commit conventions:** `feat(guidance):` for new module additions.

## Requirements covered

- [F1 — SystemState Model](../requirements.md#requirement-f1-systemstate-model) — design §F1
- [F2 — NextAction Model + Suggester](../requirements.md#requirement-f2-nextaction-model--suggester) — design §F2
- [F3 — Remediation Model + Standard Error Envelope](../requirements.md#requirement-f3-remediation-model--standard-error-envelope) — design §F3

## Files touched

| Path | Action |
|---|---|
| `the_door/src/the_door/core/guidance/__init__.py` | Create (package marker) |
| `the_door/src/the_door/core/guidance/state.py` | Create — `SystemState`, `SnapshotEntry`, `StateWarning`, `StateInspector`, `to_json_dict` |
| `the_door/src/the_door/core/guidance/actions.py` | Create — `NextAction`, `ActionContext`, `to_json_dict` |
| `the_door/src/the_door/core/guidance/suggester.py` | Create — `NextActionSuggester` + rule table |
| `the_door/src/the_door/core/guidance/remediation.py` | Create — `Remediation` + `make_error_envelope` helper + code catalogue |
| `the_door/tests/unit/core/guidance/__init__.py` | Create (package marker) |
| `the_door/tests/unit/core/guidance/test_state.py` | Create — F1 tests |
| `the_door/tests/unit/core/guidance/test_actions.py` | Create — F2 dataclass tests |
| `the_door/tests/unit/core/guidance/test_suggester.py` | Create — F2 suggester tests |
| `the_door/tests/unit/core/guidance/test_remediation.py` | Create — F3 tests |
| `the_door/tests/fixtures/sample_projects/` | Create fixture sub-dirs for perf + state tests |

---

## Task 02.1 — F1.1/F1.2: SystemState + SnapshotEntry + StateWarning dataclasses

**Files:**
- Create: `the_door/src/the_door/core/guidance/__init__.py` (empty)
- Create: `the_door/src/the_door/core/guidance/state.py`
- Create: `the_door/tests/unit/core/guidance/__init__.py` (empty)
- Create: `the_door/tests/unit/core/guidance/test_state.py`

- [ ] **Step 1: Write the failing import test**

In `test_state.py`:

```python
def test_systemstate_is_frozen_hashable():
    from the_door.core.guidance.state import SystemState, SnapshotEntry, StateWarning
    state = SystemState(
        project_path=Path("/tmp/x"),
        has_dot_the_door=False,
        has_structure_json=False,
        snapshots=(),
        l2_features_analyzed=frozenset(),
        has_api_key=False,
        api_provider=None,
        warnings=(),
    )
    # Frozen
    with pytest.raises((AttributeError, Exception)):
        state.has_dot_the_door = True
    # Hashable
    hash(state)
    # has_snapshots derived
    assert state.has_snapshots is False
    assert state.latest_snapshot is None
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — `ModuleNotFoundError: No module named 'the_door.core.guidance'`.

- [ ] **Step 3: Create the package + dataclasses**

`state.py`:

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ApiProvider = Literal["anthropic", "openai", "ollama"]


@dataclass(frozen=True)
class SnapshotEntry:
    version_id: str
    label: str | None
    git_tags: tuple[str, ...]
    commit_hash: str | None
    timestamp: str
    has_persisted_structure: bool


@dataclass(frozen=True)
class StateWarning:
    code: str
    location: str
    message: str
    remediation_code: str | None = None


@dataclass(frozen=True)
class SystemState:
    project_path: Path
    has_dot_the_door: bool
    has_structure_json: bool
    snapshots: tuple[SnapshotEntry, ...]
    l2_features_analyzed: frozenset[str]
    has_api_key: bool
    api_provider: ApiProvider | None
    warnings: tuple[StateWarning, ...]

    @property
    def has_snapshots(self) -> bool:
        return bool(self.snapshots)

    @property
    def latest_snapshot(self) -> SnapshotEntry | None:
        return self.snapshots[0] if self.snapshots else None
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/guidance/__init__.py the_door/src/the_door/core/guidance/state.py the_door/tests/unit/core/guidance/__init__.py the_door/tests/unit/core/guidance/test_state.py
git commit -m "feat(guidance): SystemState frozen dataclass + entries (F1)"
```

---

## Task 02.2 — F1.4: `to_json_dict` serialization helper

**Files:**
- Modify: `the_door/src/the_door/core/guidance/state.py`
- Modify: `the_door/tests/unit/core/guidance/test_state.py`

- [ ] **Step 1: Write the failing serialization test**

```python
def test_to_json_dict_serializes_systemstate():
    from the_door.core.guidance.state import SystemState, SnapshotEntry, StateWarning, to_json_dict
    state = SystemState(
        project_path=Path("/tmp/x"),
        has_dot_the_door=True,
        has_structure_json=True,
        snapshots=(SnapshotEntry(
            version_id="vid1", label="v1.0.0",
            git_tags=("v1.0.0",), commit_hash="abc123",
            timestamp="2026-01-01T00:00:00Z",
            has_persisted_structure=True,
        ),),
        l2_features_analyzed=frozenset({"feat-b", "feat-a"}),
        has_api_key=True,
        api_provider="anthropic",
        warnings=(),
    )
    out = to_json_dict(state)
    assert out["project_path"] == Path("/tmp/x").as_posix()
    assert out["has_snapshots"] is True  # property
    assert out["latest_snapshot"]["version_id"] == "vid1"
    # frozenset → sorted list
    assert out["l2_features_analyzed"] == ["feat-a", "feat-b"]
    # tuple → list
    assert isinstance(out["snapshots"], list)
    assert isinstance(out["snapshots"][0]["git_tags"], list)
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — `to_json_dict` not defined.

- [ ] **Step 3: Implement `to_json_dict`**

Append to `state.py`:

```python
from dataclasses import fields, is_dataclass


def _value_to_json(value):
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, frozenset):
        return sorted(value)
    if isinstance(value, tuple):
        return [_value_to_json(v) for v in value]
    if is_dataclass(value):
        return {f.name: _value_to_json(getattr(value, f.name)) for f in fields(value)}
    return value


def to_json_dict(state: SystemState) -> dict:
    out = {f.name: _value_to_json(getattr(state, f.name)) for f in fields(state)}
    out["has_snapshots"] = state.has_snapshots
    out["latest_snapshot"] = _value_to_json(state.latest_snapshot)
    return out
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/guidance/state.py the_door/tests/unit/core/guidance/test_state.py
git commit -m "feat(guidance): to_json_dict serializer with property inclusion (F1)"
```

---

## Task 02.3 — F1.1/F1.5/F1.6/F1.7/F1.8: StateInspector implementation

**Files:**
- Modify: `the_door/src/the_door/core/guidance/state.py`
- Modify: `the_door/tests/unit/core/guidance/test_state.py`

- [ ] **Step 1: Write the failing empty-project test (F1-T1)**

```python
def test_inspect_empty_dir_returns_valid_state(tmp_path):
    from the_door.core.guidance.state import StateInspector
    state = StateInspector(tmp_path).inspect()
    assert state.has_dot_the_door is False
    assert state.snapshots == ()
    assert state.warnings == ()
    assert state.l2_features_analyzed == frozenset()
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — `StateInspector` not defined.

- [ ] **Step 3: Implement bail-out path**

```python
class StateInspector:
    def __init__(self, project_path: Path) -> None:
        self._project_path = Path(project_path)

    def inspect(self) -> SystemState:
        dot = self._project_path / ".the-door"
        if not dot.is_dir():
            provider, has_key = self._detect_api_key()
            return SystemState(
                project_path=self._project_path,
                has_dot_the_door=False,
                has_structure_json=False,
                snapshots=(),
                l2_features_analyzed=frozenset(),
                has_api_key=has_key,
                api_provider=provider,
                warnings=(),
            )
        return self._inspect_full(dot)

    def _detect_api_key(self) -> tuple[ApiProvider | None, bool]:
        import os
        if os.environ.get("ANTHROPIC_API_KEY"):
            return ("anthropic", True)
        if os.environ.get("OPENAI_API_KEY"):
            return ("openai", True)
        config_path = Path.home() / ".the-door" / "config.toml"
        if config_path.is_file():
            try:
                import tomllib  # py311+
            except ImportError:
                import tomli as tomllib
            data = tomllib.loads(config_path.read_text())
            provider = data.get("default_provider")
            if provider in ("anthropic", "openai", "ollama"):
                key_field = f"{provider}_api_key"
                if data.get(key_field):
                    return (provider, True)
        return (None, False)
```

- [ ] **Step 4: Verify GREEN for empty-dir test**

Expected: PASS.

- [ ] **Step 5: Write the structure + snapshot inspection tests (F1-T2, T3, T6)**

```python
def _write_snapshot(tmp_path, vid, drift=False):
    snap_dir = tmp_path / ".the-door" / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    feat = {"feature_id": "feat-x", "label": "x", "description": "d",
            "trigger": "t", "trigger_description": "td",
            "confidence": "high", "confidence_reason": "r",
            "source_node_count": 5 if drift else 2,
            "source_nodes": [] if drift else ["a", "b"]}
    (snap_dir / f"{vid}.json").write_text(json.dumps({
        "version_id": vid,
        "label": None,
        "git_tags": [],
        "commit_hash": None,
        "timestamp": "2026-01-01T00:00:00Z",
        "analyzed_files": [],
        "feature_relations_snapshot": [],
        "l1_snapshot": {"feat-x": feat},
    }))


def test_inspect_snapshot_with_persisted_structure(tmp_path):
    _write_snapshot(tmp_path, "vid1")
    struct_dir = tmp_path / ".the-door" / "structures"
    struct_dir.mkdir()
    (struct_dir / "vid1.json.gz").write_bytes(b"placeholder")
    state = StateInspector(tmp_path).inspect()
    assert len(state.snapshots) == 1
    assert state.snapshots[0].has_persisted_structure is True


def test_inspect_snapshot_missing_structure_no_warning(tmp_path):
    _write_snapshot(tmp_path, "vid1")
    state = StateInspector(tmp_path).inspect()
    assert state.snapshots[0].has_persisted_structure is False
    # Missing structure is NOT a corruption warning (gap, not damage)
    assert not any(w.code == "structure_corrupted" for w in state.warnings)


def test_inspect_detects_source_nodes_drift(tmp_path):
    _write_snapshot(tmp_path, "vid1", drift=True)
    state = StateInspector(tmp_path).inspect()
    drift_warnings = [w for w in state.warnings if w.code == "source_nodes_drift"]
    assert len(drift_warnings) == 1
    assert "feat-x" in drift_warnings[0].location
```

- [ ] **Step 6: Verify all 3 RED**

Expected: FAIL — `_inspect_full` not implemented.

- [ ] **Step 7: Implement `_inspect_full`**

```python
def _inspect_full(self, dot: Path) -> SystemState:
    warnings_acc: list[StateWarning] = []

    has_structure_json = (dot / "structure.json").is_file()

    snap_dir = dot / "snapshots"
    struct_dir = dot / "structures"
    entries: list[SnapshotEntry] = []
    if snap_dir.is_dir():
        for snap_path in snap_dir.glob("*.json"):
            try:
                data = json.loads(snap_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                warnings_acc.append(StateWarning(
                    code="snapshot_corrupted",
                    location=f"snapshot/{snap_path.stem}",
                    message=f"failed to parse: {e}",
                    remediation_code="snapshot_corrupted",
                ))
                continue
            vid = data["version_id"]
            # Drift detection (F1 step 4)
            for feat_id, feat in (data.get("l1_snapshot") or {}).items():
                if feat.get("source_node_count", 0) > 0 and not feat.get("source_nodes"):
                    warnings_acc.append(StateWarning(
                        code="source_nodes_drift",
                        location=f"snapshot/{vid}/{feat_id}",
                        message=f"declared count={feat['source_node_count']} but source_nodes empty",
                        remediation_code="source_nodes_drift",
                    ))
            entries.append(SnapshotEntry(
                version_id=vid,
                label=data.get("label"),
                git_tags=tuple(data.get("git_tags", [])),
                commit_hash=data.get("commit_hash"),
                timestamp=data["timestamp"],
                has_persisted_structure=(struct_dir / f"{vid}.json.gz").is_file(),
            ))
    entries.sort(key=lambda e: e.timestamp, reverse=True)

    l2_dir = dot / "l2-outputs"
    l2_ids: set[str] = set()
    if l2_dir.is_dir():
        for p in l2_dir.iterdir():
            if p.suffix == ".json":
                l2_ids.add(p.stem)

    provider, has_key = self._detect_api_key()

    return SystemState(
        project_path=self._project_path,
        has_dot_the_door=True,
        has_structure_json=has_structure_json,
        snapshots=tuple(entries),
        l2_features_analyzed=frozenset(l2_ids),
        has_api_key=has_key,
        api_provider=provider,
        warnings=tuple(warnings_acc),
    )
```

- [ ] **Step 8: Verify GREEN for all 3 tests**

Expected: PASS.

- [ ] **Step 9: Write the corruption test (F1-T4)**

```python
def test_inspect_corrupted_snapshot_emits_warning_continues(tmp_path):
    (tmp_path / ".the-door" / "snapshots").mkdir(parents=True)
    (tmp_path / ".the-door" / "snapshots" / "bad.json").write_text("{not-json")
    _write_snapshot(tmp_path, "good_vid")
    state = StateInspector(tmp_path).inspect()
    assert len(state.snapshots) == 1
    assert state.snapshots[0].version_id == "good_vid"
    assert any(w.code == "snapshot_corrupted" for w in state.warnings)
```

- [ ] **Step 10: Verify GREEN**

Expected: PASS.

- [ ] **Step 11: Write API-key detection tests (F1-T7, T8)**

```python
def test_inspect_detects_anthropic_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    state = StateInspector(tmp_path).inspect()
    assert state.has_api_key is True
    assert state.api_provider == "anthropic"


def test_inspect_no_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    state = StateInspector(tmp_path).inspect()
    assert state.has_api_key is False
    assert state.api_provider is None
```

- [ ] **Step 12: Verify GREEN**

Expected: PASS.

- [ ] **Step 13: Write the performance test (F1-T10)**

Create fixture `the_door/tests/fixtures/sample_projects/perf_10_snapshots/` containing 10 ~50KB snapshot JSON files + a 1500-node structure.json (use a small helper script in the test setup OR pre-generate). Then:

```python
def test_inspect_completes_under_50ms(perf_project_fixture):
    import time
    start = time.perf_counter()
    state = StateInspector(perf_project_fixture).inspect()
    elapsed = time.perf_counter() - start
    assert state.has_dot_the_door is True
    assert len(state.snapshots) == 10
    assert elapsed < 0.05, f"inspection took {elapsed*1000:.1f}ms, over 50ms budget"
```

- [ ] **Step 14: Verify GREEN**

Expected: PASS (or refactor inspector if it overruns).

- [ ] **Step 15: Run unit suite**

Run: `PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/unit/core/guidance/ -q`

- [ ] **Step 16: Commit**

```bash
git add the_door/src/the_door/core/guidance/state.py the_door/tests/unit/core/guidance/test_state.py the_door/tests/fixtures/sample_projects/perf_10_snapshots/
git commit -m "feat(guidance): StateInspector reads .the-door state under 50ms (F1)"
```

---

## Task 02.4 — F2.1: NextAction dataclass + validation

**Files:**
- Create: `the_door/src/the_door/core/guidance/actions.py`
- Create: `the_door/tests/unit/core/guidance/test_actions.py`

- [ ] **Step 1: Write the failing validation tests**

```python
def test_nextaction_requires_exactly_one_form():
    from the_door.core.guidance.actions import NextAction
    # Both → invalid
    with pytest.raises(ValueError, match="exactly one"):
        NextAction(id="x", title="t", rationale="r", priority=1,
                   cli_command="ls", mcp_tool="y")
    # None → invalid
    with pytest.raises(ValueError, match="exactly one"):
        NextAction(id="x", title="t", rationale="r", priority=1)


def test_nextaction_mcp_tool_requires_arguments():
    from the_door.core.guidance.actions import NextAction
    with pytest.raises(ValueError, match="mcp_arguments"):
        NextAction(id="x", title="t", rationale="r", priority=1, mcp_tool="foo")
    # With arguments → valid
    NextAction(id="x", title="t", rationale="r", priority=1, mcp_tool="foo", mcp_arguments={})


def test_nextaction_to_json_dict():
    from the_door.core.guidance.actions import NextAction, to_json_dict
    a = NextAction(id="x", title="T", rationale="R", priority=1, cli_command="ls")
    d = to_json_dict(a)
    assert d == {"id": "x", "title": "T", "rationale": "R", "priority": 1,
                 "cli_command": "ls", "mcp_tool": None, "mcp_arguments": None, "viewer_route": None}
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — module missing.

- [ ] **Step 3: Implement `actions.py`**

```python
from dataclasses import dataclass, asdict
from typing import Literal

ActionContext = Literal["cli", "mcp", "viewer", "after_error"]


@dataclass(frozen=True)
class NextAction:
    id: str
    title: str
    rationale: str
    priority: int
    cli_command: str | None = None
    mcp_tool: str | None = None
    mcp_arguments: dict | None = None
    viewer_route: str | None = None

    def __post_init__(self):
        forms = sum(x is not None for x in (self.cli_command, self.mcp_tool, self.viewer_route))
        if forms != 1:
            raise ValueError("NextAction: exactly one of cli_command/mcp_tool/viewer_route must be set")
        if self.mcp_tool is not None and self.mcp_arguments is None:
            raise ValueError("NextAction: mcp_arguments required when mcp_tool is set")


def to_json_dict(action: NextAction) -> dict:
    return asdict(action)
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/guidance/actions.py the_door/tests/unit/core/guidance/test_actions.py
git commit -m "feat(guidance): NextAction frozen dataclass with form validation (F2)"
```

---

## Task 02.5 — F2.2/F2.6/F2.7: NextActionSuggester with rule table

**Files:**
- Create: `the_door/src/the_door/core/guidance/suggester.py`
- Create: `the_door/tests/unit/core/guidance/test_suggester.py`

- [ ] **Step 1: Write the empty-state test (F2-T3)**

```python
def test_suggester_empty_state_suggests_first_analyze():
    from the_door.core.guidance.suggester import NextActionSuggester
    from the_door.core.guidance.state import SystemState
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=False, has_structure_json=False,
        snapshots=(), l2_features_analyzed=frozenset(),
        has_api_key=True, api_provider="anthropic", warnings=(),
    )
    actions = NextActionSuggester().suggest(state, context="cli")
    assert len(actions) >= 1
    assert actions[0].id == "analyze.first_time"
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the suggester skeleton with the rule table**

Rule factories take `(state, context)` so each rule can emit the surface-appropriate form per design §F2 R11. This keeps `NextAction.__post_init__`'s "exactly one form" invariant honest — no MCP consumer ever receives a stray `cli_command` they cannot execute.

```python
from typing import Callable
from the_door.core.guidance.state import SystemState
from the_door.core.guidance.actions import NextAction, ActionContext


_Factory = Callable[[SystemState, ActionContext], NextAction]
_Rule = tuple[Callable[[SystemState], bool], tuple[ActionContext, ...], _Factory]


def _rule_first_time(state, context):
    path = state.project_path.as_posix()
    if context == "mcp":
        return NextAction(id="analyze.first_time", title="首次分析這個專案",
                          rationale="專案尚未建立 .the-door/，先跑首次分析。", priority=1,
                          mcp_tool="analyze", mcp_arguments={"codebase_path": path})
    return NextAction(id="analyze.first_time", title="首次分析這個專案",
                      rationale="專案尚未建立 .the-door/，先跑首次分析。", priority=1,
                      cli_command=f"the-door analyze {path}")


def _rule_first_time_mode_b(state, context):
    return NextAction(id="analyze.first_time.mode_b",
                      title="首次分析（無 API key，agent 模式）",
                      rationale="無 API key — 改用 MCP extract_structure。", priority=1,
                      mcp_tool="extract_structure",
                      mcp_arguments={"codebase_path": state.project_path.as_posix()})


def _rule_snapshot_write_first(state, context):
    return NextAction(id="snapshot.write_first", title="寫入首個 snapshot",
                      rationale="已有 structure.json 但尚未持久化為 snapshot。", priority=2,
                      mcp_tool="snapshot_write",
                      mcp_arguments={"codebase_path": state.project_path.as_posix()})


def _rule_incremental(state, context):
    path = state.project_path.as_posix()
    label = state.latest_snapshot.label or state.latest_snapshot.version_id
    if context == "mcp":
        return NextAction(id="analyze.incremental", title="分析新版本（繼承既有 baseline）",
                          rationale="已有 baseline + API key。", priority=2,
                          mcp_tool="update", mcp_arguments={"codebase_path": path, "from_snapshot": label})
    return NextAction(id="analyze.incremental", title="分析新版本（繼承既有 baseline）",
                      rationale="已有 baseline + API key。", priority=2,
                      cli_command=f"the-door update --from-snapshot {label} {path}")


def _rule_fetch_diff(state, context):
    label = state.latest_snapshot.label or state.latest_snapshot.version_id
    return NextAction(id="analyze_changes.fetch_diff",
                      title="計算 AST 差異供 agent 推論",
                      rationale="無 API key — 由 agent 看 AST 差異。", priority=2,
                      mcp_tool="analyze_changes",
                      mcp_arguments={"codebase_path": state.project_path.as_posix(), "baseline": label})


def _rule_viewer_open(state, context):
    path = state.project_path.as_posix()
    if context == "viewer":
        return NextAction(id="viewer.open", title="在 viewer 比對兩個版本",
                          rationale="已有 ≥ 2 個 snapshot。", priority=3,
                          viewer_route="/")
    return NextAction(id="viewer.open", title="在 viewer 比對兩個版本",
                      rationale="已有 ≥ 2 個 snapshot。", priority=3,
                      cli_command=f"the-door ui {path}")


def _rule_diff_cli(state, context):
    prev = state.snapshots[1]
    label = prev.label or prev.version_id
    return NextAction(id="diff.cli", title="在 CLI 看版本差異",
                      rationale="想看純文字 diff 摘要。", priority=4,
                      cli_command=f"the-door diff --baseline {label} {state.project_path.as_posix()}")


def _rule_backfill(state, context):
    target = next(s for s in state.snapshots if not s.has_persisted_structure)
    label = target.label or target.version_id
    return NextAction(id="extract.backfill_structure",
                      title="補既有 snapshot 的 persisted structure（無需 API key）",
                      rationale="baseline 缺少 structures/<vid>.json.gz。", priority=5,
                      cli_command=f"the-door extract --as-version {label} <baseline_source_path>")


def _rule_repair_drift(state, context):
    return NextAction(id="analyze.repair_drift",
                      title="重跑 analyze 修復 source_nodes 漂移",
                      rationale="偵測到 source_nodes_drift 警告。", priority=6,
                      cli_command=f"the-door analyze {state.project_path.as_posix()}")


def _rule_system_status(state, context):
    path = state.project_path.as_posix()
    if context == "mcp":
        return NextAction(id="system_status.show", title="查看目前專案狀態與建議",
                          rationale="不確定下一步時的安全選擇。", priority=90,
                          mcp_tool="system_status", mcp_arguments={"project_path": path})
    if context == "viewer":
        return NextAction(id="system_status.show", title="查看目前專案狀態與建議",
                          rationale="不確定下一步時的安全選擇。", priority=90,
                          viewer_route="/?status=1")
    return NextAction(id="system_status.show", title="查看目前專案狀態與建議",
                      rationale="不確定下一步時的安全選擇。", priority=90,
                      cli_command=f"the-door status {path}")


def _rule_onboarding(state, context):
    return NextAction(id="onboarding.read_claude_md", title="閱讀使用指南",
                      rationale="所有 fallback。", priority=99,
                      cli_command="the-door --help")


_RULES: list[_Rule] = [
    (lambda s: not s.has_dot_the_door and s.has_api_key, ("cli", "mcp"), _rule_first_time),
    (lambda s: not s.has_dot_the_door and not s.has_api_key, ("mcp",), _rule_first_time_mode_b),
    (lambda s: s.has_structure_json and not s.snapshots, ("mcp", "after_error"), _rule_snapshot_write_first),
    (lambda s: len(s.snapshots) >= 1 and s.has_api_key, ("cli", "mcp"), _rule_incremental),
    (lambda s: len(s.snapshots) >= 1 and not s.has_api_key, ("mcp",), _rule_fetch_diff),
    (lambda s: len(s.snapshots) >= 2, ("cli", "viewer"), _rule_viewer_open),
    (lambda s: len(s.snapshots) >= 2, ("cli",), _rule_diff_cli),
    (lambda s: bool(s.snapshots) and not all(e.has_persisted_structure for e in s.snapshots), ("cli", "after_error"), _rule_backfill),
    (lambda s: any(w.code == "source_nodes_drift" for w in s.warnings), ("cli",), _rule_repair_drift),
    (lambda s: True, ("cli", "mcp", "viewer", "after_error"), _rule_system_status),
    (lambda s: True, ("cli", "mcp", "viewer", "after_error"), _rule_onboarding),
]


_AFTER_ERROR_BOOST = {
    "no_persisted_structure_for_baseline": "extract.backfill_structure",
    "baseline_not_found": "system_status.show",
    "snapshot_not_found": "system_status.show",
    "no_snapshot_for_baseline": "snapshot.write_first",
}


class NextActionSuggester:
    def suggest(
        self,
        state: SystemState,
        context: ActionContext,
        failure_code: str | None = None,
    ) -> list[NextAction]:
        actions: dict[str, NextAction] = {}
        for predicate, surfaces, factory in _RULES:
            if context not in surfaces:
                continue
            if not predicate(state):
                continue
            action = factory(state, context)
            if action.id not in actions:
                actions[action.id] = action
        if context == "after_error" and failure_code in _AFTER_ERROR_BOOST:
            boost_id = _AFTER_ERROR_BOOST[failure_code]
            if boost_id in actions:
                old = actions[boost_id]
                actions[boost_id] = NextAction(
                    id=old.id, title=old.title, rationale=old.rationale,
                    priority=1,
                    cli_command=old.cli_command, mcp_tool=old.mcp_tool,
                    mcp_arguments=old.mcp_arguments, viewer_route=old.viewer_route,
                )
        result = list(actions.values())
        result.sort(key=lambda a: (a.priority, a.id))
        return result
```

- [ ] **Step 4: Verify GREEN for empty-state test**

Expected: PASS.

- [ ] **Step 5: Write remaining suggester tests (F2-T1, T2, T4–T10)**

Add tests for each test plan row in design §F2. Key ones:

```python
def test_suggester_one_snapshot_with_api_key_suggests_incremental(tmp_path):
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True, has_structure_json=True,
        snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", True),),
        l2_features_analyzed=frozenset(),
        has_api_key=True, api_provider="anthropic", warnings=(),
    )
    top = NextActionSuggester().suggest(state, context="cli")[0]
    assert top.id == "analyze.incremental"
    assert "--from-snapshot v1.0.0" in top.cli_command


def test_suggester_two_snapshots_viewer_context():
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True, has_structure_json=True,
        snapshots=(
            SnapshotEntry("v2", "v1.0.5", (), None, "2026-02-01T00:00:00Z", True),
            SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", True),
        ),
        l2_features_analyzed=frozenset(),
        has_api_key=True, api_provider="anthropic", warnings=(),
    )
    actions = NextActionSuggester().suggest(state, context="viewer")
    assert any(a.id == "viewer.open" for a in actions)


def test_suggester_context_filters_mcp_only():
    # state with 1 snapshot + no API key: fetch_diff is MCP-only
    state = SystemState(
        project_path=Path("/x"),
        has_dot_the_door=True, has_structure_json=True,
        snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", True),),
        l2_features_analyzed=frozenset(),
        has_api_key=False, api_provider=None, warnings=(),
    )
    cli_actions = NextActionSuggester().suggest(state, context="cli")
    assert not any(a.id == "analyze_changes.fetch_diff" for a in cli_actions)


def test_suggester_drift_warning_suggests_repair():
    state = SystemState(
        project_path=Path("/x"), has_dot_the_door=True, has_structure_json=True,
        snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", True),),
        l2_features_analyzed=frozenset(), has_api_key=True, api_provider="anthropic",
        warnings=(StateWarning(code="source_nodes_drift", location="snapshot/v1/feat-x", message="...", remediation_code=None),),
    )
    actions = NextActionSuggester().suggest(state, context="cli")
    assert any(a.id == "analyze.repair_drift" for a in actions)


def test_suggester_is_deterministic():
    state = SystemState(
        project_path=Path("/x"), has_dot_the_door=False, has_structure_json=False,
        snapshots=(), l2_features_analyzed=frozenset(),
        has_api_key=True, api_provider="anthropic", warnings=(),
    )
    s = NextActionSuggester()
    assert s.suggest(state, "cli") == s.suggest(state, "cli")


def test_suggester_after_error_boosts_failure_code():
    state = SystemState(
        project_path=Path("/x"), has_dot_the_door=True, has_structure_json=True,
        snapshots=(SnapshotEntry("v1", "v1.0.0", (), None, "2026-01-01T00:00:00Z", False),),
        l2_features_analyzed=frozenset(), has_api_key=True, api_provider="anthropic", warnings=(),
    )
    top = NextActionSuggester().suggest(state, context="after_error",
                                         failure_code="no_persisted_structure_for_baseline")[0]
    assert top.id == "extract.backfill_structure"


def test_suggester_fallback_always_present():
    state = SystemState(
        project_path=Path("/x"), has_dot_the_door=False, has_structure_json=False,
        snapshots=(), l2_features_analyzed=frozenset(),
        has_api_key=False, api_provider=None, warnings=(),
    )
    actions = NextActionSuggester().suggest(state, context="cli")
    assert any(a.id == "onboarding.read_claude_md" for a in actions)
```

- [ ] **Step 6: Verify all GREEN**

Expected: PASS.

- [ ] **Step 7: Run unit suite**

Run: `PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/unit/core/guidance/ -q`

- [ ] **Step 8: Commit**

```bash
git add the_door/src/the_door/core/guidance/suggester.py the_door/tests/unit/core/guidance/test_suggester.py
git commit -m "feat(guidance): NextActionSuggester rule table + after-error boost (F2)"
```

---

## Task 02.6 — F3: Remediation dataclass + envelope helper + catalogue

**Files:**
- Create: `the_door/src/the_door/core/guidance/remediation.py`
- Create: `the_door/tests/unit/core/guidance/test_remediation.py`

- [ ] **Step 1: Write the Remediation construction test (F3-T1)**

```python
def test_remediation_allows_null_next_action_and_docs():
    from the_door.core.guidance.remediation import Remediation
    r = Remediation(code="x", message="y")
    assert r.next_action is None
    assert r.docs_url is None
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — module missing.

- [ ] **Step 3: Implement Remediation + envelope helper**

`remediation.py`:

```python
from dataclasses import dataclass, asdict
from the_door.core.guidance.actions import NextAction, to_json_dict as action_to_json


@dataclass(frozen=True)
class Remediation:
    code: str
    message: str
    next_action: NextAction | None = None
    docs_url: str | None = None


REMEDIATION_CATALOGUE: dict[str, str] = {
    "no_persisted_structure_for_baseline": "Baseline 缺少持久化的 AST 結構，無法做增量分析。",
    "baseline_not_found": "找不到對應的 baseline snapshot。",
    "snapshot_not_found": "找不到指定的 snapshot 參考。",
    "no_snapshot_for_baseline": "尚未為這個專案寫入任何 snapshot。",
    "source_nodes_drift": "Snapshot 內 source_node_count 與 source_nodes 列表不一致。",
    "node_id_collision": "AST 抽取階段偵測到同名節點碰撞，已加 #N 後綴消歧。",
    "structure_corrupted": "持久化的 structure 檔損毀，已忽略。",
    "snapshot_corrupted": "Snapshot JSON 檔損毀，已略過。",
    "conflicting_flags": "傳入的旗標互斥。",
    "baseline_project_mismatch": "extract --as-version 的 source-path 與 baseline 的 project root 不一致。",
}


def make_error_envelope(
    code: str,
    message: str,
    remediation: Remediation | None,
    source: str,
) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "remediation": _remediation_to_json(remediation) if remediation else None,
            "source": source,
        }
    }


def _remediation_to_json(r: Remediation) -> dict:
    return {
        "code": r.code,
        "message": r.message,
        "next_action": action_to_json(r.next_action) if r.next_action else None,
        "docs_url": r.docs_url,
    }
```

- [ ] **Step 4: Write envelope shape test (F3-T2)**

```python
def test_make_error_envelope_matches_design_shape():
    from the_door.core.guidance.remediation import Remediation, make_error_envelope
    from the_door.core.guidance.actions import NextAction
    rem = Remediation(
        code="snapshot_not_found",
        message="找不到 baseline=v1.0.0",
        next_action=NextAction(id="system_status.show", title="查看狀態", rationale="r", priority=1, cli_command="the-door status"),
        docs_url=None,
    )
    env = make_error_envelope(code="snapshot_not_found", message="...", remediation=rem, source="api_handlers.handle_diff_versions")
    assert env["error"]["code"] == "snapshot_not_found"
    assert env["error"]["remediation"]["code"] == "snapshot_not_found"
    assert env["error"]["remediation"]["next_action"]["id"] == "system_status.show"
    assert env["error"]["source"] == "api_handlers.handle_diff_versions"
```

- [ ] **Step 5: Verify GREEN**

Expected: PASS.

- [ ] **Step 6: Write catalogue uniqueness test (F3 AC5)**

```python
def test_remediation_catalogue_codes_are_unique():
    from the_door.core.guidance.remediation import REMEDIATION_CATALOGUE
    codes = list(REMEDIATION_CATALOGUE.keys())
    assert len(codes) == len(set(codes))
```

- [ ] **Step 7: Verify GREEN**

Expected: PASS.

- [ ] **Step 8: Run unit suite**

Run: `PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/unit/core/guidance/ -q`

Expected: all guidance tests green.

- [ ] **Step 9: Commit**

```bash
git add the_door/src/the_door/core/guidance/remediation.py the_door/tests/unit/core/guidance/test_remediation.py
git commit -m "feat(guidance): Remediation + standard error envelope + code catalogue (F3)"
```

---

## Done criteria for 02-guidance-engine

1. `pytest the_door/tests/unit/core/guidance/ -q` passes (≥ ~25 new tests).
2. `from the_door.core.guidance import state, actions, suggester, remediation` works from any module.
3. `StateInspector(path).inspect()` runs under 50ms on the 10-snapshot fixture.
4. Suggester returns deterministic, sorted output for every reachable state; the fallback `onboarding.read_claude_md` action always appears for any state.
5. `make_error_envelope` produces the exact JSON shape documented in design §F3.
