# Task 06: Dogfood Histogram + N Tuning + CHANGELOG

**Files:**
- Create: `scripts/dogfood_edge_projection_report.py`
- Modify: `the_door/src/the_door/core/extraction/edge_builder.py` (`FANOUT_THRESHOLD` value if dogfood says so)
- Modify: `CHANGELOG.md`
- Modify: `README.md` + `README.zh-TW.md` (core capabilities table row)

**Goal:** 跑 fanout histogram 在主 repo + v105 test target，定 `FANOUT_THRESHOLD` 最終值；記入 CHANGELOG；雙語 README core capabilities 表加一列。

**Depends on:** Task 01–05 全部完成（dogfood 要看整個流程實際輸出）。

---

## ASTExtractor return shape 重要說明（必讀）

`ASTExtractor.extract(codebase_path)` 回傳 `ExtractionResult`，欄位**只有** `files / nodes / edges / errors / warnings`（見 `models.py:65-72`）。**沒有 `trees`、沒有 `source_bytes`** — 那些是 `extract()` 內部的 local 變數，外部拿不到。

但這對 dogfood 來說沒問題：`extract()` 內部已經跑過 `build_edges()`，`result.edges` 已經帶 resolution。Histogram 重算 `name → count` map 也只需要 `result.nodes`。**完全不需要 trees**。

---

## Phase A — Histogram script & tuning

- [ ] **Step 1: Create the dogfood script**

Create `scripts/dogfood_edge_projection_report.py`:

```python
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
```

- [ ] **Step 2: Run dogfood on the main repo**

Run:
```
cd C:/Users/Ric/Desktop/the_door && python scripts/dogfood_edge_projection_report.py the_door/src/the_door
```

Record output. Note especially p75 / p90、`name_match_ambiguous` 百分比、drop rate、callers-with-hints。

- [ ] **Step 3: Run dogfood on the v105 test target**

Run:
```
cd C:/Users/Ric/Desktop/the_door && python scripts/dogfood_edge_projection_report.py "C:/Users/Ric/Desktop/test-targets/the-door-v105"
```

Record same metrics.

- [ ] **Step 4: Decide final `FANOUT_THRESHOLD`**

Decision rule:
- 兩 repo p75 ≤ 3 且 p90 ≤ 5 → 維持 `FANOUT_THRESHOLD = 3`
- p75 落在 4–5 或 p90 > 8 → 提升到 4 或 5（取兩 repo p90 較低者）
- 兩 repo p90 ≤ 3 → 考慮降到 2（罕見，僅在 drop rate 過低時）

如有調整，edit `the_door/src/the_door/core/extraction/edge_builder.py`：

```python
# Tuned by dogfood histogram on the_door + v105 (2026-05-29):
# main repo p75=X p90=Y, v105 p75=A p90=B → threshold N gives Z% drop.
FANOUT_THRESHOLD = <final value>
```

並同步更新 `tests/integration/test_edge_fanout_threshold.py` 內 `test_threshold_default_is_three` 的 assertion 數值，與相關 fixture 的候選數使其仍能驗證 low → name_match、high → ambiguous 的兩段語意。

- [ ] **Step 5: Re-run full suite**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected: 全 GREEN。

---

## Phase B — Docs

- [ ] **Step 6: Update CHANGELOG**

Edit `CHANGELOG.md`. Add a new entry at the top:

```markdown
## v1.4.6 — 2026-05-29

### Edge noise projection (post-v1.4.5 增量)

- **`Edge.resolution` 加 `name_match_ambiguous` 枚舉值**：高 fanout（候選 > N）的裸名匹配標為 ambiguous
- **新增 `core/llm/edge_projection.py` 純函式投影層**：drop ambiguous + 把 `skipped_dynamic` 邊聚合成 `aggregate_call_hints`
- **BatchReader detail mode payload 加 `aggregate_call_hints` 欄位**；minimal mode 不變
- **L1 prompt 教 LLM 看 hint 但不可寫成依賴**

#### Dogfood §7.2 驗收

| Target | 投影前邊數 | 投影後邊數 | drop% | callers with hints |
|---|---|---|---|---|
| `the_door/src/the_door` | XXX | XXX | XX% | XXX |
| `test-targets/the-door-v105` | XXX | XXX | XX% | XXX |

`FANOUT_THRESHOLD = N`（由 dogfood histogram p75/p90 分佈決定）

#### 向後相容

- 既有 snapshot 反序列化不報錯
- source-level guard 釘住 `core/diff/` 不引用 `edge.resolution`，新枚舉值不會造成 diff 假 churn
- viewer 不需要改動
```

把表格中的 XXX 填入 Step 2–3 的實測數據。

- [ ] **Step 7: Update README.md**

Edit `README.md`. 在 core capabilities 表（scope-aware edge resolution v1.4.5 那列）後新增一列：

```markdown
| **Edge noise projection** | LLM 收到的邊已過濾高 fanout 噪音，動態 dispatch 邊聚合成 caller 級 hint；snapshot 與 viewer 仍保留完整事實。 |
```

- [ ] **Step 8: Update README.zh-TW.md**

Edit `README.zh-TW.md`，鏡像同一列（中文）：

```markdown
| **邊噪音投影** | LLM 收到的關聯邊已過濾高候選量噪音、動態 dispatch 邊聚合成 caller 散文 hint；snapshot 與 viewer 仍保留完整事實。 |
```

- [ ] **Step 9: Final full-suite run**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected: 全 GREEN。

- [ ] **Step 10: Commit**

```bash
git add scripts/dogfood_edge_projection_report.py \
        the_door/src/the_door/core/extraction/edge_builder.py \
        the_door/tests/integration/test_edge_fanout_threshold.py \
        CHANGELOG.md README.md README.zh-TW.md
git commit -m "docs(v1.4.6): edge noise projection + dogfood report + CHANGELOG"
```

---

## Verification checklist

- [ ] `scripts/dogfood_edge_projection_report.py` 兩 target 都跑得起來
- [ ] CHANGELOG XXX 全部換成實測數據
- [ ] `FANOUT_THRESHOLD` rationale comment 含實測 p75/p90 值
- [ ] README + README.zh-TW core capabilities 表都更新
- [ ] 全測試 GREEN
- [ ] `edge_projection.py` 100% coverage
- [ ] `edge_builder.py` 100% coverage 維持
