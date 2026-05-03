"""CLI mcp-serve command — starts the MCP server."""
from __future__ import annotations

import click


@click.command("mcp-serve")
def mcp_serve_cmd():
    """Start The Door MCP Server."""
    from the_door.mcp.server import TheDoorMCPServer
    server = TheDoorMCPServer()
    server.run()
