# version_narrative Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `version_narratives` (dict of baseline_version_id → plain-language narrative) to `VersionSnapshot`, wire it through the MCP tools and `/api/diff` endpoint, and surface it in the viewer diff mode.

**Architecture:** `version_narratives` is a dict field on `VersionSnapshot` (key = baseline UUID, value = narrative string). `snapshot_patch` and `snapshot_write` tools accept it as optional input; `snapshot_list` exposes a `narrative_summary` to guide agent scope decisions; `/api/diff` includes the narrative for the active baseline pair; the viewer diff mode renders it in a dedicated band.

**Tech Stack:** Python 3.11 dataclasses, jsonschema, pytest/asyncio (backend); vanilla JS + vitest (frontend).

**Branch:** `claude/clever-wright-01ac5f`
**pytest cwd:** `the_door/` (inner directory — all pytest commands run from there)
**PYTHONUTF8:** Prefix all pytest calls with `PYTHONUTF8=1` on Windows PowerShell.

---

## File Map

| File | Change |
|---|---|
| `the_door/src/the_door/models/snapshot.py` | Add `version_narratives` field to `VersionSnapshot` |
| `the_door/src/the_door/schemas/snapshot.schema.json` | Add `version_narratives` property |
| `the_door/src/the_door/core/diff/snapshot_store.py` | `_serialize`, `_deserialize`, `create_snapshot`, `patch_snapshot` |
| `the_door/tests/unit/core/diff/test_snapshot_contract.py` | Update `_maximal_snapshot` fixture |
| `the_door/src/the_door/mcp/tools/snapshot_patch_tool.py` | TOOL_SCHEMA + execute + payload |
| `the_door/tests/unit/mcp/test_snapshot_patch_tool.py` | New test class |
| `the_door/src/the_door/mcp/tools/snapshot_write_tool.py` | TOOL_SCHEMA + create_snapshot call + payload |
| `the_door/tests/unit/mcp/test_snapshot_write_tool.py` | New tests |
| `the_door/src/the_door/mcp/tools/snapshot_list_tool.py` | Per-entry fields + `narrative_summary` |
| `the_door/tests/unit/mcp/tools/test_snapshot_list_tool.py` | New tests |
| `the_door/src/the_door/core/ui/api/handlers/diff.py` | Add `version_narrative` to body |
| `the_door/tests/unit/core/ui/api/handlers/test_diff.py` | New tests |
| `docs/frontend-local-version-viewer/viewer/index.html` | Add `#version-narrative-band` element |
| `docs/frontend-local-version-viewer/viewer/js/ui-topbar.js` | Add `renderVersionNarrativeBand()` |
| `docs/frontend-local-version-viewer/viewer/js/layers.js` | Call render after diff loads |
| `CLAUDE.md` | Add version_narrative agent chain section |

---

## Task 1: Data model + schema + serialize/deserialize

**Files:**
- Modify: `the_door/src/the_door/models/snapshot.py`
- Modify: `the_door/src/the_door/schemas/snapshot.schema.json`
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py`
- Modify: `the_door/tests/unit/core/diff/test_snapshot_contract.py`

- [ ] **Step 1: Write failing bijection test (it will fail once schema is updated)**

  The existing `test_schema_serialize_field_bijection` test (line 76 of `test_snapshot_contract.py`) checks `set(schema["properties"]) == set(serialized_data)`. Adding `version_narratives` to the schema without updating serialize will break it.

  First, update `_maximal_snapshot()` in `test_snapshot_contract.py` to include the new field (add after `codebase_path=Path("/proj")`):

  ```python
  version_narratives={"baseline-uuid-abc": "Added authentication feature, removed legacy auth module."},
  ```

  The full `_maximal_snapshot` function after edit:
  ```python
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
          version_narratives={"baseline-uuid-abc": "Added authentication feature, removed legacy auth module."},
      )
  ```

- [ ] **Step 2: Run bijection test to confirm it passes (model field exists, schema not yet updated)**

  ```powershell
  cd the_door
  PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_contract.py::test_schema_serialize_field_bijection -v
  ```

  Expected: FAIL — `version_narratives` not in schema yet, or not in serialize output.
  (If it fails for a different reason, fix before continuing.)

- [ ] **Step 3: Add `version_narratives` field to `VersionSnapshot`**

  In `the_door/src/the_door/models/snapshot.py`, after `project_summary` (line 93):

  ```python
  version_narratives: dict[str, str] = field(default_factory=dict)
  # key   = baseline version_id (full UUID, immutable identity)
  # value = plain-language narrative written by agent
  # empty dict = no narratives yet (backward-compatible default)
  ```

  Full updated tail of `VersionSnapshot` (lines 86–94 become):
  ```python
  label: str | None = None
  l1_5_snapshot: dict[str, BlockSummary] = field(default_factory=dict)
  feature_relations_snapshot: list[RelationSummary] = field(default_factory=list)
  vulnerabilities_snapshot: list[VulnerabilityEntry] = field(default_factory=list)
  vulnerability_db_freshness: DatabaseFreshness | None = None
  codebase_path: Path | None = None
  contract_version: str | None = None
  project_summary: str | None = None
  version_narratives: dict[str, str] = field(default_factory=dict)
  ```

- [ ] **Step 4: Add `version_narratives` to schema**

  In `the_door/src/the_door/schemas/snapshot.schema.json`, after the `"project_summary"` property (line 16), add:

  ```json
  "version_narratives": {
    "type": "object",
    "description": "Map of baseline version_id (UUID) to plain-language narrative describing what changed in this version relative to that baseline. Empty object = no narratives.",
    "additionalProperties": { "type": "string" },
    "default": {}
  },
  ```

- [ ] **Step 5: Update `_serialize_snapshot` to emit `version_narratives`**

  In `snapshot_store.py`, in the `return {` dict of `_serialize_snapshot` (after `"project_summary"` line 381), add:

  ```python
  "version_narratives": dict(snapshot.version_narratives),
  ```

- [ ] **Step 6: Update `_deserialize_snapshot` to read `version_narratives`**

  In `snapshot_store.py`, in the `return VersionSnapshot(` call of `_deserialize_snapshot` (after `project_summary=data.get("project_summary"),` line 492), add:

  ```python
  version_narratives=dict(data.get("version_narratives") or {}),
  ```

  (`or {}` guards against a stored `null` JSON value; `dict()` ensures a mutable copy.)

- [ ] **Step 7: Run bijection test to verify it passes**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_contract.py -v
  ```

  Expected: ALL PASS (bijection, round-trip, validation, strict-mode tests).

- [ ] **Step 8: Run full test suite to check for regressions**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/ -x -q
  ```

  Expected: all existing tests pass.

- [ ] **Step 9: Commit**

  ```powershell
  git add the_door/src/the_door/models/snapshot.py `
         the_door/src/the_door/schemas/snapshot.schema.json `
         the_door/src/the_door/core/diff/snapshot_store.py `
         the_door/tests/unit/core/diff/test_snapshot_contract.py
  git commit -m "feat(model): add version_narratives dict field to VersionSnapshot"
  ```

---

## Task 2: `create_snapshot` + `patch_snapshot` store methods

**Files:**
- Modify: `the_door/src/the_door/core/diff/snapshot_store.py`

- [ ] **Step 1: Write failing tests for `patch_snapshot` with `version_narratives`**

  Create new file `the_door/tests/unit/core/diff/test_snapshot_patch_store.py`:

  ```python
  """Unit tests for patch_snapshot() version_narratives behaviour."""
  from __future__ import annotations

  import pytest
  from the_door.core.diff.snapshot_store import SnapshotStore


  @pytest.fixture
  def store_with_snapshot(tmp_path):
      store = SnapshotStore(tmp_path)
      store.create_snapshot(
          l1_snapshot={}, feature_relations=[], analyzed_files=[],
          trigger="manual", label="v1.0.0",
      )
      return store, tmp_path


  class TestPatchSnapshotVersionNarratives:
      def test_patch_adds_narrative_to_empty(self, store_with_snapshot):
          store, _ = store_with_snapshot
          snap, _ = store.patch_snapshot(
              version_ref="v1.0.0",
              version_narratives={"base-uuid-aaa": "Added login feature."},
          )
          assert snap.version_narratives == {"base-uuid-aaa": "Added login feature."}

      def test_patch_merges_with_existing(self, store_with_snapshot):
          store, _ = store_with_snapshot
          store.patch_snapshot(
              version_ref="v1.0.0",
              version_narratives={"base-uuid-aaa": "Added login."},
          )
          snap, _ = store.patch_snapshot(
              version_ref="v1.0.0",
              version_narratives={"base-uuid-bbb": "Added logout."},
          )
          assert snap.version_narratives == {
              "base-uuid-aaa": "Added login.",
              "base-uuid-bbb": "Added logout.",
          }

      def test_patch_overwrites_same_key(self, store_with_snapshot):
          store, _ = store_with_snapshot
          store.patch_snapshot(
              version_ref="v1.0.0",
              version_narratives={"base-uuid-aaa": "Old narrative."},
          )
          snap, _ = store.patch_snapshot(
              version_ref="v1.0.0",
              version_narratives={"base-uuid-aaa": "New narrative."},
          )
          assert snap.version_narratives["base-uuid-aaa"] == "New narrative."

      def test_patch_without_narratives_leaves_existing_untouched(self, store_with_snapshot):
          store, _ = store_with_snapshot
          store.patch_snapshot(
              version_ref="v1.0.0",
              version_narratives={"base-uuid-aaa": "Keep me."},
          )
          snap, _ = store.patch_snapshot(
              version_ref="v1.0.0",
              source_nodes_by_feature={},  # unrelated patch, no version_narratives
          )
          assert snap.version_narratives == {"base-uuid-aaa": "Keep me."}

      def test_narratives_persisted_to_disk_and_read_back(self, store_with_snapshot):
          store, tmp_path = store_with_snapshot
          store.patch_snapshot(
              version_ref="v1.0.0",
              version_narratives={"base-uuid-aaa": "Persisted narrative."},
          )
          store2 = SnapshotStore(tmp_path)
          snap = store2.resolve_baseline("v1.0.0")
          assert snap.version_narratives == {"base-uuid-aaa": "Persisted narrative."}
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_patch_store.py -v
  ```

  Expected: FAIL — `patch_snapshot()` does not accept `version_narratives` keyword.

- [ ] **Step 3: Update `create_snapshot` to accept and store `version_narratives`**

  In `snapshot_store.py`, add `version_narratives` parameter to `create_snapshot` (after `project_summary` on line 106):

  ```python
  version_narratives: dict[str, str] | None = None,
  ```

  And in the `VersionSnapshot(...)` constructor call (after `project_summary=project_summary,`):

  ```python
  version_narratives=dict(version_narratives) if version_narratives else {},
  ```

- [ ] **Step 4: Update `patch_snapshot` to accept and merge `version_narratives`**

  In `snapshot_store.py`, add `version_narratives` parameter to `patch_snapshot` signature (after `feature_metadata_by_feature` on line 206):

  ```python
  version_narratives: dict[str, str] | None = None,
  ```

  And in the `snap_kwargs` block (before `snap = dataclasses.replace(snap, **snap_kwargs)` on line 252), add:

  ```python
  if version_narratives:
      merged_narratives = {**snap.version_narratives, **version_narratives}
      snap_kwargs["version_narratives"] = merged_narratives
  ```

- [ ] **Step 5: Run tests to confirm they pass**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_patch_store.py -v
  ```

  Expected: ALL 5 PASS.

- [ ] **Step 6: Run full suite**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/ -x -q
  ```

  Expected: all pass.

- [ ] **Step 7: Commit**

  ```powershell
  git add the_door/src/the_door/core/diff/snapshot_store.py `
         the_door/tests/unit/core/diff/test_snapshot_patch_store.py
  git commit -m "feat(store): patch_snapshot and create_snapshot accept version_narratives"
  ```

---

## Task 3: `snapshot_patch` MCP tool

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/snapshot_patch_tool.py`
- Modify: `the_door/tests/unit/mcp/test_snapshot_patch_tool.py`

- [ ] **Step 1: Write failing tests**

  Add new test class to `the_door/tests/unit/mcp/test_snapshot_patch_tool.py` (after existing classes):

  ```python
  class TestSnapshotPatchToolVersionNarratives:
      def test_patch_narratives_returned_in_payload(self, seeded_project):
          import asyncio
          result = asyncio.run(snapshot_patch_tool.execute({
              "codebase_path": str(seeded_project),
              "version_ref": "v1.0.0",
              "version_narratives": {"base-uuid-111": "Added CLI dispatch."},
          }))
          assert result["version_narratives"] == {"base-uuid-111": "Added CLI dispatch."}

      def test_patch_merges_narratives_across_calls(self, seeded_project):
          import asyncio
          asyncio.run(snapshot_patch_tool.execute({
              "codebase_path": str(seeded_project),
              "version_ref": "v1.0.0",
              "version_narratives": {"base-uuid-111": "First narrative."},
          }))
          result = asyncio.run(snapshot_patch_tool.execute({
              "codebase_path": str(seeded_project),
              "version_ref": "v1.0.0",
              "version_narratives": {"base-uuid-222": "Second narrative."},
          }))
          assert "base-uuid-111" in result["version_narratives"]
          assert "base-uuid-222" in result["version_narratives"]
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_patch_tool.py::TestSnapshotPatchToolVersionNarratives -v
  ```

  Expected: FAIL — `version_narratives` not in payload.

- [ ] **Step 3: Update `snapshot_patch_tool.py`**

  **TOOL_SCHEMA** — add after `"analyzed_files"` property (before closing `}`):

  ```python
  "version_narratives": {
      "type": "object",
      "description": (
          "Optional. Map of baseline_version_id (UUID) → narrative string. "
          "Merge-write: provided keys overwrite existing values, absent keys are preserved. "
          "Obtain baseline version_id from snapshot_list output (version_id field). "
          "Do not use label as key — labels are mutable, version_id is permanent."
      ),
      "additionalProperties": {"type": "string"},
  },
  ```

  **`execute()` function** — add after line 64 (`store = SnapshotStore(...)`), before `try:`:

  ```python
  version_narratives = arguments.get("version_narratives") or {}
  ```

  **`store.patch_snapshot()` call** — add `version_narratives=version_narratives` argument:

  ```python
  snap, skipped = store.patch_snapshot(
      version_ref=arguments["version_ref"],
      source_nodes_by_feature=arguments.get("source_nodes_by_feature") or {},
      analyzed_files=arguments.get("analyzed_files"),
      feature_metadata_by_feature=arguments.get("feature_metadata_by_feature"),
      version_narratives=version_narratives,
  )
  ```

  **`payload` dict** — add after `"skipped_features"`:

  ```python
  "version_narratives": dict(snap.version_narratives),
  ```

- [ ] **Step 4: Run tests to confirm they pass**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_patch_tool.py -v
  ```

  Expected: ALL PASS (existing + new).

- [ ] **Step 5: Run full suite**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/ -x -q
  ```

  Expected: all pass.

- [ ] **Step 6: Commit**

  ```powershell
  git add the_door/src/the_door/mcp/tools/snapshot_patch_tool.py `
         the_door/tests/unit/mcp/test_snapshot_patch_tool.py
  git commit -m "feat(mcp): snapshot_patch accepts and returns version_narratives"
  ```

---

## Task 4: `snapshot_write` MCP tool

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/snapshot_write_tool.py`
- Modify: `the_door/tests/unit/mcp/test_snapshot_write_tool.py`

- [ ] **Step 1: Write failing tests**

  Add new test class to `the_door/tests/unit/mcp/test_snapshot_write_tool.py` after existing classes.
  The file uses `@pytest.mark.asyncio` + `async def`. `tmp_project` fixture = bare `tmp_path`.
  `VALID_FEATURES` and `_load_snapshot_by_vid` are already defined at module level in the file.

  ```python
  class TestSnapshotWriteToolVersionNarratives:
      @pytest.mark.asyncio
      async def test_version_narratives_persisted_and_returned(self, tmp_project):
          from the_door.mcp.tools.snapshot_write_tool import execute
          result = await execute({
              "codebase_path": str(tmp_project),
              "l1_features": VALID_FEATURES,
              "version_narratives": {"base-uuid-111": "Added auth feature."},
          })
          assert result["version_narratives"] == {"base-uuid-111": "Added auth feature."}
          loaded = _load_snapshot_by_vid(tmp_project, result["version_id"])
          assert loaded.version_narratives == {"base-uuid-111": "Added auth feature."}

      @pytest.mark.asyncio
      async def test_version_narratives_defaults_empty_when_omitted(self, tmp_project):
          from the_door.mcp.tools.snapshot_write_tool import execute
          result = await execute({
              "codebase_path": str(tmp_project),
              "l1_features": VALID_FEATURES,
          })
          assert result["version_narratives"] == {}
          loaded = _load_snapshot_by_vid(tmp_project, result["version_id"])
          assert loaded.version_narratives == {}
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_write_tool.py::TestSnapshotWriteToolVersionNarratives -v
  ```

  Expected: FAIL.

- [ ] **Step 3: Update `snapshot_write_tool.py`**

  **TOOL_SCHEMA** — add after `"project_summary"` property (around line 120):

  ```python
  "version_narratives": {
      "type": "object",
      "description": (
          "Optional. Map of baseline_version_id (UUID) → plain-language narrative "
          "describing what changed in this version relative to that baseline. "
          "Not inherited from baseline even in inherit_from mode — each version's "
          "narratives describe transitions FROM a specific baseline TO this version. "
          "Obtain baseline version_id from snapshot_list (version_id field)."
      ),
      "additionalProperties": {"type": "string"},
  },
  ```

  **In `execute()` function** — add after `arg_summary = arguments.get("project_summary")` (line 198):

  ```python
  arg_narratives = dict(arguments.get("version_narratives") or {})
  ```

  **`store.create_snapshot()` call** (line 324) — add `version_narratives=arg_narratives`:

  ```python
  snapshot = store.create_snapshot(
      l1_snapshot=l1_snapshot,
      feature_relations=relations,
      analyzed_files=analyzed_files,
      commit_hash=commit_hash,
      git_tags=git_tags if git_tags else [],
      trigger="manual",
      label=label,
      project_summary=project_summary,
      version_narratives=arg_narratives,
  )
  ```

  **`payload` dict** (line 338) — add after `"relation_count"`:

  ```python
  "version_narratives": dict(snapshot.version_narratives),
  ```

- [ ] **Step 4: Run tests to confirm they pass**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_snapshot_write_tool.py -v
  ```

  Expected: ALL PASS.

- [ ] **Step 5: Run full suite**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/ -x -q
  ```

  Expected: all pass.

- [ ] **Step 6: Commit**

  ```powershell
  git add the_door/src/the_door/mcp/tools/snapshot_write_tool.py `
         the_door/tests/unit/mcp/test_snapshot_write_tool.py
  git commit -m "feat(mcp): snapshot_write accepts version_narratives and returns it in payload"
  ```

---

## Task 5: `snapshot_list` MCP tool

**Files:**
- Modify: `the_door/src/the_door/mcp/tools/snapshot_list_tool.py`
- Modify: `the_door/tests/unit/mcp/tools/test_snapshot_list_tool.py`

- [ ] **Step 1: Write failing tests**

  Add to `the_door/tests/unit/mcp/tools/test_snapshot_list_tool.py`:

  ```python
  class TestSnapshotListNarrativeFields:
      @pytest.fixture
      def project_with_narratives(self, tmp_path):
          store = SnapshotStore(tmp_path)
          s1 = store.create_snapshot(
              l1_snapshot={}, feature_relations=[], analyzed_files=[],
              trigger="manual", label="v1",
          )
          s2 = store.create_snapshot(
              l1_snapshot={}, feature_relations=[], analyzed_files=[],
              trigger="manual", label="v2",
              version_narratives={s1.version_id: "Added feature A."},
          )
          return tmp_path, s1, s2

      def test_has_version_narrative_false_when_empty(self, tmp_path):
          store = SnapshotStore(tmp_path)
          store.create_snapshot(
              l1_snapshot={}, feature_relations=[], analyzed_files=[],
              trigger="manual", label="v1",
          )
          result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
          assert result["snapshots"][0]["has_version_narrative"] is False

      def test_has_version_narrative_true_when_nonempty(self, project_with_narratives):
          tmp_path, s1, s2 = project_with_narratives
          result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
          snaps = {s["label"]: s for s in result["snapshots"]}
          assert snaps["v2"]["has_version_narrative"] is True
          assert snaps["v1"]["has_version_narrative"] is False

      def test_narrative_baselines_lists_keys(self, project_with_narratives):
          tmp_path, s1, s2 = project_with_narratives
          result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
          snaps = {s["label"]: s for s in result["snapshots"]}
          assert s1.version_id in snaps["v2"]["narrative_baselines"]
          assert snaps["v1"]["narrative_baselines"] == []

      def test_narrative_summary_counts(self, project_with_narratives):
          tmp_path, s1, s2 = project_with_narratives
          result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
          ns = result["narrative_summary"]
          assert ns["total"] == 2
          assert ns["has_narrative"] == 1
          assert ns["missing_narrative"] == 1

      def test_narrative_summary_note_present(self, project_with_narratives):
          tmp_path, _, _ = project_with_narratives
          result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
          assert "note" in result["narrative_summary"]
          assert isinstance(result["narrative_summary"]["note"], str)

      def test_narrative_summary_all_present_note(self, tmp_path):
          store = SnapshotStore(tmp_path)
          s1 = store.create_snapshot(
              l1_snapshot={}, feature_relations=[], analyzed_files=[],
              trigger="manual", label="v1",
          )
          store.create_snapshot(
              l1_snapshot={}, feature_relations=[], analyzed_files=[],
              trigger="manual", label="v2",
              version_narratives={s1.version_id: "Some narrative."},
          )
          store.patch_snapshot("v1", version_narratives={s1.version_id: "Also narrative."})
          result = asyncio.run(snapshot_list_tool.execute({"codebase_path": str(tmp_path)}))
          ns = result["narrative_summary"]
          assert ns["missing_narrative"] == 0
  ```

  Also add `import asyncio` at the top of the test file if not already present.

- [ ] **Step 2: Run tests to confirm they fail**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/mcp/tools/test_snapshot_list_tool.py::TestSnapshotListNarrativeFields -v
  ```

  Expected: FAIL — `has_version_narrative`, `narrative_baselines`, `narrative_summary` not in output.

- [ ] **Step 3: Update `snapshot_list_tool.py`**

  Replace the full file content:

  ```python
  """MCP tool: snapshot_list — list all available snapshots."""
  from __future__ import annotations

  TOOL_SCHEMA = {
      "type": "object",
      "required": ["codebase_path"],
      "properties": {
          "codebase_path": {"type": "string", "description": "Path to the codebase root"},
      },
  }


  async def execute(arguments: dict) -> dict:
      """Execute the snapshot_list tool."""
      from pathlib import Path
      from the_door.core.diff.snapshot_store import SnapshotStore
      from the_door.core.diff.provenance_membrane import provenance_element_for
      from the_door.mcp.tools._response_envelope import wrap

      codebase_path = arguments["codebase_path"]
      project_root = Path(arguments.get("codebase_path") or arguments.get("project_path") or Path.cwd())
      store = SnapshotStore(Path(codebase_path))
      snapshots = store.list_snapshots()

      missing = sum(1 for s in snapshots if not s.version_narratives)
      has_narrative = len(snapshots) - missing

      if missing > 0:
          note = (
              f"{missing} 個 snapshot 缺少 version_narrative。"
              "寫入前請向使用者確認要翻譯的 baseline-current 配對，不得自行決定範圍。"
          )
      else:
          note = "所有 snapshot 均已有 version_narrative。"

      return wrap({
          "snapshots": [
              {
                  "version_id": s.version_id,
                  "timestamp": s.timestamp,
                  "trigger": s.trigger,
                  "commit_hash": s.commit_hash,
                  "git_tags": s.git_tags,
                  "label": s.label,
                  "provenance": provenance_element_for(s.contract_version).to_json(),
                  "has_version_narrative": bool(s.version_narratives),
                  "narrative_baselines": list(s.version_narratives.keys()),
              }
              for s in snapshots
          ],
          "narrative_summary": {
              "total": len(snapshots),
              "has_narrative": has_narrative,
              "missing_narrative": missing,
              "note": note,
          },
      }, project_path=project_root, context="mcp")
  ```

- [ ] **Step 4: Run tests to confirm they pass**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/mcp/tools/test_snapshot_list_tool.py -v
  ```

  Expected: ALL PASS.

- [ ] **Step 5: Run full suite**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/ -x -q
  ```

  Expected: all pass.

- [ ] **Step 6: Commit**

  ```powershell
  git add the_door/src/the_door/mcp/tools/snapshot_list_tool.py `
         the_door/tests/unit/mcp/tools/test_snapshot_list_tool.py
  git commit -m "feat(mcp): snapshot_list exposes has_version_narrative, narrative_baselines, narrative_summary"
  ```

---

## Task 6: `/api/diff` endpoint

**Files:**
- Modify: `the_door/src/the_door/core/ui/api/handlers/diff.py`
- Modify: `the_door/tests/unit/core/ui/api/handlers/test_diff.py`

- [ ] **Step 1: Write failing tests**

  In `the_door/tests/unit/core/ui/api/handlers/test_diff.py`, add to `TestVersions` class:

  ```python
  def test_diff_includes_version_narrative_when_present(self, tmp_path):
      h = DiffHandlers(_ctx(tmp_path))
      baseline_snap = MagicMock()
      baseline_snap.version_id = "vid-baseline"
      baseline_snap.label = "v0"
      current_snap = MagicMock()
      current_snap.version_id = "vid-current"
      current_snap.label = "v1"
      current_snap.version_narratives = {"vid-baseline": "Added auth feature."}
      diff_result = MagicMock()
      diff_result.node_diffs = []
      diff_result.summary.added_count = 1
      diff_result.summary.removed_count = 0
      diff_result.summary.attribute_changed_count = 0
      diff_result.summary.dependency_changed_count = 0
      diff_result.summary.total_changed_count = 1
      with (
          patch("the_door.core.ui.api.handlers.diff.SnapshotStore") as mock_ss,
          patch("the_door.core.ui.api.handlers.diff.DiffEngine") as mock_de,
          patch("the_door.core.ui.api.handlers.diff.StateInspector") as mock_si,
          patch("the_door.core.ui.api.handlers.diff.NextActionSuggester") as mock_nas,
      ):
          mock_ss.return_value.resolve_baseline.side_effect = [baseline_snap, current_snap]
          mock_de.return_value.compute_l1_diff.return_value = diff_result
          mock_si.return_value.inspect.return_value = MagicMock()
          mock_nas.return_value.suggest.return_value = []
          status, body = h.versions(baseline="v0", current="v1")
      assert status == 200
      assert body["version_narrative"] == "Added auth feature."

  def test_diff_version_narrative_null_when_absent(self, tmp_path):
      h = DiffHandlers(_ctx(tmp_path))
      baseline_snap = MagicMock()
      baseline_snap.version_id = "vid-baseline"
      baseline_snap.label = "v0"
      current_snap = MagicMock()
      current_snap.version_id = "vid-current"
      current_snap.label = "v1"
      current_snap.version_narratives = {}
      diff_result = MagicMock()
      diff_result.node_diffs = []
      diff_result.summary.added_count = 0
      diff_result.summary.removed_count = 0
      diff_result.summary.attribute_changed_count = 0
      diff_result.summary.dependency_changed_count = 0
      diff_result.summary.total_changed_count = 0
      with (
          patch("the_door.core.ui.api.handlers.diff.SnapshotStore") as mock_ss,
          patch("the_door.core.ui.api.handlers.diff.DiffEngine") as mock_de,
          patch("the_door.core.ui.api.handlers.diff.StateInspector") as mock_si,
          patch("the_door.core.ui.api.handlers.diff.NextActionSuggester") as mock_nas,
      ):
          mock_ss.return_value.resolve_baseline.side_effect = [baseline_snap, current_snap]
          mock_de.return_value.compute_l1_diff.return_value = diff_result
          mock_si.return_value.inspect.return_value = MagicMock()
          mock_nas.return_value.suggest.return_value = []
          status, body = h.versions(baseline="v0", current="v1")
      assert status == 200
      assert body["version_narrative"] is None
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/core/ui/api/handlers/test_diff.py::TestVersions::test_diff_includes_version_narrative_when_present tests/unit/core/ui/api/handlers/test_diff.py::TestVersions::test_diff_version_narrative_null_when_absent -v
  ```

  Expected: FAIL — `version_narrative` not in body.

- [ ] **Step 3: Update `handlers/diff.py`**

  In `DiffHandlers.versions()`, after the `body = { ... }` dict is assembled (after line 108 `body["next_actions"] = ...`), add:

  ```python
  # Attach narrative if current snapshot has one for this baseline pair.
  body["version_narrative"] = current_snap.version_narratives.get(baseline_snap.version_id)
  ```

  Insert this line **after** `body["next_actions"] = [action_to_json(a) for a in actions]` and **before** `return 200, body`.

- [ ] **Step 4: Run tests to confirm they pass**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/unit/core/ui/api/handlers/test_diff.py -v
  ```

  Expected: ALL PASS.

- [ ] **Step 5: Run full suite**

  ```powershell
  PYTHONUTF8=1 python -m pytest tests/ -x -q
  ```

  Expected: all pass.

- [ ] **Step 6: Commit**

  ```powershell
  git add the_door/src/the_door/core/ui/api/handlers/diff.py `
         the_door/tests/unit/core/ui/api/handlers/test_diff.py
  git commit -m "feat(api): /api/diff response includes version_narrative when available"
  ```

---

## Task 7: Frontend — viewer diff mode narrative band

**Files:**
- Modify: `docs/frontend-local-version-viewer/viewer/index.html`
- Modify: `docs/frontend-local-version-viewer/viewer/js/ui-topbar.js`
- Modify: `docs/frontend-local-version-viewer/viewer/js/layers.js`

**Note:** All frontend files are in `docs/frontend-local-version-viewer/viewer/` (唯一正式版). Do NOT touch `prototype/`.

- [ ] **Step 1: Add `#version-narrative-band` element to `index.html`**

  Locate the diff summary section in `index.html`. Look for the element that shows diff counts (added/removed/changed numbers). Add the narrative band immediately after it:

  ```html
  <div id="version-narrative-band" hidden class="narrative-band"></div>
  ```

  To find the right location: search for `diff` or `summary` in `index.html` to identify the diff mode summary area. The narrative band goes after the diff statistics block and before any feature list.

- [ ] **Step 2: Add `renderVersionNarrativeBand()` to `ui-topbar.js`**

  Add this function to `docs/frontend-local-version-viewer/viewer/js/ui-topbar.js`. Add it as an exported function at the end of the file (or near other render functions):

  ```javascript
  export function renderVersionNarrativeBand(diff) {
    const el = document.getElementById("version-narrative-band");
    if (!el) return;
    const narrative = diff?.version_narrative ?? null;
    if (narrative) {
      el.textContent = narrative;
      el.hidden = false;
    } else {
      el.hidden = true;
    }
  }
  ```

  Behavior:
  - `diff` is the `/api/diff` response object (from `state.versionDiff`).
  - `version_narrative` is `string | null` — null when the current snapshot has no narrative for this baseline.
  - `hidden = true` when null: absence is honest, no fallback placeholder text.
  - Uses `textContent` (not `innerHTML`) — narrative is agent-written plain text, not HTML.

- [ ] **Step 3: Call `renderVersionNarrativeBand` from `layers.js`**

  In `docs/frontend-local-version-viewer/viewer/js/layers.js`:

  1. Import the new function at the top (alongside other imports from `ui-topbar.js`):
     ```javascript
     import { ..., renderVersionNarrativeBand } from "./ui-topbar.js";
     ```
     (Add `renderVersionNarrativeBand` to the existing import from `ui-topbar.js`.)

  2. In `loadDiffOverlay()`, after `state.versionDiff = data;` and before the function returns, add:
     ```javascript
     renderVersionNarrativeBand(data);
     ```

  3. Also handle the case where diff is cleared (e.g. when switching back to single-version mode). Find where `state.versionDiff` is reset to null and add:
     ```javascript
     renderVersionNarrativeBand(null);
     ```

- [ ] **Step 4: Run frontend tests**

  ```powershell
  cd docs/frontend-local-version-viewer/viewer
  npx vitest run
  ```

  Expected: existing tests pass. If there are existing `ui-topbar` tests, they should still pass. If there are no tests for `renderVersionNarrativeBand`, that is acceptable — the function is simple enough to verify manually.

- [ ] **Step 5: Manual smoke test with the local server**

  Start the server against a test target that has at least two snapshots:

  ```powershell
  the-door ui "C:\Users\Ric\Desktop\test-targets\the-door-v170" --no-browser --port 8765
  ```

  - Open `http://localhost:8765` in browser.
  - Select two versions in the diff mode selectors.
  - Verify: if no narrative exists, narrative band is hidden (not shown).
  - Patch a narrative onto a snapshot via `snapshot_patch` MCP tool with `version_narratives`.
  - Reload the diff view.
  - Verify: narrative band appears with the text.

- [ ] **Step 6: Commit**

  ```powershell
  git add docs/frontend-local-version-viewer/viewer/index.html `
         docs/frontend-local-version-viewer/viewer/js/ui-topbar.js `
         docs/frontend-local-version-viewer/viewer/js/layers.js
  git commit -m "feat(viewer): diff mode narrative band shows version_narrative from /api/diff"
  ```

---

## Task 8: CLAUDE.md agent chain update

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add version_narrative chain section to CLAUDE.md**

  In `CLAUDE.md`, locate the section `### Agent-as-LLM chain (incremental update)`. Add a new section immediately after it:

  ````markdown
  ### Agent-as-LLM chain (version_narrative)

  `version_narrative` 是 diff 層產物：描述「這個版本相比 baseline 做了什麼」的白話敘述，
  由 agent 自己讀 diff 資料後撰寫，持久化進 current snapshot。

  **前置要求（重要）**：先 `snapshot_list`，向使用者聲明預計翻譯的 baseline-current 配對，
  收到確認後才執行。`narrative_summary.note` 明示此規則。不得自行決定範圍。

  1. `snapshot_list(codebase_path="./my-project")`
     → 讀 `narrative_summary`（缺口數量 + note）與各筆 `has_version_narrative`
     → **向使用者呈現缺口，詢問「要補哪幾對？」，等待明確回覆**

  2. 對每個確認的 (baseline=vX, current=vY) pair：

     a. `analyze_changes(codebase_path="./my-project", baseline="vX")`
        → 取得 `affected_features`（增/改/刪）＋`inherited_features`（不動）
        → 注意取回的 `baseline_version_id`（UUID）——這是下一步 `version_narratives` 的 key

     b. 你自己寫白話敘述（1–4 句），重點：
        - 說清楚「加了什麼、改了什麼、拿掉了什麼」（來自 affected_features）
        - 面向非技術讀者
        - **只能使用 diff 資料（affected/inherited features + summary）的資訊，不引入 snapshot 以外的描述**
        - `affected_features` 全空（純繼承版本，無 feature 變動）→ 省略 narrative，不強制寫

     c. `snapshot_patch(codebase_path="./my-project",
                        version_ref="vY",
                        version_narratives={"<baseline_version_id UUID>": "..."})`
        → `version_narratives` 的 key **必須是 `analyze_changes` 回傳的 `baseline_version_id`（UUID）**
        → 不得使用 label（label 可改寫，UUID 是永久身分）

  3. 驗證（optional）：`GET /api/diff?baseline=vX&current=vY`，確認 `"version_narrative"` 欄非 null。
  ````

- [ ] **Step 2: Verify CLAUDE.md renders correctly (quick visual check)**

  ```powershell
  # Check the section was added (just confirm no syntax errors)
  python -c "
  with open('CLAUDE.md', encoding='utf-8') as f:
      content = f.read()
  assert 'version_narrative' in content
  assert 'narrative_summary' in content
  assert 'baseline_version_id' in content
  print('CLAUDE.md looks good')
  "
  ```

  Expected: prints `CLAUDE.md looks good`.

- [ ] **Step 3: Commit**

  ```powershell
  git add CLAUDE.md
  git commit -m "docs(claude): add version_narrative agent-as-LLM chain to CLAUDE.md"
  ```

---

## Final verification

- [ ] **Run full test suite one last time**

  ```powershell
  cd the_door
  PYTHONUTF8=1 python -m pytest tests/ -q
  ```

  Expected: all tests pass, 0 failures.

- [ ] **Run frontend tests**

  ```powershell
  cd docs/frontend-local-version-viewer/viewer
  npx vitest run
  ```

  Expected: all pass.

- [ ] **Check git log**

  ```powershell
  git log --oneline -8
  ```

  Expected: 8 commits visible (Tasks 1–8, one per task).
