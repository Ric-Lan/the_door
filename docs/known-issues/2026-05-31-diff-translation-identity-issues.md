# 已發現問題記錄：差異比對的「身分」與「翻譯」耦合問題

> **狀態**：已確認真實存在，**暫不處理**。等重構階段完成、或判斷有必要時撈出來修。
> **發現時機**：2026-05-31，以 The Door 對自身（the_door v1.5.6）做 dogfood、
> 鋪設重構分析 baseline 時撈到。當時尚未正式開始重構，屬基礎建設階段。
> **發現脈絡**：合並 v105 store 的歷史 snapshot（v1.0.0/v1.0.5/v1.2.2）與當前
> 重新抽取的 v1.5.6 成單一時間軸後，檢視 v1.2.2→v1.5.6 差異頁時浮現。

---

## 根因（貫穿問題 ② 與 ④）

**L1 feature 的「身分」與「變更判定」綁在自由文字（feature_id 命名 + 翻譯
label/description），而不是綁在結構（source_nodes）。**

證據 — `the_door/src/the_door/core/diff/diff_engine.py` 第 91–98 行，matched 分支：

```python
# Matched: in both — compare label and description
for fid in baseline_map:
    if fid in current_map:
        b_feat = baseline_map[fid]
        c_feat = current_map[fid]
        if b_feat.label == c_feat.label and b_feat.description == c_feat.description:
            state = "unchanged"
        else:
            state = "attribute_changed"
```

整段**只比對 label / description 文字相等性，完全沒有比對 source_nodes**。
變更與否因此取決於翻譯措辭，而非程式碼結構。

（補充：`dependency_changed` 來自 step 4 的 edge/relation 結構比對，那段是
確定性的；問題只在 feature 本身的 added/removed/attribute_changed 判定。）

---

## 問題清單

### ② 未執行舊資料繼承 → 新版資料與舊版看起來完全無關

- **現象**：新版 snapshot 出來後，與舊版在差異頁上幾乎零連續性（大量 removed +
  大量 added），看不出演進。
- **根因**：feature_id 斷裂。產生 v1.5.6 時走 fresh `snapshot_write`（未帶
  `inherit_from`），且採用了另一套 feature_id 命名
  （舊 `feat-cli-dispatch` → 新 `feat-cli-surface`、舊 `feat-llm-pipeline`
  → 新 `feat-pipeline`、舊 `feat-mcp-server` → 新 `feat-mcp-surface` 等）。
  diff engine 以 feature_id 為身分鍵，認 id 不認語意 → 舊 id 全判 removed、
  新 id 全判 added。
- **實測**：v1.2.2(13 feat) → v1.5.6(18 feat)，僅 5 個 feature_id 重疊
  （feat-ast-extraction / feat-timeline / feat-topology / feat-ui-server /
  feat-validation），8 removed、13 added。那 8 個「移除」在 v1.5.6 其實都還
  存在，只是換了 id。
- **既有機制**：The Door 本就有繼承路徑
  （`analyze_changes` → `snapshot_write(inherit_from=...)`），設計目的正是讓
  未變 feature 沿用舊 id + 沿用舊翻譯。本次跳過了它。
- **本次 dogfood 的額外限制**：v1.2.2 來自 the-door-v105 凍結副本（源碼 1.0.5），
  與 v1.5.6 的當前源樹是**不同 source tree、不同 node_id 命名空間**，繼承
  無法自動對映。要乾淨示範繼承，須從**同一個 repo** checkout 舊 git tag 重生歷史。

### ③ 差異頁詳情面板應顯示「舊版名 vs 新版名」

- **訴求**：diff 卡片 label 用新版沒問題，但點進**詳情**時，對 changed 的
  feature 應能並陳「舊版名稱 vs 新版名稱」。
- **可行性**：✅ **資料層已就緒，幾乎零成本**。`NodeDiff` 資料模型同時保存
  `baseline_label` / `current_label` / `baseline_description` /
  `current_description`（見 `diff_engine.py` 第 70–106 行，added/removed/matched
  三分支都有填）。目前是 renderer 把它收斂成只顯示 current。
- **性質**：純 viewer 呈現層增強，不動資料模型。**可獨立先做**，不依賴 ②④。
- **前端正式版**：`docs/frontend-local-version-viewer/viewer/`。

### ④ 翻譯敘述漂移 → 無法分辨「真有差異」還是「只是換句話說」

- **現象**：同一個 `feat-ast-extraction`，A/B 版翻譯看起來只是不同敘述形式，
  無法確認該部分是否真的有結構差異。
- **這是最深的 bug，有兩個方向的錯**：
  - **誤報（false positive）**：結構沒變，翻譯換句話說 → 判成
    `attribute_changed`。
  - **漏報（false negative，更危險）**：source_nodes 真的變了，但 label/
    description 文字剛好沒變 → 判成 `unchanged`。**diff 對 matched feature
    根本沒看 source_nodes**，真實結構變動會被漏掉。
- **根因**：同上根因（變更判定綁文字不綁結構）。

---

## 修正方向（② 與 ④ 同一帖藥；③ 獨立）

| 方向 | 解什麼 | 代價 / 動到哪 |
|---|---|---|
| **A. 走繼承路徑** — 未變 feature 沿用舊 feature_id + **逐字沿用舊翻譯**（不重譯），只有結構真變者才重譯 | ② 斷裂 + ④ 誤報 | 需從**同一 repo** 重生歷史；用 `analyze_changes` + `snapshot_write(inherit_from=...)`；不動引擎 |
| **B. diff 改以 source_nodes 結構比對為準** — `attribute_changed` 由 source_nodes（與 relations）集合差決定，翻譯只當註解 | ④ 誤報 **+ 漏報** | 動 `diff_engine.py` matched 分支核心判定邏輯 |
| **C.（③）詳情面板並陳 baseline/current label** | ③ | 純 viewer/renderer，資料已備 |

**待決策**：問題 ④ 的理想解傾向 A（繼承＋沿用舊翻譯）還是 B（diff 看結構）—
這決定動的是「補繼承資料流」還是「改 diff 引擎判定」。A 與 B 不互斥，可並行；
B 能同時解掉 A 解不到的「漏報」。

---

## 關聯既有規格

- `the_door/CLAUDE.md` — 繼承鏈說明（`analyze_changes` → `snapshot_write`
  `inherit_from`）。
- `.kiro/specs/incremental-analysis/` — 增量分析設計，與方向 A 直接相關。
- `.kiro/specs/diff-engine/` — diff 引擎規格，與方向 B 直接相關。

## 重現方式

```
# 1. 確認重疊 / removed / added
#    比對 v1.2.2 與 v1.5.6 兩個 snapshot 的 l1_snapshot keys
# 2. 跑 diff 看 attribute_changed 來源
the-door diff --baseline v1.2.2 ./the_door   # 需 PYTHONUTF8=1 避免 cp950 崩潰
# 3. 讀 diff_engine.py:91-98 確認判定只看文字
```

---

## 方法論／行為準則（dogfood 過程中暴露的 agent 行為問題）

這些不是 The Door 產品的 bug，是執行任務的 agent（Claude）在本次 dogfood 暴露的
行為問題，一併記錄供日後校正。

### M1. 原有路徑斷裂時，必須停下來把決策權交還使用者

- **事發**：正規路徑是 MCP `snapshot_write`，但本 session MCP server 連不上
  （`.mcp.json` 用了壞掉的 `python -m the_door`）。
- **錯誤行為**：agent **默默選擇**繞過——自寫 glue 直接呼叫 `execute()`，
  而非停下來告知使用者並讓其在「(A) 先修 MCP 再用正規工具 / (B) 繞過」之間選擇。
- **準則**：**既有/正規路徑斷裂 = 停下來問，不要默默繞過。** 這類岔路的決策權
  屬於使用者，不是 agent 私自決定的。繞過方案即使可行，也要先攤開讓使用者拍板。

### M2. dogfood 要用專案自己的工具，不要另寫一套取代它

- **事發**：L2 產出時，agent 自寫 `_dogfood_l2.py` 重寫了 module 分組 / interaction
  推導 / anomaly 偵測，而非驅動專案既有的 `L2Generator`（`_build_prompt` → agent
  當 LLM 回答 → `_parse_response` → `_persist`）。
- **後果**：產出低保真（機械按檔分組 + 檔名直譯），且**沒有 dogfood 到工具本身**，
  失去「用自己的產品、暴露產品問題」的本意。
- **準則**：agent-as-LLM 的正解是**驅動工具本人的 prompt/parse/persist，只注入
  agent 的自然語言回答**；不要繞過工具、平行重寫其邏輯。

### 對重構的影響評估（已釐清）

- 重構判斷幾乎只依賴 `the-door extract` 產的 `structure.json`（node 數、edges、
  fan-in/out、dead-code）——那層是真工具高保真輸出，**對重構足夠，不需重新解析**。
- agent 自製的低保真 L1 分組 / L2 翻譯只是 viewer 導覽層，與重構判斷脫鉤；
  其正規重做屬「產品 dogfood」範疇，可延後，不阻擋重構主線。

