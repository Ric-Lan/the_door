# Requirements Document

## Introduction

The Door Phase 1-full is the complete LLM translation engine that extends Phase 1-min into a fully functional code-to-functional-language translation system. Building on the existing AST extraction, topology analysis, output validation, MCP Server, and constraint prompts (①–⑥), Phase 1-full adds: complete L1–L2 graph output with confidence markers, full topology-guided batch reading with pruning, narrative chain (敘事鏈) JSONL persistence for cross-session continuity, regeneration trigger functionality, one-click mode (CLI built-in LLM calls with multi-provider support), API cost model estimation, and B6 constraint items ⑦–⑬ (infrastructure consolidation, L1.5/L2 output schemas, enhanced validation, source code review mechanism, anti-hallucination constraint, anti-over-interpretation constraint).

## Glossary

- **The_Door_CLI**: The Python command-line tool that performs AST extraction, topology analysis, LLM-driven translation, output validation, and Mermaid rendering on a target codebase
- **AST_Extractor**: The component using tree-sitter-language-pack to parse source code into structured JSON material without classification (existing from Phase 1-min)
- **Topology_Analyzer**: The component that computes in-degree, out-degree, topology rank, entry-point status, and batch assignment for all AST nodes (existing from Phase 1-min)
- **Output_Validator**: The component that checks LLM output against JSON schema, coverage, language constraints, anchor points, and relation layering rules (existing from Phase 1-min, extended in Phase 1-full)
- **MCP_Server**: The Model Context Protocol server exposing The Door's core functionality as tools callable by any MCP-compatible AI medium (existing from Phase 1-min)
- **Structure_JSON**: The standardized JSON output containing files, nodes, edges, topology, and vulnerabilities extracted from a codebase (existing from Phase 1-min)
- **L1_Output**: The LLM-generated JSON containing functional overview (features, relations, unclassified nodes, infrastructure nodes) in non-technical language
- **L1_5_Output**: The LLM-generated JSON containing structural overview (blocks, block relations, infrastructure block) with transitional language that bridges functional and technical perspectives
- **L2_Output**: The LLM-generated JSON containing module-level interaction details with anomaly markers (dead code, logic dead-ends, uncertain boundaries)
- **Narrative_Chain**: An append-only JSONL file recording per-batch reading history, LLM judgments, pruning decisions, and confidence changes across sessions
- **Batch_Reader**: The topology-guided reading engine that sends Structure_JSON to the LLM in batches according to batch_assignment, manages pruning of high-confidence nodes, and maintains the narrative chain
- **Pruning_Mechanism**: The logic that skips high-confidence nodes in subsequent batches to save tokens, triggered when a node reaches confidence "high" in an earlier batch
- **Regeneration_Trigger**: The mechanism allowing users to clear cached results for specific nodes and re-invoke the LLM with the same AST material to obtain a fresh translation
- **One_Click_Mode**: The CLI execution mode where The Door internally calls an LLM API (multi-provider) to complete the full analysis pipeline without requiring an external AI medium
- **LLM_Call_Layer**: The abstraction layer within the CLI that manages LLM API calls across multiple providers (OpenAI, Anthropic, Ollama/local models) with API key management and error retry
- **Source_Code_Review**: The mechanism where the system extracts original function body text for nodes marked needs_source_review and sends it to the LLM for secondary judgment
- **Confidence_Marker**: The visual indicator (high/medium/low) attached to each L1/L1.5/L2 node showing the LLM's self-assessed certainty level
- **Mermaid_Renderer**: The component that generates Mermaid diagram text from L1 and L1.5 output JSON for visualization
- **API_Cost_Model**: The estimation module that calculates approximate token consumption and API cost before executing LLM calls
- **Infrastructure_Block**: A unified L1.5 block that consolidates all infrastructure-related nodes (logging, config, DI containers) into a single structural element

## Requirements

### Requirement 1: Topology-Guided Batch Reading Engine

**User Story:** As a developer using The Door, I want the system to read AST material in topology-guided batches and send them to the LLM sequentially, so that the LLM builds understanding progressively from entry points and core logic outward.

#### Acceptance Criteria

1. WHEN one-click mode is invoked, THE Batch_Reader SHALL send Structure_JSON nodes to the LLM in batches ordered by the topology batch_assignment field, starting with batch 1
2. THE Batch_Reader SHALL include the constraint prompt (l1-constraint.md) with each batch submission to the LLM
3. THE Batch_Reader SHALL enforce a maximum of 5 batches per analysis session
4. WHEN the batch limit is reached with unprocessed nodes remaining, THE Batch_Reader SHALL mark those nodes as unclassified with reason "information insufficient: incomplete reading"
5. THE Batch_Reader SHALL accumulate LLM responses across batches and produce a final consolidated L1 and L1.5 output after the last batch completes
6. WHEN a node receives confidence "high" in batch N, THE Batch_Reader SHALL exclude that node's downstream dependencies from subsequent batches if those dependencies have no other pending references (pruning)

### Requirement 2: Pruning Mechanism

**User Story:** As a developer using The Door, I want high-confidence nodes to be pruned from subsequent batches, so that token consumption is reduced without sacrificing analysis quality.

#### Acceptance Criteria

1. WHEN a node is assigned confidence "high" by the LLM in any batch, THE Pruning_Mechanism SHALL mark that node as pruned for subsequent batches
2. THE Pruning_Mechanism SHALL skip pruned nodes when assembling the payload for subsequent batch submissions
3. THE Pruning_Mechanism SHALL record all pruning decisions in the Narrative_Chain with the pruned node_id and the batch number where pruning was triggered
4. IF a pruned node is later referenced by a low-confidence node in a subsequent batch, THEN THE Pruning_Mechanism SHALL re-include the pruned node's context in that batch
5. THE Pruning_Mechanism SHALL achieve token savings of at least 20% compared to sending all nodes without pruning on codebases with more than 50 nodes

### Requirement 3: Narrative Chain JSONL Persistence

**User Story:** As a developer using The Door, I want the reading history and LLM judgments to persist across sessions in JSONL format, so that analysis can be resumed and audited without re-running the entire pipeline.

#### Acceptance Criteria

1. THE Narrative_Chain SHALL be stored as a JSONL file (one JSON record per line, append-only) in the local project directory
2. WHEN a batch is processed, THE Batch_Reader SHALL append a record to the Narrative_Chain containing: batch number, strategy ("topology_guided"), nodes read (with node_id, topology_rank, in_degree, is_entry_point), LLM judgment summary, pruned nodes list, pending low-confidence nodes list, and ISO8601 timestamp
3. WHEN a new session begins on the same codebase, THE Batch_Reader SHALL read the existing Narrative_Chain and resume from the last recorded state rather than restarting from batch 1
4. THE Narrative_Chain SHALL conform to the narrative.schema.json schema
5. IF the AST structure has changed since the last Narrative_Chain entry (detected by comparing node_ids and edges), THEN THE Batch_Reader SHALL start a new analysis segment in the Narrative_Chain with a marker indicating structural change
6. THE Narrative_Chain SHALL record regeneration events when a user triggers regeneration for specific nodes

### Requirement 4: Regeneration Trigger

**User Story:** As a developer using The Door, I want to manually trigger regeneration for specific L1 nodes when the initial LLM translation appears inaccurate, so that I can obtain a fresh interpretation without re-analyzing the entire codebase.

#### Acceptance Criteria

1. WHEN a user requests regeneration for a specific feature node, THE The_Door_CLI SHALL clear the cached result for that node and re-invoke the LLM with the same AST material
2. WHEN regeneration produces a result different from the previous version, THE The_Door_CLI SHALL mark the new result with label "AI inference: regenerated, differs from previous"
3. THE The_Door_CLI SHALL record the regeneration event in the Narrative_Chain including: the regenerated feature_id, previous result summary, new result summary, and timestamp
4. THE The_Door_CLI SHALL provide a CLI command `the-door regenerate <feature_id>` to trigger regeneration for a specific feature
5. THE The_Door_CLI SHALL preserve the previous result for comparison until the user explicitly accepts the new result

### Requirement 5: One-Click Mode — LLM Call Layer

**User Story:** As a non-technical user or CI/CD pipeline operator, I want to run a single CLI command that completes the entire analysis pipeline including LLM calls, so that no external AI medium is required.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL provide a command `the-door analyze <codebase-path>` that executes the complete pipeline: AST extraction, topology analysis, LLM batch reading, output validation, and Mermaid rendering
2. THE LLM_Call_Layer SHALL support multiple API providers: OpenAI (GPT-4 family), Anthropic (Claude family), and Ollama (local models)
3. THE LLM_Call_Layer SHALL read API credentials from a configuration file located at `~/.the-door/config.toml` or environment variables (THE_DOOR_OPENAI_KEY, THE_DOOR_ANTHROPIC_KEY, THE_DOOR_OLLAMA_URL)
4. WHEN an LLM API call fails, THE LLM_Call_Layer SHALL retry up to 3 times with exponential backoff before reporting failure
5. THE LLM_Call_Layer SHALL support switching between providers via a `--provider` CLI flag or configuration file default
6. WHEN using Ollama, THE LLM_Call_Layer SHALL connect to the local Ollama server and support model selection via `--model` flag

### Requirement 6: One-Click Mode — Configuration Management

**User Story:** As a developer, I want a clear configuration system for API keys and provider preferences, so that one-click mode works reliably across different environments.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL provide a command `the-door config init` that creates a default configuration file at `~/.the-door/config.toml`
2. THE configuration file SHALL support the following settings: default_provider, openai_api_key, openai_model, anthropic_api_key, anthropic_model, ollama_url, ollama_model, max_retries, and timeout_seconds
3. WHEN both environment variables and configuration file values exist for the same setting, THE The_Door_CLI SHALL prioritize environment variables over configuration file values
4. IF no API key is configured for the selected provider, THEN THE The_Door_CLI SHALL display a clear error message indicating which credential is missing and how to configure it
5. THE The_Door_CLI SHALL validate the configuration on startup and warn about any misconfigured or unreachable providers

### Requirement 7: API Cost Model Estimation

**User Story:** As a developer, I want to see an estimated API cost before running the full analysis, so that I can make informed decisions about whether to proceed or adjust parameters.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL provide a command `the-door estimate <codebase-path>` that calculates estimated token consumption and API cost without making actual LLM calls
2. THE API_Cost_Model SHALL estimate input tokens based on the Structure_JSON size per batch and the constraint prompt size
3. THE API_Cost_Model SHALL estimate output tokens based on expected L1/L1.5 output size proportional to node count
4. THE API_Cost_Model SHALL display cost estimates using current pricing for the configured provider (OpenAI, Anthropic) or "free (local)" for Ollama
5. WHEN the estimated cost exceeds a configurable threshold (default: $1.00 USD), THE The_Door_CLI SHALL display a warning and require explicit confirmation before proceeding in one-click mode

### Requirement 8: L1.5 Output Generation

**User Story:** As a developer using The Door, I want the LLM to produce L1.5 structural overview output alongside L1, so that users can switch between functional and structural perspectives of the same codebase.

#### Acceptance Criteria

1. WHEN one-click mode completes batch reading, THE Batch_Reader SHALL produce L1.5 output containing: blocks array, block_relations array, and infrastructure_block
2. THE L1_5_Output SHALL include for each block: block_id, label (module name with functional description), responsibility description, trigger_mechanism (human-readable), and related_features (referencing L1 feature_ids)
3. THE L1_5_Output SHALL include block_relations with: from block_id, to block_id, relation description, relation_type (static or inferred), and inferred_reason when applicable
4. THE L1_5_Output SHALL consolidate all infrastructure-related nodes into a single infrastructure_block with label "System Infrastructure" and a components list
5. THE L1_5_Output SHALL conform to the l1-5-output section of the output JSON schema validatable by jsonschema Draft 2020-12

### Requirement 9: L2 Output Generation

**User Story:** As a developer using The Door, I want the system to produce L2 module-level interaction output with anomaly detection, so that verification-oriented users can identify potential issues.

#### Acceptance Criteria

1. WHEN a user requests L2 expansion for a specific L1 feature or L1.5 block, THE The_Door_CLI SHALL send the corresponding subset of Structure_JSON nodes to the LLM with the L2 constraint prompt
2. THE L2_Output SHALL include module-level interaction details: module_id, interactions (from/to with description), and confidence markers
3. THE L2_Output SHALL include anomaly markers for: dead code (no call source and not a framework callback), logic dead-ends (unreachable paths), and uncertain boundaries (unknown purpose or call source)
4. THE L2_Output SHALL conform to the l2-output JSON schema validatable by jsonschema Draft 2020-12
5. IF the LLM identifies an anomaly, THEN THE L2_Output SHALL include the anomaly type, affected node_ids, and a human-readable explanation

### Requirement 10: Constraint Prompt ⑦ — Infrastructure Consolidation

**User Story:** As a developer using The Door, I want the LLM to consolidate infrastructure nodes into a unified block rather than scattering them across L1 features, so that the functional overview remains clean and focused on business capabilities.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL instruct the LLM to identify infrastructure nodes (logging, configuration, dependency injection containers, database connection pools, middleware pipelines) and group them into the infrastructure_nodes array
2. THE Constraint_Prompt SHALL instruct the LLM to produce a single infrastructure_block in L1.5 output that consolidates all infrastructure components
3. THE Constraint_Prompt SHALL prohibit the LLM from mixing infrastructure nodes into L1 feature source_nodes unless the node has a clear dual role (both infrastructure and business logic)

### Requirement 11: Constraint Prompt ⑧ — L1.5 Output JSON Schema

**User Story:** As a developer using The Door, I want the L1.5 output to follow a strict JSON schema, so that downstream validation and rendering can operate reliably on structural overview data.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL enforce that L1.5 output conforms to the L1.5 output JSON schema containing: blocks array, block_relations array, and infrastructure_block object
2. THE Constraint_Prompt SHALL require each block to include: block_id, label, responsibility, trigger_mechanism, and related_features
3. THE Constraint_Prompt SHALL require each block_relation to include: from, to, relation, relation_type (static or inferred), and inferred_reason (required when relation_type is inferred)
4. THE Constraint_Prompt SHALL require the infrastructure_block to include: label and components array

### Requirement 12: Constraint Prompt ⑨ — L2 Output JSON Schema and Anomaly Detection

**User Story:** As a developer using The Door, I want the L2 output to follow a strict JSON schema with anomaly detection rules, so that module-level issues are systematically identified and reported.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL enforce that L2 output conforms to the L2 output JSON schema containing: modules array, module_interactions array, and anomalies array
2. THE Constraint_Prompt SHALL require each anomaly to include: anomaly_type (dead_code, logic_dead_end, uncertain_boundary), affected_node_ids, explanation, and confidence
3. THE Constraint_Prompt SHALL instruct the LLM to identify dead code as nodes with zero incoming calls that are not framework callbacks
4. THE Constraint_Prompt SHALL instruct the LLM to identify logic dead-ends as code paths that cannot be reached under current conditions

### Requirement 13: Constraint Prompt ⑩ — Output Validation Rules Specification

**User Story:** As a developer using The Door, I want the five validation checks (schema, coverage, language, anchor, relation) to be fully specified in the constraint prompt, so that the LLM understands what validation its output will face and can self-correct.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL describe all five validation checks that will be applied to LLM output: schema conformance, node coverage, language prohibition, anchor point traceability, and relation layered verification
2. THE Constraint_Prompt SHALL specify that coverage requires the union of source_nodes, unclassified_nodes, and infrastructure_nodes to equal the complete set of node_ids in Structure_JSON
3. THE Constraint_Prompt SHALL specify that static relations must have corresponding AST edge paths and inferred relations must include non-empty inferred_reason
4. THE Constraint_Prompt SHALL instruct the LLM to self-check its output against these rules before finalizing

### Requirement 14: Constraint Prompt ⑪ — Source Code Review Mechanism

**User Story:** As a developer using The Door, I want the system to automatically retrieve original source code for nodes the LLM cannot confidently classify from AST JSON alone, so that classification accuracy improves without sending entire files.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL instruct the LLM to mark nodes as needs_source_review with a review_reason when AST JSON information is insufficient for confident classification
2. WHEN a node is marked needs_source_review, THE Source_Code_Review mechanism SHALL extract the original function body or class definition from the source file
3. THE Source_Code_Review mechanism SHALL send only the extracted code snippet (not the entire file) to the LLM for secondary judgment
4. THE Source_Code_Review mechanism SHALL limit review to one attempt per node to prevent infinite loops
5. WHEN secondary judgment completes, THE Source_Code_Review mechanism SHALL update the node's confidence and mark it as "AI inference: source code reviewed"
6. THE Constraint_Prompt SHALL define trigger conditions for needs_source_review: function name is generic (process, handle, run) with no docstring; decorator belongs to an unrecognized framework; call relationships are incomplete in AST JSON; business classification cannot be determined from name and context

### Requirement 15: Constraint Prompt ⑫ — Anti-Hallucination Constraint

**User Story:** As a developer using The Door, I want the LLM to be strictly prohibited from describing features or relationships that have no AST basis, so that the output is trustworthy and verifiable.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL prohibit the LLM from describing features that do not correspond to any node in the Structure_JSON
2. THE Constraint_Prompt SHALL prohibit the LLM from adding static relations (relation_type: "static") that have no corresponding edge path in the Structure_JSON edges
3. THE Constraint_Prompt SHALL require that inferred relations (relation_type: "inferred") include a non-empty inferred_reason explaining the inference basis (async call, event-driven, IoC injection)
4. THE Constraint_Prompt SHALL require that nodes the LLM cannot classify be placed in unclassified_nodes rather than force-fitted into features
5. THE Constraint_Prompt SHALL prohibit the LLM from speculating about code intent beyond what names, docstrings, and call relationships can support

### Requirement 16: Constraint Prompt ⑬ — Anti-Over-Interpretation Constraint

**User Story:** As a developer using The Door, I want the LLM's description granularity to match the available AST information, so that sparse information does not produce falsely detailed descriptions.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL require that description length and detail level be proportional to the amount of AST information available for each node
2. THE Constraint_Prompt SHALL prohibit speculative language ("this function might be used for...", "this module appears to...") in nodes marked confidence "high"
3. THE Constraint_Prompt SHALL require that nodes with minimal AST information (no docstring, generic name, few edges) receive brief descriptions acknowledging limited information
4. THE Constraint_Prompt SHALL prohibit the LLM from expanding descriptions to appear complete when underlying information is sparse

### Requirement 17: Mermaid Text Generation

**User Story:** As a developer using The Door, I want the system to generate Mermaid diagram text from L1 and L1.5 output, so that the functional and structural views can be visually rendered by any Mermaid-compatible tool.

#### Acceptance Criteria

1. THE Mermaid_Renderer SHALL generate valid Mermaid flowchart syntax from L1 output, with each feature as a node and feature_relations as edges
2. THE Mermaid_Renderer SHALL generate valid Mermaid flowchart syntax from L1.5 output, with each block as a node and block_relations as edges
3. THE Mermaid_Renderer SHALL include confidence markers as node styling: high confidence nodes use default styling, medium confidence nodes use dashed borders, low confidence nodes use dotted borders with warning color
4. THE Mermaid_Renderer SHALL include trigger type indicators in node labels using human-readable descriptions
5. THE The_Door_CLI SHALL provide a command `the-door render <l1-output-json>` that outputs Mermaid text to stdout or a specified file
6. THE Mermaid_Renderer SHALL generate syntactically valid Mermaid text that passes Mermaid.js parsing without errors

### Requirement 18: Confidence Marker Display

**User Story:** As a non-technical user viewing The Door output, I want confidence markers to be clearly visible on all translated nodes, so that I can distinguish trustworthy information from uncertain interpretations.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL display confidence markers on all L1 feature nodes in both JSON output and Mermaid rendering
2. THE The_Door_CLI SHALL use the following marker labels: "[AI inference: high confidence]", "[AI inference: medium confidence]", "[AI inference: low confidence]"
3. WHEN a node has been through source code review, THE The_Door_CLI SHALL display the marker "[AI inference: source code reviewed]"
4. WHEN a node has been regenerated with different results, THE The_Door_CLI SHALL display the marker "[AI inference: regenerated, differs from previous]"
5. WHEN a node could not be fully analyzed due to batch limits, THE The_Door_CLI SHALL display the marker "[Information insufficient: incomplete reading]"

### Requirement 19: Cross-Session Continuity

**User Story:** As a developer using The Door across multiple work sessions, I want the system to resume analysis from where it left off rather than restarting, so that time and API costs are not wasted on re-analyzing unchanged code.

#### Acceptance Criteria

1. WHEN the user invokes analysis on a codebase with an existing Narrative_Chain, THE Batch_Reader SHALL check whether the AST structure has changed since the last recorded entry
2. IF the AST structure is unchanged, THEN THE Batch_Reader SHALL use the cached L1/L1.5 results from the Narrative_Chain without re-invoking the LLM
3. IF the AST structure has partially changed (some nodes added, removed, or modified), THEN THE Batch_Reader SHALL re-analyze only the affected nodes and their direct dependents
4. THE Batch_Reader SHALL preserve confidence assessments for unchanged nodes across sessions
5. WHEN resuming a session, THE Batch_Reader SHALL display a summary of what has changed since the last analysis and what will be re-analyzed

### Requirement 20: L1.5 Output Schema Validation

**User Story:** As a developer using The Door, I want L1.5 output to be validated against its JSON schema, so that structural overview data is guaranteed to be well-formed.

#### Acceptance Criteria

1. THE Output_Validator SHALL validate L1.5 output against the l1-5-output JSON schema using jsonschema Draft 2020-12
2. THE Output_Validator SHALL verify that every block_id referenced in block_relations exists in the blocks array
3. THE Output_Validator SHALL verify that every feature_id referenced in related_features exists in the L1 features array
4. IF L1.5 validation fails, THEN THE Output_Validator SHALL return structured error messages identifying non-conformant fields

### Requirement 21: L2 Output Schema Validation

**User Story:** As a developer using The Door, I want L2 output to be validated against its JSON schema, so that module-level interaction data and anomaly markers are guaranteed to be well-formed.

#### Acceptance Criteria

1. THE Output_Validator SHALL validate L2 output against the l2-output JSON schema using jsonschema Draft 2020-12
2. THE Output_Validator SHALL verify that every node_id referenced in anomaly affected_node_ids exists in the Structure_JSON
3. THE Output_Validator SHALL verify that anomaly_type values are one of: dead_code, logic_dead_end, uncertain_boundary
4. IF L2 validation fails, THEN THE Output_Validator SHALL return structured error messages identifying non-conformant fields

### Requirement 22: Narrative Chain Schema Definition

**User Story:** As a developer using The Door, I want the narrative chain format to be formally defined, so that cross-session persistence is reliable and auditable.

#### Acceptance Criteria

1. THE Narrative_Chain SHALL conform to the narrative.schema.json schema where each line is a valid JSON object
2. THE Narrative_Chain record SHALL contain the following required fields: batch (integer), strategy (string), nodes_read (array of objects with node_id, topology_rank, in_degree, is_entry_point), llm_judgment (string), pruned_nodes (array of node_ids), pending_low_confidence (array of node_ids), and timestamp (ISO8601 string)
3. THE Narrative_Chain SHALL support additional record types: "regeneration" (with feature_id, previous_summary, new_summary) and "structural_change" (with added_nodes, removed_nodes, modified_nodes)
4. THE The_Door_CLI SHALL provide a command `the-door history <codebase-path>` that displays the narrative chain in human-readable format

### Requirement 23: Low-Confidence Node Handling Strategy

**User Story:** As a developer using The Door, I want low-confidence nodes to be automatically processed through a defined escalation path, so that confidence improves where possible without manual intervention.

#### Acceptance Criteria

1. WHEN a node receives confidence "low", THE Batch_Reader SHALL check whether the node is marked needs_source_review
2. IF needs_source_review is true, THEN THE Batch_Reader SHALL trigger the Source_Code_Review mechanism before attempting other escalation
3. IF needs_source_review is false or source review did not improve confidence, THEN THE Batch_Reader SHALL supplement the node's upstream and downstream dependency context and re-submit to the LLM for secondary inference
4. WHEN secondary inference improves confidence, THE Batch_Reader SHALL update the marker to "[AI inference: medium confidence (supplemented context)]" or "[AI inference: source code reviewed]"
5. WHEN secondary inference does not improve confidence, THE Batch_Reader SHALL maintain the "[AI inference: low confidence]" marker with a specific reason in the explanation field

### Requirement 24: Extended MCP Server Tools

**User Story:** As an AI medium developer, I want additional MCP tools for batch reading, regeneration, and rendering, so that MCP clients can access the full Phase 1-full functionality.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose an analyze tool that executes the complete one-click mode pipeline and returns L1 + L1.5 output with confidence markers
2. THE MCP_Server SHALL expose a regenerate tool that accepts a feature_id and returns the regenerated result
3. THE MCP_Server SHALL expose a render tool that accepts L1 or L1.5 output JSON and returns Mermaid text
4. THE MCP_Server SHALL expose a history tool that returns the narrative chain for a given codebase path
5. THE MCP_Server SHALL expose an estimate tool that returns API cost estimation for a given codebase path

### Requirement 25: CLI Command Extensions

**User Story:** As a developer, I want new CLI commands for the Phase 1-full capabilities, so that all functionality is accessible from the terminal.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL provide the command `the-door analyze <codebase-path>` for one-click mode execution
2. THE The_Door_CLI SHALL provide the command `the-door regenerate <feature_id>` for regeneration trigger
3. THE The_Door_CLI SHALL provide the command `the-door render <output-json>` for Mermaid text generation
4. THE The_Door_CLI SHALL provide the command `the-door estimate <codebase-path>` for API cost estimation
5. THE The_Door_CLI SHALL provide the command `the-door history <codebase-path>` for narrative chain display
6. THE The_Door_CLI SHALL provide the command `the-door config init` for configuration file creation
7. ALL new CLI commands SHALL output JSON to stdout by default and support `--output <file>` for file output

### Requirement 26: LLM Response Parsing and Error Recovery

**User Story:** As a developer using The Door, I want the system to handle malformed LLM responses gracefully, so that transient LLM errors do not crash the pipeline.

#### Acceptance Criteria

1. WHEN the LLM returns a response that fails JSON parsing, THE LLM_Call_Layer SHALL retry the request up to 3 times with the validation failure reason appended to the prompt
2. WHEN the LLM returns valid JSON that fails output validation, THE LLM_Call_Layer SHALL retry once with the specific validation errors included in the retry prompt
3. IF all retries are exhausted, THEN THE LLM_Call_Layer SHALL mark the affected nodes as "[Output validation failed]" and continue processing remaining batches
4. THE LLM_Call_Layer SHALL log all retry attempts and failure reasons in the Narrative_Chain

### Requirement 27: Output Validation Extension for L1.5 and L2

**User Story:** As a developer using The Door, I want the existing 5-check validation to be extended to cover L1.5 and L2 output, so that all LLM output levels are quality-controlled.

#### Acceptance Criteria

1. THE Output_Validator SHALL apply schema validation to L1.5 output using the l1-5-output JSON schema
2. THE Output_Validator SHALL apply schema validation to L2 output using the l2-output JSON schema
3. THE Output_Validator SHALL verify L1.5 block cross-references: every feature_id in related_features must exist in L1 output
4. THE Output_Validator SHALL verify L2 anomaly node references: every node_id in affected_node_ids must exist in Structure_JSON
5. THE Output_Validator SHALL apply language checks to L1.5 labels using the same prohibited terms list as L1 (with relaxed rules allowing module names when accompanied by functional descriptions)

### Requirement 28: Narrative Chain Pretty-Printer

**User Story:** As a developer auditing The Door's analysis process, I want to view the narrative chain in a human-readable format, so that I can understand how the LLM arrived at its conclusions.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL parse JSONL narrative chain files and display them in a formatted, readable output
2. THE pretty-printer SHALL display each batch entry with: batch number, nodes analyzed (with entry-point indicators), LLM judgment summary, pruning decisions, and timestamp
3. THE pretty-printer SHALL highlight regeneration events and structural change markers distinctly from regular batch entries
4. FOR ALL valid Narrative_Chain JSONL files, parsing then formatting then re-parsing the structured data SHALL produce equivalent information (round-trip property for the narrative chain format)

