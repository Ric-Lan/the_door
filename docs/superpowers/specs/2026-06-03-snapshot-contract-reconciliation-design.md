# Snapshot 持久化契約對賬（Finding A）— 設計

> **日期**：2026-06-03　**狀態**：設計核准、待寫 plan
> **刀序**：重構 backlog 之外的「契約誠實化」第一刀（承 2026-06-03 探查的 Finding A）
> **目標檔**：`the_door/schemas/snapshot.schema.json`、`the_door/src/the_door/core/diff/snapshot_store.py`
> **設計依據**：本 session 對真實程式碼跑的可行性 spike（§4，已跑、四項全綠，腳本用完即棄、零版控污染）

---

## 0. 一頁摘要

`schemas/snapshot.schema.json` 宣稱是 snapshot 落盤格式的契約，但：①全 repo 程式碼**從不載入它**（孤兒）；②它**缺 4 個程式實際會寫的欄位**（過時）；③它沒設 `additionalProperties: false`（太鬆，就算接進去也抓不到漂移）。真正的契約只活在 `SnapshotStore._serialize_snapshot` 的命令式碼裡——對同一件事，系統有兩個會互相矛盾的說法。

本刀把契約收斂成**單一、誠實、被強制**的真相：
1. **修 schema**：補齊缺的 4 欄、收緊為 strict（`additionalProperties: false`）。精確 delta 見 §5.1，已由 §4 spike 證明。
2. **落盤時強制**：在 `snapshot_store` 的寫入口加 `jsonschema.validate`（**比照既有 `doubt_store` 的 persist 校驗**）；讀取路徑**刻意不動**（舊 snapshot 向後相容、不被擋）。
3. **雙向 drift guard**：一道測試斷言「schema 宣告的欄位集 == serialize 實際吐出的欄位集」（**雙射**，兩向都比），外加 strict 驗證 + round-trip + 負向。
4. **合規稽核（on-demand）**：一個唯讀方法，掃磁碟既有 snapshot、列出不合規者——把「歷史資料合不合規」從**靜默未知**變成**有清單**。

這刀是 [error-code catalog 補登 + drift guard](../../refactoring/2026-05-31-refactoring-backlog.md)（2026-06-03，commit `12a5e48`）的同型手術：把「該只有一份的契約」對賬、用測試釘死、防止再漂移。

---

## 1. 背景與動機

### 1.1 已驗證的問題事實（§4 spike + 直接讀碼，非推測）

| 事實 | 證據 |
|---|---|
| `snapshot.schema.json` 程式碼零引用（只被設計文件引用） | `git grep snapshot.schema -- ':!*.json'` → 命中 `.kiro/specs/*`、`docs/*`，**`src/`、`tests/` 零命中** |
| schema 缺頂層 `codebase_path` | `_serialize_snapshot` line 332 恆吐 `codebase_path`；schema `properties` 無此鍵 |
| schema 缺 L1 entry 的 `trigger_description`/`source_nodes`/`confidence_reason` | `_serialize_snapshot` line 300–305 條件式吐出；schema l1 entry `properties` 只列 4 欄 |
| schema 太鬆（無 `additionalProperties:false`），漏的欄位也不會被擋 | schema 各 object 層級未設 `additionalProperties` → 預設 `true` |
| 對照組 `doubt_store` 做對了：載 schema 並 `jsonschema.validate` | `doubt_store.py` line 15 `import jsonschema`、line 38–48 快取載入、line 504–505 persist 前驗證、line 126/518 load 後驗證 |
| `jsonschema` 已是現有依賴（非新增） | `doubt_store.py` line 15 已 import；`Draft202012Validator` 已在用 |
| `schemas/` 非打包資源（dev/design-time 契約） | `pyproject.toml`/`MANIFEST.in` 未提及 `schemas` |

### 1.2 這「不是」什麼

- **不是**改 snapshot 的資料語意或欄位（一欄不增不減於 `VersionSnapshot`）。
- **不是**擴張格式表達力（見 §2.3 通用守門）。
- **不是**動 resolver（Finding B-1）或 doubt FSM（Finding B-2）——各自獨立刀。

### 1.3 北極星對齊

- 可讀性/維護性優先：✅ 契約單一真相、可稽核。
- 結構先行、行為不變：✅ 落盤位元組不變（schema 只補既有欄位、validate 不改 data）。
- 證據驅動：✅ schema delta、強制點行號、可行性全部來自 §4 已跑的 spike 與直接讀碼。
- 抽象要償還成本：✅ 沿用 `doubt_store` 既有模式（模組級函式 + validate），**不引入新抽象層**。

---

## 2. 範圍 / 非目標 / 護欄

### 2.1 範圍內
- 修 `schemas/snapshot.schema.json`（§5.1 精確 delta）。
- `snapshot_store.py`：加 schema 載入器 + 抽 `_write_snapshot` 單一落盤口（內含 persist 校驗）。
- 新增測試（§6）：strict 驗證 + 雙向欄位雙射 + round-trip + 負向 + 稽核工具單元測試。
- 新增唯讀合規稽核方法（§5.3）。

### 2.2 非目標（明文排除）
- **不動讀取路徑**：`get_snapshot`/`_load_all_snapshots`/`list_analyzed_versions`/`resolve_baseline` 等**不加校驗**（向後相容；理由見 §7.2）。
- 不抽 `BaselineResolver`（Finding B-1）、不改 doubt FSM（Finding B-2）。
- 不把稽核做成 CLI/MCP 指令（可為後續微任務；本刀只做引擎方法）。
- 不碰 `core/datamodel/`、不改 `VersionSnapshot` 資料模型。
- 不處理「跨欄語意不變式」（如 `source_node_count == len(source_nodes)`）——超出 jsonschema 表達力，見 §7.4、§10。

### 2.3 ⚠️ 通用守門條款（The Door 是通用型基礎建設、非特化）
snapshot 落盤格式**維持語言／廠商中立**：存的是 functional feature（label/description/confidence/source_nodes 等），**禁止**摻入任一特定語言的 AST 細節，或任一託管平台廠商（GitHub/GitLab…）專屬欄位。本刀只對賬**既有的通用格式**，不擴張它。見 [[feedback_universal_translation_no_chasm]]。

### 2.4 護欄（越線即否決）
- schema 只「補既有 serialize 已吐欄位 + 收緊」，**不得**新增 serialize 不吐的欄位（否則造幽靈欄位，違背本刀目的）。
- `additionalProperties: false` 是本刀的防線核心，**任何時候不得為了讓測試/寫入通過而改回 `true`**（見 §7.3 fail-closed 逃生閥）。
- 落盤校驗失敗時**讓它拋**（fail-closed），不得 try/except 吞掉。

---

## 3. 理論依據（收貨後校準版：每條換到具體改動，邊界講清楚）

> 沿用本專案準則「理論當改善工具、非事後背書；換不到具體改動或過度設計就剔」。下表為與使用者兩輪「收貨檢驗」後的定版。

| 理論 | 操作性結論 | 對本 spec 的具體改動 | 邊界 / 注意 |
|---|---|---|---|
| **單射 vs 雙射（集合論）** | 原單向驗證只保證 `Implementation ⊆ Specification`，放任規格膨脹出幽靈欄位 | drift guard 升級為**雙向集合相等**（§6 測試 2）：schema 宣告欄位集 == serialize 吐出欄位集 | 雙射建立在**欄位名集合 + 型別一致**上，**非完全語意等價**；且必須定義在「**可吐欄位的聯集**（最大化 snapshot）」上，不可拿任一實例（serialize 有條件式吐出，見 §7.1） |
| **演進式架構的審計線索（Audit Trail）/ 技術債可視化** | 向後相容不該以犧牲透明度為代價；把「不知道」轉成「可量化清單」 | §5.3 唯讀合規稽核方法，列出磁碟上不合規的既有 snapshot | 這是**靜態、按需**的審計／lint，**不是** runtime「可觀測性(Observability)」（後者是連續、推斷內部狀態）；且**必須是 on-demand 工具、不可做成 CI 斷言**（驗的是 gitignored、機器專屬資料，做成 CI 必 flaky，見 §7.5） |
| **Fail-closed / 安全預設（Saltzer & Schroeder, "fail-safe defaults" = default deny）** | 遇模糊地帶最危險的是「隱式放水」；預設應拒絕 | `additionalProperties: false`（預設拒絕未知欄位）+ §7.3 逃生閥：撞表達力瓶頸就停下入 backlog、**絕不**放寬成 `true` | 要的是 **fail-closed/fail-fast**，**不是** fail-safe-as-degrade（火災門鎖那種「失敗即放行」）；`additionalProperties:true` 正是要避免的 **fail-open** 反模式 |
| **內聚 / DRY（Constantine-Yourdon；Martin）** | 同一職責收一處 | 抽 `_write_snapshot` 單一落盤口（§5.2），消除 `create_snapshot` 與 `patch_snapshot` 重複的 serialize+write | 順帶的小「變分明」：「snapshot 怎麼落盤」從此只有一個地方管 |

### 3.1 被剔除 / 收回尺寸的理論（紀錄，避免日後重提）
- **「完全結構等價(Structural Equivalence)」原版**：收回為「欄位名雙射 + 型別一致」。理由：jsonschema 表達不了跨欄語意不變式，宣稱「完全等價」是 overclaim。
- **「可觀測性(Observability)」**：收回為「靜態審計／技術債可視化」。理由：名實不符（我們是一次性靜態掃描，非 runtime 連續推斷）。
- **「Fail-Safe」字面引用**：修正為 **fail-closed / default-deny**。理由：Fail-Safe 常指「失敗即退回放行的安全態」，與本意相反。
- **「徹底根除任何漂移空間」總結宣言**：剔除原版 overclaim，改用 §10 校準版（明列未保證什麼）。

---

## 4. 可行性驗證事實（spike 已跑，四項全綠）

> 本 session 對**真實** `SnapshotStore._serialize_snapshot`/`_deserialize_snapshot` 與 §5.1 修正後 schema 跑的一次性 spike（腳本用完即棄、未 commit）。**跑兩個 fixture**：
> - **maximal/manual**：`trigger='manual'`、label 為字串、每個選填欄位都填值（踩亮 serialize 三個條件式分支 `trigger_description is not None` / `source_nodes` 非空 / `confidence_reason is not None`）。
> - **minimal/commit**：`trigger='commit'`、**`label=None`**、無選填 L1 欄、空集合、`vulnerability_db_freshness=None`（這是預設、最常見的寫入路徑）。

| 檢查 | maximal/manual | minimal/commit |
|---|---|---|
| (1) strict schema 驗證序列化輸出 | **PASS** | **PASS**（label=null） |
| (3) round-trip：`serialize(deserialize(data)) == data` | **True** | **True** |
| (2a) 頂層雙射：emitted keys == declared properties（兩向差集皆空） | **True**（聯集基準＝maximal） | — |
| (2b) L1-entry 雙射 | **True**（聯集基準＝maximal） | — |
| (4) 負向：塞入未知欄位 → strict schema 拋 `ValidationError` | **PASS（被擋）** | — |

**結論**：§5.1 的 schema delta **精確且完整**；雙射定義在「可吐欄位聯集（maximal）」上是 well-defined；strict 模式**確實會咬**；round-trip 對稱。`additionalProperties:false` 與既有 `if/then`（manual→require label）**可共存無衝突**。
> ⚠️ **審查中抓到並修正的 bug（已重驗）**：`label` 型別原寫成 `{type:"string"}`，但 commit-trigger snapshot 的 `label` 是 `None`（line 90-91 只在 manual 才自動生成、line 331 無條件吐 `label`）→ 會讓**所有 commit 寫入**驗證失敗。第一版 spike 只測 manual+字串 label 而漏掉。已改為 `{type:["string","null"]}` 並用 minimal/commit fixture 重驗通過。**這是「minimal/commit fixture」必須進測試（§6 測試 1/3）的直接理由**。

### 4.1 逐層欄位對賬（已驗，實作者無須重驗）

| 層級 | serialize 實際吐出 | 原 schema 狀態 | delta |
|---|---|---|---|
| 頂層 | …+ `codebase_path`；`label` 可為 `null`（commit） | 缺 `codebase_path`；`label` 誤標 `string`；無 strict | **加 `codebase_path`、`label`→`["string","null"]`、加 `additionalProperties:false`** |
| l1 entry | label/description/source_node_count/confidence + 選填 trigger_description/source_nodes/confidence_reason | 只列前 4；無 strict | **加 3 選填欄、加 `additionalProperties:false`** |
| l1_5 entry | label/responsibility/confidence | 已列三者 | **僅加 `additionalProperties:false`** |
| relation item | from_feature/to_feature/relation | 已列三者 | **僅加 `additionalProperties:false`** |
| vuln item | cve_id/package/version/severity/cvss/source | 已列六者 | **僅加 `additionalProperties:false`** |
| freshness | timestamp/mode/stale_warning | 已列三者 | **僅加 `additionalProperties:false`** |

---

## 5. 設計

### 5.1 修正後 schema（`schemas/snapshot.schema.json` 完整內容，逐字採用）

> 此即 §4 spike 驗證通過的 schema。實作者**逐字寫入**，不得增刪欄位（增 = 幽靈欄位、減 = 漏寫真實欄位，兩者皆違護欄）。

```json
{
  "title": "The Door Version Snapshot",
  "description": "A persisted record of L1/L1.5 analysis output at a specific point in time",
  "type": "object",
  "required": ["version_id", "timestamp", "trigger", "l1_snapshot", "analyzed_files"],
  "additionalProperties": false,
  "properties": {
    "version_id": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "trigger": { "type": "string", "enum": ["commit", "manual"] },
    "commit_hash": { "type": ["string", "null"] },
    "git_tags": { "type": "array", "items": { "type": "string" } },
    "label": { "type": ["string", "null"] },
    "codebase_path": { "type": ["string", "null"] },
    "l1_snapshot": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["label", "description", "source_node_count", "confidence"],
        "additionalProperties": false,
        "properties": {
          "label": { "type": "string" },
          "description": { "type": "string" },
          "source_node_count": { "type": "integer", "minimum": 0 },
          "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
          "trigger_description": { "type": ["string", "null"] },
          "source_nodes": { "type": "array", "items": { "type": "string" } },
          "confidence_reason": { "type": ["string", "null"] }
        }
      }
    },
    "analyzed_files": { "type": "array", "items": { "type": "string" } },
    "l1_5_snapshot": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["label", "responsibility"],
        "additionalProperties": false,
        "properties": {
          "label": { "type": "string" },
          "responsibility": { "type": "string" },
          "confidence": { "type": "string", "enum": ["high", "medium", "low"] }
        }
      }
    },
    "feature_relations_snapshot": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["from_feature", "to_feature", "relation"],
        "additionalProperties": false,
        "properties": {
          "from_feature": { "type": "string" },
          "to_feature": { "type": "string" },
          "relation": { "type": "string" }
        }
      }
    },
    "vulnerabilities_snapshot": {
      "type": "array",
      "default": [],
      "items": {
        "type": "object",
        "required": ["cve_id", "package", "version", "severity", "cvss", "source"],
        "additionalProperties": false,
        "properties": {
          "cve_id": { "type": "string" },
          "package": { "type": "string" },
          "version": { "type": "string" },
          "severity": { "type": "string", "enum": ["critical", "high", "medium", "low"] },
          "cvss": { "type": "number", "minimum": 0.0, "maximum": 10.0 },
          "source": { "type": "string" }
        }
      }
    },
    "vulnerability_db_freshness": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "properties": {
        "timestamp": { "type": "string", "format": "date-time" },
        "mode": { "type": "string", "enum": ["online", "offline"] },
        "stale_warning": { "type": ["string", "null"] }
      }
    }
  },
  "if": { "properties": { "trigger": { "const": "manual" } } },
  "then": { "required": ["label"] }
}
```

### 5.2 落盤時強制（mirror `doubt_store`，僅 persist）

**(a) schema 載入器**（逐字比照 `doubt_store.py` line 32–48 的模組級快取法）：
```python
# 模組頂部（snapshot_store.py 已 import json/logging；新增 jsonschema）
import jsonschema

# snapshot_store.py 位於 the_door/src/the_door/core/diff/，與 doubt_store.py
# (core/scope/) 同層深度，故 5 個 .parent 同樣指向內層 the_door/schemas。
_SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent.parent / "schemas"
_SNAPSHOT_SCHEMA_PATH = _SCHEMAS_DIR / "snapshot.schema.json"
_snapshot_schema: dict | None = None

def _load_snapshot_schema() -> dict:
    with open(_SNAPSHOT_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)

def _get_snapshot_schema() -> dict:
    global _snapshot_schema  # noqa: PLW0603
    if _snapshot_schema is None:
        _snapshot_schema = _load_snapshot_schema()
    return _snapshot_schema
```
> 已驗證：`doubt_store.py` line 32 用 `Path(__file__).parent.parent.parent.parent.parent / "schemas"`（5 個 `.parent`：scope→core→the_door→src→the_door(inner root)→/schemas）。`snapshot_store.py` 在 `core/diff/`，**與 `core/scope/` 同深度**，同一表達式成立。`Path` 已在 `snapshot_store.py` import（VersionSnapshot.codebase_path 用）。

**(b) 抽單一落盤口 `_write_snapshot`**：消除 `create_snapshot`(line 111–112) 與 `patch_snapshot`(line 248–250) 重複的 serialize+write，並在此處唯一校驗：
```python
def _write_snapshot(self, snapshot: VersionSnapshot) -> None:
    self._snapshots_dir.mkdir(parents=True, exist_ok=True)
    data = self._serialize_snapshot(snapshot)
    jsonschema.validate(data, _get_snapshot_schema(),
                        cls=jsonschema.Draft202012Validator)   # fail-closed
    file_path = self._snapshots_dir / f"{snapshot.version_id}.json"
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                         encoding="utf-8")
```
`create_snapshot` 與 `patch_snapshot` 改為呼叫 `self._write_snapshot(snap)`（取代各自的 serialize+write）。其餘行為（回傳值）不變。
> ⚠️ `mkdir` **收進 `_write_snapshot`**（取代 `create_snapshot` line 109 的 mkdir）：`create_snapshot` 原本有 mkdir、`patch_snapshot` 沒有（它假設目錄已存在）；集中進落盤口後兩者一致、`exist_ok=True` 對 patch 無害。`json.dumps(..., indent=2, ensure_ascii=False)` 與兩處原寫法（line 112、250）**參數一致**。

**(c) 讀取路徑不動**：`get_snapshot` 等**不加** validate（向後相容，§7.2）。

### 5.3 合規稽核（唯讀、on-demand）

`SnapshotStore` 新增唯讀方法（不在 persist/load 熱路徑、不進 CI 斷言）：
```python
def audit_conformance(self) -> list[dict]:
    """Read-only: validate every on-disk snapshot against the current schema.
    Returns a list of {version_id, file, error} for NON-conforming snapshots
    (empty list = all conform). Does NOT modify, reject, or delete anything."""
```
逐一讀 `_snapshots_dir/*.json` → `jsonschema.validate` → 收集失敗者的 `(version_id, 路徑, 錯誤訊息)`。把「歷史資料合不合規」從**靜默未知**轉成**可量化清單**（審計線索 / 技術債可視化）。
> 暴露成 CLI/MCP 指令屬後續微任務（§11），本刀只做引擎方法。

---

## 6. 測試計畫（新增 `the_door/tests/unit/core/diff/test_snapshot_contract.py`）

> 全部已由 §4 spike 證明可行。完整測試碼於 plan 階段給出；此處定義**意圖與所釘不變量**，消除歧義。

1. **`test_snapshots_validate_against_schema`**（strict 驗證，**兩個 fixture 都要**）
   - **maximal/manual**（每選填欄位皆填）**與 minimal/commit**（`trigger='commit'`、`label=None`、無選填 L1 欄、空集合、freshness=None）兩者 → `_serialize_snapshot` → `jsonschema.validate(..., Draft202012Validator)` 皆須通過。
   - 釘：schema 涵蓋程式能吐的所有欄位 + 型別正確，**且涵蓋 commit/label=null 這條最常見路徑**（§4 抓到的 bug 類別的回歸守門）。

2. **`test_schema_serialize_field_bijection`**（雙向欄位雙射 = 核心 drift guard）
   - 對**每個設了 `additionalProperties:false` 的 object 層級**（頂層 / l1-entry / l1_5-entry / relation-item / vuln-item / freshness），斷言 `schema 該層 properties 的鍵集 == 最大化 snapshot 該層實際 key 集`（兩向差集皆空）。
   - 釘：①程式加欄位忘改 schema → strict 驗證會在既有寫 snapshot 測試紅；②schema 宣告了 serialize 不吐的幽靈欄位 → 此測試紅。**兩個方向都守住**。

3. **`test_snapshot_round_trip_equivalence`**（序列化對稱，**兩個 fixture 都要**）
   - 對 maximal/manual 與 minimal/commit 皆斷言 `serialize(deserialize(serialize(x))) == serialize(x)`。
   - 釘：serialize/deserialize 不對稱漂移（含 label=null、選填欄位缺席的路徑）。

4. **`test_strict_schema_rejects_unknown_field`**（負向 / fail-closed 證明）
   - 在合法序列化輸出加一個未知欄位 → `jsonschema.validate` 須拋 `ValidationError`。
   - 釘：`additionalProperties:false` 真的咬。

5. **`test_audit_conformance_reports_nonconforming`**（稽核工具單元測試）
   - 在臨時 `_snapshots_dir` 放一個合規 + 一個不合規（含未知欄位）snapshot 檔 → `audit_conformance()` 須**只**回報那個不合規者。
   - 釘：稽核邏輯正確。**注意：測的是工具邏輯（用 fixture 檔），不是對機器上真實 `.the-door/` 資料下斷言**（§7.5）。

6. **全套件零回歸**：既有寫 snapshot 的測試會自動經過新的 persist 校驗；不得有新 fail/error。

---

## 7. 注意事項與陷阱（實作者必讀）

### 7.1 serialize 是條件式吐欄位 → 雙射定義在「聯集」上
`_serialize_snapshot` line 300–305：`trigger_description`/`source_nodes`/`confidence_reason` 只在有值時才寫入 entry。故「serialize 吐出的 key 集」**隨實例變動**。測試 2 的雙射**必須**用「最大化 snapshot（全選填都填）」當基準（= 可吐 key 的聯集），不可拿最小或任意實例，否則雙射 ill-defined、會誤紅。

### 7.2 為何讀取路徑不加校驗（向後相容）
`doubt_store` 在 load 時也驗、失敗當「corrupted、skip+warn」。對 snapshot **不採此法**：snapshot 是歷史時間軸，skip 一個 = 丟失歷史。既有 `.the-door/snapshots/` 的舊檔多半已合規（因新 schema = 現行 serialize 輸出），但不保證；strict schema 套到 load 可能擋下更舊版本寫的檔。故 load 路徑**維持現狀**（僅 `json.JSONDecodeError` 容錯），合規與否改由 §5.3 稽核**主動**回報，而非在 load 被動爆。

### 7.3 fail-closed 逃生閥（語意不妥協）
若實作期發現「serialize 吐的某結構，strict schema 乾淨表達不了」：**停下、surface、記 backlog**，**絕不**把該層改回 `additionalProperties:true` 來讓它過——那等於把剛堵的洞重新挖開（fail-open / 語意降級）。逃生閥永遠導向「攤開複雜度」，不導向「靜默放水」。

### 7.4 jsonschema 表達力的邊界（本刀不處理、明列）
本刀的契約是**結構性**（欄位名 + 型別 + required + 未知欄位拒絕）。**跨欄語意不變式**（如 `source_node_count == len(source_nodes)`、`trigger=="manual" → label 非空` 已用 `if/then` 表達但 `source_node_count` 一致性沒有）**不在** jsonschema 能力內，本刀**不宣稱**覆蓋（見 §10）。這類不變式若要守，是另一道（dataclass `__post_init__` 或 property test），非本刀。

### 7.5 稽核不可做成 CI 斷言
§5.3 稽核驗的是磁碟上 `.the-door/snapshots/`——gitignored、每台機器/worktree 不同、隨時生滅。**做成 CI 測試＝對機器專屬資料下斷言＝必 flaky、不可攜**。故它是**按需呼叫的工具**；CI 只測它的**邏輯**（測試 5，用 fixture 檔）。

### 7.6 strict 化會「啟用」原 schema 既有的 enum 約束（已知、可接受）
原 schema 已有 enum 約束：`trigger`∈{commit,manual}、l1/l1_5 entry 的 `confidence`∈{high,medium,low}、vuln `severity`∈{critical,high,medium,low}、freshness `mode`∈{online,offline}。這些**不是本刀新增**，但因 schema 過去是孤兒、從未被執行，等於從未生效。本刀接上 persist 校驗後，它們**首次被強制**——任何 code path 若吐出 enum 外的值，落盤即 `ValidationError`。這對「契約誠實」是正確的（值本就該在 enum 內），且既有全套件（§6 測試 6）會立刻揭露是否有違規路徑。**若實作時發現某既有路徑確實吐 enum 外的值**：依 §7.3 逃生閥——停下、surface、評估是「碼該修」還是「enum 該放寬」，**不可**為了過關靜默拿掉 enum。

### 7.7 `label=null` 是合法值（commit-trigger 的常態）
`label` 型別為 `["string","null"]`：commit snapshot 的 label 為 `None`（line 90-91 僅 manual 自動生成），serialize line 331 無條件吐 `label`。strict schema **必須**允許 null，否則 commit 寫入全爆（§4 已抓修）。`if/then`（manual→required label）只檢查 key 存在（label key 恆存在），不檢查非空，故與 `["string","null"]` 不衝突。

### 7.8 jsonschema 已是依賴、`Draft202012Validator` 已在用
`doubt_store.py` line 15/126/505/518 已 import 並使用 `jsonschema.Draft202012Validator`。本刀**零新依賴**。schema 用了 `if/then`（Draft 2019-09+）與 `format: date-time`，`Draft202012Validator` 均支援（§4 spike 已實證通過）。

---

## 8. 引用紀錄

**學術 / 原則**
- Saltzer, J. & Schroeder, M.（1975）"The Protection of Information in Computer Systems" — **fail-safe defaults（預設拒絕 / default deny）**：本刀 `additionalProperties:false` + fail-closed 逃生閥（§3、§7.3）的錨點。
- 集合論「單射 vs 雙射」：drift guard 從單向（`Impl ⊆ Spec`）升級為雙向集合相等（§3、§6 測試 2）。
- Constantine & Yourdon（內聚光譜）；R. Martin（SRP/變更理由、DRY）：抽 `_write_snapshot` 單一落盤口（§5.2）。
- 演進式架構（Evolutionary Architecture）的 audit trail / 技術債可視化：唯讀合規稽核（§5.3）。
- Bertrand Meyer, Design by Contract — **收回為測試期 + persist 期校驗**（非完整 DbC 前後置條件框架；本刀只取「契約須被自動強制」這層）。

**專案內部前例 / 交叉參照**
- 同型前例：error-code catalog 補登 + drift-guard（backlog `12a5e48`，2026-06-03）——「該只有一份的契約對賬 + 測試釘死」。
- 強制模式來源：`the_door/src/the_door/core/scope/doubt_store.py`（schema 載入 38–48、persist 校驗 504–505）。
- 通用守門：[[feedback_universal_translation_no_chasm]]、[[feedback_refactoring_two_axes]]（「變分明」加法軸）。
- schema 被設計文件引用處：`.kiro/specs/diff-engine/*`、`.kiro/specs/vulnerability-layer/*`、`docs/superpowers/specs/2026-05-31-api-handlers-split-design.md`。

---

## 9. 驗收判準

實作完成須全數成立：
1. `schemas/snapshot.schema.json` == §5.1 內容（含 `codebase_path` + 3 個 L1 選填欄 + 6 處 `additionalProperties:false`）。
2. `snapshot_store` 經 `_write_snapshot` 唯一落盤口，`create_snapshot`/`patch_snapshot` 皆改用之；落盤時 `jsonschema.validate`（fail-closed，失敗即拋）。
3. **讀取路徑零變更**（§7.2）。
4. §6 測試 1–5 全綠；既有全套件零回歸（基準：當下 main 實際數字）。
5. `audit_conformance()` 為唯讀、不修改/拒絕/刪除任何 snapshot；**不在 CI 對真實 `.the-door/` 資料斷言**。
6. `git diff` 改動面僅：`schemas/snapshot.schema.json`、`core/diff/snapshot_store.py`、新測試檔。無其他 `.py` 被改、`core/datamodel/` 未動、`VersionSnapshot` 模型未動。
7. 零新依賴（`jsonschema` 沿用既有）。

---

## 10. 校準版收束宣言（取代原 overclaim）

> 這次補強把 snapshot 契約從**單向驗證**提升為**欄位名雙射 + 型別一致**，並為三類遺漏各設一道**強制可見**的出口：規格膨脹（幽靈欄位）→ 測試紅；歷史資料合規未知 → 稽核清單；工具表達力撞牆 → 停下入 backlog（fail-closed）。
>
> **它不宣稱消除所有漂移**——跨欄語意不變式（如計數一致性）仍在 jsonschema 表達力之外、不在本刀範圍。它宣稱的是：**這三類漂移無法再「靜默」發生**（要嘛測試紅、要嘛清單列出、要嘛流程停下）。

---

## 11. Out of scope / 後續
- Finding B-1（抽 `BaselineResolver`）、B-2（doubt FSM 顯式轉移表）——各自獨立刀。
- 把 `audit_conformance()` 暴露成 CLI/MCP 指令（微任務）。
- 跨欄語意不變式守護（dataclass `__post_init__` / property test）——若日後有需求。
- 其餘 `schemas/*.json` 是否也有同型孤兒/漂移——可另起一次稽核（本刀只處理 snapshot）。
