# `models.py` 套件化（T2）— Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 1004 行的 `the_door.models` god-module 拆成 `the_door/models/` 套件（10 子模組 + `__init__.py` 門面），**欄位/型別/邏輯零變更**、消費端零修改。

**Architecture:** 按領域（PMEST 主軸）切，依 CRP 把 snapshot 自 diff 拆出。靠 `__init__.py` 全名 re-export 維持 `from the_door.models import X` 全相容。一道 import-equivalence 安全網（拆前拆後皆綠）+ 一道 DSM 結構不變量測試守住「DAG + 邊集不增 + SDP 方向 + 全名可 import」。

**Tech Stack:** Python 3.12、pytest、`ast`/`typing`（結構測試）。設計依據：`docs/superpowers/specs/2026-06-02-models-package-split-design.md`（**本 plan 與該 spec 並讀；spec 含完整 class→檔對照表 §5.1、逐檔 import §6.2、定義順序約束 §6.3、門面 §7.2、DSM 測試 §9.3**）。

---

## 關鍵事實（執行前必讀）

**目標檔**：`the_door/src/the_door/models.py`（拆完刪除）→ `the_door/src/the_door/models/`（新套件）。

**測試 cwd**：所有 pytest / git 指令在**內層** `the_door/` 目錄執行（`testpaths=["tests"]`）。Windows console 是 cp950，跑測試前置 `PYTHONUTF8=1` 避免編碼錯誤。

**⚠️ 範圍外**：`the_door/src/the_door/core/datamodel/models.py` 是**另一個獨立檔**，**完全不碰**。

**⚠️ 原子切換**：一旦 `models/__init__.py` 存在，`the_door.models` 即解析為套件、`models.py` 被遮蔽。故「建好全部子模組 + 完整 __init__ + 刪 models.py」**必須在同一個 commit 完成**（Task 02），中間狀態會壞 import。

**⚠️ 護欄（越線即否決）**：
- 欄位名、型別註解、預設值、`frozen`、`@dataclass`、docstring **逐字保留**；只搬位置。
- 79 個型別全保留、名稱不變、不增不減。
- **子模組內維持 `models.py` 的相對定義順序**（spec §6.3：`default_factory=<裸類別名>` 在 class 定義期求值，被引用者須先定義）。
- 不為資料契約引入抽象介面（spec §8.1 SAP）。
- 不改任何其他 `.py`（門面保證消費端零改）。
- **檔案邊界 = spec §5.1 對照表（10 子模組）為唯一真相；不得自行合併/拆分任何子模組**（含 `config.py` 維持獨立，見 spec §8.2 鎖定裁定）。
- **本刀為維護性刀、執行期資源中性**（eager 門面、不採 lazy）；**產出不得宣稱效能/資源收益**（spec §1.2.1）。

**依賴脊椎（本質結構，須保留）**：`vulnerability → snapshot → diff → pipeline`；其餘 7 領域為 L0 孤島。安全建檔順序（拓樸序）：先 L0（extraction/analysis/config/vulnerability/scope/doubt/timeline），再 snapshot → diff → pipeline。

---

## 任務順序（嚴格依序）

1. **task-01** — 加 import-equivalence 安全網（79 名硬編碼，對**現行單檔** `models.py` 就綠）。這是消費端相容性的保證網，拆後須仍綠。
2. **task-02** — 原子切換：建 10 子模組（逐字搬移 + 補 import）+ 完整 `__init__.py` 門面 + 刪 `models.py`，安全網與全套件皆綠後一次 commit。
3. **task-03** — 加 DSM 結構不變量測試（§9.3）+ 欄位級等價驗證（AST 比對拆前拆後）+ 全套件/覆蓋驗收。
4. **task-04** — 更新 backlog T2 進度 + spec 狀態。

Task 01 的安全網**對未重構的單檔就必須綠**；Task 02 拆完後它必須**仍全綠**（這就是消費端透明的證據）。
