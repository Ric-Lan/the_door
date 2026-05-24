# Plan C — Backend Core/Extraction（Task 02）

> **執行分類 C**：Python 後端 — Core/Extraction 層
> **依賴：** 無；Task 10（wizard）依賴此 task 的 `extra_ignore` 參數
> **Worktree：** `loving-sinoussi-20dcd0`

---

## Task 02 — R2：file_discovery 排除 `.claude/` + extra_ignore 參數

**Files:**
- Modify: `the_door/src/the_door/core/extraction/file_discovery.py`
- Test: `the_door/tests/unit/core/extraction/test_extraction.py`

- [ ] **Step 1：寫失敗測試**

在 `test_extraction.py` 的 `TestFileDiscovery` class 末尾加入：

```python
def test_ignores_dot_claude_directory(self, tmp_path):
    """Files inside .claude/ worktrees must never appear in discovery results."""
    (tmp_path / ".claude" / "worktrees" / "foo").mkdir(parents=True)
    (tmp_path / ".claude" / "worktrees" / "foo" / "bar.py").write_text("x = 1")
    (tmp_path / "main.py").write_text("y = 2")
    files = FileDiscovery().discover(str(tmp_path))
    paths = [f.path for f in files]
    assert not any(".claude" in p for p in paths)
    assert any("main.py" in p for p in paths)


def test_extra_ignore_excludes_specified_dirs(self, tmp_path):
    """extra_ignore patterns are applied on top of the default ignore list."""
    (tmp_path / "vendor" / "lib").mkdir(parents=True)
    (tmp_path / "vendor" / "lib" / "foo.py").write_text("x = 1")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("y = 2")
    files = FileDiscovery().discover(str(tmp_path), extra_ignore=["vendor/"])
    paths = [f.path for f in files]
    assert not any("vendor" in p for p in paths)
    assert any("app.py" in p for p in paths)
```

- [ ] **Step 2：執行測試確認失敗**

```
cd the_door && pytest tests/unit/core/extraction/test_extraction.py::TestFileDiscovery::test_ignores_dot_claude_directory tests/unit/core/extraction/test_extraction.py::TestFileDiscovery::test_extra_ignore_excludes_specified_dirs -v
```

預期：FAILED（`.claude/` 未被排除；`extra_ignore` 參數不存在）

- [ ] **Step 3：實作修正**

在 `file_discovery.py`：

1. 在 `_DEFAULT_IGNORE_PATTERNS` 加入 `".claude/"`:

```python
_DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    ".claude/",          # ← 新增
    "node_modules/",
    "__pycache__/",
    "dist/",
    "build/",
    ".tox/",
    ".mypy_cache/",
    ".pytest_cache/",
    "*.pyc",
    "*.pyo",
]
```

2. `discover()` 加 `extra_ignore` 參數，傳遞給 `_load_gitignore`：

```python
def discover(
    self,
    codebase_path: str,
    extra_ignore: list[str] | None = None,
) -> list[FileInfo]:
    root = Path(codebase_path).resolve()
    if not root.is_dir():
        return []
    spec = self._load_gitignore(root, extra_ignore=extra_ignore or [])
    # ... 其餘不動 ...
```

3. `_load_gitignore` 加 `extra_ignore` 參數：

```python
@staticmethod
def _load_gitignore(
    root: Path,
    extra_ignore: list[str] | None = None,
) -> pathspec.PathSpec:
    patterns = list(_DEFAULT_IGNORE_PATTERNS)
    if extra_ignore:
        patterns.extend(extra_ignore)
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        patterns.extend(
            line.strip()
            for line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    return pathspec.PathSpec.from_lines("gitignore", patterns)
```

- [ ] **Step 4：執行測試確認通過**

```
cd the_door && pytest tests/unit/core/extraction/test_extraction.py -v
```

預期：全部 PASSED

- [ ] **Step 5：覆蓋率確認**

```
cd the_door && pytest tests/unit/core/extraction/test_extraction.py --cov=the_door.core.extraction.file_discovery --cov-report=term-missing
```

預期：`file_discovery.py` 100%

- [ ] **Step 6：Commit**

```
git add the_door/src/the_door/core/extraction/file_discovery.py the_door/tests/unit/core/extraction/test_extraction.py
git commit -m "fix(extraction): exclude .claude/ worktrees + add extra_ignore param"
```
