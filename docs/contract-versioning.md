# Snapshot 契約版本維護紀律（`SNAPSHOT_CONTRACT_VERSION`）

> **一句話**：改動 snapshot 契約（持久化 schema 或分析語義）時，**必須**手動 bump
> `SNAPSHOT_CONTRACT_VERSION`。忘了 bump 不會報錯——它會**靜默**讓 provenance
> 退化成「全部 current＝真但低資訊」。正因為無法自動偵測，才需要這條人工紀律與本文件。

---

## 1. 這個常數是什麼

- **定義**：`the_door/src/the_door/models/snapshot.py` 的 `SNAPSHOT_CONTRACT_VERSION: str`（現值 `"1"`）。
- **單一來源**：是契約版本的唯一錨點，**不是** package 版本（`1.6.0` 那種是發行噪音、與契約正交）。
- **出生蓋戳**：`core/diff/snapshot_store.py` 的 `create_snapshot()` 是唯一蓋戳點，每個新建快照
  寫入 `contract_version = SNAPSHOT_CONTRACT_VERSION`（出生事實，之後不再改）。
- **衍生**：`core/diff/provenance_membrane.py` 的 `derive_provenance(contract_version)`：
  - `== SNAPSHOT_CONTRACT_VERSION` → `"current"`
  - present 且 `!=` → `"legacy"`
  - `None`（S7 前的舊快照） → `"unknown"`

  此衍生值經 diff／analyze_changes／snapshot_list 三個 MCP 工具投影給 agent。

## 2. 何時要 bump（兩個觸發條件）

當下列任一成立、且「同一份原始碼在改動前後產生的快照應被視為**不同契約**」時，bump：

1. **持久化 schema 變更**：`the_door/schemas/snapshot.schema.json` 改了欄位的**意義或形狀**，
   使得舊快照的解讀方式與新快照不同。
2. **分析語義變更**：同樣的輸入碼，L1/L1.5 分析產出的**意義**改變（例如 feature 切分規則、
   confidence 判準、scope/severity 語義重塑）。

bump 後在 `CHANGELOG.md` 記一行「契約版本 `N` → `N+1`：<原因>」。

## 3. 何時**不**要 bump

- **純發行**（package version bump、CHANGELOG、tag、push）——契約沒動就不動常數。
- **向後相容的純加法**且舊快照解讀**不因此改變**（舊快照缺新欄＝語義不變）。
  - 反例：`contract_version` 欄本身是這樣加進來的——加它時**沒有** bump，因為舊快照
    load 成 `None`＝`"unknown"`、語義誠實未受損。判準是「舊快照的意義有沒有被新契約改寫」，
    不是「schema 檔有沒有被編輯」。
- **重構/內部結構整理**，對 CLI/MCP/viewer 的行為與輸出逐位元不變（如膜 campaign 多數刀）。

## 4. 為什麼是「紀律＋文件」而非「測試」

系統**無法**自動判斷「契約變了沒」——那正是它需要版本戳的原因。
若能機械偵測契約變更，就不需要這個常數了。因此這條規則**不可能**用 unit test 守住
（test 只能釘「新建快照的 `contract_version == SNAPSHOT_CONTRACT_VERSION`」這類機械事實，
見 `tests/unit/core/diff/test_snapshot_contract.py`／`test_provenance_membrane.py`），
落點只能是改動者的判斷 + 本文件 + 兩個變更現場的就地提示（見 §5）。

## 5. 紀律的三個落點（改動現場就會看到）

1. **常數本身**：`models/snapshot.py` 的 `SNAPSHOT_CONTRACT_VERSION` 上方註解。
2. **schema 欄**：`snapshot.schema.json` 的 `contract_version` property `description`。
3. **本文件**：canonical 說明，前兩處交叉指向這裡。

## 6. 出版（release）檢查清單行

把這一行併入出版流程（出版指令／release checklist）：

> **[ ] 契約檢查**：本次釋出有沒有改 `snapshot.schema.json` 的欄位意義，或改 L1/分析語義？
> 有 → bump `SNAPSHOT_CONTRACT_VERSION` 並在 CHANGELOG 記一行；沒有 → 不動。

---

**相關**：S7 provenance through-line spec＝`docs/superpowers/specs/2026-06-06-S7-provenance-throughline-spec.md`（§0/§5 資訊量綁維護紀律的論證）。
