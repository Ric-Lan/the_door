# Tasks — Incremental Analysis & Snapshot Hygiene

Tasks are ordered to respect dependencies (R2 + R3 before R1; R4 and R5 anywhere). Each task is one atomic commit, RED-first, with concrete test names. No task batches multiple requirements.

Recommended commit prefix per requirement: `feat(incremental): ...` for R1, `feat(snapshot): ...` for R2, `refactor(snapshot): ...` for R3, `fix(api): ...` for R4, `fix(extraction): ...` for R5, `fix(viewer): ...` for R6 and R7.

## Track A — Sequential (R3 → R2 → R1)

### Task A1 — R3.1/3.2: SnapshotStore serialization derives `source_node_count`

- [ ] Write RED test: `test_create_snapshot_overrides_caller_source_node_count` in `the_door/tests/unit/core/diff/test_snapshot_store_roundtrip.py`. Given `FeatureSummary(source_node_count=99, source_nodes=("a","b"))`, after `create_snapshot` the on-disk JSON entry has `"source_node_count": 2`.
- [ ] Verify RED — count is 99 in on-disk JSON.
- [ ] Edit [snapshot_store.py:170](the_door/src/the_door/core/diff/snapshot_store.py:170): change `"source_node_count": fs.source_node_count` to `"source_node_count": len(fs.source_nodes)`.
- [ ] Verify GREEN.
- [ ] Write RED test: `test_deserialize_legacy_drift_warns_and_normalizes` — hand-craft a JSON entry with `source_node_count: 5, source_nodes: []`, load via `SnapshotStore.get_snapshot`, assert returned `FeatureSummary.source_node_count == 0`, `source_nodes == ()`, and `caplog.records` contains a `WARNING` mentioning the snapshot file name and feature_id.
- [ ] Verify RED.
- [ ] Edit [snapshot_store.py:237](the_door/src/the_door/core/diff/snapshot_store.py:237) deserialization to handle drift per design.
- [ ] Verify GREEN.
- [ ] Run full unit + integration suite. **Commit.**

### Task A2 — R3.3: `snapshot_write` MCP tool drops `source_node_count` from required

- [ ] Write RED test in `the_door/tests/unit/mcp/test_snapshot_write_tool.py`: `test_snapshot_write_succeeds_without_source_node_count` — call tool with feature dict omitting the field, assert no error, result snapshot has `source_node_count == len(source_nodes)`.
- [ ] Verify RED (current schema requires it → tool raises schema error).
- [ ] Edit [snapshot_write_tool.py:33](the_door/src/the_door/mcp/tools/snapshot_write_tool.py:33) `required` list: remove `"source_node_count"`.
- [ ] Edit [snapshot_write_tool.py:109](the_door/src/the_door/mcp/tools/snapshot_write_tool.py:109): when constructing `FeatureSummary`, always pass `source_node_count=len(source_nodes)`, ignore caller value.
- [ ] Verify GREEN.
- [ ] **Commit.**

### Task A3 — R3.5: timeline_renderer reads from `source_nodes`

- [ ] Write RED test in `the_door/tests/unit/core/timeline/` (create file if absent): given a feature with `source_nodes=("a","b","c")` and `source_node_count=99` (drift), rendered text contains `"Source Nodes: 3"`.
- [ ] Verify RED.
- [ ] Edit [timeline_renderer.py:267](the_door/src/the_door/core/timeline/timeline_renderer.py:267): `len(feature.source_nodes)`.
- [ ] Verify GREEN.
- [ ] **Commit.**

### Task A4 — R2.1/2.4/2.6: write & read per-version gzipped structure

- [ ] Write RED test in new `the_door/tests/unit/core/extraction/test_versioned_structure.py`: `test_write_and_read_round_trip` — write a `StructureJSON` via `write_versioned_structure(path, vid, structure, scan_result)`, file exists at `.the-door/structures/<vid>.json.gz`, `SnapshotStore(path).get_structure(vid)` decompresses to the original structure.
- [ ] Verify RED (functions don't exist).
- [ ] Add `write_versioned_structure` in `core/extraction/structure_serializer.py`.
- [ ] Add `SnapshotStore.get_structure(version_id)` method.
- [ ] Verify GREEN.
- [ ] Write RED test: `test_get_structure_missing_returns_none`. Verify RED → method doesn't exist or raises. Already covered if previous task implemented the happy path; add this case explicitly.
- [ ] Write RED test: `test_get_structure_corrupted_gzip_warns_returns_none` — write `b"\x1f\x8bnot_gzip"` to the file, `get_structure` returns None with warning.
- [ ] Verify RED.
- [ ] Add corruption guard in `get_structure`.
- [ ] Verify GREEN.
- [ ] **Commit.**

### Task A5 — R2.5: `list_analyzed_versions` enumerator

- [ ] Write RED test: `test_list_analyzed_versions_marks_has_structure` — directory with two snapshots, only one has corresponding `structures/<vid>.json.gz`, method returns 2 entries, `has_structure` set correctly, ordered by snapshot timestamp desc.
- [ ] Verify RED.
- [ ] Implement `SnapshotStore.list_analyzed_versions()` per design.
- [ ] Verify GREEN.
- [ ] **Commit.**

### Task A6 — R2.1: analyze pipeline writes per-version structure

- [ ] Write RED test in `the_door/tests/integration/`: `test_analyze_pipeline_writes_versioned_structure` — run analyze on a tiny fixture, after completion `.the-door/structures/<new_snapshot.version_id>.json.gz` exists and decompresses to the same node count as the in-memory extraction.
- [ ] Verify RED.
- [ ] Edit [analyze_pipeline.py](the_door/src/the_door/core/pipeline/analyze_pipeline.py): leave the existing `write_structure_json(...)` call at line ~153 untouched (this writes the "latest" pointer file). Then, after `snapshot = _create_auto_snapshot(...)` returns (currently around line ~179–181), add a new call `write_versioned_structure(codebase_path, snapshot.version_id, structure, scan_result)` immediately before the `return AnalyzeResult(...)` statement. Wrap the new call in `try/except Exception as e: logger.warning(...); progress(...)` — versioned structure persistence failure must be non-fatal (same convention as `_create_auto_snapshot`'s failure handling already in the codebase).
- [ ] Verify GREEN.
- [ ] **Commit.**

### Task A7 — R1: pure function `compute_affected_features`

- [ ] Write RED tests in new `the_door/tests/unit/core/diff/test_feature_attribution.py` per design's tests 1–5.
- [ ] Verify all 5 RED.
- [ ] Implement `core/diff/feature_attribution.py` per design.
- [ ] Verify all 5 GREEN.
- [ ] **Commit.**

### Task A8 — R1: `analyze_changes` MCP tool

- [ ] Write RED test: `test_analyze_changes_returns_incremental_diff` — fixture with two persisted structures (via R2), call tool, assert response shape matches `IncrementalDiff` JSON form.
- [ ] Write RED test: `test_analyze_changes_baseline_without_persisted_structure_errors` — baseline snapshot exists but no `structures/<vid>.json.gz`, tool returns actionable error message.
- [ ] Verify RED.
- [ ] Implement `the_door/src/the_door/mcp/tools/analyze_changes_tool.py`. Follow the pattern of [snapshot_write_tool.py](the_door/src/the_door/mcp/tools/snapshot_write_tool.py): module exports `TOOL_SCHEMA` (dict) and `async def handle(arguments: dict, ...)`.
- [ ] Register in MCP server at **three sites** in [mcp/server.py](the_door/src/the_door/mcp/server.py): (a) add `from the_door.mcp.tools import analyze_changes_tool` to the imports near line 17; (b) add a `Tool(name="analyze_changes", ..., inputSchema=analyze_changes_tool.TOOL_SCHEMA)` entry inside `list_tools()` (currently near line 113); (c) add a dispatch branch `if name == "analyze_changes": return await self._dispatch_tool(analyze_changes_tool, arguments)` in the call-tool handler (currently near line 188).
- [ ] Verify GREEN.
- [ ] **Commit.**

### Task A9 — R1: `snapshot_write` accepts `inherit_from`

- [ ] Write RED test: `test_snapshot_write_with_inherit_from_merges_features` — fixture baseline has 12 features, call tool with `inherit_from=<baseline_vid>` + `updated_features=[<1 feature>]`, result snapshot contains 12 features (11 inherited verbatim + 1 replaced).
- [ ] Write RED test: `test_snapshot_write_without_inherit_from_unchanged` — regression: existing two-arg form still works.
- [ ] Verify both RED.
- [ ] Extend `snapshot_write_tool.py` per design.
- [ ] Verify GREEN.
- [ ] **Commit.**

### Task A10 — R1: `the-door update --from-snapshot` CLI flag

- [ ] Write RED test in `the_door/tests/unit/cli/test_cli_commands.py`: `test_update_from_snapshot_flag` — invoke CLI with `--from-snapshot v1.0.0 ./current/`, assert pipeline runs without an `old_path` directory.
- [ ] Write RED test: `test_update_old_path_form_still_works` — invoke CLI with positional `old_path new_path`, assert no regression.
- [ ] Verify RED.
- [ ] Add `--from-snapshot` flag in `cli/update_cmd.py`; wire to incremental pipeline path.
- [ ] Verify GREEN.
- [ ] **Commit.**

### Task A11 — R1: doc in CLAUDE.md

- [ ] Add a "Mode B — Incremental analysis (with baseline)" subsection to CLAUDE.md, documenting the `analyze_changes` → agent update → `snapshot_write(inherit_from=...)` flow with a worked example. Reference R1, R2, R3 by spec section.
- [ ] **Commit (docs only).**

## Track B — Parallel (any order)

### Task B1a — R4 backend: diff API accepts label/tag/sha

- [ ] Write RED test in `the_door/tests/unit/core/ui/test_api_handlers.py` (or appropriate file): `test_diff_api_resolves_label` — given snapshots labeled "v1.0.0" and "v1.0.5", call handler with `baseline_id="v1.0.0", current_id="v1.0.5"`, expect 200.
- [ ] Write RED test: `test_diff_api_still_accepts_version_id` — regression with raw UUIDs.
- [ ] Write RED test: `test_diff_api_unresolvable_returns_404` — gibberish returns 404 with `snapshot_not_found` and message identifying which side (`baseline` vs `current`) failed.
- [ ] Verify all 3 RED (current code returns 404 for label).
- [ ] Edit [api_handlers.py:348-349](the_door/src/the_door/core/ui/api_handlers.py:348) per design — try `resolve_baseline` first, on `SnapshotNotFoundError` fall back to `get_snapshot`.
- [ ] Verify GREEN.
- [ ] **Commit (backend only).**

### Task B1b — R4 frontend: viewer picker sends label

- [ ] Write RED test in `viewer/tests/`: version picker emits the snapshot's `label` (or `git_tags[0]`) as the chosen reference when present; falls back to `version_id` when no label / no git_tags.
- [ ] Verify RED.
- [ ] Edit the picker component in `docs/frontend-local-version-viewer/viewer/js/` (grep for the existing picker rendering point to locate exactly — single grep target, no scope creep).
- [ ] Verify GREEN.
- [ ] **Commit (frontend only).**

### Task B2 — R5: AST extractor disambiguates colliding node_ids

- [ ] Add new fixture `the_door/tests/fixtures/sample_codebases/colliding_init/` containing one Python file with two classes both defining `__init__` plus a top-level function `__init__`.
- [ ] Write RED test in `the_door/tests/unit/core/extraction/test_ast_extractor.py`: extract on fixture → 3 distinct node_ids, base + `#2` + `#3`, ordered by line number.
- [ ] Write RED test: `test_no_collisions_no_suffix` — fixture with no name collisions produces no `#N` suffixes.
- [ ] Write property test: any fixture with N items sharing a name → N distinct node_ids.
- [ ] Verify all RED.
- [ ] Implement post-processing in [`ASTExtractor`](the_door/src/the_door/core/extraction/ast_extractor.py): after all nodes are collected (before return), group nodes by tentative `node_id`, sort each group by `(file_path, line_number)` ascending, leave index-0 unchanged, append `#2`, `#3`, … to subsequent indices. No changes to call-site contracts; this is a pure post-processing pass within the extractor.
- [ ] Verify GREEN.
- [ ] **Commit.**

### Task B3 — R6: detail-panel wires user notes + diff explanation

- [ ] Write RED test in `docs/frontend-local-version-viewer/viewer/tests/ui-detail.test.js`: `renderFeature in baseline mode renders user-notes-section into container`. Verify RED — container doesn't contain that class because stub is no-op.
- [ ] Write RED test: `renderFeature in diff mode renders BOTH user-notes-section AND diff-explanation-section`. Verify RED.
- [ ] Write RED test: node-selection path (line 263) in diff mode renders both sections. Verify RED.
- [ ] Edit [ui-detail.js:1-2](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:1): add `import { appendUserNotesSection } from './ui-notes.js';` and `import { appendDiffExplanationSection } from './ui-diff-explanation.js';`.
- [ ] Edit [ui-detail.js:5-6](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:5): delete the two no-op stub definitions.
- [ ] Edit three call sites ([:132](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:132), [:161](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:161), [:263](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:263)) to pass `(container, mode, versionA, versionB, featureId)` order per the real exports' signature. The diff-explanation call sites take `(container, featureId)`.
- [ ] Verify all three RED tests now GREEN.
- [ ] Run `cd docs/frontend-local-version-viewer/viewer && npm run test:coverage`; confirm no regressions in existing 571 tests, new tests included in count.
- [ ] **Commit.**

### Task B4 — R7: mindmap reads versionDiff as fallback

- [ ] Write RED test in `docs/frontend-local-version-viewer/viewer/tests/layers.test.js` (or appropriate file): import `buildMindmapData` — fails because function doesn't exist yet.
- [ ] Write RED tests per design's 6 cases (no source / report only / versionDiff only / both prefer report / report-says-no-diff fallback / nodes pass-through).
- [ ] Verify all RED.
- [ ] Add `export function buildMindmapData(state)` to [layers.js](docs/frontend-local-version-viewer/viewer/js/layers.js) implementing the fallback chain per design.
- [ ] Edit [layers.js:541-554 switchToMindmap](docs/frontend-local-version-viewer/viewer/js/layers.js:541): replace inline data literal with `const data = buildMindmapData(state)`.
- [ ] Verify all RED tests now GREEN.
- [ ] Run JS test suite; confirm no regressions.
- [ ] **Commit.**

## Execution Constraints (Read Before Starting Any Task)

These constraints exist to prevent the executing agent from "doing extra things" or "randomly grepping to verify intent." They are testable.

1. **One task = one commit.** Do not bundle. If two tasks share a file, commit twice; the second amends the file the first touched.
2. **No file reads outside the paths named in the task.** Every implementation file and every test file is named explicitly above. If a task lists `[file.py:NN]`, that is the only file to be edited for that change. Reading sibling files for "context" is **not allowed** — if the spec lacks the context you need, stop and ask, do not explore.
3. **No design re-evaluation.** The Rejected Alternatives section in design.md is binding. Do not propose a different approach mid-task even if it looks cleaner; raise it as a follow-up issue if convinced.
4. **No defensive code beyond what an AC mandates.** If an AC does not require error handling for a case, do not add it.
5. **No comments explaining the change.** Spec is the documentation. Do not add `# fixes R3 AC5` or similar — git blame + commit message suffices.
6. **TDD discipline is mandatory.** RED-verify with the predicted failure mode (the one stated in the task) before writing any production code. If the RED looks different from predicted, **stop and re-read the spec** — do not "adapt" the test to match unexpected behavior; the spec or your understanding is wrong.
7. **No new files unless explicitly listed.** New file paths in this spec are: `core/diff/feature_attribution.py`, `mcp/tools/analyze_changes_tool.py`, `pipeline/incremental_pipeline.py`, and the four new test files in Tasks A4, A7, A8 (one), and the fixture directory in B2. No other new files.
8. **No spec edits during execution.** If the spec is wrong, stop and report. Do not "fix as we go."
9. **Verification scope.** When a task says "verify GREEN" it means: run the specific test file(s) the task created. When a task says "run full suite" it means the entire `pytest the_door/tests/unit/ the_door/tests/integration/ -q` or the entire `npm run test:coverage`. Do not run anything in between (no "let me also check this related module").

## Acceptance / "Done" Definition

The spec is complete when:

1. All 16 tasks above are committed to main.
2. `pytest the_door/tests/unit/ the_door/tests/integration/ -q` reports ≥ 593 passing tests (current 580 + at least 13 new Python behaviors pinned; actual count will be higher).
3. `cd docs/frontend-local-version-viewer/viewer && npm run test:coverage` reports ≥ 580 passing tests (current 571 + at least 9 new JS behaviors across B3 + B4; actual count will be higher).
4. End-to-end verification on the v105 test target: `the-door update --from-snapshot v1.0.0 C:\Users\Ric\Desktop\test-targets\the-door-v105` produces a new snapshot where only `feat-ui-server` is in `affected_features`; viewer diff mode displays `attribute_changed: 1`.
5. Viewer detail panel renders "使用者備註" section in all three layers (baseline / current / diff); also renders "AI 差異說明" section in diff mode.
6. Viewer mindmap popup, when the user has selected two snapshots via the version picker (no `the-door update` report present), displays `Δ 有差異` badge on the L1 nodes whose features changed.
7. `the-door ui` no longer requires a manual UUID lookup before calling `/api/diff?baseline=v1.0.0&current=v1.0.5`.
8. No existing test is deleted to make a new test pass.
9. No new CLI command was added beyond `--from-snapshot` flag (overall command surface unchanged in count).

## Estimation

- Track A: 11 tasks, mostly small. Bottleneck is A7 (pure function with 5 test cases) and A9 (snapshot_write extension touches the most existing tests). Estimate: 2 working days end-to-end.
- Track B: 5 tasks (B1a backend ~1 hour, B1b frontend ~1 hour, B2 ~3 hours, B3 ~2 hours, B4 ~2 hours). Can run in parallel with Track A or anywhere. Total ~1.5 working days.

Total: ~3.5 working days for one developer following TDD without batching.
