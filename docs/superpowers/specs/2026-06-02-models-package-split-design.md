# T2：`models.py` 套件化（god-module 依領域拆分）— 設計

> **日期**：2026-06-02　**狀態**：已實作（plan: docs/superpowers/plans/2026-06-02-models-package-split/）
> **刀序**：第二刀第二段（T4 `run()` 拉直已實作並 merge；本刀承 backlog T2）
> **目標檔**：`the_door/src/the_door/models.py`（1004 行、79 個型別）
> **設計依據**：本 session 的兩支結構測繪腳本（純 AST 分析，已跑、結果內嵌於本文件第 4、5 節，腳本用完即刪、零版控污染）

---

## 0. 一頁摘要（給審查者）

把單檔 `the_door/src/the_door/models.py`（1004 行 / 79 型別 / 13 個領域）拆成
`the_door/src/the_door/models/` **套件（10 個子模組 + 一個 `__init__.py` 門面）**，
**欄位、型別、邏輯零變更**，靠 `__init__.py` 全名 re-export 達成**消費端零修改**。

- **不是**為了解糾纏——測繪證明內部依賴**本來就是乾淨的有向無環圖（DAG）**。
- **是**為了治「單檔 1000 行的導航成本 + 共用檔合併衝突面」。
- 切法依據**已量測**：按領域切＝依賴圖的最小割；snapshot 自 diff 拆出（CRP）後，
  依賴脊椎收斂成單調鏈 `vulnerability → snapshot → diff → pipeline`，且不穩定度
  （Martin I 值）呈完美遞增階梯、**零 SDP 違規**。
- 一道 **DSM 回歸測試**把「DAG + 邊集不增 + 方向順穩定度 + 門面全名可 import」釘成永久不變量。

---

## 1. 背景與動機

### 1.1 問題陳述
`the_door.models`（頂層）是一個典型的 **god-module**：1004 行、79 個 `@dataclass` 與例外類，
橫跨抽取、L1/L1.5/L2、驗證、敘事、設定、diff、快照、漏洞、scope、doubt、timeline、pipeline
共 13 個功能領域，全堆在單一檔案。痛點具體有三：

1. **導航成本**：找任一型別要在 1000 行裡翻；新進者打開檔案無法一眼看出系統有哪些領域。
2. **合併衝突面**：任一領域改自己的型別，動到的都是「全 repo 共用的單檔」，git 衝突機率高。
3. **認知負荷**：開檔即被迫一次面對 13 個領域（遠超工作記憶組塊上限）。

### 1.2 這「不是」什麼問題（避免把它做成 T4 型重構）
**內部結構本來就好。** 測繪（第 4 節）證明：
- 每個 `@dataclass` 都小、職責單一、多數 `frozen`（52/79 frozen）。
- 型別之間的「依賴」關係**已是合法偏序（反對稱、無環）**——沒有任何循環依賴。

所以本刀**不是「解結」**（那是 T4 對 `run()` 做的事），而是**「把堆在一個房間、彼此不糾纏的東西，
照領域分櫃」**。性質是分類與搬移，不是邏輯重整。⇒ **急迫性低、風險極低、近乎機械**。

### 1.2.1 ⚠️ 定位：維護性刀，執行期資源**中性**（不得宣稱省資源）
本刀的收益**只有維護性**：導航成本、合併衝突面、認知負荷、結構不變量被測試守住，外加 dev-time
小利（改一個領域只重編該檔的 `.pyc`）。**對 production 執行期資源（CPU/記憶體/載入時間）是中性的，
不會變省**——因為門面 `__init__.py` 採 **eager re-export**（一次載入全部 10 子模組），
`from the_door.models import X` 載入的內容與佔用記憶體與現行單檔**完全相同**（甚至因多幾次檔案
stat 而極輕微變慢，可忽略）。

**明確不採 lazy façade**（PEP 562 `__getattr__` 延後載入）：79 個極輕 dataclass 的載入成本本就
毫秒級、記憶體微不足道，lazy 省下的趨近於零，卻多一層間接並把 import 錯誤延後到存取時——
**償不了成本、且違反「不過度設計」準則**。除非日後有實測冷啟動痛點，否則維持 eager。

> 推論：若目標是「降低執行期資源」，T2 是錯的槓桿（該動的是刪死碼/熱路徑配置）。本刀請以
> **維護性**為唯一驗收口徑，**不得**在任何產出宣稱效能/資源收益。

### 1.3 北極星準則對齊
- ①可讀性/維護性優先：✅ 導航與合併面是主要收益。
- ②結構先行、行為不變：✅ 欄位/型別/邏輯零變更。
- ③證據驅動：✅ 切法、脊椎、I 值全部來自已跑的 AST 測繪。
- ④抽象要償還成本：✅ 唯一新增的抽象是「門面 + 一道測試」，償還的是永久結構保證；
  **明確拒絕**為資料契約套抽象介面（見 §3 非目標與 §8 SAP 註記）。

---

## 2. 理論依據（每條都換到一個具體 spec 改動，非裝飾）

| 理論 | 操作性結論 | 對本 spec 的具體改動 |
|---|---|---|
| **內聚力光譜 + SRP「變更理由」**（Constantine/Yourdon；Martin）| 按「同一變更理由」歸檔＝強內聚（功能/順序）；按「同一種類」歸檔（如 errors.py）＝邏輯內聚＝弱 | 主軸選**領域**；**拒絕**按角色（errors/summaries）切；小領域（l1/l1.5/l2/validation/narrative）因屬「同一條分析流水線的前後階段」（順序內聚）而**合併**為 `analysis.py` |
| **CCP/CRP**（Martin 套件內聚）| CRP：不要逼使用者依賴用不到的東西 | 測繪顯示 `diff` 對 `vuln` 的依賴僅來自 `VersionSnapshot`，純比對型別不碰 vuln ⇒ **把 snapshot 自 diff 拆出**（見 §4.4），消除「diff 消費者被迫拖入 vuln」 |
| **ADP + SDP + 不穩定度量**（Martin）| 依賴須無環且指向更穩定方向；`I = Ce/(Ca+Ce)` | spec 內嵌 **I 值表**（§5.2）並把「DAG + 方向順穩定度」寫進 DSM 測試斷言 |
| **設計結構矩陣 DSM**（系統工程）| 依賴矩陣重排成下三角＝拓樸排序；上三角格＝越界/回授 | 落地成 **DSM 回歸測試**（§9），把一次性測繪升級為永久護欄 |
| **Ranganathan 引用次序（PMEST）**（刻面分類）| 多 facet 時用固定優先序決定主櫃 | 訂「**領域 > 生命週期 > 角色**」為維護守則（§7），規範未來新增型別的歸檔 |
| **單型 vs 多型分類**（分類哲學）| 多型分類必有邊界爭議，需顯式裁決規則 | 附**邊界型別裁決表**（§6），把模糊歸屬顯式化 |
| **本質 vs 偶然複雜度**（Brooks）| 只動偶然複雜度、本質結構逐位保留 | 訂為驗收判準（§8）：本質結構（脊椎/79 型別/欄位）零變更，只動檔案擺放 |

被**剔除**（償不了成本，不採用）：動態語意網（無執行期推理需求；Python 型別系統已涵蓋語意）、
Cynefin/重系統理論（問題複雜度不足以償還）。

---

## 3. 範圍與非目標

### 3.1 範圍內
- 只拆**頂層** `the_door/src/the_door/models.py` → `the_door/src/the_door/models/` 套件。
- 新增 `__init__.py` 門面 + 一道 DSM 回歸測試。

### 3.2 ⚠️ 範圍外（明文排除，避免誤傷）
- **`the_door/src/the_door/core/datamodel/models.py` 完全不碰。** 這是 datamodel 契約驗證功能
  自己的獨立 `models.py`（消費端寫法為 `from the_door.core.datamodel.models import DeclaredField, CodeTouch`），
  與本刀目標是**不同檔案**。本刀一個字都不動它。
- 不改任何抽取層 / ASTNode / L1–L3 / snapshot **schema**（欄位）。
- 不改任何消費端程式（門面保證零修改）。
- 不寫框架/廠商解析器。

### 3.3 護欄（越線即否決）
- **欄位、型別名稱、預設值、`frozen`/`@dataclass` 裝飾、docstring 逐字保留**——只搬位置，不改內容。
- 不新增/移除任何型別；79 個型別全數保留、名稱不變。
- 不為資料契約引入抽象基底類別/Protocol/介面（見 §8 SAP）。
- 不調整 `from __future__ import annotations` 行為（每個子模組都保留）。
- 測試零回歸、覆蓋不降。

---

## 4. 測繪證據（已跑，純結構分析）

> 兩支 AST 腳本對 `models.py` 跑出，數字為本文件權威來源。下列為**完整輸出**，非摘要。

### 4.1 規模與刻面盤點
```
classes: 79   domains(原始): 13
per-role count: record 37, aggregate 16, error 12, summary 10, config 4
frozen: 52   non-frozen: 27
```
角色軸（error/summary）為**跨領域刻面**，但測繪證實它們**不產生結構壓力**（例外全是葉子、
摘要都在自己領域內）⇒ 確認**主軸選領域、角色軸退化為註記**（§2 內聚力光譜）。

### 4.2 循環依賴檢查（class 級 + 領域級）
```
CLASS-LEVEL CYCLES:  NONE — depends-on 在 class 級即為反對稱（DAG）
DOMAIN-LEVEL CYCLES: NONE — 領域圖為 DAG
```

### 4.3 原始 13 領域的跨領域依賴邊（拆 snapshot 前）
```
[diff]     VersionSnapshot -> DatabaseFreshness   [vuln]
[diff]     VersionSnapshot -> VulnerabilityEntry  [vuln]
[pipeline] AnalyzeResult   -> VersionSnapshot     [diff]
[pipeline] PipelineResult  -> VersionSnapshot     [diff]
[pipeline] PipelineResult  -> DiffResult          [diff]
[pipeline] AnalyzeResult   -> L1Output            [l1]
[pipeline] PipelineResult  -> ScopeResult         [scope]
[pipeline] PipelineResult  -> TimelineResult      [timeline]
[pipeline] AnalyzeResult   -> ScanResult          [vuln]
[pipeline] PipelineResult  -> ScanResult          [vuln]
```
共 10 條 class 級跨領域邊，全集中在 `diff` 與 `pipeline` 兩源；其餘 11 領域為彼此獨立孤島。
⇒ 按領域切＝依賴圖的最小割（§2 最小割/modularity）。

### 4.4 CRP 精煉：snapshot 自 diff 拆出（已驗證仍 DAG）
觀察：原 `diff` 領域對 `vuln` 的唯一依賴來源是 **`VersionSnapshot`**（持有
`vulnerabilities_snapshot`、`vulnerability_db_freshness`）；真正的比對型別
`NodeDiff/EdgeDiff/DiffSummary/DiffResult` 不碰 vuln。據 CRP 把持久化＋投影型別拆成
獨立 `snapshot` 模組後，重跑驗證（§5）：仍是 DAG、脊椎收斂為單調鏈。

---

## 5. 拆分後的目標結構（最終切法 = C + CRP 精煉，10 子模組）

### 5.1 完整 class → 檔案對照表（79 個，含現行行號便於機械搬移）

> 行號對應**現行** `the_door/src/the_door/models.py`。搬移時連同 docstring、裝飾器、欄位逐字複製。

**`models/extraction.py`（8）— 抽取層原始資料**
| 型別 | 現行行 | frozen |
|---|---|---|
| FileInfo | 10 | ✓ |
| ASTNode | 18 | ✓ |
| Edge | 34 | ✓ |
| TopologyEntry | 44 | ✓ |
| ExtractionError | 56 | ✗ |
| ExtractionResult | 64 | ✗ |
| TopologyResult | 75 | ✗ |
| StructureJSON | 82 | ✗ |

**`models/analysis.py`（15）— 一條分析流水線的前後階段（l1→validation→l1.5→l2→narrative）**
| 型別 | 現行行 | 原領域 |
|---|---|---|
| Feature | 95 | l1 |
| FeatureRelation | 112 | l1 |
| L1Output | 123 | l1 |
| CheckResult | 137 | validation |
| ValidationResult | 146 | validation |
| L1_5Block | 176 | l1.5 |
| BlockRelation | 187 | l1.5 |
| InfrastructureBlock | 198 | l1.5 |
| L1_5Output | 206 | l1.5 |
| L2Module | 218 | l2 |
| ModuleInteraction | 229 | l2 |
| Anomaly | 240 | l2 |
| L2Output | 250 | l2 |
| NarrativeNodeRead | 262 | narrative |
| NarrativeRecord | 272 | narrative |

**`models/config.py`（3）— LLM/設定（完全孤立島，Ca=0 Ce=0）**
| 型別 | 現行行 |
|---|---|
| TheDoorConfig | 297 |
| CostEstimate | 313 |
| ParseResult | 326 |

**`models/snapshot.py`（7）— 持久化 + 投影摘要（CRP 自 diff 拆出）**
| 型別 | 現行行 | 備註 |
|---|---|---|
| FeatureSummary | 341 | 投影自 Feature |
| BlockSummary | 369 | |
| RelationSummary | 379 | |
| BaselineInfo | 388 | 被 diff 的 DiffResult 依賴 |
| VersionSnapshot | 401 | 唯一碰 vuln 的型別（用 Path）|
| SnapshotError | 471 | 例外（基底）|
| SnapshotNotFoundError | 477 | 例外（繼承 SnapshotError）|

**`models/diff.py`（5）— 純比對**
| 型別 | 現行行 |
|---|---|
| NodeDiff | 420 |
| EdgeDiff | 434 |
| DiffSummary | 445 |
| DiffResult | 456 |
| DiffError | 486 |

**`models/vulnerability.py`（6）**
| 型別 | 現行行 |
|---|---|
| VulnerabilityEntry | 500 |
| DatabaseFreshness | 512 |
| ScanResult | 521 |
| VulnerabilitySummaryEntry | 531 |
| VulnerabilitySummary | 544 |
| VulnerabilityDiffSummary | 559 |

**`models/scope.py`（5）**
| 型別 | 現行行 |
|---|---|
| ScopeFeatureEntry | 579 |
| ScopeDefinition | 587 |
| ScopeEntry | 599 |
| ScopeCounts | 609 |
| ScopeResult | 618 |

**`models/doubt.py`（8）**
| 型別 | 現行行 |
|---|---|
| StateTransition | 630 |
| Resolution | 641 |
| DoubtRecord | 651 |
| DoubtSummary | 667 |
| ScopeDefinitionError | 679 |
| DoubtNotFoundError | 687 |
| InvalidTransitionError | 695 |
| DoubtTerminalError | 706 |

**`models/timeline.py`（7）**
| 型別 | 現行行 |
|---|---|
| SemanticDriftEvent | 722 |
| FeatureTimeline | 735 |
| TimelineSummary | 748 |
| TimelineResult | 757 |
| RetentionDecision | 768 |
| TimelineError | 779 |
| RetentionConfigError | 785 |

**`models/pipeline.py`（15）— 頂層彙總**
| 型別 | 現行行 | 備註 |
|---|---|---|
| AnalyzeConfig | 801 | |
| AnalyzeResult | 815 | 依賴 snapshot/analysis/vuln |
| StepTimeouts | 831 | |
| PipelineConfig | 843 | 用 Path |
| PipelineStep | 860 | |
| PipelineSummary | 872 | |
| L1ChangeEntry | 885 | |
| L2DetailEntry | 896 | |
| L3Appendix | 911 | |
| DiffChangeExplanation | 921 | |
| UpdateReport | 942 | |
| PipelineResult | 961 | 依賴 snapshot/diff/scope/timeline/vuln |
| PipelineError | 981 | 例外 |
| AnalyzeError | 989 | 例外 |
| CostConfirmationRequired | 995 | 例外 |

**計數核對**：8+15+3+7+5+6+5+8+7+15 = **79** ✓

### 5.2 不穩定度（Martin I 值）與依賴脊椎（拆 snapshot 後實測）
```
模組            Ca(被依賴) Ce(依賴)  I=Ce/(Ca+Ce)  層
analysis            1        0        0.00         L0
config              0        0        0.00         L0（孤立島）
doubt               0        0        0.00         L0
extraction          0        0        0.00         L0
scope               1        0        0.00         L0
timeline            1        0        0.00         L0
vulnerability       2        0        0.00         L0
snapshot            2        1        0.33         L1
diff                1        1        0.50         L2
pipeline            0        6        1.00         L3
```
**SDP 方向檢查：零違規**——每條依賴都指向 I 更低（更穩定）的一端。

**依賴脊椎（本質結構，須逐位保留）：**
```
L0  analysis / config / doubt / extraction / scope / timeline / vulnerability  （極小元，誰都不靠）
L1  snapshot      -> vulnerability
L2  diff          -> snapshot
L3  pipeline      -> analysis, diff, scope, snapshot, timeline, vulnerability
```
主幹單調鏈：**`vulnerability → snapshot → diff → pipeline`**。

### 5.3 拓樸排序（安全建檔/import 順序之一；L0 間任意）
```
analysis -> config -> doubt -> extraction -> scope -> timeline -> vulnerability -> snapshot -> diff -> pipeline
```

---

## 6. 各子模組的 import 需求（逐檔精確，含 §6.1 關鍵等價性）

### 6.0 共通
- 每個子模組頂部保留 `from __future__ import annotations`。
- 每個用到 dataclass 的子模組：`from dataclasses import dataclass, field`（`field` 視該檔是否用到，
  用不到則只 import `dataclass`）。

### 6.1 ⚠️ 關鍵等價性：跨模組引用全是「註解」或「=None」，無 default_factory 跨界
逐一核對跨模組引用點（§4.3 的 10 條 class 級邊）：
- `VersionSnapshot.vulnerabilities_snapshot: list[VulnerabilityEntry] = field(default_factory=list)` → factory 是 `list`，**非** `VulnerabilityEntry`；型別僅出現在註解。
- `VersionSnapshot.vulnerability_db_freshness: DatabaseFreshness | None = None` → 註解 + None。
- `DiffResult.baseline_info: BaselineInfo`（必填，無預設）→ 僅註解。
- `AnalyzeResult.snapshot/l1_output/scan_result`（必填）→ 僅註解。
- `PipelineResult.old_snapshot/new_snapshot/diff_result/scope_result/timeline_result/scan_result_*` 全是 `= None` → 註解 + None。

結論：**沒有任何跨模組型別出現在 `default_factory` 或 class 定義期會被求值的位置**。因
`from __future__ import annotations` 使所有註解延後為字串，跨模組 import **在 class 定義期不被求值**。
但為了 (a) `typing.get_type_hints()`（序列化端可能呼叫）能解析、(b) 可讀性，**仍採正常執行期
`from .X import Y`**——DAG 已證無環，正常 import 100% 安全、零循環風險。

### 6.2 逐檔 import 清單
| 子模組 | 跨模組 import | 標準庫 import |
|---|---|---|
| `extraction.py` | （無）| dataclass, field |
| `analysis.py` | （無）| dataclass, field |
| `config.py` | （無）| dataclass |
| `vulnerability.py` | （無）| dataclass, field |
| `snapshot.py` | `from .vulnerability import DatabaseFreshness, VulnerabilityEntry` | dataclass, field；**`from pathlib import Path`**（VersionSnapshot.codebase_path）|
| `diff.py` | `from .snapshot import BaselineInfo` | dataclass, field |
| `scope.py` | （無）| dataclass, field |
| `doubt.py` | （無）| dataclass, field |
| `timeline.py` | （無）| dataclass, field |
| `pipeline.py` | `from .analysis import L1Output`；`from .snapshot import VersionSnapshot`；`from .vulnerability import ScanResult`；`from .diff import DiffResult`；`from .scope import ScopeResult`；`from .timeline import TimelineResult` | dataclass, field；**`from pathlib import Path`**（PipelineConfig.old_path/new_path）|

> **註**：現行 `models.py` 第 795 行有一個位於檔案中段的 `from pathlib import Path`（靠
> `from __future__ import annotations` 延後求值才沒爆）。拆檔後此「中段 import」消失，
> 改由 `snapshot.py` 與 `pipeline.py` 各自在**頂部**正常 import `Path`，順手清掉這個味道。

### 6.3 ⚠️ 子模組內「定義順序」必須保留（factory 前向引用約束）
雖然跨模組引用無 `default_factory`（§6.1），但**同一子模組內**有 6 處 `default_factory=<裸類別名>`，
這些在 **class 定義期即被求值**（`from __future__ import annotations` 只延後「註解」，不延後 `field()`
的引數），故被引用的類別**必須先於引用者定義**。逐一列出（皆 intra-module、現行已滿足）：

| 子模組 | 引用者（行）| factory 引用（行）| 約束 |
|---|---|---|---|
| analysis | ValidationResult (146) | `lambda: CheckResult` (152–164) | lambda 已延後求值；CheckResult(137) 仍在前，無虞 |
| diff | DiffResult (456) | `DiffSummary` (464→指 445) | DiffSummary 必須在 DiffResult 前（445<456 ✓）|
| scope | ScopeResult (618) | `ScopeCounts` (624→指 609) | 609<618 ✓ |
| timeline | TimelineResult (757) | `TimelineSummary` (765→指 748) | 748<757 ✓ |
| pipeline | PipelineConfig (843) | `AnalyzeConfig`(849→801)、`StepTimeouts`(853→831) | 801,831<843 ✓ |
| pipeline | UpdateReport (942) | `L3Appendix` (952→指 911) | 911<942 ✓ |

**實作守則**：搬移型別進各子模組時，**一律照現行 `models.py` 的相對先後順序排列**，即自動滿足上表。
不得為了「分組美觀」重排同檔內的型別順序。

---

## 7. 門面 `models/__init__.py`（消費端零修改的關鍵）

### 7.1 設計
`models/__init__.py` 以**顯式具名** re-export 全部 79 個型別，使既有
`from the_door.models import <name>` 全部維持有效。**不使用** `from .x import *`（顯式才可審、可測）。

### 7.2 完整 re-export（按子模組分組；79 名全列，漏一個即有消費端炸）
```python
"""Core data models for The Door — package façade.

Re-exports every model from the per-domain submodules so that existing
`from the_door.models import X` imports continue to work unchanged.
Filing axis = domain (PMEST citation order: domain > lifecycle > role).
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
    # extraction
    "FileInfo", "ASTNode", "Edge", "TopologyEntry",
    "ExtractionError", "ExtractionResult", "TopologyResult", "StructureJSON",
    # analysis
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
```
`__all__` 長度必須 == 79（測試會斷言，見 §9）。

### 7.3 維護守則（PMEST 引用次序）—— 寫入門面 docstring 與 backlog
未來新增型別時，依**固定優先序決定歸檔主櫃**：
1. **領域（Personality，最高）**：屬於哪個功能領域 → 進該領域子模組。
2. **生命週期（Time）**：若跨領域，看它是輸入/中間/輸出，靠近其主要生產者所在層。
3. **角色（最低）**：summary/error/config 等角色**不單獨成檔**，跟隨其領域。
此守則防止結構隨時間侵蝕（entropy）。

---

## 8. 邊界型別裁決表（單型 vs 多型分類；顯式化模糊歸屬）

型別歸屬本質是多型（家族相似），必有邊界爭議。下表把**會被質疑**的歸屬顯式記錄，附依據：

| 型別 | 候選歸屬 | 最終歸屬 | 裁決依據 |
|---|---|---|---|
| VersionSnapshot | diff / snapshot | **snapshot** | 存在理由是「持久化某時點的 L1/L1.5 狀態」，非「比對」；它是 diff 的**輸入**而非 diff 的一部分 |
| BaselineInfo | diff / snapshot | **snapshot** | 描述某快照/版本的中繼資料；被 DiffResult 引用（diff→snapshot 邊），屬被依賴的穩定層 |
| FeatureSummary / BlockSummary / RelationSummary | analysis / snapshot | **snapshot** | 是「存進快照」的投影（projection），其存在理由是序列化儲存，非 L1 分析產物本身 |
| AnalyzeConfig | config / pipeline | **pipeline** | Phase 5 管線配置，與 PipelineConfig 同生命週期；`config.py` 專指 LLM/cost 設定（TheDoorConfig 等）|
| SnapshotError / SnapshotNotFoundError | diff / snapshot | **snapshot** | 快照操作的例外，跟隨 snapshot 領域（角色軸不單獨成檔）|
| 各 *Summary（Diff/Vulnerability/Timeline/Scope）| summaries.py / 各領域 | **各自領域** | 角色軸（summary）不成檔；摘要跟隨其資料領域，維持 locality |
| 各例外類 | errors.py / 各領域 | **各自領域** | 同上；例外是領域葉子，跟隨領域 |

### 8.1 SAP 註記（穩定抽象原則）—— 明文拒絕過度設計
L0 地基型別是「穩定（I=0）＋具體」，落在 Martin 的**痛苦區（Zone of Pain）**。
**這是資料傳輸物件（DTO）的天命，非缺陷。** 本刀**明確不為其引入抽象基底類別/Protocol/介面**——
那會增加層次、償不了成本（違準則④）。痛苦區對純資料契約是可接受的、預期的狀態。

### 8.2 ⚠️ 鎖定裁定：`config.py` 維持獨立檔、檔數從屬內聚力（執行時零模糊）
**決定：維持 10 個子模組；`config.py`（`TheDoorConfig` / `CostEstimate` / `ParseResult`，3 個型別、
`Ca=0 Ce=0` 完全孤立）獨立成檔，不併入 `analysis.py` 或任何其他檔。** 此為**最終裁定，不再爭論**。

理由（依本 spec 一貫的內聚力/SRP 準則）：
- `config` 的「變更理由」＝ **LLM 廠商/金鑰/計價/回應解析** 變動；`analysis` 的變更理由＝
  **L1/L2/validation 語意 schema** 變動。**兩者是不同的變更理由**（SRP），不該同檔。
- 把兩者併在一起的唯一動機是「都小、都 L0」——那是內聚力光譜上最弱的**偶然內聚
  （coincidental cohesion）**，**牴觸 §2 自訂的分檔準則**。為降檔數而併＝為形式犧牲內聚，否決。
- 「~8–9 檔」僅為 Miller 認知負荷的**軟性參考，從屬於內聚力**；職責清楚的 3 類別檔，
  優於混兩種變更理由的 18 類別檔。

執行守則：實作者**不得**自行合併/拆分任何子模組（含 config）；檔案邊界以 §5.1 對照表為**唯一真相**。
若未來確要調整檔數，須回到本 spec 修訂 §5.1 + §7.2 門面分組 + §9 `SUBMODULES` 清單三處後再動，
不得在實作時臨機決定。

---

## 9. DSM 回歸測試（把本質結構釘成永久不變量）

### 9.1 目的
把第 4、5 節的一次性測繪，升級為 CI 永久守住的不變量：
**(a)** 門面全 79 名可 import；**(b)** 模組依賴圖無環（ADP）；
**(c)** 跨模組邊集 == 設計邊集（不增不減）；**(d)** 每條邊方向順穩定度（SDP）。

### 9.2 檔案
- 新增：`the_door/tests/unit/core/test_models_package_structure.py`

### 9.3 完整測試碼（自含；採執行期型別解析，不靠原始碼字串比對）
```python
"""DSM regression test for the the_door.models package.

Pins the post-split structure as an enforced invariant:
  (a) every public name re-exported by the façade is importable;
  (b) the module dependency graph is acyclic (ADP);
  (c) the cross-module edge set equals the designed set (no new coupling);
  (d) every dependency points toward greater stability (SDP, Martin's I).

The dependency graph is rebuilt at runtime by resolving each dataclass's
field type hints (and exception bases) and mapping referenced model classes
to their defining submodule — so it tracks real code, not a transcript.
"""
from __future__ import annotations

import dataclasses
import importlib
import typing

import the_door.models as M

# ── (a) the façade must export exactly these 79 names ────────────────────
EXPECTED_NAMES = set(M.__all__)
EXPECTED_COUNT = 79

# ── (c) the designed cross-module edge set (module -> module) ────────────
# Derived from the 2026-06-02 measurement; see spec §5.2.
EXPECTED_MODULE_EDGES = {
    ("snapshot", "vulnerability"),
    ("diff", "snapshot"),
    ("pipeline", "analysis"),
    ("pipeline", "snapshot"),
    ("pipeline", "vulnerability"),
    ("pipeline", "diff"),
    ("pipeline", "scope"),
    ("pipeline", "timeline"),
}

SUBMODULES = [
    "extraction", "analysis", "config", "vulnerability", "snapshot",
    "diff", "scope", "doubt", "timeline", "pipeline",
]

PKG = "the_door.models"


def _short(module_name: str) -> str | None:
    """'the_door.models.snapshot' -> 'snapshot'; None if outside the package."""
    if module_name == PKG or not module_name.startswith(PKG + "."):
        return None
    return module_name[len(PKG) + 1:]


def _referenced_model_classes(hint) -> set:
    """Walk a (possibly generic) type hint, collecting model classes."""
    found = set()
    for arg in typing.get_args(hint):
        found |= _referenced_model_classes(arg)
    if isinstance(hint, type) and getattr(hint, "__module__", "").startswith(PKG):
        found.add(hint)
    return found


def _build_module_graph():
    edges = set()
    nodes = set()
    for sub in SUBMODULES:
        mod = importlib.import_module(f"{PKG}.{sub}")
        nodes.add(sub)
        for name in dir(mod):
            obj = getattr(mod, name)
            if not isinstance(obj, type):
                continue
            if getattr(obj, "__module__", None) != f"{PKG}.{sub}":
                continue  # only classes DEFINED here, not re-imports
            referenced = set()
            if dataclasses.is_dataclass(obj):
                hints = typing.get_type_hints(obj)
                for h in hints.values():
                    referenced |= _referenced_model_classes(h)
            for base in getattr(obj, "__bases__", ()):
                if getattr(base, "__module__", "").startswith(PKG):
                    referenced.add(base)
            for ref in referenced:
                target = _short(ref.__module__)
                if target and target != sub:
                    edges.add((sub, target))
    return nodes, edges


def _instability(nodes, edges):
    ce = {n: 0 for n in nodes}  # efferent: depends on
    ca = {n: 0 for n in nodes}  # afferent: depended on by
    for a, b in edges:
        ce[a] += 1
        ca[b] += 1
    return {n: (ce[n] / (ca[n] + ce[n]) if (ca[n] + ce[n]) else 0.0) for n in nodes}


def _has_cycle(nodes, edges):
    adj = {n: set() for n in nodes}
    for a, b in edges:
        adj[a].add(b)
    color = {n: 0 for n in nodes}

    def dfs(u):
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1:
                return True
            if color[v] == 0 and dfs(v):
                return True
        color[u] = 2
        return False

    return any(color[n] == 0 and dfs(n) for n in nodes)


def test_facade_exports_exactly_79_names():
    assert len(M.__all__) == EXPECTED_COUNT
    assert len(set(M.__all__)) == EXPECTED_COUNT  # no duplicates


def test_every_public_name_is_importable():
    for name in EXPECTED_NAMES:
        assert hasattr(M, name), f"façade missing re-export: {name}"
        assert isinstance(getattr(M, name), type), f"{name} is not a class"


def test_module_graph_is_acyclic():
    nodes, edges = _build_module_graph()
    assert not _has_cycle(nodes, edges), f"models package has an import cycle: {edges}"


def test_cross_module_edges_match_design():
    _, edges = _build_module_graph()
    assert edges == EXPECTED_MODULE_EDGES, (
        f"unexpected edges (new coupling?): added={edges - EXPECTED_MODULE_EDGES}, "
        f"missing={EXPECTED_MODULE_EDGES - edges}"
    )


def test_dependencies_point_toward_stability():
    nodes, edges = _build_module_graph()
    I = _instability(nodes, edges)
    violations = [(a, I[a], b, I[b]) for a, b in edges if I[a] < I[b] - 1e-9]
    assert not violations, f"SDP violations (depend on less stable): {violations}"
```

> **註**：測試以 `typing.get_type_hints()` 在執行期解析註解（這也順帶驗證了 §6.1 的
> 「跨模組型別在 get_type_hints 時可解析」），用 `obj.__module__ == f"{PKG}.{sub}"` 過濾
> 「只算在該檔**定義**的 class、不算 re-import」。`EXPECTED_MODULE_EDGES` 即 §5.2 脊椎的
> 模組級邊集（**8 條模組級邊**）。注意：拆 snapshot 後的 class 級跨模組邊為 **11 條**
> （§4.3 的 10 條 + 因 BaselineInfo 移入 snapshot 而新曝光的 `DiffResult→BaselineInfo`），
> 去重到模組級後為 8 條。測試斷言的是這 8 條模組級邊。

---

## 10. 消費端串聯影響分析（已掃，零繞過門面）

對頂層 `the_door.models` 的全 repo 消費端（`the_door/src` + `the_door/tests`，約 140 檔）掃描結論：

| 危險用法 | 出現次數 | 影響 |
|---|---|---|
| `from the_door.models import *`（會讓 `__all__` 成命脈）| **0** | 無 |
| `import the_door.models as m` / `from the_door import models`（模組物件存取）| **0** | 無 |
| `patch("the_door.models.X")`（monkeypatch 打定義點）| **0** | 無 |
| 靠 `__module__`/`qualname`/`pickle` 的序列化 | **0**（唯一 `__module__` 用法在 `core/ui/api/router.py`，操作路由 handler，與 models 無關）| 無 |
| `from the_door.models import Path/field/dataclass`（非 class 符號）| **0** | 無 |

**所有消費端皆為 `from the_door.models import <具名清單>`（絕對路徑、具名）**，含函式內 lazy import，
全數被門面全名 re-export 接住。三層串聯確認：
1. **執行期 import**：~140 檔具名 import 拆檔後逐一仍解析得到（門面轉發）。
2. **持久化相容**：序列化走 dataclass→dict **逐欄位**、**不記錄 `__module__`**（無 pickle）⇒
   `.the-door/` 既有舊 snapshot JSON 拆檔後照常反序列化。
3. **型別識別**：class 名稱與物件不變 ⇒ `isinstance`、身分判斷零影響。

⇒ **本刀對其他程式透明**：無任何消費端需改、舊持久化資料相容、型別識別不變。

---

## 11. 驗收判準（Brooks：本質零變更、只動偶然複雜度）

實作完成須全數成立：
1. **欄位/型別零變更**：`git diff` 對照拆前拆後，所有 dataclass 的欄位名、型別註解、預設值、
   `frozen`、docstring 逐字相同（只是分散到 10 檔）。**型別總數 == 79、名稱集合不變。**
2. **門面全名可 import**：§9 的 `test_every_public_name_is_importable` + `__all__` 長度 == 79 通過。
3. **結構不變量**：§9 的 acyclic / edges-match-design / SDP 三測通過。
4. **消費端零修改**：除 `models.py`→`models/` 的搬移外，**不改任何其他 `.py` 檔**（含 import 行）。
   （`git diff --stat` 應只見 `models.py` 刪除 + `models/` 新增 + 一個新測試檔。）
5. **零回歸**：`PYTHONUTF8=1 python -m pytest` 全綠，數量與拆前一致（拆前基準：1383 passed /
   46 skipped / 1 xfailed，實作時以當下 main 為準重新記錄）。
6. **覆蓋不降**：`models` 套件覆蓋率 ≥ 拆前 `models.py`。

---

## 12. 風險與緩解

| 風險 | 機率 | 緩解 |
|---|---|---|
| 門面漏掉某個 re-export 名 → 消費端 ImportError | 中 | §7.2 完整 79 名清單 + §9 全名 import 測試逐名斷言；`__all__` 長度斷言 == 79 |
| 搬移時手誤改到欄位/預設值 | 低 | §11.1 逐字 diff 核對；測試零回歸 |
| 拆檔意外引入循環 import | 極低 | DAG 已證；正常執行期 import 安全；§9 acyclic 測試永久守住 |
| 誤動到 `core/datamodel/models.py` | 低 | §3.2 明文排除；diff 範圍核對 |
| `get_type_hints` 在某子模組解析不到跨模組名 | 低 | §6.2 採正常執行期 import（非 TYPE_CHECKING-only）；§9 測試本身就會呼叫 get_type_hints 驗證 |
| 中段 `from pathlib import Path` 漏遷 | 低 | §6.2 明列 snapshot.py 與 pipeline.py 各自頂部 import Path |

---

## 13. Out of scope / 後續

- 不在本刀：`core/datamodel/models.py`（獨立檔）、任何消費端重構、schema 變更。
- 後續（非本刀）：backlog T3/T5 已降級，除非日後有具體異味。

---

## 附錄 A：實作順序提示（供 writing-plans 參考，非硬性）
1. 建 `models/` 套件目錄。
2. 依拓樸序（§5.3，L0 先）建各子模組，逐檔搬移對應型別 + 補 §6.2 的 import。
3. 寫 `__init__.py` 門面（§7.2）。
4. 刪除原 `models.py`。
5. 加 §9 DSM 測試。
6. 跑全套件 + 覆蓋 + §11 驗收。
7. 更新 backlog T2 進度、spec 狀態。
