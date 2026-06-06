# F-severity-default plan：severity 缺值誠實化 4-task inline TDD

> **日期**：2026-06-06　**狀態**：plan（待執行）　**承**：[`2026-06-06-F-severity-default-spec.md`](../specs/2026-06-06-F-severity-default-spec.md)（雙審：concept+5 軸；本 plan 引 spec §3.x 不重貼）。
> **執行方式**：inline TDD（red→green）。characterization 先行（既有測皆 recognized severity＝基線）。逐 task gate、末 task 全測。完成 ff-merge main、**不主動 push**。
> **基線**：main `8233374`、全測 1582 passed。驗收＝1582＋新測、零回歸（除有意更新）。
> **環境**：`pip install -e ./the_door`（本 session 已裝）；pytest cwd＝內層 `the_door/`；`PYTHONUTF8=1`。

---

## 範圍鎖定（承 spec §1）

- **in**：①scanner 去自鑄 + model 容 None ②schema 容 null（snapshot fail-closed + ast-raw doc）③renderer None 守衛 + format_summary_header 存在性 guard ④membrane/serde characterization。
- **out（不得誤動）**：severity SignalPosition／membrane B-側／VulnerabilitySummary 新欄／`update-report.schema.json`／前端 viewer／CVSS 解析／既有快照回填。
- **grep gate（末 task）**：`git diff --stat` 僅含 `vulnerability_scanner.py`＋`models/vulnerability.py`＋`snapshot.schema.json`＋`ast-raw.schema.json`＋`vulnerability_renderer.py`＋對應測；**無 update-report.schema/前端/新 SignalPosition**。

---

## Task 1 — scanner 去自鑄 + model 容 None（V1/V2）

**交付**（exact code＝spec §3.1-3.2）：
- `vulnerability_scanner.py:148-156`：缺/不認得 → `severity_str = None`（不 fallback "medium"）。
- `models/vulnerability.py:14`：`VulnerabilityEntry.severity: str | None`；`:46` `VulnerabilitySummaryEntry.severity: str | None`。

**TDD（red→green）**：
1. **pin**：`test_vulnerability_scanner.py` 既有 4 測全綠（基線；皆 recognized severity）。
2. **red→green**（`test_vulnerability_scanner.py` 擴充；`_osv` helper 現恆傳 severity_db，新增無 severity 鍵的 OSV 建構）：
   - V1：OSV `database_specific` **無 severity 鍵** → `entry.severity is None`。
   - V1：`database_specific.severity="UNKNOWN_LEVEL"`（不認得）→ None。
   - V2：`database_specific.severity="HIGH"` → "high"（regression pin）。

**gate**：`PYTHONUTF8=1 python -m pytest tests/unit/core/vulnerability/test_vulnerability_scanner.py -q` 綠。

---

## Task 2 — schema 容 null + serde round-trip（V3）

**交付**（exact code＝spec §3.3-3.4）：
- `snapshot.schema.json:81`：severity → `oneOf[4 const, null]`（比照同檔 confidence）。
- `ast-raw.schema.json:191`：severity → `oneOf[4 const, null]`（doc additive）。

**TDD（red→green）**：
1. **red→green**（`test_snapshot_store_roundtrip.py` 或 `test_snapshot_contract.py` 擴充）：V3 — `VulnerabilityEntry(..., severity=None, ...)` 經 `create_snapshot`（內含 `_write_snapshot` fail-closed）**不拋**；`get_snapshot` 讀回 `severity is None`。
2. 釘 schema additive：既有 string-severity 快照仍 validate（既有 contract 測綠＝基線保障）。

**gate**：`pytest tests/unit/core/diff/test_snapshot_store_roundtrip.py tests/unit/core/diff/test_snapshot_contract.py -q` 綠。

---

## Task 3 — renderer None 守衛 + 存在性 guard + membrane characterization（V4/V5/V6）

**交付**（exact code＝spec §3.5）：
- `vulnerability_renderer.py:71-73`：counts 迴圈加 `if v.severity in counts` 守衛。
- `vulnerability_renderer.py:103-116`：`format_summary_header` 存在性綁 `summary.entries`＋未分級 part。

**TDD（red→green）**：
1. **V6 red→green**（`vulnerability_renderer` 測，新檔或擴充）：
   - 僅一筆 None-severity 漏洞 → `format_summary_header` **非** "✅ 未偵測到已知漏洞"、含「未分級」。
   - 零漏洞 → "✅ 未偵測到已知漏洞"（regression）。
   - 混合 high＋None → header 同列高風險與未分級數。
2. **V4 characterization**：含 None-severity 的 `build_vulnerability_summary` 不炸；該筆在 entries、4-桶 total 不含它（counts 無 None 鍵）、排最後（`SEVERITY_ORDER.get(None,9)`）。
3. **V5 membrane characterization**（`test_vulnerability_membrane.py` 擴充）：`VulnerabilityEntry(severity=None, evidence="CVSS:...")` → `verdict_element().to_json()` payload `severity is None`＋position kind=="relayed_verdict"；`severity=None, evidence=""` → position kind=="noise"（indeterminate）。**證 position 鍵於 evidence、與 severity None 無關**。

**gate**：`pytest tests/unit/core/vulnerability/ -q` 綠。

---

## Task 4 — 全測 gate + grep gate

- `cd the_door && PYTHONUTF8=1 python -m pytest -q` ＝**1582＋新測、零回歸**。
- 回驗：vulnerability 既有測（emit 排序/dedup/membrane）全綠；snapshot serde/contract（additive）綠。
- `git diff --stat`：`vulnerability_scanner.py`＋`models/vulnerability.py`＋`snapshot.schema.json`＋`ast-raw.schema.json`＋`vulnerability_renderer.py`＋測檔。**無 update-report.schema/前端/新 model 欄/新 SignalPosition**。

---

## 完成後（ff-merge）

1. commit（建議：`docs(yi-an): F-severity-default spec+plan`／`fix(vuln): scanner 停止自鑄 medium，severity str|None (V1/V2)`／`fix(vuln-schema): severity 容 null + serde round-trip (V3)`／`fix(vuln-renderer): 存在性誠實 guard，None-severity 不謊報 (V4/V6) + membrane char (V5)`）。
2. ff-merge 回 main、**不主動 push**。
3. 更新 handoff：F-severity-default merged；剩餘＝contract-version bump 文件化／人類面整膜／presence-flag 型。

---

## 驗收清單（對應 spec §4）

| # | 驗收 | task |
|---|---|---|
| V1 | 缺/不認得 severity → None（不自鑄 medium） | 1 |
| V2 | recognized severity 保真 | 1 |
| V3 | None-severity serde round-trip + fail-closed 通過 | 2 |
| V4 | renderer None-safe（不入 4 桶、排最後、列 entries） | 3 |
| V5 | membrane payload severity 容 None；position 鍵於 evidence | 3 |
| V6 | 存在性不謊報（僅 None-severity 漏洞 header 非「未偵測」） | 3 |
| 回歸 | 全測 1582＋新測零回歸、out 清單未動 | 4 |

**plan 完成 → 待執行 inline TDD Task 1→4 → ff-merge。**
