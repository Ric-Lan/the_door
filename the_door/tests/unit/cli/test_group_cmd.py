"""Unit tests for `the-door group` CLI commands."""
from __future__ import annotations

import pytest
from click.testing import CliRunner
from pathlib import Path

from the_door.cli.group_cmd import group_group
from the_door.core.registry import ProjectRegistry


@pytest.fixture
def runner():
    return CliRunner()


def test_group_create_prints_confirmation(runner, tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["create", "my-group"])
    assert result.exit_code == 0
    assert "my-group" in result.output
    assert "g001" in result.output


def test_group_create_duplicate_prints_error(runner, tmp_path, monkeypatch):
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("my-group")
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["create", "my-group"])
    assert result.exit_code != 0
    assert "已存在" in result.output


def test_group_add_prints_confirmation(runner, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("grp")
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["add", "grp", str(proj)])
    assert result.exit_code == 0
    assert "proj" in result.output


def test_group_add_nonexistent_group_prints_error(runner, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["add", "no-such-group", str(proj)])
    assert result.exit_code != 0
    assert "群組不存在" in result.output


def test_group_list_shows_members(runner, tmp_path, monkeypatch):
    proj = tmp_path / "ms-ts"
    proj.mkdir()
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("samples")
    reg.add_to_group("samples", str(proj))
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["list"])
    assert result.exit_code == 0
    assert "samples" in result.output
    assert "ms-ts" in result.output


def test_group_list_shows_ungrouped(runner, tmp_path, monkeypatch):
    proj = tmp_path / "solo-proj"
    proj.mkdir()
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.register(str(proj))
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["list"])
    assert "solo-proj" in result.output
    assert "未分群" in result.output


def test_group_remove_prints_confirmation(runner, tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    reg = ProjectRegistry(registry_path=tmp_path / "reg.json")
    reg.create_group("grp")
    reg.add_to_group("grp", str(proj))
    monkeypatch.setattr("the_door.cli.group_cmd.ProjectRegistry", lambda: reg)
    result = runner.invoke(group_group, ["remove", "grp", str(proj)])
    assert result.exit_code == 0
    assert "移除" in result.output
