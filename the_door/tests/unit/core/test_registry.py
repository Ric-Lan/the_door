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


class TestProjectRegistryGroups:

    def test_list_projects_skips_groups_key(self, registry):
        """list_projects must not include __groups__ as a project entry."""
        registry._save({
            "001": {"name": "proj-a", "path": "/a", "registered_at": "2026-01-01T00:00:00+00:00"},
            "__groups__": {"g001": {"name": "grp", "member_ids": ["001"], "created_at": "2026-01-01T00:00:00+00:00"}},
        })
        projects = registry.list_projects()
        assert len(projects) == 1
        assert projects[0]["id"] == "001"

    def test_create_group_returns_sequential_gid(self, registry):
        gid = registry.create_group("frontend")
        assert gid == "g001"
        gid2 = registry.create_group("backend")
        assert gid2 == "g002"

    def test_create_group_duplicate_name_raises(self, registry):
        registry.create_group("frontend")
        with pytest.raises(ValueError, match="群組名稱已存在"):
            registry.create_group("frontend")

    def test_add_to_group_auto_registers_path(self, registry, tmp_path):
        registry.create_group("my-group")
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        result = registry.add_to_group("my-group", str(project_dir))
        assert result["project_name"] == "proj"
        assert result["group_id"] == "g001"
        assert len(registry.list_projects()) == 1

    def test_add_to_group_idempotent(self, registry, tmp_path):
        """Adding same project twice is a no-op."""
        registry.create_group("grp")
        d = tmp_path / "p"
        d.mkdir()
        registry.add_to_group("grp", str(d))
        registry.add_to_group("grp", str(d))
        groups = registry.list_groups()
        assert len(groups[0]["members"]) == 1

    def test_add_to_group_already_in_another_raises(self, registry, tmp_path):
        registry.create_group("grp-a")
        registry.create_group("grp-b")
        d = tmp_path / "p"
        d.mkdir()
        registry.add_to_group("grp-a", str(d))
        with pytest.raises(ValueError, match="已在群組"):
            registry.add_to_group("grp-b", str(d))

    def test_remove_from_group(self, registry, tmp_path):
        registry.create_group("grp")
        d = tmp_path / "p"
        d.mkdir()
        registry.add_to_group("grp", str(d))
        registry.remove_from_group("grp", str(d))
        assert registry.list_groups()[0]["members"] == []

    def test_remove_not_in_group_raises(self, registry, tmp_path):
        registry.create_group("grp")
        d = tmp_path / "p"
        d.mkdir()
        registry.register(str(d))
        with pytest.raises(ValueError, match="不在群組"):
            registry.remove_from_group("grp", str(d))

    def test_list_groups_returns_members_with_details(self, registry, tmp_path):
        registry.create_group("samples")
        d = tmp_path / "ms-ts"
        d.mkdir()
        registry.add_to_group("samples", str(d))
        groups = registry.list_groups()
        assert len(groups) == 1
        assert groups[0]["name"] == "samples"
        assert groups[0]["members"][0]["name"] == "ms-ts"

    def test_get_group_for_project_returns_group(self, registry, tmp_path):
        registry.create_group("g")
        d = tmp_path / "p"
        d.mkdir()
        registry.add_to_group("g", str(d))
        pid = registry.get_by_path(str(d))["id"]
        group = registry.get_group_for_project(pid)
        assert group["name"] == "g"

    def test_get_group_for_project_returns_none_when_ungrouped(self, registry, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        registry.register(str(d))
        assert registry.get_group_for_project("001") is None

    def test_get_by_path_returns_project(self, registry, tmp_path):
        d = tmp_path / "my-app"
        d.mkdir()
        registry.register(str(d))
        result = registry.get_by_path(str(d))
        assert result is not None
        assert result["name"] == "my-app"

    def test_get_by_path_returns_none_for_unknown(self, registry, tmp_path):
        assert registry.get_by_path(str(tmp_path / "nope")) is None

    def test_update_last_opened_writes_timestamp(self, registry, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        registry.register(str(d))
        registry.update_last_opened(str(d))
        projects = registry.list_projects()
        assert projects[0]["last_opened_at"] is not None

    def test_get_most_recently_opened_returns_latest(self, registry, tmp_path):
        for name in ["a", "b"]:
            d = tmp_path / name
            d.mkdir()
            registry.register(str(d))
        registry.update_last_opened(str(tmp_path / "b"))
        result = registry.get_most_recently_opened()
        assert result["name"] == "b"

    def test_get_most_recently_opened_returns_none_when_all_null(self, registry, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        registry.register(str(d))
        assert registry.get_most_recently_opened() is None

    def test_find_active_project_detects_checklist_newer_than_last_opened(self, registry, tmp_path):
        import time
        d = tmp_path / "proj"
        d.mkdir()
        (d / ".the-door").mkdir()
        registry.register(str(d))
        registry.update_last_opened(str(d))
        time.sleep(0.05)
        (d / ".the-door" / "checklist.json").write_text("{}")
        result = registry.find_active_project()
        assert result is not None
        assert result["name"] == "proj"

    def test_find_active_project_returns_none_when_checklist_older_than_last_opened(self, registry, tmp_path):
        import time
        d = tmp_path / "proj"
        d.mkdir()
        (d / ".the-door").mkdir()
        (d / ".the-door" / "checklist.json").write_text("{}")
        time.sleep(0.05)
        registry.register(str(d))
        registry.update_last_opened(str(d))
        result = registry.find_active_project()
        assert result is None

    def test_backward_compat_no_groups_key(self, registry, tmp_path):
        """Old registry.json without __groups__ works transparently."""
        d = tmp_path / "old-proj"
        d.mkdir()
        registry._save({"001": {"name": "old-proj", "path": str(d), "registered_at": "2026-01-01T00:00:00+00:00"}})
        assert registry.list_groups() == []
        assert registry.get_most_recently_opened() is None
        assert len(registry.list_projects()) == 1
