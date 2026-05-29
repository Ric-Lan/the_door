"""Edge.resolution accepts the new name_match_ambiguous value."""
from the_door.models import Edge


def test_edge_accepts_name_match_ambiguous_resolution():
    """name_match_ambiguous is a valid resolution value."""
    edge = Edge(
        from_node="a",
        to_node="b",
        type="calls",
        resolution="name_match_ambiguous",
    )
    assert edge.resolution == "name_match_ambiguous"


def test_edge_resolution_legacy_default_unchanged():
    """Default resolution remains 'name_match' for backward compat."""
    edge = Edge(from_node="a", to_node="b", type="calls")
    assert edge.resolution == "name_match"


def test_edge_all_known_resolutions_accepted():
    """All five known resolution values construct without error."""
    for res in ("scope_rule", "import_alias", "name_match",
                "name_match_ambiguous", "skipped_dynamic"):
        edge = Edge(from_node="a", to_node="b", type="calls", resolution=res)
        assert edge.resolution == res
