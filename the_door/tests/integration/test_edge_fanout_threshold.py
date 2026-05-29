"""EdgeBuilder marks high-fanout name_match edges as name_match_ambiguous.

These tests probe `_resolve()` directly by hand-injecting the lookup
state that `build_edges()` would normally populate. This isolates the
threshold logic from tree-sitter parsing.
"""
from the_door.core.extraction.edge_builder import (
    EdgeBuilder, FANOUT_THRESHOLD, ScopeContext,
)
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS
from the_door.models import ASTNode


def _node(node_id: str, name: str, file: str = "x.py",
          ntype: str = "function") -> ASTNode:
    return ASTNode(node_id=node_id, type=ntype, name=name, file=file,
                   language="python")


def _builder_with(nodes: list[ASTNode]) -> EdgeBuilder:
    """Construct an EdgeBuilder and hand-populate its lookup state.

    Mirrors what `build_edges()` does at lines 69-72.
    """
    builder = EdgeBuilder()
    builder._name_to_ids = {}
    builder._node_map = {}
    for n in nodes:
        builder._name_to_ids.setdefault(n.name, []).append(n.node_id)
        builder._node_map[n.node_id] = n
    return builder


def _ctx(current_file: str = "external.py") -> ScopeContext:
    """Context that forces Step 4 fallback (scope_rule won't apply)."""
    return ScopeContext(
        current_file=current_file,
        import_aliases={},
        caller_class=None,
    )


def test_threshold_default_is_three():
    """Anchor test: dogfood (Task 06) may tune this — keep test in sync."""
    assert FANOUT_THRESHOLD == 3


def test_low_fanout_keeps_name_match():
    """When candidates ≤ threshold, resolution stays name_match."""
    nodes = [
        _node("a.py::shared", "shared", "a.py"),
        _node("b.py::shared", "shared", "b.py"),
    ]  # 2 candidates < threshold 3
    builder = _builder_with(nodes)
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    resolved = builder._resolve("shared", _ctx(), rules)
    assert len(resolved) == 2
    assert all(res == "name_match" for _nid, res in resolved)


def test_high_fanout_marks_ambiguous():
    """When candidates > threshold, resolution becomes name_match_ambiguous."""
    nodes = [_node(f"f{i}.py::shared", "shared", f"f{i}.py")
             for i in range(4)]  # 4 > threshold 3
    builder = _builder_with(nodes)
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    resolved = builder._resolve("shared", _ctx(), rules)
    assert len(resolved) == 4
    assert all(res == "name_match_ambiguous" for _nid, res in resolved)


def test_dynamic_dispatch_unaffected_by_threshold():
    """skipped_dynamic does NOT receive ambiguous — projection handles it."""
    nodes = [_node(f"f{i}.py::send", "send", f"f{i}.py") for i in range(10)]
    builder = _builder_with(nodes)
    # Ruby's scope_rules has method_resolution == "dynamic_dispatch"
    rules = LANGUAGE_CONFIGS["ruby"].scope_rules
    resolved = builder._resolve("send", _ctx("caller.rb"), rules)
    assert all(res == "skipped_dynamic" for _nid, res in resolved)


def test_extends_path_also_gets_ambiguous():
    """_detect_extends calls _resolve too → threshold applies to extends edges."""
    nodes = [_node(f"f{i}.py::Base", "Base", f"f{i}.py", ntype="class")
             for i in range(4)]
    builder = _builder_with(nodes)
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    ctx = ScopeContext(current_file="child.py", import_aliases={},
                       caller_class="Child", caller_name="Child")
    resolved = builder._resolve("Base", ctx, rules)
    assert all(res == "name_match_ambiguous" for _nid, res in resolved)


def test_no_candidates_returns_empty():
    """Step 4 with zero candidates returns empty list (no edge)."""
    builder = _builder_with([])
    rules = LANGUAGE_CONFIGS["python"].scope_rules
    assert builder._resolve("nonexistent_name", _ctx(), rules) == []


def test_no_rules_path_also_escalates():
    """rules=None early branch (line ~386) also escalates on high fanout."""
    nodes = [_node(f"f{i}.py::shared", "shared", f"f{i}.py") for i in range(4)]
    builder = _builder_with(nodes)
    resolved = builder._resolve("shared", _ctx(), rules=None)
    assert all(res == "name_match_ambiguous" for _nid, res in resolved)


def test_no_rules_no_candidates_returns_empty():
    """rules=None early branch with zero candidates returns empty list."""
    builder = _builder_with([])
    resolved = builder._resolve("missing", _ctx(), rules=None)
    assert resolved == []
