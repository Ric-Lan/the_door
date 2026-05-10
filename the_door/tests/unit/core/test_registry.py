"""Unit tests for ProjectRegistry."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from the_door.core.registry import ProjectRegistry


@pytest.fixture
def registry(tmp_path):
    """A ProjectRegistry backed by a temp directory."""
    return ProjectRegistry(registry_path=tmp_path / "registry.json")


class TestProjectRegistry:

    def test_register_new_project_gets_sequential_id(self, registry, tmp_path):
        """First registered project gets id '001'."""
        project_dir = tmp_path / "my-web-app"
        project_dir.mkdir()
        pid = registry.register(str(project_dir))
        assert pid == "001"

    def test_register_idempotent_same_path(self, registry, tmp_path):
        """Registering the same path twice returns the same id."""
        project_dir = tmp_path / "my-web-app"
        project_dir.mkdir()
        pid1 = registry.register(str(project_dir))
        pid2 = registry.register(str(project_dir))
        assert pid1 == pid2
        assert len(registry.list_projects()) == 1

    def test_name_derived_from_folder(self, registry, tmp_path):
        """Project name is the last component of the resolved path."""
        project_dir = tmp_path / "game-engine"
        project_dir.mkdir()
        registry.register(str(project_dir))
        projects = registry.list_projects()
        assert projects[0]["name"] == "game-engine"

    def test_sequential_ids_increment(self, registry, tmp_path):
        """Multiple projects get 001, 002, 003 in order."""
        for name in ["proj-a", "proj-b", "proj-c"]:
            d = tmp_path / name
            d.mkdir()
            registry.register(str(d))
        ids = [p["id"] for p in registry.list_projects()]
        assert ids == ["001", "002", "003"]

    def test_list_projects_sorted_by_id(self, registry):
        """list_projects returns entries sorted by id ascending even when stored out of order."""
        registry._save({
            "003": {"name": "proj-c", "path": "/c", "registered_at": "2026-01-01T00:00:00+00:00"},
            "001": {"name": "proj-a", "path": "/a", "registered_at": "2026-01-01T00:00:00+00:00"},
            "002": {"name": "proj-b", "path": "/b", "registered_at": "2026-01-01T00:00:00+00:00"},
        })
        ids = [p["id"] for p in registry.list_projects()]
        assert ids == ["001", "002", "003"]

    def test_get_by_id_returns_project(self, registry, tmp_path):
        """get_by_id returns the correct project dict."""
        project_dir = tmp_path / "api-server"
        project_dir.mkdir()
        pid = registry.register(str(project_dir))
        result = registry.get_by_id(pid)
        assert result is not None
        assert result["name"] == "api-server"
        assert result["id"] == "001"

    def test_get_by_id_returns_none_for_missing(self, registry):
        """get_by_id returns None when id does not exist."""
        assert registry.get_by_id("999") is None

    def test_registry_persists_to_disk(self, tmp_path):
        """Data survives across separate ProjectRegistry instances."""
        path = tmp_path / "registry.json"
        project_dir = tmp_path / "my-app"
        project_dir.mkdir()

        ProjectRegistry(registry_path=path).register(str(project_dir))
        projects = ProjectRegistry(registry_path=path).list_projects()
        assert len(projects) == 1
        assert projects[0]["name"] == "my-app"
