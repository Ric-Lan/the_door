# Scope-Aware Edge Resolution

**Date:** 2026-05-28
**Status:** Draft — pending user approval
**Builds on:** v1.4.0（L1 Prompt Context Modes + `LanguageConfig` declarative pattern）
**Defers:** W3 typed references、SCIP/LSIF 接入、跨 repo、新語言擴張

---

## 1. Goal — 產品宣告

**The Door 的跨檔關聯解析從「裸名猜測」升級為「scope-aware 解析」**：

- 7 種既支援語言（Python / TypeScript / Java / Go / Rust / Ruby / PHP / C#）一起升級
- **不增加任何 build 環境需求**（不接 SCIP / LSP / 編譯器）
- LLM 拿到的 edges 從「高信心錯誤多」變成「高信心正確 + 標記低信心 fallback」
- 既有 Feature / FeatureRelation / VersionSnapshot **schema 完全不變**，無 migration

對使用者的可觀察效果：
1. L1 features 的 description 內容更精準（LLM 不再被誤連邊誤導寫出自信錯誤內容）
2. Mindmap / 詳情面板顯示的關聯邊**邊質量**提升（誤連 ↓、漏連微升、provenance 可標示）
3. Diff 歸因（feature_attribution）精準度同步提升

---

## 2. Background — 現況問題

### 2.1 EdgeBuilder 的「裸名全域匹配」

`src/the_door/core/extraction/edge_builder.py` 第 79 行：

```python
if called_name in name_to_ids:
    for target_id in name_to_ids[called_name]:
        edges.append(Edge(...))
```

`name_to_ids` 是 `dict[str, list[node_id]]`，全 codebase 共用。一個 `foo()` call 會連到**所有**叫 `foo` 的節點，不分檔案、不分類別、不看 import。

實例：

```python
# orders/validator.py
def validate(cart): ...

# users/validator.py
def validate(user): ...

# orders/service.py
result = validate(cart)  # 目前：兩條邊都連，LLM 看到「validate 同時來自 orders 跟 users」
```

### 2.2 對 LLM 翻譯的具體傷害

v1.4.0 把節點完整 signature/docstring 送進 prompt，LLM 看到的「節點本身」已經夠用。**目前剩下的翻譯品質瓶頸落在「節點之間的關聯」**：

- LLM 看到 5 條 `process` 來源的邊 → 寫描述時要嘛挑一條（可能挑錯）、要嘛寫成模糊的「處理多種 process 流程」
- 漏掉 import alias 解析（`from foo import bar as baz` → `baz()` 沒連回 foo.bar）
- 繼承鏈不解析（`super().validate()` 沒連到 parent class 的 validate）

### 2.3 為什麼不接 SCIP

評估後**明確排除** SCIP / LSIF 接入：

| SCIP 帶入的耦合 | 對 The Door「通用型基礎建設翻譯」定位的傷害 |
|---|---|
| 每語言 indexer 需要可建構環境（venv / node_modules / maven build） | 「指向資料夾即分析」破功 |
| PHP 無官方 indexer、C# 早期 | 「所有語言通用」打折 |
| protobuf schema 由 Sourcegraph 控制 | 上游改向被綁架 |
| 每個 indexer 符號格式 quirks 不同 | 又得寫 6 套 per-language adapter |
| 跑 indexer 前要先解 build 依賴 | 把「給非技術讀者的工具」變成「先教使用者搞 build」 |

**SCIP 解的是工程師問題**（IDE-grade navigation、jump-to-definition）；The Door 解的是非技術讀者問題。兩條路。

---

## 3. Non-Goals

明確列為**本 spec 不做**：

| 項目 | 為何不做 | 何時可考慮 |
|---|---|---|
| **W3 typed references**（變數 type 推導） | 縮水版 type checker → 產生「自信錯誤」反而傷 LLM；做完整等於再造 pyright / tsc | 永遠不做（定位上不對齊） |
| **SCIP / LSIF 接入** | 見 §2.3 | 永遠不做（定位上不對齊） |
| **跨 repo 分析** | 另一個產品宣告（node_id 升全域符號 + snapshot 路徑改造 + UI 多 repo 切換） | 另開 spec |
| **新語言擴張**（Kotlin / Scala / Swift / Elixir 等） | 7 語言齊做已經是本 spec 上限 | 另開 spec |
| **動態 dispatch 完整解析**（Ruby method_missing / Python `__getattr__` / Java reflection DI） | 結構性無解 | 永遠標 `skipped_dynamic`，不假裝解 |
| **Edge UI 視覺差異化** | 不在抽取層範圍 | 後續 viewer spec 可吃 provenance 加渲染 |

---

## 4. Design — 架構

### 4.1 三層結構

```
┌─────────────────────────────────────────────────────────┐
│ LanguageConfig（既有，v1.4.0 declarative pattern 延伸） │
│   + scope_rules: ScopeRules | None                     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ ScopeRules（新 dataclass）                              │
│   - import_resolution: ImportStrategy                  │
│   - function_resolution: FunctionStrategy              │
│   - method_resolution: MethodStrategy                  │
│   - inheritance_resolution: InheritanceStrategy        │
│   - dynamic_markers: frozenset[str]                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ EdgeBuilder._resolve()（重寫）                          │
│   1. 嘗試 scope rule 解析                                │
│   2. 解不到 → fallback to name_match                    │
│   3. 動態 marker → 標 skipped_dynamic、不解析            │
│   每條 edge 標 resolution provenance                    │
└─────────────────────────────────────────────────────────┘
```

### 4.2 `ScopeRules` schema

```python
from typing import Literal
from dataclasses import dataclass, field

ImportStrategy = Literal[
    "qualified",      # Python: from module import name (alias 追蹤)
    "namespaced",     # Java/C#/PHP: package.Class / namespace
    "module_path",    # Go/Rust: 模組路徑前綴
    "es_module",      # TS/JS: ES6 import + alias
]

FunctionStrategy = Literal[
    "file_local_then_imports",   # 同檔優先，否則 import 解析
    "package_local_then_imports",# 同 package/module 優先
    "global",                    # Ruby 風格：全域 namespace 加 monkey patching
]

MethodStrategy = Literal[
    "class_local_then_inherited",  # 同類別優先，再走繼承鏈
    "structural",                  # Go interface 結構性滿足
    "trait_dispatch",              # Rust trait
    "dynamic_dispatch",            # Python / Ruby：標 dynamic
]

InheritanceStrategy = Literal[
    "single",      # Java / C# / Rust: 單繼承（trait 不算）
    "multiple",    # Python / C++: 多繼承 / MRO
    "mixin",       # Ruby: include / extend
    "interface_only",  # Go: 沒繼承，只有 interface
]


@dataclass(frozen=True)
class ScopeRules:
    import_resolution: ImportStrategy
    function_resolution: FunctionStrategy
    method_resolution: MethodStrategy
    inheritance_resolution: InheritanceStrategy
    # 偵測到此 type / pattern 的節點 → 標 skipped_dynamic 不嘗試解析
    dynamic_markers: frozenset[str] = field(default_factory=frozenset)
```

### 4.3 七語言 `ScopeRules` 對照表（W1 + W2）

| 語言 | import | function | method | inheritance | dynamic_markers |
|---|---|---|---|---|---|
| Python | qualified | file_local_then_imports | class_local_then_inherited | multiple | `getattr_call`, `__getattr__` def |
| TypeScript | es_module | file_local_then_imports | class_local_then_inherited | single | `any_typed_call` |
| Java | namespaced | package_local_then_imports | class_local_then_inherited | single | `reflection_invoke` |
| Go | module_path | package_local_then_imports | structural | interface_only | `reflect_value_call` |
| Rust | module_path | package_local_then_imports | trait_dispatch | single | `dyn_trait_call` |
| Ruby | qualified | global | dynamic_dispatch | mixin | `method_missing` def, `define_method`, `send` |
| PHP | namespaced | package_local_then_imports | class_local_then_inherited | single | `__call`, `call_user_func` |
| C# | namespaced | package_local_then_imports | class_local_then_inherited | single | `dynamic` keyword, reflection |

**註：Ruby 因為 monkey patching + method_missing 太常見，`method_resolution` 直接設 `dynamic_dispatch` —— 等同把 method 解析全部 fallback 到 name_match + provenance 標 `dynamic`，不假裝精準。**

### 4.4 `Edge` provenance schema

```python
@dataclass(frozen=True)
class Edge:
    from_node: str
    to_node: str
    edge_type: Literal["call", "extends", "implements", "imports"]
    # 新增欄位
    resolution: Literal["scope_rule", "import_alias", "name_match", "skipped_dynamic"]
```

`resolution` 語意：
- `scope_rule` — 透過 scope rules 明確解到（**高信心**）
- `import_alias` — 透過 import alias 解到（**高信心**）
- `name_match` — fallback 到舊的裸名匹配（**低信心，僅供參考**）
- `skipped_dynamic` — 偵測到動態 dispatch context（method_missing / __getattr__ / reflection），**仍保留 name_match 候選邊**但標明「靠裸名找到、不可採信為事實」

### 4.5 LLM prompt 變化

`L1_SYSTEM_PROMPT` 新增一段：

> 你會收到的節點之間有 `edges`，每條邊有 `resolution` 標籤：
> - `scope_rule` / `import_alias`：**高信心**，可以放心採用為事實
> - `name_match`：**低信心**，可能是程式內多個同名節點之一，僅作參考；若描述會因為它的不確定性而產生分歧，**寧可不提**
> - `skipped_dynamic`：動態 dispatch 解不到，**不要對此邊的目的端做任何斷言**

### 4.6 EdgeBuilder 重寫流程

```python
ResolutionType = Literal["scope_rule", "import_alias", "name_match", "skipped_dynamic"]


def _resolve(
    self, name: str, context: ScopeContext, rules: ScopeRules
) -> list[tuple[str, ResolutionType]]:
    """回傳 (target_node_id, resolution) 的 list。空 list 表示無邊產生。

    多目標只在 name_match fallback 情境出現（裸名撞到多個候選）；
    scope_rule / import_alias 一律單目標，skipped_dynamic 無目標但保留標記邊。
    """
    # 1. 動態 markers 檢查 — 仍走 name_match 但標 skipped_dynamic
    if context.has_dynamic_marker(rules.dynamic_markers):
        matches = self._name_to_ids.get(name, [])
        # 保留所有 name_match 候選，但 resolution 標 skipped_dynamic
        # 語意：「不嘗試 scope 解析、靠裸名找到的候選你別當真」
        return [(m, "skipped_dynamic") for m in matches]

    # 2. 嘗試 scope rule 解析（單目標）
    scoped_target = self._resolve_by_scope(name, context, rules)
    if scoped_target:
        return [(scoped_target, "scope_rule")]

    # 3. 嘗試 import alias 解析（單目標）
    aliased_target = self._resolve_by_import_alias(name, context, rules)
    if aliased_target:
        return [(aliased_target, "import_alias")]

    # 4. Fallback：保留原本 name_match（多目標、低信心）
    matches = self._name_to_ids.get(name, [])
    return [(m, "name_match") for m in matches]
```

**關鍵紀律：** 第 4 步 fallback **必須保留**，確保新版本不會比舊版本漏邊。「可見的低信心邊」**比**「靜默漏邊」**好**。

---

## 5. Three Noise Disciplines（雜訊紀律）

本 spec 的設計核心約束，所有實作必須遵守：

### 紀律 1：每條 edge 標 provenance（§4.4）

無例外。沒有「裸 Edge」存在的可能性。`Edge` 建構時 `resolution` 必填。

### 紀律 2：Scope 解不出時 fallback to name_match（§4.6 第 4 步）

**不丟邊**。理由：
- 漏邊 = 靜默失真，使用者察覺不到
- name_match 邊 = 標明低信心，LLM 與 viewer 都可決定要不要採用
- 「可見的雜訊」嚴格優於「隱形的雜訊」

### 紀律 3：動態 dispatch 節點明示「不解析」（§4.3 dynamic_markers）

對偵測到 Ruby `method_missing` / Python `__getattr__` / Java reflection / C# `dynamic` 的呼叫情境：**直接標 `skipped_dynamic`、不嘗試解析**。

承認「結構上解不了」**好過**「半套解析產生自信錯誤」。LLM prompt 明示此類邊不可作為事實依據。

---

## 6. Data Flow

### 6.1 抽取階段（ASTExtractor → EdgeBuilder）

```
trees: dict[file, (Tree, source_bytes)]
nodes: list[ASTNode]               ← v1.4.0 已 enriched
config: dict[lang, LanguageConfig] ← 加 scope_rules
                ↓
EdgeBuilder.build_edges(nodes, trees, configs)
    └─ per file: _detect_calls / _detect_extends / _detect_imports
        └─ each call site: _resolve(name, ctx, rules) → (target, provenance)
                ↓
edges: list[Edge]                  ← 每條帶 resolution 標籤
```

### 6.2 LLM 階段（BatchReader）

```
StructureJSON.edges → BatchReader._build_payload
    └─ detail mode: 序列化每條 edge 含 resolution
                ↓
LLM 收到的 prompt 包含 edges 與 provenance 標籤
    └─ L1_SYSTEM_PROMPT 教 LLM 如何看待四種 resolution
                ↓
L1Output.features（description 品質提升）
```

### 6.3 Viewer / Snapshot 階段（向後相容）

```
- VersionSnapshot schema 不變
- snapshot.l1_output 不變
- snapshot.edges 多 resolution 欄位，但舊 snapshot 沒這欄位 → loader 給預設值 "name_match"
```

向後相容路徑：舊 snapshot 讀進來時所有 edge `resolution=name_match`（行為等同 v1.4.0），不破壞既有資料。

---

## 7. Acceptance Criteria

### 7.1 結構性驗收（必達）

- [ ] `LanguageConfig.scope_rules` 欄位存在，7 種語言皆有非 None 值
- [ ] `ScopeRules` dataclass 含 §4.2 列出的 5 欄位
- [ ] `Edge.resolution` 欄位存在，所有新產生的 edge 必填
- [ ] `EdgeBuilder._resolve()` 走「scope → alias → name_match fallback」三段式
- [ ] 動態 markers 偵測：7 語言至少各 1 個 dynamic_markers 規則被測試覆蓋
- [ ] 舊 snapshot 載入時 `resolution` 預設為 `"name_match"`（向後相容）
- [ ] L1_SYSTEM_PROMPT 含 §4.5 的四種 resolution 說明

### 7.2 數據驗收（量化，用 the_door 自己 + v105 跑）

用 the_door 自己跑 dogfood 比對（v1.4.0 vs 本 spec ship 後）：

| 指標 | 期望變化 | 容忍區間 |
|---|---|---|
| 總邊數 | 下降 | -10% ~ -30% |
| `scope_rule` + `import_alias` 邊佔比 | ≥ 50% | — |
| `name_match` 殘留邊佔比 | ≤ 40% | — |
| `skipped_dynamic` 邊佔比 | 因語言而異 | Ruby/Python 可能較高 |
| 邊**錯誤率**（人工抽 50 條） | 下降 50%+ | 強制達標 |
| 邊**漏抓率**（人工抽 30 條 known edges） | 上升 ≤ 10% | 容忍 |

### 7.3 LLM 主觀驗收（spec §11 acceptance proxy）

抽 10 個 L1 feature description 對比 §4.2 風格規則違反條目數（沿用 v1.4.0 acceptance proxy 流程）。本 spec ship 後違反條目數應**≤ v1.4.0 已 ship 版本**。

### 7.4 紀律驗收（程式碼層面）

- [ ] **紀律 1**：grep 證明 `Edge(` 所有建構處皆有 `resolution=` 參數
- [ ] **紀律 2**：`_resolve()` 函式必有 fallback 路徑、且有 property test 釘住「scope 失敗時必出 name_match edge」
- [ ] **紀律 3**：dynamic_markers 偵測在 7 語言至少各有一個正向測試

---

## 8. Risks & Mitigations

### Risk 1：Tree-sitter grammar 對 scope 上下文支援不齊

v1.4.0 教訓：Ruby 把 method 包在 `body_statement`、PHP grammar quirks、Rust `attribute_item` 都吃過虧。Scope rules 仰賴更深的 AST 上下文，**風險更大**。

**Mitigation：**
- 接受 xfail：明確解不出的情境標 xfail 並文件化為 known limitation
- Per-language smoke test 在實作每語言的 ScopeRules 前**先寫 5 個典型場景 fixture**，確認 grammar 能拿到必要上下文
- Fallback to name_match 是兜底（紀律 2）

### Risk 2：「Schema 演化」破壞既存 snapshot

`Edge` 加欄位 → 舊 snapshot 格式不含 `resolution`。

**Mitigation：**
- Snapshot loader 給預設值 `"name_match"`（§6.3）
- 加 schema migration test：載入 v1.4.0 snapshot、確認 edges 全部 `resolution=name_match`、行為等同 v1.4.0

### Risk 3：實作工期溢出

7 語言 × W1+W2 估計 10-13 任務（v1.4.0 是 9 任務）。Grammar quirks 可能拖長。

**Mitigation：**
- Phase 0 任務：先用 Python 把 `ScopeRules` schema 釘死，再開始填其他 6 語言（避免半路改 schema）
- 動態語言 Ruby 強制使用 `method_resolution=dynamic_dispatch`（§4.3 註），不假裝精準 → 縮減 Ruby 任務量
- 任務拆檔每個語言獨立可平行

### Risk 4：「自信錯誤」變成「保守模糊」反而讓使用者體驗變差

新雜訊形狀（漏邊 / 模糊）**可能**讓 description 變得語氣保守，使用者感覺「少了東西」。

**Mitigation：**
- LLM prompt 明示「name_match 邊不夠肯定就不要寫進 description，但可以提及『此節點與 X 區域可能有關』」
- 驗收標準 §7.2 設「漏抓率 ≤ 10%」上限
- v1.4.0 detail mode 已經補強單節點脈絡，scope 升級後 LLM 的「節點本身理解」不變、只是「節點間關聯」更乾淨

### Risk 5：本 spec ship 後又被要求「補 W3」

W3 永遠的拒絕理由（§3）：定位不對齊。

**Mitigation：**
- §3 Non-Goals 表格寫死「永遠不做」
- W3 的正確擁有者是 SCIP / LSP / pyright / rust-analyzer
- 若使用者需求變化（例如轉做工程師工具），這是大方向 pivot，不是 spec 補丁

---

## 9. Implementation Layering（給 plan 階段參考）

預期任務分層（plan 階段會細化，這裡給方向）：

1. **Phase 0 — Schema 釘死**：`ScopeRules` dataclass + `Edge.resolution` schema + 載入向後相容
2. **Phase 1 — Python ScopeRules 完整實作**：證明 schema 涵蓋得了真實語言（dogfood）
3. **Phase 2 — EdgeBuilder 重寫**：generic `_resolve()` + provenance 標記 + fallback 路徑
4. **Phase 3 — TS / Java / Go / Rust / C# / PHP / Ruby**：六語言 ScopeRules 平行填入（Ruby 簡化版）
5. **Phase 4 — LLM prompt 更新**：L1_SYSTEM_PROMPT 教 LLM 看 resolution
6. **Phase 5 — 驗收 + CHANGELOG + README + dogfood 比對報告**

---

## 10. References

- **v1.4.0 spec**：`docs/superpowers/specs/2026-05-27-l1-prompt-context-modes-design.md`（同模式 declarative LanguageConfig 延伸）
- **v1.4.0 plan**：`docs/superpowers/plans/2026-05-27-l1-prompt-context-modes/` 對照
- **EdgeBuilder 現況**：`src/the_door/core/extraction/edge_builder.py`
- **LanguageConfig 現況**：`src/the_door/core/extraction/language_configs.py`
- **L1_SYSTEM_PROMPT 現況**：`src/the_door/core/llm/prompts.py`

---

## 11. Out-of-spec future TODOs（記錄）

- **DB schema diff as L1 signal**（spawn_task 已記，使用 sqlglot）
- **Cross-repo analysis**（node_id 升全域符號）
- **Scope rules for new languages**（Kotlin / Scala / Swift / Elixir）
- **LLM 看 resolution 後的 confidence schema 增強**（若 ship 後實證資料顯示有需要）
