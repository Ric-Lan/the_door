# Design — Incremental Analysis & Snapshot Hygiene

## Overview

This spec lands as **two independent tracks** to limit blast radius:

```
Track A — Incremental Analysis (R1, blocked by R2 + R3)
  ├── R2  Per-version structure persistence  ──┐
  └── R3  Source-nodes invariant              ──┼──▶ R1  Incremental entry
                                                ┘
Track B — Independent improvements
  ├── R4  Diff API label resolution                       (standalone)
  ├── R5  Node_id uniqueness                              (standalone)
  ├── R6  Detail-panel notes + diff-explanation wiring    (standalone, viewer)
  └── R7  Mindmap reads snapshot-comparison diff          (standalone, viewer)
```

Within Track A, R2 and R3 are independent of each other and can land in either order, but R1 must come after both. Track B items are all independent of Track A and of each other.

All design decisions below were filtered through: clean code, TDD, no logic bugs, no hallucination, no resource waste, no over-design.

## Track A — Incremental Analysis

### R3 — Source-Nodes Invariant

**Approach: B-2 (single source of truth, deprecate-in-place)**

Rejected alternatives:
- **B-1 (delete field entirely)**: ~16 files of churn (5 src + 7 tests + schema + 3 scripts + docs + legacy deserializer), no functional gain over B-2.
- **B-3 (strict assert)**: turns existing hand-edited drift into hard crashes; doesn't fix the bug, just makes it louder.

#### Changes

| File | Change |
|---|---|
| [snapshot_store.py:170](the_door/src/the_door/core/diff/snapshot_store.py:170) | Serialization: write `source_node_count = len(fs.source_nodes)` regardless of `fs.source_node_count` value. The field becomes derived-on-write. |
| [snapshot_store.py:237](the_door/src/the_door/core/diff/snapshot_store.py:237) | Deserialization: when `fdata["source_node_count"] > 0` and `fdata.get("source_nodes")` is empty/absent, log warning naming snapshot file + feature_id, then construct with `source_node_count=0, source_nodes=()`. |
| [snapshot_write_tool.py:33](the_door/src/the_door/mcp/tools/snapshot_write_tool.py:33) | Drop `source_node_count` from `required` list. |
| [snapshot_write_tool.py:109](the_door/src/the_door/mcp/tools/snapshot_write_tool.py:109) | Always compute `source_node_count=len(source_nodes)`; ignore caller value if supplied. |
| [timeline_renderer.py:267](the_door/src/the_door/core/timeline/timeline_renderer.py:267) | Read `len(feature.source_nodes)` instead of `feature.source_node_count`. |

Untouched (by design): `models.py:360` field definition, all 7 test files, JSON schema, integration scripts, docs. Tests will still set `source_node_count` and it will still round-trip — the value just gets overwritten on write to match `len(source_nodes)`. No test should fail except those (if any) that intentionally exercise drift.

#### Test plan (TDD)

| RED | Behavior |
|---|---|
| 1 | `create_snapshot` with `FeatureSummary(source_node_count=99, source_nodes=("a","b"))` → on-disk JSON has `"source_node_count": 2`. |
| 2 | Deserialize a hand-crafted JSON with `source_node_count=5, source_nodes=[]` → returns `FeatureSummary(source_node_count=0, source_nodes=())` AND `caplog` captures a warning matching the snapshot file + feature_id. |
| 3 | `snapshot_write` MCP tool called without `source_node_count` in the feature dict → succeeds; resulting snapshot has `source_node_count == len(source_nodes)`. |
| 4 | `timeline_renderer` text output for a feature with `source_nodes=("a","b","c")` contains `"Source Nodes: 3"` regardless of the in-memory `source_node_count` value. |

---

### R2 — Per-Version Structure Persistence

**Approach: gzipped sibling under `.the-door/structures/`, no manifest**

Rejected alternatives:
- **Separate manifest.json**: duplicates data already in `snapshots/<vid>.json` (`label`, `git_tags`, `commit_hash`, `timestamp`, `analyzed_files`). DRY violation, drift risk.
- **Uncompressed**: 1.8 MB × N versions. Gzip brings this to ~200 KB with one stdlib call, zero new dependencies.
- **Per-version `structure.json` instead of `structure.json.gz`**: trades 9× disk for negligible (these are machine-only files, never human-edited).

#### File layout

```
.the-door/
├── snapshots/
│   └── <vid>.json
├── structures/                  # NEW
│   └── <vid>.json.gz            # NEW: gzipped StructureJSON
├── structure.json               # unchanged: latest-extraction convenience pointer
└── fingerprints/
    └── <vid>.json
```

#### Changes

| File | Change |
|---|---|
| `core/extraction/structure_serializer.py` | Add `write_versioned_structure(codebase_path, version_id, structure_json, scan_result)` that writes `structures/<vid>.json.gz`. Use `gzip.open(..., 'wt', encoding='utf-8')` + `json.dump(...)`. |
| `core/diff/snapshot_store.py` | Add `get_structure(version_id) -> StructureJSON \| None`: load `structures/<vid>.json.gz`, decompress, parse. Return `None` if file missing. Catch `gzip.BadGzipFile / json.JSONDecodeError`, log warning, return `None`. |
| `core/diff/snapshot_store.py` | Add `list_analyzed_versions() -> list[dict]`: iterate `snapshots/*.json`, parse minimally (just `version_id` + `label` + `git_tags`), check `structures/<vid>.json.gz` exists, return `[{version_id, label, git_tags, has_structure: bool}, ...]` sorted by snapshot timestamp desc. |
| [analyze_pipeline.py:152-154](the_door/src/the_door/core/pipeline/analyze_pipeline.py:152) | After writing `structure.json`, also call `write_versioned_structure` with the new snapshot's `version_id`. Order matters: snapshot creation at line ~310 produces the `version_id`, so the versioned write should move to after `_create_auto_snapshot` returns, or accept the snapshot's vid as input. |

#### Test plan (TDD)

| RED | Behavior |
|---|---|
| 1 | After `run_analyze_pipeline` completes, `.the-door/structures/<new_vid>.json.gz` exists and decompresses to a `StructureJSON` matching the in-memory extraction. |
| 2 | `SnapshotStore.get_structure(<unknown_vid>)` returns `None`. |
| 3 | `SnapshotStore.get_structure(<valid_vid>)` returns a `StructureJSON` with the same `nodes`, `edges`, `files`, `topology` as the persisted file. |
| 4 | `SnapshotStore.get_structure(<vid>)` where the file is truncated gzip → returns `None`, logs warning, does not raise. |
| 5 | `SnapshotStore.list_analyzed_versions()` on a directory with 2 snapshots and 1 corresponding structure → returns 2 entries, one with `has_structure: True`, one with `has_structure: False`. |
| 6 | `list_analyzed_versions()` ordering: most recent timestamp first. |

---

### R1 — Incremental Analysis Entry

**Approach: one pure function + extend existing tool/CLI surfaces**

Rejected alternatives:
- **New CLI command `the-door analyze --inherit-from`**: conceptually overlaps with `the-door update` (both produce "new version analysis informed by an older one"). Choose extension over duplication.
- **Two MCP tools `prepare_incremental_diff` + `snapshot_write_incremental`**: same logic can ride on existing `snapshot_write` with optional params + one read-only sibling tool. Two-tool design forces agents through a rigid two-step dance for no functional gain.

#### Core data structure

```python
# core/diff/feature_attribution.py — NEW FILE

@dataclass(frozen=True)
class NodeDelta:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    modified: tuple[str, ...]  # signature-changed: name same, params/return/decorators/docstring differ

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
    inherited_features: tuple[FeatureSummary, ...]  # untouched, ready to carry forward
    affected_features: tuple[AffectedFeature, ...]   # LLM/agent must update these
    unmapped_nodes: NodeDelta                        # nodes in AST diff not claimed by any feature
```

#### Pure function

```python
# core/diff/feature_attribution.py

def compute_affected_features(
    baseline_structure: StructureJSON,
    current_structure: StructureJSON,
    baseline: VersionSnapshot,
) -> IncrementalDiff:
    """Pure: no I/O, no LLM. Deterministic given inputs."""
```

Algorithm:
1. Build `baseline_nodes = {node_id: signature_hash}` from `baseline_structure.nodes`. Signature = `(name, parameters, return_type, decorators, docstring)`.
2. Build `current_nodes` similarly.
3. `added = current_nodes.keys() - baseline_nodes.keys()`
4. `removed = baseline_nodes.keys() - current_nodes.keys()`
5. `modified = {k for k in common if baseline[k] != current[k]}`
6. For each feature `fs` in `baseline.l1_snapshot.values()`:
   - `owned = set(fs.source_nodes)`
   - `feature_delta = NodeDelta(added & owned, removed & owned, modified & owned)`
   - If any of the three sets non-empty → `AffectedFeature`; else inherit verbatim.
7. `unmapped` = AST diff nodes not in any feature's `source_nodes`.

This function is the entire intellectual content of R1; everything else is wiring.

#### Wiring

| Surface | Change |
|---|---|
| MCP tool: NEW `analyze_changes` | Inputs: `codebase_path`, `baseline` (label/tag/sha/date/vid). Steps: (1) `SnapshotStore.resolve_baseline(baseline)`, (2) `get_structure(baseline.version_id)` — fail with actionable error if missing per R2 AC2, (3) `ASTExtractor.extract(codebase_path)` → current structure, (4) `compute_affected_features(...)`, (5) serialize `IncrementalDiff` to JSON. |
| MCP tool: EXTEND `snapshot_write` | Add optional `inherit_from: str` (baseline ref) + `updated_features: list[FeatureDict]` (subset). When both present: load baseline, replace features whose `feature_id` appears in `updated_features`, carry the rest verbatim. When absent: existing behavior unchanged. |
| CLI: EXTEND `update_cmd` | Add `--from-snapshot <ref>` flag. When supplied: load baseline structure via `get_structure`, skip the `old_path` AST extraction, run the rest of the pipeline against current new_path. Mutually exclusive with positional `old_path`. |
| `incremental_pipeline.py` (NEW) | Thin orchestrator wired by both the MCP tool and the CLI. Pure functions where possible; I/O at the edges. |
| `CLAUDE.md` | Add a third Mode B subsection: "Mode B — Incremental analysis (with baseline)". Document the two-MCP-call flow: `analyze_changes` → agent updates affected → `snapshot_write` with `inherit_from`. |

#### Test plan (TDD)

| RED | Behavior |
|---|---|
| 1 | `compute_affected_features` with identical baseline and current structures → `affected_features=()`, `inherited_features` has all baseline features, `unmapped_nodes` is empty. |
| 2 | Add one node whose `node_id` is in `feat-x`'s `source_nodes` → `affected_features` contains `feat-x` with `delta.added == (node_id,)`; `inherited_features` excludes `feat-x`. |
| 3 | Remove one node from `feat-y`'s `source_nodes` → `feat-y` in `affected_features` with `delta.removed`; `feat-y.source_nodes` reflects the post-removal set. |
| 4 | Modify a node's signature (params change) that belongs to `feat-z` → `feat-z` in `affected_features` with `delta.modified`. |
| 5 | An AST diff node belonging to no feature → appears in `unmapped_nodes`, no feature flagged. |
| 6 | `snapshot_write` MCP tool with `inherit_from="v1.0.0"` and `updated_features=[{"feature_id": "feat-x", ...}]` → result snapshot has 12 features (11 inherited from v1.0.0 + 1 replaced). |
| 7 | `snapshot_write` MCP tool without `inherit_from` → existing behavior, no inheritance logic touched. |
| 8 | `analyze_changes` MCP tool against a baseline whose `structures/<vid>.json.gz` is missing → returns error mentioning R2 / how to enable per-version structure persistence. |
| 9 | `the-door update --from-snapshot v1.0.0 ./current/` → runs full incremental flow, exits 0, writes new snapshot. |
| 10 | `the-door update ./old/ ./new/` (existing form) → unchanged behavior. |

## Track B — Independent Improvements

### R4 — Diff API Label Resolution

**Approach: try `resolve_baseline` first, fall back to `get_snapshot`**

Verified on 2026-05-16: [`SnapshotStore.resolve_baseline`](the_door/src/the_door/core/diff/snapshot_store.py:105) only resolves (1) ISO date format, (2) git tag / commit SHA `[0-9a-f]{7,40}` pattern, (3) manual label exact match. It does **NOT** handle raw `version_id` UUID lookup — a UUID with hyphens fails the SHA regex and won't match labels. The fallback to `get_snapshot(reference)` is therefore **load-bearing**, not defensive. Both paths must be tried for the API to accept both human-readable and UUID inputs.

#### Changes

| File | Change |
|---|---|
| [api_handlers.py:348-349](the_door/src/the_door/core/ui/api_handlers.py:348) | Replace `baseline = store.get_snapshot(baseline_id)` with: try `store.resolve_baseline(baseline_id)`, on `SnapshotNotFoundError` fall back to `store.get_snapshot(baseline_id)`, on still-None return 404. Same for `current_id`. |
| Viewer version picker | When the API exposes `label` alongside `version_id`, the picker passes the label. Already covered by `list_analyzed_versions()` from R2 — picker becomes a consumer of that endpoint. **Split into separate commit** (Task B1b) per atomic principle. |

#### Test plan (TDD)

| RED | Behavior |
|---|---|
| 1 | `/api/diff?baseline=v1.0.0&current=v1.0.5` on a project with two correctly-labeled snapshots → 200, returns `summary` + `node_states`. |
| 2 | `/api/diff?baseline=<valid_uuid>&current=<valid_uuid>` → 200 (regression check). |
| 3 | `/api/diff?baseline=nonexistent&current=v1.0.5` → 404 with `code: "snapshot_not_found"` and message naming `baseline` and `"nonexistent"`. |

---

### R5 — Node ID Uniqueness via Suffix Disambiguation

**Approach: deterministic `#N` suffix on collision, default schema unchanged**

Rejected alternative: full requalification (`<file>::<qualified>::<name>`) — surface too large; would invalidate every existing snapshot's `source_nodes`. Defer to separate epic.

#### Changes

| File | Change |
|---|---|
| `core/extraction/ast_extractor.py` (location to be confirmed by implementer; current grep shows the field assembly in extractor, not a single hot line) | After all nodes are produced, post-process: group by tentative `node_id`, for groups of size > 1, sort within group by `(file, line_number)` ascending, leave the first as-is, suffix the rest with `#2`, `#3`, ... |
| Property test fixture | A Python file containing two classes each with `__init__`, plus a top-level function `__init__` — extract should produce 3 unique node_ids. |

#### Test plan (TDD)

| RED | Behavior |
|---|---|
| 1 | Fixture with two classes both having `__init__` → extract produces node_ids `<file>::__init__` and `<file>::__init__#2`, sorted by line number ascending. |
| 2 | Fixture with no collisions → no `#N` suffixes appear (regression: don't introduce suffixes when not needed). |
| 3 | Property test: any fixture with N items sharing a name → N distinct node_ids, base form is the lowest-line-number occurrence. |
| 4 | Determinism: extract twice on unchanged source → byte-identical node lists. |

### R6 — Detail-Panel Notes + Diff-Explanation Wiring

**Approach: replace stubs with real imports; adjust argument order at call sites**

This is mechanical regression repair. The two real modules already exist and are tested in isolation; only the `ui-detail.js` orchestrator never wired them in.

Rejected alternatives:
- **Recreate the rendering inside ui-detail.js**: duplicates code that already exists in `ui-notes.js` / `ui-diff-explanation.js`. DRY violation.
- **Change the real modules' signature to match the stubs**: easier diff but the real signature `(container, ...)` is more idiomatic (container always first); stubs are wrong, not the real exports.

#### Changes

| File | Change |
|---|---|
| [ui-detail.js:1-2](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:1) | Add `import { appendUserNotesSection } from './ui-notes.js';` and `import { appendDiffExplanationSection } from './ui-diff-explanation.js';` |
| [ui-detail.js:5-6](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:5) | Delete the two no-op stub function definitions. |
| [ui-detail.js:132](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:132) | Call site for diff mode: `appendUserNotesSection(content, 'diff', state.versionA, state.versionB, state.selectedId)` + `appendDiffExplanationSection(content, state.selectedId)`. |
| [ui-detail.js:161](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:161) | Call site for feature view: `appendUserNotesSection(content, state.mode, state.versionA, state.versionB, feature.id)`. |
| [ui-detail.js:263](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:263) | Call site for node selection in diff: `appendUserNotesSection(content, 'diff', state.versionA, state.versionB, node.id)` + `appendDiffExplanationSection(content, node.id)`. |

Existing tests for `ui-notes.js` and `ui-diff-explanation.js` already pin the inner rendering — this requirement adds **integration tests** at the ui-detail orchestration level.

#### Test plan (TDD)

| RED | Behavior |
|---|---|
| 1 | When `renderFeature` runs for a feature in `baseline` mode, the rendered container contains a child with class `user-notes-section`. |
| 2 | When `renderFeature` runs in `diff` mode, the container contains both `user-notes-section` AND `diff-explanation-section`. |
| 3 | When a node is selected (the line 263 path) in diff mode, the panel container contains both sections. |
| 4 | When `state.versionA` and `state.versionB` differ, the notes section receives those values and persists them on note creation (verified via `NoteStore` mock or a single round-trip integration test). |

---

### R7 — Mindmap Reads Snapshot-Comparison Diff

**Approach: extract pure data-shaping function with fallback chain**

Rejected alternatives:
- **Pass both `updateModel.changes` and `versionDiff.node_states` through sessionStorage, decide in mindmap-popup.html**: forces mindmap-popup to learn about the parent's two-source duality. Couples popup to parent's internal state model. Keep popup as a dumb consumer of `{diffNodes, diffAvailable}`.
- **Make `versionDiff` always populate `updateModel`**: violates the conceptual split (report vs snapshot-comparison). Two genuinely different artifacts.
- **Duplicate the transform inline in `switchToMindmap`**: not unit-testable without `window.open` / `sessionStorage` mocking.

#### Changes

| File | Change |
|---|---|
| [layers.js — new export](docs/frontend-local-version-viewer/viewer/js/layers.js:541) | Extract pure function `buildMindmapData(state)` that returns `{project, nodes, diffNodes, diffAvailable}`. Logic: prefer `updateModel.changes` if `updateModel?.diff_available`; else if `versionDiff?.node_states` exists, map entries where `state !== "unchanged"` into `[{id, change_type}]`; else `diffNodes=[]`, `diffAvailable=false`. |
| [layers.js:541-554 switchToMindmap](docs/frontend-local-version-viewer/viewer/js/layers.js:541) | Replace inline `data = {...}` literal with `const data = buildMindmapData(state)`. `sessionStorage` write and `window.open` unchanged. |
| `viewer/tests/` (new file) | Unit tests for `buildMindmapData`. |

The mindmap-popup.html consumer (line 393: `data.diffNodes.find(d => d.id === id)` and line 523: `data.diffNodes.find(...)`) requires no change — both already expect the `[{id, change_type}]` shape.

#### Test plan (TDD)

| RED | Behavior |
|---|---|
| 1 | `buildMindmapData({updateModel: null, versionDiff: null, l1GraphViewModel: {nodes: [...]} })` → `{diffNodes: [], diffAvailable: false, nodes: [...]}`. |
| 2 | `buildMindmapData` with `updateModel.diff_available=true` and `changes=[{id:'a', change_type:'attribute_changed'}]` → `diffNodes` equals the report's changes, `diffAvailable=true`. |
| 3 | `buildMindmapData` with `updateModel=null` AND `versionDiff.node_states={feat-a: "attribute_changed", feat-b: "unchanged"}` → `diffNodes=[{id:'feat-a', change_type:'attribute_changed'}]` (unchanged filtered out), `diffAvailable=true`. |
| 4 | `buildMindmapData` with BOTH sources present and report `diff_available=true` → report wins (returns report's changes, not versionDiff's). |
| 5 | `buildMindmapData` with `updateModel?.diff_available=false` (report exists but explicitly says no diff) AND `versionDiff` populated → falls through to versionDiff. |
| 6 | Returned object's `nodes` field equals `state.l1GraphViewModel?.nodes ?? []` (regression: don't change the nodes side). |

## Verification Strategy

- All RED tests in this spec MUST fail (with the expected error/message) before any production code in that section is touched.
- After each Requirement lands, run `pytest the_door/tests/unit/ the_door/tests/integration/ -q` — current baseline is 580 passing; new tests grow the count, no existing tests should fail.
- For R1 specifically, end-to-end verification on the v105 test target: re-run the same scenario this session uncovered (v1.0.0 baseline + v1.0.5 source) using the new flow, confirm only `feat-ui-server` is reported as affected, write the new snapshot, viewer diff mode shows `attribute_changed: 1`.

## Out-of-Scope Reminders

These remain explicitly excluded (carried from requirements.md):
- Restoring v1.0.0 to English in the test target.
- Globally renaming node_id schema.
- Deleting `source_node_count` field.
- Building reconcile/migration CLIs.
- Populating anomaly entries on hand-edited L2 outputs.
- Redesigning the report-vs-snapshot-comparison diff duality.
