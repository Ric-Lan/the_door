"""Dogfood report for edge_projection: fanout histogram + projection effect.

Runs ASTExtractor on a target codebase and reports:
  1. Histogram of bare-name candidate_count (drives FANOUT_THRESHOLD tuning)
  2. Edge resolution distribution
  3. Pre-/post-projection edge count diff (validates spec §7.2 Step 2)
  4. Per-caller aggregate_call_hints coverage

Usage:
    python scripts/dogfood_edge_projection_report.py <codebase_path>
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.extraction.edge_builder import FANOUT_THRESHOLD
from the_door.core.llm.edge_projection import project_edges_for_prompt


def main(path: str) -> int:
    root = Path(path).resolve()
    if not root.exists():
        print(f"ERROR: {root} does not exist")
        return 1

    extractor = ASTExtractor()
    result = extractor.extract(str(root))
    print(f"\n== ASTExtractor result ({root}) ==")
    print(f"  files: {len(result.files)}  nodes: {len(result.nodes)}  "
          f"edges: {len(result.edges)}  errors: {len(result.errors)}")

    # --- Name → candidate_count histogram (derived from result.nodes) ---
    name_to_count: dict[str, int] = {}
    for n in result.nodes:
        name_to_count[n.name] = name_to_count.get(n.name, 0) + 1
    counts = Counter(name_to_count.values())
    print(f"\n== Bare-name candidate_count histogram ==")
    print(f"  total unique names: {len(name_to_count)}")
    for c, n in sorted(counts.items()):
        bar = "#" * min(n, 60)
        print(f"  count={c:>3}: {n:>5} names  {bar}")
    sorted_values = sorted(name_to_count.values())
    if sorted_values:
        m = len(sorted_values)
        print(f"  p50={sorted_values[m//2]}  "
              f"p75={sorted_values[3*m//4]}  "
              f"p90={sorted_values[9*m//10]}  "
              f"p95={sorted_values[19*m//20]}  "
              f"max={sorted_values[-1]}")

    # --- Resolution distribution (from result.edges) ---
    res_counts = Counter(e.resolution for e in result.edges)
    total = sum(res_counts.values()) or 1
    print(f"\n== Edge resolution distribution (total={total}) ==")
    for res in ("scope_rule", "import_alias", "name_match",
                "name_match_ambiguous", "skipped_dynamic"):
        c = res_counts.get(res, 0)
        print(f"  {res:<23}: {c:>5}  ({100*c/total:.1f}%)")

    # --- Projection effect ---
    edge_dicts = [{"from": e.from_node, "to": e.to_node,
                   "type": e.type, "resolution": e.resolution}
                  for e in result.edges]
    kept, hints = project_edges_for_prompt(edge_dicts)
    raw = len(edge_dicts)
    drop_pct = 100 * (raw - len(kept)) / max(raw, 1)
    print(f"\n== Projection effect ==")
    print(f"  raw edges:           {raw}")
    print(f"  kept edges:          {len(kept)}  ({drop_pct:.1f}% dropped)")
    print(f"  callers with hints:  {len(hints)}")
    print(f"  unique callers in graph: "
          f"{len({e['from'] for e in edge_dicts})}")

    print(f"\n== Current FANOUT_THRESHOLD = {FANOUT_THRESHOLD} ==")
    print("If p75/p90 suggests a different threshold, edit edge_builder.py.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/dogfood_edge_projection_report.py <path>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
