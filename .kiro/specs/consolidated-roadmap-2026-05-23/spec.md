# Consolidated Roadmap — 2026-05-23

四條同時在飛的工作流的單一查閱來源。本文件**不重複**既有 spec/plan 內容，只
作為跨流目錄、依賴對照、與決策紀錄；各工作流的細節仍在原 spec 檔。

---

## 0 · 文件目的

把以下散落在不同 session/handoff/worktree 的工作整合到一個入口：

- 多語言 L1 抽取（spec 已寫完未排程）
- viewer 視覺套用新設計系統（本 session 新增）
- diff 詳情面板重做（spec + plan 已寫完未執行）
- CLAUDE.md → hooks 補強（流程改進）

下個對話讀本檔即可拿到完整現況，不必再追查多份 handoff。

---

## 1 · 工作流總覽

| ID | 工作流 | 既有 artifact | 狀態 | 阻擋 / 被阻擋 |
|---|---|---|---|---|
| **A** | 多語言 L1 抽取 | `.kiro/specs/multilang-node-extraction/spec.md`（worktree `peaceful-bell-8b569a`，未 commit） | spec 已 code-review，未排程實作 | 獨立，不阻擋其他流 |
| **B** | Viewer 視覺套設計系統 | `design/The Door Design System/design_handoff_v1.1.1_diff_visuals/` + 本 session 的 3 個 mockup（`docs/frontend-local-version-viewer/viewer/mockup{,-graph,-mindmap}.html`） | 設計確認 ✅，待寫 plan | **阻擋 C**（兩者都動 DetailPanel）；**前置**：stoic-spence #3 落地 main（見 § 4.2） |
| **C** | Diff 詳情面板重做 | `.kiro/specs/frontend-local-version-viewer/` 內 design.md + tasks.md 的相關章節（worktree `ecstatic-beaver-49806e`） | spec + 3-task plan 寫完，code-review 過，未執行 | 被 **B** 阻擋；同樣前置 stoic-spence #3 落地 main（見 § 4.2） |
| **D** | CLAUDE.md → hooks | 本文件 § 5 + `.claude/settings.json`（待新增） | 設計確認 ✅，待落地 | 獨立 |

git 起點：`main` HEAD `0b353df` + tag `v1.2.1`（本 session 未動 main）。

---

## 2 · 工作流 A — 多語言 L1 抽取

### 2.1 問題（已 grep 驗證）

現況：`the_door/src/the_door/core/extraction/node_builder.py` 的 `_walk()`（line 40-45）只對 python / typescript+javascript 有專屬抽取邏輯：

```
_walk_python      (line 49)
_walk_typescript  (line 264)
_walk_generic     (line 369)   ← 其餘 8 種語言全落到這裡
```

`_walk_generic` 用脆弱的子字串比對（如 `"function_definition" in node.type`），對以下語言近乎全失效：

| 語言 | 真實 tree-sitter node type | 在 _walk_generic 表現 |
|---|---|---|
| Rust | `function_item`, `impl_item` | 完全抓不到 |
| Java | `method_declaration` | 完全抓不到 |
| Ruby | 裸 `method` / `class` | 完全抓不到 |
| C# / Go / PHP / C / C++ | 各自的 specific type | 抓不到或誤判 |

結果：8 種語言的 source nodes 稀疏甚至空 → L1 功能分群失真。

⚠️ 易誤解點：The Door 早就用 tree-sitter（`ast_extractor.py::_init_language_loaders` 已註冊 11 種 grammar），**不是用 Python `ast`**。「多語言支援」≠ 引入新技術棧，指的是「The Door 能正確分析目標專案的多種語言」。**Scope 是通用的**，不限定特定目標語言（已與使用者確認）。

### 2.2 設計（既有 spec 摘要）

完整內容在 `multilang-node-extraction/spec.md`，核心動作：

1. 借用 codegraph（commit `5aae9c4bbff4fe02f8284ef5f91dd9d5391027f6`，MIT）各語言的 tree-sitter node-type 對照表
2. 新增 `language_configs.py`，定義 `LANGUAGE_CONFIGS: dict[str, LanguageConfig]`
3. `LanguageConfig` 含 `function_types` / `class_types` / `container_types` 三個 frozenset
4. 用 config-driven 的新 `_walk` 取代寫死的 `_walk_generic`
5. **不動** `_walk_python` 與 `_walk_typescript`（既有行為位元級保留）
6. 不引入 codegraph 的 `LanguageExtractor` 框架、SQLite property graph、WASM grammar — 服務目標不同

### 2.3 Acceptance

- Rust 含 `impl` 區塊方法的 fixture，跑出 L1 功能（先寫 failing test 再修，TDD）
- Java / Ruby / Go / PHP / C# / C / C++ 各一份小 fixture 抽出至少一個 function 與一個 class
- python / typescript / javascript 的既有 test 全綠不變
- `language_configs.py` 是 pure data，無副作用、無 I/O

### 2.4 待決定

依 `multilang-node-extraction/spec.md` 第 9 節（worktree `peaceful-bell-8b569a`）：用 `writing-plans` 把該 spec 轉成可執行 task plan。

---

## 3 · 工作流 B — Viewer 視覺套設計系統

### 3.1 問題

`docs/frontend-local-version-viewer/viewer/` 目前的視覺與 `design/The Door Design System/design_handoff_v1.1.1_diff_visuals/README.md` 描述的目標有落差。10 個 section 的設計改動跨 topbar / summary band / cards filter bar / detail panel / relation graph / mindmap badges。

### 3.2 已決策（本 session）

**技術棧**：維持 vanilla JS、無 build step、無 React。設計檔內的 `.jsx` reference 僅用於對照 DOM 結構與樣式，**不引入**。任何要新增的技術都先確認。

**例外保留現況的區塊**：

| 區塊 | 決議 | 理由 |
|---|---|---|
| 功能卡片（feature card）顯示方式 | **維持現有 layout 與 DOM 結構**：`<button>` + `label/desc/meta`、grid（`auto-fill, minmax(240px, 1fr)`）、`.active`/`.changed` class、原始 `.feature-card-meta` 只放一個 badge | 使用者明示沿用 |
| 心智圖整體 layout（中心節點 + 放射 L1 + JS 動態座標計算） | **不動**。只改：徽章 SVG block / `L1_W`/`L1_H` 常數 / toolbar `.tb-badge` 列 / guide-panel 文案 | 使用者明示沿用 |
| 心智圖右側 `#info-panel` | **不動** | 設計文件明確排除 |
| 設計文件 § 6（feature-card 密度 chips：`N src` / `⚠ N` / `⚠ 新增 + 低信心`） | **撤回**——卡片要原狀 | 與「卡片維持原本顯示」決議衝突 |
| 設計文件 § 7.4 在 card 上的 danger chip | **撤回**（detail panel 內的 warning banner 仍保留） | 同上 |

**模擬版面**（已產出，使用者確認無問題）：

| URL | 對應設計章節 |
|---|---|
| `viewer/mockup.html` | § 1–§ 7（不含 § 6 / § 7.4 卡片 chip）、§ 7.5 備註 tab |
| `viewer/mockup-graph.html` | § 9 關聯圖 — grid 卡片 layout（對齊現有 viewer 截圖） |
| `viewer/mockup-mindmap.html` | § 10 心智圖 — Before/After 對照表（不動 layout） |

3 個 mockup 都用設計系統 tokens，所有顏色、字級、間距與 `design/.../colors_and_type.css` 對齊。

### 3.3 套用範圍（已對核 viewer/ 現況）

| 設計 § | 套用 → 生產檔 | 性質 |
|---|---|---|
| § 1 設計 tokens | `viewer/styles.css` `:root` | 補齊缺漏 token |
| § 2 page layout & 行為契約 | 多檔（行為層） | 驗證既有行為符合契約 |
| § 3.2 risk filter 可點擊 | `index.html` + `js/ui-topbar.js` | `<span id="count-risk">` → `<button>` + `state.riskOnly` |
| § 3.3 mode-switch 動態版本名 | `js/ui-topbar.js` | label 跟著版本選擇器更新 |
| § 3.4 版本選擇器 pill（A 紅 / B 綠） | `index.html` + `styles.css` | markup 替換 |
| § 3.5 logo 狀態對應 | `js/ui-topbar.js` | `resolveLogoState(mode, layerState)` |
| § 4 summary band per-mode | `index.html` + `js/ui-topbar.js` | 新增 `<span id="summary-version-tag">` |
| § 5 cards filter bar | `js/ui-list.js` + `styles.css` | 信心 / 類型 / 排序 + 啟用條 |
| § 6 feature card 密度 chips | **撤回**（見 § 3.2） | — |
| § 7 detail panel sections / sticky / Before-After / warning | `js/ui-detail.js` + `styles.css` + 新檔 `js/diff-util.js` | 主要改動 — 與工作流 C 衝突 |
| § 7.4 card-level danger chip | **撤回**（detail banner 仍保留） | — |
| § 7.5 備註 tab | `js/ui-notes.js` | collapsed form + card list |
| § 8 doubts view | 新檔 `js/ui-doubt.js` | 沿用 detail panel 結構 |
| § 9 關聯圖節點 | `js/graph.js`（Cytoscape style block） | pale fill + saturated border + dark text |
| § 10 心智圖徽章 | `mindmap-popup.html`（4 個 block） | 不動 layout |

### 3.4 Acceptance

照 `design_handoff_v1.1.1_diff_visuals/README.md` 的 "Consolidated acceptance criteria" 節跑，但減去：

- 不檢查 `.feature-card-source-chip` / `.feature-card-anomaly-chip` / `.feature-card-danger`（已撤回）
- 不檢查心智圖 layout 的任何位置/座標變化（僅檢查徽章樣式、`L1_W`/`L1_H`、toolbar legend、guide-panel）

**測試 acceptance**（既有 `viewer/vitest.config.js` + `viewer/tests/` 已有完整 vitest 套件，含 `ui-detail.test.js` / `ui-list.test.js` 等）：

- 既有 vitest test 全綠不退化
- B 新增/改動的 pure function 必須有 unit test：
  - `resolveLogoState(mode, layerState)`（§ 3.5）
  - cards filter pipeline（§ 5）— 信心/類型/排序的純函式版本
  - word-diff util（§ 7.3，新檔 `js/diff-util.js`）— CJK tokeniser + LCS 結果結構
  - mode-switch label resolver（§ 3.3）
- 純 CSS 變更不要求新測試；DOM markup 改動若觸發 `ui-*.test.js` 失敗，需同步更新 test

### 3.5 與工作流 C 的衝突點 → 處理策略

兩條都重寫 `js/ui-detail.js`：
- B 要做 § 7 全套（DiffText / warning / section 重排序 / sticky tabs）
- C 要重寫 `renderStructuralDiffDetail` 並加 `node_details`

→ 先做 **B** 的 plan（含 § 7），再判斷 C 是否：
1. 已被 B 完全涵蓋（合併移除）
2. 仍需獨立 task（只動 `renderStructuralDiffDetail` 細部結構）
3. 變成 B 的尾巴 task

決策點：B 寫 plan 時，先讀 C 的 design.md/tasks.md（在 worktree `ecstatic-beaver-49806e`）對照差異。

---

## 4 · 工作流 C — Diff 詳情面板重做（繼承）

### 4.1 既有 artifact

在 worktree `ecstatic-beaver-49806e` 內：

- `.kiro/specs/frontend-local-version-viewer/design.md`（diff 詳情面板章節）
- `.kiro/specs/frontend-local-version-viewer/tasks.md`（3 個 task）

3 個 task：

| # | 動作 | 主檔 |
|---|---|---|
| 1 | 後端 `/api/diff` 加 `node_details` 欄位 | `the_door/src/the_door/core/ui/api_handlers.py` |
| 2 | 重寫 `renderStructuralDiffDetail` | `docs/frontend-local-version-viewer/viewer/js/ui-detail.js` |
| 3 | 詳情欄加寬 | `docs/frontend-local-version-viewer/viewer/styles.css` |

### 4.2 前置阻擋（**B 與 C 共同**，已 git 驗證）

worktree `stoic-spence-860a5b` 目前狀態：

- 分支 `claude/stoic-spence-860a5b` 已從 `origin/main` 分岔 **4 commits behind + 2 ahead**（非 fast-forward）
- 未 commit 改動檔案：`CLAUDE.md`、`js/app.js`、**`js/ui-detail.js`**、**`js/ui-list.js`**

`ui-detail.js` 與 `ui-list.js` 正是工作流 **B 也要動的同兩支檔**。因此此前置阻擋的不只是 C，**B 同樣阻擋**。

落地動作（非「順手」可做）：

1. 在 `stoic-spence-860a5b` 內 `git fetch && git rebase origin/main` 解 4 個 behind commits 的衝突
2. commit 既有未 staged 改動
3. 開 PR 走標準 review → merge main
4. 工作流 B 與 C 的 plan 都以 merge 後的 main 為基準

### 4.3 重新評估後的執行策略

如 § 3.5 所述，B 的 plan 出來後再決定 C 是否整段併入或留作獨立 task。在那之前，C 暫不獨立排程。

---

## 5 · 工作流 D — CLAUDE.md → hooks 補強

### 5.1 問題

CLAUDE.md 是 system prompt 的「背景資訊」，模型可選擇性忽略。對話越長、context 被擠壓時越容易整段被跳過。某些絕對不能違反的規則（如「禁止動 `prototype/`」「指令是 `ui` 不是 `serve`」）放在 CLAUDE.md 太脆弱。

### 5.2 設計：規則分層配置

| 規則性質 | 載體 | 例子 |
|---|---|---|
| 強制 / 阻擋型（違反會壞事） | Hook `PreToolUse` | 阻擋寫入 `prototype/`、阻擋 `the-door serve` |
| 每次必載短警告 | Hook `UserPromptSubmit` | 「前端唯一正式版路徑」「啟動指令是 `ui`」 |
| 工作流引導（提示/最佳路徑） | CLAUDE.md | 「先跑 status」「分支決策樹」 |
| 背景知識（API、術語） | CLAUDE.md | 指令表、snapshot ref 格式 |

### 5.3 立即可落地的 3 條 hook

1. **`PreToolUse` on Edit/Write**：`file_path` 包含 `docs/frontend-local-version-viewer/prototype/` → 拒絕
2. **`UserPromptSubmit`**：注入 2 行短警告：
   - 「前端唯一正式版：`docs/frontend-local-version-viewer/viewer/`」
   - 「啟動指令是 `the-door ui <test-target>`，不是 `serve`」
3. **`PreToolUse` on Bash**：偵測 `the-door serve` → 提示「指令是 `ui`」

### 5.4 Acceptance

- 3 條 hook 設定在 `.claude/settings.json` 或 `.claude/settings.local.json`
- 不引入新 dependency；用 harness 既有 hook system
- 觸發測試：故意 `Edit prototype/...` 應被擋；故意 `Bash the-door serve` 應有提示

### 5.5 落地方式

走 `update-config` skill 寫 `.claude/settings.json`，或使用者授權後直接編輯。

---

## 6 · 跨工作協調與執行順序

### 6.1 依賴圖

```
A (多語言抽取)        獨立
D (hooks)              獨立
B (設計系統)           → 影響 C
C (diff 詳情)         ← 被 B 阻擋；外加 stoic-spence #3 前置
```

### 6.2 推薦執行順序與理由

1. **D（hooks）先做** — 5 分鐘工作，與其他流無交集，先把流程護欄裝起來避免後續工作觸雷
2. **A（多語言抽取）寫 plan + 執行** — 與前端完全無交集，可獨立推進；scope 通用、優先級高
3. **stoic-spence #3 落地 main（B+C 共同前置）** — 依 § 4.2 步驟：rebase 解 4 commit 衝突 → commit 既有改動 → PR → merge。**必須先完成才能啟動 B**，因為 B 與該分支動到同樣的 `ui-detail.js` / `ui-list.js`
4. **B（設計系統）寫 plan + 執行** — 寫 plan 時先讀 C 的既有 design/tasks.md（worktree `ecstatic-beaver-49806e`）並判斷併入或拆分
5. **C（diff 詳情）** — 根據 B 寫 plan 時的判斷，決定獨立執行 / 併入 B / 移除

### 6.3 為什麼不平行做 A 與 B

可以平行（無交集），但同 session 平行會吃 context。下個對話建議單條推進，必要時用 worktree 分流。

---

## 7 · 變更檔案清單（跨工作流去重）

下表把 4 條工作流會碰的所有檔案整合，避免後續執行時兩條 plan 同時動到。

| 檔案 | A | B | C | D |
|---|---|---|---|---|
| `the_door/src/the_door/core/extraction/node_builder.py` | ✅ 改 `_walk` |  |  |  |
| `the_door/src/the_door/core/extraction/language_configs.py`（新） | ✅ |  |  |  |
| `the_door/src/the_door/core/ui/api_handlers.py` |  |  | ✅ `node_details` |  |
| `docs/frontend-local-version-viewer/viewer/index.html` |  | ✅ |  |  |
| `docs/frontend-local-version-viewer/viewer/styles.css` |  | ✅ |  ✅（C 若獨立則欄寬） |  |
| `docs/frontend-local-version-viewer/viewer/js/ui-topbar.js` |  | ✅ |  |  |
| `docs/frontend-local-version-viewer/viewer/js/ui-list.js` |  | ✅ filter 條 |  |  |
| `docs/frontend-local-version-viewer/viewer/js/ui-detail.js` |  | ✅ § 7 全套 | ⚠️ 與 B 衝突 |  |
| `docs/frontend-local-version-viewer/viewer/js/ui-notes.js` |  | ✅ |  |  |
| `docs/frontend-local-version-viewer/viewer/js/ui-doubt.js`（新） |  | ✅ |  |  |
| `docs/frontend-local-version-viewer/viewer/js/diff-util.js`（新） |  | ✅ |  |  |
| `docs/frontend-local-version-viewer/viewer/js/graph.js` |  | ✅ § 9 |  |  |
| `docs/frontend-local-version-viewer/viewer/mindmap-popup.html` |  | ✅ § 10 |  |  |
| `.claude/settings.json` |  |  |  | ✅ |

---

## 8 · Clean code 合規檢查

引用 `karpathy-guidelines` 與 The Door 既有偏好，作為各工作流寫 plan / 實作時的自我檢查：

| 原則 | 適用工作流 | 怎麼檢查 |
|---|---|---|
| 不過度設計 | 全部 | 任何「未來可能」「為了擴展」的代碼/抽象 → 刪 |
| 修正連根 | A, B | 改 `_walk_generic` 時同步更新 spec 表/test/註解；改 detail panel 時同步 mockup 註解 |
| TDD（rigid skill） | A 必跑 | 先寫 failing Rust impl_item test → 再實作 |
| 確認問題真實存在 | 全部 | 已驗證的部分本文件都標 "（已 grep 驗證）"；新發現的問題寫 plan 前再驗 |
| Agent-as-LLM ≠ 直接寫檔 | （流程） | 提到「需要 LLM 」時先想是否能走 MCP `extract_structure` → 自產 L1 → `snapshot_write` |
| 測邏輯，不測內容 | A | 多語言 fixture test 斷言「抽到 N 個 function、M 個 class」而非斷言「某字串」 |
| 既有 spec 不重複 | 本文件 | 引用 `multilang-node-extraction/spec.md` / `frontend-local-version-viewer/design.md`，不貼內文 |

---

## 9 · 開放問題（單一收集處）

| # | 問題 | 觸發決策的時機 |
|---|---|---|
| 9.1 | A 的 plan 拆成幾個 task 合適？（spec 第 7 節要求 TDD） | 寫 plan 時 |
| 9.2 | B 寫 plan 時，C 的 3 個 task 是併入、留作獨立、還是移除？ | B 寫 plan 時 |
| 9.3 | stoic-spence #3 修正內容是否仍適用 main 當前 HEAD `0b353df`？ | C 排程前 |
| 9.4 | D 的 hook 是放 `.claude/settings.json`（repo 共享）還是 `.claude/settings.local.json`（個人）？ | D 落地時 |

---

## 10 · 下個對話起手清單

1. 讀本檔（單一入口）
2. 確認 git：`main` 在 `0b353df` + tag `v1.2.1`
3. 確認本文件位置：worktree `goofy-einstein-acd2d0` 的 `.kiro/specs/consolidated-roadmap-2026-05-23/spec.md`（未 commit）
4. 確認 3 個 mockup 仍在 `docs/frontend-local-version-viewer/viewer/mockup{,-graph,-mindmap}.html`
5. 依 § 6.2 順序 D → A → B → C 推進；每條跑前讀對應 spec/handoff 細節
6. 不要直接實作——先按工作流寫 plan，plan 過 code-review 再執行

---

## 附錄 · 來源 handoff 索引（背景知識，不主動推進其內容）

- `~/.claude/projects/.../memory/handoff_2026_05_22.md` — codegraph 評估 + A 的 spec 完成
- `~/.claude/projects/.../memory/handoff_2026_05_20_b.md` — C 的 spec + plan 完成
- `~/.claude/projects/.../memory/handoff_2026_05_20.md` — prompt enforcement plan（已落地 `v1.2.1`）
- `design/The Door Design System/design_handoff_v1.1.1_diff_visuals/README.md` — B 的設計來源（高保真）
- 本 session（2026-05-23）— B 的設計確認 + 模擬版面 + 本合併文件
