# packaging-schemas-fix spec+plan：pip 裝起來找不到 JSON schemas（v1.7.1）

> 實機測試 v1.7.0（非-editable pip install）時 `snapshot_write` 報
> `[Errno 2] No such file or directory: <python>/Lib/schemas/snapshot.schema.json`。
> 根因＝**schemas 沒進 wheel ＋ runtime 路徑寫死 dev 佈局**。本刀修正並發 v1.7.1（patch）。

---

## 0. spike（已對真實碼/裝起來的套件驗，事實寫入）

| 事實 | 來源 | 影響 |
|---|---|---|
| 4 個生產模組用 `_SCHEMAS_DIR = Path(__file__).parent×5 / "schemas"` | `core/diff/snapshot_store.py:41`、`core/scope/doubt_store.py:33`、`core/scope/scope_verifier.py:32`、`core/validation/schema_check.py:13` | dev 佈局（`src/the_door/...`）×5 剛好到 `the_door/`；裝起來（`site-packages/the_door/...`，少 `src/` 一層）×5 overshoot 到 `<python>/Lib/` → 找不到 |
| schemas 放在套件**外**（`the_door/schemas/`，非 `src/the_door/` 內）| `ls the_door/schemas/`（11 檔） | `[tool.setuptools.packages.find] where=["src"]` 只打包 `src/the_door/` → schemas 整批被排除、不進 wheel |
| 裝起來的 `site-packages/the_door/` **無 schemas/** | 實測 | 證實 schemas 沒進 wheel（雙重病灶之二） |
| pyproject **無** package-data／MANIFEST | `pyproject.toml`（只有 `packages.find where=["src"]`） | 需新增 package-data 才會打包 schemas |
| requires-python `>=3.10` | `pyproject.toml` | `importlib.resources.files()`（3.9+）可用 |
| 為何 pytest 沒抓到 | pytest `pythonpath=["src"]` 跑源碼樹；過去都用 `pip install -e`（editable＝dev 佈局，path 算得對、檔也在） | 單元測對源碼樹永遠綠；**唯有非-editable install 才暴露**＝需新增「對齊 importlib.resources 解析」的測來釘樁 |
| 11 個 schema | ast-raw / diff-result / doubt-record / l1-5-output / l1-output / l2-output / narrative / scope-definition / snapshot / timeline-result / **update-report** | 全部一起搬 |
| Python 測 2 處引用 schema 路徑 | `tests/unit/core/pipeline/test_risk_flag_membrane.py:24`（update-report）、`tests/unit/core/scope/test_doubt_membrane_parity.py:8`（doubt-record），皆 `parents[4]/"schemas"` | 搬檔後 `parents[4]/"schemas"` 失效 → 改成 robust 解析 |
| JS 測 1 處 | `viewer/tests/membrane-vocabulary.test.js:30` `'../../../../the_door/schemas'`（＋:27 註解「schema 不在 src 下」） | 搬檔後改 `'../../../../the_door/src/the_door/schemas'`＋更新註解 |

### 根因裁定（不是只補 package-data，要連路徑一起修）
- 光補 package-data（讓 schemas 進 wheel）→ 路徑仍 `.parent×5` overshoot → 還是找不到。
- 光改路徑（`.parent×3`）→ schemas 仍在套件外、沒進 wheel → 還是找不到。
- ⟹ **兩個都要修**：①schemas 搬進套件 `src/the_door/schemas/`；②路徑改 `importlib.resources.files("the_door")/"schemas"`（不再數 parent 層數＝根除「數錯層」這類 bug）；③pyproject 加 package-data 把 `schemas/*.json` 打包。

---

## 1. 目標 / 非目標
**目標**：讓非-editable `pip install` 後，所有 schema 載入（snapshot_write／validate／doubt／scope）都能找到 schemas，並有單元測釘住「schemas 經 `importlib.resources` 可解析」防再退化。

**非目標**：
- ❌ 不改任何 schema 內容（純搬位置）→ 契約版號不動。
- ❌ 不改 schema 驗證邏輯（只改「去哪載」）。
- ❌ 不碰 gate hooks（stdlib、不載 schema，無關）。

---

## 2. 設計

### 2.1 搬位置（git mv，保留歷史）
`the_door/schemas/*.json`（11 檔）→ `the_door/src/the_door/schemas/*.json`。

### 2.2 生產 4 模組：robust 解析
**前置 audit（審查 warning）**：改 Traversable 前，grep 4 模組內 `_SCHEMAS_DIR`／`*_SCHEMA_PATH`
的**每一處用法**，確認只有 `.open()`／`/`（join）；若有 `.exists()`／`os.path.*`／`str()`／`glob()`／
builtin `open(path)` 等 Path-only 操作，一併轉成 Traversable-safe（`files()` 回傳的 Traversable 對
一般安裝套件雖是 `Path` 子類、但不可假設——只用 Traversable 保證的 `.open()`/`/`/`.read_text()`/`.is_file()`）。

每處 `_SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent.parent / "schemas"` →
```python
from importlib.resources import files
_SCHEMAS_DIR = files("the_door") / "schemas"
```
並把 `open(_X_SCHEMA_PATH ...)` → `_X_SCHEMA_PATH.open(...)`（Traversable 用 `.open()`，不能用 builtin `open()`）。
- `snapshot_store.py:48`、`doubt_store.py:41`、`scope_verifier.py:38` 已是 `with open(path, encoding="utf-8")` → 改 `with path.open(encoding="utf-8")`。
- `schema_check.py:23-28` 三處 `with open(path)`（無 encoding）→ `with path.open(encoding="utf-8")`。

> `files("the_door")` 在 dev（`pythonpath=src`）→ `src/the_door/`；裝起來 → `site-packages/the_door/`。兩者 `/schemas` 都正確（搬檔＋package-data 後）。不再依賴 module 相對層數。

### 2.3 pyproject：打包 schemas（＋sdist 涵蓋）
```toml
[tool.setuptools.package-data]
the_door = ["schemas/*.json"]
```
（`where=["src"]` 下，key `the_door` 對應 `src/the_door/`，glob `schemas/*.json` 納入 wheel。）
＋新增 `the_door/MANIFEST.in`：`recursive-include src/the_door/schemas *.json`（涵蓋 sdist 路徑，審查 suggestion）。

### 2.4 測試對齊（2 py + 1 js）
- 2 個 py 測：`Path(__file__)...parents[4]/"schemas"/X` → `files("the_door")/"schemas"/X`（與生產同源、robust）。`.read_text(encoding="utf-8")` Traversable 支援。
- JS 測：路徑字串 `'../../../../the_door/schemas'` → `'../../../../the_door/src/the_door/schemas'`；:27 註解「schema 不在 src 下」→「schema 在 src/the_door/schemas 下」。

### 2.5 防退化測（新）
新增 `tests/unit/test_schema_packaging.py`：
- **P-1（路徑解析）**：對 11 個 schema 逐一斷言 `(files("the_door")/"schemas"/name)` `.is_file()` 且
  `json.loads(.read_text())` 不拋（合法 JSON）。搬檔前 dev 即紅（`files("the_door")`＝`src/the_door`，其下無 schemas）；搬檔後綠。
  - 🔴 **誠實邊界（審查 warning）**：P-1 在 dev 跑＝只釘**路徑解析**，**驗不到「wheel 是否真的含 schemas」**（原 bug 真因之二）。
- **P-2（打包設定釘樁）**：讀 `pyproject.toml` 斷言 `[tool.setuptools.package-data]` 的 `the_door` 含
  `"schemas/*.json"`（純文字/解析斷言）＋ `MANIFEST.in` 含 `src/the_door/schemas`。防 package-data 設定被靜默移除。
- **wheel 真實內容**由 §4 T6（**強制發版閘門、非可選**）以 install 後 `site-packages/the_door/schemas/` 存在 + snapshot_write 成功來保證。

---

## 3. 測試（plan 層）
- P-1（新）`test_schema_packaging.py`：11 schema 皆 `importlib.resources` 可解析＋合法 JSON（路徑解析釘樁）。
- P-2（新）同檔：pyproject `package-data` 含 `schemas/*.json`＋`MANIFEST.in` 含 schemas（打包設定釘樁）。
- 回歸：既有 schema 驗證測全綠——`test_snapshot_store*`、`test_doubt*`、`test_scope*`、`test_schema_check*`、`test_risk_flag_membrane`、`test_doubt_membrane_parity`（後二者改路徑後仍綠）。
- JS：`membrane-vocabulary.test.js` 改路徑後 viewer `npm test` 0 red。
- **裝起來驗（強制閘門，非可選；T6a）**：rebuild wheel → `pip install` → 確認 `site-packages/the_door/schemas/`（11 檔）存在 → `snapshot_write` 不再報 schema 錯（接續 v1.7.0 解析）＝唯一能保證 wheel 真含 schemas 的關。**此關屬「本地修好驗證」，不含 tag/push（發版 v1.7.1 ＝ T6b，待使用者明示）。**

## 4. Task 拆解（inline TDD）
- **T0** 寫 P-1＋P-2（red：dev 下 `src/the_door/schemas` 不存在；package-data 未設）。
- **T1** `git mv` 11 schema 進 `src/the_door/schemas/`（P-1 轉綠）。
- **T2** **先 audit** 4 模組內 `_SCHEMAS_DIR`/`*_SCHEMA_PATH` 全用法（確認只 `.open()`/`/`）→ 改 importlib.resources＋`.open()`；跑 schema 驗證相關測全綠。
- **T3** pyproject 加 package-data ＋ 新增 `MANIFEST.in`（P-2 轉綠）。
- **T4** 改 2 py 測 + 1 js 測路徑；py 全套綠（scoped→全套）；**viewer 測需 cwd=`docs/frontend-local-version-viewer/viewer/`、先 `npm ci` 再 `npm test`**（0 red）。
- **T5** 全套回歸（Python 0 failed、viewer 0 red）。各 task 的「綠」為 scoped（T2＝schema 驗證相關測、P-2 預期綠於 T3）；**全套綠在 T5**。
- **T6a（本輪必做＝解鎖 v1.7.0 解析）** rebuild wheel → `pip install ./the_door` → **實機驗 `site-packages/the_door/schemas/` 11 檔存在＋`snapshot_write` 成功** → 接續跑完 v1.7.0 解析（snapshot_write → diff）。**不 bump、不 tag、不 push。**
- **T6b（發版 v1.7.1，待使用者明示，不主動）** bump pyproject 1.7.0→1.7.1、CHANGELOG `[Unreleased]`→v1.7.1（記 packaging fix）、commit、ff-merge、tag、push。**使用者明示才做。**

## 5. 終局護欄
- Python 全套 0 failed（含新 P-1）；viewer 0 red。
- `pip install`（非-editable）後 `site-packages/the_door/schemas/` 有 11 檔。
- `snapshot_write` 不再報 schema 路徑錯。
- 契約版號不動（`SNAPSHOT_CONTRACT_VERSION` 仍 `"1"`；schema 內容未改）。
