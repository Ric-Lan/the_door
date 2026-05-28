# Shared Test Helper Snippet

> **For task files 02–05**: 每個 task 的測試檔案開頭都需要這段 inline helper（**不要** import 不存在的 `tree_sitter_languages` 套件）。複製這段到每個測試檔案的 `import` 區之後、`class Test...` 之前。

```python
# ── inline tree-sitter parser helper ──────────────────────────────────────
# 專案使用個別 tree_sitter_<lang> 套件（見 ast_extractor.py:25-79），
# 沒有 tree_sitter_languages 統一入口；以下 helper 對齊真實依賴。
import tree_sitter

_LANG_LOADERS = {
    "python":     ("tree_sitter_python",     "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "javascript": ("tree_sitter_javascript", "language"),
    "java":       ("tree_sitter_java",       "language"),
    "go":         ("tree_sitter_go",         "language"),
    "rust":       ("tree_sitter_rust",       "language"),
    "ruby":       ("tree_sitter_ruby",       "language"),
    "php":        ("tree_sitter_php",        "language_php"),
    "c_sharp":    ("tree_sitter_c_sharp",    "language"),
    "csharp":     ("tree_sitter_c_sharp",    "language"),
}


def _make_parser(lang: str) -> tree_sitter.Parser:
    mod_name, attr = _LANG_LOADERS[lang]
    mod = __import__(mod_name)
    language = tree_sitter.Language(getattr(mod, attr)())
    parser = tree_sitter.Parser(language)
    return parser


def _parse(lang: str, source: str):
    parser = _make_parser(lang)
    tree = parser.parse(source.encode())
    return tree, source.encode()
```

**注意**：此 helper 是給 plan 文件的執行者**複製貼上**到每個測試檔的，**不是**要建立成獨立模組——避免「文件裡寫還需要寫其他文件才能執行」。

---

## 為什麼不用 `tree_sitter_languages`

| 項目 | 真實狀態 |
|---|---|
| `pyproject.toml` dependency | `tree-sitter-language-pack`（**不是** `tree-sitter-languages`） |
| `ast_extractor.py:25-79` | 直接 import `tree_sitter_python` / `tree_sitter_typescript` / 等 9 個個別套件 |
| `tree_sitter_languages` 套件 | **本專案完全沒使用**；vendor 不同，API 不同 |

寫成 `import tree_sitter_languages` 會在第一行 ImportError，整個測試 suite 跑不起來。
