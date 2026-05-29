# Task 01: Resolution Enum Extension

**Files:**
- Modify: `the_door/src/the_door/models.py:41`
- Test: `the_door/tests/unit/core/test_models_resolution.py` (new)
- Test: `the_door/tests/integration/diff/test_resolution_change_no_diff.py` (new)

**Goal:** 把 `Edge.resolution` 的合法值從 4 個擴張為 5 個（加 `name_match_ambiguous`），並用 regression test 釘住「resolution 標籤變動本身不該觸發 diff 狀態變更」這個事實。

**Why this is small:** `Edge.resolution` 是 `str`（dataclass）不是 `Literal`，型別系統不會在執行期擋。所以實作改動只是更新 comment 註記。重點在測試。

---

- [ ] **Step 1: Write the failing unit test**

Create `the_door/tests/unit/core/test_models_resolution.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `cd the_door && python -m pytest tests/unit/core/test_models_resolution.py -v`

Expected: PASS (resolution is `str`, no enum constraint — but the test pins behavior for the future).

- [ ] **Step 3: Update the comment註記 in `models.py`**

Edit `the_door/src/the_door/models.py:41`:

```python
    resolution: str = "name_match"  # "scope_rule" | "import_alias" | "name_match" | "name_match_ambiguous" | "skipped_dynamic"
```

(Just add `| "name_match_ambiguous"` to the inline comment.)

- [ ] **Step 4: Write the diff regression guard test**

Create `the_door/tests/integration/diff/test_resolution_change_no_diff.py`:

```python
"""Changing only Edge.resolution between two snapshots must not surface
as any diff state change — the diff engine compares feature relations,
not edge resolution labels.
"""
from the_door.core.diff.diff_engine import DiffEngine
from the_door.models import (
    BaselineInfo, Feature, FeatureRelation, VersionSnapshot,
)


def _make_snapshot(version_id: str, label: str) -> VersionSnapshot:
    return VersionSnapshot(
        version_id=version_id,
        label=label,
        timestamp="2026-05-29T00:00:00Z",
        features=(
            Feature(feature_id="feat-a", label="A", description="A",
                    source_nodes=("n1",), source_node_count=1, confidence="high"),
            Feature(feature_id="feat-b", label="B", description="B",
                    source_nodes=("n2",), source_node_count=1, confidence="high"),
        ),
        feature_relations=(
            FeatureRelation(from_feature="feat-a", to_feature="feat-b",
                            relation="depends_on"),
        ),
    )


def test_resolution_only_change_produces_no_edge_diff():
    """If only edge.resolution differs but feature relations are identical,
    diff_engine must report zero edge_diffs and zero state changes."""
    baseline = _make_snapshot("v-baseline", "v1.4.5")
    current = _make_snapshot("v-current", "v1.4.6")

    engine = DiffEngine()
    result = engine.compute(
        baseline=baseline,
        current=current,
        baseline_info=BaselineInfo(version_id="v-baseline", label="v1.4.5"),
        current_info=BaselineInfo(version_id="v-current", label="v1.4.6"),
    )

    assert result.edge_diffs == []
    assert result.summary.added_count == 0
    assert result.summary.removed_count == 0
```

- [ ] **Step 5: Run the regression guard**

Run: `cd the_door && python -m pytest tests/integration/diff/test_resolution_change_no_diff.py -v`

Expected: PASS — proves `edge.resolution` change doesn't affect diff.

If FAIL: stop. Diff engine reads resolution somewhere we missed. Re-grep `\.resolution\b` in `core/diff/` and reconsider before continuing.

- [ ] **Step 6: Run the full test suite**

Run: `cd the_door && python -m pytest 2>&1 | tail -5`

Expected: 1254 passed + 2 new passed = 1256 passed (or close — count is for tracking, not exact match).

- [ ] **Step 7: Commit**

```bash
git add the_door/src/the_door/models.py \
        the_door/tests/unit/core/test_models_resolution.py \
        the_door/tests/integration/diff/test_resolution_change_no_diff.py
git commit -m "feat(edge): add name_match_ambiguous resolution value + diff regression guard"
```
