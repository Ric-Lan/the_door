import asyncio, json, sys
sys.path.insert(0, 'the_door/src')
from the_door.mcp.tools.snapshot_write_tool import execute

with open('structure_v100.json', encoding='utf-8') as f:
    structure = json.load(f)

l1_features = [
    {"feature_id": "feat-cli-dispatch", "label": "CLI Entry Point & Command Routing", "description": "Main CLI dispatcher that registers and routes all user-facing commands via Click framework.", "source_node_count": 42, "confidence": "high"},
    {"feature_id": "feat-ast-extraction", "label": "AST Structure Extraction", "description": "Parses Python/JS/TS source files via tree-sitter AST, extracts classes, functions, methods, decorators, and call relationships into a structured node/edge graph.", "source_node_count": 58, "confidence": "high"},
    {"feature_id": "feat-topology", "label": "Call Graph & Topology Analysis", "description": "Analyzes the node/edge graph to compute in/out degrees, topology rank, entry point detection, and batch assignment for ordered processing.", "source_node_count": 45, "confidence": "high"},
    {"feature_id": "feat-llm-pipeline", "label": "LLM Analysis Pipeline", "description": "Orchestrates the full analyze flow: batch reading, LLM prompting, response parsing, and L1 feature generation. Supports external API key configuration.", "source_node_count": 95, "confidence": "high"},
    {"feature_id": "feat-diff-snapshots", "label": "Version Diff & Snapshot Management", "description": "Stores timestamped L1 snapshots, resolves baselines by label/tag/date/SHA, and computes added/removed/changed feature diffs between versions.", "source_node_count": 68, "confidence": "high"},
    {"feature_id": "feat-mcp-server", "label": "MCP Server Protocol Layer", "description": "Exposes all Door tools over the Model Context Protocol stdio transport, enabling MCP-compatible AI agents to call extract_structure, analyze, diff, and validate_output.", "source_node_count": 48, "confidence": "high"},
    {"feature_id": "feat-ui-server", "label": "Local Web UI Server", "description": "Starts a localhost HTTP server serving the graph visualization frontend with REST API endpoints for L1 graph data, L2 generation, and job status polling.", "source_node_count": 62, "confidence": "high"},
    {"feature_id": "feat-validation", "label": "LLM Output Validation", "description": "Validates AI-generated L1 output against five checks: schema, coverage, language, anchor, and relation integrity.", "source_node_count": 52, "confidence": "high"},
    {"feature_id": "feat-scope-verification", "label": "Scope Verification", "description": "Defines project delivery scopes and verifies whether the current L1 feature graph fulfills the declared scope commitments.", "source_node_count": 38, "confidence": "medium"},
    {"feature_id": "feat-mermaid-rendering", "label": "Mermaid & Report Rendering", "description": "Converts L1 features and diff results into Mermaid flowchart syntax and human-readable text reports for non-technical stakeholders.", "source_node_count": 33, "confidence": "high"},
    {"feature_id": "feat-timeline", "label": "Feature Evolution Timeline", "description": "Analyzes snapshot history to produce a narrative timeline showing how features appeared, changed, or disappeared across versions.", "source_node_count": 28, "confidence": "medium"},
    {"feature_id": "feat-vulnerability-scan", "label": "Vulnerability Scanning", "description": "Integrates with osv-scanner to detect known CVEs in codebase dependencies and surfaces results through CLI and MCP interfaces.", "source_node_count": 22, "confidence": "medium"},
]

relations = [
    {"from_feature": "feat-cli-dispatch", "to_feature": "feat-ast-extraction", "relation": "depends_on"},
    {"from_feature": "feat-cli-dispatch", "to_feature": "feat-llm-pipeline", "relation": "depends_on"},
    {"from_feature": "feat-cli-dispatch", "to_feature": "feat-diff-snapshots", "relation": "depends_on"},
    {"from_feature": "feat-cli-dispatch", "to_feature": "feat-ui-server", "relation": "depends_on"},
    {"from_feature": "feat-cli-dispatch", "to_feature": "feat-mcp-server", "relation": "depends_on"},
    {"from_feature": "feat-cli-dispatch", "to_feature": "feat-validation", "relation": "depends_on"},
    {"from_feature": "feat-cli-dispatch", "to_feature": "feat-scope-verification", "relation": "depends_on"},
    {"from_feature": "feat-cli-dispatch", "to_feature": "feat-mermaid-rendering", "relation": "depends_on"},
    {"from_feature": "feat-cli-dispatch", "to_feature": "feat-timeline", "relation": "depends_on"},
    {"from_feature": "feat-cli-dispatch", "to_feature": "feat-vulnerability-scan", "relation": "depends_on"},
    {"from_feature": "feat-ast-extraction", "to_feature": "feat-topology", "relation": "depends_on"},
    {"from_feature": "feat-topology", "to_feature": "feat-llm-pipeline", "relation": "depends_on"},
    {"from_feature": "feat-llm-pipeline", "to_feature": "feat-validation", "relation": "depends_on"},
    {"from_feature": "feat-llm-pipeline", "to_feature": "feat-diff-snapshots", "relation": "depends_on"},
    {"from_feature": "feat-llm-pipeline", "to_feature": "feat-mermaid-rendering", "relation": "depends_on"},
    {"from_feature": "feat-mcp-server", "to_feature": "feat-ast-extraction", "relation": "depends_on"},
    {"from_feature": "feat-mcp-server", "to_feature": "feat-llm-pipeline", "relation": "depends_on"},
    {"from_feature": "feat-mcp-server", "to_feature": "feat-diff-snapshots", "relation": "depends_on"},
    {"from_feature": "feat-mcp-server", "to_feature": "feat-validation", "relation": "depends_on"},
    {"from_feature": "feat-diff-snapshots", "to_feature": "feat-mermaid-rendering", "relation": "depends_on"},
    {"from_feature": "feat-diff-snapshots", "to_feature": "feat-timeline", "relation": "depends_on"},
    {"from_feature": "feat-ui-server", "to_feature": "feat-diff-snapshots", "relation": "depends_on"},
    {"from_feature": "feat-scope-verification", "to_feature": "feat-llm-pipeline", "relation": "depends_on"},
]

result = asyncio.run(execute({
    "codebase_path": r"C:\Users\Ric\Desktop\test-targets\the-door-v100",
    "l1_features": l1_features,
    "relations": relations,
    "label": "v1.0.0",
    "git_tags": ["v1.0.0"],
    "analyzed_files": structure["analyzed_files"],
}))

print(json.dumps(result, indent=2, ensure_ascii=False))
