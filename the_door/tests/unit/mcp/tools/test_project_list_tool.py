"""Unit tests for project_list MCP tool — group fields."""
from __future__ import annotations

import asyncio

import pytest

from the_door.core.registry import ProjectRegistry
from the_door.mcp.tools import project_list_tool


def test_project_list_includes_group_id_and_name(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "ms-ts"
    proj.mkdir()
    reg.create_group("samples")
    reg.add_to_group("samples", str(proj))
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    p = result["projects"][0]
    assert p["group_id"] == "g001"
    assert p["group_name"] == "samples"


def test_project_list_ungrouped_project_has_null_group(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "solo"
    proj.mkdir()
    reg.register(str(proj))
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    p = result["projects"][0]
    assert p["group_id"] is None
    assert p["group_name"] is None


def test_project_list_includes_groups_list(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("my-group")
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    assert "groups" in result
    assert result["groups"][0]["name"] == "my-group"


def test_project_list_hint_when_ungrouped_projects(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "solo"
    proj.mkdir()
    reg.register(str(proj))
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    assert "hint" in result
    assert "the-door group add" in result["hint"]


def test_project_list_no_hint_when_all_grouped(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "proj"
    proj.mkdir()
    reg.create_group("grp")
    reg.add_to_group("grp", str(proj))
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    assert "hint" not in result


def test_project_list_ungrouped_count(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    for name in ["a", "b"]:
        d = tmp_path / name
        d.mkdir()
        reg.register(str(d))
    monkeypatch.setattr("the_door.mcp.tools.project_list_tool.ProjectRegistry", lambda: reg)
    result = asyncio.run(project_list_tool.execute({}))
    assert result["ungrouped_count"] == 2
