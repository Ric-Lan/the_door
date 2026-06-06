# F-severity-default spec：殺自鑄 medium、severity 缺值誠實化（str|None）

> **日期**：2026-06-06　**狀態**：spec（pre-plan，寫前已對真實碼 spike＋全消費端掃描）　**性質**：獨立小刀（非主軸；vulnerability 域的 A-側「閉集 enum 缺值誠實化」，承 S4 confidence A-側通則）。承 S3 vulnerability_membrane（RelayedVerdict/NoisePosition）＋Finding A（snapshot fail-closed 落盤口）。
> **一句話**：OSV 未給 severity 類別時，scanner 現在**自鑄 `"medium"` 中點**（`vulnerability_scanner.py:149,156`）＝違 fact-finder（自鑄裁決）。改為缺值→`None`（誠實缺席），讓 model/schema 容 null。

---

## 0. 理論錨點

| 原則 | 對本刀約束 |
|---|---|
| **fact-finder、禁自鑄裁決**（§8.2A/O1） | severity 是 OSV 給的外部裁決類別；OSV 沒給 → 不可自鑄 `"medium"`（捏中點＝最嚴重的自鑄，與 S3 已殺的 CVSS 捏中點同類）。缺值＝`None`（誠實缺席）。 |
| **S4 A-側缺值誠實化通則** | 閉集 enum 的缺值：model `str\|None`、schema `oneOf[consts]+null`、移除 `= "medium"` 自鑄 default。完全比照 S4 confidence（移 7 處 `.get(...,"medium")`）。 |
| **severity ∈ payload 非 Door 軸**（S3 §membrane） | severity 是「裁決識別事實、OSV 直給」住 RelayedVerdict/Noise payload，**非 Door 自有的 Signal 軸**（contrast 集屬 OSV 非 Door）⟹ **本刀只做 A-側誠實化、不建 severity SignalPosition**。缺值的「indeterminate」語義已由既有 `NoisePosition(gap_kind="indeterminate")`（無 evidence 時）在 position 層表達；severity=None 在 payload 表達「無類別」。 |
| **寫嚴讀寬／向後相容**（Finding A） | schema 加 null＝additive（舊快照 severity 皆 string、仍合法）；新 None-severity 經 `_write_snapshot` fail-closed 須通過 ⟹ snapshot.schema.json **必須**容 null（否則 None-severity vuln 無法持久化）。 |

**核心定位**：本刀＝把 S3 已對 CVSS 數值做的「停止捏中點」**延伸到 severity 類別**。S3 修了數值面（cvss=None+evidence），漏了類別面（severity 仍 fabricate "medium"）。本刀補齊。

---

## 1. 範圍（in / out）

### 做（in）
1. **scanner 停止自鑄**（`vulnerability_scanner.py:148-156`）：`database_specific.severity` present 且 ∈ 4-enum → 用之；否則（缺鍵／不認得）→ `None`（不再 fallback "medium"）。
2. **model 容 None**（`models/vulnerability.py`）：`VulnerabilityEntry.severity: str → str | None`（＋註解）；`VulnerabilitySummaryEntry.severity: str → str | None`（衍生自 entry、一致）。
3. **schema 容 null**：
   - `snapshot.schema.json:81`（**fail-closed 強制**）：severity `{type:string, enum:[4]}` → `oneOf[4 const, null]`（比照同檔 confidence 樣式）。
   - `ast-raw.schema.json:191`（reference 文件 schema、無 code 強制但記錄同契約）：severity 加 null（doc 誠實一致）。
4. **存在性誠實 guard**（`vulnerability_renderer.format_summary_header`，**concept/5 軸審查補**）：header 的「有無漏洞」判斷現綁 `total_critical+high+medium+low`（`:105`）⟹ None-severity 漏洞不入 4 桶 → header 謊報「✅ 未偵測到已知漏洞」。**且此 header 同時餵 `scan_tool.py:53`（agent-facing MCP）與 `report_renderer.py:477`（人類報告）⟹ 是 agent 面誠實問題、非純人類面**。修：存在性判斷改用 `summary.entries`（已含全部漏洞含 None-severity），並由 entries 即席算「未分級」數加一個 part。**localized 在回傳字串內、零新 model 欄、零 schema、零 render_json 結構改、零前端**。

### 不做（out）
- **severity SignalPosition／membrane B-側投影**：severity ∈ OSV payload 非 Door 軸（§0）⟹ 不建 Signal。
- **summary 4-桶以外的呈現重設計／indeterminate 計數欄入持久化或 render_json schema**：屬獨立「人類面整膜」刀。本刀的 §1.4 guard 只在 `format_summary_header` 回傳字串內（顯示文字非 schema 契約），不加 model 欄、不改 update-report.schema/前端。
- **改 OSV 解析其他面**（CVSS 已於 S3 修畢）。
- **回填既有快照**（既有皆 string、無缺值資料）。

---

## 2. Spike 事實（2026-06-06 對真實碼，file:line 已驗）

| 層 | 檔案:line | 事實 |
|---|---|---|
| 自鑄點 | `vulnerability_scanner.py:149` `severity_str="medium" #default`／`:156` 不認得→"medium" | **兩處自鑄中點**＝本刀標的。 |
| model | `models/vulnerability.py:14` `severity: str`／`:46`(SummaryEntry) | 改 `str\|None`。 |
| membrane（payload） | `vulnerability_membrane.py:25` `"severity": entry.severity` | 直接 passthrough，None 安全；position 鍵在 evidence 非 severity ⟹ 不改。 |
| renderer | `vulnerability_renderer.py:73`(counts)／`:78`(sort None-safe)／`:86`(passthrough)／**`:105` header total 綁 4-桶** | counts/sort None-safe；但 **header `:105` 存在性綁 4-桶 total ⟹ None-severity 漏洞謊報「未偵測」**＝§1.4 標的（V6）。 |
| header 消費端（**agent＋人類**） | `scan_tool.py:53`(MCP agent-facing)／`report_renderer.py:477`(人類報告) | `format_summary_header` 雙面共用 ⟹ 謊報是 agent 面誠實問題、非純人類面。 |
| sort（scan_tool） | `scan_tool.py:57` `.get(v.severity,9)` | None-safe。 |
| serde | `snapshot_store.py:385` 序列化 `v.severity`／`:453` 反序列化 `v["severity"]` | None→null→None round-trip；`v["severity"]`（必有鍵）持久化 null 後讀回 None。✓ |
| schema-強制 | `snapshot.schema.json:81` enum 4 值（無 null） | **fail-closed 拒 null** ⟹ 必加 null（本刀關鍵耦合）。 |
| schema-doc | `ast-raw.schema.json:191` enum 4 值 | grep 證**無 code 引用驗證**（reference only）；加 null 為 doc 一致。 |
| 其他 emit | `analyze_pipeline.py:258`／`structure_serializer.py:55-62`／`report_renderer.py:378` `v.severity in (...)` | 皆 None-safe passthrough／比對（None→False，不 crash）。無 severity-enum schema 強制這些面。 |
| 既有測 | `test_vulnerability_scanner.py`/`_emit`/`_membrane`/`test_snapshot_contract.py` | 皆用 recognized severity（"high"/"medium"）⟹ 新 None 路徑為**純加法、不破舊斷言**。 |

**spike 結論**：自鑄點 2 處（scanner）；唯一 fail-closed 耦合＝snapshot.schema.json 須容 null；其餘消費端（renderer/serde/membrane/emit）**已 None-safe**。本刀＝scanner 去自鑄＋model/schema 容 null＋characterization 釘 None-safe，**零新型別、零 membrane B-側**。

---

## 3. 設計（exact code；落點標注）

### 3.1 scanner 去自鑄 `vulnerability_scanner.py:148-156`
```python
# Get severity — OSV 給的外部裁決類別；OSV 沒給/不認得 → None（不自鑄中點，fact-finder）。
severity_str: str | None = None
db_specific = vuln.get("database_specific", {})
if isinstance(db_specific, dict) and "severity" in db_specific:
    candidate = db_specific["severity"].lower()
    if candidate in ("critical", "high", "medium", "low"):
        severity_str = candidate
# 不認得/缺鍵 → severity_str 保持 None（誠實缺席）
```
> 行為改變：原本「缺/不認得 → medium」、現在「缺/不認得 → None」。recognized 值路徑不變（regression-safe）。

### 3.2 model `models/vulnerability.py`
```python
severity: str | None  # "critical"|"high"|"low"|"medium"|None（OSV 未給類別＝誠實缺席，不捏中點）
# VulnerabilitySummaryEntry.severity 同步 str | None（衍生自 entry）
```

### 3.3 schema `snapshot.schema.json:81`（fail-closed、比照 confidence oneOf 樣式）
```json
"severity": { "oneOf": [
  { "const": "critical" }, { "const": "high" },
  { "const": "medium" }, { "const": "low" },
  { "type": "null", "description": "OSV 未給 severity 類別（誠實缺席，不捏中點）" }
] },
```

### 3.4 schema `ast-raw.schema.json:191`（reference doc、additive）
```json
"severity": { "oneOf": [
  { "const": "critical" }, { "const": "high" },
  { "const": "medium" }, { "const": "low" }, { "type": "null" }
] },
```

### 3.5 存在性誠實 guard `vulnerability_renderer.py`
counts 迴圈（`:71-73`）加 None 守衛（避免 `counts[None]` 雜散鍵）：
```python
counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
for v in vulnerabilities:
    if v.severity in counts:           # None-severity 不入 4 桶（誠實）
        counts[v.severity] += 1
```
`format_summary_header`（`:103-116`）存在性判斷改綁 entries、加未分級 part：
```python
def format_summary_header(self, summary: VulnerabilitySummary) -> str:
    if not summary.entries:            # 存在性看 entries（含 None-severity），非 4-桶 total
        return "✅ 未偵測到已知漏洞"
    parts = []
    high_count = summary.total_critical + summary.total_high
    if high_count > 0:
        parts.append(f"🔴 {high_count} 個高風險")
    if summary.total_medium > 0:
        parts.append(f"🟠 {summary.total_medium} 個中風險")
    if summary.total_low > 0:
        parts.append(f"{summary.total_low} 個低風險")
    indeterminate = sum(1 for e in summary.entries if e.severity is None)
    if indeterminate > 0:
        parts.append(f"❓ {indeterminate} 個未分級嚴重度")
    return " | ".join(parts)
```
> entries 已含全部漏洞（`build_vulnerability_summary:76-88` append 所有 sorted_vulns）⟹ `summary.entries` 為存在性單一真相；未分級數即席由 entries severity 算（零新 model 欄）。

---

## 4. 不變量清單

| # | 不變量 | 強制處 | 理論 |
|---|---|---|---|
| V1 | OSV `database_specific.severity` 缺/不認得 → `severity is None`（不自鑄 medium） | scanner ＋ unit | fact-finder |
| V2 | OSV 給 recognized severity → 保真該值（regression） | scanner ＋ unit | 保真 |
| V3 | None-severity entry serde round-trip 保 None；經 `_write_snapshot` fail-closed **通過**（schema 容 null） | serde ＋ schema ＋ characterization | 寫嚴讀寬/Finding A |
| V4 | renderer 對 None-severity **不 crash**：不入 4 桶（None 守衛）、排最後、仍列於 entries | renderer characterization | 誠實 |
| V5 | membrane payload severity 容 None（passthrough）；position 仍鍵於 evidence（不因 severity None 改變） | membrane characterization | severity ∈ payload 非軸 |
| V6 | None-severity 漏洞**不得從「有無漏洞」結論消失**：`format_summary_header` 對「僅 None-severity 漏洞」回非「未偵測」字串（含未分級數）；存在性綁 entries | renderer guard ＋ unit | fact-finder（agent＋人類面皆不謊報） |

> **無新型別、無 severity SignalPosition、無 NoisePosition 新分支**（None 的 indeterminate 語義已由既有「無 evidence→NoisePosition(indeterminate)」在 position 層提供；severity=None 在 payload 層表達無類別）。

---

## 5. 測試策略

- **scanner unit**（`test_vulnerability_scanner.py` 擴充）：
  - V1：OSV `database_specific` 無 severity 鍵 → entry.severity is None。
  - V1：`database_specific.severity="UNKNOWN_LEVEL"`（不認得）→ None。
  - V2：`database_specific.severity="HIGH"` → "high"（pin 既有行為）。
- **serde/schema**（`test_snapshot_store_roundtrip.py` 或 `test_snapshot_contract.py` 擴充）：V3 None-severity entry create_snapshot→get_snapshot round-trip 保 None＋fail-closed 不拒。
- **renderer characterization**（`vulnerability_renderer` 測）：V4 含一筆 None-severity vuln → `build_vulnerability_summary` 不炸；該筆在 entries、4 桶 total 不含它、排最後。
- **V6 存在性 guard**（`vulnerability_renderer` 測）：①僅一筆 None-severity 漏洞 → `format_summary_header` **非** "✅ 未偵測到已知漏洞"、含「未分級」字樣；②零漏洞 → 仍回 "✅ 未偵測"；③混合（high＋None）→ header 同列高風險與未分級數。
- **membrane characterization**（`test_vulnerability_membrane.py` 擴充）：V5 None-severity entry → `verdict_element().to_json()` payload severity is None；有 evidence→RelayedVerdict、無 evidence→NoisePosition（與 severity None 無關）。
- **回歸**：vulnerability 既有測（emit 排序/dedup/membrane）全綠；全測零回歸。
- **執行**：`cd the_door && PYTHONUTF8=1 python -m pytest -q`。基線 1582＋新測。

---

## 6. spec 完成後 7 點審查（第 4 點 grep 已驗）

1. **單一職責**：scanner 去自鑄；model/schema 容 null；其餘釘現狀。✓
2. **介面最小**：scanner 改 ~5 行、model 2 欄型別、schema 2 處 enum→oneOf+null。無新函式/型別。✓
3. **可測**：V1-V5 皆可斷言（scanner 純解析、serde round-trip、renderer/membrane 純投影）。✓
4. **API grep 驗真**（§2）：scanner:149/156✓／model:14,46✓／membrane:25✓／renderer:73,78,86✓／serde:385,453✓／snapshot.schema:81✓／ast-raw.schema:191✓（無 code 引用＝reference）／其他 emit 皆 None-safe✓。**無虛構**。
5. **錯誤路徑**：None severity → renderer 不入桶（非錯、誠實）；schema null 合法；deserialize `v["severity"]`=null→None（不炸）。
6. **向後相容**：純加法；severity nullable＝additive；既有 string severity 全部仍合法、既有測不破（皆 recognized 值）。**有意契約變更＝snapshot/ast-raw schema severity 容 null＋scanner 缺值→None**＝characterization 見證。
7. **文件**：結構化、exact code、file:line、零佔位符；plan 引本 spec §3.x。

---

## 7. 連貫律回驗

- **承 S3/S4**：S3 殺 CVSS 數值捏中點；S4 殺 confidence `.get(...,"medium")`；本刀殺 severity 類別捏中點＝同一「A-側閉集缺值誠實化」通則第三次套用，**零新機制**。
- **與三主軸正交**：severity ∈ vulnerability payload（OSV 外部裁決），與 confidence/scope/provenance（Door 自有軸）不同縫。
- **不預啟人類面**：renderer None-safe 已足；「summary 顯示 indeterminate severity」屬獨立人類面整膜刀（碰前端/呈現），本刀 out。

---

## 8. 交付物（plan 拆 task）

1. scanner 去自鑄＋model 容 None（V1/V2）＋unit。
2. schema 容 null（snapshot fail-closed＋ast-raw doc）＋serde round-trip characterization（V3）。
3. renderer None 守衛＋存在性 guard（V4/V6）＋membrane characterization（V5）。
4. gate：全測零回歸；grep 確認無 severity SignalPosition、無 model 新欄、無前端/update-report.schema 改動。

**驗收**：缺值→None（V1）、recognized 保真（V2）、None round-trip＋fail-closed 通過（V3）、renderer None-safe（V4）、membrane payload None（V5）、存在性不謊報（V6）、全測零回歸。
