# C6 spec：跑完彙整回報使用者（丙案 軌2 階段2）

> 承接：種子 `2026-06-08-execution-model-control-via-structure-seed.md` 基礎原則 7（line 121）、
> §10.6 表（「PostToolUse 彙整｜跑完回報使用者｜資訊」）、§10.7 表（C6 列：「各關是否執行/產物/結果
> 彙整回報」，量小、依賴 C2）、§10.7.2 階段2。
> 承接 C2（已 merged）：checklist `stages` 是 versioned open map，`stamped_at` 欄位**本就為 C6 預留**
> （C2 spec §2.1 明列「stamped_at＝C6 預留；本刀 gate 不讀」）。
> **C6 = 把 checklist 升成「執行鏈事實 ledger」並在鏈尾回報**，讓使用者有事實基礎核對、非黑箱。

---

## 0. 已拍板範圍決策（使用者 2026-06-10 確認，先盤點後動）

| 問題 | 決策 |
|---|---|
| **seam**（回報落在哪） | **MCP 工具讀取側**：snapshot_write（鏈尾工具）跑完讀 checklist、把整鏈 ledger 嵌入回應 payload，由 agent（agent-as-LLM）轉述給使用者。不新增 hook（資訊層、無牙齒，守 §10.6 守則）。 |
| **ledger 範圍** | **整條鏈**：snapshot_write 跑完也**蓋自己的 stage**（新增 `snapshot_write` stage，純加法、不影響 C3 gate），使 ledger 完整呈現 `edge_residue → snapshot_write` 全鏈「各關是否執行/產物/結果」。 |

---

## 1. spike（已對真實碼驗，事實寫入；不需事後再驗）

| 事實 | 來源 file:line | 對設計的影響 |
|---|---|---|
| 基礎原則 7＝「每條鏈跑完，把『各關是否執行、產物、結果』彙整回報，使用者才有事實基礎核對（非黑箱）」 | 種子 line 121 | C6 的驗收意圖＝**防 agent 黑箱/捏造回報**；ledger 要是「我」轉述的事實來源 |
| §10.6 把 C6 定位「PostToolUse 彙整」、層級＝**資訊**（守則：強制力 100% 在 deny gate、文字無牙齒） | 種子 line 302,304-308 | C6 **不加 hook、不加 gate**；純讀取側資訊投影 |
| checklist `stages` 已是 versioned open map、每 stage 記 `stamped_at`/`node_count`/`covered_nodes`；`stamped_at` 明列「C6 預留」 | `core/checklist.py:62-72`、C2 spec §2.1 | C6 直接讀現成 schema；只需 ①snapshot_write 也蓋章 ②讀取側投影 ledger |
| `stamp_stage(codebase_path, stage, *, covered_nodes, contract_version)` 目前 `covered_nodes` 為必填 keyword | `core/checklist.py:45-77` | snapshot_write stage **無 covered_nodes 語義**（它產 feature、不「涵蓋 node」）→ 需把 `covered_nodes` 改 optional（預設 None＝不寫 node 欄位） |
| 既有 `stamp_stage` 呼叫**全部顯式傳 covered_nodes**（edge_residue 傳 list；測試傳 list 或 `[]`） | `edge_residue_tool.py:59-64`、`test_checklist.py`、`test_execution_gates.py` | 把 covered_nodes 改 optional-with-default 對既有呼叫**完全向後相容** |
| C2-15 drift-pin 只釘**固定一組**常數（CHECKLIST_FILENAME/FIELD_STAGES/STAGE_EDGE_RESIDUE/FIELD_COVERED_NODES/FIELD_CONTRACT_VERSION），**非動態掃全模組** | `test_execution_gates.py:123-130` | 新增 `STAGE_SNAPSHOT_WRITE` 等常數**不會反咬** drift-pin；C3 hook 不需引用它們 |
| C3 gate 只讀 `stages.edge_residue.covered_nodes`；對 checklist 額外欄位/額外 stage 無感 | `c3_gate_snapshot_write.py`、C2 spec §2.4 | 新增 snapshot_write stage、stage 內 details 欄位＝**對 gate 純加法、零互動** |
| snapshot_write 兩模式（direct / inherit）在 `create_snapshot` 收斂於同一點，payload 經 `wrap()` 注入 next_actions | `snapshot_write_tool.py:298-320` | 單一蓋章＋嵌 ledger 點＝`create_snapshot` 後、`wrap()` 前；兩模式皆覆蓋 |
| C3 gate 在 snapshot_write **之前**跑、已驗 checklist 存在＋edge_residue 蓋章＋currency＋coverage | settings.json PreToolUse、C2 spec §2.4 | execute() 跑到時 checklist 必已存在（gate 放行）；snapshot_write 蓋章只是**疊加** stage |
| `SNAPSHOT_CONTRACT_VERSION = "1"`（models.snapshot） | `models/snapshot.py:12` | snapshot_write 蓋章沿用同一 contract_version（單一蓋戳點，與 edge_residue 一致） |
| covered_nodes 可達數千字串（大型 codebase） | C2 spec §2.1 已知取捨 | **ledger 投影必須排除 covered_nodes 陣列**（保留 node_count），否則每次 snapshot_write 回應被灌爆 |

### spike 校正（種子文字 → 真實可行）
- 種子 §10.6 寫「PostToolUse 彙整」。**校正為「鏈尾 MCP 工具（snapshot_write）讀取側嵌入 ledger」**，理由：
  1. PostToolUse hook 的 stdout 非乾淨 user-facing（進 transcript/context），且須 stdlib-only 重寫 checklist 讀取邏輯（重蹈 C3 drift-pin 取捨）、只在分析 The Door 自身時生效。
  2. 基礎原則 7 的意圖＝「鏈跑完、我據實轉述」。**把 ledger 放進鏈尾工具的回應**＝我呼叫的最後一個工具必帶事實 ledger ⟹ 最能防黑箱（我無法略過它）。
  3. 對任何 target codebase 皆生效、可 pytest 驗（pip 半損下 live MCP 不可靠，pytest 直呼 execute() 是既有驗證路徑）。
  4. 與使用者選的「MCP 工具讀取側」一致；snapshot_write 本就是 MCP 工具，讀 checklist 投影 ledger 即「讀取側」。

---

## 2. 目標與非目標

**目標**：
1. **snapshot_write 蓋章**：成功寫入 snapshot 後，於 checklist 蓋 `snapshot_write` stage，記 `stamped_at` ＋產物事實（`version_id`/`label`/`feature_count`/`relation_count`）。使 checklist 成為**整條鏈**的執行事實來源（非只 edge_residue）。
2. **讀取側 ledger 投影**：`read_ledger(codebase_path)` 把 checklist `stages` 投影成**有序、摘要化**的 ledger（每關：stage 名、是否執行＝有戳即執行、stamped_at、node_count、產物 details；**排除龐大 covered_nodes 陣列**）。
3. **鏈尾回報**：snapshot_write 回應 payload 增 `execution_ledger` 欄位（＝`read_ledger` 結果）。agent 據此向使用者彙整「各關是否執行/產物/結果」。

**非目標（釘樁，防 gold-plating）**：
- ❌ **不加 PostToolUse hook、不加任何 gate**（C6 是資訊層、無牙齒；守 §10.6 守則 1/2）。
- ❌ **不擴 system_status / 不新增 report 工具**（鏈尾嵌入已兌現「跑完回報」；獨立查詢面屬日後「水平推廣」另刀，避免雙重表面 gold-plating）。
- ❌ **不改 C3 gate / C4 / edge_residue 既有蓋章行為**（snapshot_write stage 對 gate 純加法）。
- ❌ **不在 ledger 投影 covered_nodes 全陣列**（只給 node_count；防回應膨脹）。
- ❌ **不做 staleness／品質度量**（C2 已誠實 deferred 的部分，與 C6 無關）。
- ❌ **不渲染人類最終文字**（ledger 給結構化事實，agent-as-LLM 負責轉述；保 fact-finder 原則）。

---

## 3. 設計

### 3.1 `core/checklist.py` 擴充

**新常數**：
```python
STAGE_SNAPSHOT_WRITE = "snapshot_write"
# stage 順序（ledger 投影用；未知 stage 依字母序附後）
STAGE_ORDER = (STAGE_EDGE_RESIDUE, STAGE_SNAPSHOT_WRITE)
```

**`stamp_stage` 簽章調整**（向後相容）：
```python
def stamp_stage(
    codebase_path, stage, *, contract_version,
    covered_nodes: list[str] | None = None,   # 改 optional
    details: dict | None = None,              # 新增：stage 專屬產物事實
) -> dict:
```
- `covered_nodes is not None` → 照舊寫 `node_count` + `covered_nodes`（排序去重）。
- `covered_nodes is None` → **不寫** node 欄位（snapshot_write stage 無此語義）。
- `details` → 各鍵併入 stage entry（snapshot_write 傳 `{version_id, label, feature_count, relation_count}`）。`stamped_at` 永遠寫。
- 既有 edge_residue／測試呼叫顯式傳 `covered_nodes=` → 行為不變。

**新讀取側 `read_ledger`**：
```python
def read_ledger(codebase_path) -> list[dict]:
    """投影 checklist.stages 成有序、摘要化 ledger（給 C6 回報）。

    每項：{"stage", "stamped_at", + node_count(若有), + details 鍵}。
    刻意排除龐大的 covered_nodes 陣列（只保留 node_count）。
    缺檔/壞檔 → []（fail-soft）。
    """
```
- 讀 `read_checklist`；None → `[]`。
- 依 `STAGE_ORDER` 排序已知 stage，未知 stage 依字母序附後（向前相容水平推廣的新 stage）。
- 每 entry copy stage dict、**非破壞移除 `covered_nodes`**（`dict.pop(FIELD_COVERED_NODES, None)`——snapshot_write stage 本就無此鍵，不可 KeyError）、塞入 `stage` 名。
- **保留鍵約束（防水平推廣碰撞）**：`details` 的鍵**不得**用 `stage`/`stamped_at`/`node_count`/`covered_nodes`（投影注入鍵＋既有欄位）。本刀 snapshot_write 的 details（version_id/label/feature_count/relation_count）皆不犯；明列為約束供日後新 stage 遵守。

> 註：`read_ledger` 屬讀取側、純投影、零副作用，放 checklist.py（與 `read_checklist` 同處）。模組 docstring 標「write side」需順手補一句涵蓋讀取投影。

### 3.2 `snapshot_write_tool.execute()` 蓋章＋嵌 ledger

`create_snapshot(...)` 之後、`return wrap(payload, ...)` 之前：
```python
from the_door.core.checklist import STAGE_SNAPSHOT_WRITE, read_ledger, stamp_stage
from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION

# C6: 蓋 snapshot_write stage（磁碟 best-effort）＋嵌整鏈 ledger 回報。
sw_details = {
    "version_id": snapshot.version_id,
    "label": snapshot.label,
    "feature_count": len(l1_snapshot),
    "relation_count": len(relations),
}
try:
    stamp_stage(
        codebase_path, STAGE_SNAPSHOT_WRITE,
        contract_version=SNAPSHOT_CONTRACT_VERSION,
        details=sw_details,
    )
except OSError:
    pass  # 磁碟/權限——見 §3.3 fail-soft 理由（簽章/邏輯 bug 不在此吞）
payload["execution_ledger"] = _ledger_with_snapshot_write(codebase_path, sw_details)
```
其中 `_ledger_with_snapshot_write` 保證**回傳 ledger 永不漏報已執行的 snapshot_write 本關**（解第一輪審 warning）：
```python
def _ledger_with_snapshot_write(codebase_path, sw_details) -> list[dict]:
    ledger = read_ledger(codebase_path)
    if not any(e["stage"] == STAGE_SNAPSHOT_WRITE for e in ledger):
        # 磁碟蓋章失敗（OSError）→ 用記憶體事實補本關，不靠剛失敗的寫入。
        ledger.append({"stage": STAGE_SNAPSHOT_WRITE, **sw_details})
    return ledger
```
- 嵌在既有 payload（`version_id`/`label`/`timestamp`/`feature_count`/`relation_count`/`warnings?`）旁，純加法。
- 只在**成功路徑**蓋章＋嵌 ledger；error/checkpoint/baseline_not_found 等早退路徑不帶 ledger（鏈未完成、無「跑完回報」語義；C3 deny 等已各自有訊息）。
- ⚠ 用 `except OSError`（非裸 `Exception`）：磁碟/權限類容忍 fail-soft，但本刀**正在改 `stamp_stage` 簽章**，簽章/型別 bug 必須能在測試/生產浮現，不可被寬 except 遮蔽。

### 3.3 失敗模式：snapshot_write 蓋章＝fail-soft（與 edge_residue fail-loud 對稱相反）
- **edge_residue 蓋章 fail-loud**（C2 §2.3）：它是 snapshot_write 過 gate 的**前置條件**，蓋章失敗卻回成功 → agent 以為可往下、卻在 gate 被 deny（死循環）⟹ 必須 surface。
- **snapshot_write 蓋章 fail-soft**：此刻 snapshot **已落盤成功**（`create_snapshot` 已持久化、ProjectRegistry 已註冊）。若因 ledger 蓋章（純事後紀錄）失敗而讓整個 snapshot_write 回 error，會**謊報使用者的真實工作失敗**——這比「ledger 不完整」嚴重。⟹ 磁碟蓋章 `except OSError` 吞掉，仍回 snapshot 結果。
- 🔴 **但回傳 ledger 不靠剛失敗的磁碟寫入**（解第一輪審 warning）：`_ledger_with_snapshot_write` 在 disk-stamp 失敗時用**記憶體事實**（sw_details，version_id 等已在手）補上 snapshot_write entry。⟹ 回傳的 `execution_ledger` **永不出現「payload 有 version_id、ledger 卻漏報 snapshot_write」的自相矛盾**。fail-soft 只影響**磁碟 checklist**（日後查詢可能缺本關，那是真實狀態），不影響**本次回報的誠實完整性**。

### 3.4 ledger 形狀（範例）
snapshot_write 成功回應 `execution_ledger`：
```json
[
  {"stage": "edge_residue", "stamped_at": "2026-06-10T08:00:00+00:00", "node_count": 1431},
  {"stage": "snapshot_write", "stamped_at": "2026-06-10T08:01:12+00:00",
   "version_id": "8de9b18...", "label": "v1.0.0", "feature_count": 18, "relation_count": 5}
]
```
- 「是否執行」＝該 stage 是否出現在 ledger（有戳＝執行過）。
- 「產物」＝snapshot_write 的 version_id/label；edge_residue 的 node_count。
- 「結果」＝feature_count/relation_count（inherit 模式為合併後總數，與既有 payload `feature_count` 同語義、非本次 delta；不引入新謊）。
- **不含 covered_nodes**（數千字串）。
- 🔴 **誠實邊界（軸3）**：ledger 是「**已記錄的事實**」（各關曾執行＋當時產物），**非新鮮度宣稱**。edge_residue 的 stamped_at/node_count 可能來自更早的 run（staleness 偵測 C2 已 deferred）。agent 據此轉述時**不得暗示「現時最新」**，只據實陳述「各關於何時執行、產物為何」。

---

## 4. 向後相容 / 遷移
- 既有 codebase 的 checklist 只有 edge_residue stage：C6 後第一次 snapshot_write 即補上 snapshot_write stage；ledger 自然顯示兩關。無需遷移動作。
- `stamp_stage` 簽章變更對所有現有呼叫向後相容（皆顯式傳 covered_nodes）。
- snapshot_write 回應新增 `execution_ledger` 鍵＝純加法；既有消費者（viewer 不讀此工具回應；CLI 經 store）不受影響。⚠ plan 須掃既有整合測試是否對 snapshot_write payload 做**精確鍵集**斷言（加法鍵會破壞 exact-equality）。
- ⚠ **新副作用（軸5）**：snapshot_write 現在會寫 `<codebase>/.the-door/checklist.json`。blast radius 與既有 `create_snapshot`（本就寫同一 `.the-door/`）相同。**plan 須驗**：既有 snapshot_write 相關測試（`test_mcp_flow_guard`/`test_snapshot_write_checkpoint_e2e`/`test_incremental_source_nodes`/`test_v105_incremental_flow` 等）皆對 **tmp 或 copytree 副本**跑，無對 checked-in fixture／dogfood `.the-door` 跑而被寫入污染（承 T2 fixture 污染教訓）。

---

## 5. 測試（spec 層；plan 細分 task）

**checklist 模組（單元）**：
- C6-1 `stamp_stage(..., covered_nodes=None, details={...})`：entry 含 stamped_at＋details 鍵，**不含** node_count/covered_nodes。
- C6-2 `stamp_stage` 既有 edge_residue 呼叫（傳 covered_nodes=list）行為不變（node_count/covered_nodes 仍寫）＝回歸保護。
- C6-3 `read_ledger` 缺檔/壞檔 → `[]`。
- C6-4 `read_ledger` 投影：edge_residue+snapshot_write 兩 stage → 依 STAGE_ORDER 排序、各 entry 含 `stage` 名、**covered_nodes 被剝除**、node_count 保留。並驗對「無 covered_nodes 鍵的 snapshot_write stage」投影**不 KeyError**（非破壞移除）。
- C6-5 `read_ledger` 未知 stage（如 "future_stage"）→ 附在已知 stage 之後（向前相容）。

**snapshot_write 工具（單元／E2E）**：
- C6-6 `execute()` 成功（direct 模式）→ 回應含 `execution_ledger`，內含 `snapshot_write` stage（version_id/feature_count 等）；checklist 落了 snapshot_write stage。
- C6-7 **磁碟蓋章失敗**（monkeypatch stamp_stage 拋 `OSError`）→ ①**仍回 snapshot 結果**（version_id 在）、不回 error（fail-soft）；②🔴 **`execution_ledger` 仍含 snapshot_write entry**（記憶體事實補回，version_id 一致）——驗回傳 ledger 不與 payload 自相矛盾（第一輪審 warning 的回歸樁）。
- C6-8 整鏈 E2E（input-only fixture→tmp）：先真跑 `edge_residue`（蓋 edge_residue stage）→ 再 `snapshot_write` → `execution_ledger` 兩 stage 齊、edge_residue 在前、無 covered_nodes 陣列。

**回歸**：
- C6-9 既有 C2/C3 gate 測（test_execution_gates）全綠：snapshot_write stage 不影響 gate 對 edge_residue stage 的讀取。
- 既有 test_checklist C2-1..C2-4、test_edge_residue C2-5/5b 全綠（向後相容驗證）。

---

## 6. 終局護欄
- Python 全套 0 failed；新測 C6-1..C6-9 綠。
- 既有 C2/C3/C4 gate 測、checklist/edge_residue 測全綠（向後相容）。
- 真實 codebase 跑 `edge_residue → snapshot_write` → snapshot_write 回應 `execution_ledger` 完整呈現兩關、無 covered_nodes 灌爆。
- 無新增 hook、無 gate 行為改動（production hook diff 空）。

---

## 7. Forward-coherence（against 後續刀）
- **C5（README gate 指回）**：C5 是控制/資訊層的入口指回，與 C6 的 ledger 正交；ledger 的 stage 名（edge_residue/snapshot_write）即 C5 README 可引述的「鏈關卡」清單。✓
- **水平推廣 gate（extract/diff 鏈）**：新 stage 進 checklist 後，`read_ledger` 的「未知 stage 附後」邏輯（C6-5）使 ledger 自動納入，無需改 C6。✓ 已向前相容。
- **完整 staleness**：與 C6 正交（C6 純回報、不判定新鮮度）。✓
