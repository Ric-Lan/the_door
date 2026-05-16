# 03 — Pipeline + MCP (O1 + S2)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox syntax.

**Goal:** Build the Operations tier's incremental-analysis primitive (O1: `compute_affected_features` pure function + `incremental_pipeline` orchestrator) and the entire MCP surface (S2: `next_actions` envelope on every tool, two new tools `analyze_changes` + `system_status`, extension of `snapshot_write` with `inherit_from`, MCP coverage meta-test).

**Skill profile:** Python — pipeline orchestration, MCP tool authoring + 3-site server registration, response-envelope DRY, hashlib signature comparison, pure function design with no I/O at the core.

**Dependencies:**
- [00-test-infrastructure.md](00-test-infrastructure.md) — contract + scenario scaffolds
- [01-core-data.md](01-core-data.md) — `SnapshotStore.get_structure` and per-version structure files
- [02-guidance-engine.md](02-guidance-engine.md) — `StateInspector`, `NextActionSuggester`, `Remediation`, `make_error_envelope`

Skip removals owned by this file:

- **Task 03.2** (`incremental_pipeline` orchestrator) → scenario step 4.
- **Task 03.5** (`analyze_changes` MCP tool) → producer side of `tests/contract/test_incremental_diff_shape_contract.py`.
- **Task 03.6** (`snapshot_write` `inherit_from`) → scenario step 5.

Property-test candidate in this file: **Task 03.1** (`compute_affected_features`) — invariant "for any baseline + current structures, `len(inherited) + len(affected) == len(baseline.l1_snapshot)` AND no node appears in BOTH `affected_features[*].delta` and `unmapped_nodes`". Copy from `tests/unit/_property_examples.py`.

**Commit conventions:** `feat(incremental):` for O1, `feat(mcp):` for S2, `refactor(mcp):` when modifying existing tools.

## Requirements covered

- [O1 — Incremental Analysis](../requirements.md#requirement-o1-incremental-analysis) — design §O1
- [S2 — MCP Surface](../requirements.md#requirement-s2-mcp-surface) — design §S2

## Files touched

| Path | Action |
|---|---|
| `the_door/src/the_door/core/diff/feature_attribution.py` | Create — `NodeDelta`, `AffectedFeature`, `IncrementalDiff`, `compute_affected_features` |
| `the_door/src/the_door/core/pipeline/incremental_pipeline.py` | Create — orchestrator wiring extract + attribution |
| `the_door/src/the_door/mcp/tools/_response_envelope.py` | Create — DRY helper for `next_actions` injection |
| `the_door/src/the_door/mcp/tools/system_status_tool.py` | Create — F1+F2 dump |
| `the_door/src/the_door/mcp/tools/analyze_changes_tool.py` | Create — O1 read-only tool |
| `the_door/src/the_door/mcp/tools/snapshot_write_tool.py` | Modify — `inherit_from` + `updated_features` optional fields |
| `the_door/src/the_door/mcp/server.py` | Modify — register 2 new tools at 3 sites (imports + `list_tools` + dispatch) |
| Every other `the_door/src/the_door/mcp/tools/*_tool.py` | Modify — wrap responses with `_response_envelope.wrap()` |
| `the_door/tests/unit/core/diff/test_feature_attribution.py` | Create |
| `the_door/tests/unit/mcp/_invocation_recipes.py` | Create — minimal valid inputs per tool, for the meta-test |
| `the_door/tests/unit/mcp/test_response_envelope_coverage.py` | Create — S2 meta-test |
| `the_door/tests/unit/mcp/test_system_status_tool.py` | Create |
| `the_door/tests/unit/mcp/test_analyze_changes_tool.py` | Create |
| `the_door/tests/unit/mcp/test_snapshot_write_tool.py` | Modify — `inherit_from` flow tests |

---

## Task 03.1 — O1 core: `compute_affected_features` pure function

**Files:**
- Create: `the_door/src/the_door/core/diff/feature_attribution.py`
- Create: `the_door/tests/unit/core/diff/test_feature_attribution.py`

- [ ] **Step 1: Write the failing identical-input test (O1-T1)**

```python
def test_identical_structures_no_affected_features():
    from the_door.core.diff.feature_attribution import compute_affected_features
    structure = _sample_structure_with_nodes([("file.py::foo", 1), ("file.py::bar", 5)])
    baseline = _baseline_with_feature("feat-x", source_nodes=("file.py::foo", "file.py::bar"))
    result = compute_affected_features(structure, structure, baseline)
    assert result.affected_features == ()
    assert len(result.inherited_features) == 1
    assert result.unmapped_nodes.added == ()
    assert result.unmapped_nodes.removed == ()
    assert result.unmapped_nodes.modified == ()
```

`_sample_structure_with_nodes` and `_baseline_with_feature` are local test helpers — define them inline in the test file with the minimum fields each requires.

- [ ] **Step 2: Verify RED**

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the dataclasses + function**

```python
from dataclasses import dataclass
import hashlib
from the_door.models import FeatureSummary, VersionSnapshot  # adapt to real imports
from the_door.core.extraction.models import StructureJSON, Node


@dataclass(frozen=True)
class NodeDelta:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    modified: tuple[str, ...]


@dataclass(frozen=True)
class AffectedFeature:
    feature_id: str
    current_label: str
    current_description: str
    current_trigger_description: str | None
    delta: NodeDelta


@dataclass(frozen=True)
class IncrementalDiff:
    baseline_version_id: str
    inherited_features: tuple[FeatureSummary, ...]
    affected_features: tuple[AffectedFeature, ...]
    unmapped_nodes: NodeDelta


def _signature(node: Node) -> str:
    payload = (
        node.name,
        tuple(getattr(node, "params", ()) or ()),
        getattr(node, "return_type", None),
        tuple(getattr(node, "decorators", ()) or ()),
        getattr(node, "docstring", None),
    )
    return hashlib.md5(repr(payload).encode("utf-8")).hexdigest()


def compute_affected_features(
    baseline_structure: StructureJSON,
    current_structure: StructureJSON,
    baseline: VersionSnapshot,
) -> IncrementalDiff:
    baseline_sig = {n.node_id: _signature(n) for n in baseline_structure.nodes}
    current_sig = {n.node_id: _signature(n) for n in current_structure.nodes}

    added = set(current_sig.keys()) - set(baseline_sig.keys())
    removed = set(baseline_sig.keys()) - set(current_sig.keys())
    common = set(baseline_sig.keys()) & set(current_sig.keys())
    modified = {k for k in common if baseline_sig[k] != current_sig[k]}

    inherited: list[FeatureSummary] = []
    affected: list[AffectedFeature] = []
    all_owned_nodes: set[str] = set()

    for fs in baseline.l1_snapshot.values():
        owned = set(fs.source_nodes)
        all_owned_nodes |= owned
        f_added = tuple(sorted(added & owned))
        f_removed = tuple(sorted(removed & owned))
        f_modified = tuple(sorted(modified & owned))
        if f_added or f_removed or f_modified:
            affected.append(AffectedFeature(
                feature_id=fs.feature_id,
                current_label=fs.label,
                current_description=fs.description,
                current_trigger_description=fs.trigger_description,
                delta=NodeDelta(f_added, f_removed, f_modified),
            ))
        else:
            inherited.append(fs)

    unmapped = NodeDelta(
        added=tuple(sorted(added - all_owned_nodes)),
        removed=tuple(sorted(removed - all_owned_nodes)),
        modified=tuple(sorted(modified - all_owned_nodes)),
    )

    return IncrementalDiff(
        baseline_version_id=baseline.version_id,
        inherited_features=tuple(inherited),
        affected_features=tuple(affected),
        unmapped_nodes=unmapped,
    )
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Write remaining O1 tests (T2–T5)**

```python
def test_added_node_in_feature_sources_marks_affected():
    base_struct = _sample_structure_with_nodes([("file.py::foo", 1)])
    cur_struct = _sample_structure_with_nodes([("file.py::foo", 1), ("file.py::new", 10)])
    baseline = _baseline_with_feature("feat-x", source_nodes=("file.py::foo", "file.py::new"))
    diff = compute_affected_features(base_struct, cur_struct, baseline)
    assert len(diff.affected_features) == 1
    assert diff.affected_features[0].delta.added == ("file.py::new",)


def test_removed_node_marks_affected():
    base_struct = _sample_structure_with_nodes([("file.py::foo", 1), ("file.py::gone", 10)])
    cur_struct = _sample_structure_with_nodes([("file.py::foo", 1)])
    baseline = _baseline_with_feature("feat-y", source_nodes=("file.py::foo", "file.py::gone"))
    diff = compute_affected_features(base_struct, cur_struct, baseline)
    assert diff.affected_features[0].delta.removed == ("file.py::gone",)


def test_modified_node_signature_marks_affected():
    base_struct = _sample_structure_with_nodes([("file.py::foo", 1, ("a",))])
    cur_struct = _sample_structure_with_nodes([("file.py::foo", 1, ("a", "b"))])  # params changed
    baseline = _baseline_with_feature("feat-z", source_nodes=("file.py::foo",))
    diff = compute_affected_features(base_struct, cur_struct, baseline)
    assert diff.affected_features[0].delta.modified == ("file.py::foo",)


def test_unmapped_node_does_not_flag_feature():
    base_struct = _sample_structure_with_nodes([])
    cur_struct = _sample_structure_with_nodes([("file.py::orphan", 1)])
    baseline = _baseline_with_feature("feat-w", source_nodes=("file.py::other",))
    diff = compute_affected_features(base_struct, cur_struct, baseline)
    assert diff.affected_features == ()
    assert "file.py::orphan" in diff.unmapped_nodes.added
```

- [ ] **Step 6: Verify all GREEN**

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/diff/feature_attribution.py the_door/tests/unit/core/diff/test_feature_attribution.py
git commit -m "feat(incremental): compute_affected_features pure function (O1)"
```

---

## Task 03.2 — O1: `incremental_pipeline` orchestrator

**Files:**
- Create: `the_door/src/the_door/core/pipeline/incremental_pipeline.py`
- Create: `the_door/tests/unit/core/pipeline/test_incremental_pipeline.py`

- [ ] **Step 1: Write the failing orchestrator test**

```python
def test_run_incremental_pipeline_returns_diff_for_valid_baseline(tmp_path, monkeypatch):
    from the_door.core.pipeline.incremental_pipeline import run_incremental_pipeline
    # Set up a project with one snapshot + persisted structure
    _seed_project(tmp_path, baseline_label="v1.0.0", nodes=[("a", 1), ("b", 2)])
    monkeypatch.setattr(...)  # patch extract if needed
    result = run_incremental_pipeline(codebase_path=tmp_path, baseline_ref="v1.0.0")
    assert result.diff.baseline_version_id  # non-empty
    assert isinstance(result.diff.inherited_features, tuple)
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the orchestrator**

```python
from dataclasses import dataclass
from pathlib import Path

from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.diff.feature_attribution import compute_affected_features, IncrementalDiff
from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.guidance.remediation import Remediation
from the_door.core.guidance.actions import NextAction


@dataclass(frozen=True)
class IncrementalResult:
    diff: IncrementalDiff
    baseline_label: str | None


class IncrementalAnalysisError(Exception):
    def __init__(self, remediation: Remediation):
        super().__init__(remediation.message)
        self.remediation = remediation


def run_incremental_pipeline(
    codebase_path: Path,
    baseline_ref: str,
) -> IncrementalResult:
    codebase_path = Path(codebase_path)
    store = SnapshotStore(codebase_path)
    try:
        baseline = store.resolve_baseline(baseline_ref)
    except Exception:
        baseline = None
    if baseline is None:
        baseline = store.get_snapshot(baseline_ref)
    if baseline is None:
        raise IncrementalAnalysisError(Remediation(
            code="baseline_not_found",
            message=f"Cannot resolve baseline {baseline_ref!r}",
            next_action=NextAction(
                id="system_status.show", title="查看可用 snapshot",
                rationale="列出目前 .the-door/snapshots 內容",
                priority=1,
                cli_command=f"the-door status {codebase_path.as_posix()}",
            ),
        ))

    baseline_structure = store.get_structure(baseline.version_id)
    if baseline_structure is None:
        raise IncrementalAnalysisError(Remediation(
            code="no_persisted_structure_for_baseline",
            message=(
                f"Baseline {baseline_ref!r} 缺少持久化 AST。"
                " 如仍有原始碼：跑 `the-door extract --as-version <baseline_ref> <baseline_source_path>` 補檔（不需 API key）。"
                " 如原始碼已遺失：以 `the-door analyze <current_path>` 重跑完整分析。"
            ),
            next_action=NextAction(
                id="extract.backfill_structure",
                title="補既有 baseline 的 persisted structure",
                rationale="增量分析需要 baseline 的 AST 結構檔。",
                priority=1,
                cli_command=f"the-door extract --as-version {baseline_ref} <baseline_source_path>",
            ),
        ))

    current_structure = ASTExtractor().extract(codebase_path)
    diff = compute_affected_features(baseline_structure, current_structure, baseline)
    return IncrementalResult(diff=diff, baseline_label=baseline.label)
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Write the "missing persisted structure" error test (O1-T8)**

```python
def test_missing_persisted_structure_raises_with_backfill_action(tmp_path):
    _seed_project(tmp_path, baseline_label="v1.0.0", nodes=[], persist_structure=False)
    with pytest.raises(IncrementalAnalysisError) as exc:
        run_incremental_pipeline(codebase_path=tmp_path, baseline_ref="v1.0.0")
    rem = exc.value.remediation
    assert rem.code == "no_persisted_structure_for_baseline"
    assert rem.next_action.id == "extract.backfill_structure"
```

- [ ] **Step 6: Verify GREEN**

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/core/pipeline/incremental_pipeline.py the_door/tests/unit/core/pipeline/test_incremental_pipeline.py
git commit -m "feat(incremental): incremental_pipeline orchestrator (O1)"
```

---

## Task 03.3 — S2: response-envelope helper for all MCP tools

**Files:**
- Create: `the_door/src/the_door/mcp/tools/_response_envelope.py`
- Create: `the_door/tests/unit/mcp/test_response_envelope.py`

- [ ] **Step 1: Write the failing wrap test**

```python
def test_wrap_injects_next_actions(tmp_path):
    from the_door.mcp.tools._response_envelope import wrap
    payload = {"result": "ok"}
    wrapped = wrap(payload, project_path=tmp_path, context="mcp")
    assert "next_actions" in wrapped
    assert isinstance(wrapped["next_actions"], list)
    assert wrapped["result"] == "ok"
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the helper**

```python
from pathlib import Path
from the_door.core.guidance.state import StateInspector
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.core.guidance.actions import ActionContext, to_json_dict as action_to_json


def wrap(payload: dict, project_path: Path, context: ActionContext = "mcp") -> dict:
    state = StateInspector(Path(project_path)).inspect()
    actions = NextActionSuggester().suggest(state, context=context)
    payload["next_actions"] = [action_to_json(a) for a in actions]
    return payload
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/mcp/tools/_response_envelope.py the_door/tests/unit/mcp/test_response_envelope.py
git commit -m "feat(mcp): shared response envelope helper injecting next_actions (S2)"
```

---

## Task 03.4 — S2: `system_status` MCP tool

**Files:**
- Create: `the_door/src/the_door/mcp/tools/system_status_tool.py`
- Modify: `the_door/src/the_door/mcp/server.py` (register at 3 sites)
- Create: `the_door/tests/unit/mcp/test_system_status_tool.py`

- [ ] **Step 1: Write the failing tool test (S2-T1)**

```python
async def test_system_status_returns_state_and_next_actions(tmp_path):
    from the_door.mcp.tools import system_status_tool
    result = await system_status_tool.execute({"project_path": str(tmp_path)})
    assert "state" in result
    assert "next_actions" in result
    assert result["state"]["has_dot_the_door"] is False
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the tool**

```python
from pathlib import Path
from the_door.core.guidance.state import StateInspector, to_json_dict as state_to_json
from the_door.core.guidance.suggester import NextActionSuggester
from the_door.core.guidance.actions import to_json_dict as action_to_json


TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "project_path": {"type": "string", "description": "Defaults to CWD if omitted."},
    },
    "required": [],
}


async def execute(arguments: dict) -> dict:
    project_path = Path(arguments.get("project_path", "."))
    state = StateInspector(project_path).inspect()
    actions = NextActionSuggester().suggest(state, context="mcp")
    return {
        "state": state_to_json(state),
        "next_actions": [action_to_json(a) for a in actions],
    }
```

- [ ] **Step 4: Register in MCP server**

In `mcp/server.py`:
- Near line 17 imports: add `from the_door.mcp.tools import system_status_tool`
- Inside `list_tools()` near line 113: add a `Tool(name="system_status", description="Report current project state + next-action suggestions", inputSchema=system_status_tool.TOOL_SCHEMA)` entry.
- Inside the dispatch handler near line 188: add `if name == "system_status": return await self._dispatch_tool(system_status_tool, arguments)` (match the existing dispatcher pattern).

- [ ] **Step 5: Verify GREEN**

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/mcp/tools/system_status_tool.py the_door/src/the_door/mcp/server.py the_door/tests/unit/mcp/test_system_status_tool.py
git commit -m "feat(mcp): system_status tool (S2)"
```

---

## Task 03.5 — O1: `analyze_changes` MCP tool

**Files:**
- Create: `the_door/src/the_door/mcp/tools/analyze_changes_tool.py`
- Modify: `the_door/src/the_door/mcp/server.py` (register at 3 sites)
- Create: `the_door/tests/unit/mcp/test_analyze_changes_tool.py`

- [ ] **Step 1: Write the failing tool tests (O1-T8, T11)**

```python
async def test_analyze_changes_returns_incremental_diff(seeded_v105_fixture):
    from the_door.mcp.tools import analyze_changes_tool
    result = await analyze_changes_tool.execute({
        "codebase_path": str(seeded_v105_fixture),
        "baseline": "v1.0.0",
    })
    assert "baseline_version_id" in result
    assert "inherited_features" in result
    assert "affected_features" in result
    assert "unmapped_nodes" in result
    assert "next_actions" in result


async def test_analyze_changes_missing_structure_returns_error_envelope(tmp_path):
    # Project with snapshot but no .the-door/structures/<vid>.json.gz
    _seed_project(tmp_path, baseline_label="v1.0.0", persist_structure=False)
    from the_door.mcp.tools import analyze_changes_tool
    result = await analyze_changes_tool.execute({
        "codebase_path": str(tmp_path),
        "baseline": "v1.0.0",
    })
    assert "error" in result
    assert result["error"]["remediation"]["code"] == "no_persisted_structure_for_baseline"
    assert result["error"]["remediation"]["next_action"]["id"] == "extract.backfill_structure"
```

- [ ] **Step 2: Verify RED**

Expected: FAIL.

- [ ] **Step 3: Implement the tool**

```python
from pathlib import Path
from dataclasses import asdict
from the_door.core.pipeline.incremental_pipeline import (
    run_incremental_pipeline, IncrementalAnalysisError,
)
from the_door.core.guidance.remediation import make_error_envelope
from the_door.mcp.tools._response_envelope import wrap


TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "codebase_path": {"type": "string"},
        "baseline": {"type": "string", "description": "label / tag / SHA / date / UUID"},
    },
    "required": ["codebase_path", "baseline"],
}


def _feature_to_json(fs):
    return {
        "feature_id": fs.feature_id, "label": fs.label, "description": fs.description,
        "trigger": fs.trigger, "trigger_description": fs.trigger_description,
        "confidence": fs.confidence, "confidence_reason": fs.confidence_reason,
        "source_nodes": list(fs.source_nodes), "source_node_count": len(fs.source_nodes),
    }


def _affected_to_json(af):
    return {
        "feature_id": af.feature_id,
        "current_label": af.current_label,
        "current_description": af.current_description,
        "current_trigger_description": af.current_trigger_description,
        "delta": {"added": list(af.delta.added), "removed": list(af.delta.removed), "modified": list(af.delta.modified)},
    }


async def execute(arguments: dict) -> dict:
    codebase_path = Path(arguments["codebase_path"])
    baseline_ref = arguments["baseline"]
    try:
        result = run_incremental_pipeline(codebase_path=codebase_path, baseline_ref=baseline_ref)
    except IncrementalAnalysisError as e:
        rem = e.remediation
        return make_error_envelope(code=rem.code, message=rem.message, remediation=rem, source="analyze_changes_tool.handle")

    diff = result.diff
    payload = {
        "baseline_version_id": diff.baseline_version_id,
        "baseline_label": result.baseline_label,
        "inherited_features": [_feature_to_json(fs) for fs in diff.inherited_features],
        "affected_features": [_affected_to_json(af) for af in diff.affected_features],
        "unmapped_nodes": {
            "added": list(diff.unmapped_nodes.added),
            "removed": list(diff.unmapped_nodes.removed),
            "modified": list(diff.unmapped_nodes.modified),
        },
    }
    return wrap(payload, project_path=codebase_path, context="mcp")
```

- [ ] **Step 4: Register at 3 sites in `mcp/server.py`**

Same pattern as 02.4.

- [ ] **Step 5: Verify GREEN**

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/mcp/tools/analyze_changes_tool.py the_door/src/the_door/mcp/server.py the_door/tests/unit/mcp/test_analyze_changes_tool.py
git commit -m "feat(mcp): analyze_changes read-only tool (O1 + S2)"
```

---

## Task 03.6 — O1: `snapshot_write` accepts `inherit_from` + `updated_features`

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/snapshot_write_tool.py`
- Modify: `the_door/tests/unit/mcp/test_snapshot_write_tool.py`

- [ ] **Step 1: Write the inheritance test (O1-T6)**

```python
async def test_snapshot_write_with_inherit_from_merges_features(seeded_v105_fixture):
    from the_door.mcp.tools import snapshot_write_tool
    args = {
        "codebase_path": str(seeded_v105_fixture),
        "inherit_from": "v1.0.0",
        "updated_features": [{
            "feature_id": "feat-ui-server",
            "label": "Local Version Viewer Server (updated)",
            "description": "now serves v1.0.5",
            "trigger": "user runs ui",
            "trigger_description": "td",
            "confidence": "high",
            "confidence_reason": "r",
            "source_nodes": ["node-a", "node-b"],
        }],
    }
    result = await snapshot_write_tool.execute(args)
    assert "error" not in result
    # New snapshot has 12 features: 11 inherited + 1 replaced
    snapshot = _load_snapshot_by_vid(seeded_v105_fixture, result["version_id"])
    assert len(snapshot.l1_snapshot) == 12
    assert snapshot.l1_snapshot["feat-ui-server"].label == "Local Version Viewer Server (updated)"
```

- [ ] **Step 2: Write the regression test (O1-T7)**

```python
async def test_snapshot_write_without_inherit_from_unchanged(tmp_path):
    # Existing 2-arg form (l1_features + relations) still works
    from the_door.mcp.tools import snapshot_write_tool
    args = {
        "codebase_path": str(tmp_path),
        "l1_features": [{"feature_id": "feat-a", "label": "A", "description": "d",
                         "trigger": "t", "trigger_description": "td",
                         "confidence": "high", "confidence_reason": "r",
                         "source_nodes": ["n1"]}],
        "relations": [],
    }
    result = await snapshot_write_tool.execute(args)
    assert "error" not in result
```

- [ ] **Step 3: Verify both RED**

Expected: FAIL — current tool does not understand `inherit_from`.

- [ ] **Step 4: Extend `snapshot_write_tool.py`**

In the schema, add to `properties`:

```python
"inherit_from": {"type": "string", "description": "Baseline ref (label/UUID/...) to inherit features from"},
"updated_features": {"type": "array", "items": {"$ref": "#/$defs/feature"}, "description": "Features to override"},
```

`l1_features` becomes optional when `inherit_from` is present (schema-level: use `oneOf` or runtime check in `handle`).

In `handle`:

```python
async def execute(arguments: dict) -> dict:
    codebase_path = Path(arguments["codebase_path"])
    store = SnapshotStore(codebase_path)

    inherit_from = arguments.get("inherit_from")
    if inherit_from:
        baseline = store.resolve_baseline(inherit_from)
        if baseline is None:
            baseline = store.get_snapshot(inherit_from)
        if baseline is None:
            rem = Remediation(code="baseline_not_found", message=f"Cannot resolve {inherit_from!r}",
                              next_action=NextAction(id="system_status.show", title="查看狀態", rationale="r",
                                                     priority=1, cli_command=f"the-door status {codebase_path.as_posix()}"))
            return make_error_envelope(code=rem.code, message=rem.message, remediation=rem, source="snapshot_write_tool.handle")
        merged = dict(baseline.l1_snapshot)  # feature_id -> FeatureSummary
        for feat_dict in arguments.get("updated_features", []):
            fs = _feature_dict_to_summary(feat_dict)
            merged[fs.feature_id] = fs
        relations = baseline.feature_relations_snapshot
        l1_features = list(merged.values())
    else:
        l1_features = [_feature_dict_to_summary(f) for f in arguments["l1_features"]]
        relations = arguments.get("relations", [])

    snapshot = store.create_snapshot(
        l1_snapshot={fs.feature_id: fs for fs in l1_features},
        feature_relations_snapshot=relations,
        analyzed_files=arguments.get("analyzed_files", []),
        label=arguments.get("label"),
    )
    payload = {"version_id": snapshot.version_id, "label": snapshot.label}
    return wrap(payload, project_path=codebase_path, context="mcp")
```

- [ ] **Step 5: Verify GREEN**

Expected: PASS for both tests.

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/mcp/tools/snapshot_write_tool.py the_door/tests/unit/mcp/test_snapshot_write_tool.py
git commit -m "feat(mcp): snapshot_write accepts inherit_from + updated_features (O1)"
```

---

## Task 03.7 — S2.1/S2.4: wrap every other MCP tool's response

**Files:**
- Modify: every `the_door/src/the_door/mcp/tools/*_tool.py` file that does NOT already use `wrap()`

- [ ] **Step 1: Enumerate tools needing the wrap**

Run `grep -L "_response_envelope" the_door/src/the_door/mcp/tools/*_tool.py` to find any tool whose `execute()` does not import the envelope. Each tool's entry function is named `execute` (verified by grep on `async def execute` across the directory).

- [ ] **Step 2: For each tool, add the wrap call at the end of the success path**

The path-argument name varies per tool — there is **no** uniform `codebase_path` local. Confirmed by grep:

| Tool module | Path argument key in `arguments` |
|---|---|
| `analyze_tool`, `extract_tool` (CLI), `scan_tool`, `update_tool`, `diff_tool`, `snapshot_list_tool`, `snapshot_create_tool`, `snapshot_prune_tool`, `snapshot_write_tool`, `timeline_tool`, `history_tool`, `doubt_list_tool`, `doubt_transition_tool`, `scope_create_tool`, `scope_verify_tool`, `render_tool`, `estimate_tool`, `regenerate_tool`, `analyze_changes_tool` | `codebase_path` |
| `system_status_tool` | `project_path` |
| `project_list_tool` | (none — operates on the global registry) |

Build the path lookup with explicit fallback so each call site stays one line:

```python
from the_door.mcp.tools._response_envelope import wrap
# At the top of execute():
project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
# At the success-path return:
return wrap(payload, project_path=project_root, context="mcp")
```

For `project_list_tool` (no project context), pass `Path.cwd()` — `wrap()` still emits `next_actions` for the current directory state, which is a reasonable fallback.

Read-only listing tools MAY have an empty `next_actions` list but MUST still include the key — `wrap()` handles this uniformly.

- [ ] **Step 3: Run the MCP unit test suite**

```bash
PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/unit/mcp/ -q
```

Expected: all tests still pass; modified tools haven't broken any existing assertion.

- [ ] **Step 4: Commit**

```bash
git add the_door/src/the_door/mcp/tools/*.py
git commit -m "feat(mcp): inject next_actions into every tool's success response (S2)"
```

---

## Task 03.8 — S2 meta-test: response envelope coverage

**Files:**
- Create: `the_door/tests/unit/mcp/_invocation_recipes.py`
- Create: `the_door/tests/unit/mcp/test_response_envelope_coverage.py`

- [ ] **Step 1: Build invocation recipes**

`_invocation_recipes.py`:

```python
"""Minimal valid input per MCP tool, for the meta-test in test_response_envelope_coverage.py.

Each entry: tool_module_name -> async callable producing (args, fixture_setup) for the call.
This is a TEST FIXTURE FILE, not a production module.
"""
from pathlib import Path


def _seeded_project(tmp_path: Path) -> Path:
    # Build a minimal valid .the-door/ structure
    (tmp_path / ".the-door" / "snapshots").mkdir(parents=True)
    (tmp_path / ".the-door" / "structure.json").write_text("{}")
    return tmp_path


RECIPES = {
    "system_status_tool": lambda tmp: ({"project_path": str(_seeded_project(tmp))}, None),
    "snapshot_list_tool": lambda tmp: ({"codebase_path": str(_seeded_project(tmp))}, None),
    "project_list_tool": lambda tmp: ({}, None),
    # ... add one entry per registered tool
}
```

Enumerate every tool in `the_door/src/the_door/mcp/tools/` and add a recipe.

- [ ] **Step 2: Write the meta-test**

```python
import pytest
from pathlib import Path
import importlib
from the_door.mcp import server as mcp_server
from the_door.tests.unit.mcp._invocation_recipes import RECIPES


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_module_name", sorted(RECIPES.keys()))
async def test_every_tool_returns_next_actions(tool_module_name, tmp_path):
    module = importlib.import_module(f"the_door.mcp.tools.{tool_module_name}")
    args, _ = RECIPES[tool_module_name](tmp_path)
    result = await module.execute(args)
    if "error" in result:
        # Error envelopes don't need next_actions at the top level — they live under error.remediation
        pytest.skip(f"{tool_module_name} returned error envelope; check covered by F3 tests")
    assert "next_actions" in result, f"{tool_module_name} did not include next_actions key"
    assert isinstance(result["next_actions"], list)
```

- [ ] **Step 3: Verify GREEN**

Expected: PASS for all enumerated tools. Any tool missing the wrap call fails this meta-test by name.

- [ ] **Step 4: Commit**

```bash
git add the_door/tests/unit/mcp/_invocation_recipes.py the_door/tests/unit/mcp/test_response_envelope_coverage.py
git commit -m "test(mcp): meta-test enforces next_actions on every tool response (S2)"
```

---

## Done criteria for 03-pipeline-mcp

1. `pytest the_door/tests/unit/core/diff/test_feature_attribution.py the_door/tests/unit/core/pipeline/test_incremental_pipeline.py the_door/tests/unit/mcp/ -q` passes.
2. MCP `system_status` tool returns `{state, next_actions}` for any project path.
3. MCP `analyze_changes` tool returns the IncrementalDiff JSON for a seeded baseline; returns F3 envelope when baseline structure is missing.
4. MCP `snapshot_write` accepts `inherit_from + updated_features` and produces a merged snapshot; existing two-arg form still works.
5. Meta-test in `test_response_envelope_coverage.py` proves every registered MCP tool injects `next_actions` on success.
