# Implementation Plan: Phase 2 Diff Engine

## Overview

Implement version comparison capabilities for The Door. This plan follows the dependency order: data models → shared utilities → core modules (SnapshotStore, DiffEngine, DiffRenderer) → CLI commands → MCP tools → integration hooks. Each task includes tests alongside implementation. Property-based tests use Hypothesis with `@settings(max_examples=100)` and ASCII-only strings on Windows.

## Tasks

- [x] 1. Define Phase 2 data models and JSON schemas
  - [x] 1.1 Add diff engine dataclasses to models.py
    - Add 9 new frozen dataclasses to `src/the_door/models.py`: `FeatureSummary`, `BlockSummary`, `RelationSummary`, `BaselineInfo`, `VersionSnapshot`, `NodeDiff`, `EdgeDiff`, `DiffSummary`, `DiffResult`
    - Add custom exception classes: `SnapshotError`, `SnapshotNotFoundError`, `DiffError`
    - Follow existing conventions: `frozen=True`, `field(default_factory=...)` for mutable defaults
    - _Requirements: 1.1, 3.5, 4.5, 5.4, 10.1, 10.2_

  - [x] 1.2 Create JSON schema files
    - Create `schemas/snapshot.schema.json` (Draft 2020-12) with required fields: version_id, timestamp, trigger, l1_snapshot, analyzed_files; optional: commit_hash, git_tags, label, l1_5_snapshot, feature_relations_snapshot; conditional: label required when trigger is "manual"
    - Create `schemas/diff-result.schema.json` (Draft 2020-12) with: baseline_info, current_info, node_diffs, edge_diffs, summary; use `$defs/version_info` for shared structure
    - _Requirements: 10.1, 10.2_

  - [ ]* 1.3 Write property tests for JSON round-trip and schema compliance
    - **Property 14: Snapshot and DiffResult JSON round-trip** — serializing to JSON and deserializing back produces equivalent objects
    - **Property 15: Snapshot and DiffResult schema compliance** — serialized JSON validates against respective schemas
    - Create `tests/property/test_diff_properties.py` with shared Hypothesis strategies (`feature_summaries`, `version_snapshots`, etc.)
    - **Validates: Requirements 10.1, 10.2, 10.3**

  - [ ]* 1.4 Write unit tests for data models
    - Create `tests/unit/core/diff/` directory with `__init__.py`
    - Test frozen immutability, default factory values, field types
    - Test exception classes: `SnapshotNotFoundError` stores reference and available list
    - _Requirements: 10.1, 10.2_

- [x] 2. Extract shared Mermaid utility
  - [x] 2.1 Create mermaid_utils.py with shared escape function
    - Create `src/the_door/core/rendering/mermaid_utils.py`
    - Extract `escape_mermaid_label()` as a module-level function (same logic as `MermaidRenderer._escape_label`)
    - Refactor `MermaidRenderer._escape_label` to delegate to `escape_mermaid_label()` from `mermaid_utils` (backward compatible)
    - Verify all existing tests still pass after refactor
    - _Requirements: 6.6 (valid Mermaid syntax depends on proper escaping)_

- [x] 3. Implement SnapshotStore
  - [x] 3.1 Create core/diff package and implement SnapshotStore
    - Create `src/the_door/core/diff/__init__.py`
    - Create `src/the_door/core/diff/snapshot_store.py` with `SnapshotStore` class
    - Implement `__init__(project_root)` — sets up `.the-door/snapshots/` directory
    - Implement `create_snapshot(...)` — generates UUID v4 version_id, ISO8601 timestamp, persists as JSON with `encoding="utf-8"`
    - Implement `get_snapshot(version_id)` — loads by version_id, returns None if not found
    - Implement `get_latest()` — returns most recent snapshot by timestamp
    - Implement `resolve_baseline(reference)` — priority: ISO 8601 date → git tag/commit SHA → manual label; raises `SnapshotNotFoundError` with available snapshots on failure
    - Implement `list_snapshots()` — returns all snapshots sorted by timestamp descending
    - Handle corrupted JSON files gracefully (skip + log warning)
    - Support abbreviated commit SHA matching (≥7 characters)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ]* 3.2 Write property tests for SnapshotStore
    - **Property 16: Date-based lookup returns most recent on or before** — for any set of snapshots and query date, returns the snapshot with most recent timestamp ≤ query date
    - **Property 17: Snapshot list ordering** — listing snapshots returns them sorted by timestamp descending
    - **Validates: Requirements 2.3, 9.3**

  - [ ]* 3.3 Write unit tests for SnapshotStore
    - Create `tests/unit/core/diff/test_snapshot_store.py`
    - Test: create auto-snapshot with git info, create manual snapshot with label, git fallback (commit_hash=null), UTF-8 encoding, error on no analysis output, file persistence, resolve by git tag, resolve by commit SHA (full + abbreviated), resolve by date, resolve by label, Unicode labels, multiple matches use most recent, not-found error with available list
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 4. Checkpoint — Verify models, schemas, utility extraction, and SnapshotStore
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement DiffEngine
  - [x] 5.1 Implement DiffEngine with L1 and L1.5 diff computation
    - Create `src/the_door/core/diff/diff_engine.py` with `DiffEngine` class
    - Implement `compute_l1_diff(baseline, current)` — pure function, no I/O:
      - Match features by `feature_id`
      - Classify: added (in current only), removed (in baseline only), attribute_changed (label/description differs), unchanged
      - Compare `feature_relations_snapshot` edges by `(from_feature, to_feature)` composite key
      - Upgrade unchanged → dependency_changed when edges change
      - Apply priority: added > removed > dependency_changed > attribute_changed
      - Record attribute changes in `secondary_changes` when dependency_changed takes priority
      - Compute `DiffSummary` counts
    - Implement `compute_l1_5_diff(baseline, current)` — same algorithm on blocks using `block_id`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 11.1, 11.2_

  - [ ]* 5.2 Write property tests for DiffEngine core properties
    - **Property 1: Diff symmetry** — diff(A,B) added ↔ diff(B,A) removed; attribute_changed/dependency_changed same in both directions
    - **Property 2: Self-diff idempotency** — diff(S,S) produces all unchanged, zero counts
    - **Property 3: Count consistency** — added + removed + dep_changed + attr_changed = total_changed
    - **Property 4: Exclusive single classification** — every node has exactly one diff_state
    - **Validates: Requirements 3.1, 3.6, 5.4, 13.1, 13.2, 13.3**

  - [ ]* 5.3 Write property tests for DiffEngine classification rules
    - **Property 5: Node classification correctness** — identical label+description → unchanged; different → attribute_changed (or dependency_changed if edges also changed)
    - **Property 6: Dependency change priority** — both attribute + edge changes → dependency_changed with secondary_changes populated
    - **Property 7: Added/removed exclusivity** — added/removed nodes have secondary_changes=None
    - **Validates: Requirements 3.3, 3.4, 4.3, 4.4, 5.1, 5.2, 5.3**

  - [ ]* 5.4 Write unit tests for DiffEngine
    - Create `tests/unit/core/diff/test_diff_engine.py`
    - Test specific examples: feature added, feature removed, label changed, description changed, edge added/removed/modified, dependency_changed upgrade, priority rules, L1.5 block diff, infrastructure block diff
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 11.1, 11.2_

- [x] 6. Implement DiffRenderer
  - [x] 6.1 Implement DiffRenderer with L1 and L1.5 rendering
    - Create `src/the_door/core/diff/diff_renderer.py` with `DiffRenderer` class
    - Define `DIFF_CLASSDEFS` dict (diff_added, diff_removed, diff_dep_changed, diff_attr_changed, unchanged)
    - Define `DIFF_SYMBOLS` dict (+, −, ≠, ~)
    - Implement `render_l1_diff(diff_result, marker_context=None)`:
      - Emit summary panel as `%%` comment block via `_render_summary_panel()`
      - Emit diff classDef definitions
      - Emit node definitions with label format: `[confidence_icon] [diff_symbol] escaped_label`
      - Assign classDef per node based on diff_state (diff classDef overrides confidence)
      - Emit edge definitions with diff edge styles (green dashed for added, red dashed for removed, orange solid for modified; light gray for unchanged edges)
    - Implement `render_l1_5_diff(diff_result)` — same pattern for blocks
    - Implement `_render_summary_panel(diff_result)` — Traditional Chinese functional language, omit zero-count categories, no-change message when identical
    - Implement `_format_baseline_label(baseline_info)` — format by trigger type
    - Implement `_build_node_label(node_diff, confidence_icon)` — compose label with escaping
    - Import `escape_mermaid_label` from `core/rendering/mermaid_utils.py`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 11.3, 11.4, 12.1, 12.2, 12.3, 12.4_

  - [ ]* 6.2 Write property tests for DiffRenderer
    - **Property 8: Rendering node count preservation** — rendered Mermaid contains exactly len(node_diffs) node definitions
    - **Property 9: Rendering classDef assignment** — each node assigned correct classDef for its diff_state; diff classDefs override confidence
    - **Property 10: Rendering diff symbol prefix** — changed nodes have correct symbol prefix (+, −, ≠, ~)
    - **Property 11: Diff + confidence label format** — labels follow "[confidence_icon] [diff_symbol] node_label" format
    - **Property 12: Summary panel count accuracy** — summary counts match DiffSummary; zero-count categories omitted
    - **Property 13: Summary panel functional language** — summary uses `%%` comments and "功能" term
    - **Validates: Requirements 6.2, 6.3, 6.4, 6.7, 7.1, 7.3, 7.4, 7.5, 12.1, 12.2, 12.3, 12.4**

  - [ ]* 6.3 Write unit tests for DiffRenderer
    - Create `tests/unit/core/diff/test_diff_renderer.py`
    - Test: all 5 classDef definitions present in output, edge styles correct (green/red/orange dashed/solid), summary panel format for 3 trigger types (git ref, date, manual label), no-change message, label escaping with Mermaid-unsafe characters, confidence icon + diff symbol coexistence, unchanged node de-emphasis
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 12.1, 12.2, 12.3, 12.4_

- [x] 7. Checkpoint — Verify all core modules (SnapshotStore, DiffEngine, DiffRenderer)
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement CLI commands
  - [x] 8.1 Implement diff CLI command
    - Create `src/the_door/cli/diff_cmd.py`
    - Implement `@click.command("diff")` with:
      - `codebase_path` as positional ARGUMENT (`click.Path(exists=True)`)
      - `--baseline` (required) — baseline reference string
      - `--json` flag — output raw DiffResult JSON
      - `--layer` choice (l1/l1.5, default l1)
      - `-o/--output` — write to file instead of stdout
    - Wire: SnapshotStore → resolve_baseline + get_latest → DiffEngine → DiffRenderer → output
    - Handle errors: no snapshots, unresolvable baseline, missing layer data
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 8.2 Implement snapshot CLI commands
    - Create `src/the_door/cli/snapshot_cmd.py`
    - Implement `@click.group("snapshot")` with two subcommands:
      - `create` — positional `codebase_path` ARGUMENT (default "."), `--label` (required), creates manual snapshot from most recent analysis output
      - `list` — positional `codebase_path` ARGUMENT (default "."), displays all snapshots in human-readable table format sorted by timestamp descending
    - Handle errors: no analysis output, empty snapshot list
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 8.3 Register new CLI commands in main.py
    - Import `diff_cmd` and `snapshot_group` in `src/the_door/cli/main.py`
    - Register via `main.add_command(diff_cmd)` and `main.add_command(snapshot_group)`
    - _Requirements: 8.1, 9.1_

  - [ ]* 8.4 Write unit tests for CLI commands
    - Create `tests/unit/cli/test_diff_cmd.py` — test CLI invocation with click.testing.CliRunner, --json flag, --layer flag, -o flag, error messages for missing baseline/no snapshots
    - Create `tests/unit/cli/test_snapshot_cmd.py` — test create command, list command, table format output, empty list message
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 9.1, 9.2, 9.3, 9.4_

- [x] 9. Implement MCP tools
  - [x] 9.1 Implement diff MCP tool
    - Create `src/the_door/mcp/tools/diff_tool.py`
    - Define `TOOL_SCHEMA` with required: codebase_path, baseline; optional: format (mermaid/json), layer (l1/l1.5)
    - Implement `async def execute(arguments)` — wire SnapshotStore + DiffEngine + DiffRenderer
    - Return Mermaid text or DiffResult JSON based on format flag
    - Return structured error responses on failure
    - _Requirements: 14.1, 14.4_

  - [x] 9.2 Implement snapshot_create MCP tool
    - Create `src/the_door/mcp/tools/snapshot_create_tool.py`
    - Define `TOOL_SCHEMA` with required: codebase_path; optional: label
    - Implement `async def execute(arguments)` — create snapshot, return version_id
    - _Requirements: 14.2, 14.4_

  - [x] 9.3 Implement snapshot_list MCP tool
    - Create `src/the_door/mcp/tools/snapshot_list_tool.py`
    - Define `TOOL_SCHEMA` with required: codebase_path
    - Implement `async def execute(arguments)` — list snapshots, return list
    - _Requirements: 14.3, 14.4_

  - [x] 9.4 Register new MCP tools in server.py
    - Import `diff_tool`, `snapshot_create_tool`, `snapshot_list_tool` in `src/the_door/mcp/server.py`
    - Add 3 new `Tool(...)` entries to `list_tools()`
    - Add 3 new dispatch branches to `call_tool()`
    - _Requirements: 14.1, 14.2, 14.3_

  - [ ]* 9.5 Write unit tests for MCP tools
    - Create `tests/unit/mcp/test_diff_tools.py`
    - Test: tool registration (3 new tools appear in list_tools), execute with valid args, error responses for missing baseline/no snapshots, structured error format
    - _Requirements: 14.1, 14.2, 14.3, 14.4_

- [x] 10. Checkpoint — Verify CLI commands and MCP tools
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Integrate auto-snapshot into analyze command
  - [x] 11.1 Hook SnapshotStore into analyze_cmd
    - Modify `src/the_door/cli/analyze_cmd.py`:
      - After successful analysis output, create automatic snapshot via `SnapshotStore.create_snapshot()`
      - Extract git info (commit hash, tags) via `subprocess.run` with graceful fallback
      - Pass L1 features, feature_relations, analyzed_files, and git info to `create_snapshot()`
      - If git is unavailable, create snapshot with `commit_hash=None`, `trigger="manual"`, auto-generated label
      - Display snapshot version_id to user after creation
    - _Requirements: 1.1, 1.2_

  - [ ]* 11.2 Write unit tests for analyze_cmd auto-snapshot integration
    - Create `tests/unit/cli/test_analyze_snapshot.py`
    - Test: auto-snapshot created after successful analysis, git info captured, git fallback behavior, snapshot version_id displayed
    - _Requirements: 1.1, 1.2_

- [x] 12. Final checkpoint — Full integration verification
  - Ensure all tests pass (existing 247 + all new Phase 2 tests), ask the user if questions arise.
  - Verify no regressions in existing Phase 1 functionality
  - Verify `escape_mermaid_label` refactor is backward compatible (existing MermaidRenderer tests pass)

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (17 properties from design)
- Unit tests validate specific examples and edge cases
- All file I/O must use `encoding="utf-8"` for Windows compatibility
- Hypothesis strategies use ASCII-only strings (cp950 encoding issue on Windows)
- The design uses Python — no language selection needed
