"""Reference patterns for hypothesis property tests.

Downstream task files identify specific production functions (compute_affected_features,
NextActionSuggester, _disambiguate_node_ids, etc.) that should be property-tested.
Each task copies the pattern below and replaces the example with the production
function's invariant.

Do NOT import this file from production code — it is a documentation fixture only.
"""
from __future__ import annotations
from hypothesis import given, strategies as st


# Pattern A — invariant over input shape:
# "for any valid input, the output satisfies P(output)"
@given(st.lists(st.integers(), max_size=20))
def example_reverse_is_involutive(xs):
    """Reversing twice yields the original list — invariant, not a single example."""
    assert list(reversed(list(reversed(xs)))) == xs


# Pattern B — invariant over input/output relationship:
# "for any input X partitioned into (A, B), |A| + |B| == |X|"
@given(st.lists(st.integers(), min_size=0, max_size=20))
def example_partition_total_preserved(xs):
    evens = [x for x in xs if x % 2 == 0]
    odds = [x for x in xs if x % 2 == 1]
    assert len(evens) + len(odds) == len(xs)


# Pattern C — invariant over composition:
# "f(g(x)) == g(f(x)) for commuting f, g, or f(g(x)) == identity for inverses"
# (Use when proving a serializer + deserializer round-trip.)
@given(st.dictionaries(st.text(min_size=1, max_size=10), st.integers(), max_size=10))
def example_json_roundtrip(d):
    import json
    assert json.loads(json.dumps(d)) == d
