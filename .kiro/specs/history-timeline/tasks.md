# Implementation Plan: Phase 4 History Timeline Layer

## Overview

Implement multi-version timeline analysis and retention policy for The Door. This plan follows the dependency order: data models + JSON schema → core engines (TimelineEngine, RetentionEngine) → SnapshotStore extension → TimelineRenderer → CLI commands → MCP tools → final integration. Each task follows TDD: property/unit tests as sub-tasks alongside implementation. Property-based tests use Hypothesis with `@settings(max_examples=100)` and ASCII-only strings for Windows compatibility.

## Tasks

- [x] 1. Define Phase 4 data models and JSON schema
  - [x] 1.1 Add timeline and retention dataclasses to models.py
    - Add to `src/the_door/models.py` under a new `# Phase 4: History Timeline models` section
    - Add 5 frozen dataclasses: `SemanticDriftEvent` (snapshot_version_id, previous_description, new_description, timestamp), `FeatureTimeline` (feature_id, first_seen_timestamp, last_seen_timestamp, change_count, current_state, current_label, drift_events), `TimelineSummary` (active_count, removed_count, total_drift_events), `TimelineResult` (snapshot_count, time_range_start, time_range_end, feature_timelines, summary), `RetentionDecision` (to_retain, to_remove)
    - Add 2 exception classes: `TimelineError`, `RetentionConfigError`
    - Follow existing conventions: `frozen=True`, `field(default_factory=list)` for mutable defaults
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.4, 9.1, 9.2_

  - [x] 1.2 Create timeline-result JSON schema
    - Create `the_door/schemas/timeline-result.schema.json` (Draft 2020-12)
    - Define required fields: snapshot_count (integer ≥ 0), time_range_start (string|null, date-time), time_range_end (string|null, date-time), feature_timelines (array of FeatureTimeline objects), summary (object with active_count, removed_count, total_drift_events)
    - FeatureTimeline items: feature_id, first_seen_timestamp, last_seen_timestamp, change_count (integer ≥ 0), current_state (enum: active/removed), current_label, drift_events array
    - SemanticDriftEvent items: snapshot_version_id, previous_description, new_description, timestamp
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 1.3 Write unit tests for data models
    - Create `the_door/tests/unit/core/timeline/` directory with `__init__.py`
    - Test frozen immutability, default factory values, field types for all 5 dataclasses
    - Test exception classes: `TimelineError`, `RetentionConfigError`
    - _Requirements: 9.1, 9.2_

- [x] 2. Implement TimelineEngine
  - [x] 2.1 Create core/timeline package and implement TimelineEngine
    - Create `the_door/src/the_door/core/timeline/__init__.py`
    - Create `the_door/src/the_door/core/timeline/timeline_engine.py` with `TimelineEngine` class
    - Implement `analyze(snapshots: list[VersionSnapshot]) -> TimelineResult` — pure function, no I/O:
      - Sort snapshots by timestamp
      - Collect all distinct feature_ids (union of all `l1_snapshot` keys)
      - For each feature_id: find first_seen/last_seen, count changes (label or description differs between consecutive snapshots; confidence changes excluded), detect semantic drift (label unchanged + description changed), determine current_state (active if in latest snapshot, removed if not)
      - Compute TimelineSummary (active_count, removed_count, total_drift_events)
      - Handle edge cases: empty list → empty result (snapshot_count=0), single snapshot → all change_count=0
    - Implement `analyze_feature(snapshots, feature_id) -> FeatureTimeline | None`
    - Implement `_detect_drift(prev_feature, curr_feature, snapshot) -> SemanticDriftEvent | None`
    - Implement `_compute_summary(feature_timelines) -> TimelineSummary`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ]* 2.2 Write property test: Timeline completeness (Property 1)
    - **Property 1: Timeline completeness**
    - For any snapshot sequence, the number of FeatureTimeline entries equals the number of distinct feature_ids across all input snapshots
    - Create `the_door/tests/property/test_timeline_properties.py` with shared Hypothesis strategies (`snapshot_sequences` composite strategy using ASCII-only strings)
    - **Validates: Requirements 1.1, 1.6**

  - [ ]* 2.3 Write property test: Change count correctness (Property 2)
    - **Property 2: Change count correctness**
    - For any snapshot sequence and any feature in multiple snapshots, change_count equals the number of consecutive pairs where label or description differs
    - **Validates: Requirements 1.4**

  - [ ]* 2.4 Write property test: Semantic drift detection correctness (Property 3)
    - **Property 3: Semantic drift detection correctness**
    - (a) label unchanged + description changed → exactly one SemanticDriftEvent; (b) both changed → no event; (c) neither changed → no event
    - **Validates: Requirements 2.1, 2.3, 2.5**

  - [ ]* 2.5 Write property test: Drift events time-ordered (Property 4)
    - **Property 4: Drift events time-ordered**
    - For any snapshot sequence, drift_events in each FeatureTimeline are sorted by timestamp ascending
    - **Validates: Requirements 2.4**

  - [ ]* 2.6 Write property test: Timeline idempotency (Property 5)
    - **Property 5: Timeline idempotency**
    - Running analyze(S) twice produces identical TimelineResult objects
    - **Validates: Requirements 1.5, 10.6**

  - [ ]* 2.7 Write property test: Time ordering invariant (Property 6)
    - **Property 6: Time ordering invariant**
    - Every FeatureTimeline's first_seen_timestamp ≤ last_seen_timestamp
    - **Validates: Requirements 10.1**

  - [ ]* 2.8 Write property test: Change count upper bound (Property 7)
    - **Property 7: Change count upper bound**
    - For snapshot sequence of length N, every change_count ≤ N - 1
    - **Validates: Requirements 10.2**

  - [ ]* 2.9 Write property test: State consistency with latest snapshot (Property 8)
    - **Property 8: State consistency with latest snapshot**
    - active features exist in latest snapshot's l1_snapshot; removed features do not
    - **Validates: Requirements 10.3**

  - [ ]* 2.10 Write property test: Drift event traceability (Property 9)
    - **Property 9: Drift event traceability**
    - Every SemanticDriftEvent.timestamp corresponds to an actual input snapshot's timestamp
    - **Validates: Requirements 10.4**

  - [ ]* 2.11 Write unit tests for TimelineEngine
    - Create `the_door/tests/unit/core/timeline/test_timeline_engine.py`
    - Test: empty sequence, single snapshot (all change_count=0, drift_events empty), two snapshots with no changes, feature added then removed, label change increments change_count, description change increments change_count, confidence change does NOT increment change_count, semantic drift (label same + description changed), no drift when both change, feature appears/disappears/reappears, multiple features across snapshots
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 3. Implement RetentionEngine
  - [x] 3.1 Implement RetentionEngine
    - Create `the_door/src/the_door/core/timeline/retention_engine.py` with `RetentionEngine` class
    - Implement `compute_retention(snapshots, max_snapshots=50, enabled=True) -> RetentionDecision` — pure function, no I/O:
      - If enabled=False → all in to_retain, to_remove empty
      - Classify: protected (trigger=="manual" OR git_tags non-empty) vs unprotected
      - Protected always in to_retain
      - Unprotected sorted by timestamp descending (newest first), keep first max_snapshots, rest in to_remove
      - Handle: max_snapshots ≤ 0 → all unprotected in to_remove; empty list → empty result
    - Implement `_is_protected(snapshot) -> bool`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [ ]* 3.2 Write property test: Retention partition completeness (Property 10)
    - **Property 10: Retention partition completeness**
    - Union of to_retain and to_remove equals all input version_ids; intersection is empty
    - Create `the_door/tests/property/test_retention_properties.py` with Hypothesis strategies
    - **Validates: Requirements 3.6, 11.4**

  - [ ]* 3.3 Write property test: Protected snapshots always retained (Property 11)
    - **Property 11: Protected snapshots always retained**
    - All manual snapshots and tagged snapshots appear in to_retain regardless of max_snapshots
    - **Validates: Requirements 3.2, 11.1, 11.2**

  - [ ]* 3.4 Write property test: Disabled retention retains all (Property 12)
    - **Property 12: Disabled retention retains all**
    - When enabled=False, all snapshots in to_retain, to_remove empty
    - **Validates: Requirements 3.3, 11.3**

  - [ ]* 3.5 Write property test: Retention removal count predictable (Property 13)
    - **Property 13: Retention removal count predictable**
    - Number in to_remove equals max(0, unprotected_count - max_snapshots)
    - **Validates: Requirements 11.6**

  - [ ]* 3.6 Write property test: Retention idempotency (Property 14)
    - **Property 14: Retention idempotency**
    - Running compute_retention() twice with same inputs produces identical RetentionDecision
    - **Validates: Requirements 3.5, 11.5**

  - [ ]* 3.7 Write unit tests for RetentionEngine
    - Create `the_door/tests/unit/core/timeline/test_retention_engine.py`
    - Test: all protected (none removed), all unprotected (oldest removed), mixed, enabled=false (none removed), max_snapshots=0 (all unprotected removed), max_snapshots > count (none removed), empty list, single snapshot
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

- [x] 4. Extend SnapshotStore with delete_snapshot
  - [x] 4.1 Add delete_snapshot method to SnapshotStore
    - Extend `the_door/src/the_door/core/diff/snapshot_store.py`
    - Implement `delete_snapshot(version_id: str) -> None` — delete `{version_id}.json` from snapshots dir; silently ignore if file doesn't exist (idempotent)
    - _Requirements: 4.7_

  - [ ]* 4.2 Write unit tests for delete_snapshot
    - Create `the_door/tests/unit/core/diff/test_snapshot_store_delete.py`
    - Test: delete existing file removes it, delete non-existent file is silent, deleted snapshot no longer in list_snapshots, delete then delete again is silent
    - _Requirements: 4.7_

- [x] 5. Checkpoint — Verify core engines and SnapshotStore extension
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement TimelineRenderer
  - [x] 6.1 Implement TimelineRenderer
    - Create `the_door/src/the_door/core/timeline/timeline_renderer.py` with `TimelineRenderer` class
    - Define `TIMELINE_MARKERS` dict: first_seen=🟢, removed=🔴, attribute_changed=🟠, semantic_drift=🔵, unchanged=⚪
    - Implement `render_mermaid(result: TimelineResult) -> str`:
      - Emit summary panel as `%%` comments via `_render_summary_panel()`
      - Emit `gantt` chart declaration with dateFormat
      - Use sections per feature, tasks per version state with marker prefixes
      - Semantic drift events get 🔵 marker + hint text
    - Implement `render_text(result: TimelineResult) -> str`:
      - Header: `=== 功能演進時間軸 ===`
      - Stats line: snapshot count, time range, active/removed/drift counts
      - Table: feature name, first_seen, change_count, state, drift count
      - Drift detail lines with 🔵 prefix
      - Sort by first_seen_timestamp ascending
    - Implement `render_feature_detail(feature_timeline, snapshots) -> str`:
      - Per-version detail: commit_hash, git_tags, label, description, confidence, source_node_count, state marker
      - Side-by-side description comparison for drift events
    - Import `escape_mermaid_label` from `core/rendering/mermaid_utils.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 8.1, 8.2, 8.3, 8.4_

  - [ ]* 6.2 Write property test: Timeline result serialization round-trip (Property 15)
    - **Property 15: Timeline result serialization round-trip**
    - Serializing TimelineResult to JSON and deserializing back produces equivalent object
    - Add to `the_door/tests/property/test_timeline_properties.py`
    - **Validates: Requirements 9.3**

  - [ ]* 6.3 Write property test: Mermaid rendering contains all features (Property 16)
    - **Property 16: Mermaid rendering contains all features**
    - Rendered Mermaid text contains a reference to every feature_id in feature_timelines
    - **Validates: Requirements 5.1**

  - [ ]* 6.4 Write property test: Text output contains all feature information (Property 17)
    - **Property 17: Text output contains all feature information**
    - Rendered text contains each feature's current_label (or feature_id), change_count, and current_state; drift features also have drift details
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 6.5 Write property test: Text output ordering (Property 18)
    - **Property 18: Text output ordering**
    - Features in rendered text appear in ascending order of first_seen_timestamp
    - **Validates: Requirements 6.3**

  - [ ]* 6.6 Write unit tests for TimelineRenderer
    - Create `the_door/tests/unit/core/timeline/test_timeline_renderer.py`
    - Test: Mermaid syntax correctness (gantt declaration, sections, tasks), summary panel content, marker prefixes (🟢/🔴/🟠/🔵/⚪), escape_mermaid_label usage, text format header/stats/table, drift detail lines, feature detail output with version-by-version info, empty result rendering, single feature rendering
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 8.1, 8.2, 8.3, 8.4_

- [x] 7. Checkpoint — Verify TimelineRenderer
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement CLI commands
  - [x] 8.1 Implement timeline CLI command
    - Create `the_door/src/the_door/cli/timeline_cmd.py`
    - Implement `@click.command("timeline")` with:
      - `codebase_path` positional argument (`click.Path(exists=True)`)
      - `--render` flag — output Mermaid timeline chart
      - `--json` flag — output full TimelineResult JSON
      - `--feature <feature_id>` — show single feature detail
      - `--since <date>` — filter snapshots after ISO 8601 date
      - `-o/--output <file>` — write to file (UTF-8 encoding)
    - Wire: SnapshotStore.list_snapshots() → filter by --since → TimelineEngine.analyze() → TimelineRenderer → output
    - Handle --feature: call analyze_feature(), if None show error + available feature_ids
    - Handle no snapshots: display guidance message
    - Handle --since parse error: display format hint
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 8.2 Implement snapshot prune CLI subcommand
    - Extend `the_door/src/the_door/cli/snapshot_cmd.py`
    - Add `@snapshot_group.command("prune")` with:
      - `codebase_path` positional argument (default ".")
      - `--dry-run` flag — show what would be deleted without deleting
      - `--force` flag — skip confirmation
      - `--max <N>` — override max_snapshots for this run
    - Wire: SnapshotStore.list_snapshots() → load retention-config.json from `.the-door/retention-config.json`（若不存在則使用預設值 max_snapshots=50, enabled=true；格式錯誤則 warning log + 預設值）→ RetentionEngine.compute_retention() → display to_remove list → confirm (unless --force) → SnapshotStore.delete_snapshot() for each
    - Handle: no snapshots to prune message, user cancellation, dry-run output
    - _Requirements: 3.7, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 8.3 Register timeline command in main.py
    - Import `timeline_cmd` in `the_door/src/the_door/cli/main.py`
    - Register via `main.add_command(timeline_cmd)`
    - _Requirements: 7.1_

  - [ ]* 8.4 Write unit tests for timeline CLI command
    - Create `the_door/tests/unit/cli/test_timeline_cmd.py`
    - Test with click.testing.CliRunner: default text output, --render flag, --json flag, --feature with valid/invalid id, --since with valid/invalid date, -o file output, no snapshots message
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 8.5_

  - [ ]* 8.5 Write unit tests for snapshot prune CLI subcommand
    - Create `the_door/tests/unit/cli/test_snapshot_prune_cmd.py`
    - Test with click.testing.CliRunner: --dry-run shows list without deleting, --force skips confirmation, --max override, no-prune-needed message, user cancellation
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 9. Checkpoint — Verify CLI commands
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement MCP tools
  - [x] 10.1 Implement timeline MCP tool
    - Create `the_door/src/the_door/mcp/tools/timeline_tool.py`
    - Define `TOOL_SCHEMA` with required: codebase_path; optional: feature_id, since
    - Implement `async def execute(arguments)` — wire SnapshotStore + TimelineEngine + optional feature filter + since filter
    - Return TimelineResult JSON (serialized with ensure_ascii=False)
    - Return structured error responses: no snapshots, invalid feature_id (with available list), invalid since date
    - _Requirements: 12.1, 12.3_

  - [x] 10.2 Implement snapshot_prune MCP tool
    - Create `the_door/src/the_door/mcp/tools/snapshot_prune_tool.py`
    - Define `TOOL_SCHEMA` with required: codebase_path; optional: dry_run (default True), max_snapshots
    - Implement `async def execute(arguments)` — wire SnapshotStore + RetentionEngine + retention-config.json loading
    - Default dry_run=True for MCP safety
    - When dry_run=False, actually delete via SnapshotStore.delete_snapshot()
    - Return RetentionDecision JSON (to_retain + to_remove lists)
    - _Requirements: 12.2, 12.3_

  - [x] 10.3 Register new MCP tools in server.py
    - Import `timeline_tool` and `snapshot_prune_tool` in `the_door/src/the_door/mcp/server.py`
    - Add 2 new `Tool(...)` entries to `list_tools()`: `timeline` and `snapshot_prune`
    - Add 2 new dispatch branches to `call_tool()`
    - _Requirements: 12.1, 12.2_

  - [ ]* 10.4 Write unit tests for MCP tools
    - Create `the_door/tests/unit/mcp/test_timeline_tools.py`
    - Test: tool registration (2 new tools in list_tools), timeline execute with valid args, timeline with feature_id filter, timeline with since filter, snapshot_prune execute with dry_run=True, error responses for no snapshots/invalid feature_id/invalid date
    - _Requirements: 12.1, 12.2, 12.3_

- [x] 11. Final checkpoint — Full integration verification
  - Ensure all tests pass (existing tests + all new Phase 4 tests), ask the user if questions arise.
  - Verify no regressions in existing Phase 1–3 functionality
  - Verify existing `the-door history` command still works unchanged
  - Verify existing MCP `history` tool still works unchanged

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate 18 universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All file I/O must use `encoding="utf-8"` for Windows compatibility
- Hypothesis strategies use ASCII-only strings (cp950 encoding issue on Windows)
- The design uses Python — no language selection needed
- TimelineEngine and RetentionEngine are pure functions (no I/O) following the DiffEngine pattern
- TimelineRenderer reuses `escape_mermaid_label` from `core/rendering/mermaid_utils.py`
- MCP `snapshot_prune` defaults to `dry_run=True` for safety in MCP environments
- Retention config follows the `scope-config.json` pattern: project-level `.the-door/` config with defaults when missing. Config file is created by the user in their codebase, not by the project. CLI/MCP loads it at runtime with fallback to defaults.
