# Requirements Document

## Introduction

The Door Phase 3 — Scope Verification Layer (範圍驗核層) enables PM/SPM to pre-define sprint or release scope as a JSON file, then auto-compares the scope definition against The Door's analysis output (L1 features) to mark each feature as in-scope complete (✓), out-of-scope (⚠), or in-scope incomplete (○). When out-of-scope items are discovered, the system enters the Doubt Path (疑義路徑) — a full state machine that tracks doubts from discovery through investigation to resolution, with configurable timeout escalation to prevent doubts from being indefinitely ignored. The scope verification layer builds on the Phase 0a scope boundary protocol (docs/phase-0a/05-scope-boundary.md) and doubt path concept design (docs/phase-0a/doubt-path-concept.md), implementing the concrete state names, transition conditions, timeout values, data schema, and notification mechanism that Phase 0a left as "to be defined in Phase 3." Scope badges use label-embedded symbols (✓/⚠/○ with `<sup>scope</sup>`) per Phase 0a §5.5, NOT classDef — classDef is already occupied by diff/anomaly/vulnerability styling. Doubt tracking data is persisted as JSON files following the same `.the-door/` directory pattern established by SnapshotStore in Phase 2. This phase requires Phase 2.5 (Vulnerability Layer) to be complete.

## Glossary

- **The_Door_CLI**: The Python command-line tool that performs AST extraction, topology analysis, LLM-driven translation, output validation, Mermaid rendering, diff comparison, vulnerability scanning, and now scope verification on a target codebase
- **Scope_Definition**: A JSON file created and maintained by PM/SPM that declares which features are expected in a given sprint or release. Contains a sprint/release name, a list of expected feature IDs (referencing L1 feature_ids from analysis output), and optional metadata. Stored at a user-specified path or default `.the-door/scopes/<scope-name>.json`
- **Scope_Verifier**: The component that compares a Scope_Definition against the current L1 analysis output to classify each feature into one of three scope states: in_scope_complete, out_of_scope, or in_scope_incomplete
- **Scope_State**: One of three mutually exclusive states assigned to each feature node during scope verification: "in_scope_complete" (✓ green #28a745 — expected feature, present in analysis), "out_of_scope" (⚠ orange #fd7e14 — feature present in analysis but not in scope definition), "in_scope_incomplete" (○ gray #6c757d — expected feature, not found or partially present in analysis)
- **Scope_Badge**: A label-embedded visual indicator placed on Mermaid node labels using the format `symbol<sup>scope</sup>` per Phase 0a §5.5. Does not use classDef. Three variants: ✓ (in-scope complete), ⚠ (out-of-scope), ○ (in-scope incomplete)
- **Scope_Summary_Panel**: A Mermaid comment block displaying aggregate scope verification results: sprint/release name, counts per scope state, with "（需調查）" hint on out-of-scope items. Format per Phase 0a §5.3
- **Doubt_Path**: The complete lifecycle for tracking and resolving doubts (疑義) discovered during scope verification. Implements the three-stage process from Phase 0a doubt-path-concept.md: Identify → Track → Resolve
- **Doubt_Record**: A persistent JSON record tracking a single doubt from discovery to resolution. Contains: doubt_id, source_node (feature_id), doubt_type, current_state, created_by, created_at, assigned_to, state_history, resolution, and timeout metadata
- **Doubt_Store**: The component that persists and retrieves Doubt_Record JSON files. Follows the same `.the-door/doubts/` directory pattern as SnapshotStore uses `.the-door/snapshots/`
- **Doubt_State**: One of five states in the doubt lifecycle: "discovered" (疑義已記錄，尚未指派), "investigating" (已指派調查者，分析中), "explained" (確認為誤報或有合理解釋), "fixed" (對應問題已修正), "escalated" (需要管理層決策，已升級)
- **Timeout_Escalation**: An automatic mechanism that transitions a doubt to "escalated" state when it remains in "discovered" state beyond N days without assignment, or sends a reminder/escalates when it remains in "investigating" state beyond M days without progress. N and M are configurable with defaults
- **Scope_Renderer**: The component that extends MermaidRenderer to add scope badges to node labels and generate the scope summary panel. Operates in the badge/label layer per Phase 0a §6.4, independent of classDef
- **Diff_Scope_Merged_Panel**: A combined summary panel shown when both diff and scope views are active simultaneously, following the format defined in Phase 0a §6.6: "📊 Sprint N 變更驗核" with scope-grouped diff counts
- **MCP_Server**: The Model Context Protocol server exposing The Door's core functionality as tools callable by any MCP-compatible AI medium (existing from Phase 2.5, with 11 tools)
- **Mermaid_Renderer**: The existing component that generates Mermaid diagram text from L1 and L1.5 output JSON, extended by DiffRenderer and VulnerabilityRenderer in prior phases, now extended for scope badges
- **L1_Output**: The LLM-generated feature analysis containing features with feature_id, label, description, confidence, and source_nodes — the primary data source that scope verification compares against

## Requirements

### Requirement 1: Scope Definition File Format and Parsing

**User Story:** As a PM/SPM, I want to define sprint scope in a simple JSON file listing expected feature IDs, so that the tool can automatically compare my expectations against the actual analysis output.

#### Acceptance Criteria

1. THE Scope_Verifier SHALL accept a Scope_Definition JSON file containing: a `scope_name` string (e.g., "Sprint 12"), a `features` array of objects each with a `feature_id` string and an optional `expected_label` string, and an optional `description` string
2. WHEN a valid Scope_Definition file is provided, THE Scope_Verifier SHALL parse the file and validate that the `scope_name` field is non-empty and the `features` array contains at least one entry with a non-empty `feature_id`
3. IF the Scope_Definition file contains malformed JSON, THEN THE Scope_Verifier SHALL return a descriptive parse error indicating the file path and the nature of the JSON syntax error
4. IF the Scope_Definition file is missing required fields (`scope_name` or `features`), THEN THE Scope_Verifier SHALL return a validation error listing the missing fields
5. THE Scope_Verifier SHALL validate the Scope_Definition against a JSON schema (`scope-definition.schema.json`) using jsonschema, consistent with the existing validation pattern in The Door
6. THE Scope_Verifier SHALL store Scope_Definition files in `.the-door/scopes/` by default, with the filename derived from the scope_name in kebab-case format
7. FOR ALL valid Scope_Definition JSON files, parsing into an internal Scope_Definition object and serializing back to JSON SHALL produce an equivalent document (round-trip property)

### Requirement 2: Scope Comparison Engine

**User Story:** As a PM/SPM, I want the tool to automatically compare my scope definition against the current analysis output and classify each feature, so that I can see at a glance which features are complete, missing, or unexpected.

#### Acceptance Criteria

1. WHEN a Scope_Definition and an L1_Output are provided, THE Scope_Verifier SHALL classify each feature into exactly one Scope_State using the following rules: a feature present in both the Scope_Definition and L1_Output is classified as "in_scope_complete" (✓); a feature present in L1_Output but not in the Scope_Definition is classified as "out_of_scope" (⚠); a feature present in the Scope_Definition but not in L1_Output is classified as "in_scope_incomplete" (○)
2. THE Scope_Verifier SHALL match features by `feature_id` string equality between the Scope_Definition `features[].feature_id` and L1_Output `features[].feature_id`
3. THE Scope_Verifier SHALL produce a Scope_Result containing: the scope_name, a list of Scope_Entry records (each with feature_id, scope_state, feature_label, and expected_label), and aggregate counts for each scope state
4. FOR ALL inputs, the total count of Scope_Entry records SHALL equal the count of unique feature_ids across both the Scope_Definition and L1_Output combined (no feature is lost or duplicated during classification)
5. FOR ALL inputs, every feature_id in the Scope_Definition SHALL appear exactly once in the Scope_Result, and every feature_id in the L1_Output SHALL appear exactly once in the Scope_Result (completeness property)
6. THE scope comparison SHALL be a pure function: given the same Scope_Definition and L1_Output, the Scope_Result SHALL be identical across invocations (determinism property)

### Requirement 3: Scope Badge Rendering in Mermaid

**User Story:** As a non-engineer viewing a diagram, I want to see scope status badges (✓/⚠/○) on each feature node, so that I can immediately identify which features are in scope, out of scope, or incomplete.

#### Acceptance Criteria

1. WHEN scope verification results are available, THE Scope_Renderer SHALL append a scope badge to each feature node's Mermaid label using the format `symbol<sup>scope</sup>` as defined in Phase 0a §5.5, where symbol is ✓ for in_scope_complete, ⚠ for out_of_scope, or ○ for in_scope_incomplete
2. THE Scope_Renderer SHALL NOT use Mermaid classDef for scope badges — scope information is conveyed entirely through label-embedded symbols, per Phase 0a §5.5 which states "範圍邊界標記不使用 classDef"
3. WHEN a node has both a confidence icon prefix and a scope badge, THE Scope_Renderer SHALL place the confidence icon at the beginning of the label and the scope badge at the end, following the format: `"[confidence_icon] feature_label symbol<sup>scope</sup>"`
4. WHEN scope verification results include "in_scope_incomplete" features (○) that have no corresponding node in the L1_Output, THE Scope_Renderer SHALL generate a placeholder node with the expected_label from the Scope_Definition and the ○ badge, styled with a dashed border using Mermaid inline style (`style node stroke-dasharray:5 5`) rather than classDef
5. THE scope badge rendering SHALL NOT alter the existing classDef assignments for confidence, diff, anomaly, or vulnerability styling — scope badges operate exclusively in the label/badge layer per Phase 0a §6.4 visual layering rules
6. WHEN no scope verification results are provided, THE Scope_Renderer SHALL produce output identical to the existing MermaidRenderer output (backward compatibility property)

### Requirement 4: Scope Summary Panel

**User Story:** As a PM/SPM, I want a summary panel at the top of the diagram showing aggregate scope verification counts, so that I can quickly assess overall sprint scope status without examining individual nodes.

#### Acceptance Criteria

1. WHEN scope verification results are available, THE Scope_Renderer SHALL generate a scope summary panel as Mermaid comment lines at the top of the diagram output, following the format defined in Phase 0a §5.3
2. THE scope summary panel SHALL include: the scope_name as the title (e.g., "📋 Sprint 12 範圍驗核"), a count line for each scope state using the corresponding symbol prefix (✓ 範圍內已完成：N 個功能, ⚠ 超出範圍：N 個功能（需調查）, ○ 範圍內未完成：N 個功能)
3. WHEN the out-of-scope count is zero, THE scope summary panel SHALL omit the ⚠ line rather than displaying "⚠ 超出範圍：0 個功能"
4. WHEN the in-scope-incomplete count is zero, THE scope summary panel SHALL omit the ○ line rather than displaying "○ 範圍內未完成：0 個功能"
5. THE scope summary panel counts SHALL be consistent with the Scope_Result aggregate counts produced by the Scope_Verifier (summary matches detail)

### Requirement 5: Diff and Scope Merged Summary Panel

**User Story:** As a PM/SPM viewing a diff diagram with scope verification, I want a merged summary panel that combines diff changes and scope status, so that I can see both what changed and whether changes align with the sprint plan.

#### Acceptance Criteria

1. WHEN both diff results and scope verification results are available, THE Scope_Renderer SHALL generate a merged summary panel following the format defined in Phase 0a §6.6: "📊 Sprint N 變更驗核" with scope-grouped diff counts
2. THE merged summary panel SHALL group diff changes by scope state: "✓ 範圍內變更：N 個（M 新增、K 修改）", "⚠ 範圍外變更：N 個（需調查）", "○ 預期變更缺失：N 個（尚未完成）"
3. WHEN both diff and scope views are active, THE Scope_Renderer SHALL generate the merged panel instead of separate diff and scope panels, per Phase 0a §6.6 which specifies that the merged panel replaces the independent panels in combined view
4. THE merged panel counts SHALL be consistent with both the DiffResult summary and the Scope_Result: every changed node appears in exactly one scope category, and the total across categories equals the total changed count plus incomplete count

### Requirement 6: Doubt Path State Machine — State Definitions and Transitions

**User Story:** As a PM/SPM, I want a formal state machine that tracks doubts from discovery through resolution, so that every out-of-scope or suspicious item has a clear lifecycle and cannot be silently ignored.

#### Acceptance Criteria

1. THE Doubt_Path SHALL implement six states: "discovered" (疑義已記錄), "investigating" (調查中), "explained" (已解釋 — 確認為誤報), "fixed" (已修復 — 問題已修正), "escalated" (已升級 — 需管理層決策), "accepted_risk" (已接受風險 — 管理層決定不處理)
2. THE Doubt_Path SHALL enforce the following valid state transitions: discovered → investigating (assign investigator), discovered → escalated (timeout or manual escalation), investigating → explained (investigator confirms false alarm), investigating → fixed (code issue corrected), investigating → escalated (needs management decision or timeout), escalated → explained (management confirms false alarm), escalated → fixed (management approves fix), escalated → accepted_risk (management accepts risk and closes doubt)
3. IF a state transition is attempted that is not in the valid transitions list, THEN THE Doubt_Store SHALL reject the transition and return an error indicating the current state and the invalid target state
4. THE Doubt_Path SHALL record each state transition in the Doubt_Record's state_history array, including: from_state, to_state, timestamp (ISO8601 UTC), actor (who triggered the transition), and an optional reason string
5. THE "explained", "fixed", and "accepted_risk" states SHALL be terminal states: no further transitions are permitted from these states
6. FOR ALL valid transition sequences, the state_history array length SHALL equal the number of transitions performed, and the final entry's to_state SHALL match the Doubt_Record's current_state (state history consistency property)

### Requirement 7: Doubt Record Persistence

**User Story:** As a PM/SPM, I want doubt records to be persisted as JSON files, so that doubt tracking survives across sessions and can be reviewed at any time.

#### Acceptance Criteria

1. THE Doubt_Store SHALL persist each Doubt_Record as a JSON file in the `.the-door/doubts/` directory, with the filename `<doubt_id>.json`, following the same pattern as SnapshotStore uses `.the-door/snapshots/`
2. THE Doubt_Store SHALL generate a UUID v4 as the doubt_id when creating a new Doubt_Record
3. THE Doubt_Record JSON SHALL contain: doubt_id, source_node (the feature_id that triggered the doubt), doubt_type (one of: "out_of_scope", "in_scope_incomplete", "anomaly", "low_confidence"), current_state, created_by, created_at (ISO8601 UTC), assigned_to (nullable), updated_at (ISO8601 UTC), state_history array, and resolution (nullable object with type, description, resolved_by, resolved_at)
4. THE Doubt_Store SHALL write all JSON files with UTF-8 encoding to ensure Windows compatibility
5. THE Doubt_Store SHALL validate Doubt_Record JSON against a `doubt-record.schema.json` schema using jsonschema before persisting
6. FOR ALL valid Doubt_Record objects, serializing to JSON and deserializing back SHALL produce an equivalent Doubt_Record (round-trip property)
7. WHEN loading a Doubt_Record from disk, THE Doubt_Store SHALL validate the JSON against the schema and return a descriptive error if the file is corrupted or does not conform

### Requirement 8: Timeout Escalation Mechanism

**User Story:** As a PM/SPM, I want doubts that remain unaddressed for too long to be automatically escalated, so that no doubt is silently forgotten or indefinitely deferred.

#### Acceptance Criteria

1. WHEN a Doubt_Record has been in "discovered" state for longer than the configured discovery_timeout_days (default: 3 days), THE Doubt_Store SHALL transition the doubt to "escalated" state with the actor set to "system_timeout" and the reason set to "Auto-escalated: no investigator assigned within N days"
2. WHEN a Doubt_Record has been in "investigating" state for longer than the configured investigation_timeout_days (default: 7 days) without a state_history update, THE Doubt_Store SHALL transition the doubt to "escalated" state with the actor set to "system_timeout" and the reason set to "Auto-escalated: no progress in M days"
3. THE timeout check SHALL be performed when doubts are listed or queried (lazy evaluation), not by a background daemon, to keep the system simple and avoid requiring a running process
4. THE discovery_timeout_days and investigation_timeout_days SHALL be configurable as project-level defaults stored in `.the-door/scope-config.json` (default: discovery_timeout_days=3, investigation_timeout_days=7). Per-doubt overrides are not supported in Phase 3.
5. WHEN a doubt is manually transitioned to "investigating" before the discovery timeout expires, THE discovery timeout SHALL be cancelled (the doubt is no longer eligible for discovery-based auto-escalation)
6. THE timeout calculation SHALL use UTC timestamps and compare against the current UTC time, ensuring consistent behavior across time zones

### Requirement 9: Doubt Creation from Scope Verification

**User Story:** As a PM/SPM, I want out-of-scope features to automatically create doubt records, so that every unexpected change enters the tracking system without manual intervention.

#### Acceptance Criteria

1. WHEN scope verification identifies a feature as "out_of_scope" (⚠), THE Scope_Verifier SHALL automatically create a Doubt_Record with doubt_type "out_of_scope", source_node set to the feature_id, current_state "discovered", and created_by set to "scope_verification"
2. WHEN scope verification identifies a feature as "in_scope_incomplete" (○), THE Scope_Verifier SHALL automatically create a Doubt_Record with doubt_type "in_scope_incomplete", source_node set to the feature_id, current_state "discovered", and created_by set to "scope_verification"
3. IF a Doubt_Record already exists for the same source_node and doubt_type and is not in a terminal state, THEN THE Scope_Verifier SHALL NOT create a duplicate doubt — the existing active doubt takes precedence
4. THE Scope_Verifier SHALL return the list of newly created Doubt_Records alongside the Scope_Result, so that the caller can report which doubts were opened

### Requirement 10: Doubt Listing and Querying

**User Story:** As a PM/SPM, I want to list and filter active doubts, so that I can review the current state of all open issues and prioritize investigation.

#### Acceptance Criteria

1. THE Doubt_Store SHALL provide a method to list all Doubt_Records, optionally filtered by: current_state (one or more states), doubt_type (one or more types), source_node (specific feature_id), and active_only (exclude terminal states)
2. THE Doubt_Store SHALL return Doubt_Records sorted by created_at in descending order (newest first) by default
3. WHEN listing doubts, THE Doubt_Store SHALL first check and apply timeout escalation for all eligible doubts before returning results (lazy timeout evaluation per Requirement 8 AC3)
4. THE Doubt_Store SHALL provide a method to retrieve a single Doubt_Record by doubt_id, returning the record or an error if not found
5. THE Doubt_Store SHALL provide a summary method returning aggregate counts: total active doubts, count per state, count per doubt_type

### Requirement 11: Doubt State Transition Operations

**User Story:** As a team member, I want to transition doubts through their lifecycle states (assign, explain, fix, escalate), so that doubts progress toward resolution.

#### Acceptance Criteria

1. THE Doubt_Store SHALL provide an `assign` operation that transitions a doubt from "discovered" to "investigating", setting the assigned_to field and recording the transition in state_history
2. THE Doubt_Store SHALL provide an `explain` operation that transitions a doubt from "investigating" to "explained", setting the resolution object with type "explained", a description, and the resolver identity
3. THE Doubt_Store SHALL provide a `fix` operation that transitions a doubt from "investigating" to "fixed", setting the resolution object with type "fixed", a description, and the resolver identity
4. THE Doubt_Store SHALL provide an `escalate` operation that transitions a doubt from "discovered" or "investigating" to "escalated", recording the escalation reason in state_history
5. THE Doubt_Store SHALL provide a `resolve_escalation` operation that transitions a doubt from "escalated" to one of: "explained" (management confirms false alarm), "fixed" (management approves fix), or "accepted_risk" (management accepts risk)
6. WHEN any transition operation is invoked, THE Doubt_Store SHALL persist the updated Doubt_Record to disk immediately, ensuring crash safety
7. IF a transition operation is invoked on a doubt in a terminal state, THEN THE Doubt_Store SHALL return an error indicating that the doubt is already resolved and cannot be transitioned

### Requirement 12: Scope Verification CLI Command

**User Story:** As a PM/SPM, I want a CLI command to run scope verification against a scope definition file, so that I can check sprint scope status from the command line.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL provide a command `the-door scope verify <codebase-path> --scope <scope-file>` that loads the Scope_Definition from the specified scope file (or from `.the-door/scopes/` if a scope name is given), loads the most recent L1 analysis output from the codebase path, runs scope comparison, and outputs the Scope_Result
2. THE `the-door scope verify` command SHALL output a human-readable scope summary to stdout by default, showing the scope_name, counts per scope state, and a list of out-of-scope and incomplete features
3. THE `the-door scope verify` command SHALL support a `--json` flag that outputs the full Scope_Result as JSON for programmatic consumption
4. THE `the-door scope verify` command SHALL support a `--render` flag that outputs a Mermaid diagram with scope badges applied to all feature nodes
5. IF no L1 analysis output exists for the target codebase, THEN THE `the-door scope verify` command SHALL display an error message instructing the user to run `the-door analyze` first
6. THE `the-door scope verify` command SHALL write output files with UTF-8 encoding to ensure Windows compatibility

### Requirement 13: Scope Definition Management CLI Commands

**User Story:** As a PM/SPM, I want CLI commands to create and manage scope definition files, so that I can define sprint scope without manually editing JSON.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL provide a command `the-door scope create <scope-name>` that creates a new Scope_Definition file with the given scope_name and an empty features array, stored in `.the-door/scopes/<scope-name>.json`
2. THE `the-door scope create` command SHALL list available feature_ids and labels from the most recent L1 analysis output for PM reference, but SHALL NOT auto-populate the features array — PM manually adds desired feature_ids to the scope file
3. THE The_Door_CLI SHALL provide a command `the-door scope list` that lists all Scope_Definition files in `.the-door/scopes/` with their scope_name and feature count
4. THE The_Door_CLI SHALL provide a command `the-door scope show <scope-name>` that displays the contents of a specific Scope_Definition file in human-readable format

### Requirement 14: Doubt Management CLI Commands

**User Story:** As a PM/SPM or team member, I want CLI commands to view and manage doubts, so that I can track and resolve doubts from the command line.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL provide a command `the-door doubt list` that displays all active doubts with their doubt_id (abbreviated to 8 characters), source_node, doubt_type, current_state, created_at, and assigned_to
2. THE `the-door doubt list` command SHALL support `--state <state>` and `--type <type>` filters to narrow the output
3. THE `the-door doubt list` command SHALL support a `--json` flag for programmatic consumption
4. THE The_Door_CLI SHALL provide a command `the-door doubt show <doubt-id>` that displays the full Doubt_Record including state_history and resolution details
5. THE The_Door_CLI SHALL provide a command `the-door doubt assign <doubt-id> <assignee>` that transitions the doubt to "investigating" state
6. THE The_Door_CLI SHALL provide a command `the-door doubt resolve <doubt-id> --as <explained|fixed|accepted_risk> --reason <reason>` that resolves the doubt with the specified resolution type and reason. The `--as explained` and `--as fixed` options require the doubt to be in "investigating" state; the `--as accepted_risk` option requires the doubt to be in "escalated" state.
7. THE The_Door_CLI SHALL provide a command `the-door doubt escalate <doubt-id> --reason <reason>` that manually escalates a doubt to management
8. ALL doubt CLI commands SHALL write output with UTF-8 encoding to ensure Windows compatibility

### Requirement 15: MCP Server Scope and Doubt Tools

**User Story:** As an AI medium developer, I want MCP tools for scope verification and doubt management, so that MCP clients can perform scope checks and manage doubts programmatically.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `scope_verify` tool that accepts a scope definition file path and an optional codebase path, runs scope verification, and returns the Scope_Result as JSON
2. THE MCP_Server SHALL expose a `scope_create` tool that accepts a scope_name and an optional from_analysis flag, creates a Scope_Definition file, and returns the file path
3. THE MCP_Server SHALL expose a `doubt_list` tool that accepts optional state and type filters and returns the list of Doubt_Records as JSON
4. THE MCP_Server SHALL expose a `doubt_transition` tool that accepts a doubt_id, target_state, actor, and optional reason/assignee, performs the state transition, and returns the updated Doubt_Record
5. WHEN an MCP tool encounters an error (invalid scope file, doubt not found, invalid transition), THE MCP_Server SHALL return a structured response with an error message, consistent with the existing MCP error handling pattern

### Requirement 16: Scope Verification with Diff Coexistence

**User Story:** As a PM/SPM viewing a diff diagram, I want scope badges and diff markers to coexist correctly on the same nodes, so that I can see both what changed and whether changes align with the sprint plan.

#### Acceptance Criteria

1. WHEN rendering a diff diagram with scope verification results, THE Scope_Renderer SHALL apply scope badges in the label layer and diff classDefs in the classDef layer, per Phase 0a §6.5 multi-indicator priority rules
2. THE scope badge SHALL appear at the end of the node label after the diff symbol, following the format: `"[confidence_icon] [diff_symbol] feature_label symbol<sup>scope</sup>"`
3. WHEN a node is marked as diff "added" (+) and scope "out_of_scope" (⚠), THE Scope_Renderer SHALL render both indicators: the diff_added classDef for fill color and the ⚠ scope badge in the label, representing "a new feature that was not in the sprint plan"
4. WHEN a node is marked as diff "unchanged" and scope "in_scope_incomplete" (○), THE Scope_Renderer SHALL render the unchanged classDef and the ○ scope badge, representing "an expected feature that has not changed (still incomplete)"
5. THE scope badge rendering SHALL NOT interfere with vulnerability markers (⚑): when both are present, the label format SHALL be `"[confidence_icon] [vuln_symbol] [diff_symbol] feature_label scope_badge"`

### Requirement 17: Scope Verification JSON Schema

**User Story:** As a developer, I want formal JSON schemas for scope definitions and doubt records, so that data integrity is enforced and validated consistently.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL include a `scope-definition.schema.json` in the schemas directory that validates Scope_Definition files, requiring: scope_name (non-empty string), features (non-empty array of objects with feature_id string and optional expected_label string), and optional description string
2. THE The_Door_CLI SHALL include a `doubt-record.schema.json` in the schemas directory that validates Doubt_Record files, requiring: doubt_id (UUID format), source_node (string), doubt_type (enum), current_state (enum), created_by (string), created_at (ISO8601), state_history (array), and optional fields for assigned_to, resolution, and timeout_config
3. ALL schemas SHALL use JSON Schema Draft 2020-12, consistent with the existing schemas in The Door

### Requirement 18: Scope Verification Correctness Properties

**User Story:** As a developer, I want the scope verification and doubt tracking pipeline to satisfy formal correctness properties, so that scope data and doubt lifecycle are consistent and trustworthy.

#### Acceptance Criteria

1. FOR ALL valid Scope_Definition and L1_Output pairs, the Scope_Result SHALL classify every feature_id from both inputs exactly once — no feature is lost, duplicated, or left unclassified (partition property: in_scope_complete ∪ out_of_scope ∪ in_scope_incomplete = all feature_ids, and the three sets are disjoint)
2. FOR ALL valid Scope_Definition JSON files, parsing and re-serializing SHALL produce an equivalent JSON document (round-trip property for scope definitions)
3. FOR ALL valid Doubt_Record objects, serializing to JSON and deserializing back SHALL produce an equivalent Doubt_Record (round-trip property for doubt records)
4. FOR ALL Doubt_Records, the state_history array SHALL form a valid path through the state machine: each consecutive (from_state, to_state) pair SHALL be a valid transition as defined in Requirement 6 AC2 (state machine path validity)
5. FOR ALL Doubt_Records in a terminal state ("explained", "fixed", "accepted_risk"), the resolution field SHALL be non-null and contain a valid resolution type, description, resolved_by, and resolved_at (terminal state completeness)
6. THE scope comparison function SHALL be idempotent: running scope verification twice with the same inputs SHALL produce identical Scope_Results (idempotence property)
7. FOR ALL timeout checks, a doubt that has been in "discovered" state for exactly discovery_timeout_days SHALL be escalated, and a doubt that has been in "discovered" state for discovery_timeout_days minus one second SHALL NOT be escalated (timeout boundary correctness)
