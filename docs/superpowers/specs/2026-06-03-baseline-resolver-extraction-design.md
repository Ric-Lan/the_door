# BaselineResolver 抽出 + UUID 文法收編（Finding B-1）— 設計

> **日期**：2026-06-03　**狀態**：設計核准、待寫 plan
> **刀序**：Finding B 第一刀（store 各藏一個子元件 → 顯性化）。承 2026-06-03 探查；與 B-2（doubt 轉移表）獨立、命題不同（B-1=差異/參照解析，B-2=範圍/狀態機）。
> **目標檔**：`the_door/src/the_door/core/diff/baseline_resolver.py`（新）、`the_door/src/the_door/core/diff/snapshot_store.py`、3 個消費者、1 新測試檔。
> **scope**：B（抽出 + 收編 UUID），非 A（純搬移）。經使用者拍板。

---

## §1 命題（為什麼動）

`SnapshotStore` 目前同時是「實體的儲存者」與「人類參照的解碼器」。後者——把 `v1.0.0` / `2026-05-06` / `8de9b18` / `my-label` / 完整 `version_id` 這些**鬆散的人類能指（Signifier）**映射到唯一的 **所指（Signified）`VersionSnapshot`**——是一種獨立技能，目前以四個私有方法埋在 store 裡，且**沒被說出口**。

抽出具名 `BaselineResolver` = 建立唯一的**符號轉譯器**（索緒爾符號學）：store 退回純客體存在、不再認得任何參照語彙；resolver 專責詮釋。

**變分明判準命中（加法軸）**：抽完系統多說出一件今天說不清楚的事——「resolver 認**全部 5 種**參照文法」。今天它只認 4 種（date/tag/SHA/label），第 5 種（version_id/UUID）散落在各消費者手動拼接，**複製 3 份、漏 4 處**（見 §2）。收編後，5 文法收斂到一處、消費者改單一呼叫。

---

## §2 驗證事實（已對真實碼核對，不需重驗）

### §2.1 接縫乾淨：resolver 對 store 的唯一依賴 = `_load_all_snapshots()`
- `resolve_baseline`（snapshot_store.py:154）+ `_resolve_by_date`(504) + `_resolve_by_git_ref`(534) + `_resolve_by_label`(557) + `_build_available_list`(566) 這一簇，對 `self` 的唯一外部依賴是 `_load_all_snapshots()`（line 320，回 `list[VersionSnapshot]`，內部已吞 `JSONDecodeError`）。其餘全是純比對（`datetime`/`re` + snapshot 欄位）。
- `_resolve_by_*` 與 `_build_available_list` **只在 snapshot_store.py 內被引用**（grep 全 repo：零外部消費者）。
- **無任何測試直接呼叫這些私有方法**（grep tests：只測公開 `resolve_baseline`）→ 搬移不破既有測試。

### §2.2 公開契約（必須逐字保留）
- 簽名：`resolve_baseline(self, reference: str) -> VersionSnapshot`。
- 失敗：`raise SnapshotNotFoundError(reference, available)`。`SnapshotNotFoundError.__init__(reference: str, available: list[dict])` 設 `.reference`/`.available`（models/snapshot.py:98）。
- `e.available` **真被消費**：`cli/diff_cmd.py:54-59` 渲染成 "Available snapshots:" 候選清單給使用者（Norman 認知緩衝＝契約一等公民，非裝飾）。
- 8 個呼叫端（7 外部 + 1 內部）：`cli/diff_cmd.py:50`、`cli/extract_cmd.py:112`、`mcp/diff_tool.py:38`、`mcp/analyze_changes_tool.py:95`、`mcp/snapshot_write_tool.py:173`、`core/pipeline/incremental_pipeline.py:54`、`core/ui/api/handlers/diff.py:135`、`snapshot_store.py:234`（patch_snapshot 內部）。

### §2.3 UUID 文法名實不符（B 要修的缺陷）
- `resolve_baseline` **不處理** version_id；UUID 由 `get_snapshot(version_id)`（snapshot_store.py:135，直接讀 `{id}.json`）處理。
- 消費者各自手動拼「先 resolve_baseline，落空再 get_snapshot」：**3 處有拼**（`handlers/diff.py`、`snapshot_write_tool.py`、`incremental_pipeline.py`），**4 處漏**（`diff_cmd`、`diff_tool`、`analyze_changes_tool`、`extract_cmd`）→ `the-door diff --baseline <uuid>` 今天會被拒，但 web `/api/diff` 不會。

### §2.4 version_id 掃描 ≡ get_snapshot（等價性，無行為漂移風險）
- `get_snapshot(ref)` 讀檔 `{ref}.json`；檔名由 `_write_snapshot` 一律寫成 `{snapshot.version_id}.json`（內外 id 恆等）。
- resolver 的 version_id 分支掃 `_load_all_snapshots()` 找 `s.version_id == ref`。
- 兩者命中集合相同（檔名恆等內部 id；損毀檔兩邊都跳過）。**無等價性破口**。

### §2.5 version_id 與既有分支無碰撞
- UUID（如 `6dc585ec-...`）不符 date regex `^\d{4}-\d{2}-\d{2}$`（首段含十六進位字母，`\d{4}` 失敗）。
- 不會被 `_resolve_by_git_ref` 誤命中（它比對 `commit_hash.startswith(ref)`，UUID 值不等於 commit hash）。

---

## §3 理論收貨／剔除紀錄（理論當磨刀、不當背書）

| 理論 | 留下的利刃（換得到具體改動） | 剔除的過頭版本 |
|---|---|---|
| 索緒爾 能指/所指 | resolver = signifier→signified 唯一映射；store 喪失參照語彙知識 | 不建「符號學分層/Semiotic 框架」——就一個 class + cascade |
| Norman 認知緩衝 | 失敗帶候選清單＝契約一等公民（已被 diff_cmd 渲染） | 不做模糊比對／「你是不是要找…」建議引擎 |
| Kahn 服務/被服務 | resolver **零 I/O**（前店）、store 管 `_load_all_snapshots`（後廠）→ 支撐「I/O 末端」 | **剔除其「讀寫效能/安全」收益宣稱**（違執行期資源中性，見 §10） |
| 邊界守門人 | cascade=policy、會隨文法增減而改＝CCP 變更理由，隔離後改一處 | **剔除 policy engine／獨立決策個體／Strategy 模式**；不抽 interface |

---

## §4 設計

### §4.1 新檔 `core/diff/baseline_resolver.py`（純、零 I/O）

具體 class（**不抽 interface/ABC**），純函數語意 `resolve(reference, snapshots) -> VersionSnapshot`：

```python
"""Resolve a human baseline reference (the 5 grammars) to a concrete snapshot.

Pure: no file I/O. The store loads snapshots and feeds them in; this class only
interprets the reference and matches. Single home of all reference grammars:
date / git tag / commit SHA / manual label / version_id (UUID).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from the_door.models import SnapshotNotFoundError, VersionSnapshot


class BaselineResolver:
    """Maps a signifier (human reference string) to a signified (VersionSnapshot)."""

    def resolve(
        self, reference: str, snapshots: list[VersionSnapshot]
    ) -> VersionSnapshot:
        """Resolve ``reference`` against an already-loaded snapshot list.

        Priority cascade (order is behaviour-preserving — see spec §7.1):
          1. ISO date (YYYY-MM-DD)  -> most recent on or before that date
          2. git tag exact / commit SHA prefix (>=7 chars)
          3. manual label exact
          4. version_id exact (UUID)            # new in B; placed AFTER label
        Raises SnapshotNotFoundError(reference, available) if nothing matches.
        """
        if re.match(r"^\d{4}-\d{2}-\d{2}$", reference):
            return self._resolve_by_date(reference, snapshots)

        result = self._resolve_by_git_ref(reference, snapshots)
        if result is not None:
            return result

        result = self._resolve_by_label(reference, snapshots)
        if result is not None:
            return result

        result = self._resolve_by_version_id(reference, snapshots)
        if result is not None:
            return result

        raise SnapshotNotFoundError(reference, self._build_available_list(snapshots))
```

- `_resolve_by_date` / `_resolve_by_git_ref` / `_resolve_by_label` / `_build_available_list`：**逐字搬自** snapshot_store.py（504/534/557/566），唯一改動是 `_resolve_by_date` 內 `self._build_available_list(...)` 仍指向本 class 的同名私有方法（自然成立）。
- **新增** `_resolve_by_version_id(reference, snapshots) -> VersionSnapshot | None`：
  ```python
  def _resolve_by_version_id(
      self, reference: str, snapshots: list[VersionSnapshot]
  ) -> VersionSnapshot | None:
      """Find snapshot by exact version_id match."""
      for s in snapshots:
          if s.version_id == reference:
              return s
      return None
  ```

### §4.2 `SnapshotStore` 變薄殼（I/O 留在末端）

- `__init__`（snapshot_store.py:74，`_snapshots_dir` 設於 85 後）新增**單一實例**：
  ```python
  self._baseline_resolver = BaselineResolver()
  ```
  （持一實例、免每呼叫 new；stateless collaborator，非過度設計。）
- `resolve_baseline`（154）整段 body 改為委派（公開簽名與 raise 契約不變）：
  ```python
  def resolve_baseline(self, reference: str) -> VersionSnapshot:
      """Resolve a baseline reference to a snapshot. See BaselineResolver."""
      return self._baseline_resolver.resolve(reference, self._load_all_snapshots())
  ```
- **刪除** store 內已搬走的 `_resolve_by_date` / `_resolve_by_git_ref` / `_resolve_by_label` / `_build_available_list`（504-582）。`get_snapshot`（135）**保留**為「直接 id 讀檔」原語。

### §4.3 消費者收斂（3 處拼接 → 單一呼叫；4 處不改碼自動支援 UUID）

**(a) `core/ui/api/handlers/diff.py` `_resolve_snapshot`（133-140）** → 收斂為 raise→None adapter：
```python
def _resolve_snapshot(self, store: SnapshotStore, ref: str):
    try:
        return store.resolve_baseline(ref)
    except SnapshotNotFoundError:
        return None
```
（兩個呼叫端需要「miss 回 None → 404」；resolve_baseline 現解全 5 文法，get_snapshot 後援冗餘，移除。）

**(b) `mcp/tools/snapshot_write_tool.py`（170-177）** → 移除 get_snapshot 後援行：
```python
    if inherit_from:
        try:
            baseline_snap = store.resolve_baseline(inherit_from)
        except SnapshotNotFoundError:
            baseline_snap = None
        if baseline_snap is None:
            # ... 既有 baseline_not_found remediation 不動
```
（刪掉 `if baseline_snap is None: baseline_snap = store.get_snapshot(inherit_from)`。）

**(c) `core/pipeline/incremental_pipeline.py` `_resolve_baseline`（47-56）** → 收窄例外 + 補 import：
```python
from the_door.models import SnapshotNotFoundError  # 新增 import（現未 import）

def _resolve_baseline(store: SnapshotStore, baseline_ref: str) -> VersionSnapshot | None:
    """Resolve baseline_ref (all 5 grammars). None if no snapshot matches."""
    try:
        return store.resolve_baseline(baseline_ref)
    except SnapshotNotFoundError:
        return None
```
（`except Exception` 收窄為 `except SnapshotNotFoundError`：resolve_baseline 只會丟這個；收窄不再遮蔽非預期錯誤。回傳 None 契約不變。）

**(d) 不改碼者**：`cli/diff_cmd.py`、`cli/extract_cmd.py`、`mcp/diff_tool.py`、`mcp/analyze_changes_tool.py` 維持單一 `resolve_baseline` 呼叫，行為自動擴成接受 UUID（嚴格超集）。

**(e) 內部呼叫端 `patch_snapshot`（snapshot_store.py:234）**：委派 `resolve_baseline`，B 下一併繼承 version_id 超集，**無需改碼、無測試影響**（已驗：patch 測試全用 label `"v1.0.0"`，`test_patch_unknown_version_ref_raises` 用 `"v-nonexistent"` 在 B 下仍 raise）。

### §4.4 測試遷移（B 的必要連動）

- **刪除** `tests/unit/core/ui/api/handlers/test_diff.py::test_resolve_falls_back_to_get_snapshot`（line 86-95）：它專測被移除的消費者層 get_snapshot 後援。其守護行為（UUID 解析）下移 resolver，由 §6 新測試覆蓋。
- `test_diff.py` 的 `test_baseline_not_found_returns_404`(19)、`test_current_not_found_returns_404`(28)：**不改**仍綠（mock `resolve_baseline` 回 `None`，新 adapter 對 None 回 None → 404；`get_snapshot` mock 設定變死碼但無害）。
- scenario `tests/scenario/test_v105_incremental_flow.py:130`（current 端傳 raw version_id）：**不改斷言、仍綠**（version_id 改由統一 resolver 解）；更新 line 135 stale 註解「→ get_snapshot fallback」為「→ unified BaselineResolver (version_id grammar)」。
- **§4.3(b) snapshot_write 收斂的安全網（必盯、不改、B 下仍綠）**：`tests/unit/mcp/test_snapshot_write_inherit.py`（`inherit_from=<version_id>` ×6：58/71/90/108/128/147）、`tests/integration/test_mcp_flow_guard.py:85`、`tests/contract/test_flow_guard_contract.py:89`。它們今天靠被移除的 get_snapshot 後援才綠；B 下改靠 `resolve_baseline` 的 version_id 分支才綠（§4.1）。**故 (b) 的 fallback 移除必須與 version_id 分支同刀落地**，否則這些測試紅。

---

## §5 契約保留（驗收硬條件）

- `SnapshotStore.resolve_baseline(str) -> VersionSnapshot` 簽名與 raise `SnapshotNotFoundError(reference, available)` 不變。
- `e.available` 結構不變（`_build_available_list` 逐字搬移、邏輯零改）。
- `get_snapshot` 保留。9 消費者中 6 個零改、3 個僅移除冗餘後援。
- 讀取路徑、`VersionSnapshot` 模型、`core/datamodel/` 不動。

---

## §6 測試計畫

**新 `tests/unit/core/diff/test_baseline_resolver.py`（純單元、無檔案 I/O，直接建 `list[VersionSnapshot]` 餵 `BaselineResolver().resolve`）：**
1. date 文法：回「該日或之前最近」。
2. git tag exact / SHA 前綴（≥7）各命中；平手「最新 timestamp 勝」。
3. label exact 命中；平手最新勝。
4. **version_id exact 命中**（B 新增）。
5. **序保留**：同一字串既是某 label 又是另一 snapshot 的 version_id 時，**label 先勝**（version_id 置 label 後）。
6. 全落空 → `raise SnapshotNotFoundError`，`e.available` 含全候選。

**整合層（證 B 行為擴張）：** `SnapshotStore.resolve_baseline(<version_id>)` 回該 snapshot（證 §2.3 那 4 個舊拒 UUID 入口現已支援）。

**回歸：** 全套件零回歸（基準＝當下 main）；§4.4 的刪除/註解更新後綠。**消費者收斂的既有安全網**（無新測、必須維持綠）：snapshot_write→§4.4 列的 inherit_from=vid 測試組；api/diff→`test_diff.py` 19/28 + scenario step6；pipeline→`test_v105_incremental_flow` 端對端。

---

## §7 陷阱（給實作者）

1. **version_id 置 label 之後**：今天消費者序是「resolve_baseline(date→git→label) 失敗才 get_snapshot」，故 version_id 是最後手段。cascade 必須維持此序，否則同字串撞 label 時行為漂移。
2. **incremental_pipeline 收窄例外要補 import**：該檔現**未** import `SnapshotNotFoundError`（grep 證實），改 `except SnapshotNotFoundError` 必須同時加 import，否則 NameError。
3. **resolver 持單一實例**：在 store `__init__` 建一次、`resolve_baseline` 重用 `self._baseline_resolver`；勿在 `resolve_baseline` 內每呼叫 `BaselineResolver()`（無謂配置）。
4. **逐字搬移 `_build_available_list`**：含 `sorted(..., reverse=True)` 與選填欄位拼裝，逐字搬、勿順手「優化」，以保 `e.available` 結構穩定（被 diff_cmd 渲染）。
5. **刪 store 私有方法後**：確認 snapshot_store.py 內無殘留呼叫（patch_snapshot:234 呼叫的是公開 `resolve_baseline`，不受影響）。

---

## §8 Non-goals

- 不抽 interface/ABC；不建 policy/strategy 引擎。
- 不加 `matched_by`/`tie_break` 來路輸出（無現成消費者，YAGNI）。
- 不碰 B-2（doubt 轉移表）、不碰讀取路徑、不碰 `core/datamodel/`。
- 不宣稱效能/吞吐收益（見 §10）。

---

## §9 驗收

- 新 `BaselineResolver` 純、零 I/O、5 文法收斂、單元測涵蓋 §6 全 6 項 + 序保留。
- `SnapshotStore.resolve_baseline` 委派薄殼、公開契約逐字不變；store 內 4 私有方法已刪、無殘留呼叫。
- 3 消費者收斂單一呼叫；4 消費者自動支援 UUID；`test_diff.py:86` 已刪、scenario 註解已更。
- 改動面：新檔 + snapshot_store + 3 消費者 + 1 新測試檔 + 1 測試刪除 + 1 scenario 註解。**不得有其他檔被改。**
- 全套件零回歸。

---

## §10 校準宣言（執行期資源中性）

本刀買到的是**可理解性與變更局部性**（變分明）：5 文法收斂一處、消費者去重。**執行期中性**——同樣的 `_load_all_snapshots()` 一次讀取、同樣的比對。B 順帶消掉舊路徑「resolve 失敗再 get_snapshot 二次讀檔」的冗餘讀取，記為 **DRY/簡化**，**不**作為 throughput/效能宣稱。剔除 Kahn 理論附帶的「讀寫效能/安全」收益語言（§3）。
