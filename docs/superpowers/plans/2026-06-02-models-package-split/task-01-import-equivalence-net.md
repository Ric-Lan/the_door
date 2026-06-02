# Task 01: Import-equivalence safety net

**目的**：建立一道測試，斷言全部 79 個型別都能從 `the_door.models` import。這道測試**對現行（未拆）單檔 `models.py` 就必須通過**——它是 Task 02 拆檔後「消費端零修改」的安全網（拆後須仍全綠）。

**Files:**
- Create: `the_door/tests/unit/core/test_models_import_equivalence.py`

**前置**：cwd = 內層 `the_door/`。本任務只新增測試檔，不碰任何 src。

---

- [ ] **Step 1: 寫安全網測試（79 名硬編碼）**

建立 `the_door/tests/unit/core/test_models_import_equivalence.py`，完整內容如下：

```python
"""Import-equivalence safety net for the_door.models.

Pins the public surface: every one of the 79 model types must be importable
from `the_door.models`. Passes against the CURRENT single-file models.py and
MUST stay green after the package split (proves consumers are unaffected).
"""
from __future__ import annotations

import importlib

# The complete public surface of the_door.models (79 types).
EXPECTED_NAMES = [
    # extraction
    "FileInfo", "ASTNode", "Edge", "TopologyEntry",
    "ExtractionError", "ExtractionResult", "TopologyResult", "StructureJSON",
    # analysis (l1 + validation + l1.5 + l2 + narrative)
    "Feature", "FeatureRelation", "L1Output",
    "CheckResult", "ValidationResult",
    "L1_5Block", "BlockRelation", "InfrastructureBlock", "L1_5Output",
    "L2Module", "ModuleInteraction", "Anomaly", "L2Output",
    "NarrativeNodeRead", "NarrativeRecord",
    # config
    "TheDoorConfig", "CostEstimate", "ParseResult",
    # vulnerability
    "VulnerabilityEntry", "DatabaseFreshness", "ScanResult",
    "VulnerabilitySummaryEntry", "VulnerabilitySummary", "VulnerabilityDiffSummary",
    # snapshot
    "FeatureSummary", "BlockSummary", "RelationSummary", "BaselineInfo", "VersionSnapshot",
    "SnapshotError", "SnapshotNotFoundError",
    # diff
    "NodeDiff", "EdgeDiff", "DiffSummary", "DiffResult", "DiffError",
    # scope
    "ScopeFeatureEntry", "ScopeDefinition", "ScopeEntry", "ScopeCounts", "ScopeResult",
    # doubt
    "StateTransition", "Resolution", "DoubtRecord", "DoubtSummary",
    "ScopeDefinitionError", "DoubtNotFoundError", "InvalidTransitionError", "DoubtTerminalError",
    # timeline
    "SemanticDriftEvent", "FeatureTimeline", "TimelineSummary", "TimelineResult",
    "RetentionDecision", "TimelineError", "RetentionConfigError",
    # pipeline
    "AnalyzeConfig", "AnalyzeResult", "StepTimeouts", "PipelineConfig",
    "PipelineStep", "PipelineSummary", "L1ChangeEntry", "L2DetailEntry", "L3Appendix",
    "DiffChangeExplanation", "UpdateReport", "PipelineResult",
    "PipelineError", "AnalyzeError", "CostConfirmationRequired",
]


def test_expected_names_count_is_79():
    assert len(EXPECTED_NAMES) == 79
    assert len(set(EXPECTED_NAMES)) == 79  # no duplicates


def test_all_names_importable_from_the_door_models():
    mod = importlib.import_module("the_door.models")
    missing = [n for n in EXPECTED_NAMES if not hasattr(mod, n)]
    assert not missing, f"the_door.models is missing: {missing}"
    # every name resolves to a class
    non_class = [n for n in EXPECTED_NAMES if not isinstance(getattr(mod, n), type)]
    assert not non_class, f"not classes: {non_class}"


def test_names_match_actual_module_classes():
    """The 79 expected names equal the set of classes the module actually
    defines/exports — guards against the list drifting out of sync."""
    import inspect
    mod = importlib.import_module("the_door.models")
    actual = {
        name for name, obj in inspect.getmembers(mod, inspect.isclass)
        if obj.__module__.startswith("the_door.models")
    }
    assert actual == set(EXPECTED_NAMES), (
        f"drift: only-in-module={sorted(actual - set(EXPECTED_NAMES))}, "
        f"only-in-expected={sorted(set(EXPECTED_NAMES) - actual)}"
    )
```

- [ ] **Step 2: 跑測試，確認對現行單檔就綠**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/test_models_import_equivalence.py -v
```
Expected: **3 passed**。
若 FAIL（例如 `test_names_match_actual_module_classes` 報 drift），表示 EXPECTED_NAMES 與現行 `models.py` 不符——**停下回報**，不要改 src 迎合（這是現狀的刻畫）。

> 註：`test_names_match_actual_module_classes` 的過濾條件 `obj.__module__.startswith("the_door.models")` 對現行單檔（`__module__ == "the_door.models"`）與拆後套件（`__module__ == "the_door.models.snapshot"` 等）**都成立**，故拆後此測試仍正確。

- [ ] **Step 3: Commit**

```
git add tests/unit/core/test_models_import_equivalence.py
git commit -m "test(models): import-equivalence safety net for models public surface"
```
