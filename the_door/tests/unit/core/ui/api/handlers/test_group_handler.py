"""Unit tests for GET /api/group handler."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from the_door.core.registry import ProjectRegistry
from the_door.core.ui.api.context import APIContext
from the_door.core.ui.api.handlers.group import GroupHandlers


def _make_ctx(project_root: Path) -> APIContext:
    ctx = MagicMock(spec=APIContext)
    ctx.project_root = project_root
    return ctx


def test_get_group_returns_group_when_project_is_grouped(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "ms-ts"
    proj.mkdir()
    reg.create_group("samples")
    reg.add_to_group("samples", str(proj))
    monkeypatch.setattr("the_door.core.ui.api.handlers.group.ProjectRegistry", lambda: reg)
    ctx = _make_ctx(proj)
    handler = GroupHandlers(ctx)
    status, body = handler.get_group()
    assert status == 200
    assert body["group"]["name"] == "samples"
    assert len(body["group"]["members"]) == 1
    assert body["group"]["members"][0]["is_current"] is True
    assert body["current_project"]["name"] == "ms-ts"


def test_get_group_returns_null_group_when_ungrouped(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj = tmp_path / "solo"
    proj.mkdir()
    reg.register(str(proj))
    monkeypatch.setattr("the_door.core.ui.api.handlers.group.ProjectRegistry", lambda: reg)
    ctx = _make_ctx(proj)
    handler = GroupHandlers(ctx)
    status, body = handler.get_group()
    assert status == 200
    assert body["group"] is None
    assert "hint" in body
    assert "the-door group add" in body["hint"]


def test_get_group_unregistered_project_returns_null(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    monkeypatch.setattr("the_door.core.ui.api.handlers.group.ProjectRegistry", lambda: reg)
    proj = tmp_path / "unknown"
    proj.mkdir()
    ctx = _make_ctx(proj)
    handler = GroupHandlers(ctx)
    status, body = handler.get_group()
    assert status == 200
    assert body["group"] is None


def test_get_group_shows_all_members_with_is_current_flag(tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    proj_a.mkdir()
    proj_b.mkdir()
    reg.create_group("grp")
    reg.add_to_group("grp", str(proj_a))
    reg.add_to_group("grp", str(proj_b))
    monkeypatch.setattr("the_door.core.ui.api.handlers.group.ProjectRegistry", lambda: reg)
    ctx = _make_ctx(proj_a)
    handler = GroupHandlers(ctx)
    status, body = handler.get_group()
    members = body["group"]["members"]
    assert len(members) == 2
    current = [m for m in members if m["is_current"]]
    other = [m for m in members if not m["is_current"]]
    assert len(current) == 1 and current[0]["name"] == "proj-a"
    assert len(other) == 1 and other[0]["name"] == "proj-b"
