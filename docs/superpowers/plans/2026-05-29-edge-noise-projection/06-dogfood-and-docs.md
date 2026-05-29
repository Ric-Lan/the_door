# Task 06: Dogfood Histogram + N Tuning + CHANGELOG

**Files:**
- Create: `scripts/dogfood_edge_projection_report.py`
- Modify: `the_door/src/the_door/core/extraction/edge_builder.py` (`FANOUT_THRESHOLD` value if dogfood says so)
- Modify: `CHANGELOG.md`
- Modify: `README.md` + `README.zh-TW.md` (core capabilities table row)

**Goal:** 跑 fanout histogram 在主 repo + v105 test target，定 `FANOUT_THRESHOLD` 最終值；記入 CHANGELOG；雙語 README core capabilities 表加一列。

**Depends on:** Task 01–05 全部完成（dogfood 要看整個流程實際輸出）。

---

## Phase A — Histogram script & tuning

- [ ] **Step 1: Create the dogfood script**

Create `scripts/dogfood_edge_projection_report.py`:

```python
"""Dogfood report for edge_projection: fanout histogram + projection effect.

Runs EdgeBuilder on a target codebase and reports:
  1. Histogram of bare-name candidate_count (drives FANOUT_THRESHOLD tuning)
  2. Pre-/post-projection edge count diff (validates spec §7.2 Step 2)
  3. Per-caller aggregate_call_hints coverage

Usage:
    python scripts/dogfood_edge_projection_report.py <codebase_path>
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.extraction.edge_builder import EdgeBuilder, FANOUT_THRESHOLD
from the_door.core.llm.edge_projection import project_edges_for_prompt


def main(path: str) -> int:
    root = Path(path).resolve()
    if not root.exists():
        print(f"ERROR: {root} does not exist")
        return 1

    extractor = ASTExtractor()
    extraction = extractor.extract(str(root))
    builder = EdgeBuilder(list(extraction.nodes))
    edges = builder.build_edges(extraction.trees, extraction.source_bytes)

    # --- Histogram ---
    name_to_count = {name: len(ids) for name, ids in builder._name_to_ids.items()}
    counts = Counter(name_to_count.values())
    print(f"\n== Bare-name candidate_count histogram ({root}) ==")
    print(f"  total unique names: {len(name_to_count)}")
    sorted_buckets = sorted(counts.items())
    for c, n in sorted_buckets:
        bar = "#" * min(n, 60)
        print(f"  count={c:>3}: {n:>5} names  {bar}")
    sorted_values = sorted(name_to_count.values())
    if sorted_values:
        n = len(sorted_values)
        print(f"  p50={sorted_values[n//2]}  "
              f"p75={sorted_values[3*n//4]}  "
              f"p90={sorted_values[9*n//10]}  "
              f"p95={sorted_values[19*n//20]}  "
              f"max={sorted_values[-1]}")

    # --- Resolution distribution ---
    res_counts = Counter(e.resolution for e in edges)
    total = sum(res_counts.values()) or 1
    print(f"\n== Edge resolution distribution (total={total}) ==")
    for res in ("scope_rule", "import_alias", "name_match",
                "name_match_ambiguous", "skipped_dynamic"):
        c = res_counts.get(res, 0)
        print(f"  {res:<23}: {c:>5}  ({100*c/total:.1f}%)")

    # --- Projection effect ---
    edge_dicts = [{"from": e.from_node, "to": e.to_node,
                   "type": e.type, "resolution": e.resolution}
                  for e in edges]
    kept, hints = project_edges_for_prompt(edge_dicts)
    print(f"\n== Projection effect ==")
    print(f"  raw edges:           {len(edge_dicts)}")
    print(f"  kept edges:          {len(kept)}  "
          f"({100*(len(edge_dicts)-len(kept))/max(len(edge_dicts),1):.1f}% dropped)")
    print(f"  callers with hints:  {len(hints)}")
    print(f"  unique callers in graph: "
          f"{len({e['from'] for e in edge_dicts})}")

    print(f"\n== Current FANOUT_THRESHOLD = {FANOUT_THRESHOLD} ==")
    print("If p75 or p90 suggests a different threshold, edit edge_builder.py.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/dogfood_edge_projection_report.py <path>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
```

- [ ] **Step 2: Run dogfood on the main repo**

Run:
```
cd C:/Users/Ric/Desktop/the_door && python scripts/dogfood_edge_projection_report.py the_door/src/the_door
```

Record the output in a scratch buffer. Note specifically:
- p75 and p90 of candidate_count distribution
- `name_match_ambiguous` percentage of total edges
- Drop rate (`X% dropped`)
- Caller-with-hints coverage

- [ ] **Step 3: Run dogfood on the v105 test target**

Run:
```
cd C:/Users/Ric/Desktop/the_door && python scripts/dogfood_edge_projection_report.py "C:/Users/Ric/Desktop/test-targets/the-door-v105"
```

Record same metrics.

- [ ] **Step 4: Decide final `FANOUT_THRESHOLD`**

Decision rule:
- If both repos' p75 ≤ 3 and p90 ≤ 5 → keep `FANOUT_THRESHOLD = 3`
- If p75 between 4-5 or p90 > 8 → raise to 4 or 5 (use lower of the two repos' p90)
- If both p90 ≤ 3 → consider lowering to 2 (rare; only if drop rate is too low)

Edit `the_door/src/the_door/core/extraction/edge_builder.py` `FANOUT_THRESHOLD` if needed. Update comment with the dogfood-determined rationale:

```python
# Tuned by dogfood histogram on the_door + v105 (2026-05-29):
# main repo p75=X p90=Y, v105 p75=A p90=B → threshold N gives Z% drop.
FANOUT_THRESHOLD = <final value>
```

- [ ] **Step 5: Re-run full suite after tuning**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected: all GREEN. If `test_edge_fanout_threshold.py::test_low_fanout_keeps_name_match` fails because it asserts `FANOUT_THRESHOLD == 3`, update the assertion to match the new value AND update the fixture candidate counts in the related tests so that the test still validates the threshold semantics (low → name_match, high → ambiguous).

---

## Phase B — Docs

- [ ] **Step 6: Update CHANGELOG**

Edit `CHANGELOG.md`. Add a new entry at the top:

```markdown
## v1.4.6 — 2026-05-29

### Edge noise projection (post-v1.4.5 增量)

- **`Edge.resolution` 加 `name_match_ambiguous` 枚舉值**：高 fanout（候選 > N）的裸名匹配標為 ambiguous，與一般 `name_match` 區分
- **新增 `core/llm/edge_projection.py` 純函式投影層**：drop ambiguous + 把 `skipped_dynamic` 邊聚合成 `aggregate_call_hints`
- **BatchReader detail mode payload 加 `aggregate_call_hints` 欄位**：minimal mode 不變動
- **L1 prompt 教 LLM 看 hint 但不可寫成依賴**

#### Dogfood §7.2 驗收

| Target | 投影前邊數 | 投影後邊數 | drop% | callers with hints |
|---|---|---|---|---|
| `the_door/src/the_door` | XXX | XXX | XX% | XXX |
| `test-targets/the-door-v105` | XXX | XXX | XX% | XXX |

`FANOUT_THRESHOLD = N`（由 dogfood histogram p75/p90 分佈決定）

#### 向後相容

- 既有 snapshot 反序列化不報錯
- `core/diff/` 從不比對 `edge.resolution`，新枚舉值不會造成 diff 假 churn（有 regression test 釘住）
- viewer 不需要改動
```

把表格中的 XXX 填入 Step 2–3 的實測數據。

- [ ] **Step 7: Update README.md core capabilities row**

Edit `README.md`. Find the core capabilities table (look for the row about scope-aware edge resolution from v1.4.5) and add a new row after it:

```markdown
| **Edge noise projection** | LLM 收到的邊已過濾高 fanout 噪音，動態 dispatch 邊聚合成 caller 級 hint；snapshot 與 viewer 仍保留完整事實。 |
```

- [ ] **Step 8: Update README.zh-TW.md core capabilities row**

Edit `README.zh-TW.md` (mirror the structure). Add the same row in Chinese:

```markdown
| **邊噪音投影** | LLM 收到的關聯邊已過濾高候選量噪音、動態 dispatch 邊聚合成 caller 散文 hint；snapshot 與 viewer 仍保留完整事實。 |
```

- [ ] **Step 9: Final full-suite run**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected: all GREEN.

- [ ] **Step 10: Commit**

```bash
git add scripts/dogfood_edge_projection_report.py \
        the_door/src/the_door/core/extraction/edge_builder.py \
        CHANGELOG.md README.md README.zh-TW.md
git commit -m "docs(v1.4.6): edge noise projection + dogfood report + CHANGELOG"
```

---

## Verification checklist (before declaring task complete)

- [ ] `scripts/dogfood_edge_projection_report.py` runs on both targets without error
- [ ] CHANGELOG XXX placeholders all replaced with real numbers
- [ ] `FANOUT_THRESHOLD` rationale comment names actual p75/p90 values
- [ ] README + README.zh-TW core capabilities table both updated
- [ ] Full test suite GREEN
- [ ] `edge_projection.py` 100% coverage
- [ ] `edge_builder.py` 100% coverage maintained
