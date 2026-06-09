# C2 spec：checklist schema gate（丙案 軌2 階段2）

> 承接：種子 `2026-06-08-execution-model-control-via-structure-seed.md` §10.7（C2 列）、
> §10.7.2 階段2「把階段1的 ad-hoc 存在檢查升成 schema」。
> 承接 C3+C4（已 merged）：C3 gate 目前只驗 `.the-door/edge-residue.json` **存在性**，
> coverage/currency **deferred 已登記偏差**（C3 hook docstring §11、種子 §3）。
> **C2 = 把該偏差從「零深度」推進一級**：把存在性檢查升級成「結構化、versioned 的
> checklist」，並補上 **node-coverage（validity）**（agent 要寫的 source_nodes 必須 ⊆
> edge_residue 實際分析過的 node 集）與 **currency**（contract_version 比對）。
> ⚠ 完整 staleness（刪除/原地修改偵測、mtime 重算）仍 deferred——見 §2.5 誠實涵蓋宣稱。

---

## 0. spike（已對真實碼驗，事實寫入；不需事後再驗）

| 事實 | 來源 file:line | 對設計的影響 |
|---|---|---|
| C3 gate 目前只做存在性檢查 | `.claude/hooks/c3_gate_snapshot_write.py:44-51` | C2 改它讀 checklist、加 coverage/currency |
| edge_residue artifact＝`{indeterminate, low_confidence_ambiguous, total_edges, kept_edges}`，**無 node 集／fingerprint／version** | `mcp/tools/edge_residue_tool.py:41-46` | C2 要 edge_residue 另蓋 checklist，記錄 covered node_ids |
| edge_residue 已 `ASTExtractor().extract()`，**`extraction.nodes` 現成可用**（目前只用 edges） | `edge_residue_tool.py:34`、`ast_extractor.py:184-192` | 記 covered node_ids 零額外成本 |
| snapshot_write tool_input 含 `l1_features[].source_nodes` 與 `updated_features[].source_nodes`（structure.json node_id） | `snapshot_write_tool.py:53-56,100-103` | gate 可對「agent 要寫的 source_nodes」做 ⊆ 檢查＝node-coverage |
| **node_id 同一性已驗**：`extract_structure`（agent 取得 node_id 處）與 `edge_residue` 都讀**同一個** `ASTExtractor().extract().nodes`，逐字 expose `n.node_id` | `mcp/server.py:256`（extract）、`edge_residue_tool.py:34`（residue） | covered_nodes ≡ agent 看到的 source_nodes 命名空間 → ⊆ 檢查不會因格式不符而誤 deny。**前提＝agent 依協定把 extract_structure 回傳的 node_id 逐字當 source_nodes**（CLAUDE.md 已如此教） |
| node_id 碰撞會被 `_disambiguate_node_ids` 加 `#i` 後綴（罕見） | `ast_extractor.py:207-225` | 兩端皆套同一 disambiguation（同一 `result.nodes`）→ 仍一致；非問題 |
| `SNAPSHOT_CONTRACT_VERSION = "1"` | `models/snapshot.py:12` | checklist 掛此版本戳（種子要求） |
| hook 是 **stdlib-only standalone**（不上 the_door PYTHONPATH） | `c3_*.py`/`c4_*.py` 全 stdlib；`pip install -e` 半損（交接 §0） | gate 的「讀＋驗」邏輯必須 hook 內 stdlib 自足；不可 import the_door |
| hook 慣例：fail-open、deny 走 `stderr.buffer`（cp950 安全）、`CLAUDE_PROJECT_DIR` 守衛 | C3+C4 spec §2.4、settings.json | C2 hook 沿用 |
| ProjectRegistry 存在（專案身份） | `snapshot_write_tool.py:308`、`registry.py` | checklist 落在「目標 codebase 自己的 .the-door/」即可，不需 `<project>` 子路徑 |

### spike 校正（種子文字 → 真實可行）
- 種子寫 `.the-door/checklists/<project>/<version>.json`。**校正為單一 `.the-door/checklist.json`（codebase 自己的 .the-door 下）**，理由：
  1. gate 在 snapshot_write **之前**跑，那一刻**還沒有 snapshot version_id**，無法以 `<version>` 為鍵。
  2. checklist 描述的是「**目前工作狀態**（這份 codebase 現在跑到哪關）」，本質 per-codebase-working-state，不是 per-snapshot。
  3. `<project>` 子路徑多餘——artifact 已在該 codebase 自己的 `.the-door/`。
  - `<version>` 改為 **檔案內的 `contract_version` 欄位**（掛 `SNAPSHOT_CONTRACT_VERSION`），即種子「掛 SNAPSHOT_CONTRACT_VERSION」之意。

---

## 1. 目標與非目標

**目標**：
1. 引入 **checklist 結構（單一真相來源）**：versioned、可擴展到多 stage（為階段2「水平推廣 gate 到 extract/snapshot/diff 鏈」鋪路）。
2. `edge_residue` 工具**完成時自動蓋章**（種子「工具完成自動蓋章」）：寫 stage 戳記＋covered node_ids＋contract_version＋timestamp。
3. C3 gate **改讀 checklist**，驗三件：①edge_residue stage 已蓋章（≡舊存在性）②**currency**：`contract_version` == 當前 ③**node-coverage（validity 讀法）**：snapshot_write 要寫的所有 source_nodes ⊆ edge_residue 記錄的 covered node 集。

**「node-coverage」採 validity 讀法（明確界定）**：本刀檢查的是「agent 要寫的 source_nodes **都在** edge_residue 分析過的 node 集內」＝防止 agent 引用未分析/捏造的 node、並擋住「新增 node 但沒重跑 edge_residue」的漂移。**不採 completeness 讀法**（不檢查「codebase 的每個 node 都被某 feature 認領／無孤兒 node」）——completeness 是品質度量、非「防繞過」gate 本職，且需 codebase 全 node 集對 L1 全 source_nodes 的反向涵蓋，屬另一刀。

**非目標（釘樁，防 gold-plating）**：
- ❌ 不做 mtime／檔案內容級 staleness 偵測（gate 不可在 PreToolUse 重抽 AST＝太貴）。currency 以 contract_version 比對 ＋ node-coverage 天然擋程式漂移代替。**明確 deferred、文件化。**
- ❌ 不擴展到 extract/diff 等其他 gate（本刀只升級既有 snapshot_write gate；schema 設計成可擴展但只接一關）。對應種子階段2「水平推廣」另刀。
- ❌ 不碰 C4（原生 code-exec gate，與 checklist 無關）。
- ❌ 不動 edge-residue.json 既有結構（T2 的可觀察輸出，purpose 不同）；checklist 是**新增**第二 artifact，edge_residue 同時寫兩者。
- ❌ 不做 C5/C6（README gate 指回／回報），各自獨立刀。

---

## 2. 設計

### 2.1 Artifact：`.the-door/checklist.json`
```json
{
  "contract_version": "1",
  "stages": {
    "edge_residue": {
      "stamped_at": "2026-06-09T12:34:56Z",
      "node_count": 1431,
      "covered_nodes": ["Foo.bar", "Foo.baz", "module.func", "..."]
    }
  }
}
```
- `covered_nodes`＝該次 extraction 全部 node_id（排序、去重）。確定性、純本地。
- 大型 codebase 會讓檔案偏大（數千字串）；pilot 接受，文件化為已知取捨。**每次 edge_residue 覆寫該 stage（非 append）→ 不會無限增長。**
- `stamped_at`＝**C6（跑完回報）預留**；本刀 gate **不讀** stamped_at（currency 只看 contract_version）。記錄理由：C6 要彙整「各關何時執行」。明列避免被誤讀為 currency 依據。

### 2.2 生產模組：`core/checklist.py`（單一真相來源・寫入側）
純函式、零外部 I/O 依賴（只 json + pathlib + datetime）：
- 常數：`CHECKLIST_FILENAME = "checklist.json"`、`STAGE_EDGE_RESIDUE = "edge_residue"`、欄位名常數（`contract_version`/`stages`/`stamped_at`/`node_count`/`covered_nodes`）。
- `checklist_path(codebase_path) -> Path`
- `stamp_stage(codebase_path, stage, *, covered_nodes, contract_version) -> dict`：load-or-init（讀現有、壞檔則重建）→ 設 `stages[stage]`（含 `stamped_at`=UTC ISO、`node_count`、`covered_nodes` 排序）→ 寫回 → 回傳寫入的 dict。`contract_version` 一律以最新覆寫（單一蓋戳點，比照 snapshot 出生戳）。
- `read_checklist(codebase_path) -> dict | None`：壞檔／不存在→`None`（fail-soft）。

> 註：gate **reader 不 import 此模組**（hook stdlib 自足）。此模組是**寫入側**單一來源；reader 端的欄位名以**測試雙向釘樁**對齊（§4 釘樁測），防 schema drift。這是 hook 物理限制下的取捨（與 C3 既已硬編 artifact 路徑同性質）。

### 2.3 `edge_residue` 工具：完成時蓋章
`edge_residue_tool.execute()` 末端（寫完 edge-residue.json 後）新增：
```python
from the_door.core.checklist import stamp_stage, STAGE_EDGE_RESIDUE
from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION
covered = sorted({n.node_id for n in extraction.nodes})
stamp_stage(codebase_path, STAGE_EDGE_RESIDUE,
            covered_nodes=covered, contract_version=SNAPSHOT_CONTRACT_VERSION)
```
回傳 payload 增 `checklist_path`（可觀察）。不改既有 edge-residue.json 行為。

**失敗模式**：`stamp_stage` 寫入失敗（磁碟/權限）時**不可吞**——edge_residue 的存在目的就是讓後續 snapshot_write 過 gate；蓋章失敗卻回成功，會讓 agent 以為可往下走、卻在 snapshot_write 被 deny 且訊息指回 edge_residue（死循環）。⟹ 蓋章失敗應讓 edge_residue 回 error envelope（明示「checklist 蓋章失敗」），讓 agent 當下知道。

### 2.4 C3 hook：`c3_gate_snapshot_write.py` 升級（stdlib 自足）
讀 `<codebase>/.the-door/checklist.json`，依序驗（任一不過即 deny，訊息指回 `edge_residue`）：
1. **存在＋可解析**：無 checklist／壞檔 → deny「請先呼叫 edge_residue」。
2. **stage 蓋章**：`stages.edge_residue` 缺 → deny。
3. **currency**：`contract_version` != `"1"`（hook 內硬編當前值，釘樁測對齊 `SNAPSHOT_CONTRACT_VERSION`）→ deny「checklist 版本過期，請重跑 edge_residue」。
4. **node-coverage**：蒐集 tool_input 的 `l1_features[].source_nodes` ∪ `updated_features[].source_nodes`，若有任一 node ∉ `covered_nodes` → deny，訊息列出前幾個未涵蓋 node「這些 node 不在 edge_residue 涵蓋範圍（可能程式已變動）；請重跑 edge_residue」。
- source_nodes 全空／無 → coverage 真空通過（不阻擋 inherit-only 寫入）。
- fail-open 守則不變：stdin 無法解析／無 codebase_path → exit 0。**但「checklist 缺失」是 deny（非 fail-open）**——這正是 gate 的本職（與舊存在性檢查同語義）。

### 2.5 currency／coverage 兌現 C3偏差到什麼程度（誠實涵蓋宣稱）
- **version_id（currency）**：checklist 掛 `contract_version`；schema 演進時舊 checklist 自動失效 → deny → 重跑。
- **node-coverage 擋得到的漂移**：①agent 引用**未分析/捏造**的 node；②程式**新增** node 但沒重跑 edge_residue（新 source_nodes ∉ 舊 covered）。
- 🔴 **node-coverage 擋不到的漂移（誠實 deferred，不可宣稱等效 staleness）**：
  - **刪除** node：新 source_nodes 仍 ⊆ 舊 covered（子集成立）→ 通過，但 edge-residue 已 stale。
  - **原地修改**（node_id 不變、body/edges 變）：source_nodes 不變 → 通過，但 edges 已變。
  - ⟹ 完整 staleness（mtime／內容雜湊重算）**本刀不做**（gate 不可在 PreToolUse 重抽 AST＝太貴），與「刪除/原地改偵測」一起明確 deferred。C2 把 C3偏差從「零深度檢查」推進到「validity coverage + contract currency」，**非宣稱完全 staleness**。

---

## 3. 向後相容 / 遷移
- 既有 codebase 只有 edge-residue.json、無 checklist.json：C2 後 gate 要求 checklist → 第一次會 deny → 重跑 `edge_residue`（零-key、便宜）即蓋章。**刻意不做「舊 artifact 存在就放行」的 fallback**（那會繞過新 coverage/currency）。文件化為遷移註記。
- dogfood 本 repo `.the-door/`：同理，重跑一次 edge_residue 即可。

---

## 4. 測試（spec 層；plan 細分 task）
**checklist 模組（單元）**：
- C2-1 `stamp_stage` 建新檔：寫入 stage＋contract_version＋covered_nodes（排序）＋node_count；UTC stamped_at。
- C2-2 `stamp_stage` 既有檔疊加第二 stage 不毀前一 stage；contract_version 覆寫為最新。
- C2-3 `read_checklist` 壞檔／缺檔 → None。
- C2-4 covered_nodes 去重＋排序穩定。

**edge_residue 蓋章（單元／E2E）**：
- C2-5 `execute()` 跑完，checklist.json 存在、`stages.edge_residue.covered_nodes` == sorted(extraction node_ids)、contract_version=="1"；payload 含 checklist_path。（E2E：copytree fixture→tmp，守 E2E fixture-input-only。）

**hook gate（黑箱 subprocess，比照 test_execution_gates）**：
- C2-6 無 checklist → deny(rc2)，stderr 提 edge_residue。
- C2-7 **用 `stamp_stage` 真實產生 checklist**（非手搓）＋ source_nodes ⊆ covered → allow(rc0)。**producer↔reader 誠實綁定**：測試用生產側 `stamp_stage` 寫出的真實 artifact 形狀去餵 reader hook，確保兩端 schema 一致（防「手搓 checklist 過、真 artifact 形狀不同」假綠）。
- C2-8 source_nodes 含未涵蓋 node → deny(rc2)，stderr 提 coverage/變動。
- C2-9 contract_version 過期（如 "0"）→ deny(rc2)。
- C2-10 updated_features 的 source_nodes 也納入 coverage 檢查。
- C2-11 source_nodes 全空（inherit-only）→ allow(rc0)。
- C2-12 壞 checklist json → deny(rc2)（缺 = 要 gate）。
- C2-13 stdin 非 json／無 codebase_path → exit 0（fail-open）。

**釘樁（防 drift）— 機制具體化**：
- C2-14 **讀 hook 原始碼文字**，assert 硬編的當前 contract version 字串（`"1"`）出現；且 `== SNAPSHOT_CONTRACT_VERSION`。
- C2-15 **讀 hook 原始碼文字**，assert `core/checklist.py` 的每個欄位名常數值（CHECKLIST_FILENAME/`stages`/STAGE_EDGE_RESIDUE/`covered_nodes`/`contract_version`）字串都出現在 hook 原始碼中。**含負向驗證**：在測試內注入一個不存在於 hook 的假欄位名常數，斷言釘樁會抓到缺漏（防恆綠）。
- C2-16 settings.json 仍註冊 c3 hook on `mcp__the-door__snapshot_write`（既有 G-9 不回歸）。

**回歸**：既有 `test_execution_gates.py` C3 測會因「存在性→checklist」語義改變而需更新（artifact 從 edge-residue.json 改 checklist.json）——plan 列為改動非新增。

---

## 5. 終局護欄
- Python 全套 0 failed；新測 C2-1..C2-16 綠。
- `edge_residue` 跑後 `.the-door/checklist.json` 生成且 covered_nodes 非空（真實 codebase）。
- C3 hook 對「無 checklist」「coverage 不足」「version 過期」皆 deny；對合法寫入 allow；fail-open 守則保留。
- 既有 C3+C4 測全綠（更新後）。

---

## 6. Forward-coherence（against 後續刀）
- **C5（README gate 指回）**：checklist 的 stage 名是 README 指回的錨；本 schema 的 `stages` 命名需穩定（`edge_residue` 為首個）。✓ 已用穩定 key。
- **水平推廣（extract/diff gate）**：schema `stages` 是 open map，加新 stage 不破壞舊 reader（reader 只查自己關心的 stage）。✓ 可擴展。
- **C6（回報）**：checklist 即「各關是否執行」的結構化事實來源，C6 可直接讀它彙整。✓
