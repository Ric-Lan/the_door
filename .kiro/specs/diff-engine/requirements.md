# Requirements Document

## Introduction

The Door Phase 2 — Diff Engine enables version comparison for The Door's code visualization output. It allows non-engineers to independently confirm "what changed between this version and the last" by comparing two L1/L1.5 snapshots and rendering the differences using the visual diff symbols defined in Phase 0a (docs/phase-0a/04-diff-symbols.md). The Diff Engine supports three "previous version" trigger methods (git tag/commit SHA, date selector, manual snapshot), computes differences across three dimensions (node added/removed, node attribute change, dependency change), and produces Mermaid diff diagrams with a natural-language summary panel. This phase builds on the complete Phase 1-full pipeline (AST extraction, topology analysis, LLM translation, narrative chain, one-click mode, Mermaid rendering with confidence markers) and the Phase 0a/0b visual specifications.

## Glossary

- **The_Door_CLI**: The Python command-line tool that performs AST extraction, topology analysis, LLM-driven translation, output validation, and Mermaid rendering on a target codebase
- **Diff_Engine**: The component that computes structural and semantic differences between two version snapshots of L1/L1.5 output, producing a diff result with change classifications
- **Version_Snapshot**: A persisted record of L1/L1.5 output at a specific point in time, stored in LOG format (spec §5.1), containing feature labels, descriptions, source node counts, confidence levels, and metadata about the snapshot trigger
- **Snapshot_Store**: The local storage layer that manages creation, retrieval, and querying of Version_Snapshot records, supporting lookup by git tag, commit SHA, date, or manual label. Also responsible for automatic snapshot creation after successful analysis.
- **Diff_Result**: The structured output of the Diff_Engine containing: lists of added nodes, removed nodes, attribute-changed nodes, dependency-changed nodes, added edges, removed edges, and modified edges, along with the comparison baseline metadata
- **Diff_Renderer**: The component that extends the existing Mermaid_Renderer to produce Mermaid diff diagrams using the Phase 0a diff visual symbols (classDefs: diff_added, diff_removed, diff_dep_changed, diff_attr_changed, unchanged) and edge diff styles
- **Diff_Summary_Panel**: A natural-language summary block rendered at the top of the diff diagram showing change counts categorized by type, using functional language accessible to non-engineers
- **Comparison_Baseline**: The "previous version" reference point for a diff operation, identified by one of three trigger methods: git tag/commit SHA, date, or manual snapshot label
- **Manual_Snapshot**: A Version_Snapshot explicitly created by the user at a chosen point in time, labeled with a human-readable name (e.g., "Sprint 12 結束快照")
- **Structure_JSON**: The standardized JSON output containing files, nodes, edges, topology, and vulnerabilities extracted from a codebase (existing from Phase 1-min)
- **L1_Output**: The LLM-generated JSON containing functional overview (features, relations, unclassified nodes, infrastructure nodes) in non-technical language (existing from Phase 1-full)
- **L1_5_Output**: The LLM-generated JSON containing structural overview (blocks, block relations, infrastructure block) with transitional language (existing from Phase 1-full)
- **Mermaid_Renderer**: The existing component that generates Mermaid diagram text from L1 and L1.5 output JSON for visualization (existing from Phase 1-full, extended by Diff_Renderer)
- **MCP_Server**: The Model Context Protocol server exposing The Door's core functionality as tools callable by any MCP-compatible AI medium (existing from Phase 1-full)

## Requirements

### Requirement 1: Version Snapshot Creation and Storage

**User Story:** As a developer using The Door, I want the system to create and persist version snapshots of L1/L1.5 analysis output — both automatically after analysis and manually on demand — so that previous versions are available for comparison when the Diff Engine runs.

#### Acceptance Criteria

1. WHEN `the-door analyze` completes successfully, THE Snapshot_Store SHALL automatically create a Version_Snapshot containing: a unique version_id, the current git commit hash (if available), associated git tags, trigger type ("commit"), ISO8601 timestamp, the complete L1 feature map (feature_id to label, description, source_node_count, confidence), the complete L1.5 block map, the analyzed file list, and the feature_relations array needed for dependency-change detection
2. IF git is not available or the codebase is not a git repository, THEN THE Snapshot_Store SHALL create the snapshot with commit_hash set to null, git_tags set to an empty array, and trigger type "manual" with an auto-generated label "Auto-snapshot YYYY-MM-DD HH:MM:SS"
3. WHEN a user invokes `the-door snapshot create --label <name>`, THE Snapshot_Store SHALL create a Manual_Snapshot from the most recent analysis output, with trigger type "manual" and the user-provided label stored in the snapshot metadata
4. THE Snapshot_Store SHALL persist Version_Snapshots as JSON files in a `.the-door/snapshots/` directory within the target codebase's project root, with filenames based on the version_id
5. IF no prior analysis output exists when snapshot creation is requested, THEN THE Snapshot_Store SHALL return a clear error message indicating that analysis must be run first
6. THE Snapshot_Store SHALL store all snapshot files with UTF-8 encoding to ensure Windows compatibility

### Requirement 2: Version Snapshot Retrieval

**User Story:** As a user of The Door, I want to retrieve a previous version snapshot by git reference, date, or manual label, so that I can use it as the comparison baseline for diff operations.

#### Acceptance Criteria

1. WHEN a user specifies a git tag as the comparison baseline, THE Snapshot_Store SHALL locate the Version_Snapshot whose git_tags array contains the specified tag
2. WHEN a user specifies a commit SHA as the comparison baseline, THE Snapshot_Store SHALL locate the Version_Snapshot whose commit_hash matches the specified SHA (supporting both full and abbreviated SHA formats of at least 7 characters)
3. WHEN a user specifies a date (ISO 8601 format YYYY-MM-DD) as the comparison baseline, THE Snapshot_Store SHALL locate the Version_Snapshot with the most recent timestamp that is on or before the specified date
4. WHEN a user specifies a manual snapshot label as the comparison baseline, THE Snapshot_Store SHALL locate the Version_Snapshot whose label matches the specified string exactly
5. THE Snapshot_Store SHALL support labels containing Unicode characters (e.g., Traditional Chinese) for international users
6. WHEN multiple snapshots match a git tag (due to re-tagging) or fall on the same date, THE Snapshot_Store SHALL use the most recently created snapshot
7. IF no Version_Snapshot matches the specified baseline reference, THEN THE Snapshot_Store SHALL return a clear error message listing available snapshots with their identifiers (git tags, commit hashes, dates, and manual labels as applicable)

### Requirement 3: L1 Node-Level Diff Computation

**User Story:** As a user of The Door, I want the Diff Engine to compute node-level differences between two L1 snapshots, so that I can see which features were added, removed, or modified.

#### Acceptance Criteria

1. THE Diff_Engine SHALL classify each L1 feature node into exactly one of four diff states: added (present in current but not in baseline), removed (present in baseline but not in current), attribute_changed (present in both but label or description differs), or unchanged
2. THE Diff_Engine SHALL match features between snapshots using feature_id as the primary key
3. WHEN a feature exists in both snapshots but its label or description has changed, THE Diff_Engine SHALL classify it as attribute_changed
4. WHEN a feature exists in both snapshots with identical label and description, THE Diff_Engine SHALL classify it as unchanged
5. THE Diff_Engine SHALL produce a Diff_Result containing separate lists for each diff state (added, removed, attribute_changed, unchanged) with the feature details from both snapshots where applicable
6. FOR ALL pairs of snapshots, diffing snapshot A against B and then diffing B against A SHALL produce symmetric results: nodes classified as "added" in one direction SHALL be classified as "removed" in the reverse direction, and vice versa (symmetry property)

### Requirement 4: Dependency-Change Diff Computation

**User Story:** As a user of The Door, I want the Diff Engine to detect changes in feature-to-feature relationships, so that I can see when the connections between features have changed even if the features themselves appear unchanged.

#### Acceptance Criteria

1. THE Diff_Engine SHALL compare the feature_relations (edges) between the baseline and current snapshots to identify: added edges (present in current but not in baseline), removed edges (present in baseline but not in current), and modified edges (same from/to pair but relation description changed)
2. THE Diff_Engine SHALL match edges between snapshots using the (from_feature, to_feature) pair as the composite key
3. WHEN a node has unchanged attributes but its incoming or outgoing edges have changed, THE Diff_Engine SHALL upgrade that node's diff state from unchanged to dependency_changed
4. WHEN a node has both attribute changes and dependency changes, THE Diff_Engine SHALL classify it as dependency_changed (dependency change takes priority over attribute change, per Phase 0a §4.2 priority rules)
5. THE Diff_Engine SHALL include edge-level diff details (added_edges, removed_edges, modified_edges) in the Diff_Result

### Requirement 5: Diff Priority Rules

**User Story:** As a user of The Door, I want diff classifications to follow a clear priority order, so that the most significant change type is always displayed when multiple changes affect the same node.

#### Acceptance Criteria

1. THE Diff_Engine SHALL apply the following priority order when a node has multiple change types: added (priority 1, highest) > removed (priority 2) > dependency_changed (priority 3) > attribute_changed (priority 4, lowest)
2. WHEN a node is classified as added or removed, THE Diff_Engine SHALL not additionally classify it as dependency_changed or attribute_changed
3. WHEN a node has both dependency changes and attribute changes, THE Diff_Engine SHALL classify it as dependency_changed and record the attribute change details in a secondary field for the side panel
4. FOR ALL nodes in a Diff_Result, each node SHALL have exactly one primary diff classification

### Requirement 6: Mermaid Diff Diagram Rendering

**User Story:** As a user of The Door, I want the diff results rendered as a Mermaid diagram using the Phase 0a visual symbols, so that I can visually identify changes at a glance.

#### Acceptance Criteria

1. THE Diff_Renderer SHALL generate Mermaid flowchart syntax that includes the five diff classDef definitions: diff_added (fill:#d4edda, stroke:#28a745), diff_removed (fill:#f8d7da, stroke:#dc3545), diff_dep_changed (fill:#f5c6a0, stroke:#e67e22), diff_attr_changed (fill:#ffe0cc, stroke:#fd7e14), and unchanged (fill:#f8f9fa, stroke:#dee2e6, color:#6c757d, stroke-dasharray:2 2)
2. THE Diff_Renderer SHALL assign each node the classDef corresponding to its primary diff classification
3. THE Diff_Renderer SHALL prefix each changed node's label with the appropriate ASCII diff symbol: "+" for added, "−" for removed, "≠" for dependency_changed, "~" for attribute_changed
4. THE Diff_Renderer SHALL render unchanged nodes with the unchanged classDef (de-emphasized: light gray fill, dashed border, gray text) so that changed nodes visually stand out
5. THE Diff_Renderer SHALL render edge-level diffs using the Phase 0a edge styles: added edges as green dashed lines (stroke:#28a745), removed edges as red dashed lines (stroke:#dc3545), and modified edges as orange solid lines (stroke:#fd7e14)
6. THE Diff_Renderer SHALL generate syntactically valid Mermaid text that passes Mermaid.js parsing without errors
7. FOR ALL Diff_Results, rendering and then parsing the Mermaid output SHALL produce valid Mermaid syntax containing exactly the same number of node definitions as there are nodes in the Diff_Result (round-trip node count preservation)

### Requirement 7: Diff Summary Panel

**User Story:** As a non-technical user, I want a natural-language summary at the top of the diff diagram showing what changed, so that I can quickly understand the scope of changes without examining every node.

#### Acceptance Criteria

1. THE Diff_Renderer SHALL include a summary panel at the top of the Mermaid diagram as a Mermaid comment block containing change counts in natural language
2. THE Diff_Summary_Panel SHALL display the comparison baseline in the appropriate format based on trigger method: "比較基準：v1.2.0 (abc1234)" for git references, "比較基準：2024-01-15 的快照" for date-based comparisons, "比較基準：Sprint 12 結束快照" for manual snapshots
3. THE Diff_Summary_Panel SHALL display counts using functional language: "新增 N 個功能 | 移除 N 個功能 | 修改 N 個功能（M 個依賴關係變更、K 個屬性變更）"
4. THE Diff_Summary_Panel SHALL use the term "功能" (feature/function) rather than technical terms like "節點" (node) or "模組" (module)
5. WHEN there are zero changes in a category, THE Diff_Summary_Panel SHALL omit that category from the summary rather than displaying "0 個"
6. WHEN the baseline and current snapshots are identical (zero changes), THE Diff_Summary_Panel SHALL display a message indicating no changes were detected

### Requirement 8: Diff CLI Command

**User Story:** As a developer, I want a CLI command to run diff comparisons, so that I can compare versions from the command line.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL provide a command `the-door diff <codebase-path> --baseline <reference>` that computes and renders the diff between the most recent snapshot (as current) and the specified baseline snapshot
2. THE `--baseline` flag SHALL accept three formats: git tag or commit SHA (e.g., `--baseline v1.2.0` or `--baseline abc1234`), date (e.g., `--baseline 2024-01-15`), or manual snapshot label (e.g., `--baseline "Sprint 12 結束快照"`)
3. THE The_Door_CLI SHALL resolve the baseline reference using the following priority order: (1) try ISO 8601 date format match, (2) try git tag or commit SHA match in the snapshot store, (3) fall back to manual snapshot label match
4. THE The_Door_CLI SHALL output the Mermaid diff diagram to stdout by default, with an optional `-o <file>` flag to write to a file
5. IF the baseline cannot be resolved or no snapshots exist, THEN THE The_Door_CLI SHALL display a clear error message with suggestions for available baselines
6. THE The_Door_CLI SHALL support a `--json` flag that outputs the raw Diff_Result as JSON instead of Mermaid text, for programmatic consumption
7. THE The_Door_CLI SHALL support a `--layer` flag accepting "l1" (default) or "l1.5" to select which layer's diff to render

### Requirement 9: Snapshot Management CLI Commands

**User Story:** As a developer, I want CLI commands to manage version snapshots, so that I can create manual snapshots and list available baselines.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL provide a command `the-door snapshot create --label <name>` that creates a manual snapshot from the most recent analysis output
2. THE The_Door_CLI SHALL provide a command `the-door snapshot list` that displays all available snapshots with: version_id, timestamp, trigger type, git tags (if any), commit hash (if any), and manual label (if any)
3. WHEN listing snapshots, THE The_Door_CLI SHALL sort them by timestamp in descending order (most recent first)
4. THE The_Door_CLI SHALL display snapshot list output in a human-readable table format

### Requirement 10: Diff Data Format

**User Story:** As a developer, I want the diff result and version snapshot formats to follow formal JSON schemas, so that storage, retrieval, and downstream consumption are reliable and consistent.

#### Acceptance Criteria

1. THE Version_Snapshot SHALL conform to a snapshot.schema.json schema validatable by jsonschema Draft 2020-12, defining required fields: version_id (string), timestamp (ISO8601 string), trigger (enum: "commit", "manual"), l1_snapshot (object mapping feature_id to feature summary with label, description, source_node_count, confidence), and analyzed_files (array of file paths); and optional fields: commit_hash (string or null), git_tags (array of strings), label (string, required when trigger is "manual"), l1_5_snapshot (object mapping block_id to block summary), and feature_relations_snapshot (array of relation objects for dependency-change detection)
2. THE Diff_Result SHALL conform to a diff-result.schema.json schema validatable by jsonschema Draft 2020-12, defining top-level fields: baseline_info (comparison baseline metadata), current_info (current version metadata), node_diffs (array of node-level diff entries with feature_id, diff_state, current/baseline label and description, and secondary_changes), edge_diffs (array of edge-level diff entries with from_feature, to_feature, diff_state, current/baseline relation), and summary (added_count, removed_count, dependency_changed_count, attribute_changed_count, total_changed_count)
3. FOR ALL valid Version_Snapshots and Diff_Results, serializing to JSON and deserializing back SHALL produce an equivalent object (round-trip property)

### Requirement 11: L1.5 Diff Support

**User Story:** As a user of The Door, I want the Diff Engine to also compute and render diffs for L1.5 structural overview, so that I can see structural changes alongside functional changes.

#### Acceptance Criteria

1. THE Diff_Engine SHALL compute block-level diffs for L1.5 output using the same classification scheme as L1: added, removed, attribute_changed, dependency_changed, and unchanged
2. THE Diff_Engine SHALL match L1.5 blocks between snapshots using block_id as the primary key
3. THE Diff_Renderer SHALL generate L1.5 diff diagrams using the same diff classDefs and visual symbols as L1 diff diagrams
4. WHEN rendering L1.5 diff, THE Diff_Renderer SHALL include the infrastructure_block in the diff comparison, showing whether infrastructure components were added or removed

### Requirement 12: Diff and Confidence Marker Coexistence

**User Story:** As a user of The Door, I want diff visual markers and confidence markers to coexist correctly on the same diagram, so that I can see both what changed and how confident the system is about each node.

#### Acceptance Criteria

1. WHEN rendering a diff diagram, THE Diff_Renderer SHALL assign the diff classDef to changed nodes, overriding the confidence classDef (per Phase 0a §6.2 Mermaid classDef limitation: one classDef per node, diff takes priority)
2. THE Diff_Renderer SHALL preserve confidence information for changed nodes by including the confidence icon prefix in the node label (e.g., "✓ + 訂單處理" for a high-confidence added node)
3. THE Diff_Renderer SHALL apply the unchanged classDef to unchanged nodes, overriding their confidence classDef, with confidence information preserved in the icon prefix
4. THE label format for diff nodes SHALL be: "[confidence_icon] [diff_symbol] node_label" (e.g., "✓ + 新功能名稱", "? ≠ 修改的功能"). Note: when L2 anomaly markers coexist in future phases, the format will extend to "[confidence_icon] [anomaly_symbol] [diff_symbol] node_label" per Phase 0a §6.7 rule #6.

### Requirement 13: Diff Correctness Properties

**User Story:** As a developer, I want the diff engine to satisfy formal correctness properties, so that diff results are mathematically consistent and trustworthy.

#### Acceptance Criteria

1. FOR ALL pairs of snapshots A and B, diffing A against B and then diffing B against A SHALL produce symmetric results: nodes classified as "added" in one direction SHALL be classified as "removed" in the reverse direction, and vice versa; attribute_changed and dependency_changed classifications SHALL be identical in both directions (symmetry property)
2. WHEN the baseline and current snapshots are identical, THE Diff_Engine SHALL produce a Diff_Result with zero added, removed, attribute_changed, and dependency_changed nodes, and SHALL classify all nodes as unchanged (idempotency property)
3. FOR ALL valid Diff_Results, the sum of added_count + removed_count + dependency_changed_count + attribute_changed_count SHALL equal total_changed_count (count consistency property)

### Requirement 14: MCP Server Diff Tools

**User Story:** As an AI medium developer, I want MCP tools for diff operations and snapshot management, so that MCP clients can access the full Phase 2 diff functionality.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `diff` tool that accepts a codebase path, baseline reference, and optional output format flag ("mermaid" default or "json"), and returns either the Mermaid diff diagram text or the Diff_Result JSON
2. THE MCP_Server SHALL expose a `snapshot_create` tool that accepts a codebase path and optional label, and returns the created snapshot's version_id
3. THE MCP_Server SHALL expose a `snapshot_list` tool that accepts a codebase path and returns the list of available snapshots
4. WHEN an MCP tool encounters an error (missing baseline, no snapshots), THE MCP_Server SHALL return a structured error response with a human-readable message
