# 01 — Core Data Layer (P1 + P2 + P3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this file task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock down the three Primitives-tier requirements — snapshot store source-nodes invariant (P1), per-version structure persistence (P2), and AST node_id disambiguation (P3) — so every downstream tier can rely on a coherent on-disk format.

**Skill profile:** Python data work — frozen dataclasses, JSON I/O, gzip, deterministic post-processing, `caplog` warning capture, pytest fixtures, integration tests over the analyze pipeline.

**Dependencies:** Requires [00-test-infrastructure.md](00-test-infrastructure.md) — `hypothesis` dev dep + the contract/scenario test scaffolds must be in place.

Skip removals owned by this file (each is one step in `tests/contract/` or `tests/scenario/`; remove the matching `pytest.skip` in the same commit that satisfies the task):

- **Task 01.5** (`list_analyzed_versions`) → scenario step 1 (`tests/scenario/test_v105_incremental_flow.py::_step_1_inspect_returns_one_snapshot`) AND the producer side of `tests/contract/test_snapshot_entry_contract.py` (consumer side still blocked on 02.3 — the contract stays GREEN-skipped if 02.3 hasn't landed yet).

Property-test candidate in this file: **Task 01.7** (`_disambiguate_node_ids`) — invariant "`len(set(output node_ids)) == len(input nodes)`" for any node list. Copy the pattern from `tests/unit/_property_examples.py`.

**Commit conventions:** `refactor(snapshot):` for P1, `feat(snapshot):` for P2, `fix(extraction):` for P3.

## Requirements covered

- [P1 — Snapshot Store Source-Nodes Invariant](../requirements.md#requirement-p1-snapshot-store-source-nodes-invariant) — design §P1
- [P2 — Per-Version Structure Persistence](../requirements.md#requirement-p2-per-version-structure-persistence) — design §P2
- [P3 — AST Extractor node_id Uniqueness](../requirements.md#requirement-p3-ast-extractor-node_id-uniqueness) — design §P3

## Files touched

| Path | Action |
|---|---|
| `the_door/src/the_door/core/diff/snapshot_store.py` | Modify (P1 serialize/deserialize, P2 add `get_structure` + `list_analyzed_versions`) |
| `the_door/src/the_door/core/extraction/structure_serializer.py` | Modify (P2 add `write_versioned_structure`) |
| `the_door/src/the_door/core/extraction/ast_extractor.py` | Modify (P3 add `_disambiguate_node_ids` post-processing pass) |
| `the_door/src/the_door/core/pipeline/analyze_pipeline.py` | Modify (P2 wire `write_versioned_structure` after snapshot creation) |
| `the_door/src/the_door/core/timeline/timeline_renderer.py` | Modify (P1 read from `source_nodes`) |
| `the_door/src/the_door/mcp/tools/snapshot_write_tool.py` | Modify (P1 drop `source_node_count` from required) |
| `the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py` | Modify or create (P1 + P2 tests) |
| `the_door/tests/unit/core/extraction/test_versioned_structure.py` | Create (P2 round-trip tests) |
| `the_door/tests/unit/core/extraction/test_ast_extractor.py` | Modify (P3 disambiguation tests) |
| `the_door/tests/unit/core/timeline/test_timeline_renderer.py` | Modify or create (P1 reader test) |
| `the_door/tests/unit/mcp/test_snapshot_write_tool.py` | Modify (P1 schema test) |
| `the_door/tests/integration/test_analyze_pipeline_versioned_structure.py` | Create (P2 pipeline integration) |
| `the_door/tests/fixtures/sample_codebases/colliding_init/__init__.py` | Create (P3 fixture) |
| `the_door/tests/fixtures/sample_codebases/colliding_init/module_a.py` | Create (P3 fixture) |

---

## Task 01.1 — P1.1/P1.2: SnapshotStore serialization derives `source_node_count`

**Files:**
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py` (write path near line 170)
- Test: `the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py`

- [ ] **Step 1: Write the failing serialization test**

Add to `test_snapshot_store_roundtrip.py`:

```python
def test_create_snapshot_overrides_caller_source_node_count(tmp_path):
    store = SnapshotStore(tmp_path)
    fs = FeatureSummary(
        feature_id="feat-x",
        label="x",
        description="d",
        trigger="t",
        trigger_description="td",
        confidence="high",
        confidence_reason="r",
        source_node_count=99,
        source_nodes=("a", "b"),
    )
    snapshot = store.create_snapshot(
        l1_snapshot={"feat-x": fs},
        feature_relations_snapshot=[],
        analyzed_files=[],
    )
    on_disk = json.loads((tmp_path / ".the-door" / "snapshots" / f"{snapshot.version_id}.json").read_text())
    assert on_disk["l1_snapshot"]["feat-x"]["source_node_count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py::test_create_snapshot_overrides_caller_source_node_count -v`

Expected: FAIL with `assert 99 == 2` (current code writes `fs.source_node_count` verbatim).

- [ ] **Step 3: Implement the serialization derivation**

In `snapshot_store.py` change the serialization line (grep for `"source_node_count": fs.source_node_count` to find the exact current location):

```python
"source_node_count": len(fs.source_nodes),
```

- [ ] **Step 4: Verify the test now passes**

Run the same command. Expected: PASS.

- [ ] **Step 5: Write the deserialize drift test**

Drift is emitted via `warnings.warn` (stdlib), so the test uses `pytest.warns` — `caplog` does NOT capture warnings. Add to the same file:

```python
def test_deserialize_legacy_drift_warns_and_normalizes(tmp_path):
    snap_dir = tmp_path / ".the-door" / "snapshots"
    snap_dir.mkdir(parents=True)
    vid = "abc12345-0000-0000-0000-000000000000"
    (snap_dir / f"{vid}.json").write_text(json.dumps({
        "version_id": vid,
        "timestamp": "2026-01-01T00:00:00Z",
        "label": None,
        "git_tags": [],
        "commit_hash": None,
        "analyzed_files": [],
        "feature_relations_snapshot": [],
        "l1_snapshot": {
            "feat-x": {
                "feature_id": "feat-x", "label": "x", "description": "d",
                "trigger": "t", "trigger_description": "td",
                "confidence": "high", "confidence_reason": "r",
                "source_node_count": 5,
                "source_nodes": [],
            }
        },
    }))
    with pytest.warns(UserWarning, match=r"source_nodes_drift.*feat-x"):
        snap = SnapshotStore(tmp_path).get_snapshot(vid)
    fs = snap.l1_snapshot["feat-x"]
    assert fs.source_node_count == 0
    assert fs.source_nodes == ()
```

- [ ] **Step 6: Verify the test fails**

Expected: FAIL — current deserializer either constructs `FeatureSummary(source_node_count=5, source_nodes=())` (drift carried through) or raises `ValueError` if it asserts equality.

- [ ] **Step 7: Implement the deserialize warning**

In `snapshot_store.py` find the deserialization site (grep `source_node_count` near `_deserialize_snapshot` or `get_snapshot`). Add:

```python
import warnings
# inside the per-feature deserialize loop:
declared_count = fdata.get("source_node_count", 0)
source_nodes = tuple(fdata.get("source_nodes", ()) or ())
if declared_count > 0 and not source_nodes:
    warnings.warn(
        f"source_nodes_drift in snapshot {snapshot_path.name} feature {fdata['feature_id']}: "
        f"declared count={declared_count} but source_nodes empty; normalized to 0/()",
        stacklevel=2,
    )
    declared_count = 0
fs_kwargs["source_node_count"] = declared_count
fs_kwargs["source_nodes"] = source_nodes
```

(Adapt to the actual variable names in the existing deserializer — the architectural commitment is: drift triggers a stdlib `warnings.warn` AND normalizes count to `len(source_nodes)` before constructing the `FeatureSummary`.)

- [ ] **Step 8: Verify the test passes**

Expected: PASS.

- [ ] **Step 9: Run full unit suite**

Run: `PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/unit/ -q`

Expected: all green; 2 new tests added.

- [ ] **Step 10: Commit**

```bash
git add the_door/src/the_door/core/diff/snapshot_store.py the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py
git commit -m "refactor(snapshot): derive source_node_count on write, warn on read-time drift (P1)"
```

---

## Task 01.2 — P1.3: `snapshot_write` MCP tool drops `source_node_count` from required

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/snapshot_write_tool.py` (schema near line 33, construction near line 109)
- Test: `the_door/tests/unit/mcp/test_snapshot_write_tool.py`

- [ ] **Step 1: Write the failing test**

Add to `test_snapshot_write_tool.py`:

```python
async def test_snapshot_write_succeeds_without_source_node_count(tmp_path):
    args = {
        "codebase_path": str(tmp_path),
        "l1_features": [{
            "feature_id": "feat-a", "label": "A", "description": "d",
            "trigger": "t", "trigger_description": "td",
            "confidence": "high", "confidence_reason": "r",
            "source_nodes": ["n1", "n2", "n3"],
            # source_node_count intentionally absent
        }],
        "relations": [],
    }
    result = await snapshot_write_tool.execute(args)
    assert "error" not in result
    on_disk = json.loads((tmp_path / ".the-door" / "snapshots" / f"{result['version_id']}.json").read_text())
    assert on_disk["l1_snapshot"]["feat-a"]["source_node_count"] == 3
```

- [ ] **Step 2: Verify RED**

Run: `pytest the_door/tests/unit/mcp/test_snapshot_write_tool.py::test_snapshot_write_succeeds_without_source_node_count -v`

Expected: FAIL — current schema requires `source_node_count`; tool returns a schema validation error.

- [ ] **Step 3: Update schema**

In `snapshot_write_tool.py` find the `required` array within the `l1_features` item schema and remove `"source_node_count"`. Keep `source_nodes` required.

- [ ] **Step 4: Update construction**

In the same file, find where `FeatureSummary` (or the equivalent feature dict) is constructed from input. Replace `source_node_count=feature["source_node_count"]` with:

```python
source_node_count=len(feature.get("source_nodes", []) or []),
```

The caller-supplied value (if any) is ignored.

- [ ] **Step 5: Verify GREEN**

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/mcp/tools/snapshot_write_tool.py the_door/tests/unit/mcp/test_snapshot_write_tool.py
git commit -m "refactor(snapshot_write): make source_node_count optional in schema (P1)"
```

---

## Task 01.3 — P1.4: `timeline_renderer` reads from `source_nodes`

**Files:**
- Modify: `the_door/src/the_door/core/timeline/timeline_renderer.py` (near line 267 — grep `source_node_count` to find current line)
- Test: `the_door/tests/unit/core/timeline/test_timeline_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
def test_timeline_renders_source_node_count_from_list_length():
    fs = FeatureSummary(
        feature_id="feat-x", label="X", description="d",
        trigger="t", trigger_description="td",
        confidence="high", confidence_reason="r",
        source_node_count=99,  # drift
        source_nodes=("a", "b", "c"),
    )
    output = render_timeline_for_feature(fs)  # or the actual entry point
    assert "Source Nodes: 3" in output
```

- [ ] **Step 2: Verify RED**

Expected: FAIL with `"Source Nodes: 99" in output` (drift carried through).

- [ ] **Step 3: Edit the renderer**

Locate the line emitting `source_node_count`. Change `feature.source_node_count` to `len(feature.source_nodes)`.

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/timeline/timeline_renderer.py the_door/tests/unit/core/timeline/test_timeline_renderer.py
git commit -m "refactor(timeline): read source-node count from list length (P1)"
```

---

## Task 01.4 — P2.1: `write_versioned_structure` + `get_structure` round trip

**Files:**
- Create: `the_door/src/the_door/core/extraction/structure_serializer.py` is existing — add `write_versioned_structure` function.
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py` — add `get_structure` method.
- Create: `the_door/tests/unit/core/extraction/test_versioned_structure.py`

- [ ] **Step 1: Write the failing round-trip test**

Note: the existing serializer uses `build_structure_dict(structure, scan_result)` to convert StructureJSON → dict (see `core/extraction/structure_serializer.py`). There is **no** symmetric parse helper today — this task adds one (`parse_structure_dict`) so `get_structure` can round-trip.

Create the test file with:

```python
import gzip, json
from pathlib import Path
from the_door.core.extraction.structure_serializer import write_versioned_structure
from the_door.core.diff.snapshot_store import SnapshotStore
from the_door.core.extraction.models import StructureJSON  # adapt to real import

def _sample_structure():
    return StructureJSON(
        files=[],
        nodes=[],
        edges=[],
        topology={},
        analyzed_files=[],
    )

def test_write_and_read_roundtrip(tmp_path):
    vid = "11111111-2222-3333-4444-555555555555"
    structure = _sample_structure()
    path = write_versioned_structure(tmp_path, vid, structure, scan_result=None)
    assert path.exists()
    assert path.name == f"{vid}.json.gz"
    loaded = SnapshotStore(tmp_path).get_structure(vid)
    assert loaded is not None
    # Compare via the dict form (StructureJSON dataclass equality may not be implemented)
    from the_door.core.extraction.structure_serializer import build_structure_dict
    assert build_structure_dict(loaded, scan_result=None) == build_structure_dict(structure, scan_result=None)
```

- [ ] **Step 2: Verify RED**

Run: `pytest the_door/tests/unit/core/extraction/test_versioned_structure.py -v`

Expected: FAIL with `ImportError: cannot import name 'write_versioned_structure'` (or `AttributeError: 'SnapshotStore' has no attribute 'get_structure'`).

- [ ] **Step 3: Implement `write_versioned_structure` + add `parse_structure_dict`**

In `structure_serializer.py`, reuse the existing `build_structure_dict(structure, scan_result)` for the write side and add a `parse_structure_dict` for the read side:

```python
def write_versioned_structure(
    project_path: Path,
    version_id: str,
    structure: StructureJSON,
    scan_result: ScanResult | None,
) -> Path:
    dst_dir = Path(project_path) / ".the-door" / "structures"
    dst_dir.mkdir(parents=True, exist_ok=True)
    path = dst_dir / f"{version_id}.json.gz"
    data = build_structure_dict(structure, scan_result)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def parse_structure_dict(data: dict) -> StructureJSON:
    """Inverse of build_structure_dict. Reconstructs StructureJSON from a parsed dict.
    Field set must match build_structure_dict's output."""
    # Implement to mirror build_structure_dict — same field names + Node/Edge/Topology
    # reconstruction. Confirm field set by reading build_structure_dict.
    ...
```

The `...` is implementation-direction: read `build_structure_dict` to enumerate the dict shape (files / nodes / edges / topology / analyzed_files keys), then reverse with `StructureJSON(...)` and `Node(...)` constructors. Keep the function in the same module — symmetric with the write helper.

- [ ] **Step 4: Implement `SnapshotStore.get_structure`**

```python
def get_structure(self, version_id: str) -> StructureJSON | None:
    path = self._project_path / ".the-door" / "structures" / f"{version_id}.json.gz"
    if not path.is_file():
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        return parse_structure_dict(data)
    except (gzip.BadGzipFile, json.JSONDecodeError, OSError) as e:
        warnings.warn(f"structure_corrupted at {path.name}: {e}", stacklevel=2)
        return None
```

- [ ] **Step 5: Verify GREEN**

Expected: PASS.

- [ ] **Step 6: Write the corruption + missing-file tests**

```python
def test_get_structure_missing_returns_none(tmp_path):
    assert SnapshotStore(tmp_path).get_structure("does-not-exist") is None

def test_get_structure_corrupted_gzip_warns_returns_none(tmp_path):
    dst = tmp_path / ".the-door" / "structures"
    dst.mkdir(parents=True)
    (dst / "vid.json.gz").write_bytes(b"\x1f\x8bnotgzip")
    with pytest.warns(UserWarning, match="structure_corrupted"):
        result = SnapshotStore(tmp_path).get_structure("vid")
    assert result is None
```

- [ ] **Step 7: Verify GREEN (corruption guard already in place from Step 4)**

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add the_door/src/the_door/core/extraction/structure_serializer.py the_door/src/the_door/core/diff/snapshot_store.py the_door/tests/unit/core/extraction/test_versioned_structure.py
git commit -m "feat(snapshot): write and read per-version gzipped structure (P2)"
```

---

## Task 01.5 — P2.5: `SnapshotStore.list_analyzed_versions`

**Files:**
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py`
- Test: `the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py`

- [ ] **Step 1: Write the failing test**

```python
def test_list_analyzed_versions_marks_has_persisted_structure(tmp_path):
    store = SnapshotStore(tmp_path)
    # Create two snapshots
    s1 = store.create_snapshot(l1_snapshot={}, feature_relations_snapshot=[], analyzed_files=[])
    s2 = store.create_snapshot(l1_snapshot={}, feature_relations_snapshot=[], analyzed_files=[])
    # Only persist structure for s2
    write_versioned_structure(tmp_path, s2.version_id, _sample_structure(), None)
    entries = store.list_analyzed_versions()
    assert len(entries) == 2
    by_id = {e.version_id: e for e in entries}
    assert by_id[s1.version_id].has_persisted_structure is False
    assert by_id[s2.version_id].has_persisted_structure is True
    # Order by timestamp DESC (s2 created after s1)
    assert entries[0].version_id == s2.version_id
```

Note: `SnapshotEntry` is defined in [02-guidance-engine.md](02-guidance-engine.md) Task 02.1. For this task's test to compile, **at the top of `snapshot_store.py` define a forward-compatible local type** (or import from `core.guidance.state` if 02-guidance-engine has already landed). Choose: if executing 01 before 02 (recommended order), define `SnapshotEntry` in `core/diff/snapshot_store.py` as a frozen dataclass with fields `(version_id, label, git_tags, commit_hash, timestamp, has_persisted_structure)`. When 02-guidance-engine lands, `core/guidance/state.py` imports and re-exports this exact type — no duplicate definition.

- [ ] **Step 2: Verify RED**

Expected: FAIL — method doesn't exist.

- [ ] **Step 3: Implement `list_analyzed_versions`**

```python
def list_analyzed_versions(self) -> list[SnapshotEntry]:
    snap_dir = self._project_path / ".the-door" / "snapshots"
    struct_dir = self._project_path / ".the-door" / "structures"
    if not snap_dir.is_dir():
        return []
    entries = []
    for snap_path in snap_dir.glob("*.json"):
        try:
            data = json.loads(snap_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        vid = data["version_id"]
        entries.append(SnapshotEntry(
            version_id=vid,
            label=data.get("label"),
            git_tags=tuple(data.get("git_tags", [])),
            commit_hash=data.get("commit_hash"),
            timestamp=data["timestamp"],
            has_persisted_structure=(struct_dir / f"{vid}.json.gz").is_file(),
        ))
    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries
```

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/core/diff/snapshot_store.py the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py
git commit -m "feat(snapshot): list_analyzed_versions enumerates snapshot + structure availability (P2)"
```

---

## Task 01.6 — P2.1: analyze pipeline writes per-version structure

**Files:**
- Modify: `the_door/src/the_door/core/pipeline/analyze_pipeline.py` (near lines 179–181 — confirm with grep)
- Create: `the_door/tests/integration/test_analyze_pipeline_versioned_structure.py`

- [ ] **Step 1: Write the failing integration test**

The real LLM entry point in `analyze_pipeline.py` goes via `create_provider(td_config)` + `BatchReader(llm_provider=...)`. To avoid hitting the network, patch the provider factory to return a stub that yields empty feature lists.

```python
def test_analyze_pipeline_writes_versioned_structure(tiny_python_fixture, tmp_path, monkeypatch):
    # tiny_python_fixture = an existing fixture (one .py file). Reuse the smallest
    # fixture under the_door/tests/fixtures/sample_codebases/.

    class _StubProvider:
        async def complete(self, *a, **k):
            return ""  # adapt to the real provider interface
    monkeypatch.setattr(
        "the_door.core.pipeline.analyze_pipeline.create_provider",
        lambda *a, **k: _StubProvider(),
    )
    # If BatchReader still tries to parse the LLM response into features, also patch it
    # to return an empty list — grep `BatchReader` in analyze_pipeline.py to confirm
    # the exact attribute to stub. Architectural commitment: the test must not require
    # an API key.

    result = run_analyze_pipeline(codebase_path=tiny_python_fixture, project_path=tmp_path)
    snapshot = result.snapshot
    gz_path = tmp_path / ".the-door" / "structures" / f"{snapshot.version_id}.json.gz"
    assert gz_path.is_file()
    loaded = SnapshotStore(tmp_path).get_structure(snapshot.version_id)
    assert loaded is not None
    assert len(loaded.nodes) == len(result.structure.nodes)
```

- [ ] **Step 2: Verify RED**

Expected: FAIL — pipeline does not call `write_versioned_structure`; `.gz` file absent.

- [ ] **Step 3: Wire `write_versioned_structure` into the pipeline**

In `analyze_pipeline.py`, after `snapshot = _create_auto_snapshot(...)` returns and before `return AnalyzeResult(...)`:

```python
try:
    write_versioned_structure(codebase_path, snapshot.version_id, structure, scan_result)
except Exception as e:
    logger.warning("versioned_structure_write_failed", extra={"version_id": snapshot.version_id, "error": str(e)})
    if progress is not None:
        progress("warning", f"per-version structure write failed: {e}")
```

(Non-fatal — failure must not break the pipeline. Mirrors `_create_auto_snapshot`'s own try/except convention.)

- [ ] **Step 4: Verify GREEN**

Expected: PASS.

- [ ] **Step 5: Write the "non-fatal" failure test**

```python
def test_analyze_pipeline_versioned_structure_write_failure_is_nonfatal(monkeypatch, tiny_python_fixture, tmp_path, caplog):
    monkeypatch.setattr(
        "the_door.core.pipeline.analyze_pipeline.write_versioned_structure",
        lambda *a, **k: (_ for _ in ()).throw(IOError("disk full"))
    )
    monkeypatch.setattr("the_door.core.pipeline.analyze_pipeline._call_llm_for_features", lambda *a, **k: ())
    with caplog.at_level("WARNING"):
        result = run_analyze_pipeline(codebase_path=tiny_python_fixture, project_path=tmp_path)
    assert result is not None  # pipeline completed
    assert any("versioned_structure_write_failed" in r.message for r in caplog.records)
```

- [ ] **Step 6: Verify GREEN**

Expected: PASS.

- [ ] **Step 7: Run full integration suite**

Run: `PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/integration/ -q`

Expected: green, including the 2 new tests.

- [ ] **Step 8: Commit**

```bash
git add the_door/src/the_door/core/pipeline/analyze_pipeline.py the_door/tests/integration/test_analyze_pipeline_versioned_structure.py
git commit -m "feat(pipeline): analyze writes per-version structure non-fatally (P2)"
```

---

## Task 01.7 — P3: AST extractor disambiguates colliding node_ids

**Files:**
- Modify: `the_door/src/the_door/core/extraction/ast_extractor.py`
- Modify: `the_door/tests/unit/core/extraction/test_ast_extractor.py`
- Create: `the_door/tests/fixtures/sample_codebases/colliding_init/__init__.py` (empty)
- Create: `the_door/tests/fixtures/sample_codebases/colliding_init/module_a.py`

- [ ] **Step 1: Create the collision fixture**

`module_a.py` content:

```python
class A:
    def __init__(self):
        pass

class B:
    def __init__(self):
        pass

def __init__():
    pass
```

`__init__.py` content: empty (just makes the directory a package — match existing fixture style).

- [ ] **Step 2: Write the failing collision test**

In `test_ast_extractor.py`:

```python
def test_extract_disambiguates_three_colliding_init():
    fixture = Path(__file__).parent.parent.parent.parent / "fixtures" / "sample_codebases" / "colliding_init"
    result = ASTExtractor().extract(fixture)
    init_ids = [
        n.node_id for n in result.nodes
        if n.node_id.endswith("::__init__") or "::__init__#" in n.node_id
    ]
    # Three colliding __init__ nodes: base + #2 + #3
    assert len(init_ids) == 3
    assert len(set(init_ids)) == 3  # all distinct
    assert any(nid.endswith("::__init__") for nid in init_ids)       # the base id is kept
    assert any(nid.endswith("::__init__#2") for nid in init_ids)
    assert any(nid.endswith("::__init__#3") for nid in init_ids)
    # No duplicate ids globally
    assert len(set(n.node_id for n in result.nodes)) == len(result.nodes)
```

- [ ] **Step 3: Verify RED**

Expected: FAIL — either duplicate ids in the result, or only one `__init__` node returned (current extractor collapses).

- [ ] **Step 4: Implement `_disambiguate_node_ids`**

In `ast_extractor.py`, add at the bottom of `ASTExtractor`:

```python
def _disambiguate_node_ids(self, nodes: list[Node]) -> list[Node]:
    from collections import defaultdict
    from dataclasses import replace
    groups: dict[str, list[Node]] = defaultdict(list)
    for n in nodes:
        groups[n.node_id].append(n)
    result: list[Node] = []
    for tentative_id, group in groups.items():
        if len(group) == 1:
            result.append(group[0])
            continue
        group_sorted = sorted(group, key=lambda n: (n.file, n.line_number))
        self._warnings.append(
            ("node_id_collision", group_sorted[0].file, f"{len(group)} nodes share node_id={tentative_id!r}; suffix-disambiguated")
        )
        result.append(group_sorted[0])  # first keeps bare id
        for i, n in enumerate(group_sorted[1:], start=2):
            result.append(replace(n, node_id=f"{tentative_id}#{i}"))
    result.sort(key=lambda n: (n.file, n.line_number))
    return result
```

Call this from `extract()` immediately before the return:

```python
nodes = self._disambiguate_node_ids(nodes)
```

Add `self._warnings: list[tuple[str, str, str]] = []` to `__init__`, and expose via `result.warnings = tuple(self._warnings)` or a similar surface — the inspector reads this list in 02-guidance-engine. Architectural commitment: collisions are observable.

- [ ] **Step 5: Verify GREEN**

Expected: PASS.

- [ ] **Step 6: Write the no-collision regression test**

```python
def test_extract_no_collision_no_suffix(tmp_path):
    tmp_path.joinpath("a.py").write_text("def foo():\n    pass\n")
    result = ASTExtractor().extract(tmp_path)
    assert all("#" not in n.node_id for n in result.nodes)
```

- [ ] **Step 7: Verify GREEN**

Expected: PASS.

- [ ] **Step 8: Write determinism test**

```python
def test_extract_collision_is_deterministic():
    fixture = ... # collision fixture path
    r1 = ASTExtractor().extract(fixture)
    r2 = ASTExtractor().extract(fixture)
    assert [n.node_id for n in r1.nodes] == [n.node_id for n in r2.nodes]
```

- [ ] **Step 9: Verify GREEN**

Expected: PASS.

- [ ] **Step 10: Run full unit suite**

Run: `PYTHONIOENCODING=utf-8 python -m pytest the_door/tests/unit/ -q`

Expected: all green.

- [ ] **Step 11: Commit**

```bash
git add the_door/src/the_door/core/extraction/ast_extractor.py the_door/tests/unit/core/extraction/test_ast_extractor.py the_door/tests/fixtures/sample_codebases/colliding_init/
git commit -m "fix(extraction): disambiguate colliding node_ids with #N suffix (P3)"
```

---

## Done criteria for 01-core-data

1. `pytest the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py the_door/tests/unit/core/extraction/test_versioned_structure.py the_door/tests/unit/core/extraction/test_ast_extractor.py the_door/tests/integration/test_analyze_pipeline_versioned_structure.py -q` passes.
2. `pytest the_door/tests/unit/ the_door/tests/integration/ -q` reports no regressions over the pre-task baseline.
3. Re-running `the-door analyze` on the v105 fixture creates `.the-door/structures/<vid>.json.gz` alongside the snapshot.
4. A hand-edited snapshot with drift (`source_node_count > 0, source_nodes=[]`) emits a deprecation-style warning when loaded.
5. The `colliding_init` fixture produces 3 distinct node_ids for the three `__init__` nodes when extracted.
