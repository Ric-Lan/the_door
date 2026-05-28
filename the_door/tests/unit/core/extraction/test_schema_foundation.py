"""Tests for Task 01 — ScopeRules / ScopeContext / Edge.resolution / serializer backward compat."""
from __future__ import annotations

import pytest

from the_door.core.extraction.language_configs import (
    LANGUAGE_CONFIGS,
    LanguageConfig,
    ScopeContext,
    ScopeRules,
)
from the_door.core.extraction.structure_serializer import (
    build_structure_dict,
    default_structure_path,
    parse_structure_dict,
    write_structure_json,
    write_versioned_structure,
)
from the_door.models import (
    ASTNode,
    CostConfirmationRequired,
    DoubtNotFoundError,
    DoubtTerminalError,
    Edge,
    InvalidTransitionError,
    PipelineError,
    ScopeDefinitionError,
    SnapshotNotFoundError,
    StructureJSON,
)


# ── ScopeRules schema ──────────────────────────────────────────────────────────

class TestScopeRulesSchema:
    def test_can_construct_with_all_fields(self):
        rules = ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="multiple",
            dynamic_markers=frozenset({"__getattr__"}),
        )
        assert rules.import_resolution == "qualified"
        assert rules.function_resolution == "file_local_then_imports"
        assert rules.method_resolution == "class_local_then_inherited"
        assert rules.inheritance_resolution == "multiple"
        assert "__getattr__" in rules.dynamic_markers

    def test_dynamic_markers_defaults_to_empty_frozenset(self):
        rules = ScopeRules(
            import_resolution="es_module",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="single",
        )
        assert rules.dynamic_markers == frozenset()

    def test_is_frozen(self):
        rules = ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="multiple",
        )
        with pytest.raises(Exception):
            rules.import_resolution = "namespaced"  # type: ignore

    def test_import_resolution_valid_literals(self):
        for val in ("qualified", "namespaced", "module_path", "es_module"):
            rules = ScopeRules(
                import_resolution=val,  # type: ignore
                function_resolution="file_local_then_imports",
                method_resolution="class_local_then_inherited",
                inheritance_resolution="single",
            )
            assert rules.import_resolution == val

    def test_function_resolution_valid_literals(self):
        for val in ("file_local_then_imports", "package_local_then_imports", "global"):
            rules = ScopeRules(
                import_resolution="qualified",
                function_resolution=val,  # type: ignore
                method_resolution="class_local_then_inherited",
                inheritance_resolution="single",
            )
            assert rules.function_resolution == val

    def test_method_resolution_valid_literals(self):
        for val in ("class_local_then_inherited", "structural", "trait_dispatch", "dynamic_dispatch"):
            rules = ScopeRules(
                import_resolution="qualified",
                function_resolution="file_local_then_imports",
                method_resolution=val,  # type: ignore
                inheritance_resolution="single",
            )
            assert rules.method_resolution == val

    def test_inheritance_resolution_valid_literals(self):
        for val in ("single", "multiple", "mixin", "interface_only"):
            rules = ScopeRules(
                import_resolution="qualified",
                function_resolution="file_local_then_imports",
                method_resolution="class_local_then_inherited",
                inheritance_resolution=val,  # type: ignore
            )
            assert rules.inheritance_resolution == val


# ── ScopeContext schema ────────────────────────────────────────────────────────

class TestScopeContextSchema:
    def test_can_construct(self):
        ctx = ScopeContext(
            current_file="orders/service.py",
            import_aliases={"v": "validate"},
            caller_class="OrderService",
            caller_name="checkout",
        )
        assert ctx.current_file == "orders/service.py"
        assert ctx.import_aliases == {"v": "validate"}
        assert ctx.caller_class == "OrderService"
        assert ctx.caller_name == "checkout"

    def test_caller_name_defaults_to_empty_string(self):
        ctx = ScopeContext(
            current_file="main.py",
            import_aliases={},
            caller_class=None,
        )
        assert ctx.caller_name == ""

    def test_caller_class_can_be_none(self):
        ctx = ScopeContext(current_file="main.py", import_aliases={}, caller_class=None)
        assert ctx.caller_class is None

    def test_has_dynamic_marker_true_when_caller_name_matches(self):
        ctx = ScopeContext(
            current_file="x.py",
            import_aliases={},
            caller_class=None,
            caller_name="__getattr__",
        )
        assert ctx.has_dynamic_marker(frozenset({"__getattr__", "method_missing"})) is True

    def test_has_dynamic_marker_false_when_no_match(self):
        ctx = ScopeContext(
            current_file="x.py",
            import_aliases={},
            caller_class=None,
            caller_name="checkout",
        )
        assert ctx.has_dynamic_marker(frozenset({"__getattr__", "method_missing"})) is False

    def test_has_dynamic_marker_false_on_empty_markers(self):
        ctx = ScopeContext(
            current_file="x.py",
            import_aliases={},
            caller_class=None,
            caller_name="__getattr__",
        )
        assert ctx.has_dynamic_marker(frozenset()) is False


# ── LanguageConfig.scope_rules ─────────────────────────────────────────────────

class TestLanguageConfigScopeRules:
    def test_scope_rules_field_defaults_to_none(self):
        cfg = LanguageConfig()
        assert cfg.scope_rules is None

    def test_scope_rules_can_be_set(self):
        rules = ScopeRules(
            import_resolution="qualified",
            function_resolution="file_local_then_imports",
            method_resolution="class_local_then_inherited",
            inheritance_resolution="multiple",
        )
        cfg = LanguageConfig(scope_rules=rules)
        assert cfg.scope_rules is rules

    def test_existing_language_configs_still_constructable(self):
        assert "python" in LANGUAGE_CONFIGS
        assert LANGUAGE_CONFIGS["python"].function_types


# ── Edge.resolution ────────────────────────────────────────────────────────────

class TestEdgeResolution:
    def test_edge_default_resolution_is_name_match(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls")
        assert e.resolution == "name_match"

    def test_edge_resolution_can_be_set_explicitly(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls", resolution="scope_rule")
        assert e.resolution == "scope_rule"

    def test_edge_resolution_accepts_all_valid_values(self):
        for val in ("scope_rule", "import_alias", "name_match", "skipped_dynamic"):
            e = Edge(from_node="A.foo", to_node="B.bar", type="calls", resolution=val)
            assert e.resolution == val

    def test_edge_still_frozen(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls")
        with pytest.raises(Exception):
            e.resolution = "scope_rule"  # type: ignore

    def test_edge_type_field_still_named_type_not_edge_type(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls")
        assert hasattr(e, "type")
        assert not hasattr(e, "edge_type")

    def test_edge_type_value_is_calls_not_call(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls")
        assert e.type == "calls"


# ── structure_serializer backward compat ──────────────────────────────────────

def _make_structure(edges):
    return StructureJSON(
        files=[],
        nodes=[],
        edges=edges,
        topology=[],
    )


class TestSerializerResolution:
    def test_build_structure_dict_writes_resolution_field(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls", resolution="scope_rule")
        structure = _make_structure([e])
        data = build_structure_dict(structure, None)
        assert data["edges"][0]["resolution"] == "scope_rule"

    def test_build_structure_dict_writes_name_match_for_default(self):
        e = Edge(from_node="A.foo", to_node="B.bar", type="calls")
        structure = _make_structure([e])
        data = build_structure_dict(structure, None)
        assert data["edges"][0]["resolution"] == "name_match"

    def test_parse_structure_dict_reads_resolution_when_present(self):
        data = {
            "files": [],
            "nodes": [],
            "edges": [{"from": "A.foo", "to": "B.bar", "type": "calls", "resolution": "import_alias"}],
            "topology": [],
        }
        result = parse_structure_dict(data)
        assert result.edges[0].resolution == "import_alias"

    def test_parse_structure_dict_defaults_resolution_to_name_match_for_old_snapshots(self):
        data = {
            "files": [],
            "nodes": [],
            "edges": [{"from": "A.foo", "to": "B.bar", "type": "calls"}],
            "topology": [],
        }
        result = parse_structure_dict(data)
        assert result.edges[0].resolution == "name_match"

    def test_roundtrip_preserves_resolution(self):
        e = Edge(from_node="X.m", to_node="Y.n", type="extends", resolution="skipped_dynamic")
        structure = _make_structure([e])
        data = build_structure_dict(structure, None)
        restored = parse_structure_dict(data)
        assert restored.edges[0].resolution == "skipped_dynamic"


# ── Pre-existing models.py exception coverage (needed for 100% gate) ─────────

class TestModelsExceptions:
    def test_snapshot_not_found_error(self):
        err = SnapshotNotFoundError("v1.0.0", [])
        assert err.reference == "v1.0.0"
        assert err.available == []
        assert "v1.0.0" in str(err)

    def test_scope_definition_error(self):
        err = ScopeDefinitionError("scope.yaml", "bad format")
        assert err.file_path == "scope.yaml"
        assert "scope.yaml" in str(err)

    def test_doubt_not_found_error(self):
        err = DoubtNotFoundError("doubt-123")
        assert err.doubt_id == "doubt-123"
        assert "doubt-123" in str(err)

    def test_invalid_transition_error(self):
        err = InvalidTransitionError("discovered", "resolved")
        assert err.current_state == "discovered"
        assert err.target_state == "resolved"

    def test_doubt_terminal_error(self):
        err = DoubtTerminalError("doubt-abc", "fixed")
        assert err.doubt_id == "doubt-abc"
        assert err.current_state == "fixed"

    def test_pipeline_error(self):
        err = PipelineError("analyze", "timeout")
        assert err.step_name == "analyze"
        assert "analyze" in str(err)

    def test_cost_confirmation_required(self):
        err = CostConfirmationRequired(1.23, 5000)
        assert err.estimated_cost == 1.23
        assert err.total_tokens == 5000
        assert "1.2300" in str(err)


# ── structure_serializer file I/O helpers coverage ───────────────────────────

class TestSerializerFileHelpers:
    def test_default_structure_path(self, tmp_path):
        p = default_structure_path(tmp_path)
        assert p == tmp_path / ".the-door" / "structure.json"

    def test_write_structure_json(self, tmp_path):
        target = tmp_path / ".the-door" / "structure.json"
        structure = _make_structure([])
        result = write_structure_json(target, structure, None)
        assert result == target
        assert target.exists()

    def test_write_versioned_structure(self, tmp_path):
        structure = _make_structure([])
        result = write_versioned_structure(tmp_path, "test-version-id", structure, None)
        assert result == tmp_path / ".the-door" / "structures" / "test-version-id.json.gz"
        assert result.exists()

    def test_build_structure_dict_with_db_freshness(self):
        from the_door.models import DatabaseFreshness, ScanResult
        freshness = DatabaseFreshness(timestamp="2026-01-01T00:00:00Z", mode="online")
        scan = ScanResult(db_freshness=freshness)
        structure = _make_structure([])
        data = build_structure_dict(structure, scan)
        assert "vulnerability_db_freshness" in data
        assert data["vulnerability_db_freshness"]["mode"] == "online"
