"""BatchReader detail mode applies edge_projection at payload boundary."""
from the_door.core.reading.batch_reader import BatchReader
from the_door.models import ASTNode, Edge, StructureJSON


class _StubProvider:
    """Minimal LLM provider stub — _build_payload doesn't use it."""
    pass


def _node(node_id: str, name: str, file: str = "x.py") -> ASTNode:
    return ASTNode(node_id=node_id, type="function", name=name, file=file,
                   language="python")


def _make_structure(nodes: list[ASTNode], edges: list[Edge]) -> StructureJSON:
    return StructureJSON(nodes=list(nodes), edges=list(edges))


def _reader(structure: StructureJSON, mode: str = "detail") -> BatchReader:
    return BatchReader(_StubProvider(), structure, context_mode=mode)


def test_detail_payload_includes_aggregate_call_hints_key():
    """Even when no edges trigger aggregation, the key exists as empty dict."""
    nodes = [_node("caller", "caller"), _node("target", "target")]
    edges = [Edge(from_node="caller", to_node="target",
                  type="calls", resolution="scope_rule")]
    payload = _reader(_make_structure(nodes, edges))._build_payload(
        ["caller", "target"], batch_num=0
    )
    assert "aggregate_call_hints" in payload
    assert payload["aggregate_call_hints"] == {}
    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["resolution"] == "scope_rule"


def test_ambiguous_edges_dropped_and_hint_populated():
    nodes = [_node("caller", "caller")] + [
        _node(f"M{i}.write", "write") for i in range(4)
    ]
    edges = [
        Edge(from_node="caller", to_node=f"M{i}.write",
             type="calls", resolution="name_match_ambiguous")
        for i in range(4)
    ]
    node_ids = ["caller"] + [f"M{i}.write" for i in range(4)]
    payload = _reader(_make_structure(nodes, edges))._build_payload(
        node_ids, batch_num=0
    )
    # No ambiguous edges leaked through
    assert all(e["resolution"] != "name_match_ambiguous"
               for e in payload["edges"])
    # Caller has a hint
    assert payload["aggregate_call_hints"] == {"caller": ["write"]}


def test_dynamic_edges_aggregated_into_hints():
    nodes = [_node("caller", "caller"), _node("Bus.send", "send")]
    edges = [Edge(from_node="caller", to_node="Bus.send",
                  type="calls", resolution="skipped_dynamic")]
    payload = _reader(_make_structure(nodes, edges))._build_payload(
        ["caller", "Bus.send"], batch_num=0
    )
    assert payload["edges"] == []
    assert payload["aggregate_call_hints"] == {"caller": ["send"]}


def test_minimal_mode_has_no_aggregate_call_hints_key():
    """minimal mode payload must NOT contain aggregate_call_hints."""
    nodes = [_node("a", "a"), _node("b", "b")]
    edges = [Edge(from_node="a", to_node="b",
                  type="calls", resolution="name_match_ambiguous")]
    payload = _reader(_make_structure(nodes, edges), mode="minimal")._build_payload(
        ["a", "b"], batch_num=0
    )
    assert "aggregate_call_hints" not in payload
    assert payload == {"batch": 0, "context_mode": "minimal",
                       "nodes": ["a", "b"]}


def test_batch_local_filter_applied_before_projection():
    """Edges to nodes outside the batch are dropped first; projection
    only sees in-batch edges, so its hints only reference in-batch callers."""
    nodes = [_node("caller", "caller"),
             _node("In.x", "x"),
             _node("Out.y", "y")]
    edges = [
        Edge(from_node="caller", to_node="In.x",
             type="calls", resolution="name_match_ambiguous"),
        Edge(from_node="caller", to_node="Out.y",
             type="calls", resolution="name_match_ambiguous"),
    ]
    # Batch excludes "Out.y"
    payload = _reader(_make_structure(nodes, edges))._build_payload(
        ["caller", "In.x"], batch_num=0
    )
    # Only the in-batch edge fed projection → only 'x' in hint, not 'y'
    assert payload["aggregate_call_hints"] == {"caller": ["x"]}
