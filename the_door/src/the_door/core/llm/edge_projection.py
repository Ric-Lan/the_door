"""Edge projection layer for L1 prompt input.

Filters and aggregates raw graph edges into a form suitable for LLM
consumption: high-confidence and bounded-fanout edges pass through;
ambiguous and dynamic-dispatch edges are folded into a per-caller
"aggregate hint" dict the prompt can describe as imprecise call hints.

This module is pure: no I/O, no logging, no global state, no flags.
Same input always produces same output. Tests live in
tests/unit/core/llm/test_edge_projection.py and
tests/property/test_edge_projection_properties.py.
"""
from __future__ import annotations

_AGGREGATED_RESOLUTIONS = frozenset({"name_match_ambiguous", "skipped_dynamic"})


def project_edges_for_prompt(
    edges: list[dict],
) -> tuple[list[dict], dict[str, list[str]]]:
    """Project edges for prompt consumption.

    See module docstring + plan task 02 for contract.
    """
    kept: list[dict] = []
    hint_sets: dict[str, set[str]] = {}

    for edge in edges:
        if edge.get("resolution") in _AGGREGATED_RESOLUTIONS:
            caller = edge["from"]
            hint_sets.setdefault(caller, set()).add(
                _method_name_from_to(edge["to"])
            )
        else:
            kept.append(edge)

    hints = {caller: sorted(names) for caller, names in hint_sets.items()}
    return kept, hints


def _method_name_from_to(to_node: str) -> str:
    """Extract bare method name from a node_id like 'Class.method'."""
    if "." in to_node:
        return to_node.rsplit(".", 1)[-1]
    return to_node
