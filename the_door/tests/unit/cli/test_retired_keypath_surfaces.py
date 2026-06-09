"""Guardrail: the analyze key-path surfaces retired in T5-A (丙案) stay gone.

Terminal state = zero API-key interface, single agent-as-LLM path. These
assertions fail loudly if a retired CLI command or MCP tool is ever
re-registered.
"""
from __future__ import annotations

import pytest

from mcp.types import ListToolsRequest

_RETIRED_CLI = {"analyze", "update", "estimate", "regenerate", "wizard", "config"}
_RETIRED_MCP = {"analyze", "update", "estimate", "regenerate"}


def test_retired_cli_commands_absent():
    from the_door.cli.main import main
    present = set(main.commands)
    leaked = present & _RETIRED_CLI
    assert leaked == set(), f"retired CLI commands re-registered: {sorted(leaked)}"
    # Sanity: the surviving agent-as-LLM / display commands are still there.
    assert {"status", "extract", "diff", "ui"} <= present


@pytest.mark.asyncio
async def test_retired_mcp_tools_absent():
    from the_door.mcp.server import TheDoorMCPServer

    server = TheDoorMCPServer()
    handler = server._server.request_handlers[ListToolsRequest]
    result = await handler(None)
    tool_names = {t.name for t in result.root.tools}
    leaked = tool_names & _RETIRED_MCP
    assert leaked == set(), f"retired MCP tools re-registered: {sorted(leaked)}"
    # Sanity: the agent-as-LLM chain tools survive.
    assert {"extract_structure", "edge_residue", "snapshot_write"} <= tool_names
