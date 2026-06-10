# staleness-detection spec：mtime+size 指紋 staleness gate（丙案 軌2 收尾）

> 承接：C2 spec `2026-06-09-C2-checklist-schema-gate-spec.md` §2.5（誠實 deferred 宣稱）、
> 水平推廣（`2026-06-10-horizontal-gate-*`）。
> C2 把 C3 的 artifact-存在性升級成 versioned checklist + node-coverage(validity) + currency，
> 但**明確 deferred**「完整 staleness」：node-coverage **擋不到**程式**刪除**或**原地修改**
> （node_id 不變、body/edges 變）的漂移（C2 spec §2.5 🔴）。
> **本刀 = 兌現該 deferred 的兩個具名案**，在不重抽 AST 的硬約束下，用 **per-file (mtime_ns, size)
> 指紋**讓 gate 偵測「edge_residue 蓋章後程式是否變動」。

---

## 0. spike（已對真實碼驗，事實寫入；不需事後再驗）

| 事實 | 來源 file:line | 對設計的影響 |
|---|---|---|
| C2 deferred 的具名 staleness 案＝**刪除**＋**原地修改**（node_id 不變）；node-coverage 子集檢查皆通過 | C2 spec §2.5（`...C2-checklist-schema-gate-spec.md:109-112`） | 本刀目標＝這兩案；機制不可重抽 AST |
| edge_residue 已 `ASTExtractor().extract()`，`extraction.files`＝`list[FileInfo(path, language)]`，**path 為相對路徑、現成可用** | `mcp/tools/edge_residue_tool.py:36`、`models/extraction.py:7-12`、`core/extraction/file_discovery.py:80,92` | 記每檔指紋零額外抽取成本；只需對每檔 `stat()` |
| `read_bytes()` 不改 mtime；蓋章時 stat 反映「最後一次寫入」 | `ast_extractor.py:161` | 蓋章後 agent 用 Edit/Write 改檔 → mtime 必升 → gate 偵測得到 |
| FileInfo.path 為 **OS-native 分隔符**（`str(rel_dir / fname)`） | `file_discovery.py:80` | checklist 為 per-codebase working-state、同機產讀；hook `os.path.join(codebase_path, relpath)` 同 OS 一致；checklist 非跨平台可攜（重生即可），不需正規化 |
| **`.the-door/*.json`（checklist/edge-residue 自產物）不進 `extraction.files`**：file_discovery 只收 `_EXTENSION_MAP` 內的**原始碼副檔**（`.py`/`.ts`…，**無 `.json`**）→ `language=None` 即 skip | `file_discovery.py:11-29,88-90` | edge_residue 寫自己的 `.the-door/*.json` **不會**被登記為被追蹤檔 → 無「edge_residue 後第一個 snapshot_write self-deny stale」死鎖。**保護來自副檔名過濾、非目錄排除**（`.the-door/` 不在 `_DEFAULT_IGNORE_PATTERNS`，但其內容皆 .json） |
| **測試 fake `_fake_extraction` 只給 `edges`+`nodes`、無 `files` 屬性** | `tests/unit/mcp/tools/test_edge_residue_tool.py:28-34` | 新增 `for fi in extraction.files` 迴圈會在所有 monkeypatched 測（T-1/T-2/T-5/C2-5/C2-5b）`AttributeError`。**plan 須更新 fake 加 `files=[]`（誠實鏡像真實 `ExtractionResult` 形狀）；production 不用 getattr 防禦**（`ExtractionResult.files` 有 default_factory、真實路徑恆有，getattr 會掩蓋形狀不符） |
| C2-5 E2E 用 **field-access 子集斷言**（非 exact-dict 等值） | `test_edge_residue_tool.py:124-128` | 新增 `source_files`/`file_count` 鍵**不破** C2-5（子集斷言）；唯一回歸點＝上一列的 fake `files` 屬性 |
| checklist 寫入側單源＝`core/checklist.py:stamp_stage`，已支援 `covered_nodes`(+`node_count`)＋`details` | `core/checklist.py:52-96` | 加 `source_files` 為**第三個 first-class optional 參數**，鏡像 covered_nodes 形狀 |
| `read_ledger`（C6）已 strip 龐大 `covered_nodes` 只留 `node_count` | `core/checklist.py:99-125` | source_files 也龐大（每檔一筆）→ read_ledger **必須** strip（鏡像 covered_nodes pop；否則 C6 ledger 被檔案清單淹沒＝read_ledger 存在目的被破壞）。**不另存派生 `file_count`**（投機欄位、會與 dict 漂移；C6 若要檔數，後續刀於 read_ledger 自 `len` 算） |
| gate hook 為 **stdlib-only standalone**（不上 the_door PYTHONPATH）；fail-open on 無法解析、deny 走 `stderr.buffer`（cp950 安全） | `.claude/hooks/c3_gate_snapshot_write.py:35-37,49-59` | staleness 判定須 hook 內 stdlib 自足（`os.stat`）；欄位名以釘樁測對齊 |
| settings.json 已註冊 c3 hook on `snapshot_write` **與** `snapshot_patch` | `.claude/settings.json:22-39` | **不需改 settings**（同一 hook） |
| `st_mtime_ns`＝int、`st_size`＝int | stdlib `os.stat_result` | JSON-exact（避開 float 等值比對陷阱）；單次 stat 同時得兩者 |
| `SNAPSHOT_CONTRACT_VERSION = "1"`；前 4 刀皆純加法不 bump | `models/snapshot.py:12`、`docs/contract-versioning.md` §6 | 本刀新增欄位＋缺失優雅退化＝純加法 → 不 bump |

### spike 校正 / 機制定案（證據定方案，不帶選項問使用者）
- **mtime+size（stat-only）勝 content-hash**：兩者皆不重抽 AST（守硬約束），但 stat-only **不讀 bytes** ⟹ 對 PreToolUse 阻塞 hook 更便宜（數千檔 <100ms）。size 補 mtime 粗解析度（極罕見的「同秒改寫、mtime_ns 未變」由 size 變化兜住）。
- **fail-safe 方向**：mtime 在 git checkout/pull 重置時會 false-positive（內容相同卻判 stale）；但方向安全＝過度 deny → 重跑零-key/確定性 edge_residue 自癒，無資料損失。對比 false-negative（改了卻沒判 stale）只在「改檔後人為重置 mtime 且 size 不變」的對抗情境，非正常工作流。
- **最強價值案**：agent 可只跑一次 edge_residue，然後跨多次編輯持續 snapshot_write，只要 node_id 子集成立就一路過 coverage。mtime 指紋關掉這個＝兌現「改碼後必重跑 edge_residue」的軌2 紀律。

---

## 1. 目標與非目標

**目標**：在 C2 checklist gate 上加第 4 道檢查 **staleness**，偵測 edge_residue 蓋章後被追蹤檔案的
**刪除**與**原地修改**，兌現 C2 spec §2.5 兩個具名 deferred 案，**不重抽 AST**。

1. `edge_residue` 蓋章時，額外記錄每個已發現檔案的 `(st_mtime_ns, st_size)` 指紋 → checklist
   `stages.edge_residue.source_files`。
2. C3 gate hook 新增 staleness 檢查：對 `source_files` 每筆 `stat()`（檔案缺失→deny 刪除；
   mtime_ns/size 變→deny 原地修改）。deny 訊息指回 `edge_residue`＋單一權威（沿用 C5 deny 尾段）。
3. `read_ledger`（C6）strip `source_files`、保留派生 `file_count`（C6 回報「涵蓋 N nodes / M files」）。

**誠實涵蓋宣稱（精確，不可誇大為「完整 staleness」）**：本刀關掉 §2.5 **兩個具名 deferred 案**
（刪除＋原地修改）＝C2 留下的主缺口。**仍 honest-deferred 的殘餘**（§2.5 之外、列入非目標）：
- **新增未追蹤檔**且其 node **未被任何 source_node 引用**：stat-loop 只掃「已記錄檔集」看不到新檔；
  該檔的 edges 會讓 residue 略 stale，但偵測需在 stdlib hook 內複刻 file-discovery 的 ignore 規則
  （脆弱、易與 `FileDiscovery` 漂移）。被引用的新檔之 node 已由 node-coverage 擋下。
- **對抗式 false-negative**：改檔後人為把 mtime 重置回舊值且 size 不變。非正常工作流。

**非目標（釘樁，防 gold-plating）**：
- ❌ 不在 gate 重抽 AST／不讀檔 bytes（守硬約束；只 `os.stat`）。
- ❌ 不做 content-hash（stat-only 已涵蓋具名案、更便宜；hash 的精確度增益不抵 byte-read 成本）。
- ❌ 不掃「新增未追蹤檔」（需複刻 ignore 規則於 stdlib hook＝脆弱；honest-deferred、文件化）。
- ❌ 不 bump `SNAPSHOT_CONTRACT_VERSION`（純加法＋缺失優雅退化）。
- ❌ 不改 settings.json（同一 c3 hook 已掛 snapshot_write＋snapshot_patch）。
- ❌ 不碰 C4／edge-residue.json 既有結構／node-coverage 既有語義（staleness 為**新增**第 4 檢查）。

---

## 2. 設計

### 2.1 checklist schema 增補（純加法）
```json
{
  "contract_version": "1",
  "stages": {
    "edge_residue": {
      "stamped_at": "...",
      "node_count": 1431,
      "covered_nodes": ["..."],
      "source_files": { "the_door/src/.../foo.py": [1739812345678901234, 5123], "...": [m, s] }
    }
  }
}
```
- `source_files`＝`{ relpath: [mtime_ns, size] }`（OS-native relpath，同機產讀）。
- **不存派生計數欄**（剔投機欄位）；C6 ledger 需要時於 read_ledger strip 前 `len` 自算（本刀不預作）。
- **缺 `source_files`（舊 checklist）→ gate staleness 檢查 skip**（向後相容、優雅退化；見 §3）。

### 2.2 `core/checklist.py`（寫入側單源）
- 新欄位常數：`FIELD_SOURCE_FILES = "source_files"`（**不**加 file_count 常數）。
- `stamp_stage(...)` 加 **first-class optional 參數** `source_files: dict | None = None`（鏡像 `covered_nodes`）：
  - 給定時：寫 `source_files`（原樣 dict）。
  - 預設 None：不寫（既有 caller 零 churn、向後相容）。
- `read_ledger(...)`：`entry.pop(FIELD_SOURCE_FILES, None)`（非破壞、鏡像既有 `covered_nodes` pop）。
  既有 `node_count` 投影不變。

### 2.3 `edge_residue` 工具：蓋章時記指紋
`edge_residue_tool.execute()` 蓋章前計算：
```python
root = Path(codebase_path)
source_files = {}
for fi in extraction.files:
    try:
        st = (root / fi.path).stat()
    except OSError:
        continue  # 發現後到 stat 間檔案消失：跳過（fail-soft）
    source_files[fi.path] = [st.st_mtime_ns, st.st_size]
stamp_stage(codebase_path, STAGE_EDGE_RESIDUE,
            covered_nodes=covered, source_files=source_files,
            contract_version=SNAPSHOT_CONTRACT_VERSION)
```
- 用 `extraction.files`（**所有已發現檔**，含 parse 失敗者）＝正確 superset：修 parse error 也改結構，應觸發 stale。`.the-door/*.json` 因副檔名過濾不在其中（§0 spike），故無自產物 self-staleness。
- 既有 edge-residue.json 行為、payload 既有欄位不變（可選：payload 增 `file_count` 可觀察——plan 決定，非必須）。
- **production 直接 `extraction.files`（不 getattr 防禦）**；測試 fake 須補 `files`（§0 spike 末二列；plan Task 列為回歸更新）。

### 2.4 C3 hook：新增 staleness 檢查（stdlib 自足）
在既有 ①存在 ②currency ③coverage 之後，加 **④staleness**：
```python
FIELD_SOURCE_FILES = "source_files"   # 釘樁對齊 checklist 模組
src_files = stage.get(FIELD_SOURCE_FILES)
if isinstance(src_files, dict):
    for rel, fp in src_files.items():
        full = os.path.join(codebase_path, rel)
        try:
            st = os.stat(full)
        except OSError:
            return _deny(... rel + " 已刪除/移動 ..." )          # 刪除
        if not (isinstance(fp, list) and len(fp) == 2):
            continue                                              # 壞筆：跳過（fail-soft）
        if st.st_mtime_ns != fp[0] or st.st_size != fp[1]:
            return _deny(... rel + " 自 edge_residue 後已變動 ..." )  # 原地修改
```
- `source_files` 缺（舊 checklist）→ **skip staleness**（向後相容；coverage/currency 仍照常）。
- deny 訊息沿用既有 `teach`（指回 `edge_residue`＋C5 單一權威尾段），主詞 tool-aware（`label`）。
- 順序置於 coverage **之後**：agent 新增 node 時 coverage 訊息（「node 不在涵蓋範圍」）較具體先講；
  純刪除/原地改（coverage 通過）由 staleness 兜住＝本刀新增的偵測面。
- engage 條件不變（沿用既有 `if tool_short == "snapshot_patch" and not src: return 0`）：
  metadata-only patch 仍豁免；snapshot_write 恆 engage（含 inherit-only，此時 staleness 仍跑＝
  「宣稱沿用 baseline 但程式已變」正是該擋的高價值案）。

### 2.5 向後相容 / 遷移
- 舊 checklist（無 `source_files`）：staleness skip，行為＝C2 現狀（不回歸）。重跑一次 `edge_residue`
  即補上指紋、啟用 staleness。**刻意不做「舊形狀就放行」以外的特例**。文件化為遷移註記。
- dogfood 本 repo `.the-door/`：同理，重跑 edge_residue 即補。

---

## 3. 測試（spec 層；plan 細分 task）

**checklist 模組（單元）**：
- S-1 `stamp_stage(..., source_files={...})` 寫 `source_files`（原樣）；既有 covered_nodes/node_count 不受影響。
- S-2 `read_ledger` strip `source_files`、保留 `node_count`（C6 不被淹沒）；無 KeyError。
- S-3 `stamp_stage` 不給 source_files → entry 無 `source_files` 鍵（向後相容、既有 caller 零 churn）。

**edge_residue 蓋章（E2E，copytree fixture→tmp，守 fixture-input-only）**：
- S-4 `execute()` 跑完，`stages.edge_residue.source_files` 對每個 `extraction.files` 檔案＝磁碟上
  真實 `[st_mtime_ns, st_size]`；既有 covered_nodes/contract 不回歸。

**gate hook（黑箱 subprocess，producer↔reader honesty：用真實 stamp_stage＋真實磁碟檔）**：
- S-5 檔未變動（stamp 後不動）→ allow(rc0)。
- S-6 被追蹤檔**原地修改**（改寫使 size 變、mtime 升）後 → deny(rc2)，stderr 提變動／edge_residue。
- S-7 被追蹤檔**刪除**後 → deny(rc2)，stderr 提刪除／edge_residue。
- S-8 checklist 無 `source_files`（舊形狀、coverage 通過）→ staleness skip → allow(rc0)（向後相容）。
- S-9 `source_files` 含壞筆（非 `[int,int]`）→ 該筆跳過、其餘正常（fail-soft；不誤 deny 合法呼叫）。
- S-10 inherit-only（無 source_nodes）但被追蹤檔已變動 → deny(rc2)（高價值案：沿用 baseline 卻程式已變）。
- S-12 **snapshot_patch**（帶 `source_nodes_by_feature`）＋被追蹤檔已變動 → deny(rc2)（共用 hook 的 patch 面 staleness 對稱守，補水平推廣的 patch 顯式覆蓋）。

**釘樁（防 drift）**：
- S-11 讀 hook 原始碼文字，assert `core/checklist.py` 的 `FIELD_SOURCE_FILES` 值字串出現在 hook 中；
  延伸既有 C2-15 的欄位名釘樁清單（含既有負向控制 `__nonexistent_field__` 不回歸）。

**回歸（明確區分兩類）**：
- **手搓 stamp 測**（C2/水平推廣，stamp 不帶 source_files）：因「staleness skip-when-absent」全數不回歸＝向後相容硬證據。
- **真實 extract 測**（T-1/T-2/T-5/C2-5/C2-5b，走 monkeypatched edge_residue）：因新增 `for fi in extraction.files`
  迴圈，**需更新 `_fake_extraction` 加 `files=[]`**（§0 spike）。C2-5 子集斷言不因新鍵破壞。plan 列為回歸更新 task。

---

## 4. 終局護欄
- Python 全套 0 failed；新測 S-1..S-12 綠。
- `edge_residue` 跑後 `.the-door/checklist.json` 的 `stages.edge_residue.source_files` 非空、
  指紋 == 磁碟真實值（真實 codebase）。
- C3 hook：未變動→allow；原地改/刪除→deny；舊形狀→skip(allow)；fail-open 守則保留。
- 既有 C2/C3/C4/C5/C6/水平推廣測全綠（不回歸）。
- `SNAPSHOT_CONTRACT_VERSION` 仍 `"1"`（純加法）。

---

## 5. Forward-coherence
- **C6（回報）**：read_ledger 已 strip source_files、保留 node_count；C6 若要回報檔數，後續刀於 read_ledger
  `len(source_files)` 自算即可（本刀不預作派生欄＝不 gold-plate）。✓
- **未來 content-hash 升級**（若真有需求）：`source_files` 值是 list，可擴成 `[mtime_ns, size, sha]`；
  hook 對長度 `>= 2` 容忍（S-9 已釘 fail-soft 不嚴格等長）→ 向前相容。✓
- **誠實邊界**：殘餘 deferred（新增未追蹤檔未被引用、對抗式 mtime 重置）已於 §1 非目標明列、文件化。
