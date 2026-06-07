# H3 spec：人類面膜詞彙封閉集 drift-guard（schema 為單一來源，viewer key-set 不漂移）

> **日期**：2026-06-07　**狀態**：spec（已雙審＋修；pre-plan，已對真實碼＋schema spike＋grep 驗真）　**性質**：人類面整膜末刀。
> **一句話**：viewer 在多個 JS 檔硬編「以膜封閉集為鍵」的 map。真缺陷**不是** label 文字（per-surface 合法各異），而是這些 map 的 **key-set 與 schema 封閉集無結構性綁定**——Python 改 enum 而 JS 漏接即靜默漂移。本刀＝新增一支 **vitest conformance 測**，讀 checked-in schema enum 斷言每個「封閉集為鍵」的 JS 消費點**處理了全集**（漏值不 fall-through）。**零 endpoint／零 generator／零 runtime／零呈現改動**。
>
> **雙審結論（已併入本稿）**：①核心切分改述為 **KEY 維度（守）vs VALUE 維度（per-surface 不動）**，非「Role A+F vs B/C/D/E」（後者使「label map 是標的」與「label OUT」自相矛盾）。②機制定稿＝**行為斷言為主**（餵每 schema 值、斷言消費點不 fall-through），非常數內省。③目標清單 grep 驗真重列（修正 dom.js 誤列）。④排序 map 排除理由改為「漏鍵良性退化」。⑤新增 guard 涵蓋邊界誠實節＋跨樹 fs 退路。

---

## 0. 理論錨點

| 原則 | 對本刀約束 |
|---|---|
| **意義靠結構不靠約定**（種子 §8.10／乙案核心） | 封閉集成員（哪些值存在）是膜合約。viewer 在 N 處重建「以該集為鍵」的 map，今日恰一致、明日 Python 改 enum 即靠人記得同步。本刀讓「消費點處理全集」由結構（schema↔測）強制。**正當性錨在「固化合約／收束人類面整膜」，非「防一個常見 bug」**（enum 罕變；價值在結構誠實、非缺陷頻率）。 |
| **KEY ⊥ VALUE 二分**（本刀核心切分） | 守的是 map 的 **key 涵蓋**（封閉集每值都被消費點處理）。**不**碰 value：label 中文（`graph.js '~ 修改'` vs `layers.js '~ 屬性變更'` vs `ui-detail.js '屬性變更'`）、顏色、排序序——皆 per-surface 合法各異、不單源化、不綁一致。 |
| **正做不窄做亦不虛做**（Economy） | **正**＝守 key 漏接會「可見錯誤/誤計」的消費點。**不窄**＝涵蓋三軸（change_type/risk_flags/confidence）全部此類消費點。**不虛**＝拒 runtime `/api/lexicon`（value per-surface 不可單源⟹ runtime 唯一可單源者只剩 key 成員、收益薄；guard 零耦合達標）。 |
| **通用型基礎建設 vs 加深技術鴻溝** | guard＝純測試、讀既有 checked-in JSON、無新依賴/build/async/上游耦合。 |
| **膜拒編序**（`diff_membrane.py:22-24`／H2） | 排序 map（Role C）的 value＝序，膜拒編序、本刀不綁。其 **key** 漏接＝良性退化（落預設殿後、膜本不編序），非可見錯誤 ⟹ **排序 map 不入本測**（理由＝漏鍵良性，非「拒編序」本身）。 |
| **fact-finder 誠實 token**（H1/H1-5） | confidence 軸 viewer 合約＝schema 3 值 `{high,medium,low}` **∪ viewer 誠實額外 `unknown`**（None→未評估、不在 schema）。測須編碼此**不對稱**。 |

---

## 1. 範圍（in / out）

### 做（in）

新增**單一** vitest 測檔（暫名 `tests/membrane-vocabulary.test.js`），對三軸各斷言「每個封閉集消費點處理 schema 全集」。**目標清單（grep 驗真 2026-06-07，file:line＋map/函式名）**：

**change_type 軸**（schema 封閉集 4 值；下列皆 keyed by `change_type`，守 key 涵蓋、不動 value）：
| 消費點 | file:line | 形態 | 測法 |
|---|---|---|---|
| `TYPE_TAG` | `graph.js:3` | exported? 否（頂層 const，未 export） | 行為：`buildDisplayLabel`（:10 用 TYPE_TAG）餵每值斷言含 tag |
| `DIFF_BADGE` | `mindmap-util.js:3` | **已 export** | 集斷言：keys ⊇ 4 值；或 `badgeFor`（:16）行為 |
| `DIFF_LABELS` | `layers.js:16` | 否（頂層 const，未 export，:451 用） | 行為：經其渲染路徑斷言不 fall-through 到 `?? change.change_type` |
| `CHANGE_TYPE_LABEL` | `ui-detail.js:161` | 否（:201 用 `?? changeType`） | 行為：餵每值斷言非裸值 fall-through |
| `changeSymbol` | `ui-list.js:41` | **已 export（函式）** | 行為：`changeSymbol(v)` 對每值 ≠ `'?'`（其 `?? '?'` 為 fall-through 哨兵） |

**risk_flags 軸**（schema 封閉集 3 值）：
| 消費點 | file:line | 形態 | 測法 |
|---|---|---|---|
| `riskCounts` | `viewmodel.js:42` | 計數累加器（count init, key-依賴） | 集斷言：keys ⊇ 3 值（漏鍵＝誤計＝可見錯誤） |
| `RISK_PRIORITY` | `ui-detail.js:440` | **排序 map** | ⚠ 見 OUT：排序 map、漏鍵良性退化、**不入測** |

**confidence 軸**（schema 3 值 ∪ viewer `unknown`）：
| 消費點 | file:line | 形態 | 測法 |
|---|---|---|---|
| `CONF_LABEL` | `graph.js:244` | 否（頂層 const） | 行為/集：對 `{high,medium,low,unknown}` 皆有標籤 |
| `confidenceMap` | `ui-diff-explanation.js:38` | 函式內 const | 行為：餵每值（含 unknown）斷言非裸值 fall-through（H1-5 已修） |
| `CONF_PRIORITY` | `ui-list.js:4` | **排序/優先 map** | ⚠ 漏鍵良性？——**見決策**：CONF_PRIORITY 漏鍵會讓未知 confidence 落 `?? 2`（=medium 位）＝**謊報**（非良性），故**納入**集斷言 keys ⊇ 4 值（與排序 map 不同：此處漏鍵＝誠實性退化） |

> **可 import 性策略（雙審定稿）**：**行為斷言為主**——對「函式」（changeSymbol）與「未 export 的 const」（TYPE_TAG/DIFF_LABELS/CHANGE_TYPE_LABEL/CONF_LABEL），經其公開渲染/取值路徑餵每 schema 值、斷言**不 fall-through**（不出現 `'?'`/裸 enum 字串/undefined/空白）。對「已 export 的純資料 map」（DIFF_BADGE）可加集斷言 keys ⊇ schemaSet 作佐證。**不為了集斷言而把內部 const 強行 export**（避免為測洩漏實作細節；export 僅在行為路徑不可達時退而求其次，plan 逐點確認路徑可達性）。

### 不做（out）
- **per-surface value（label 中文／顏色／排序序）**：合法各異，不單源化、不綁一致、不動。
- **排序 map：`TYPE_PRIORITY`（ui-list.js:5）／`CHANGE_PRIORITY`（ui-detail.js:441）／`RISK_PRIORITY`（ui-detail.js:440）**：value＝序（膜拒編序）；key 漏接＝落 `?? 9`/`?? 7`/`?? 99` 良性殿後退化、非可見錯誤 ⟹ 不入測。（**例外＝`CONF_PRIORITY`**：其漏鍵落 `?? 2`＝謊報成 medium 位＝誠實性退化、非良性 ⟹ **納入**，見 §1-in。）
- **doubt status 軸（`ui-doubt.js:3 MAP`：open/assigned/resolved）**：不同封閉集（doubt 生命週期、非本三軸）；其借用 confidence-badge CSS 的語義耦合＝另案（handoff §5 已記）⟹ 本刀 OUT。
- **diff_state（node 5-val／edge 3-val，`diff-result.schema.json:16,34`）**：viewer 的 change_type 面是 4-val changed-only 閉集（≠ diff_state）；除非 spike 發現某 JS map 實渲染 diff_state，否則不入（避免綁錯集＝S6 C4 教訓）。grep 已驗：上列 change_type 消費點皆 keyed by `change_type` 欄、非 `diff_state`。
- **severity**：viewer 無渲染＝無消費者，OUT。
- **runtime `/api/lexicon`／generator／build step／任何 runtime JS／呈現／schema／persisted 改動**：虛做或越界，拒。本刀**現況零漂移**（grep 親驗所有 map 覆蓋 4/3/4）⟹ 預期**零生產碼改動**；若行為斷言意外抓到既有缺口＝真 bug、當場修。
- **8 個既有 red 測**：pre-existing、正交、紅數維持恰 8。

---

## 2. Spike 事實（2026-06-07，file:line grep 驗真）

| 主題 | 檔案:line | 事實 |
|---|---|---|
| 膜拒編序 | `core/diff/diff_membrane.py:22-24` | change_type categorical 非全序；contrasts 不編序。H2＝intentional 不修之據。 |
| change_type 封閉集權威 | `the_door/schemas/update-report.schema.json:99-103,143-146` | `enum [added,removed,attribute_changed,dependency_changed]`（兩處）。⚠ schema 在 `the_door/schemas/`（**非** src 下）。 |
| risk_flags 權威 | `update-report.schema.json:110-113` | `items.enum [out_of_scope,vulnerability,semantic_drift]`（array 元素 enum）。 |
| confidence 權威 | `the_door/schemas/l1-output.schema.json:62-66` | `oneOf` const high/medium/low。 |
| change_type 消費點（grep 驗真） | `graph.js:3 TYPE_TAG`／`mindmap-util.js:3 DIFF_BADGE`(export)／`layers.js:16 DIFF_LABELS`／`ui-detail.js:161 CHANGE_TYPE_LABEL`／`ui-list.js:41 changeSymbol`(export 函式) | 皆 keyed by change_type、皆覆蓋 4 值（**現況零漂移**）。**`dom.js` 無 change_type map**（`dom.js:8` 是 `els.countAdded` DOM id，非膜詞彙——雙審修正 handoff §5 誤列）。**graph.js 無 `CHANGE_LABEL`**（僅 `TYPE_TAG`）。 |
| confidence 消費點 | `graph.js:244 CONF_LABEL`／`ui-list.js:4 CONF_PRIORITY`／`ui-diff-explanation.js:38 confidenceMap` | 均含 high/medium/low/unknown（H1/H1-5 後）。 |
| risk 消費點 | `viewmodel.js:42 riskCounts`(count)／`ui-detail.js:440 RISK_PRIORITY`(排序) | 均含 3 值。 |
| changeSymbol 共用 | `layers.js:6 import { changeSymbol }` | symbol 單一來源＝ui-list；layers 共用（無第二份 symbol map）。 |
| per-surface value 實異 | `graph.js:6 '~ 修改'`/`layers.js:19 '~ 屬性變更'`/`ui-detail.js:164 '屬性變更'` | 同 key 不同 value＝VALUE 維度 per-surface、勿綁。 |

**結論**：封閉集權威已 checked-in（schema JSON），Python＋JS 皆可讀。真缺陷＝JS 多個消費點重建「以封閉集為鍵」的處理、無結構強制其涵蓋全集。本刀＝net-add 行為 conformance 測把該涵蓋釘成結構性失敗點。零 runtime。

---

## 3. 設計（落點；exact code 留 plan）

### 3.1 測檔結構（單檔、三 describe + 一 meta）
```
tests/membrane-vocabulary.test.js
  helper readSchemaEnum(absPath, shape) → string[]
     shape ∈ {'enum','items-enum','oneof-const'}（三形狀，見 §3.3）
  describe 'change_type 封閉集 drift-guard'   // 5 消費點，行為斷言為主
  describe 'risk_flags 封閉集 drift-guard'    // riskCounts 集斷言（RISK_PRIORITY 排序 OUT）
  describe 'confidence 封閉集 drift-guard'    // schema 3 ∪ {unknown}；含 CONF_PRIORITY
  describe 'guard 自我有效性（meta）'          // 防恆綠，見 §5
```

### 3.2 斷言語意（行為為主、集為輔）
- **行為斷言**（主）：對每個 schema 值 `v`，經消費點公開路徑取結果，斷言**非 fall-through**：
  - label/symbol：結果 ≠ 該點的 fall-through 哨兵（`'?'`／裸 `v`／`undefined`／空字串）。
  - count（riskCounts）：初始化後含該鍵（漏鍵＝誤計）。
- **集斷言**（輔，僅 export 的純資料 map）：`new Set(keysOf(map)) ⊇ schemaSet`。
- confidence：schemaSet 先 `∪ {'unknown'}` 再要求涵蓋（編碼不對稱）。

### 3.3 schema 讀取（路徑 + 三形狀解析）
- 路徑：viewer 在 `docs/frontend-local-version-viewer/viewer/`，schema 在 repo `the_door/schemas/`。用 `path.resolve(__dirname, <上溯>, 'the_door/schemas/<f>.json')`；**plan 須親跑確認上溯層數**（承 H1 plan schema 路徑 critical 教訓——schema 不在 src 下）。讀檔失敗即測載入爆（fail-loud、非 silent skip）。
- 三形狀：change_type＝`properties.<container>.items.properties.change_type.enum`（plan 親驗實際 JSON path）；risk_flags＝`...risk_flags.items.enum`；confidence＝`...confidence.oneOf[].const`。helper 依 shape 參數統一回 `string[]`。

### 3.4 guard 涵蓋邊界（誠實節，雙審 D 項）
本 guard 守的是**枚舉於 §1-in 的消費點清單**，非自動發現全 viewer。**限制（明列、不誇稱全自動）**：未來新增「以封閉集為鍵」的 JS 消費點若沒加進本測清單，guard 不會自動抓到。
- **降低 meta-drift（plan 可選、非必須）**：加一條輔助掃描——grep/簡易 AST 掃 `viewer/js` 找「object literal 含 ≥2 個 change_type/risk_flag 字面量鍵」之檔案集，斷言該集 ⊆ 已測檔案集。若實作成本過高則退為「在測檔頂註明維護規約：新增膜詞彙消費點須登記於此」並接受手動納管。plan 評估成本後定。

---

## 4. 不變量清單

| # | 不變量 | 強制處 | 理論 |
|---|---|---|---|
| H3-1 | change_type 5 個消費點（§1-in 表）對 schema 4 值皆**不 fall-through**（label≠哨兵/symbol≠`'?'`） | membrane-vocabulary.test.js（行為） | KEY 涵蓋 |
| H3-2 | risk_flags：`riskCounts` keys ⊇ schema 3 值 | 同（集斷言） | 不誤計 |
| H3-3 | confidence：`CONF_LABEL`/`confidenceMap`/`CONF_PRIORITY` 對 `{high,medium,low,unknown}` 皆不 fall-through／皆有鍵（編碼 unknown 不對稱） | 同 | fact-finder/H1 |
| H3-4 | 測**讀 checked-in schema**（非硬編期望集副本）⟹ Python 改 enum→測隨動、漏接 JS→紅 | helper readSchemaEnum | 單一來源 |
| H3-5 | **零 runtime／呈現／endpoint／schema／persisted 改動**；行為斷言策下**零生產碼**（僅在路徑不可達時退而 export，plan 確認應可全行為） | grep gate ＋ diff 審 | 正不虛做／§8.12 |
| H3-6 | **不**綁任何排序 value（priority 序）；排序 map（TYPE_PRIORITY/CHANGE_PRIORITY/RISK_PRIORITY）不入測（CONF_PRIORITY 例外＝其漏鍵謊報非良性、納入 key 涵蓋） | 測碼僅斷 key/行為 | 膜拒編序/H2 |
| H3-7 | meta describe 證 guard 非恆綠（負例）；guard 涵蓋邊界於測檔誠實標明 | §3.1 meta／§3.4 | feasibility 誠實 |
| H3-8 | 既有 red 測維持恰 8；其餘 vitest 零回歸 | full vitest | 隔離 |

---

## 5. 測試策略
- **本刀產物即測**：membrane-vocabulary.test.js 獨立新檔（不碰 8-red 檔）。
- **防恆綠（meta，H3-7）**：負例斷言——構造一個「故意缺 schema 某值」的假 map，斷言 guard helper 對它**會判失敗**（`expect(() => assertCovers(badMap, schemaSet)).toThrow()` 或等價），確保斷言邏輯有效、非永真。承 E2E/TDD 誠實紀律。
- **gate**：vitest 紅數維持恰 8（新測全綠）；grep 確認無 runtime/schema/persisted/endpoint 改動；行為斷言策下 diff 僅見新測檔。
- **零 python 影響**（零 python 改動）。

---

## 6. 連貫律回驗
- **承 H1/H1-5**：confidence 的 `unknown` 誠實 token 在本刀成「合約一等公民」（schemaSet ∪ {unknown}）＝把 H1 約定固化成結構斷言。
- **承 H2**：H2 證膜拒編序⟹本刀只守 key 涵蓋、不綁序（H3-6）；排序 map 排除理由＝漏鍵良性退化。
- **收束人類面整膜**：agent 面（前數 session）＋人類面（H1 渲染、H1-5 diff-explanation、H3 key drift-guard）⟹ 膜詞彙跨 Python/schema/viewer 三側由結構綁住。
- **未來**：若真需 runtime 單源（新增第 5 值且 viewer 要動態適配 label），再起 endpoint 刀；本 guard 屆時即「該補哪些消費點」的精確清單。

---

## 7. 雙審紀錄（concept-review --design ＋ 5 軸 reframe，2026-06-07，已併入本稿）
- **[critical] 目標清單 spike 錯誤**（concept + 5軸A）：dom.js 誤列（TYPE_TAG 實在 graph.js:3、dom.js:8 是 DOM id）、graph.js 無 CHANGE_LABEL → §1/§2 grep 重列。
- **[critical] 框架矛盾**（5軸A）：「Role B label OUT」vs「測 label map」→ 改述為 KEY⊥VALUE 二分（§0），label map 守 key 不動 value。
- **[warning] 機制未定**（concept Logical Continuity）：常數內省 vs 行為斷言 → 定稿行為斷言為主（§3.2、§1 表、§4 一致）。
- **[warning] 排序排除理由錯位**（5軸B）：改「漏鍵良性退化」（§0/§1-out）；並抓出 **CONF_PRIORITY 例外**（漏鍵落 `?? 2` 謊報 medium、非良性）→ 納入（§1-in/H3-6）。
- **[warning] guard meta-drift**（concept Feasibility）：加 §3.4 涵蓋邊界誠實節＋可選反向掃描。
- **[warning] 跨樹 fs 耦合**（concept Feasibility）：§3.3 補路徑親驗＋fail-loud；§6 記解耦退路。
- **[warning] changeSymbol 函式/共用**（5軸C）：歸行為斷言（§1 表）。
- **[warning] doubt status 軸**（5軸D）：§1-out 明列。
- **[suggestion] schema 三形狀**（5軸E）：§3.3 helper shape 參數。
- **[suggestion] 價值錨點**（concept Economy）：§0 錨「合約固化」非「防常見 bug」。
