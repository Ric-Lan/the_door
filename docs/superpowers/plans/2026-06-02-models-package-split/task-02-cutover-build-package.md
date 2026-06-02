# Task 02: 原子切換 — 建套件 + 門面 + 刪舊檔

**目的**：把 `models.py` 的 79 個型別逐字搬進 10 個子模組、寫完整 `__init__.py` 門面、刪除 `models.py`。**全部在一個 commit 完成**（中間狀態會壞 import）。

**Files:**
- Create: `the_door/src/the_door/models/__init__.py`
- Create: `the_door/src/the_door/models/{extraction,analysis,config,vulnerability,snapshot,diff,scope,doubt,timeline,pipeline}.py`
- Delete: `the_door/src/the_door/models.py`

**前置**：Task 01 安全網已 commit 且綠。cwd = 內層 `the_door/`。**搬移＝逐字複製**（decorator + class + 完整 body + docstring），**保持各型別在 `models.py` 的相對先後順序**。每個子模組頂部先放下列 import 區，再依序貼入該檔型別。

> 來源行號見 spec §5.1；逐檔 import 見 spec §6.2；順序約束見 spec §6.3。下方每個 Step 已把該檔的 import 區與型別清單（含現行起始行）列全。

---

- [ ] **Step 1: 建目錄 + L0 葉子模組 `extraction.py`（8 型別，無跨模組 import）**

建 `the_door/src/the_door/models/extraction.py`，頂部：
```python
"""Extraction-layer data models (AST extraction output + topology)."""
from __future__ import annotations

from dataclasses import dataclass, field
```
依序逐字搬入（來源 `models.py` 行）：`FileInfo`(10)、`ASTNode`(18)、`Edge`(34)、`TopologyEntry`(44)、`ExtractionError`(56)、`ExtractionResult`(64)、`TopologyResult`(75)、`StructureJSON`(82)。

- [ ] **Step 2: `analysis.py`（15 型別，無跨模組 import）**

建 `models/analysis.py`，頂部：
```python
"""Analysis-pipeline data models (L1, validation, L1.5, L2, narrative chain)."""
from __future__ import annotations

from dataclasses import dataclass, field
```
依序搬入：`Feature`(95)、`FeatureRelation`(112)、`L1Output`(123)、`CheckResult`(137)、`ValidationResult`(146)、`L1_5Block`(176)、`BlockRelation`(187)、`InfrastructureBlock`(198)、`L1_5Output`(206)、`L2Module`(218)、`ModuleInteraction`(229)、`Anomaly`(240)、`L2Output`(250)、`NarrativeNodeRead`(262)、`NarrativeRecord`(272)。
（`ValidationResult` 的 `default_factory=lambda: CheckResult(...)` 靠 lambda 延後求值；`CheckResult` 在其前，無虞。）

- [ ] **Step 3: `config.py`（3 型別，無跨模組 import，無 `field`）**

建 `models/config.py`，頂部：
```python
"""LLM / configuration data models."""
from __future__ import annotations

from dataclasses import dataclass
```
依序搬入：`TheDoorConfig`(297)、`CostEstimate`(313)、`ParseResult`(326)。
（這三個型別都用簡單預設值、**不使用 `field()`**，故只 import `dataclass`。）

- [ ] **Step 4: `vulnerability.py`（6 型別，無跨模組 import）**

建 `models/vulnerability.py`，頂部：
```python
"""Vulnerability-layer data models."""
from __future__ import annotations

from dataclasses import dataclass, field
```
依序搬入：`VulnerabilityEntry`(500)、`DatabaseFreshness`(512)、`ScanResult`(521)、`VulnerabilitySummaryEntry`(531)、`VulnerabilitySummary`(544)、`VulnerabilityDiffSummary`(559)。

- [ ] **Step 5: `scope.py`（5）、`doubt.py`（8）、`timeline.py`（7）（皆 L0，無跨模組 import）**

`models/scope.py` 頂部：
```python
"""Scope verification data models."""
from __future__ import annotations

from dataclasses import dataclass, field
```
依序搬入：`ScopeFeatureEntry`(579)、`ScopeDefinition`(587)、`ScopeEntry`(599)、`ScopeCounts`(609)、`ScopeResult`(618)。

`models/doubt.py` 頂部：
```python
"""Doubt-path data models (and doubt exceptions)."""
from __future__ import annotations

from dataclasses import dataclass, field
```
依序搬入：`StateTransition`(630)、`Resolution`(641)、`DoubtRecord`(651)、`DoubtSummary`(667)、`ScopeDefinitionError`(679)、`DoubtNotFoundError`(687)、`InvalidTransitionError`(695)、`DoubtTerminalError`(706)。

`models/timeline.py` 頂部：
```python
"""History-timeline data models (and timeline exceptions)."""
from __future__ import annotations

from dataclasses import dataclass, field
```
依序搬入：`SemanticDriftEvent`(722)、`FeatureTimeline`(735)、`TimelineSummary`(748)、`TimelineResult`(757)、`RetentionDecision`(768)、`TimelineError`(779)、`RetentionConfigError`(785)。

- [ ] **Step 6: `snapshot.py`（7，L1 — 依賴 vulnerability + 用 Path）**

建 `models/snapshot.py`，頂部：
```python
"""Snapshot persistence + projection data models (and snapshot exceptions)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .vulnerability import DatabaseFreshness, VulnerabilityEntry
```
依序搬入：`FeatureSummary`(341)、`BlockSummary`(369)、`RelationSummary`(379)、`BaselineInfo`(388)、`VersionSnapshot`(401)、`SnapshotError`(471)、`SnapshotNotFoundError`(477)。
（`VersionSnapshot` 用到 `Path`（codebase_path）、`DatabaseFreshness`/`VulnerabilityEntry`（註解）；`FeatureSummary/BlockSummary/RelationSummary` 在其前，順序保留。）

- [ ] **Step 7: `diff.py`（5，L2 — 依賴 snapshot）**

建 `models/diff.py`，頂部：
```python
"""Diff-engine data models (and diff exception)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .snapshot import BaselineInfo
```
依序搬入：`NodeDiff`(420)、`EdgeDiff`(434)、`DiffSummary`(445)、`DiffResult`(456)、`DiffError`(486)。
（`DiffResult` 用 `default_factory=DiffSummary`（intra，在其前）+ `baseline_info: BaselineInfo`（自 snapshot import）。）

- [ ] **Step 8: `pipeline.py`（15，L3 — 依賴 analysis/snapshot/vulnerability/diff/scope/timeline + 用 Path）**

建 `models/pipeline.py`，頂部：
```python
"""Realtime pipeline + report data models (and pipeline exceptions)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .analysis import L1Output
from .diff import DiffResult
from .scope import ScopeResult
from .snapshot import VersionSnapshot
from .timeline import TimelineResult
from .vulnerability import ScanResult
```
依序搬入：`AnalyzeConfig`(801)、`AnalyzeResult`(815)、`StepTimeouts`(831)、`PipelineConfig`(843)、`PipelineStep`(860)、`PipelineSummary`(872)、`L1ChangeEntry`(885)、`L2DetailEntry`(896)、`L3Appendix`(911)、`DiffChangeExplanation`(921)、`UpdateReport`(942)、`PipelineResult`(961)、`PipelineError`(981)、`AnalyzeError`(989)、`CostConfirmationRequired`(995)。
（順序保留即滿足 `PipelineConfig` 用 `AnalyzeConfig`/`StepTimeouts`、`UpdateReport` 用 `L3Appendix` 的 factory 前向引用。）

- [ ] **Step 9: 寫 `__init__.py` 門面（全 79 名 re-export）**

建 `the_door/src/the_door/models/__init__.py`，**完整內容**如下：

```python
"""Core data models for The Door — package façade.

Re-exports every model from the per-domain submodules so that existing
`from the_door.models import X` imports continue to work unchanged.
Filing axis = domain (PMEST citation order: domain > lifecycle > role).
When adding a new model: file it by domain first; summaries/errors follow
their domain (no role-based files); never reorder within a submodule
(default_factory forward refs are evaluated at class-definition time).
"""
from __future__ import annotations

from .extraction import (
    FileInfo, ASTNode, Edge, TopologyEntry,
    ExtractionError, ExtractionResult, TopologyResult, StructureJSON,
)
from .analysis import (
    Feature, FeatureRelation, L1Output,
    CheckResult, ValidationResult,
    L1_5Block, BlockRelation, InfrastructureBlock, L1_5Output,
    L2Module, ModuleInteraction, Anomaly, L2Output,
    NarrativeNodeRead, NarrativeRecord,
)
from .config import TheDoorConfig, CostEstimate, ParseResult
from .vulnerability import (
    VulnerabilityEntry, DatabaseFreshness, ScanResult,
    VulnerabilitySummaryEntry, VulnerabilitySummary, VulnerabilityDiffSummary,
)
from .snapshot import (
    FeatureSummary, BlockSummary, RelationSummary, BaselineInfo, VersionSnapshot,
    SnapshotError, SnapshotNotFoundError,
)
from .diff import NodeDiff, EdgeDiff, DiffSummary, DiffResult, DiffError
from .scope import (
    ScopeFeatureEntry, ScopeDefinition, ScopeEntry, ScopeCounts, ScopeResult,
)
from .doubt import (
    StateTransition, Resolution, DoubtRecord, DoubtSummary,
    ScopeDefinitionError, DoubtNotFoundError, InvalidTransitionError, DoubtTerminalError,
)
from .timeline import (
    SemanticDriftEvent, FeatureTimeline, TimelineSummary, TimelineResult,
    RetentionDecision, TimelineError, RetentionConfigError,
)
from .pipeline import (
    AnalyzeConfig, AnalyzeResult, StepTimeouts, PipelineConfig,
    PipelineStep, PipelineSummary, L1ChangeEntry, L2DetailEntry, L3Appendix,
    DiffChangeExplanation, UpdateReport, PipelineResult,
    PipelineError, AnalyzeError, CostConfirmationRequired,
)

__all__ = [
    "FileInfo", "ASTNode", "Edge", "TopologyEntry",
    "ExtractionError", "ExtractionResult", "TopologyResult", "StructureJSON",
    "Feature", "FeatureRelation", "L1Output",
    "CheckResult", "ValidationResult",
    "L1_5Block", "BlockRelation", "InfrastructureBlock", "L1_5Output",
    "L2Module", "ModuleInteraction", "Anomaly", "L2Output",
    "NarrativeNodeRead", "NarrativeRecord",
    "TheDoorConfig", "CostEstimate", "ParseResult",
    "VulnerabilityEntry", "DatabaseFreshness", "ScanResult",
    "VulnerabilitySummaryEntry", "VulnerabilitySummary", "VulnerabilityDiffSummary",
    "FeatureSummary", "BlockSummary", "RelationSummary", "BaselineInfo", "VersionSnapshot",
    "SnapshotError", "SnapshotNotFoundError",
    "NodeDiff", "EdgeDiff", "DiffSummary", "DiffResult", "DiffError",
    "ScopeFeatureEntry", "ScopeDefinition", "ScopeEntry", "ScopeCounts", "ScopeResult",
    "StateTransition", "Resolution", "DoubtRecord", "DoubtSummary",
    "ScopeDefinitionError", "DoubtNotFoundError", "InvalidTransitionError", "DoubtTerminalError",
    "SemanticDriftEvent", "FeatureTimeline", "TimelineSummary", "TimelineResult",
    "RetentionDecision", "TimelineError", "RetentionConfigError",
    "AnalyzeConfig", "AnalyzeResult", "StepTimeouts", "PipelineConfig",
    "PipelineStep", "PipelineSummary", "L1ChangeEntry", "L2DetailEntry", "L3Appendix",
    "DiffChangeExplanation", "UpdateReport", "PipelineResult",
    "PipelineError", "AnalyzeError", "CostConfirmationRequired",
]
```

- [ ] **Step 10: 刪除舊單檔**

```
git rm src/the_door/models.py
```
（必須在本 commit 內刪除：`models.py` 與 `models/` 不可並存，否則套件遮蔽舊檔造成混淆。）

- [ ] **Step 11: 跑安全網（拆後必須仍綠）**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/test_models_import_equivalence.py -v
```
Expected: **3 passed**（與 Task 01 相同）。若 FAIL → 門面漏 re-export 某名或型別搬錯檔，比對 `__all__` 與報錯名修正。

- [ ] **Step 12: 跑全套件（零回歸）**

Run：
```
PYTHONUTF8=1 python -m pytest
```
Expected: 全 PASS（與拆前一致；基準參考 1383 passed / 46 skipped / 1 xfailed，以當下實際為準，**不得有新 fail/error**）。
若有 `ImportError`/`NameError` → 多半是某子模組漏了跨模組 import 或定義順序錯，對照各 Step 的 import 區與 spec §6.2/§6.3 修正。

- [ ] **Step 13: Commit**

```
git add src/the_door/models/
git commit -m "refactor(models): split models.py into per-domain package with re-export facade"
```
（`git rm` 的刪除已 staged；本 commit 同時含新增 `models/` 與刪除 `models.py`。）
