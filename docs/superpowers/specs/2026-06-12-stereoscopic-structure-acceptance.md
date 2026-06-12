# 立體化結構 消費層驗收報告（spec §5.2，2026-06-12）

> 執行者＝主 agent（Claude，agent-as-LLM 消費端本人）。對象＝the_door/ 自身（merge 後 `925b10d` 源碼，in-process driver 呼叫新版 `_extract_structure`）。基線＝spec §1 的 F-a..F-d（同日 spike 實錄）。單一樣本、自己驗自己——結論範圍限本專案此任務，不升格通用宣稱、也不以樣本單一否定。

## 基線對照復測

| 檢核 | 基線（改動前實錄） | 復測結果 | 判定 |
|---|---|---|---|
| F-a 食量規劃 | 單發 2,819,201 字元、爆檔後自行發明切片 | 首口（L0 索引）**3,513 字元**（−99.88%），一口讀完即得全貌＋下鑽座標＋各區大小（src.gz 120KB／tests.gz 117KB 先告知） | ✅ 不復發 |
| F-b 手工 join | `from_node` 欄位名誤用→零邊假結果→錯誤結論通過交叉驗證 | 查 `wrap`：L2 視圖直接給 12 條出邊（含鏈式建構子 `StateInspector(...).inspect()`、別名匯入 `to_json_dict`），定址鍵 `to_node_id` 由 `consumption_guide.addressing` 預先告知；`topology.out_degree==len(out_edges)` 跨軸自洽可查 | ✅ 不復發（零手工 join） |
| F-c 無用區盲吃 | tests/ 佔 75% 被盲吃 | 索引標 `peel: one_way_consumer`＋證據（outbound 4429 : inbound 9、ratio 492.1、閾值 50 附上）——**未取 tests 區任何內容**即裁決跳過；資料完整在檔可下鑽 | ✅ 不復發 |
| F-d 讀法引導不可用 | batch_assignment 埋在 2.8M 裡無解釋無通道 | 索引給每區批次分佈（src: b1=31 入口/b2=502/b3=145），`consumption_guide.batch_semantics` 解釋語義 | ✅ 不復發 |

註：流向計數 4429:9（spike 時 4362:9）——差異＝本功能自身新增的源碼/測試，方向不變。

## 效力總評（分級信心＋攤開理由）

- **結構層＝high**：21 個新測試含 F-b characterization 與索引尺寸 characterization（<32KB），全套 1481 passed / 0 failed；分區/撥離/視圖皆決定性純函式。
- **「LLM 翻譯更正確/更省」＝medium**：理由攤開——(支持) 四個實測失誤型態在同一任務、同一對象上全數不復發；機制性消除（預組裝視圖使 join 不存在、標示使試吃不需要），非僅僥倖。(限制) 單一樣本、自己驗自己；「更正確」最終仍依賴消費端 LLM 行為，結構管不到判斷品質；其他專案形狀（單根目錄、多語言、generated code）未驗。

## 產出資訊可用性分類

**可用（驗收中實際做了功）**：L0 索引（3.5KB 全資訊）；peel 標示＋證據（不試吃裁決）；批次分佈＋語義；L2 node 視圖（零 join＋跨軸一致性檢查）；`structure.full.json.gz`（validate_output 接縫）；`consumption_guide`（欄位名先告知＝直接堵 F-b 的坑）。

**改動前的廢物產出（已改善）**：2.8M 扁平全量回應（75% 測試碼強制餵食）→ 改為按需下鑽，預設零浪費。

**殘餘改進候選（非瑕疵，遇真實需求再做）**：
1. 區域內無更細定址——src 區 678 nodes 一檔（120KB gz），按批次/檔案切子 artifact 可更省，但目前 LLM 可在區檔內按 node_id 過濾，邊際低。
2. `flow_to` 欄位語義未進 `consumption_guide`（審查 minor 遺留）。
3. calls＋imports 成對邊使 out_degree 含語義重複（wrap 12=6×2）——視圖帶 type 可自行過濾，攤開即誠實，但消費端須知道。

## 瑕疵記錄（本輪執行中發現）

1. **［環境・重大］live MCP server 跑舊碼且安裝損毀**：site-packages 存在 `~he_door`/`~-e_door` 等 1.7.0 損毀殘餘 dist；`pip install -e` 因權限失敗。後果＝host app 內的 MCP 工具仍是 v1.7.2 前行為（spike 已實證：回應無 verification_guidance）。**建議**：手動刪除 `site-packages` 下 `~*door*` 目錄 → 以足夠權限 `pip install -e ./the_door` → 重啟 host app；或改用 CLAUDE.md 的 source 形式 MCP 設定（`python -m the_door` + PYTHONPATH）讓重啟即生效。
2. **［流程］subagent 路徑違規污染 main**：Task 4 首次執行的子代理跑進主 repo worktree、在 main 上提交＋留 8 個 stub 殘檔（且 peel 規則寫錯）。已即時偵測、`git reset --hard 8627545`＋清殘檔復原、加路徑護欄重派成功。**建議**：日後 implementer prompt 一律內建「分支名驗證後才准 commit」護欄（本輪 Task 5 起已採用）。
3. **［計畫假設誤差・輕微］**：`.kiro/specs/incremental-analysis/design.md` 並無 extract_structure 的 I/O schema 段（計畫假設有），實際只在 suggester 規則表出現一次——不造段落、僅同步 CLAUDE.md，已於 commit 訊息記錄。

## 結論

spec §5.1（結構層 8 項）＋§5.2（消費層 4 項基線復測）全數通過；無未結瑕疵阻擋。立體化結構（撥離索引＋分層消費通道）對「通用型強化 LLM 翻譯資訊抓取、不引多餘資訊」大目標的兌現，在本專案自身樣本上成立。
