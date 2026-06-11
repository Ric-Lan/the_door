"""Pure path/filename classification of a node into operational vs non-operational.

Cut 1 of the operational-classification campaign. Given a ``node_id`` of the
form ``<relpath>::<name>``, decide whether it belongs to the project's actual
running surface (``operational``) or is test/fixture/script/prototype
scaffolding (non-operational). Zero-graph and deterministic — only the path and
filename are inspected.

**Default-safe**: anything not matching a known non-operational pattern is
``operational``. The classifier therefore only ever produces false negatives (a
test in an unconventional location stays listed), never false positives (it
never hides a real operational node). This mirrors the fact-finder rule: when
unsure, don't hide.

Consumed by the ``analyze_changes`` MCP projection to summarize the
``unmapped_nodes`` bucket instead of dumping every scaffolding node_id verbatim.
"""
from __future__ import annotations

CAT_OPERATIONAL = "operational"
CAT_TEST = "test"
CAT_FIXTURE = "fixture"
CAT_SCRIPT = "script"
CAT_PROTOTYPE = "prototype"

NON_OPERATIONAL = frozenset({CAT_TEST, CAT_FIXTURE, CAT_SCRIPT, CAT_PROTOTYPE})


def classify_node(node_id: str) -> str:
    """Classify ``node_id`` into one of the category constants.

    First-match wins, in the order below. Overlapping paths (e.g.
    ``tests/fixtures/``) resolve to the first matching rule (``test``) — both are
    non-operational so the summarized ``total`` is unaffected, only the bucket
    label differs.
    """
    path = node_id.split("::", 1)[0].replace("\\", "/").lower()
    filename = path.rsplit("/", 1)[-1]

    # filename signals
    if (
        filename == "conftest.py"
        or filename.startswith("test_")
        or filename.endswith("_test.py")
    ):
        return CAT_TEST

    # path signals (first-match wins)
    if "/tests/" in path or path.startswith("tests/"):
        return CAT_TEST
    if "/fixtures/" in path:
        return CAT_FIXTURE
    if "/scripts/" in path or path.startswith("scripts/"):
        return CAT_SCRIPT
    if "/prototype" in path:
        return CAT_PROTOTYPE

    return CAT_OPERATIONAL


def is_operational(node_id: str) -> bool:
    """``True`` iff ``classify_node(node_id)`` is the operational category."""
    return classify_node(node_id) == CAT_OPERATIONAL


def summarize_unmapped(node_ids: list[str]) -> dict:
    """Split a node_id list into listed operational ids + a counted summary of
    non-operational ones.

    Operational nodes are listed verbatim (an agent may need to see them).
    Non-operational nodes (test/fixture/script/prototype) are *summarized* — only
    per-category counts and a total, never the bare ids — to keep diagnostic
    scaffolding from drowning the diff payload (handoff #2).

    Returns::

        {"operational": [<id>...],
         "non_operational": {"by_category": {<cat>: <count>}, "total": <int>}}
    """
    operational: list[str] = []
    by_category: dict[str, int] = {}
    for node_id in node_ids:
        category = classify_node(node_id)
        if category == CAT_OPERATIONAL:
            operational.append(node_id)
        else:
            by_category[category] = by_category.get(category, 0) + 1
    return {
        "operational": operational,
        "non_operational": {
            "by_category": by_category,
            "total": sum(by_category.values()),
        },
    }
