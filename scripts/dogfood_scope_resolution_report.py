"""Run scope-aware EdgeBuilder against the_door itself and report resolution distribution.

Usage:
  python scripts/dogfood_scope_resolution_report.py [target_path]

Acceptance (spec §7.2):
  - scope_rule + import_alias >= 50%
  - name_match <= 40%
  - skipped_dynamic: language-dependent (Ruby/Python may be higher)
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor


def main(target: str = ".") -> int:
    target_path = Path(target).resolve()
    print(f"Analyzing: {target_path}")
    extractor = ASTExtractor()
    result = extractor.extract(str(target_path))

    if not result.edges:
        print("ERROR: no edges produced.")
        return 1

    counts = Counter(e.resolution for e in result.edges)
    total = sum(counts.values())
    high = counts.get("scope_rule", 0) + counts.get("import_alias", 0)
    name_match = counts.get("name_match", 0)
    dynamic = counts.get("skipped_dynamic", 0)

    print(f"\nTotal edges: {total}")
    print(f"  scope_rule:      {counts.get('scope_rule', 0):>6} ({counts.get('scope_rule', 0)/total*100:5.1f}%)")
    print(f"  import_alias:    {counts.get('import_alias', 0):>6} ({counts.get('import_alias', 0)/total*100:5.1f}%)")
    print(f"  name_match:      {name_match:>6} ({name_match/total*100:5.1f}%)")
    print(f"  skipped_dynamic: {dynamic:>6} ({dynamic/total*100:5.1f}%)")
    print(f"\nHigh confidence (scope_rule + import_alias): {high/total*100:5.1f}%  (target: >= 50%)")
    print(f"Low confidence  (name_match):                 {name_match/total*100:5.1f}%  (target: <= 40%)")

    ok = (high / total) >= 0.50 and (name_match / total) <= 0.40
    print(f"\nResult: {'PASS' if ok else 'FAIL (does not meet §7.2 acceptance thresholds)'}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
