# Implementation Plan: The Door Phase 1-full

## Overview

This plan extends the existing Phase 1-min codebase into a complete LLM translation engine. Tasks follow strict TDD (tests first, implementation after) and are ordered: foundation (schemas, models, config) → core logic (llm, reading, rendering) → validation extensions → integration (CLI, MCP). All 21 new correctness properties (#13–#33) are covered by property-based tests using Hypothesis.

**Existing codebase:** `the_door/` with 100 passing tests (Phase 1-min). All existing tests MUST continue passing throughout.

**TDD Order:** Dependencies & schemas → Data models → Test fixtures → Property tests → Unit tests → Implementation → Validation extensions → CLI & MCP wiring → Integration tests.

## Tasks

- [x] 1. Dependencies, schemas, and data models
  - [x] 1.1 Update pyproject.toml with new dependencies
    - Add `httpx` for async HTTP LLM API calls
    - Add `tomli; python_version < '3.11'` for TOML config parsing
    - Verify existing dependencies unchanged
    - _Requirements: 5.2, 6.1_

  - [x] 1.2 Create new JSON schema files
    - Create `schemas/l1-5-output.schema.json` (Draft 2020-12) for L1.5 structural overview: blocks array (block_id, label, responsibility, trigger_mechanism, related_features), block_relations array (from, to, relation, relation_type with inferred_reason conditional), infrastructure_block (label, components)
    - Create `schemas/l2-output.schema.json` (Draft 2020-12) for L2 module interaction: modules array (module_id, label, source_nodes, confidence, confidence_reason), module_interactions array (from, to, description, relation_type), anomalies array (anomaly_type enum, affected_node_ids, explanation, confidence)
    - Create `schemas/narrative.schema.json` (Draft 2020-12) for narrative chain records: record_type enum (batch, regeneration, structural_change), timestamp, conditional required fields per record_type
    - _Requirements: 8.5, 9.4, 11.1, 12.1, 20.1, 21.1, 22.1_

  - [x] 1.3 Extend models.py with Phase 1-full data classes
    - Add L1.5 models: L1_5Block, BlockRelation, InfrastructureBlock, L1_5Output
    - Add L2 models: L2Module, ModuleInteraction, Anomaly, L2Output
    - Add narrative chain models: NarrativeNodeRead, NarrativeRecord
    - Add LLM/config models: TheDoorConfig, CostEstimate, ParseResult
    - All new dataclasses use frozen=True where appropriate (matching Phase 1-min style)
    - Existing models remain unchanged
    - _Requirements: 8.1, 8.2, 9.2, 22.2, 5.3, 7.1_

  - [x] 1.4 Create new package directories with `__init__.py` files
    - Create `src/the_door/core/reading/` package
    - Create `src/the_door/core/rendering/` package
    - Create `src/the_door/core/llm/` package
    - Create test directories: `tests/unit/core/reading/`, `tests/unit/core/rendering/`, `tests/unit/core/llm/`, `tests/unit/core/validation/` (if not existing)
    - Create test fixture directories: `tests/fixtures/sample_l1_5_output/`, `tests/fixtures/sample_l2_output/`, `tests/fixtures/sample_narrative_chain/`
    - _Requirements: 1.1, 8.1, 9.1_

- [x] 2. Checkpoint — Verify foundation
  - Run existing Phase 1-min test suite (`pytest tests/`) and confirm all 100 tests still pass. Verify new schemas are valid JSON. Verify new models import correctly. Ask the user if questions arise.

- [x] 3. Test fixtures for Phase 1-full
  - [x] 3.1 Create sample L1.5 output fixtures
    - Create `tests/fixtures/sample_l1_5_output/valid_output.json` with blocks, block_relations, infrastructure_block conforming to l1-5-output.schema.json
    - Create invalid variants: missing block_id, dangling feature reference in related_features, bare technical term in label
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 20.1, 20.2, 20.3_

  - [x] 3.2 Create sample L2 output fixtures
    - Create `tests/fixtures/sample_l2_output/valid_output.json` with modules, module_interactions, anomalies conforming to l2-output.schema.json
    - Create invalid variants: invalid anomaly_type, dangling node_id in affected_node_ids, missing required fields
    - _Requirements: 9.2, 9.3, 9.4, 21.1, 21.2, 21.3_

  - [x] 3.3 Create sample narrative chain fixtures
    - Create `tests/fixtures/sample_narrative_chain/valid_chain.jsonl` with batch, regeneration, and structural_change records
    - Create `tests/fixtures/sample_narrative_chain/corrupted_chain.jsonl` with one invalid line among valid records
    - _Requirements: 3.1, 3.4, 22.1, 22.2_

  - [x] 3.4 Create MockLLMProvider test helper
    - Implement MockLLMProvider class in `tests/conftest.py` (or a shared helper) with pre-configured responses, call recording, and LLMProvider protocol compliance
    - _Requirements: 5.1, 5.2_

- [x] 4. Property tests for LLM layer (TDD: write tests BEFORE implementation)
  - [ ]* 4.1 Write property test: Config environment variable precedence (Property 22)
    - **Property 22: Config environment variable precedence**
    - Use Hypothesis to generate random config file values and env var values for THE_DOOR_OPENAI_KEY, THE_DOOR_ANTHROPIC_KEY, THE_DOOR_OLLAMA_URL; verify loaded config always uses env var value when both exist
    - **Validates: Requirements 5.3, 6.3**

- [x] 5. Property tests for reading engine (TDD: write tests BEFORE implementation)
  - [ ]* 5.1 Write property test: Batch ordering follows topology assignment (Property 13)
    - **Property 13: Batch ordering follows topology assignment**
    - Use Hypothesis to generate Structure JSONs with nodes assigned to batches 1–N; verify BatchReader processes batches in strictly ascending order and every node in batch K is submitted before any node in batch K+1
    - **Validates: Requirements 1.1**

  - [ ]* 5.2 Write property test: Batch consolidation preserves all features (Property 14)
    - **Property 14: Batch consolidation preserves all features**
    - Use Hypothesis to generate random per-batch LLM responses each containing feature sets; verify consolidated L1 output contains every feature from every batch with no losses and no duplicate feature_ids
    - **Validates: Requirements 1.5**

  - [ ]* 5.3 Write property test: Pruning invariant — high confidence excludes downstream (Property 15)
    - **Property 15: Pruning invariant — high confidence excludes downstream dependencies**
    - Use Hypothesis to generate random confidence sequences with edge graphs; verify PruningEngine marks high-confidence nodes as pruned AND excludes their downstream dependencies from subsequent batch payloads (unless those dependencies have other pending references)
    - **Validates: Requirements 1.6, 2.1, 2.2**

  - [ ]* 5.4 Write property test: Pruning reinstatement on low-confidence reference (Property 16)
    - **Property 16: Pruning reinstatement on low-confidence reference**
    - Use Hypothesis to generate pruned node sets and low-confidence reference scenarios; verify PruningEngine reinstates pruned nodes when referenced by low-confidence nodes
    - **Validates: Requirements 2.4**

  - [ ]* 5.5 Write property test: Pruning decisions recorded in narrative chain (Property 17)
    - **Property 17: Pruning decisions recorded in narrative chain**
    - Use Hypothesis to generate pruning decision sequences; verify narrative chain contains a record for each decision with correct node_id, batch number, and reason
    - **Validates: Requirements 2.3**

  - [ ]* 5.6 Write property test: Structural change detection correctness (Property 20)
    - **Property 20: Structural change detection correctness**
    - Use Hypothesis to generate pairs of Structure JSONs; verify detector reports correct added_nodes, removed_nodes, modified_nodes sets; verify identical structures report no changes
    - **Validates: Requirements 3.5, 19.1**

  - [ ]* 5.7 Write property test: Regeneration diff marking (Property 21)
    - **Property 21: Regeneration diff marking**
    - Use Hypothesis to generate same/different result pairs; verify marker "AI inference: regenerated, differs from previous" is applied iff results differ (different label, description, or source_nodes)
    - **Validates: Requirements 4.2**

  - [ ]* 5.8 Write property test: Infrastructure consolidation into single block (Property 26)
    - **Property 26: Infrastructure consolidation into single block**
    - Use Hypothesis to generate L1 outputs with infrastructure_nodes; verify corresponding L1.5 output contains exactly one infrastructure_block whose components list covers every infrastructure node_id
    - **Validates: Requirements 8.4, 10.1, 10.2**

  - [ ]* 5.9 Write property test: Source code snippet extraction accuracy (Property 33)
    - **Property 33: Source code snippet extraction accuracy**
    - Use Hypothesis to generate codebases with known function positions; verify SourceReviewer extracts correct function body text with matching start_line and end_line
    - **Validates: Requirements 14.2**

- [x] 6. Property tests for rendering and narrative chain (TDD: write tests BEFORE implementation)
  - [ ]* 6.1 Write property test: Narrative chain JSONL round-trip (Property 18)
    - **Property 18: Narrative chain JSONL round-trip**
    - Use Hypothesis to generate lists of valid NarrativeRecord objects; write to JSONL file and read back; verify no records lost, no fields altered, order preserved
    - **Validates: Requirements 3.1, 28.4**

  - [ ]* 6.2 Write property test: Narrative chain schema conformance (Property 19)
    - **Property 19: Narrative chain schema conformance**
    - Use Hypothesis to generate NarrativeRecords per type (batch, regeneration, structural_change); verify JSON representation conforms to narrative.schema.json with correct required fields per type
    - **Validates: Requirements 3.4, 22.1, 22.2, 22.3**

  - [ ]* 6.3 Write property test: Cost estimation scales with structure size (Property 23)
    - **Property 23: Cost estimation scales with structure size**
    - Use Hypothesis to generate pairs of Structure JSONs where A has strictly more nodes than B; verify estimated input and output tokens for A ≥ those for B (same provider/model)
    - **Validates: Requirements 7.2, 7.3**

  - [ ]* 6.4 Write property test: Mermaid syntax validity (Property 30)
    - **Property 30: Mermaid syntax validity**
    - Use Hypothesis to generate valid L1 and L1.5 outputs; verify rendered Mermaid text starts with valid graph declaration, contains only valid node/edge definitions, uses properly escaped labels
    - **Validates: Requirements 17.1, 17.2, 17.6**

  - [ ]* 6.5 Write property test: Mermaid content completeness (Property 31)
    - **Property 31: Mermaid content completeness**
    - Use Hypothesis to generate L1 outputs with features, relations, and confidence levels; verify Mermaid contains one node per feature, one edge per relation, confidence-based styling, and trigger descriptions
    - **Validates: Requirements 17.3, 17.4**

  - [ ]* 6.6 Write property test: Confidence marker label correctness (Property 32)
    - **Property 32: Confidence marker label correctness**
    - Use Hypothesis to generate all state combinations (confidence level, source-reviewed, regenerated-with-diff, incomplete-reading); verify displayed marker matches exactly one defined label
    - **Validates: Requirements 18.1, 18.2, 18.3, 18.4, 18.5**

- [x] 7. Property tests for validation extensions (TDD: write tests BEFORE implementation)
  - [ ]* 7.1 Write property test: L1.5 schema validation accepts valid / rejects invalid (Property 24)
    - **Property 24: L1.5 schema validation accepts valid and rejects invalid**
    - Use Hypothesis to generate valid L1.5 outputs (all required fields, valid enums) and invalid variants (missing fields, wrong types); verify schema check passes/fails correctly
    - **Validates: Requirements 8.2, 8.3, 8.5, 20.1, 27.1**

  - [ ]* 7.2 Write property test: L1.5 cross-reference integrity (Property 25)
    - **Property 25: L1.5 cross-reference integrity**
    - Use Hypothesis to generate L1.5 + L1 output pairs with valid/dangling references; verify every block_id in block_relations exists in blocks, every feature_id in related_features exists in L1 features
    - **Validates: Requirements 20.2, 20.3, 27.3**

  - [ ]* 7.3 Write property test: L2 schema validation accepts valid / rejects invalid (Property 27)
    - **Property 27: L2 schema validation accepts valid and rejects invalid**
    - Use Hypothesis to generate valid/invalid L2 outputs; verify schema check passes/fails correctly with anomaly_type enum validation
    - **Validates: Requirements 9.2, 9.3, 9.4, 9.5, 21.1, 21.3, 27.2**

  - [ ]* 7.4 Write property test: L2 anomaly node reference integrity (Property 28)
    - **Property 28: L2 anomaly node reference integrity**
    - Use Hypothesis to generate L2 outputs and Structure JSONs with valid/invalid anomaly node references; verify dangling references flagged as validation errors
    - **Validates: Requirements 21.2, 27.4**

  - [ ]* 7.5 Write property test: L1.5 language check with relaxed rules (Property 29)
    - **Property 29: L1.5 language check with relaxed rules**
    - Use Hypothesis to generate L1.5 block labels with/without prohibited terms and functional context; verify relaxed rule: bare technical term fails, technical term + functional description passes
    - **Validates: Requirements 27.5**

- [x] 8. Checkpoint — All property tests written, all should FAIL (TDD red phase)
  - Run `pytest tests/property/` and confirm new property tests fail because implementation does not exist yet. Confirm existing Phase 1-min property tests still pass. Ask the user if questions arise.

- [x] 9. Unit tests for LLM layer (TDD: write tests BEFORE implementation)
  - [x] 9.1 Write unit tests for response_parser module
    - Test: valid JSON string → ParseResult(success=True, data=parsed_dict)
    - Test: JSON wrapped in markdown code fence → extracted and parsed correctly
    - Test: leading text before JSON → JSON extracted correctly
    - Test: completely invalid response → ParseResult(success=False, error=message)
    - Test: empty string → ParseResult(success=False)
    - Test: JSON with trailing comma (common LLM error) → handled gracefully
    - _Requirements: 26.1, 26.2_

  - [x] 9.2 Write unit tests for config_manager module
    - Test: load from valid config.toml → TheDoorConfig with correct values
    - Test: missing config file → defaults + env vars used, warning logged
    - Test: invalid TOML syntax → clear error with parse location
    - Test: env var THE_DOOR_OPENAI_KEY overrides file value
    - Test: env var THE_DOOR_ANTHROPIC_KEY overrides file value
    - Test: env var THE_DOOR_OLLAMA_URL overrides file value
    - Test: no API key for selected provider → clear error message
    - Test: init_default creates config.toml at expected path
    - Test: validate() warns about unreachable/misconfigured providers
    - _Requirements: 5.3, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 9.3 Write unit tests for LLM provider modules
    - Test: OpenAIProvider.complete() with mock httpx response → correct response text
    - Test: AnthropicProvider.complete() with mock httpx response → correct response text
    - Test: OllamaProvider.complete() with mock httpx response → correct response text
    - Test: each provider timeout handling → LLMCallError raised
    - Test: each provider auth failure (401/403) → immediate failure, no retry
    - Test: each provider rate limit (429) → appropriate error
    - Test: estimate_tokens returns reasonable count (len/4 heuristic or tokenizer)
    - Test: provider_name, model_name, cost properties return correct values
    - Test: create_provider factory with valid config → correct provider type
    - Test: create_provider factory with invalid config → ConfigError
    - _Requirements: 5.1, 5.2, 5.4, 5.5, 5.6_

- [x] 10. Unit tests for reading engine (TDD: write tests BEFORE implementation)
  - [x] 10.1 Write unit tests for pruning_engine module
    - Test: record_confidence("node_a", "high", batch=1) → node_a in get_pruned_nodes()
    - Test: should_prune returns True for pruned nodes, False for non-pruned
    - Test: downstream dependencies of high-confidence node also pruned (when no other pending refs)
    - Test: downstream dependency with other pending refs NOT pruned
    - Test: reinstate("node_a", batch=3) → node_a removed from pruned set, reinstated=True in decision
    - Test: no high-confidence nodes → get_pruned_nodes() returns empty set
    - Test: all nodes high-confidence → all pruned
    - Test: get_decisions() returns complete list of PruningDecision objects
    - _Requirements: 1.6, 2.1, 2.2, 2.3, 2.4_

  - [x] 10.2 Write unit tests for narrative_chain module
    - Test: append + read_all round-trip preserves records
    - Test: empty chain file → read_all returns empty list
    - Test: corrupted JSONL line → skipped with warning, valid records preserved
    - Test: get_last_state returns last batch record's state
    - Test: detect_structural_change with identical structures → None
    - Test: detect_structural_change with added/removed nodes → correct change summary
    - Test: format_human_readable produces readable output with batch numbers, timestamps, pruning info
    - Test: regeneration record type correctly stored and retrieved
    - Test: structural_change record type correctly stored and retrieved
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 22.1, 22.2, 22.3, 28.1, 28.2, 28.3_

  - [x] 10.3 Write unit tests for source_reviewer module
    - Test: extract_snippet for known function → correct SourceSnippet with file_path, source_text, start_line, end_line
    - Test: source file not found → returns None
    - Test: node cannot be located in file → returns None
    - Test: snippet exceeds 10KB → truncated with "[truncated]" marker
    - Test: extracts only the specific node, not entire file
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [x] 10.4 Write unit tests for batch_reader module
    - Test: read() with single-batch structure → correct BatchReadResult
    - Test: read() with multi-batch structure → batches processed in order
    - Test: read() with empty structure (0 nodes) → empty result
    - Test: max batch limit (5) enforced, remaining nodes marked unclassified
    - Test: affected_nodes parameter → only specified nodes + dependents re-analyzed
    - Test: batch payload exceeding context window → auto-split into sub-batches
    - Test: LLM returns empty response → nodes marked unclassified
    - Test: low-confidence node triggers source review escalation
    - Test: regenerate() with different result → marker applied, previous preserved
    - Test: regenerate() with identical result → no marker
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 4.1, 4.2, 4.3, 4.5, 19.3, 23.1, 23.2, 23.3, 23.4, 23.5_

- [x] 11. Unit tests for rendering modules (TDD: write tests BEFORE implementation)
  - [x] 11.1 Write unit tests for mermaid_renderer module
    - Test: render_l1 with single feature → valid Mermaid flowchart with node and label
    - Test: render_l1 with multiple features and relations → correct edges
    - Test: render_l1 with all confidence levels → correct styling (default/dashed/dotted)
    - Test: render_l1 with trigger descriptions → trigger text in node labels
    - Test: render_l1_5 with blocks and relations → valid Mermaid flowchart
    - Test: render_l1_5 with infrastructure block → rendered as subgraph
    - Test: empty output (no features/blocks) → minimal valid Mermaid with placeholder node
    - Test: special characters in labels (quotes, brackets, pipes) → properly escaped
    - Test: relation referencing non-existent feature_id → edge skipped with warning
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6_

  - [x] 11.2 Write unit tests for cost_estimator module
    - Test: estimate with zero nodes → CostEstimate with 0 tokens
    - Test: estimate with Ollama provider → is_local=True, cost=0.0
    - Test: estimate with OpenAI provider → correct cost based on pricing
    - Test: estimate with Anthropic provider → correct cost based on pricing
    - Test: larger structure produces higher token estimate than smaller
    - Test: batch_count reflects expected number of batches
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 12. Unit tests for validation extensions (TDD: write tests BEFORE implementation)
  - [x] 12.1 Write unit tests for L1.5 validation
    - Test: valid L1.5 output passes schema check
    - Test: missing block_id field → schema check fails with specific error
    - Test: dangling block_id in block_relations → cross-reference error
    - Test: dangling feature_id in related_features → cross-reference error
    - Test: bare technical term in block label → language check fails
    - Test: technical term + functional description in block label → language check passes (relaxed rule)
    - Test: valid L1.5 with infrastructure_block → passes all checks
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 27.1, 27.3, 27.5_

  - [x] 12.2 Write unit tests for L2 validation
    - Test: valid L2 output passes schema check
    - Test: invalid anomaly_type → schema check fails
    - Test: dangling node_id in anomaly affected_node_ids → anchor error
    - Test: valid anomaly types (dead_code, logic_dead_end, uncertain_boundary) → passes
    - Test: missing required fields → schema check fails with specific error
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 27.2, 27.4_

- [x] 13. Checkpoint — All unit tests written, all new tests should FAIL (TDD red phase)
  - Run `pytest tests/unit/core/reading/ tests/unit/core/rendering/ tests/unit/core/llm/ tests/unit/core/validation/test_l1_5_validation.py tests/unit/core/validation/test_l2_validation.py` and confirm new tests fail. Confirm existing Phase 1-min tests still pass. Ask the user if questions arise.

- [x] 14. Implement LLM layer modules
  - [x] 14.1 Implement response_parser.py
    - Implement ResponseParser.parse() to extract JSON from LLM response text
    - Handle: raw JSON, markdown code fences, leading/trailing text, malformed JSON
    - Return ParseResult with success status, parsed data, raw text, and error message
    - _Requirements: 26.1, 26.2_

  - [x] 14.2 Implement config_manager.py
    - Implement ConfigManager.load() to read `~/.the-door/config.toml` with env var override (THE_DOOR_OPENAI_KEY, THE_DOOR_ANTHROPIC_KEY, THE_DOOR_OLLAMA_URL)
    - Implement ConfigManager.init_default() to create default config file
    - Implement ConfigManager.validate() to check config validity and warn about issues
    - Use `tomllib` (3.11+) or `tomli` (3.10) for TOML parsing
    - _Requirements: 5.3, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 14.3 Implement provider.py (protocol + factory)
    - Define LLMProvider protocol with complete, estimate_tokens, provider_name, model_name, cost_per_1k_input, cost_per_1k_output
    - Implement create_provider factory function
    - Define LLMCallError and ConfigError exception classes
    - _Requirements: 5.1, 5.2, 5.5_

  - [x] 14.4 Implement openai_provider.py
    - Implement OpenAIProvider using httpx for async HTTP calls to OpenAI API
    - Include retry with exponential backoff (1s, 2s, 4s) up to max_retries
    - Handle auth failure (401/403) with immediate failure
    - Handle rate limit (429) with Retry-After header respect
    - _Requirements: 5.1, 5.2, 5.4_

  - [x] 14.5 Implement anthropic_provider.py
    - Implement AnthropicProvider using httpx for async HTTP calls to Anthropic API
    - Same retry and error handling pattern as OpenAI
    - _Requirements: 5.1, 5.2, 5.4_

  - [x] 14.6 Implement ollama_provider.py
    - Implement OllamaProvider using httpx for HTTP calls to local Ollama server
    - Handle connection failure with clear error message
    - cost_per_1k_input and cost_per_1k_output return 0.0
    - _Requirements: 5.2, 5.6_

- [x] 15. Checkpoint — LLM layer tests pass
  - Run `pytest tests/unit/core/llm/ tests/property/test_llm_properties.py` and confirm all LLM layer tests pass. Ask the user if questions arise.

- [x] 16. Implement reading engine modules
  - [x] 16.1 Implement pruning_engine.py
    - Implement PruningEngine with edge-aware pruning: takes edges list in constructor
    - Implement record_confidence() to mark high-confidence nodes and their downstream dependencies as pruned
    - Implement should_prune(), get_pruned_nodes(), reinstate(), get_decisions()
    - Downstream dependencies only pruned if they have no other pending references from non-pruned nodes
    - _Requirements: 1.6, 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 16.2 Implement narrative_chain.py
    - Implement NarrativeChain with append-only JSONL read/write
    - Implement append(), read_all(), get_last_state(), detect_structural_change(), format_human_readable()
    - Handle corrupted JSONL lines (skip with warning)
    - Support batch, regeneration, and structural_change record types
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 22.1, 22.2, 22.3, 28.1, 28.2, 28.3, 28.4_

  - [x] 16.3 Implement source_reviewer.py
    - Implement SourceReviewer.extract_snippet() to locate and extract function body or class definition from source file
    - Handle: file not found, node not locatable, snippet exceeding 10KB (truncate)
    - Extract only the specific node, not the entire file
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [x] 16.4 Implement batch_reader.py
    - Implement BatchReader.read() orchestrator: group by batch_assignment → per-batch LLM call → parse → validate → prune → consolidate
    - Implement affected_nodes parameter for partial re-analysis (only affected + direct dependents)
    - Implement auto-split when batch payload exceeds context window (recursively halve)
    - Implement low-confidence escalation: source review → context supplement → secondary inference
    - Implement BatchReader.regenerate() for per-node re-analysis with diff detection
    - Enforce max 5 batches, mark remaining as unclassified
    - Record all events in narrative chain
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 4.1, 4.2, 4.3, 4.4, 4.5, 19.1, 19.2, 19.3, 19.4, 19.5, 23.1, 23.2, 23.3, 23.4, 23.5, 26.1, 26.2, 26.3, 26.4_

- [x] 17. Checkpoint — Reading engine tests pass
  - Run `pytest tests/unit/core/reading/ tests/property/test_reading_properties.py` and confirm all reading engine tests pass. Ask the user if questions arise.

- [x] 18. Implement rendering modules
  - [x] 18.1 Implement mermaid_renderer.py
    - Implement MermaidRenderer.render_l1() to generate Mermaid flowchart from L1 output
    - Each feature → node with label + trigger indicator; feature_relations → edges
    - Confidence-based styling: high=default, medium=dashed, low=dotted+warning color
    - Implement MermaidRenderer.render_l1_5() for L1.5 blocks and relations
    - Infrastructure block rendered as Mermaid subgraph
    - Escape Mermaid-unsafe characters in labels (quotes, brackets, pipes)
    - Empty output → minimal valid Mermaid with placeholder node
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6_

  - [x] 18.2 Implement cost_estimator.py
    - Implement CostEstimator.estimate() to calculate token count and cost without LLM calls
    - Input tokens based on Structure JSON size per batch + constraint prompt size
    - Output tokens based on expected output size proportional to node count
    - Ollama → is_local=True, cost=0.0
    - OpenAI/Anthropic → cost based on provider pricing properties
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 19. Checkpoint — Rendering tests pass
  - Run `pytest tests/unit/core/rendering/ tests/property/test_rendering_properties.py` and confirm all rendering tests pass. Ask the user if questions arise.

- [x] 20. Implement validation extensions
  - [x] 20.1 Extend schema_check.py for L1.5 and L2
    - Add L1.5 schema validation using l1-5-output.schema.json
    - Add L2 schema validation using l2-output.schema.json
    - Return CheckResult with specific non-conformant field identification
    - _Requirements: 20.1, 21.1, 27.1, 27.2_

  - [x] 20.2 Extend output_validator.py for L1.5 cross-reference checks
    - Verify every block_id in block_relations exists in blocks array
    - Verify every feature_id in related_features exists in L1 features array
    - Return structured error messages for dangling references
    - _Requirements: 20.2, 20.3, 20.4, 27.3_

  - [x] 20.3 Extend output_validator.py for L2 anomaly reference checks
    - Verify every node_id in anomaly affected_node_ids exists in Structure JSON
    - Verify anomaly_type values are valid enum members
    - Return structured error messages for invalid references
    - _Requirements: 21.2, 21.3, 21.4, 27.4_

  - [x] 20.4 Extend language_check.py for L1.5 relaxed rules
    - Apply same prohibited terms list to L1.5 block labels
    - Relaxed rule: technical term + functional description → passes; bare technical term → fails
    - _Requirements: 27.5_

  - [x] 20.5 Extend relation_check.py for L1.5 block relations
    - Validate L1.5 block_relations: static requires AST edge path, inferred requires non-empty inferred_reason
    - _Requirements: 11.3, 11.4_

- [x] 21. Checkpoint — Validation extension tests pass
  - Run `pytest tests/unit/core/validation/ tests/property/test_validation_properties.py` and confirm all validation tests pass (both existing Phase 1-min and new Phase 1-full). Ask the user if questions arise.

- [x] 22. Constraint prompt files
  - [x] 22.1 Extend l1-constraint.md with constraints ⑦–⑬
    - Add ⑦ Infrastructure Consolidation: identify infrastructure nodes, group into infrastructure_nodes array, produce single infrastructure_block in L1.5
    - Add ⑩ Output Validation Rules: describe all 5 validation checks the LLM output will face
    - Add ⑪ Source Code Review trigger conditions: generic names, unrecognized decorators, incomplete call relationships
    - Add ⑫ Anti-Hallucination: prohibit features without AST basis, prohibit static relations without edge paths, require inferred_reason for inferred relations
    - Add ⑬ Anti-Over-Interpretation: description proportional to AST info, prohibit speculative language for high-confidence, brief descriptions for sparse info
    - _Requirements: 10.1, 10.2, 10.3, 13.1, 13.2, 13.3, 13.4, 14.1, 14.6, 15.1, 15.2, 15.3, 15.4, 15.5, 16.1, 16.2, 16.3, 16.4_

  - [x] 22.2 Create prompts/l1-5-constraint.md
    - Define ⑧ L1.5 Output JSON Schema constraint: blocks array, block_relations array, infrastructure_block
    - Specify required fields per block and block_relation
    - Include inferred_reason conditional requirement
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [x] 22.3 Create prompts/l2-constraint.md
    - Define ⑨ L2 Output JSON Schema and Anomaly Detection constraint
    - Specify modules, module_interactions, anomalies arrays
    - Define anomaly detection rules: dead code, logic dead-ends, uncertain boundaries
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 23. CLI command extensions
  - [x] 23.1 Extend cli/main.py with new command registrations
    - Register: analyze, regenerate, render, estimate, history, config (with init subcommand)
    - All commands output JSON to stdout by default, support `--output <file>`
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7_

  - [x] 23.2 Implement analyze_cmd.py
    - Implement `the-door analyze <codebase-path>` one-click mode: extract → topology → batch read → validate → render
    - Support `--provider` flag and `--model` flag
    - Support `--yes` flag to skip cost confirmation
    - Display cost estimate and require confirmation when threshold exceeded
    - _Requirements: 5.1, 5.5, 7.5, 25.1_

  - [x] 23.3 Implement regenerate_cmd.py
    - Implement `the-door regenerate <feature_id>` to trigger per-node re-analysis
    - Display diff between previous and new result
    - Support `--accept` flag to accept new result
    - _Requirements: 4.1, 4.4, 4.5, 25.2_

  - [x] 23.4 Implement render_cmd.py
    - Implement `the-door render <output-json>` to generate Mermaid text from L1 or L1.5 JSON
    - Auto-detect L1 vs L1.5 input format
    - Output Mermaid text to stdout or `--output <file>`
    - _Requirements: 17.5, 25.3_

  - [x] 23.5 Implement estimate_cmd.py
    - Implement `the-door estimate <codebase-path>` to show token/cost preview
    - Display provider, model, batch count, input/output tokens, estimated cost
    - Show "free (local)" for Ollama
    - _Requirements: 7.1, 7.4, 25.4_

  - [x] 23.6 Implement history_cmd.py
    - Implement `the-door history <codebase-path>` to display narrative chain in human-readable format
    - Use NarrativeChain.format_human_readable()
    - Highlight regeneration events and structural changes distinctly
    - _Requirements: 22.4, 25.5, 28.1, 28.2, 28.3_

  - [x] 23.7 Implement config_cmd.py
    - Implement `the-door config init` to create default config.toml
    - Display created file path and next steps
    - _Requirements: 6.1, 25.6_

- [x] 24. Checkpoint — CLI tests pass
  - Run `pytest tests/unit/cli/` and confirm all CLI tests pass (both existing and new commands). Ask the user if questions arise.

- [x] 25. MCP Server extensions
  - [x] 25.1 Extend mcp/server.py with new tool registrations
    - Register: analyze, regenerate, render, history, estimate tools
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_

  - [x] 25.2 Implement mcp/tools/analyze_tool.py
    - Implement analyze MCP tool: execute complete one-click pipeline, return L1 + L1.5 output with confidence markers
    - _Requirements: 24.1_

  - [x] 25.3 Implement mcp/tools/regenerate_tool.py
    - Implement regenerate MCP tool: accept feature_id, return regenerated result with diff info
    - _Requirements: 24.2_

  - [x] 25.4 Implement mcp/tools/render_tool.py
    - Implement render MCP tool: accept L1 or L1.5 JSON, return Mermaid text
    - _Requirements: 24.3_

  - [x] 25.5 Implement mcp/tools/history_tool.py
    - Implement history MCP tool: return narrative chain for given codebase path
    - _Requirements: 24.4_

  - [x] 25.6 Implement mcp/tools/estimate_tool.py
    - Implement estimate MCP tool: return cost estimation for given codebase path
    - _Requirements: 24.5_

- [x] 26. Checkpoint — MCP tests pass
  - Run `pytest tests/unit/mcp/` and confirm all MCP tests pass (both existing and new tools). Ask the user if questions arise.

- [ ] 27. Integration tests
  - [ ]* 27.1 Write integration test: end-to-end analyze pipeline
    - Test: codebase path → extract → topology → batch read (mock LLM) → validate → render → complete L1 + L1.5 + Mermaid output
    - Verify output conforms to all schemas
    - Verify narrative chain created with correct records
    - _Requirements: 1.1, 1.5, 5.1, 17.1, 17.2_

  - [ ]* 27.2 Write integration test: cross-session continuity (unchanged)
    - Test: analyze → write narrative chain → new session → detect unchanged → use cached results without LLM calls
    - _Requirements: 3.3, 19.1, 19.2_

  - [ ]* 27.3 Write integration test: cross-session with structural changes
    - Test: analyze → write chain → modify structure (add/remove nodes) → detect changes → re-analyze only affected nodes
    - Verify unchanged nodes preserve confidence
    - _Requirements: 3.5, 19.1, 19.3, 19.4_

  - [ ]* 27.4 Write integration test: regeneration flow
    - Test: analyze → regenerate feature → verify diff marking → verify narrative record → accept new result
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [ ]* 27.5 Write integration test: MCP tool integration
    - Test: each new MCP tool (analyze, regenerate, render, history, estimate) with mock LLM
    - Verify correct tool registration, parameter handling, and response format
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_

  - [ ]* 27.6 Write integration test: cost estimation with threshold warning
    - Test: estimate exceeds threshold → warning displayed → requires confirmation
    - Test: estimate below threshold → proceeds without confirmation
    - _Requirements: 7.5_

- [x] 28. Final checkpoint — Full test suite passes
  - Run `pytest tests/` and confirm ALL tests pass: Phase 1-min's 100 existing tests + all new Phase 1-full tests (property, unit, integration). Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP (property tests, integration tests)
- Core implementation tasks (9.x, 10.x, 11.x, 12.x, 14.x–25.x) are ALL required
- Each task references specific requirements for traceability
- TDD order: tests written BEFORE implementation (tasks 4–7, 9–12 before tasks 14–20)
- Checkpoints at tasks 2, 8, 13, 15, 17, 19, 21, 24, 26, 28 ensure incremental validation
- Property tests validate the 21 new correctness properties (#13–#33) from the design document
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end pipeline flows
- All LLM-involving tests use MockLLMProvider — no real API calls in the test suite
- Phase 1-min's 100 existing tests MUST continue passing at every checkpoint
- Python with pytest + Hypothesis for all testing