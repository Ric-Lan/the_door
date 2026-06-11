# Design — C7: inherited-description immutability gate — 2026-06-11

> 丙案軌2 下一個 gate。承 handoff_2026_06_11 §4 **#3**、種子
> `2026-06-08-execution-model-control-via-structure-seed.md` §5（張拉受力分配）、
> §7（別把不可達的當可達）、§9.5（行為失敗是結構性、會復發）。
> 流程：spike→spec→雙審→plan→雙審→TDD→ff-merge。

## 1. Problem

丙案 gate（C3/C4）只管「snapshot 順序＋原生 code-exec」。handoff §4 #3 列了兩個
未被結構強制的 agent 行為缺口：

- **#1**「該用 The Door 工具輸出、別自己 grep/ls/Read 挖碼」。
- **#2**「L1 描述要忠實翻譯、不可用 campaign 記憶糊」。

本 session（與前次 dogfood）反覆在這兩點脫鉤、只被使用者人工喊停，坐實 §9.5
「軟層綁不住、自律承諾無效」。

## 2. Spike 結論：兩個行為的可 gate 性，依種子 §5 張拉模型天差地別

種子 §5 把強制力分三層：**剛性桿**（執行序/涵蓋率＝hook 可硬擋）、**柔索**（NL
生成＝hook 只驗結構、不驗語意對錯）、**固有缺口**（純文字/意圖行為＝無工具呼叫可
gate）。

### 2.1 行為 #2 有乾淨的結構性代理 → 可 gate（剛性桿）

失敗形狀具體且可在 spike 中定位：`snapshot_write(inherit_from=...)` 走
`l1_features` **全替換路**時
([snapshot_write_tool.py:254-258](../../../the_door/src/the_door/mcp/tools/snapshot_write_tool.py))，
「All features already in baseline: merge on top」——agent 傳的**每個** feature
都 override baseline，**包括沒變動的**，於是記憶版描述蓋掉 baseline 的忠實描述。
（`updated_features` 路相反：沒傳的自動繼承，agent 碰不到——所以 gate 只需處理
全替換路把未變動 feature 一起重寫的情形。）

規則「繼承的不譯」可化為**純結構斷言**：*非 affected 的 feature，其寫入描述必須
等於 baseline 描述*（字串/雜湊比對 + 集合成員）——**不是語意判斷**。完美落在剛性
桿，不碰柔索。

前提：`analyze_changes` 已算出 `inherited_features`（未變動，含 description）與
`affected_features`（變動），但**不蓋 checklist**——affected-set 與 baseline 描述
未持久化到 hook 能讀的地方。補上即可 gate。

### 2.2 行為 #1 基本上是固有缺口 → 不建 blocking gate（明文判定）

無法乾淨區分「為 re-derive Door 輸出而 grep」與「正當讀碼」。硬擋 Read/Grep/Bash
會 brick 正常工作。種子 §7 明文：「指望 hook 鎖『先讀文件』… hook 攔不到」「別把
不可達的當成可達」；守則#2 拒冗餘軟層。**結論：#1 不建 gate**；其結構性回應是
observability（種子 §4 原則7 / C6 已做）＋人工。本設計把此判定明文寫入，避免未來
重複嘗試不可達的東西。

## 3. Decision

只建 **#2 gate（代號 C7）**，#1 明文判定為固有缺口（不建 gate）。

C7 沿用既有 C2/C3 機制（checklist stamp + 同一個 PreToolUse hook），分兩件：

### 3.1 `analyze_changes` 蓋 checklist（新 stage）

在 `analyze_changes_tool.execute` 蓋章。**蓋章點必須在 `diff = result.diff` 綁定
之後、最終 `return wrap(payload, ...)` 之前的 post-pipeline 區塊內**——絕不可落在
兩個 early-return（`_decision` source-path-broken CHECKPOINT 於
[analyze_changes_tool.py:123](../../../the_door/src/the_door/mcp/tools/analyze_changes_tool.py)，
與 `result=null` re-prompt）上，那兩條沒有 `diff`，誤蓋會 NPE 或蓋出空 stage 讓
gate 誤信。`stamp_stage(..., stage="analyze_changes", ...)` details 記：

- `affected_features`: `[af.feature_id for af in diff.affected_features]`
  （合法可重寫的集合；資訊性 + 供 deny 訊息）。
- `inherited_hashes`: `{fs.feature_id: sha256(fs.description.encode("utf-8"))
  .hexdigest() for fs in diff.inherited_features}`——未變動 feature 的**描述**指紋
  （lean，不存全文）。這組 key **就是**「非 affected 的 baseline feature」集合，
  是免疫檢查的核心。
- `baseline_version_id`: `diff.baseline_version_id`。
- `baseline_ref`: agent 傳入的原始 `baseline` 字串（供 hook 盡力比對 inherit_from
  一致性，見 4.3 邊界）。

> **窮舉不變量（免疫無洞的根據）**：`compute_affected_features`
> ([feature_attribution.py:91-108](../../../the_door/src/the_door/core/diff/feature_attribution.py))
> 對 **每個** `baseline.l1_snapshot.values()` 二分——非 affected 即 inherited（else
> 分支）——故 `inherited_features ∪ affected_features == baseline 全集`。因此 key off
> `inherited_features` 不漏任何未變動 feature；`inherited_features` 又直接帶
> `description`（免去重讀 baseline）。一條 contract 測釘住此不變量。

> **僅雜湊 `description`（範圍決定）**：「繼承的不譯」的主面是 `description`。`label` /
> `trigger_description` 的記憶漂移**刻意不納入** C7（保持 gate 最小、單一關注）。若日後
> 需擴，改雜湊不可變欄位的 canonical 串接即可——本刀不做。

蓋章 fail-soft（`except OSError: pass`，比照 snapshot_write 的 C6 蓋章）——
analyze_changes 的真實產物是回傳的 diff，不因控制面蓋章 I/O 失敗而謊報失敗。

> **read-only 註記**：analyze_changes 仍不改 snapshot/source；新增的只是**控制面**
> checklist stamp（`.the-door/checklist.json`），與 edge_residue/snapshot_write 蓋章
> 同性質。docstring 的「read-only」改述為「不改 snapshot/source；蓋控制面 stage」。

### 3.2 同一個 hook（`c3_gate_snapshot_write.py`）擴 check #5

在現有 existence/currency/coverage/staleness 之後，加 **#5 inherited immutability**，
**僅當 `snapshot_write` 帶 `inherit_from`** 時 engage。**C7 是純內容免疫檢查、不附加
順序要求**（刻意不強制「先跑 analyze_changes」——那會誤殺正當的 inherited write，如
re-label baseline / fresh checkout 無 diff 需求，違反 §2.2 反過度 gate）：

1. 讀 checklist 的 `analyze_changes` stage。**缺 stamp → fail-open（跳過 #5、放行）**
   ——無蓋章＝無法確證哪些 feature 未變動，寧缺勿誤殺。
2. **baseline 一致性閘**：stamp 的 `baseline_ref` 必須 == 本次 `inherit_from` 字串
   （hook 是 stdlib-only、無法把 label/tag/date 解析成 version_id；只能字串盡力比）。
   **不等 / stamp 缺 `baseline_ref` 欄 → fail-open（跳過 #5）**——蓋章對的可能是別的
   baseline，不可據以誤殺。
3. 上兩關通過後，對每個寫入 feature（`l1_features ∪ updated_features`）取
   `(feature_id, description)`。若 `feature_id ∈ inherited_hashes`（未變動 baseline
   feature）：`sha256(寫入描述.encode("utf-8")).hexdigest()` 必須 == 蓋章 hash，否則
   **deny**：「你重寫了未變動 feature `<fid>` 的描述（繼承的不譯）；請從 `l1_features`
   省略它（讓它繼承）或保留 baseline 原文。」
4. affected-set 內、或不在 `inherited_hashes`（全新 feature）→ 放行。
5. hook 維持 stdlib-only（加 `hashlib`）；**所有缺欄/解析不確定一律 fail-open**
   （缺 `codebase_path` / 無 inherit_from / 無 description 欄 / 缺任何 stamp 欄）——
   deny 只發生在「stamp 齊全、baseline_ref 相符、且確有未變動 feature 被改寫」的
   positive 違規。hook 任何分支都不得 crash（exit≠0 會 brick 寫入）。

> **stamp 新鮮度不相關**：`inherited_hashes` 綁的是 `baseline_version_id`（不可變的
> 過去 snapshot），不是 live 檔。只要第 2 關 `baseline_ref` 相符，stamp 多舊都無妨
> ——§4.3 的 baseline-match 是唯一權威，無 staleness 概念（對比 edge_residue 指紋
> live 檔需 staleness 檢查）。

`snapshot_patch` 也走此 hook，但它寫 `source_nodes_by_feature`（無 description）→
無寫入描述可比 → check #5 自然 no-op。

### 3.3 drift-pin

新常數入 `core/checklist.py`（`STAGE_ANALYZE_CHANGES`、`FIELD_INHERITED_HASHES`、
`FIELD_AFFECTED_FEATURES`、`FIELD_BASELINE_VERSION_ID`、`FIELD_BASELINE_REF`），
`STAGE_ORDER` 補 `analyze_changes`（排在 edge_residue 前）。hook 複製的字面值由
`test_execution_gates.py` 既有 drift 測釘樁。

## 4. 邊界與風險（誠實標明）

### 4.1 全替換路才會被擋；`updated_features` 路本就安全
gate 只在「寫入描述 != baseline 且該 feature 未變動」時 deny。走 `updated_features`
（省略未變動者）的正規增量路永遠通過——gate 實際是把 agent 推向正確的增量寫法。

### 4.2 正當修正舊 baseline 描述會被擋（接受）
若 agent 想修一個本身被記憶糊的舊 baseline 描述，C7 會擋——但那本就該是獨立刻意的
動作（符合「繼承的不譯」）；可透過把該 feature 納入 affected（或不用 inherit）達成。

### 4.3 baseline 一致性只能盡力（fail-open 邊界，§3.2 第 2 關）
hook 是 stdlib-only、無法把 `inherit_from`（label/tag/date）解析成 version_id。
若 agent `analyze_changes(baseline=A)` 後卻 `snapshot_write(inherit_from=B)`（B≠A），
蓋章 hash 對的是 A。緩解：hook 比對 `inherit_from` 字串 == 蓋章 `baseline_ref`；
**相等→套用免疫檢查；不等 / 缺 baseline_ref 欄 / 缺 stamp→fail-open 跳過 #5**（寧缺
勿誤殺，比照既有 hook 的 deferred 案例）。常見單鏈同 ref 的情形完全涵蓋。**deferred
邊界**：B 與 A 字串不同但實指同一 snapshot（例 label vs SHA）時，免疫檢查不啟動
（漏網，非誤殺）——可接受，因為這不會 brick 合法工作。

### 4.4 currency / staleness 對 analyze_changes stamp
analyze_changes 蓋章記的是對「過去 baseline snapshot」算的 hash——baseline 不會變，
無 source-staleness 問題（不像 edge_residue 指紋 live 檔）。contract_version 由
`stamp_stage` 統一蓋（既有 currency 檢查涵蓋）。

### 4.5 Economy
單次記憶糊是否值得一個 gate？依丙案 §9.5（行為失敗結構性、會復發）＝是。增量小：
一個 stamp 呼叫 + 一條 hook check，落在已驗證的 C2/C3 機制上，零新基礎設施。

## 5. Scope

In:
- `core/checklist.py`（新常數 + STAGE_ORDER）。
- `mcp/tools/analyze_changes_tool.py`（成功路徑蓋 analyze_changes stage；docstring）。
- `.claude/hooks/c3_gate_snapshot_write.py`（check #5 + `_written_descriptions`
  helper + hashlib）。
- 測試：hook 單元（G-系列新案）、checklist stamp 單元、analyze_changes stamp 整合、
  drift-pin 補新常數。
- `CLAUDE.md`：在 gate 說明補 C7 一行；#1 固有缺口判定一行（避免未來重試）。

Out:
- 行為 #1 的任何 blocking gate（明文判定為固有缺口）。
- 改 snapshot_write 工具的合併語意（gate 只觀察、不改寫）。
- L2/L3 描述（同一原則可後續水平推廣，本刀不做）。
- 純加法，`SNAPSHOT_CONTRACT_VERSION` 不 bump（契約 §6）。

## 6. Verification

**Deny（唯一的 positive 違規路）：**
- agent 走 `l1_features` 全替換、stamp 齊全且 baseline_ref 相符、重寫一個未變動
  feature 描述 → **deny**，訊息點名 feature_id + 教學。

**Allow（含全部 fail-open 安全閥，每條斷言 exit 0、不 brick）：**
- agent 走 `updated_features` 正規增量路（省略未變動者）→ 通過。
- agent 全替換但未變動 feature 描述逐字等於 baseline → 通過。
- inherit_from 但**無 analyze_changes 蓋章** → fail-open 放行（不強制順序）。
- stamp 存在但**缺 `baseline_ref` 欄**（舊 stamp）→ fail-open 放行（不 KeyError/crash）。
- inherit_from 字串 **!= 蓋章 baseline_ref** → fail-open 放行。
- affected-set 內的 feature 自由重寫 → 通過。
- 全新 feature（不在 inherited_hashes）→ 通過。
- snapshot_patch（無 description）→ 不受 #5 影響。
- snapshot_write **無 inherit_from**（direct/首次）→ 不 engage #5。

**蓋章正確性：**
- analyze_changes 成功 → checklist `analyze_changes` stage 含 inherited_hashes /
  affected_features / baseline_version_id / baseline_ref。
- analyze_changes 走 `_decision` CHECKPOINT early-return（source-path-broken /
  result=null）→ **不蓋** analyze_changes stage（蓋章只在 post-pipeline 區塊）。
- contract 測釘住 `inherited ∪ affected == baseline` 不變量。

**回歸：** 全套 `python -m pytest` 綠、drift 測涵蓋新常數。
