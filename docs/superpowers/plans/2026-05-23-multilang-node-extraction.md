# Multilang Node Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `NodeBuilder._walk_generic`'s hardcoded substring matching with a config-driven per-language node-type table, fixing extraction for 8 languages (java, rust, ruby, php, csharp, c, cpp, go).

**Architecture:** New pure-data module `language_configs.py` defines a `LanguageConfig` dataclass + `LANGUAGE_CONFIGS` dict. `_walk_generic` is renamed `_walk_config_driven` and dispatches on the config. Go's `type_spec` struct/interface requires one special-case branch. Python/TS/JS paths are untouched (G4 bit-level compatibility). All name extraction uses `child_by_field_name("name")` where possible, falling back to `_child_text` helpers.

**Tech Stack:** Python, tree-sitter (existing), pytest, hypothesis (existing)

**Working worktree:** `C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a`
**All commands run from:** `the_door/` subdirectory of that worktree

---

## File Map

| Action | Path |
|---|---|
| **Create** | `the_door/src/the_door/core/extraction/language_configs.py` |
| **Modify** | `the_door/src/the_door/core/extraction/node_builder.py` (lines 369–406: replace `_walk_generic`) |
| **Create** | `the_door/tests/unit/core/extraction/test_multilang_extraction.py` |
| **Create** | `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.rs` |
| **Create** | `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.java` |
| **Create** | `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.rb` |
| **Create** | `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.php` |
| **Create** | `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.cs` |
| **Create** | `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.c` |
| **Create** | `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.cpp` |
| **Create** | `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.go` |

---

## Task 1: Failing Rust test (TDD red phase)

Spec § 7 requires a failing test first — proves the bug is real before fixing it.

**Files:**
- Create: `the_door/tests/unit/core/extraction/test_multilang_extraction.py`
- Create: `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.rs`

- [ ] **Step 1: Create Rust fixture**

`the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.rs`:
```rust
fn free_function() {}

struct MyStruct {
    x: i32,
}

impl MyStruct {
    fn impl_method(&self) {}
}
```

- [ ] **Step 2: Write the failing test**

`the_door/tests/unit/core/extraction/test_multilang_extraction.py`:
```python
"""Tests for config-driven multilang node extraction (spec: multilang-node-extraction/spec.md)."""
from pathlib import Path

import pytest

from the_door.core.extraction.ast_extractor import ASTExtractor

FIXTURES = Path(__file__).parent.parent.parent.parent / "fixtures" / "sample_codebases" / "multilang_nodes"


class TestRustExtraction:
    """Rust: function_item, struct_item, impl_item container (spec R3 + R6)."""

    def test_rust_free_function_extracted(self, tmp_path):
        (tmp_path / "s.rs").write_text("fn free_function() {}\n")
        result = ASTExtractor().extract(str(tmp_path))
        names = {n.name for n in result.nodes}
        assert "free_function" in names

    def test_rust_struct_extracted_as_class(self, tmp_path):
        (tmp_path / "s.rs").write_text("struct MyStruct { x: i32 }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "MyStruct" in nodes
        assert nodes["MyStruct"].type == "class"

    def test_rust_impl_method_extracted_as_method(self, tmp_path):
        src = "struct MyStruct {}\nimpl MyStruct { fn impl_method(&self) {} }\n"
        (tmp_path / "s.rs").write_text(src)
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "impl_method" in nodes, f"impl_method not found; got {set(nodes)}"
        assert nodes["impl_method"].type == "method", f"expected method, got {nodes['impl_method'].type}"

    def test_rust_free_fn_is_function_not_method(self, tmp_path):
        (tmp_path / "s.rs").write_text("fn free_function() {}\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert nodes["free_function"].type == "function"
```

- [ ] **Step 3: Run — expect RED**

```
cd C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a/the_door
pytest tests/unit/core/extraction/test_multilang_extraction.py -v 2>&1 | head -40
```

Expected: `test_rust_impl_method_extracted_as_method` FAILS (impl_method not found) and `test_rust_struct_extracted_as_class` FAILS (MyStruct not found). This proves spec § 2.2.

- [ ] **Step 4: Commit red test**

```bash
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" add \
  the_door/tests/unit/core/extraction/test_multilang_extraction.py \
  the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.rs
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" commit -m "test(multilang): failing Rust impl_item test (TDD red phase)"
```

---

## Task 2: Create `language_configs.py`

Pure data module — no I/O, no side effects (spec R1).

**Files:**
- Create: `the_door/src/the_door/core/extraction/language_configs.py`

- [ ] **Step 1: Create the file**

`the_door/src/the_door/core/extraction/language_configs.py`:
```python
"""Per-language tree-sitter node-type maps for config-driven extraction.

Data ported from codegraph commit 5aae9c4bbff4fe02f8284ef5f91dd9d5391027f6
(MIT License, Copyright (c) 2026 Colby Mchenry),
files src/extraction/languages/*.ts.
See .kiro/specs/multilang-node-extraction/spec.md section 4.1 for the
full citation table.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LanguageConfig:
    function_types: frozenset[str] = field(default_factory=frozenset)
    method_types: frozenset[str] = field(default_factory=frozenset)
    class_types: frozenset[str] = field(default_factory=frozenset)
    # Container nodes: establish a parent scope (so inner functions become
    # methods) but do not themselves produce an ASTNode. Only Rust uses this
    # (impl_item). See spec § 5.2 step 2b.
    container_types: frozenset[str] = field(default_factory=frozenset)


LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "java": LanguageConfig(
        function_types=frozenset(),
        method_types=frozenset({"method_declaration", "constructor_declaration"}),
        class_types=frozenset({"class_declaration", "interface_declaration", "enum_declaration"}),
    ),
    "go": LanguageConfig(
        function_types=frozenset({"function_declaration"}),
        method_types=frozenset({"method_declaration"}),
        class_types=frozenset(),  # handled via type_spec special case in _walk_config_driven
    ),
    "rust": LanguageConfig(
        function_types=frozenset({"function_item"}),
        method_types=frozenset({"function_item"}),
        class_types=frozenset({"struct_item", "enum_item", "trait_item"}),
        container_types=frozenset({"impl_item"}),
    ),
    "ruby": LanguageConfig(
        function_types=frozenset({"method"}),
        method_types=frozenset({"method", "singleton_method"}),
        class_types=frozenset({"class"}),
    ),
    "php": LanguageConfig(
        function_types=frozenset({"function_definition"}),
        method_types=frozenset({"method_declaration"}),
        class_types=frozenset({
            "class_declaration", "trait_declaration",
            "interface_declaration", "enum_declaration",
        }),
    ),
    "csharp": LanguageConfig(
        function_types=frozenset(),
        method_types=frozenset({"method_declaration", "constructor_declaration"}),
        class_types=frozenset({
            "class_declaration", "interface_declaration",
            "struct_declaration", "enum_declaration",
        }),
    ),
    "c": LanguageConfig(
        function_types=frozenset({"function_definition"}),
        method_types=frozenset(),
        class_types=frozenset({"struct_specifier", "enum_specifier"}),
    ),
    "cpp": LanguageConfig(
        function_types=frozenset({"function_definition"}),
        method_types=frozenset({"function_definition"}),
        class_types=frozenset({"class_specifier", "struct_specifier", "enum_specifier"}),
    ),
}
```

- [ ] **Step 2: Verify it imports cleanly**

```
cd C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a/the_door
python -c "from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS; print(list(LANGUAGE_CONFIGS))"
```

Expected: `['java', 'go', 'rust', 'ruby', 'php', 'csharp', 'c', 'cpp']`

- [ ] **Step 3: Commit**

```bash
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" add \
  the_door/src/the_door/core/extraction/language_configs.py
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" commit -m "feat(extraction): add language_configs.py with per-language node-type maps"
```

---

## Task 3: Replace `_walk_generic` with `_walk_config_driven`

**Files:**
- Modify: `the_door/src/the_door/core/extraction/node_builder.py`

Key name-extraction facts (verified via actual tree-sitter parsing):
- Most languages: `node.child_by_field_name("name")` works
- C/C++ functions: name is nested — `node.child_by_field_name("declarator").child_by_field_name("declarator")`
- Rust `impl_item` container name: `node.child_by_field_name("type")`
- Go `type_spec`: name via `node.child_by_field_name("name")`; class check via child named `"type"` whose type is `struct_type` or `interface_type`
- Ruby class name field is `"name"` → returns a `constant` node

- [ ] **Step 1: Add import at top of node_builder.py**

At the top of `node_builder.py`, after the existing imports, add:

```python
from the_door.core.extraction.language_configs import LANGUAGE_CONFIGS
```

- [ ] **Step 2: Add `_get_name` static helper after existing `_child_text`**

Add this new static method to `NodeBuilder` (after `_find_child`):

```python
@staticmethod
def _get_name_by_field(node: TSNode) -> str | None:
    """Get node name via child_by_field_name('name'), decode if found."""
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return name_node.text.decode("utf-8", errors="replace")
    return None
```

- [ ] **Step 3: Replace `_walk_generic` with `_walk_config_driven`**

Replace the entire `_walk_generic` method (lines 369–406 of node_builder.py) with:

```python
def _walk_config_driven(
    self,
    node: TSNode,
    file_info: FileInfo,
    results: list[ASTNode],
    parent_class: str | None,
) -> None:
    """Config-driven walker for languages covered by LANGUAGE_CONFIGS."""
    cfg = LANGUAGE_CONFIGS.get(file_info.language)
    if cfg is None:
        # Fallback for languages not yet in the config table.
        # Retained so newly-registered grammars get rough extraction
        # rather than nothing.
        if "function_definition" in node.type or "function_declaration" in node.type:
            name = self._child_text(node, "identifier")
            if name:
                results.append(ASTNode(
                    node_id=f"{file_info.path}::{name}",
                    type="method" if parent_class else "function",
                    name=name,
                    file=file_info.path,
                    language=file_info.language,
                ))
            return
        if "class_definition" in node.type or "class_declaration" in node.type:
            name = self._child_text(node, "identifier") or self._child_text(node, "type_identifier")
            if name:
                results.append(ASTNode(
                    node_id=f"{file_info.path}::{name}",
                    type="class",
                    name=name,
                    file=file_info.path,
                    language=file_info.language,
                ))
            return
        for child in node.children:
            self._walk_config_driven(child, file_info, results, parent_class)
        return

    # ── Go type_spec special case (spec § 5.3) ──────────────────────
    if file_info.language == "go" and node.type == "type_spec":
        type_child = node.child_by_field_name("type")
        if type_child is not None and type_child.type in ("struct_type", "interface_type"):
            name = self._get_name_by_field(node)
            if name:
                results.append(ASTNode(
                    node_id=f"{file_info.path}::{name}",
                    type="class",
                    name=name,
                    file=file_info.path,
                    language=file_info.language,
                ))
        return

    # ── Container nodes (e.g. Rust impl_item): scope but no own node ──
    if node.type in cfg.container_types:
        type_node = node.child_by_field_name("type")
        container_name = (
            type_node.text.decode("utf-8", errors="replace")
            if type_node is not None
            else "__impl__"
        )
        for child in node.children:
            self._walk_config_driven(child, file_info, results, container_name)
        return

    # ── Class nodes ───────────────────────────────────────────────────
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

    # ── Method nodes (inside a class/container scope) ─────────────────
    if node.type in cfg.method_types and parent_class is not None:
        name = self._extract_name(node, file_info.language)
        if name:
            results.append(ASTNode(
                node_id=f"{file_info.path}::{name}",
                type="method",
                name=name,
                file=file_info.path,
                language=file_info.language,
            ))
        return

    # ── Function nodes (top-level or method_types with no parent) ─────
    if node.type in cfg.function_types:
        name = self._extract_name(node, file_info.language)
        if name:
            results.append(ASTNode(
                node_id=f"{file_info.path}::{name}",
                type="function",
                name=name,
                file=file_info.path,
                language=file_info.language,
            ))
        return

    # ── Recurse ───────────────────────────────────────────────────────
    for child in node.children:
        self._walk_config_driven(child, file_info, results, parent_class)
```

- [ ] **Step 4: Add `_extract_name` static helper**

Add after `_get_name_by_field`:

```python
@staticmethod
def _extract_name(node: TSNode, language: str) -> str | None:
    """Extract node name, handling per-language quirks."""
    # C and C++: function name is nested in declarator field
    if language in ("c", "cpp") and node.type == "function_definition":
        decl = node.child_by_field_name("declarator")
        if decl is not None:
            inner = decl.child_by_field_name("declarator")
            if inner is not None:
                return inner.text.decode("utf-8", errors="replace")
        return None

    # Standard: try name field first, then type_identifier, then identifier
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return name_node.text.decode("utf-8", errors="replace")

    for child_type in ("type_identifier", "identifier"):
        for child in node.children:
            if child.type == child_type:
                return child.text.decode("utf-8", errors="replace")
    return None
```

- [ ] **Step 5: Update `_walk` dispatch to call `_walk_config_driven`**

In `_walk` method, change the `else` branch from `_walk_generic` to `_walk_config_driven`:

```python
else:
    self._walk_config_driven(node, file_info, results, parent_class)
```

- [ ] **Step 6: Run the failing Rust test — expect GREEN**

```
cd C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a/the_door
pytest tests/unit/core/extraction/test_multilang_extraction.py::TestRustExtraction -v
```

Expected: all 4 Rust tests PASS.

- [ ] **Step 7: Run existing tests — expect no regressions**

```
cd C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a/the_door
pytest tests/ -x --tb=short -q 2>&1 | tail -20
```

Expected: same pass count as before (no failures).

- [ ] **Step 8: Commit**

```bash
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" add \
  the_door/src/the_door/core/extraction/node_builder.py
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" commit -m "feat(extraction): replace _walk_generic with config-driven _walk_config_driven"
```

---

## Task 4: Java, Ruby, PHP, C# tests and fixtures

**Files:**
- Create: `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.java`
- Create: `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.rb`
- Create: `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.php`
- Create: `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.cs`
- Modify: `the_door/tests/unit/core/extraction/test_multilang_extraction.py`

- [ ] **Step 1: Create fixtures**

`sample.java`:
```java
public class Animal {
    public void speak() {}
    public Animal() {}
}
```

`sample.rb`:
```ruby
class Animal
  def speak
  end
end

def standalone_func
end
```

`sample.php`:
```php
<?php
function standalone_func() {}

class Animal {
    function speak() {}
}
```

`sample.cs`:
```csharp
class Animal {
    void Speak() {}
    public Animal() {}
}
```

- [ ] **Step 2: Add test classes to test_multilang_extraction.py**

Append to the test file:

```python
class TestJavaExtraction:
    """Java: method_declaration, constructor_declaration, class_declaration (spec R3)."""

    def test_java_class_extracted(self, tmp_path):
        (tmp_path / "A.java").write_text("public class Animal { public void speak() {} public Animal() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Animal" in nodes
        assert nodes["Animal"].type == "class"

    def test_java_method_extracted_as_method(self, tmp_path):
        (tmp_path / "A.java").write_text("public class Animal { public void speak() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "speak" in nodes
        assert nodes["speak"].type == "method"

    def test_java_constructor_extracted_as_method(self, tmp_path):
        (tmp_path / "A.java").write_text("public class Animal { public Animal() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Animal" in nodes
        # class + constructor both named Animal; at least one must be method
        method_nodes = [n for n in result.nodes if n.name == "Animal" and n.type == "method"]
        assert len(method_nodes) >= 1


class TestRubyExtraction:
    """Ruby: method, class (spec R3)."""

    def test_ruby_class_extracted(self, tmp_path):
        (tmp_path / "a.rb").write_text("class Animal\n  def speak\n  end\nend\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Animal" in nodes
        assert nodes["Animal"].type == "class"

    def test_ruby_method_inside_class_is_method(self, tmp_path):
        (tmp_path / "a.rb").write_text("class Animal\n  def speak\n  end\nend\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "speak" in nodes
        assert nodes["speak"].type == "method"

    def test_ruby_standalone_method_is_function(self, tmp_path):
        (tmp_path / "a.rb").write_text("def standalone_func\nend\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "standalone_func" in nodes
        assert nodes["standalone_func"].type == "function"


class TestPhpExtraction:
    """PHP: function_definition, method_declaration, class_declaration (spec R3)."""

    def test_php_standalone_function_extracted(self, tmp_path):
        (tmp_path / "a.php").write_text("<?php\nfunction standalone_func() {}\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "standalone_func" in nodes
        assert nodes["standalone_func"].type == "function"

    def test_php_class_extracted(self, tmp_path):
        (tmp_path / "a.php").write_text("<?php\nclass Animal { function speak() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Animal" in nodes
        assert nodes["Animal"].type == "class"

    def test_php_method_inside_class_is_method(self, tmp_path):
        (tmp_path / "a.php").write_text("<?php\nclass Animal { function speak() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "speak" in nodes
        assert nodes["speak"].type == "method"


class TestCSharpExtraction:
    """C#: method_declaration, constructor_declaration, class_declaration (spec R3)."""

    def test_csharp_class_extracted(self, tmp_path):
        (tmp_path / "a.cs").write_text("class Animal { void Speak() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Animal" in nodes
        assert nodes["Animal"].type == "class"

    def test_csharp_method_extracted_as_method(self, tmp_path):
        (tmp_path / "a.cs").write_text("class Animal { void Speak() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Speak" in nodes
        assert nodes["Speak"].type == "method"

    def test_csharp_constructor_extracted_as_method(self, tmp_path):
        (tmp_path / "a.cs").write_text("class Animal { public Animal() {} }\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        method_nodes = [n for n in result.nodes if n.name == "Animal" and n.type == "method"]
        assert len(method_nodes) >= 1
```

- [ ] **Step 3: Run new tests — expect GREEN**

```
cd C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a/the_door
pytest tests/unit/core/extraction/test_multilang_extraction.py -v -k "Java or Ruby or Php or CSharp"
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" add \
  the_door/tests/unit/core/extraction/test_multilang_extraction.py \
  the_door/tests/fixtures/sample_codebases/multilang_nodes/
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" commit -m "test(multilang): add Java/Ruby/PHP/C# extraction tests"
```

---

## Task 5: C, C++, Go tests and fixtures

**Files:**
- Create: `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.c`
- Create: `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.cpp`
- Create: `the_door/tests/fixtures/sample_codebases/multilang_nodes/sample.go`
- Modify: `the_door/tests/unit/core/extraction/test_multilang_extraction.py`

- [ ] **Step 1: Create fixtures**

`sample.c`:
```c
struct Point { int x; int y; };
void move(struct Point p) {}
```

`sample.cpp`:
```cpp
class Shape {
    void draw() {}
};
void render() {}
```

`sample.go`:
```go
package main

func Standalone() {}

func (s Shape) Draw() {}

type Shape struct {
    X int
}

type Drawable interface {
    Draw()
}
```

- [ ] **Step 2: Add test classes**

Append to `test_multilang_extraction.py`:

```python
class TestCExtraction:
    """C: function_definition, struct_specifier (spec R3)."""

    def test_c_function_extracted(self, tmp_path):
        (tmp_path / "a.c").write_text("void move(int x) {}\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "move" in nodes
        assert nodes["move"].type == "function"

    def test_c_struct_extracted_as_class(self, tmp_path):
        (tmp_path / "a.c").write_text("struct Point { int x; };\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Point" in nodes
        assert nodes["Point"].type == "class"


class TestCppExtraction:
    """C++: function_definition, class_specifier (spec R3)."""

    def test_cpp_class_extracted(self, tmp_path):
        (tmp_path / "a.cpp").write_text("class Shape { void draw() {} };\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Shape" in nodes
        assert nodes["Shape"].type == "class"

    def test_cpp_method_inside_class_is_method(self, tmp_path):
        (tmp_path / "a.cpp").write_text("class Shape { void draw() {} };\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "draw" in nodes
        assert nodes["draw"].type == "method"

    def test_cpp_top_level_function_is_function(self, tmp_path):
        (tmp_path / "a.cpp").write_text("void render() {}\n")
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "render" in nodes
        assert nodes["render"].type == "function"


class TestGoExtraction:
    """Go: function_declaration, method_declaration, type_spec struct/interface (spec R4)."""

    def test_go_standalone_function_extracted(self, tmp_path):
        src = "package main\nfunc Standalone() {}\n"
        (tmp_path / "a.go").write_text(src)
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Standalone" in nodes
        assert nodes["Standalone"].type == "function"

    def test_go_method_extracted_as_method(self, tmp_path):
        src = "package main\ntype Shape struct{}\nfunc (s Shape) Draw() {}\n"
        (tmp_path / "a.go").write_text(src)
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Draw" in nodes
        assert nodes["Draw"].type == "method"

    def test_go_struct_extracted_as_class(self, tmp_path):
        src = "package main\ntype Shape struct { X int }\n"
        (tmp_path / "a.go").write_text(src)
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Shape" in nodes
        assert nodes["Shape"].type == "class"

    def test_go_interface_extracted_as_class(self, tmp_path):
        src = "package main\ntype Drawable interface { Draw() }\n"
        (tmp_path / "a.go").write_text(src)
        result = ASTExtractor().extract(str(tmp_path))
        nodes = {n.name: n for n in result.nodes}
        assert "Drawable" in nodes
        assert nodes["Drawable"].type == "class"
```

- [ ] **Step 3: Run — expect GREEN**

```
cd C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a/the_door
pytest tests/unit/core/extraction/test_multilang_extraction.py -v -k "C or Cpp or Go"
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" add \
  the_door/tests/unit/core/extraction/test_multilang_extraction.py \
  the_door/tests/fixtures/sample_codebases/multilang_nodes/
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" commit -m "test(multilang): add C/C++/Go extraction tests"
```

---

## Task 6: Verify python/typescript/javascript regression (spec R5)

**Files:**
- Read only: existing extraction tests

- [ ] **Step 1: Run python/ts/js scoped tests**

```
cd C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a/the_door
pytest tests/ -k "python or typescript or javascript" -v --tb=short 2>&1 | tail -30
```

Expected: all GREEN, count identical to pre-change baseline.

- [ ] **Step 2: Run full suite**

```
cd C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a/the_door
pytest tests/ --tb=short -q 2>&1 | tail -10
```

Expected: 0 failures, same or higher pass count.

- [ ] **Step 3: Run coverage**

```
cd C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a/the_door
pytest tests/ --cov=the_door.core.extraction.language_configs --cov=the_door.core.extraction.node_builder --cov-report=term-missing --tb=short -q 2>&1 | tail -20
```

Expected: `language_configs.py` 100%, `node_builder.py` ≥ 95% (the no-config fallback branch may not be hit by tests — if below 95%, add a test for the fallback).

- [ ] **Step 4: If coverage < 100% for language_configs.py or fallback branch**

Add a test for the fallback path:

```python
class TestConfigFallback:
    """Unknown language uses old substring fallback (spec R2)."""

    def test_unknown_language_gets_substring_fallback(self, tmp_path):
        # Write a file with an extension not in LANGUAGE_CONFIGS
        # but containing a function_definition-like pattern.
        # We test the fallback by calling _walk_config_driven directly.
        from the_door.core.extraction.node_builder import NodeBuilder
        from the_door.models import FileInfo
        import tree_sitter_python
        from tree_sitter import Language, Parser

        lang = Language(tree_sitter_python.language())
        parser = Parser(lang)
        tree = parser.parse(b"def foo(): pass")
        file_info = FileInfo(path="x.unknown", language="unknown_lang")
        nb = NodeBuilder()
        results = []
        nb._walk_config_driven(tree.root_node, file_info, results, None)
        # Python AST has function_definition which the fallback can catch
        names = {n.name for n in results}
        assert "foo" in names
```

Run again until 100% on `language_configs.py`.

- [ ] **Step 5: Commit coverage baseline**

```bash
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" add \
  the_door/tests/unit/core/extraction/test_multilang_extraction.py
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" commit -m "test(multilang): verify python/ts/js regression + coverage baseline"
```

---

## Task 7: Merge to main

**Files:**
- Target: `main` branch

- [ ] **Step 1: Verify branch log**

```bash
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" log --oneline main..HEAD
```

Expected: spec commit + feat commits + test commits (≥ 5 commits).

- [ ] **Step 2: Check if fast-forward is possible**

```bash
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" fetch origin main
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" log --oneline HEAD..origin/main
```

If output is empty → ff possible. If not → rebase first:

```bash
git -C "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a" rebase origin/main
```

- [ ] **Step 3: Fast-forward merge**

```bash
git -C "C:/Users/Ric/Desktop/the_door" checkout main
git -C "C:/Users/Ric/Desktop/the_door" merge --ff-only claude/peaceful-bell-8b569a
```

- [ ] **Step 4: Push**

```bash
git -C "C:/Users/Ric/Desktop/the_door" push origin main
```

- [ ] **Step 5: Remove worktree**

```bash
git -C "C:/Users/Ric/Desktop/the_door" worktree remove "C:/Users/Ric/Desktop/the_door/.claude/worktrees/peaceful-bell-8b569a"
```

---

## Acceptance Checklist

- [ ] Rust: `free_function` (function) + `MyStruct` (class) + `impl_method` (method) all extracted
- [ ] Java: class + method + constructor extracted, constructor type=method
- [ ] Ruby: class + inside-method (method) + standalone method (function) extracted
- [ ] PHP: standalone function + class + method extracted
- [ ] C#: class + method + constructor (method) extracted
- [ ] C: function + struct (class) extracted
- [ ] C++: class + inside-method (method) + top-level function extracted
- [ ] Go: function + method + struct (class) + interface (class) extracted
- [ ] python/typescript/javascript existing tests all GREEN (R5)
- [ ] `language_configs.py` 100% test coverage
- [ ] `node_builder.py` fallback branch covered
- [ ] All changes merged to main
