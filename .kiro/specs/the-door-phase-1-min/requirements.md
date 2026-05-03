# Requirements Document

## Introduction

The Door Phase 1-min delivers the minimum viable LLM constraint pipeline for translating code structure into functional-language diagrams readable by non-technical stakeholders. This phase implements the core local toolchain: AST structure extraction via tree-sitter-language-pack, topology analysis (in-degree/out-degree/entry-point detection/batch assignment), LLM constraint prompts (items ①–⑥), output validation (jsonschema + semantic checks + relation layered verification), and an MCP Server exposing two core tools. The system operates in "complete mode" where the AI medium orchestrates LLM calls using the structured material and constraint prompts produced by The Door.

## Glossary

- **The_Door_CLI**: The Python command-line tool that performs AST extraction, topology analysis, and output validation on a target codebase
- **AST_Extractor**: The component using tree-sitter-language-pack to parse source code into structured JSON material without classification
- **Topology_Analyzer**: The component that computes in-degree, out-degree, topology rank, entry-point status, and batch assignment for all AST nodes using dependency graph analysis
- **MCP_Server**: The Model Context Protocol server exposing The Door's core functionality as tools callable by any MCP-compatible AI medium
- **Structure_JSON**: The standardized JSON output containing files, nodes, edges, topology, and vulnerabilities extracted from a codebase
- **Output_Validator**: The component that checks LLM output against JSON schema, coverage, language constraints, anchor points, and relation layering rules
- **Constraint_Prompt**: The markdown files containing LLM input/output constraints that control how the LLM processes Structure_JSON and produces L1 output
- **L1_Output**: The LLM-generated JSON containing functional overview (features, relations, unclassified nodes, infrastructure nodes) in non-technical language
- **Entry_Point_Node**: An AST node identified as a framework entry point (has known entry decorator, or has in-degree 0 with out-degree > 0 and resides in routes/handlers/controllers/views/endpoints directory)
- **Batch_Assignment**: The pre-computed reading order for topology-guided LLM analysis, where entry points are always batch 1 and remaining nodes are ordered by descending in-degree
- **Topology_Rank**: A global priority ranking for each node determining reading order, with rank 1 being highest priority
- **Anchor_Point**: The traceability link between an L1 feature node and at least one AST node, preventing hallucinated features

## Requirements

### Requirement 1: AST Structure Extraction

**User Story:** As a developer using The Door, I want to extract structured AST information from any codebase, so that the resulting JSON material can be sent to an LLM for functional analysis.

#### Acceptance Criteria

1. WHEN a valid codebase path is provided, THE AST_Extractor SHALL parse all source files using tree-sitter-language-pack and output a Structure_JSON containing files, nodes, and edges
2. THE AST_Extractor SHALL extract the following node attributes for each function, class, and method: node_id, type, name, file, language, decorators, parameters, return_type, docstring, and comments
3. THE AST_Extractor SHALL extract edges representing calls, imports, extends, and implements relationships between nodes
4. WHEN tree-sitter-language-pack supports the source file language, THE AST_Extractor SHALL parse the file using the appropriate grammar
5. IF tree-sitter-language-pack fails to parse a specific file, THEN THE AST_Extractor SHALL skip that file, record it in an error list, and continue processing remaining files
6. THE AST_Extractor SHALL preserve docstrings and key comments (TODO, FIXME, business-logic annotations) in the node output without interpretation
7. THE AST_Extractor SHALL record the programming language for each node in the Structure_JSON

### Requirement 2: Topology Analysis

**User Story:** As a developer using The Door, I want the system to compute dependency topology for all AST nodes, so that LLM reading order is determined by code structure rather than guesswork.

#### Acceptance Criteria

1. WHEN AST extraction completes, THE Topology_Analyzer SHALL compute in_degree and out_degree for every node based on edges of type calls, imports, extends, and implements
2. THE Topology_Analyzer SHALL identify Entry_Point_Nodes using the following rules: the node has a known framework entry decorator (such as @app.route, @Controller, @Get, @Post, @Cron, @EventSubscriber), OR the node has in_degree equal to 0 AND out_degree greater than 0 AND the file path contains routes/, handlers/, controllers/, views/, or endpoints/
3. THE Topology_Analyzer SHALL assign batch_assignment value 1 to all Entry_Point_Nodes regardless of their in_degree
4. THE Topology_Analyzer SHALL assign batch_assignment values to non-entry-point nodes by sorting them in descending order of in_degree
5. THE Topology_Analyzer SHALL compute a topology_rank for each node representing its global reading priority, where rank 1 is the highest priority
6. THE Topology_Analyzer SHALL write the complete topology array (node_id, in_degree, out_degree, topology_rank, is_entry_point, batch_assignment) into the Structure_JSON topology field
7. THE Topology_Analyzer SHALL complete topology computation for a codebase with up to 1000 nodes in less than 1 second

### Requirement 3: LLM Constraint Prompt — Input Trimming Strategy

**User Story:** As a developer using The Door, I want the constraint prompts to specify how AST material is trimmed for different analysis levels, so that LLM context windows are used efficiently.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL define input trimming rules that send only node-level information (names, decorators, docstrings, edges) for L1 analysis, excluding function body details
2. THE Constraint_Prompt SHALL instruct the AI medium to send Structure_JSON in batches according to the topology batch_assignment field
3. THE Constraint_Prompt SHALL specify a maximum of 5 batches per analysis session
4. WHEN the batch limit is reached with unprocessed nodes remaining, THE Constraint_Prompt SHALL instruct the LLM to mark those nodes as unclassified with reason "information insufficient: incomplete reading"

### Requirement 4: LLM Constraint Prompt — L1 Output JSON Schema

**User Story:** As a developer using The Door, I want the LLM output to follow a strict JSON schema, so that downstream validation and rendering can operate reliably.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL enforce that LLM output conforms to the L1 output JSON schema containing: l1.summary, l1.features array, l1.feature_relations array, l1.unclassified_nodes array, and l1.infrastructure_nodes array
2. THE Constraint_Prompt SHALL require each feature object to include: feature_id, label, description, trigger, trigger_description, confidence, confidence_reason, and source_nodes
3. THE Constraint_Prompt SHALL require each feature_relations entry to include: from, to, relation, relation_type (static or inferred), and inferred_reason (required when relation_type is inferred)
4. THE Constraint_Prompt SHALL enforce that the L1 output JSON schema is validatable using jsonschema Draft 2020-12

### Requirement 5: LLM Constraint Prompt — Language Constraints

**User Story:** As a developer using The Door, I want L1 output to use purely functional language with zero technical jargon, so that non-engineers can directly understand the system capabilities.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL include a prohibited technical terms list containing at minimum: Service, Handler, Controller, Loader, IoC, Middleware, Decorator, Class, Module, Import, Endpoint, Router, Provider, Factory, Repository, DAO, ORM, SDK, API (as implementation reference)
2. THE Constraint_Prompt SHALL include positive examples demonstrating how to translate technical concepts into functional language
3. THE Constraint_Prompt SHALL include a trigger mechanism translation table mapping technical triggers (HTTP route handler, Cron job, EventSubscriber, IoC injection, Middleware) to human-readable descriptions

### Requirement 6: LLM Constraint Prompt — Confidence Self-Assessment

**User Story:** As a developer using The Door, I want the LLM to self-assess confidence for every feature node, so that users can identify which parts of the analysis need further verification.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL require the LLM to assign a confidence value of high, medium, or low to every feature node
2. THE Constraint_Prompt SHALL require the LLM to provide a confidence_reason explaining the basis for each confidence assessment
3. THE Constraint_Prompt SHALL prohibit the LLM from using vague language to mask uncertainty in nodes marked as confidence high

### Requirement 7: LLM Constraint Prompt — Unclassified Nodes

**User Story:** As a developer using The Door, I want the LLM to explicitly list all nodes it cannot classify, so that no AST nodes silently disappear from the analysis.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL require the LLM to list all AST nodes that cannot be assigned to any L1 feature in the unclassified_nodes array
2. THE Constraint_Prompt SHALL prohibit the LLM from forcing classification on nodes where functional purpose cannot be determined from available information
3. THE Constraint_Prompt SHALL require the LLM to separately list nodes identified as infrastructure in the infrastructure_nodes array

### Requirement 8: LLM Constraint Prompt — Anchor Point Constraint

**User Story:** As a developer using The Door, I want every L1 feature to be traceable to at least one AST node, so that hallucinated features are structurally prevented.

#### Acceptance Criteria

1. THE Constraint_Prompt SHALL require every feature in the features array to reference at least one valid node_id in its source_nodes field
2. THE Constraint_Prompt SHALL prohibit the LLM from describing features or relationships that have no corresponding nodes in the Structure_JSON
3. THE Constraint_Prompt SHALL require that static feature_relations reference edges that exist in the Structure_JSON edges array

### Requirement 9: Output Validation — Schema Check

**User Story:** As a developer using The Door, I want LLM output to be automatically validated against the JSON schema, so that malformed output is caught before rendering.

#### Acceptance Criteria

1. WHEN LLM output is submitted for validation, THE Output_Validator SHALL verify conformance to the L1 output JSON schema using jsonschema Draft 2020-12
2. IF the LLM output fails schema validation, THEN THE Output_Validator SHALL return structured error messages identifying which fields are non-conformant
3. THE Output_Validator SHALL validate that relation_type is either "static" or "inferred" for every feature_relations entry

### Requirement 10: Output Validation — Coverage Check

**User Story:** As a developer using The Door, I want to verify that LLM output accounts for all AST nodes, so that no code is silently ignored.

#### Acceptance Criteria

1. WHEN LLM output is submitted for validation, THE Output_Validator SHALL verify that the union of source_nodes across all features, unclassified_nodes, and infrastructure_nodes covers all node_ids present in the Structure_JSON
2. IF coverage is incomplete, THEN THE Output_Validator SHALL return the list of uncovered node_ids

### Requirement 11: Output Validation — Language Check

**User Story:** As a developer using The Door, I want L1 descriptions to be automatically checked for prohibited technical terms, so that non-technical readability is enforced.

#### Acceptance Criteria

1. WHEN LLM output is submitted for validation, THE Output_Validator SHALL scan all label and description fields in the features array against the prohibited technical terms list
2. IF prohibited terms are found, THEN THE Output_Validator SHALL return the offending terms and their locations

### Requirement 12: Output Validation — Anchor Point Check

**User Story:** As a developer using The Door, I want to verify that every L1 feature traces back to real AST nodes, so that hallucinated features are detected.

#### Acceptance Criteria

1. WHEN LLM output is submitted for validation, THE Output_Validator SHALL verify that every node_id referenced in source_nodes exists in the Structure_JSON nodes array
2. IF a feature references a non-existent node_id, THEN THE Output_Validator SHALL flag that feature as containing a hallucination anchor error

### Requirement 13: Output Validation — Relation Layered Verification

**User Story:** As a developer using The Door, I want static and inferred relations to be validated at different strictness levels, so that LLM inference capability is preserved while pure hallucinations are caught.

#### Acceptance Criteria

1. WHEN a feature_relation has relation_type "static", THE Output_Validator SHALL verify that a corresponding path exists in the Structure_JSON edges connecting the source_nodes of the two referenced features
2. WHEN a feature_relation has relation_type "inferred", THE Output_Validator SHALL verify only that both referenced feature_ids exist and each has at least one valid source_node
3. IF a static relation has no corresponding AST edge path, THEN THE Output_Validator SHALL flag it as a static relation verification failure
4. THE Output_Validator SHALL verify that every inferred relation includes a non-empty inferred_reason field

### Requirement 14: MCP Server — extract_structure Tool

**User Story:** As an AI medium developer, I want to call an MCP tool to extract structure from a codebase, so that any MCP-compatible client can use The Door without custom integration.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose an extract_structure tool that accepts a codebase_path string parameter
2. WHEN extract_structure is called with a valid codebase path, THE MCP_Server SHALL execute AST extraction followed by topology analysis and return the complete Structure_JSON
3. IF the codebase path is invalid or inaccessible, THEN THE MCP_Server SHALL return a structured error message indicating the failure reason
4. THE MCP_Server SHALL be startable via the command `the-door mcp-serve` or `python -m the_door.mcp.server`

### Requirement 15: MCP Server — validate_output Tool

**User Story:** As an AI medium developer, I want to call an MCP tool to validate LLM output, so that output quality can be verified without implementing validation logic in each AI medium.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a validate_output tool that accepts an llm_output dict parameter
2. WHEN validate_output is called, THE MCP_Server SHALL execute all five validation checks: schema, coverage, language, anchor point, and relation layered verification
3. THE MCP_Server SHALL return a structured validation result containing: overall pass/fail status, and per-check results with failure details when applicable
4. IF validation fails, THEN THE MCP_Server SHALL include actionable failure reasons suitable for LLM retry

### Requirement 16: CLI Command Interface

**User Story:** As a developer, I want clear CLI commands for extraction and validation, so that The Door can be used from any terminal or scripted into pipelines.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL provide an `extract` command that accepts a codebase path and outputs Structure_JSON to stdout or a specified file
2. THE The_Door_CLI SHALL provide a `validate` command that accepts LLM output JSON and the corresponding Structure_JSON, and outputs validation results
3. THE The_Door_CLI SHALL provide an `mcp-serve` command that starts the MCP Server
4. IF a required argument is missing, THEN THE The_Door_CLI SHALL display a usage message describing the expected arguments

### Requirement 17: Structure JSON Schema Conformance

**User Story:** As a developer, I want the Structure_JSON output to follow a defined schema, so that any consumer (LLM, validator, renderer) can reliably parse it.

#### Acceptance Criteria

1. THE AST_Extractor SHALL output Structure_JSON conforming to the ast-raw.schema.json schema containing: files array, nodes array, edges array, and topology array
2. THE Structure_JSON SHALL use node_id values that are unique across the entire output
3. THE Structure_JSON SHALL ensure every edge references valid node_ids in both from and to fields

### Requirement 18: Testing on Open-Source Codebases

**User Story:** As a project stakeholder, I want The Door tested on 3 open-source codebases with quantified metrics, so that the system's effectiveness is objectively measured.

#### Acceptance Criteria

1. THE The_Door_CLI SHALL be tested on 3 distinct open-source codebases of varying size and language
2. WHEN tested, THE The_Door_CLI SHALL achieve L1 feature identification accuracy of at least 70% compared to human-established ground truth
3. WHEN tested, THE The_Door_CLI SHALL achieve AST node coverage of at least 90% (nodes accounted for in features + unclassified + infrastructure)
4. WHEN tested with topology-guided batching, THE The_Door_CLI SHALL demonstrate token savings of at least 20% compared to sending all nodes without topology guidance
5. WHEN tested, THE Topology_Analyzer SHALL confirm that all Entry_Point_Nodes are assigned to batch 1

### Requirement 19: MCP Client Integration Verification

**User Story:** As a project stakeholder, I want at least one MCP client to successfully complete the full analysis flow, so that the MCP integration is proven functional.

#### Acceptance Criteria

1. WHEN an MCP-compatible client (Claude Desktop or Cursor) connects to THE MCP_Server, the client SHALL successfully call extract_structure and receive valid Structure_JSON
2. WHEN the MCP client submits LLM output to validate_output, THE MCP_Server SHALL return validation results without errors
3. THE MCP_Server SHALL handle concurrent tool calls without data corruption
