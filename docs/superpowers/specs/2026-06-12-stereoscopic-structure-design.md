# 立體化結構：撥離索引＋分層消費通道（design spec）

> 讀者＝執行實作的 Claude Code（LLM）。本文件零佔位符；所有數字與檔案路徑皆為 2026-06-12 spike 實測值（對象＝v1.7.2 源碼 worktree 的內層 `the_door/`）。
> 狀態：spec（待雙審）。上游討論：使用者「多軸平行→立體化、增加縱軸提升翻譯信心率」原始命題，經 spike 收斂。

## 0. 一句話

`extract_structure` 的輸出從「單發 2.8M 字元扁平全量」改為**縱軸三層**：L0 撥離索引（infra 計算分區＋標示＋證據，回應本體）→ L1 區域/批次切片（artifact 落檔、按座標取用）→ L2 node 座標視圖（預組裝多軸、統一定址）。**不新增資訊、不過濾、不判斷**——只重排、統計、標示既有資訊並附下鑽座標，讓消費端 LLM 讀標示即可規劃食量、不試吃即可裁決、不手工 join 即可定位。

## 1. 動機證據（2026-06-12 spike 實錄，全部可重跑）

對象：`the_door/`（372 檔／2638 nodes／7249 edges）。LLM（Claude）親自跑 agent-as-LLM 鏈翻譯 verification-guidance 功能（有 ground truth 可對答案），錄得四筆消費端失敗：

| # | 失敗實錄 | 根因 | 對應解層 |
|---|---|---|---|
| F-a | `extract_structure` 單發回應 2,819,201 字元，超過 MCP 回應上限直接爆檔；LLM 無任何「裡面有什麼/多大/怎麼分段」線索，只能落檔後自己發明切片 | 無食量規劃資訊（無索引） | L0 |
| F-b | LLM 用 `from_node`/`to_node` 過濾 edges（實際欄位名 `from`/`to`），得到「零邊」假結果，並把它敘事成「靜默丟失」；**該錯誤通過了 edge_residue 交叉驗證**（兩個面共享同一錯誤 join 假設）；最終被 topology（工具端預 join 的 out_degree=12）的跨軸矛盾戳破 | 跨視圖定址欄位名不一致＋LLM 手工 join | L2 |
| F-c | `tests/` 佔 1969/2638 nodes、5426/7249 edges（≈75%），與「翻譯程式主體」無關卻被盲吃；其結構差異其實自明：**test→prod 4362 條 vs prod→test 9 條**（單向流動不對稱） | 無撥離標示；訊號存在但 infra 未計算未攤開 | L0 |
| F-d | `core/topology/batch_assigner.py` docstring 自述「Assign batch numbers for topology-guided LLM reading」，`batch_assignment` 已逐 node 算好——但攤平埋在同一 2.8M 回應裡，無解釋、無按批取用通道，消費端不可見不可用 | 縱軸（讀法引導）已蓋一半、無運用層級 | L1 |

旁證（操作面，非本 spec 範圍但實作時注意）：live MCP server 回應無 `verification_guidance` 欄＝跑的是 v1.7.2 前安裝；實機驗證前須 `pip install -e ./the_door` ＋重啟 host app。

## 2. 不可飄移原則（與既有裁決對齊）

1. **surface 不 judge**：分區/標示＝決定性結構計算（與 topology、edge_residue 同性質）；「這區對當下任務有沒有用」的裁決完整留給消費端 LLM。
2. **標註不過濾、加法不減法**：撥離≠刪除。全量資料落 artifact 可定址；預設不進回應而已。任何區域（含被撥離區）LLM 都可沿座標取回。
3. **零路徑名寫死**：撥離標示只由結構訊號導出（見 §4.2）；`tests/` 三個字不得出現在判定邏輯。換任何專案機制不變。
4. **壓縮帶座標＋基數可下鑽**（乙案種子 §8.3 兩層輸出鐵律＋F2 發現管道）：索引裡每個壓縮 token（區域條目）必帶 `基數＋比例＋artifact 位址＋大小`，且索引本身就是發現管道。
5. **意義經結構非散文**：撥離理由＝低基數 enum 進膜（照 `core/reading/confidence_membrane.py` 樣板），不是自由文字。
6. **L1 功能分群仍是 LLM 的**：infra 不提供 module/目錄功能聚類（CLAUDE.md 明令 L1 分群 by functional purpose, not by file or class；infra 預聚類＝誘導違反）。infra 可計算單元的上限＝node。
7. **不碰持久化契約**：`SNAPSHOT_CONTRACT_VERSION` 仍 `"1"`；既有欄位（edges 的 `from`/`to`＝`ast-raw.schema.json:107-115` 契約欄位、residue 的 `caller`、structure `.json.gz` round-trip）一律不改名。新層內部統一用 `node_id` 詞彙。（前端經查不直接消費 edge `from`/`to`，非本決策依據。）

## 3. 縱軸三層架構

```
L0 撥離索引（= extract_structure MCP 回應本體，索引尺寸）
 ├─ 全域統計：files/nodes/edges 總量、語言、入口點數
 ├─ 區域條目[]（依路徑頂層段聚類）：
 │    region_id、node_count、edge 三向計數(internal/inbound/outbound)、
 │    佔比%、batch 分佈、artifact_path、size_bytes、
 │    peel: {reason(膜元素) , evidence(流向計數)} | null
 └─ 下鑽說明：artifact 格式、L2 視圖的定址欄位名（node_id）
L1 區域/批次切片（= .the-door/structure-view/ 下的 artifact，按 region 落檔）
 └─ regions/<region_id>.json.gz：該區全部 L2 node 視圖（含跨區邊，雙方掛載）
L2 node 座標視圖（= L1 檔內逐 node 的預組裝物件，無獨立檔）
 └─ 單一 node 的多軸並置：屬性＋出入邊（resolved，欄位名統一 node_id）＋
    topology（in/out degree、batch_assignment、is_entry_point）＋
    殘餘引用（edge-residue 中以此 node 為 caller 的條目索引）
```

縱軸語義：**粒度**。L0 不吃內容即可裁決；L1 按區按批控制食量；L2 消滅手工 join。橫軸＝既有膜軸（不動）。

## 4. 交付物（exact）

### 4.1 新套件 `the_door/src/the_door/core/structure_view/`

| 檔案 | 職責 |
|---|---|
| `region_partition.py` | `partition(nodes, edges) -> list[Region]`。聚類鍵＝node_id 的路徑頂層段（`src`、`tests`…，泛用、非寫死名單）。逐區算 edge 三向計數與跨區流向矩陣。純函式、決定性。**退化案例明定**：單根專案（僅 1 個頂層段）→ 1 區、零撥離標示＝正確輸出（無誤標即誠實），第一刀**不得**自行加第二層聚類補救。 |
| `peel_membrane.py` | 撥離理由膜（照 confidence_membrane 樣板：CONTRASTS＋_GLOSS＋element/schema_fragment）。**第一刀 enum 僅一值** `one_way_consumer`（單向消費區：對某鄰區 outbound/inbound 流向比 ≥ 閾值且自身不被主體回流消費）。不預鑄未驗證的值（能做≠該做；isolation/可達性訊號已被 [[project_t1_guidance_falsified]] 證偽為不可靠，**禁止**用作撥離訊號）。 |
| `node_view.py` | `assemble(node, edges, topology, residue) -> dict`。單 node 的 L2 視圖組裝；輸出鍵統一 `node_id`／`out_edges[].to_node_id`／`in_edges[].from_node_id`（新層內自洽，不回寫舊欄位）。 |
| `structure_index.py` | `build_index(regions, …) -> dict`：L0 索引組裝；`write_artifacts(…)`：落 `.the-door/structure-view/index.json` ＋ `regions/<region_id>.json.gz`。 |

撥離判定閾值：流向比 ≥ 50:1 視為單向（spike 實測 4362:9 ≈ 485:1，餘量充足）；閾值為模組常數並寫進索引的 evidence（消費端可稽核）。

### 4.2 MCP `extract_structure` 行為變更

- 解析照舊（`ASTExtractor.extract`，不動）。解析後追加：partition → peel 標示 → artifacts 落檔。
- **回應＝L0 索引**（經 `wrap` 走正常 envelope，照舊附 next_actions/verification_guidance）。不再內嵌全量 nodes/edges/topology。
- **下游接縫（審查揪出，必處理）**：`validate_output`（`mcp/server.py:49`）`required: ["llm_output","structure_json"]`——文件化工作流裡 structure_json 來自 extract 回應。解法（加法）：`validate_output` 增加可選 `codebase_path` 參數，自行讀 `.the-door/structure-view/` artifact 取結構；`structure_json` 保留、優先序＝顯式 structure_json > codebase_path artifact。註：大專案下 LLM 本來就不可能把 2.8M 塞進工具參數，此接縫在現狀已半殘，artifact 路徑同時修復它。
- 其他工具（edge_residue/snapshot_write/analyze_changes）自行讀磁碟、不吃 extract 回應，grep 證實無其他程式端 reader；CLAUDE.md 同步改寫 agent-as-LLM 鏈步驟 1（見 §4.4）。
- `edge_residue`、checklist C2/C3 gate、snapshot 流程**全部不動**（殘餘 artifact 與覆蓋集語義不變）。

### 4.3 不做（第一刀明確排除）

- 不為**下鑽**新增查詢參數/新 MCP 工具（下鑽走 artifact＋Read/jq；`doubt_list` 式 filter 參數留待真實需求）。例外＝§4.2 的 `validate_output.codebase_path`：那是修既有輸入鏈接縫，非下鑽通道。
- 不做 module/目錄功能聚類視圖（§2-6）。
- 不改既有欄位名、不 bump 契約。
- 不把撥離 enum 預擴成多值。
- CLI `extract` 路徑不動（僅 MCP 面；CLI backfill 用途不同）。

### 4.4 文件

- CLAUDE.md「Agent-as-LLM chain (single version)」步驟 1 改寫：說明回應＝索引、如何讀標示、如何沿 `artifact_path` 下鑽、`batch_assignment` 的用途（入口點第 1 批→in_degree 降冪 2..5 批）。
- `.kiro/specs/incremental-analysis/design.md` 的 extract_structure schema 段同步。

## 5. 驗證

### 5.1 結構層（pytest 可驗，目標 high 信心）

1. `region_partition`：決定性（同輸入同輸出）；fixture 上流向矩陣計數正確（手算對照）。
2. `peel_membrane`：照樣板的 membrane 測試（contrasts/gloss/schema_fragment 同源、無副本）。
3. 撥離判定：fixture 造 60:1 單向區→標 `one_way_consumer`；10:1→不標；證據欄帶實際計數與閾值。
4. `node_view`：含 F-b 反例 characterization——組裝視圖內查 `wrap` 必須直接給出 12 條出邊（含鏈式建構子 `StateInspector(...).inspect()` 與別名匯入 `to_json_dict as action_to_json` 的解析結果），無需消費端 join。
5. `structure_index`：對 the_door 自身 index.json 尺寸 < 32KB（characterization，釘「索引尺寸」承諾）；every 區域條目帶齊 基數/比例/artifact_path/size_bytes。
6. artifact round-trip：regions gz 寫讀一致；被撥離區資料完整在檔（標註不過濾的結構性證明）。
7. `validate_output` 接縫：帶 `codebase_path`（無 structure_json）→ 從 structure-view artifact 取結構驗證成功；兩者皆給→ structure_json 優先；皆缺→既有錯誤路徑不變。
8. 既有測試全綠（基線 1460 passed；加法驗證）。

### 5.2 消費層（LLM 翻譯回饋，效力上限 medium，不洗白）

**基線＝§1 的 F-a..F-d 四筆實錄（已存在，本 spec 即記錄）。**

實作完成後，由執行驗收的 LLM 對同一對象（`the_door/` 自身）只經新通道重跑同一翻譯任務（產 verification-guidance 功能的 L1 描述），逐項回報：

| 檢核 | 通過判準 |
|---|---|
| F-a 復測 | 首口（索引）實際字元數；是否不再需要「吃到撐再切片」 |
| F-b 復測 | 查 `wrap` 出邊：是否從 L2 視圖直接得到、零手工 join；欄位名歧義是否還可能發生 |
| F-c 復測 | 是否僅讀撥離標示＋證據（不取 tests 區內容）即裁決跳過；需要測試線索時下鑽是否可行 |
| F-d 復測 | batch_assignment 是否經索引可見、可按批取用 |
| 效力總評 | 對「翻譯更正確/更省」給**分級信心＋攤開理由**；單一樣本（自己驗自己），結論範圍限本專案此任務，**不得升格通用宣稱、也不得以樣本單一否定它** |

### 5.3 誠實界線

- 結構層 gate 驗得到：形狀、決定性、加法、尺寸。驗不到：「LLM 因此翻得更忠實」——該宣稱永遠有判斷殘餘，信心上限 medium。
- 撥離訊號第一刀只有單向流動一種；其他「無用」型態（generated code、vendored、多語言）未驗證未支援——遇真實案例再擴 enum，不預做。

## 6. 決策記錄（證據裁決，2026-06-12）

| 決策 | 裁決 | 證據 |
|---|---|---|
| 下鑽通道 | artifact＋索引回應（edge_residue 同型） | 家規前例（edge_residue、`structures/<vid>.json.gz`）；MCP 回應上限實測 2.8M 爆 |
| 單元粒度 | node（不做 module 聚類） | CLAUDE.md 明令 L1 分群非按檔案/類別；infra 預聚類＝誘導違反 |
| 定址統一 | 加法（新層用 node_id 詞彙、舊欄位不動） | `from`/`to` 進契約 schema（ast-raw.schema.json:107-115）＋持久化 gz round-trip |
| 撥離詞彙 | 進膜（enum＋gloss＋證據欄） | confidence_membrane docstring 明示樣板地位；「意義經結構」家法 |
| 撥離訊號 | 僅單向流動；禁用可達性/isolation | 流向 4362:9 本次實測成立；fan-in=0 已被 project_t1_guidance_falsified 證偽 |
| 驗證含消費端回饋 | 必含（§5.2），基線＝本次 spike | 使用者拍板；效力層 LLM 可驗＝分級信心＋攤開理由（既有裁決） |
