# S7 plan：provenance 主軸（版本戳 + Signal）4-task inline TDD

> **日期**：2026-06-06　**狀態**：plan（待執行）　**承**：[`2026-06-06-S7-provenance-throughline-spec.md`](../specs/2026-06-06-S7-provenance-throughline-spec.md)（雙審：concept+5 軸；本 plan 引 spec §3.x 不重貼）。
> **執行方式**：inline TDD（red→green→必要 refactor）。**一刀、內部 4-task 排序**（持久化風險先地基後 emit）。逐 task gate、末 task 全測。完成 ff-merge main、**不主動 push**。
> **基線**：main `0034291`、全測 1557 passed。驗收＝1557＋新測、零回歸（除 emit/serde characterization 有意更新）。
> **環境**：`pip install -e ./the_door`（本 session 已裝）；pytest cwd＝內層 `the_door/`；`PYTHONUTF8=1`。

---

## 範圍鎖定（執行前確認，承 spec §1）

- **in**：①持久化戳（`VersionSnapshot.contract_version`＋`SNAPSHOT_CONTRACT_VERSION`＋create_snapshot 蓋戳＋serde＋schema）②`core/diff/provenance_membrane.py`（derive＋膜）③emit 投影（diff_tool／analyze_changes／snapshot_list）。
- **out（不得誤動）**：`report_renderer.render_json`／viewer／CLI／前端／`update-report.schema.json`、per-feature 戳、audit_conformance 違規明細、自動遷移既有快照、F-severity-default。
- **grep gate（末 task）**：`git diff --stat` 僅含 models/snapshot.py＋snapshot_store.py＋snapshot.schema.json＋provenance_membrane.py＋diff_tool.py＋analyze_changes_tool.py＋snapshot_list_tool.py＋對應測；**無 report_renderer/前端/render_json**。

---

## Task 1 — 持久化出生戳地基（characterization 先行：契約改動）

**交付**（exact code＝spec §3.1-3.4）：
- `models/snapshot.py`：`SNAPSHOT_CONTRACT_VERSION="1"`＋`VersionSnapshot.contract_version: str|None=None`。
- `snapshot_store.py`：`create_snapshot` 蓋戳；`_serialize_snapshot`/`_deserialize_snapshot` round-trip。
- `snapshot.schema.json`：加 `contract_version` optional 欄。

**TDD（P1/P2/P7）**：
1. **pin（先釘現狀）**：既有 `test_snapshot_store_roundtrip.py` 全綠（基線）。
2. **red→green**：
   - 新測：`create_snapshot(...).contract_version == SNAPSHOT_CONTRACT_VERSION`（P1）。
   - round-trip：`create_snapshot`→讀回 `get_snapshot`→`contract_version` 保真（P2）。
   - **legacy-load（P7、O3）**：構造**無 `contract_version` 鍵**的舊 snapshot JSON 寫檔→`get_snapshot`/`_load_all_snapshots`→`contract_version is None`、**schema validate 通過**（additive optional）、不炸（復用 `test_snapshot_store_roundtrip` 既有 legacy 樣式 `:84` test_legacy_snapshot...）。
   - 加碼照 spec §3.1-3.4。
3. **[F-other-snapshot-producers]＝🟢 已查實（單一蓋戳點）**：grep 證**全建立路由經 `create_snapshot`**（cli/snapshot_cmd、snapshot_write_tool、snapshot_create_tool、analyze_pipeline 皆呼之）；`VersionSnapshot(` 僅 `snapshot_store.py:116`(create)/`:468`(deserialize) 構造 ⟹ **蓋戳一點即全覆蓋**、無散落蓋戳。
4. **patch 保留戳 characterization（concept-review 補）**：`snapshot_patch`（`snapshot_store.py:247` 重寫 loaded snapshot）**不 re-stamp、保原戳**。測：建 stamped snapshot→patch→assert `contract_version` 不變（複用 `test_snapshot_patch.py` fixture）。確保 post-S7 快照經 patch 不掉戳→誤判 unknown。

**gate**：`PYTHONUTF8=1 python -m pytest tests/unit/core/diff/test_snapshot_store_roundtrip.py tests/unit/mcp/ -q` 綠（既有 serde/snapshot 測零回歸＋新戳測）。

---

## Task 2 — 衍生 ＋ provenance 膜詞彙（red→green）

**交付**：`core/diff/provenance_membrane.py`（exact code＝spec §3.5）＋`tests/unit/core/diff/test_provenance_membrane.py`。

**TDD（P3/P4）**：
1. **red**：寫測 import `PROVENANCE_CONTRASTS`/`derive_provenance`/`provenance_element`/`provenance_element_for`（ImportError）。
2. **green**：建 `provenance_membrane.py`。

**測試**：
- **P3 derive**：`derive_provenance("1")`→"current"（=="1"＝SNAPSHOT_CONTRACT_VERSION）；`derive_provenance("0")`→"legacy"（present 且 !=）；`derive_provenance(None)`→"unknown"。
- **P4 膜**：`PROVENANCE_CONTRASTS==("current","legacy","unknown")`；`provenance_signal(v).contrasts==PROVENANCE_CONTRASTS`＋gloss；`provenance_element("unknown").to_json()` position.kind=="**signal**"（**unknown 是格內真值、非 noise**——P4 關鍵）；`provenance_element_for(None).to_json()` value=="unknown"+signal。
- 防呆：`provenance_element("bogus")`→KeyError（_GLOSS 無）。
- gloss 涵蓋：`set(_GLOSS)==set(PROVENANCE_CONTRASTS)`。

**gate**：`pytest tests/unit/core/diff/test_provenance_membrane.py -q` 綠。

---

## Task 3 — emit 投影（3 agent-facing 面，characterization flip）

**交付**（exact code＝spec §3.6）：
- `diff_tool.py` json baseline_info/current_info 加 provenance（`baseline_snap`/`current` 的 contract_version）。
- `analyze_changes_tool.py` payload 加 `baseline_provenance`（**由 `diff.baseline_version_id` 穩健取 baseline snapshot**，不用條件 `snap`——spec §3.6 修）。
- `snapshot_list_tool.py` 每筆加 provenance。

**TDD（P5/P6）**：
1. **diff_tool flip**（複用 S6 `test_diff_tool.py` 的 SnapshotStore fixture 樣式）：pin 現狀（baseline_info 無 provenance）→ flip：baseline_info/current_info 含 `provenance` 膜 `{value,position(signal)}`。**跨版點亮案例**：構造 baseline 為**手寫無戳舊 snapshot**（unknown）+ 新 current（蓋戳 current）→ baseline provenance=="unknown"、current=="current"（驗 §283 點亮）。
2. **analyze_changes flip**：payload 含 `baseline_provenance` 膜；**P6 正交**：同 payload 仍含 `inherited_features`/`affected_features`、互不干涉。source_path 帶與不帶兩案皆不炸（驗 spec §3.6 穩健取 baseline）。
3. **snapshot_list flip**：每筆含 provenance 膜。
4. **green**：照 spec §3.6 接線（皆 inline、不經 render_json）。

**gate**：`pytest tests/unit/mcp/ -q` 綠。grep 確認 `report_renderer.py`/render_json 未動。

---

## Task 4 — 全測 gate ＋ grep gate

- `cd the_door && PYTHONUTF8=1 python -m pytest -q` ＝**1557＋新測、零回歸**（唯一既有改動＝3 emit 新增 provenance 鍵＋snapshot serde 新增 optional 欄，由 characterization 圈住）。
- 回驗：S0-S8 membrane 測全綠；既有 snapshot serde 測（additive 欄）綠；既有 diff/analyze_changes/snapshot_list 測——provenance 為新增鍵、舊斷言不破（若有全等 dict 斷言→有意更新）。
- `git diff --stat`：models/snapshot.py＋snapshot_store.py＋snapshot.schema.json＋provenance_membrane.py(新)＋diff_tool.py＋analyze_changes_tool.py＋snapshot_list_tool.py＋測檔。**無 report_renderer/前端/update-report.schema.json。**

---

## 完成後（ff-merge）

1. commit（campaign 風格，建議：`feat(snapshot): contract_version 出生戳 (P1/P2/P7)`／`feat(provenance-membrane): current/legacy/unknown Signal`／`feat(provenance-emit): diff/analyze_changes/snapshot_list 投影 + test`）。
2. ff-merge 回 main、**不主動 push**。
3. 更新 handoff：S7 merged；**乙案三主軸（confidence/scope/provenance）agent 面整膜收齊**；[F-contract-version-bump-discipline]（契約變更 bump 常數入流程）；剩餘＝人類面整膜（碰前端）／presence-flag 型／F-severity-default。

---

## 驗收清單（對應 spec §4 不變量）

| # | 驗收 | task | 測 |
|---|---|---|---|
| P1 | 新建快照 contract_version==SNAPSHOT_CONTRACT_VERSION | 1 | create_snapshot 測 |
| P2 | serde round-trip 保真 | 1 | round-trip 測 |
| P7 | schema additive、legacy-load→None、不炸 | 1 | legacy-load 測 |
| P3 | derive ==/!=/None → current/legacy/unknown | 2 | test_provenance_membrane |
| P4 | unknown 是格內 Signal 真值（無 noise/None） | 2 | test_provenance_membrane |
| P5 | 3 emit 經膜無裸值；render_json 未動 | 3 | flip 測＋grep gate |
| P6 | provenance ⊥ inherited/affected | 3 | analyze_changes 測 |
| 回歸 | S0-S8 全測綠、out 清單未動 | 4 | 全測＋git diff --stat |

**plan 完成 → 待執行 inline TDD Task 1→4 → ff-merge。**（本 session 依指示：spec→plan 完成即停。）
