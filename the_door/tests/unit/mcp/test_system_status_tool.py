"""Unit tests for system_status MCP tool."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_system_status_returns_state_and_next_actions(tmp_path):
    from the_door.mcp.tools import system_status_tool
    result = await system_status_tool.execute({"project_path": str(tmp_path)})
    assert "state" in result
    assert "next_actions" in result
    assert result["state"]["has_dot_the_door"] is False
