# Task 03 — `_walk_config_driven` Enriched Builder

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `_walk_config_driven` 內每個產出 `ASTNode(...)` 的分支改用統一 `_build_enriched_node` 函式，呼叫 4 個 helper（`_extract_parameters` / `_extract_return_type` / `_extract_decorators` / `_extract_doc_comment`）填滿 ASTNode 內容欄位。產出後對 java/go/rust/ruby/php/csharp 6 語言至少能抽出 parameters + docstring + decorators（依該語言慣例）。

**Architecture:** 引入 `_build_enriched_node(node, cfg, file_info, kind, parent_class)` 取代各分支內手寫 ASTNode 建構。`comments` 維持 `[]`（generic 路徑暫不收）。Python / TypeScript 走專用 walker，不受本任務影響。

**Tech Stack:** Python 3.11+, tree-sitter, pytest, pytest fixtures。

**Test Coverage Requirement:** `_walk_config_driven`、`_build_enriched_node` 與 4 個 extract helper 合計達 100% line coverage。每個 LANGUAGE_CONFIGS 註冊語言（java/go/rust/ruby/php/csharp）至少 1 個 fixture 測試覆蓋 enriched 抽取路徑。pytest 加 `--cov=the_door.core.extraction.node_builder --cov-fail-under=100`。

---

## Background（自含）

`_walk_config_driven` 在 `the_door/src/the_door/core/extraction/node_builder.py:370-499` 是 config-driven 通用 walker，處理 java/go/rust/ruby/php/csharp 等語言。它在 4 個分支建構 ASTNode：

1. fallback path（語言不在 LANGUAGE_CONFIGS）
2. Go `type_spec` special case
3. Class nodes（node.type ∈ cfg.class_types）
4. Method nodes inside class（node.type ∈ cfg.method_types and parent_class is not None）
5. Orphaned method nodes（method_types but no parent class — Go 頂層方法）
6. Function nodes（node.type ∈ cfg.function_types）

**問題**：每個分支建構 ASTNode 時只填 node_id / type / name / file / language 5 個欄位，其他內容欄位（parameters / return_type / decorators / docstring / comments）保留 dataclass 預設（[] / None）。

`LanguageConfig` 已在前置任務（檔案 `language_configs.py`）擴充加上 6 個抽取規則欄位。4 個 extract helper 已在前置任務加到 `NodeBuilder` 內。本任務把它們串起來。

`ASTNode` 定義（`the_door/src/the_door/models.py:19-31`）：

```python
@dataclass(frozen=True)
class ASTNode:
    node_id: str
    type: str
    name: str
    file: str
    language: str
    decorators: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    return_type: str | None = None
    docstring: str | None = None
    comments: list[str] = field(default_factory=list)
```

**重要**：Python `_walk_python` 與 TypeScript `_walk_typescript` 走專用 walker，**本任務不動它們**。

---

## Files

- Modify: `the_door/src/the_door/core/extraction/node_builder.py`
- Create fixtures: `the_door/tests/fixtures/multilang/{java,go,rust,ruby,php,csharp}/sample.<ext>`
- Test (new): `the_door/tests/unit/core/extraction/test_walk_config_driven_enriched.py`

---

## Steps

### Step 1 — Create per-language fixtures

- [ ] **Step 1: Create 6 minimal source files for fixtures**

Create the following files. Each must contain at least one function/method with: (a) parameters, (b) a doc-comment matching the language's convention, (c) where applicable, an annotation/attribute/decorator.

File `the_door/tests/fixtures/multilang/java/sample.java`:

```java
/** Greet someone with a custom message. */
@Deprecated
public class Greeter {
    public String greet(String name, int times) {
        return "hello " + name;
    }
}
```

File `the_door/tests/fixtures/multilang/go/sample.go`:

```go
// Greet builds a greeting line.
// Returns the formatted message.
func Greet(name string, times int) string {
    return "hello " + name
}
```

File `the_door/tests/fixtures/multilang/rust/sample.rs`:

```rust
/// Greet someone by name.
/// Returns the formatted string.
#[derive(Debug)]
pub struct Greeter;

impl Greeter {
    /// Build the greeting.
    pub fn greet(&self, name: &str, times: i32) -> String {
        format!("hello {}", name)
    }
}
```

File `the_door/tests/fixtures/multilang/ruby/sample.rb`:

```ruby
class Greeter
  # Greet someone by name.
  # Returns a string.
  def greet(name, times)
    "hello #{name}"
  end
end
```

File `the_door/tests/fixtures/multilang/php/sample.php`:

```php
<?php
class Greeter {
    /** Greet someone by name. */
    public function greet(string $name, int $times): string {
        return "hello " . $name;
    }
}
```

File `the_door/tests/fixtures/multilang/csharp/sample.cs`:

```csharp
public class Greeter {
    /// <summary>Greet someone by name.</summary>
    [System.Obsolete]
    public string Greet(string name, int times) {
        return "hello " + name;
    }
}
```

### Step 2 — Write failing tests

- [ ] **Step 2: Write per-language ASTNode enrichment tests**

Create `the_door/tests/unit/core/extraction/test_walk_config_driven_enriched.py`:

```python
"""Tests that _walk_config_driven produces enriched ASTNode for 6 languages."""
from __future__ import annotations

from pathlib import Path

import pytest

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.models import ASTNode


FIXTURE_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "multilang"


def _extract_for_language(lang: str, ext: str) -> list[ASTNode]:
    path = FIXTURE_DIR / lang / f"sample.{ext}"
    assert path.exists(), f"fixture missing: {path}"
    extractor = ASTExtractor()
    # ASTExtractor 公開介面用法：對單一檔案抽取。實作可能用 extract() 接資料夾，
    # 此處只取該檔結果。若 ASTExtractor 強制資料夾輸入，改成 path.parent。
    result = extractor.extract(str(path.parent))
    return [n for n in result.nodes if n.file.endswith(f"sample.{ext}")]


def _find_method_or_function(nodes: list[ASTNode], name_substring: str) -> ASTNode:
    matches = [n for n in nodes if name_substring.lower() in n.name.lower()]
    assert matches, f"no node containing {name_substring!r} in {[n.name for n in nodes]}"
    # Prefer method/function over class.
    for n in matches:
        if n.type in ("method", "function"):
            return n
    return matches[0]


class TestJavaEnrichment:
    def test_greet_method_has_parameters(self):
        nodes = _extract_for_language("java", "java")
        greet = _find_method_or_function(nodes, "greet")
        assert any("name" in p for p in greet.parameters)
        assert any("times" in p for p in greet.parameters)

    def test_class_has_block_comment_docstring(self):
        nodes = _extract_for_language("java", "java")
        greeter = next((n for n in nodes if n.name == "Greeter"), None)
        assert greeter is not None
        assert greeter.docstring is not None
        assert "Greet" in greeter.docstring

    def test_class_has_annotation_decorator(self):
        nodes = _extract_for_language("java", "java")
        greeter = next((n for n in nodes if n.name == "Greeter"), None)
        assert greeter is not None
        assert any("Deprecated" in d for d in greeter.decorators)


class TestGoEnrichment:
    def test_function_parameters(self):
        nodes = _extract_for_language("go", "go")
        greet = _find_method_or_function(nodes, "Greet")
        assert any("name" in p for p in greet.parameters)

    def test_function_docstring_from_preceding_line_comments(self):
        nodes = _extract_for_language("go", "go")
        greet = _find_method_or_function(nodes, "Greet")
        assert greet.docstring is not None
        assert "greeting" in greet.docstring.lower()


class TestRustEnrichment:
    def test_struct_has_outer_doc(self):
        nodes = _extract_for_language("rust", "rs")
        greeter = next((n for n in nodes if n.name == "Greeter"), None)
        assert greeter is not None
        assert greeter.docstring is not None
        assert "Greet someone" in greeter.docstring

    def test_struct_has_derive_attribute(self):
        nodes = _extract_for_language("rust", "rs")
        greeter = next((n for n in nodes if n.name == "Greeter"), None)
        assert greeter is not None
        assert any("derive" in d for d in greeter.decorators)

    def test_method_parameters_extracted(self):
        nodes = _extract_for_language("rust", "rs")
        greet = _find_method_or_function(nodes, "greet")
        joined = " ".join(greet.parameters)
        assert "name" in joined

    def test_method_return_type(self):
        nodes = _extract_for_language("rust", "rs")
        greet = _find_method_or_function(nodes, "greet")
        assert greet.return_type is not None
        assert "String" in greet.return_type


class TestRubyEnrichment:
    def test_method_has_doc_comment(self):
        nodes = _extract_for_language("ruby", "rb")
        greet = _find_method_or_function(nodes, "greet")
        assert greet.docstring is not None
        assert "name" in greet.docstring.lower()

    def test_method_parameters(self):
        nodes = _extract_for_language("ruby", "rb")
        greet = _find_method_or_function(nodes, "greet")
        joined = " ".join(greet.parameters)
        assert "name" in joined
        assert "times" in joined

    def test_method_no_decorators(self):
        nodes = _extract_for_language("ruby", "rb")
        greet = _find_method_or_function(nodes, "greet")
        assert greet.decorators == []


class TestPhpEnrichment:
    def test_method_phpdoc_extracted(self):
        nodes = _extract_for_language("php", "php")
        greet = _find_method_or_function(nodes, "greet")
        if greet.docstring is None:
            pytest.xfail("PHP grammar quirk — see Task 03 acceptance note")
        assert "Greet" in greet.docstring

    def test_method_parameters(self):
        nodes = _extract_for_language("php", "php")
        greet = _find_method_or_function(nodes, "greet")
        joined = " ".join(greet.parameters)
        assert "name" in joined


class TestCsharpEnrichment:
    def test_method_xmldoc_extracted(self):
        nodes = _extract_for_language("csharp", "cs")
        greet = _find_method_or_function(nodes, "Greet")
        assert greet.docstring is not None
        assert "Greet" in greet.docstring

    def test_method_attribute_extracted(self):
        nodes = _extract_for_language("csharp", "cs")
        greet = _find_method_or_function(nodes, "Greet")
        assert any("Obsolete" in d for d in greet.decorators)


class TestCommentsFieldEmptyForGenericPath:
    """generic walker 統一 comments=[]（spec §3.5）。"""

    @pytest.mark.parametrize("lang,ext", [
        ("java", "java"), ("go", "go"), ("rust", "rs"),
        ("ruby", "rb"), ("php", "php"), ("csharp", "cs"),
    ])
    def test_comments_is_empty_list(self, lang, ext):
        nodes = _extract_for_language(lang, ext)
        for n in nodes:
            assert n.comments == [], f"{lang} {n.name} should have empty comments (generic path)"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest the_door/tests/unit/core/extraction/test_walk_config_driven_enriched.py -v`
Expected: 多數 PASS 的 assertion 在 enrichment 接好之前 FAIL，例如 `assert greet.docstring is not None` 失敗（docstring 為 None）、`assert any(...)` 對空列表失敗等。

### Step 3 — Implement `_build_enriched_node` + wire into 4 branches

- [ ] **Step 4: Add _build_enriched_node helper to NodeBuilder**

Open `the_door/src/the_door/core/extraction/node_builder.py`. Add this method to the `NodeBuilder` class (alongside the 4 extract helpers added in the previous task):

```python
    def _build_enriched_node(
        self,
        node,
        cfg,                # LanguageConfig
        file_info,          # FileInfo
        kind: str,          # "function" | "method" | "class"
        name: str,
    ):
        """Build an ASTNode with all content fields populated via cfg + helpers."""
        from the_door.models import ASTNode
        return ASTNode(
            node_id=f"{file_info.path}::{name}",
            type=kind,
            name=name,
            file=file_info.path,
            language=file_info.language,
            parameters=self._extract_parameters(node, cfg.parameters_field),
            return_type=self._extract_return_type(node, cfg.return_type_field),
            decorators=self._extract_decorators(node, cfg.decorator_types),
            docstring=self._extract_doc_comment(
                node,
                cfg.doc_comment_strategy,
                cfg.doc_comment_types,
                cfg.doc_comment_markers,
            ),
            comments=[],   # generic 路徑不收 comments
        )
```

- [ ] **Step 5: Replace ASTNode constructions in _walk_config_driven**

Locate `_walk_config_driven`. Replace each branch's hand-written `ASTNode(...)` block with a call to `_build_enriched_node`. The 6 branches are:

1. **Fallback path (cfg is None)** — function/class shape match: keep the existing minimal ASTNode (no cfg available, no enrichment possible). Add an inline comment to make this explicit.
2. **Go type_spec special case** — class kind. Replace ASTNode constructor.
3. **Class nodes** — `if node.type in cfg.class_types`. Replace ASTNode constructor.
4. **Method nodes inside class** — `if node.type in cfg.method_types and parent_class is not None`. Replace.
5. **Orphaned method nodes** — `if node.type in cfg.method_types and node.type not in cfg.function_types`. Replace.
6. **Function nodes** — `if node.type in cfg.function_types`. Replace.

Concrete diff pattern (apply to each of branches 2–6):

```python
# BEFORE (e.g. class branch):
if node.type in cfg.class_types:
    name = self._extract_name(node, file_info.language)
    if name:
        results.append(ASTNode(
            node_id=f"{file_info.path}::{name}",
            type="class",
            name=name,
            file=file_info.path,
            language=file_info.language,
        ))
        for child in node.children:
            self._walk_config_driven(child, file_info, results, name)
    else:
        for child in node.children:
            self._walk_config_driven(child, file_info, results, parent_class)
    return

# AFTER:
if node.type in cfg.class_types:
    name = self._extract_name(node, file_info.language)
    if name:
        results.append(
            self._build_enriched_node(node, cfg, file_info, "class", name)
        )
        for child in node.children:
            self._walk_config_driven(child, file_info, results, name)
    else:
        for child in node.children:
            self._walk_config_driven(child, file_info, results, parent_class)
    return
```

For the **fallback path** (cfg is None), add an inline comment but keep the existing minimal ASTNode build:

```python
# Fallback for languages not in LANGUAGE_CONFIGS — no cfg means no enrichment.
# This is intentional: detail mode value here is limited to node_id + file path.
```

For the **Go type_spec branch**, the kind is `"class"`:

```python
if file_info.language == "go" and node.type == "type_spec":
    type_child = node.child_by_field_name("type")
    if type_child is not None and type_child.type in ("struct_type", "interface_type"):
        name = self._get_name_by_field(node)
        if name:
            results.append(
                self._build_enriched_node(node, cfg, file_info, "class", name)
            )
    return
```

For method / orphaned method / function branches: same pattern with `kind` set to `"method"` or `"function"` as appropriate.

- [ ] **Step 6: Run tests**

Run: `pytest the_door/tests/unit/core/extraction/test_walk_config_driven_enriched.py -v`
Expected: All previously failing assertions now PASS。少數 `xfail` 因 grammar quirk 允許保留。

若某語言測試仍失敗，先驗證該語言 grammar 的實際 field name（在 Python REPL 用 tree_sitter 載入 grammar、印出 parse tree），就地修正 `language_configs.py` 對應欄位（屬於 spec §3.4 「就地修正」彈性）。

- [ ] **Step 7: Coverage check**

Run: `pytest the_door/tests/unit/core/extraction/ --cov=the_door.core.extraction.node_builder --cov-report=term-missing`

Expected:
- `_walk_config_driven`、`_build_enriched_node`、4 個 helper 合計 100% line coverage
- 若有未覆蓋分支（如 fallback path、Go type_spec），補測試直到 100%

- [ ] **Step 8: Full regression**

Run: `pytest the_door/tests/ -x -q`
Expected: 無新 failure。既有 batch_reader / pipeline / scenario 測試應不受影響（generic walker 抽出更豐富的 ASTNode 仍是同樣 ASTNode 介面）。

- [ ] **Step 9: Commit**

```bash
git add the_door/src/the_door/core/extraction/node_builder.py the_door/tests/unit/core/extraction/test_walk_config_driven_enriched.py the_door/tests/fixtures/multilang/
git commit -m "feat(extraction): enrich ASTNode in _walk_config_driven for 6 languages

java/go/rust/ruby/php/csharp now produce ASTNode with parameters,
return_type, decorators, docstring populated via _build_enriched_node.
Python/TS walkers unchanged. comments=[] per spec §3.5 to avoid noise."
```

---

## Acceptance Criteria

- [ ] `_build_enriched_node` method 存在於 `NodeBuilder`，呼叫 4 個 extract helper
- [ ] `_walk_config_driven` 內 6 個分支（fallback / Go type_spec / class / method-in-class / orphaned-method / function）皆改用 `_build_enriched_node`（fallback 例外，已註明 limitation）
- [ ] 6 個 fixture 檔案存在於 `tests/fixtures/multilang/`，內容各自包含 doc-comment + parameters + （如該語言有慣例）annotation/attribute
- [ ] Java/Rust/C# 至少能抽出 decorator
- [ ] 所有 6 語言能抽出 parameters
- [ ] 所有 6 語言能抽出 docstring（PHP 允許 xfail 若 grammar 限制）
- [ ] `comments` 欄位對所有 generic-walker 產出之 ASTNode 維持 `[]`
- [ ] Python / TypeScript walker 未修改
- [ ] `node_builder.py` line coverage = 100%（含本任務新增 + 前置任務的 4 helper）
- [ ] `pytest the_door/tests/` 無新增 failure
