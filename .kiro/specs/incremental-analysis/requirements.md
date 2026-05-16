# Requirements Document — Incremental Analysis & Snapshot Hygiene

## Introduction

This spec captures seven issues uncovered during a session on 2026-05-16. Five surfaced while attempting to "run analysis on v1.0.5"; two additional viewer regressions were discovered when verifying the result in the browser. Each issue forced manual scripting, multiple round-trips, or violated the intended design ("inherit baseline features, re-analyze only the AST diff").

The fixes form two independent tracks:

- **Track A — Incremental analysis** (痛點 1+2+3): make "baseline snapshot + new source code → updated snapshot" a first-class flow, with the supporting data persistence and field-integrity fixes it depends on.
- **Track B — Independent improvements** (痛點 4+6+7+8): four unrelated UX / data-integrity / regression fixes that surfaced during the same investigation.

All痛點 below were verified against current `main` (HEAD `3b44ead`) via grep / runtime inspection. File:line references are real.

## Glossary

- **Baseline_Snapshot**: A previously persisted `VersionSnapshot` whose L1 features serve as the starting point for analyzing a newer version of the same codebase.
- **AST_Diff**: The set of `node_id`s added/removed/modified between two `structure.json` outputs of the same codebase at different points in time.
- **Affected_Feature**: A baseline feature whose `source_nodes` intersects the `AST_Diff`, i.e., the LLM needs to re-evaluate its label/description.
- **Inherited_Feature**: A baseline feature whose `source_nodes` does NOT intersect the `AST_Diff` — carried forward verbatim into the new snapshot.
- **Per_Version_Structure**: A persisted copy of `structure.json` keyed by snapshot `version_id`, allowing the AST of any prior analyzed version to be retrieved without keeping that version's source code on disk.
- **Source_Nodes_Invariant**: The rule that `FeatureSummary.source_node_count` is always equal to `len(FeatureSummary.source_nodes)`, eliminating drift between the two fields.

## Requirements

### Requirement 1: Incremental Analysis Entry (痛點 1)

**User Story:** As a user with a previously analyzed v1.0.0 snapshot, I want to analyze v1.0.5 by inheriting v1.0.0's features and only re-evaluating those touched by the AST diff, so that I don't pay for a full LLM re-analysis and the older source code does not need to remain on disk.

#### Acceptance Criteria

1. WHEN a user invokes incremental analysis on a codebase path with a baseline reference (label / tag / commit SHA / date / version_id), THE system SHALL load the baseline's persisted `structure.json` and L1 features, extract the current codebase's AST, compute the AST diff, and identify Affected_Features.
2. WHEN the baseline's persisted `structure.json` is absent, THE system SHALL fail with an error containing: (a) the baseline reference the user supplied, (b) the expected file path `<codebase_path>/.the-door/structures/<vid>.json.gz`, (c) a one-line remediation (e.g., `Run "the-door analyze" once on this codebase first; older snapshots created before Requirement 2 landed do not have persisted structures`). It SHALL NOT fall back to re-extracting from a non-existent old source path.
3. WHEN the AST diff is empty (no added / removed / modified nodes), THE system SHALL produce a new snapshot whose L1 features are byte-identical to the baseline's, with only metadata (timestamp, version_id) differing.
4. WHEN the AST diff intersects a feature's `source_nodes`, THE system SHALL emit a structured "to be inferred" entry containing: `feature_id`, current label/description/trigger_description, added nodes, removed nodes, modified nodes.
5. WHEN an AST diff node belongs to no baseline feature's `source_nodes`, THE system SHALL list it under `unmapped_nodes` without dropping it.
6. WHEN an agent (Mode B) or the in-process LLM (Mode A) supplies updated label/description for Affected_Features, THE system SHALL produce a new snapshot containing inherited features (verbatim) + updated features (replaced), preserving `feature_relations_snapshot` from the baseline by default.
7. WHEN the incremental flow runs to completion, THE system SHALL write the new snapshot under `.the-door/snapshots/<new_vid>.json` AND its corresponding `.the-door/structures/<new_vid>.json.gz` (per Requirement 2).
8. THE system SHALL NOT introduce a new top-level CLI command if an existing one can be extended — `the-door update` SHALL accept `--from-snapshot <ref>` as an alternative to `<old_path>`.
9. THE system SHALL NOT introduce a second MCP tool when one suffices — the existing `snapshot_write` MCP tool SHALL accept optional `inherit_from: <baseline-ref>` + `updated_features` (subset), with default behavior unchanged when absent. A separate read-only MCP tool `analyze_changes(codebase_path, baseline)` SHALL return a JSON object with exactly these top-level keys: `baseline_version_id`, `inherited_features` (list), `affected_features` (list per AC4), `unmapped_nodes` (object with `added`/`removed`/`modified` arrays per AC5). No other top-level keys.

### Requirement 2: Per-Version Structure Persistence (痛點 2)

**User Story:** As a user analyzing multiple versions of the same codebase over time, I want each version's AST analysis output to be persisted independently so that I can run diffs against any prior version without having to re-extract from source files I may no longer have on disk.

#### Acceptance Criteria

1. WHEN `analyze_pipeline._create_auto_snapshot` writes a new snapshot, THE system SHALL also write `.the-door/structures/<version_id>.json.gz` containing the gzipped form of that version's `structure.json`.
2. THE `.the-door/structure.json` file at `.the-door/structure.json` SHALL continue to exist as a convenience pointer to the latest extraction (current contract); this requirement does not remove it.
3. THE system SHALL NOT maintain a separate `manifest.json` index file — `version_id → structure path` mapping is derivable from `snapshots/<version_id>.json` existing and `structures/<version_id>.json.gz` existing. Duplicating that data violates DRY.
4. WHEN code asks `SnapshotStore.get_structure(version_id)`, THE system SHALL return the decompressed `StructureJSON` if the per-version file exists, else `None`.
5. WHEN code asks `SnapshotStore.list_analyzed_versions()`, THE system SHALL return one entry per snapshot in `snapshots/`, each tagged with `has_structure: bool` indicating whether `structures/<version_id>.json.gz` exists. (Old snapshots created before this spec lands SHALL appear with `has_structure: False`, without crashing the iterator.)
6. WHEN a per-version structure file is corrupted (truncated gzip, bad JSON), THE system SHALL log a warning and behave as if it does not exist, NOT raise.

### Requirement 3: Source Nodes Invariant (痛點 3)

**User Story:** As a developer reading or writing snapshots, I want `source_node_count` to be impossible to drift away from `len(source_nodes)`, so that Requirement 1's AST_Diff → Affected_Features mapping is reliable.

#### Acceptance Criteria

1. WHEN `SnapshotStore.create_snapshot` serializes a `FeatureSummary`, THE system SHALL write `source_node_count = len(fs.source_nodes)` regardless of the caller-supplied value, becoming the single source of truth from `source_nodes`.
2. WHEN `SnapshotStore` deserializes a legacy snapshot with `source_node_count > 0` AND `source_nodes` empty/absent, THE system SHALL log a warning identifying the snapshot file and feature_id, return `FeatureSummary` with `source_nodes=()` and `source_node_count=0`, and NOT crash.
3. THE `snapshot_write` MCP tool's input schema SHALL mark `source_node_count` as optional (currently required at [snapshot_write_tool.py:33](the_door/src/the_door/mcp/tools/snapshot_write_tool.py:33)). Supplied values SHALL be ignored in favor of `len(source_nodes)`.
4. THE `FeatureSummary` dataclass SHALL retain its `source_node_count` field for backward compatibility with existing JSON snapshots; field removal is explicitly out of scope for this spec.
5. THE `timeline_renderer` at [timeline_renderer.py:267](the_door/src/the_door/core/timeline/timeline_renderer.py:267) SHALL display `len(feature.source_nodes)` instead of reading `feature.source_node_count`. (Verified via grep on 2026-05-16: this is the only live reader of the field outside of model definition and (de)serializer code.)
6. NO new `reconcile` CLI / migration tool SHALL be created. Hand-edited legacy snapshots that violate the invariant SHALL be re-generated via `the-door analyze` or accepted as-is with the warning from AC2.

### Requirement 4: Diff API Accepts Human-Readable References (痛點 4)

**User Story:** As a viewer user (or curl-ing developer), I want `/api/diff?baseline=v1.0.0&current=v1.0.5` to resolve labels/tags/dates/SHAs the same way `the-door diff --baseline` does, so that I can compare versions without first looking up UUIDs.

#### Acceptance Criteria

1. WHEN `/api/diff` receives a `baseline` or `current` query parameter, THE system SHALL first attempt resolution via `SnapshotStore.resolve_baseline(ref)`, falling back to `SnapshotStore.get_snapshot(ref)` (raw version_id) only if `resolve_baseline` raises `SnapshotNotFoundError`.
2. WHEN neither resolution succeeds, THE system SHALL return HTTP 404 with `code="snapshot_not_found"` and a message naming which side (baseline/current) failed and what reference was attempted.
3. THE existing behavior for valid `version_id` UUIDs SHALL not regress.
4. THE viewer's version picker SHALL pass the human-readable label (when one exists) instead of the version_id, with version_id used as fallback only when no label is set.

### Requirement 5: Unique Node IDs from AST Extraction (痛點 6)

**User Story:** As a downstream consumer indexing AST nodes by `node_id` (e.g., AST diff, source-node-to-feature mapping), I want every node_id emitted by `ASTExtractor` to be unique within a single extraction run, so that `dict[node_id]` lookups don't silently collapse multiple distinct nodes.

#### Acceptance Criteria

1. WHEN `ASTExtractor.extract` emits two or more nodes that would otherwise share a node_id (e.g., multiple `__init__` methods in different classes within a single file), THE system SHALL deterministically suffix the second-and-later occurrences with `#2`, `#3`, … in ascending line-number order.
2. THE deterministic ordering SHALL be stable across re-runs on the same source — running extract twice on unchanged source yields identical node_ids.
3. THE existing node_id schema `<file>::<name>` SHALL remain the default for the first/unique occurrence; only the 2nd, 3rd, … receive `#2`, `#3`, … suffixes. This avoids breaking source_nodes references in existing snapshots that point to the non-colliding majority.
4. WHEN an existing snapshot's `source_nodes` references a bare `<file>::<name>` id, and the current extraction now produces a collision for that name (so the bare id ambiguously refers to one of multiple occurrences), THE incremental analysis flow (Requirement 1) SHALL list that reference under `unmapped_nodes` rather than silently mapping it to whichever occurrence happens to take the bare id post-disambiguation. This is consistent with AC3 — AC3 picks a deterministic owner for the bare id within the new extraction, but the old snapshot's intent is no longer recoverable, so we surface the ambiguity instead of guessing.
5. A property test SHALL pin: any fixture containing N items sharing the same `<file>::<name>` tuple produces N distinct node_ids in the extraction output.
6. **Known limitation (documented, not fixed):** when a colliding `<name>` exists in BOTH baseline and current extraction but the line-number-ordered first occurrence differs (e.g., a new class was inserted above the original), the bare id may point to a different physical node across versions. This is a fundamental property of suffix-based disambiguation. Resolving it requires full requalification (out of scope per the Non-Requirements section).

### Requirement 6: Detail Panel User Notes & Diff Explanation Wiring (痛點 7)

**User Story:** As a viewer user inspecting a feature in the right-hand detail panel, I want to write personal notes ("使用者備註") and read AI-generated diff explanations, so that the per-feature drill-down workflow works as it did before the app.js refactor.

#### Acceptance Criteria

1. WHEN any layer (`L1` baseline / current / diff) renders a feature into the detail panel, THE system SHALL include a "使用者備註" section that lets the user add, list, and delete personal notes scoped to `(mode, feature_id, versionA, versionB)`.
2. WHEN the user opens a feature card in `diff` mode, THE system SHALL include a "AI 差異說明" section that fetches and displays the diff explanation for that `feature_id`.
3. THE `ui-detail.js` no-op stubs at [ui-detail.js:5-6](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:5) SHALL be replaced by real `import` of `appendUserNotesSection` from `ui-notes.js` and `appendDiffExplanationSection` from `ui-diff-explanation.js`, called at the existing call sites with the documented argument order.
4. WHEN the stub signature `(mode, id, vA, vB, container)` differs from the real export's signature `(container, mode, vA, vB, featureId)`, THE call-site update SHALL adjust argument order at all three current invocations ([ui-detail.js:132, 161, 263](docs/frontend-local-version-viewer/viewer/js/ui-detail.js:132)).
5. THE backend `NoteStore` and `/api/notes` endpoint behavior SHALL NOT change — this requirement is wiring only.

### Requirement 7: Mindmap Reads Snapshot-Comparison Diff (痛點 8)

**User Story:** As a viewer user who has selected two snapshots via the version picker and opens the mindmap popup, I want the L1 nodes whose features changed to display the `Δ 有差異` badge, so that the mindmap reflects the same diff result the main view shows.

#### Acceptance Criteria

1. WHEN the user opens the mindmap and `state.versionDiff` is populated (from `/api/diff?baseline=...&current=...`) but `state.updateModel` is null (no `the-door update` report exists), THE mindmap SHALL still receive the diff data and mark affected L1 nodes with `Δ 有差異`.
2. WHEN both `state.updateModel.diff_available === true` AND `state.versionDiff` are present, THE mindmap SHALL prefer `state.updateModel.changes`. Rationale: report-based `changes` carry richer per-feature metadata (e.g., `change_reason`) that snapshot-comparison `node_states` lacks. When `updateModel.diff_available === false` (report exists but explicitly says no diff), `versionDiff` SHALL be used.
3. WHEN neither source is present, THE mindmap SHALL render with no diff badges (no regression).
4. WHEN converting `state.versionDiff.node_states` (dict form `{feature_id: state}`) into the mindmap's expected `[{id, change_type}]` array form, THE transformation SHALL exclude entries whose state is `"unchanged"`.
5. THE data-shaping logic SHALL be extracted into a pure function `buildMindmapData(state)` exported from `layers.js`, so it is unit-testable independently of `window.open` and `sessionStorage`.
6. THE mindmap popup (`mindmap-popup.html`) SHALL NOT be modified — the fix lives entirely in the parent viewer's data assembly.
7. ANOMALY rendering in mindmap SHALL remain unchanged. Anomaly absence on hand-edited L2 data is expected behavior, not a bug.

## Non-Requirements (Explicitly Out of Scope)

The following came up during investigation but are explicitly NOT in this spec:

- Restoring v1.0.0 to English labels in the test target (`scripts/integration-test/validate_v100.py` holds the originals; user has confirmed restoration is not wanted).
- Renaming node_id schema globally to `<file>::<qualified_path>::<name>`. Suffix disambiguation (Requirement 5) is the chosen minimal fix; full requalification can be a separate epic if needed.
- Deleting the `source_node_count` field outright. Requirement 3 makes it derived-only; deletion is deferred to a later cleanup commit.
- Building any `the-door snapshot reconcile-source-nodes` migration CLI.
- Touching the viewer's L2 generation flow, mermaid rendering, or non-diff API handlers.
- Populating anomaly data on hand-edited L2 outputs. The mindmap's ⚠ badge correctly stays absent when no anomalies are recorded by analysis. Generating anomaly entries requires an LLM-driven L2 analysis run (not in scope).
- Redesigning the two-track diff data model (`updateModel` report-based vs `versionDiff` snapshot-comparison). Requirement 7 only adds the missing read of the second track in mindmap; the underlying duality is preserved.

## Cross-Reference

- 痛點 1 → Requirement 1
- 痛點 2 → Requirement 2
- 痛點 3 → Requirement 3
- 痛點 4 → Requirement 4
- 痛點 6 → Requirement 5
- 痛點 7 (detail-panel notes regression) → Requirement 6
- 痛點 8 (mindmap diff data source) → Requirement 7
- 痛點 5 (CLAUDE.md doc gap) was downgraded to a doc deliverable embedded in Requirement 1's tasks, not a separate requirement.
