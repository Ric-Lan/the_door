"""Edge projection layer for L1 prompt input (membrane residue shape).

Filters and aggregates raw graph edges into a form suitable for LLM
consumption: high-confidence and bounded-fanout edges pass through;
off-grid residue (dynamic dispatch) and low-confidence ambiguous matches
are split into separate coordinates (membrane A-side, §8.13/§8.14):
  - skipped_dynamic → NoisePosition(indeterminate, real-count, proportion)
  - name_match_ambiguous → counted bucket (confidence Signal deferred to S4)

This module is pure: no I/O, no logging, no global state, no flags.
Same input always produces same output. Tests live in
tests/unit/core/llm/test_edge_projection.py and
tests/property/test_edge_projection_properties.py.
"""
from __future__ import annotations

from collections import Counter

from the_door.core.llm.edge_membrane import indeterminate_residue_element, is_residue
from the_door.core.reading.confidence_membrane import confidence_element

_AMBIGUOUS = "name_match_ambiguous"   # 格內低信心（confidence 軸＝S4）


def project_edges_for_prompt(
    edges: list[dict],
) -> tuple[list[dict], dict]:
    """投影 edges 供 prompt 消費（膜化殘餘）。

    回傳 (kept, residue)：
      kept＝格內 resolution 邊（不變）。
      residue＝座標分明的格外/低信心殘餘（修 F5：基數保留、不併桶）：
        {
          "indeterminate": [<NoisePosition element .to_json()>, ...],  # skipped_dynamic
          "low_confidence_ambiguous": [                                # name_match_ambiguous（S4 升 confidence Signal）
            {caller, methods, cardinality, confidence: <Signal element .to_json()>}, ...
          ],
        }
    """
    kept: list[dict] = []
    indeterminate_counts: dict[str, Counter] = {}      # caller -> Counter(method)
    ambiguous_counts: dict[str, Counter] = {}          # caller -> Counter(method)
    total = len(edges)

    for edge in edges:
        res = edge.get("resolution")
        if is_residue(res):                            # skipped_dynamic（格外殘餘）
            caller = edge["from"]
            indeterminate_counts.setdefault(caller, Counter())[_method_name_from_to(edge["to"])] += 1
        elif res == _AMBIGUOUS:                         # 格內低信心
            caller = edge["from"]
            ambiguous_counts.setdefault(caller, Counter())[_method_name_from_to(edge["to"])] += 1
        else:
            kept.append(edge)

    residue = {
        "indeterminate": [
            indeterminate_residue_element(caller, dict(counts), total).to_json()
            for caller, counts in sorted(indeterminate_counts.items())
        ],
        "low_confidence_ambiguous": [
            {
                "caller": caller,
                "methods": dict(sorted(counts.items())),          # 基數保留（method→count）
                "cardinality": sum(counts.values()),              # 此 caller 低信心邊總數
                "confidence": confidence_element("low").to_json(),  # value="low"（∈contrasts、I4 合法）＋position=signal
            }
            for caller, counts in sorted(ambiguous_counts.items())
        ],
    }
    return kept, residue


def _method_name_from_to(to_node: str) -> str:
    """Extract bare method name from a node_id like 'Class.method'."""
    if "." in to_node:
        return to_node.rsplit(".", 1)[-1]
    return to_node
