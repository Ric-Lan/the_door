# Spec — Config-Driven Multi-Language Node Extraction

狀態：草稿（未審查、未排程）
建立日期：2026-05-22
範圍：`the_door/src/the_door/core/extraction/node_builder.py` 的多語言 node 抽取

---

## 1. 引用來源登記表（Citation Registry）

> 本節是本 spec 的「可回查根據」。任何下游 task 對外部事實有疑問時，
> **先回到這裡找到來源座標，再去原始碼驗證**。不要憑記憶下判斷。

### 1.1 外部專案：codegraph

| 欄位 | 值 |
|---|---|
| 用途 | 借用「每種語言對應哪些 tree-sitter node type」的對照資料 |
| Repo | https://github.com/colbymchenry/codegraph |
| 釘選 commit | `5aae9c4bbff4fe02f8284ef5f91dd9d5391027f6` |
| Commit 日期 | 2026-05-22 |
| 授權 | MIT License — Copyright (c) 2026 Colby Mchenry |
| 本機 clone（評估時） | `%TEMP%\codegraph`（暫時性，非永久；要回查請重新 clone 上述 commit） |

**回查方式**：
```
git clone https://github.com/colbymchenry/codegraph.git
cd codegraph && git checkout 5aae9c4bbff4fe02f8284ef5f91dd9d5391027f6
```
若該 commit 已不存在（repo 被刪/改寫），改信本 spec 第 4.1 節抄錄的對照表——
那是 2026-05-22 從上述 commit 逐字抄出的快照。

### 1.2 codegraph 內被引用的具體檔案

| 引用編號 | 檔案路徑（codegraph repo 內） | 引用了什麼 |
|---|---|---|
| CG-1 | `src/extraction/tree-sitter-types.ts` | `LanguageExtractor` interface 的「概念」——node-type 分類欄位的命名（functionTypes / classTypes / methodTypes …）。**只借命名與分類概念，不抄 TS 程式碼。** |
| CG-2 | `src/extraction/languages/python.ts` | Python node-type 對照 |
| CG-3 | `src/extraction/languages/typescript.ts` | TypeScript node-type 對照 |
| CG-4 | `src/extraction/languages/javascript.ts` | JavaScript node-type 對照 |
| CG-5 | `src/extraction/languages/java.ts` | Java node-type 對照（注意 `functionTypes: []`） |
| CG-6 | `src/extraction/languages/go.ts` | Go node-type 對照 + `resolveTypeAliasKind` / `getReceiverType` 特例邏輯 |
| CG-7 | `src/extraction/languages/rust.ts` | Rust node-type 對照 |
| CG-8 | `src/extraction/languages/ruby.ts` | Ruby node-type 對照（注意 node 名是裸 `method` / `class`） |
| CG-9 | `src/extraction/languages/php.ts` | PHP node-type 對照 |
| CG-10 | `src/extraction/languages/csharp.ts` | C# node-type 對照（注意 `functionTypes: []`） |
| CG-11 | `src/extraction/languages/c-cpp.ts` | C 與 C++ node-type 對照（同檔兩個 export） |
| CG-12 | `src/extraction/grammars.ts` | `EXTENSION_MAP` 副檔名→語言對照（僅參考，The Door 已有自己的 file_discovery） |

### 1.3 內部來源：The Door 現況

| 引用編號 | 檔案路徑（The Door repo 內） | 內容 |
|---|---|---|
| TD-1 | `the_door/src/the_door/core/extraction/node_builder.py:31-46` | `_walk` 分派：只有 python / typescript 兩條一級路徑，其餘走 `_walk_generic` |
| TD-2 | `the_door/src/the_door/core/extraction/node_builder.py:369-406` | `_walk_generic` 全文——本 spec 要取代的對象 |
| TD-3 | `the_door/src/the_door/core/extraction/ast_extractor.py:17-87` | `_init_language_loaders`：已註冊 11 種語言 grammar（python, typescript, javascript, java, go, rust, ruby, php, csharp, cpp, c） |
| TD-4 | `the_door/src/the_door/core/extraction/node_builder.py:49-262` | `_walk_python`：既有 Python 抽取，本 spec **不改動其行為**，只在重構後讓它走 config 路徑或維持原樣（見 5.4） |
| TD-5 | `the_door/src/the_door/core/extraction/node_builder.py:264-367` | `_walk_typescript`：既有 TS/JS 抽取，同上 |

---

## 2. 問題陳述（Root Cause）

### 2.1 已驗證的事實

`ASTExtractor` 在 TD-3 註冊了 **11 種** tree-sitter grammar。但 `NodeBuilder._walk`（TD-1）只對 `python` 和 `typescript`/`javascript` 有專屬抽取邏輯。其餘 **8 種**（java, go, rust, ruby, php, csharp, cpp, c）一律落到 `_walk_generic`（TD-2）。

`_walk_generic` 的判斷式（TD-2，node_builder.py:377、391）只用子字串比對：

```python
if "function_definition" in node.type or "function_declaration" in node.type:
    ...
if "class_definition" in node.type or "class_declaration" in node.type:
    ...
```

### 2.2 這個 fallback 為什麼是壞的

逐語言對照 codegraph 的權威 node-type（見第 4.1 節）後確認：

| 語言 | 函式/方法的真實 node type | `_walk_generic` 抓得到？ |
|---|---|---|
| Rust | `function_item` | ❌ 不含 `function_definition`/`function_declaration` 子字串 |
| Java | `method_declaration`, `constructor_declaration` | ❌ `method_declaration` 不含 `function_*` |
| Ruby | `method`, `singleton_method` | ❌ 完全不匹配 |
| C# | `method_declaration`, `constructor_declaration` | ❌ 同 Java |
| PHP | `function_definition`, `method_declaration` | ⚠️ 只抓到 `function_definition`，方法漏掉 |
| Go | `function_declaration`, `method_declaration` | ⚠️ 只抓到 `function_declaration`，方法漏掉 |
| C / C++ | `function_definition` | ✅ 可抓到函式 |

class 類同理：Rust 用 `struct_item`/`enum_item`/`trait_item`、Ruby 用裸 `class`、Go 沒有 class（用 `type_spec` 包 `struct_type`），全部抓不到。

額外缺陷（TD-2 內可見）：
- `_walk_generic` 遞迴時 `parent_class` 永遠是 `None`（沒有任何地方設值）→ 非 python/ts 語言的方法一律被標成 `function` 而非 `method`。
- 不抽 interface / struct / enum / signature。

### 2.3 影響

The Door 的 L1 功能分群品質取決於 node/edge 的完整度與語義正確度。對 8 種語言的專案，`extract_structure` 產出的 node 集合稀疏甚至為空 → LLM（或 agent-as-LLM）無從正確分群 → L1 特徵失真。

---

## 3. 目標與非目標

### 3.1 目標

- **G1**：把 `_walk_generic` 的寫死子字串比對，換成一張「每語言 → node-type 集合」的宣告式設定表，資料來源為 codegraph（CG-2…CG-11）。
- **G2**：讓 java, rust, ruby, php, csharp, c, cpp 七種語言能正確抽出 function / method / class（含巢狀 `parent_class` 判定）。
- **G3**：Go 的 `type_spec` → struct/interface 下鑽，作為唯一需要超出平面對照表的特例處理（見 5.3）。
- **G4**：python / typescript / javascript 的抽取行為**位元級不變**（既有測試全綠）。

### 3.2 非目標（明確不做，附原因）

| 不做 | 原因 |
|---|---|
| 引入 codegraph 的完整 `LanguageExtractor` interface 與 `ExtractorContext` hook 框架（CG-1） | codegraph 那套十幾個 hook 是為「19+ 語言共用一個核心 walker」付出的抽象成本。The Door node_builder 僅 464 行、需求單純（function/method/class 三類）。整套搬進來是 premature abstraction。**只借資料表，不借框架。** |
| 擴充 `ASTNode.type`（新增 struct/interface/enum/trait 等 kind） | 那是資料模型變更，會波及 edge_builder、snapshot、L1 分群、viewer。本 spec 把 struct/interface/enum/trait 的 grammar node 一律歸為 `type="class"`（見 5.2）。模型擴充另立 spec。 |
| 改 `edge_builder.py` 的多語言 call/import 偵測 | edge 偵測同樣有語言侷限，但與 node 抽取可獨立修。列為 follow-up（見第 8 節），不混入本 spec。 |
| 改用 codegraph 的 web-tree-sitter（WASM）runtime | The Door 是 Python 後端，用原生 `tree_sitter` binding 正確。換 WASM 只會引入記憶體碎片問題（codegraph `grammars.ts` 自身註解即記載多個 ABI 坑）。 |
| 採用 codegraph 的 SQLite property graph / MCP 查詢工具 / file watcher | 服務目標不同（codegraph 服務 AI agent 即時索引；The Door 服務版本 diff 與功能敘事）。與本 spec 無關。 |

---

## 4. 引用資料：node-type 對照表

### 4.1 權威對照表（2026-05-22 自 codegraph commit `5aae9c4` 抄錄）

> 下表為事實性資料（tree-sitter grammar 的 node 名稱），逐欄對應 codegraph
> `src/extraction/languages/<lang>.ts` 的 export 物件。欄位語義見 CG-1。
> **若實作時對某格有疑問，回查對應的 CG-編號檔案。**

| 語言 | function 類 | method 類 | class 類（The Door 統一歸 class） | 來源 |
|---|---|---|---|---|
| python | `function_definition` | `function_definition` | `class_definition` | CG-2 |
| typescript | `function_declaration`, `arrow_function`, `function_expression` | `method_definition`, `public_field_definition` | `class_declaration`, `abstract_class_declaration`, `interface_declaration`, `enum_declaration` | CG-3 |
| javascript | `function_declaration`, `arrow_function`, `function_expression` | `method_definition`, `field_definition` | `class_declaration` | CG-4 |
| java | （無）`[]` | `method_declaration`, `constructor_declaration` | `class_declaration`, `interface_declaration`, `enum_declaration` | CG-5 |
| go | `function_declaration` | `method_declaration` | （見 5.3 — `type_spec` 下鑽） | CG-6 |
| rust | `function_item` | `function_item` | `struct_item`, `enum_item`, `trait_item`；容器 `impl_item`（見下方註記） | CG-7 |
| ruby | `method` | `method`, `singleton_method` | `class` | CG-8 |
| php | `function_definition` | `method_declaration` | `class_declaration`, `trait_declaration`, `interface_declaration`, `enum_declaration` | CG-9 |
| csharp | （無）`[]` | `method_declaration`, `constructor_declaration` | `class_declaration`, `interface_declaration`, `struct_declaration`, `enum_declaration` | CG-10 |
| c | `function_definition` | （無） | `struct_specifier`, `enum_specifier` | CG-11 |
| cpp | `function_definition` | `function_definition` | `class_specifier`, `struct_specifier`, `enum_specifier` | CG-11 |

注意事項（抄錄時一併記下，避免回查時困惑）：
- **java / csharp 的 `functionTypes` 是空陣列**——這兩種語言沒有自由函式，只有方法。設定表保留空集合，不是遺漏。
- **ruby 的 node 名是裸字 `method` / `class`**——不是 `method_declaration`/`class_declaration`。這正是 `_walk_generic` 子字串比對對 Ruby 全失效的原因。
- **rust 的 method 與 function 同為 `function_item`**——兩者靠所在容器區分：位於 `impl_item` 或 `trait_item` 內 → method，否則 → function。關鍵：`impl_item` 是「容器但不是 class node」（`impl Foo` 不是型別宣告），平面的 class_types 表達不了，必須用 `container_types` 機制（見 5.2）。資料根據 CG-7：codegraph `rust.ts` 的 `classTypes` 為 `[]`，並由 `getReceiverType` 向上走訪尋找 `impl_item` parent。
- **cpp 的 method 與 function 同為 `function_definition`**——靠是否位於 `class_specifier` / `struct_specifier` 內區分（兩者皆在 cpp 的 class_types）。已知限制見第 8 節 follow-up #5。
- **typescript / javascript 兩列為完整抄錄，但本 spec 不使用**（見 5.4 範圍決策）——`arrow_function` / `function_expression` 等匿名函式形式由 The Door 既有的 `_walk_typescript` 自行處理，與本表無關，列出僅為對照完整性。

### 4.2 名稱欄位（identifier 取法）

codegraph 各語言 config 的 `nameField` 多數為 `"name"`。The Door 現有 `_child_text(node, "identifier")`（TD-2）走的是 child type 比對而非 field 名。

實作時的建議與**待確認事項**：

- 可考慮用 tree-sitter 的 `Node.child_by_field_name("name")`（對應 codegraph `nameField`）取名稱，較穩健。
- ⚠️ **The Door 現有 extraction 程式碼完全沒用過 `child_by_field_name`**（已 grep 驗證 node_builder.py / ast_extractor.py 無此呼叫）。它是 `tree_sitter` Python binding 的標準 API，但對 The Door 是新依賴——task 階段需先確認專案釘選的 `tree_sitter` 版本支援此方法，否則退回純 `_child_text` child-type 比對。
- 保底：取不到時 fallback 到既有的 `_child_text(node, "identifier")` / `"type_identifier"`。

此處若行為有疑問，回查 CG-2…CG-11 各檔的 `nameField` 值。

---

## 5. 設計

### 5.1 新增設定模組

新檔：`the_door/src/the_door/core/extraction/language_configs.py`

```python
"""Per-language tree-sitter node-type maps.

Data ported from codegraph commit 5aae9c4 (MIT, (c) 2026 Colby Mchenry),
files src/extraction/languages/*.ts. See
.kiro/specs/multilang-node-extraction/spec.md section 4.1 for the citation table.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LanguageConfig:
    function_types: frozenset[str] = field(default_factory=frozenset)
    method_types: frozenset[str] = field(default_factory=frozenset)
    class_types: frozenset[str] = field(default_factory=frozenset)
    # 容器節點：建立 parent scope（使內部函式歸為 method），但本身不產出 node。
    # 目前僅 Rust 的 impl_item 使用。見 5.2 step 2b。
    container_types: frozenset[str] = field(default_factory=frozenset)


LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "java": LanguageConfig(
        function_types=frozenset(),
        method_types=frozenset({"method_declaration", "constructor_declaration"}),
        class_types=frozenset({"class_declaration", "interface_declaration", "enum_declaration"}),
    ),
    "rust": LanguageConfig(
        function_types=frozenset({"function_item"}),
        method_types=frozenset({"function_item"}),
        class_types=frozenset({"struct_item", "enum_item", "trait_item"}),
        container_types=frozenset({"impl_item"}),
    ),
    # … ruby, php, csharp, c, cpp 同理，逐筆對照第 4.1 節 …
}
```

`container_types` 是本 spec 唯一超出「平面 node-type 對照」的欄位。它只有一個 frozenset、
只被 Rust 一種語言使用，用來表達一個無法迴避的真實語言構造（`impl` 區塊）。不加它，
Rust 的 method 會全數誤判為 function（違反 R3）；因此它是達成目標的最小必要結構，
不屬過度設計。

- 設定表只收 `_walk_generic` 負責的語言（java, go, rust, ruby, php, csharp, c, cpp）。
- python / typescript / javascript **不放進設定表**（見 5.4 的範圍決策）。

模組 docstring 必須保留 codegraph commit SHA 與授權聲明——這是回查的錨點，也是 MIT 授權要求。

### 5.2 改寫 `_walk_generic` → `_walk_config_driven`

取代 TD-2 的整個方法。新邏輯：

1. 用 `file_info.language` 查 `LANGUAGE_CONFIGS`；查不到 → 維持目前的子字串 fallback（保底，不退化）。
   - 註：在目前 11 種已註冊 grammar 下此分支不會命中（8 種有 config、python/ts/js 走另路）。
     刻意保留，是為「未來於 `ast_extractor` 新增 grammar loader 但尚未補 config」的保底，
     使新語言至少有粗略抽取而非整批落空。非死碼，是預留路徑。
2. `node.type ∈ class_types` → 建 `type="class"` node，並以此 class 名作為 `parent_class` 遞迴子節點。
2b. `node.type ∈ container_types` → **不建 node**；best-effort 解析容器名稱後，以該名稱作為
   `parent_class` 遞迴子節點。名稱解析失敗時以非 `None` 佔位字串代入，確保內部函式仍歸為 `method`。
   （Rust `impl_item` 的名稱解析：取其最後一個 `type_identifier` 子節點，邏輯依據 CG-7 `getReceiverType`。）
3. `node.type ∈ method_types` 且 `parent_class is not None` → 建 `type="method"`。
4. `node.type ∈ function_types`（或 `∈ method_types` 但 `parent_class is None`）→ 建 `type="function"`。
   - 處理 rust/cpp「method 與 function 同 node type」：靠 `parent_class` 是否為 `None` 決定 method 或 function。
     Rust 的 `parent_class` 由 step 2b（`impl_item`）或 step 2（`trait_item`）設定；cpp 由 step 2（`class_specifier`/`struct_specifier`）設定。
5. 其餘 → 遞迴 children，`parent_class` 原樣傳遞。

這修正了 2.2 末段「`parent_class` 永遠 `None`」的缺陷。

### 5.3 Go 特例

Go 沒有 class node。`type X struct {...}` 在 tree-sitter 是 `type_declaration` → `type_spec`（name 在此）→ `struct_type` / `interface_type`。

- 設定表中 Go 的 `class_types` 留空。
- `_walk_config_driven` 對 Go 額外處理：遇到 `type_spec`，檢查其 `type` field 的子節點；若為 `struct_type` 或 `interface_type` → 建 `type="class"` node。
- 此邏輯的根據是 CG-6 的 `resolveTypeAliasKind`。**回查時看 codegraph `src/extraction/languages/go.ts`。**
- Go method 的 receiver（CG-6 `getReceiverType`）**不在本 spec 範圍**——它影響限定名品質，列為 follow-up（第 8 節）。本 spec 只保證 Go method 被抽出且標為 `method`。

### 5.4 python / typescript 範圍決策

`_walk_python`（TD-4）與 `_walk_typescript`（TD-5）已能運作且有測試覆蓋。

**決策：本 spec 不重構這兩條路徑**，理由：
- G4 要求其行為位元級不變；重構它們會擴大風險面與測試負擔。
- 把它們也收進 config 表是「順手統一」的誘惑，但超出修復缺口的最小範圍。

`_walk` 分派維持三叉：python → `_walk_python`、ts/js → `_walk_typescript`、其餘 → `_walk_config_driven`。
第 4.1 節仍列出 python/ts/js 三列，純為對照完整性與未來統一時的參考，不代表本 spec 會用到。

---

## 6. 需求（Requirements）

- **R1**：新增 `language_configs.py`，內容逐筆對應第 4.1 節對照表，docstring 含 codegraph commit SHA + MIT 聲明。
- **R2**：`_walk_generic` 由 config-driven 版本取代；查無設定的語言維持舊子字串 fallback。
- **R3**：java, rust, ruby, php, csharp, c, cpp 的 function / method / class 均能抽出；巢狀於 class 節點或 `container_types`（Rust `impl_item`）內的方法 `type="method"`，否則 `type="function"`。
- **R4**：Go 的 function、method、`type_spec`-struct/interface 均能抽出。
- **R5**：python / typescript / javascript 既有測試全數維持綠燈（G4）。
- **R6**：每種新支援語言至少一個 fixture-based 測試，斷言抽出的 node 數量與 type/name（見第 7 節）。

---

## 7. 驗收與測試

- 測試遵循專案慣例「fixture 只放 input、不放 hand-built 結果」：每語言放一個最小原始碼 fixture（含 1 個 class + 1 個 method + 1 個自由函式，java/csharp 除外因無自由函式），呼叫 `ASTExtractor.extract`，斷言產出的 `ASTNode` 集合。
- Rust fixture **必須包含一個 `impl` 區塊內的方法**（外加 1 個 `struct` 與 1 個自由 `fn`），用以驗證 `container_types` 機制；斷言該 impl 方法 `type="method"`、自由函式 `type="function"`、struct `type="class"`。
- 先寫 **failing test**：對上述 Rust fixture 跑現況 `extract`，斷言「應抽出 3 個 node 且 impl 方法 `type="method"`」——預期紅燈（現況 `_walk_generic` 連 `function_item` 都不認），證明 2.2 的缺陷真實存在，再進行修復（TDD）。
- 驗收條件：
  - R3 / R4 的 7+1 種語言測試全綠。
  - R5：執行既有 extraction 測試套件，python/ts/js 相關全綠、數量不變。

---

## 8. Follow-up（不在本 spec 範圍，明確記錄以免遺漏）

1. **edge_builder 多語言化**：`edge_builder.py` 的 call/import/extends 偵測同樣偏 python/ts。可用同樣的 config-driven 手法，引用 codegraph 各語言 config 的 `callTypes` / `importTypes`（第 4.1 節未收，回查 CG-2…CG-11）。
2. **Go method receiver**：限定名加上 receiver type，引用 CG-6 `getReceiverType`。
3. **signature 抽取**：codegraph 各語言 config 有 `getSignature` hook，The Door 目前非 python/ts 語言不抽 signature。
4. **ASTNode.type 模型擴充**：若未來要區分 struct / interface / enum / trait，需另立 spec（見 3.2）。
5. **C++ class 外定義的方法**：`void Foo::bar() {}` 形式的 out-of-class method definition，其 `function_definition` 出現在 top-level，會被標為 `function` 而非 `method`。屬已知降級，與 codegraph 行為一致（codegraph 同樣不向上回溯 `Foo::` 限定符）。
6. **Rust trait 純簽章方法**：`trait` 內無預設實作的方法是 `function_signature_item`，不是 `function_item`，不會被抽出。與 codegraph `methodTypes: ['function_item']` 一致——本 spec 不擴大範圍處理。

---

## 9. 審查紀錄與下一步

- [x] code-review（`--concept` / design）已執行，2026-05-22。發現 1 critical + 1 warning + 2 suggestion：
  - critical：Rust `impl_item` 不在 class_types → 方法誤判 → **已修**（新增 `container_types`，見 5.1/5.2 step 2b）。
  - warning：4.1 表格 ts/js 兩列原為未讀檔的幻覺資料 → **已修**（實讀 CG-3/CG-4 後更正）。
  - suggestion：5.2 step 1 fallback 死分支 → **已修**（補註明為未來語言預留路徑）。
  - suggestion：C++ class 外方法降級 → **已修**（補入第 8 節 follow-up #5）。
- [ ] 用 writing-plans 產出 task plan。
- [ ] 本 spec 尚未排程實作。
