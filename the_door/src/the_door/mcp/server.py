"""The Door MCP Server — exposes all tools."""
from __future__ import annotations

import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.topology.topology_analyzer import TopologyAnalyzer
from the_door.core.validation.output_validator import OutputValidator
from the_door.mcp.tools import render_tool, history_tool
from the_door.mcp.tools import diff_tool, snapshot_create_tool, snapshot_list_tool
from the_door.mcp.tools import scan_tool
from the_door.mcp.tools import scope_verify_tool, scope_create_tool, doubt_list_tool, doubt_transition_tool
from the_door.mcp.tools import timeline_tool, snapshot_prune_tool
from the_door.mcp.tools import snapshot_write_tool
from the_door.mcp.tools import project_list_tool
from the_door.mcp.tools import system_status_tool
from the_door.mcp.tools import analyze_changes_tool
from the_door.mcp.tools import snapshot_patch_tool
from the_door.mcp.tools import localize_datamodel_tool, verify_contract_tool
from the_door.mcp.tools import edge_residue_tool


class TheDoorMCPServer:
    """MCP Server exposing The Door's core functionality."""

    def __init__(self):
        self._server = Server("the-door")
        self._setup_tools()

    def _setup_tools(self):
        @self._server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="extract_structure",
                    description="Extract AST structure and topology from a codebase path.",
                    inputSchema={
                        "type": "object",
                        "required": ["codebase_path"],
                        "properties": {
                            "codebase_path": {
                                "type": "string",
                                "description": "Path to the codebase root directory",
                            }
                        },
                    },
                ),
                Tool(
                    name="validate_output",
                    description="Validate LLM output against Structure JSON using 5 checks.",
                    inputSchema={
                        "type": "object",
                        "required": ["llm_output", "structure_json"],
                        "properties": {
                            "llm_output": {
                                "type": "object",
                                "description": "The LLM-generated L1 output JSON",
                            },
                            "structure_json": {
                                "type": "object",
                                "description": "The Structure JSON from extract_structure",
                            },
                        },
                    },
                ),
                Tool(
                    name="render",
                    description="Generate Mermaid flowchart text from L1 or L1.5 JSON.",
                    inputSchema=render_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="history",
                    description="Return narrative chain for a given codebase path.",
                    inputSchema=history_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="diff",
                    description="Compare current analysis against a baseline version.",
                    inputSchema=diff_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="snapshot_create",
                    description="Create a manual snapshot from the most recent analysis output.",
                    inputSchema=snapshot_create_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="snapshot_list",
                    description="List all available snapshots.",
                    inputSchema=snapshot_list_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="snapshot_write",
                    description=(
                        "Write L1 analysis results produced by the calling AI directly into the snapshot store. "
                        "Use this after extract_structure + your own analysis, instead of calling analyze. "
                        "No external LLM API key required — you are the LLM."
                    ),
                    inputSchema=snapshot_write_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="scan",
                    description="Scan codebase for known vulnerabilities.",
                    inputSchema=scan_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="scope_verify",
                    description="Run scope verification against a scope definition.",
                    inputSchema=scope_verify_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="scope_create",
                    description="Create a new scope definition file.",
                    inputSchema=scope_create_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="doubt_list",
                    description="List doubt records with optional filters.",
                    inputSchema=doubt_list_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="doubt_transition",
                    description="Transition a doubt to a new state.",
                    inputSchema=doubt_transition_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="timeline",
                    description="Analyze feature evolution timeline across snapshots.",
                    inputSchema=timeline_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="snapshot_prune",
                    description="Compute snapshot retention decisions based on retention policy.",
                    inputSchema=snapshot_prune_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="project_list",
                    description=(
                        "List all codebases registered in The Door's project registry. "
                        "Use this to discover available projects before calling extract_structure or snapshot_write."
                    ),
                    inputSchema=project_list_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="system_status",
                    description="Report current project state + next-action suggestions",
                    inputSchema=system_status_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="analyze_changes",
                    description=(
                        "Read-only incremental analysis: compute IncrementalDiff between current "
                        "codebase and a baseline snapshot (label / tag / SHA / date / version_id)."
                    ),
                    inputSchema=analyze_changes_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="snapshot_patch",
                    description=(
                        "Patch source_nodes of an existing snapshot in-place without changing "
                        "version_id or timestamp. Use after extract_structure to backfill node "
                        "attribution for existing snapshots."
                    ),
                    inputSchema=snapshot_patch_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="localize_data_model",
                    description="Tier 0 local localization of data-model touch points (zero token).",
                    inputSchema=localize_datamodel_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="verify_data_model_contract",
                    description="Tier 1 bidirectional contract diff over agent-normalized field-sets.",
                    inputSchema=verify_contract_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="edge_residue",
                    description="Persist the membrane noise residue (off-grid + low-confidence edges) as a viewable artifact. Zero token, zero key. Run after extract_structure, before snapshot_write.",
                    inputSchema=edge_residue_tool.TOOL_SCHEMA,
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict):
            if name == "extract_structure":
                return await self._extract_structure(arguments)
            elif name == "validate_output":
                return await self._validate_output(arguments)
            elif name == "render":
                return await self._dispatch_tool(render_tool, arguments)
            elif name == "history":
                return await self._dispatch_tool(history_tool, arguments)
            elif name == "diff":
                return await self._dispatch_tool(diff_tool, arguments)
            elif name == "snapshot_create":
                return await self._dispatch_tool(snapshot_create_tool, arguments)
            elif name == "snapshot_list":
                return await self._dispatch_tool(snapshot_list_tool, arguments)
            elif name == "snapshot_write":
                return await self._dispatch_tool(snapshot_write_tool, arguments)
            elif name == "scan":
                return await self._dispatch_tool(scan_tool, arguments)
            elif name == "scope_verify":
                return await self._dispatch_tool(scope_verify_tool, arguments)
            elif name == "scope_create":
                return await self._dispatch_tool(scope_create_tool, arguments)
            elif name == "doubt_list":
                return await self._dispatch_tool(doubt_list_tool, arguments)
            elif name == "doubt_transition":
                return await self._dispatch_tool(doubt_transition_tool, arguments)
            elif name == "timeline":
                return await self._dispatch_tool(timeline_tool, arguments)
            elif name == "snapshot_prune":
                return await self._dispatch_tool(snapshot_prune_tool, arguments)
            elif name == "project_list":
                return await self._dispatch_tool(project_list_tool, arguments)
            elif name == "system_status":
                return await self._dispatch_tool(system_status_tool, arguments)
            elif name == "analyze_changes":
                return await self._dispatch_tool(analyze_changes_tool, arguments)
            elif name == "snapshot_patch":
                return await self._dispatch_tool(snapshot_patch_tool, arguments)
            elif name == "localize_data_model":
                return await self._dispatch_tool(localize_datamodel_tool, arguments)
            elif name == "verify_data_model_contract":
                return await self._dispatch_tool(verify_contract_tool, arguments)
            elif name == "edge_residue":
                return await self._dispatch_tool(edge_residue_tool, arguments)
            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    async def _dispatch_tool(self, tool_module, arguments: dict):
        """Dispatch to a tool module's execute function."""
        try:
            result = await tool_module.execute(arguments)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def _extract_structure(self, arguments: dict):
        codebase_path = arguments.get("codebase_path", "")
        try:
            extractor = ASTExtractor()
            result = extractor.extract(codebase_path)

            analyzer = TopologyAnalyzer()
            topology = analyzer.analyze(result.nodes, result.edges)

            output = {
                "files": [{"path": f.path, "language": f.language} for f in result.files],
                "nodes": [
                    {
                        "node_id": n.node_id, "type": n.type, "name": n.name,
                        "file": n.file, "language": n.language,
                        "decorators": n.decorators, "parameters": n.parameters,
                        "return_type": n.return_type, "docstring": n.docstring,
                        "comments": n.comments,
                    }
                    for n in result.nodes
                ],
                "edges": [
                    {"from": e.from_node, "to": e.to_node, "type": e.type}
                    for e in result.edges
                ],
                "topology": [
                    {
                        "node_id": t.node_id, "in_degree": t.in_degree,
                        "out_degree": t.out_degree, "topology_rank": t.topology_rank,
                        "is_entry_point": t.is_entry_point, "batch_assignment": t.batch_assignment,
                    }
                    for t in topology.entries
                ],
                "analyzed_files": [f.path for f in result.files],
            }
            return [TextContent(type="text", text=json.dumps(output, ensure_ascii=False))]
        except (FileNotFoundError, ValueError) as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def _validate_output(self, arguments: dict):
        llm_output = arguments.get("llm_output", {})
        structure_json = arguments.get("structure_json", {})
        try:
            validator = OutputValidator()
            result = validator.validate(llm_output, structure_json)
            output = {
                "passed": result.passed,
                "schema": {"passed": result.schema_result.passed, "errors": result.schema_result.errors},
                "coverage": {"passed": result.coverage_result.passed, "errors": result.coverage_result.errors},
                "language": {"passed": result.language_result.passed, "errors": result.language_result.errors},
                "anchor": {"passed": result.anchor_result.passed, "errors": result.anchor_result.errors},
                "relation": {"passed": result.relation_result.passed, "errors": result.relation_result.errors},
            }
            return [TextContent(type="text", text=json.dumps(output))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    def run(self):
        """Start the MCP server on stdio transport."""
        import asyncio
        asyncio.run(self._run_async())

    async def _run_async(self):
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream, write_stream, self._server.create_initialization_options()
            )
