# Task 03: DSM 結構不變量測試 + 欄位級等價驗證

**目的**：(a) 加一道 DSM 回歸測試，把「門面全名可 import + 模組圖無環(ADP) + 跨模組邊集==設計(8 條) + 依賴方向順穩定度(SDP)」釘成永久不變量；(b) 用 AST 比對拆前拆後**逐欄位等價**，證明只搬位置、零內容變更；(c) 全套件 + 覆蓋驗收。

**Files:**
- Create: `the_door/tests/unit/core/test_models_package_structure.py`

**前置**：Task 02 cutover 已 commit（HEAD = 該 cutover commit；其父 commit `HEAD~1` 仍含單檔 `models.py`）。cwd = 內層 `the_door/`。

---

- [ ] **Step 1: 寫 DSM 結構不變量測試**

建立 `the_door/tests/unit/core/test_models_package_structure.py`，完整內容如下：

```python
"""DSM regression test for the the_door.models package.

Pins the post-split structure as an enforced invariant:
  (a) every public name re-exported by the façade is importable;
  (b) the module dependency graph is acyclic (ADP);
  (c) the cross-module edge set equals the designed set (no new coupling);
  (d) every dependency points toward greater stability (SDP, Martin's I).

The dependency graph is rebuilt at runtime by resolving each dataclass's
field type hints (and exception bases) and mapping referenced model classes
to their defining submodule — so it tracks real code, not a transcript.
"""
from __future__ import annotations

import dataclasses
import importlib
import typing

import the_door.models as M

# ── (a) the façade must export exactly these 79 names ────────────────────
EXPECTED_NAMES = set(M.__all__)
EXPECTED_COUNT = 79

# ── (c) the designed cross-module edge set (module -> module) ────────────
# Derived from the 2026-06-02 measurement; see spec §5.2.
EXPECTED_MODULE_EDGES = {
    ("snapshot", "vulnerability"),
    ("diff", "snapshot"),
    ("pipeline", "analysis"),
    ("pipeline", "snapshot"),
    ("pipeline", "vulnerability"),
    ("pipeline", "diff"),
    ("pipeline", "scope"),
    ("pipeline", "timeline"),
}

SUBMODULES = [
    "extraction", "analysis", "config", "vulnerability", "snapshot",
    "diff", "scope", "doubt", "timeline", "pipeline",
]

PKG = "the_door.models"


def _short(module_name: str) -> str | None:
    """'the_door.models.snapshot' -> 'snapshot'; None if outside the package."""
    if module_name == PKG or not module_name.startswith(PKG + "."):
        return None
    return module_name[len(PKG) + 1:]


def _referenced_model_classes(hint) -> set:
    """Walk a (possibly generic) type hint, collecting model classes."""
    found = set()
    for arg in typing.get_args(hint):
        found |= _referenced_model_classes(arg)
    if isinstance(hint, type) and getattr(hint, "__module__", "").startswith(PKG):
        found.add(hint)
    return found


def _build_module_graph():
    edges = set()
    nodes = set()
    for sub in SUBMODULES:
        mod = importlib.import_module(f"{PKG}.{sub}")
        nodes.add(sub)
        for name in dir(mod):
            obj = getattr(mod, name)
            if not isinstance(obj, type):
                continue
            if getattr(obj, "__module__", None) != f"{PKG}.{sub}":
                continue  # only classes DEFINED here, not re-imports
            referenced = set()
            if dataclasses.is_dataclass(obj):
                hints = typing.get_type_hints(obj)
                for h in hints.values():
                    referenced |= _referenced_model_classes(h)
            for base in getattr(obj, "__bases__", ()):
                if getattr(base, "__module__", "").startswith(PKG):
                    referenced.add(base)
            for ref in referenced:
                target = _short(ref.__module__)
                if target and target != sub:
                    edges.add((sub, target))
    return nodes, edges


def _instability(nodes, edges):
    ce = {n: 0 for n in nodes}  # efferent: depends on
    ca = {n: 0 for n in nodes}  # afferent: depended on by
    for a, b in edges:
        ce[a] += 1
        ca[b] += 1
    return {n: (ce[n] / (ca[n] + ce[n]) if (ca[n] + ce[n]) else 0.0) for n in nodes}


def _has_cycle(nodes, edges):
    adj = {n: set() for n in nodes}
    for a, b in edges:
        adj[a].add(b)
    color = {n: 0 for n in nodes}

    def dfs(u):
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1:
                return True
            if color[v] == 0 and dfs(v):
                return True
        color[u] = 2
        return False

    return any(color[n] == 0 and dfs(n) for n in nodes)


def test_facade_exports_exactly_79_names():
    assert len(M.__all__) == EXPECTED_COUNT
    assert len(set(M.__all__)) == EXPECTED_COUNT  # no duplicates


def test_every_public_name_is_importable():
    for name in EXPECTED_NAMES:
        assert hasattr(M, name), f"façade missing re-export: {name}"
        assert isinstance(getattr(M, name), type), f"{name} is not a class"


def test_module_graph_is_acyclic():
    nodes, edges = _build_module_graph()
    assert not _has_cycle(nodes, edges), f"models package has an import cycle: {edges}"


def test_cross_module_edges_match_design():
    _, edges = _build_module_graph()
    assert edges == EXPECTED_MODULE_EDGES, (
        f"unexpected edges (new coupling?): added={edges - EXPECTED_MODULE_EDGES}, "
        f"missing={EXPECTED_MODULE_EDGES - edges}"
    )


def test_dependencies_point_toward_stability():
    nodes, edges = _build_module_graph()
    I = _instability(nodes, edges)
    violations = [(a, I[a], b, I[b]) for a, b in edges if I[a] < I[b] - 1e-9]
    assert not violations, f"SDP violations (depend on less stable): {violations}"
```

- [ ] **Step 2: 跑 DSM 測試（拆後應全綠）**

Run（cwd = `the_door/`）：
```
PYTHONUTF8=1 python -m pytest tests/unit/core/test_models_package_structure.py -v
```
Expected: **5 passed**。
- 若 `test_cross_module_edges_match_design` 報 `added=...` → 拆檔不慎引入了非設計的跨模組引用，檢查該邊來源型別是否搬錯檔。
- 若 `missing=...` → 某型別被搬到別檔，使設計邊消失，對照 spec §5.1 修正歸檔。
- 若 `test_module_graph_is_acyclic` FAIL → 出現循環，檢查是否把某型別搬到造成互指的檔。

- [ ] **Step 3: 欄位級等價驗證（AST 比對拆前 vs 拆後）**

此步用一支臨時腳本，比對「拆前單檔」與「拆後套件」每個 class 的 (基底、欄位名、型別註解、預設值表達式) 是否**逐一相同**。在 `the_door/` 目錄建立暫存檔 `_equiv_check.py`：

```python
"""TEMPORARY field-level equivalence check (delete after running)."""
import ast, subprocess, pathlib
import the_door.models as M

def sigs_from_src(src):
    out = {}
    for n in ast.parse(src).body:
        if isinstance(n, ast.ClassDef):
            fields = []
            for s in n.body:
                if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                    fields.append((
                        s.target.id,
                        ast.unparse(s.annotation),
                        ast.unparse(s.value) if s.value is not None else None,
                    ))
            out[n.name] = ([ast.unparse(b) for b in n.bases], fields)
    return out

# OLD: single-file models.py from the pre-cutover commit (HEAD~1 = Task 01 commit)
old_src = subprocess.run(
    ["git", "show", "HEAD~1:the_door/src/the_door/models.py"],
    capture_output=True, text=True, encoding="utf-8", check=True,
).stdout
old = sigs_from_src(old_src)

# NEW: union of all submodules (parse each file separately — __future__ placement)
pkgdir = pathlib.Path(M.__file__).parent
new = {}
for p in sorted(pkgdir.glob("*.py")):
    if p.name == "__init__.py":
        continue
    for k, v in sigs_from_src(p.read_text(encoding="utf-8")).items():
        assert k not in new, f"duplicate class across submodules: {k}"
        new[k] = v

assert set(old) == set(new), (
    f"class set changed: only-old={sorted(set(old)-set(new))}, "
    f"only-new={sorted(set(new)-set(old))}"
)
drift = [c for c in old if old[c] != new[c]]
assert not drift, "\n".join(
    f"DRIFT {c}:\n old={old[c]}\n new={new[c]}" for c in drift
)
print(f"FIELD-LEVEL EQUIVALENCE OK: {len(old)} classes identical "
      f"(bases + field name/annotation/default)")
```

Run（cwd = `the_door/`，**須在 Task 03 commit 之前跑**，確保 `HEAD~1` 指向 Task 01 commit）：
```
PYTHONUTF8=1 python _equiv_check.py
```
Expected: `FIELD-LEVEL EQUIVALENCE OK: 79 classes identical (...)`。
若 `DRIFT ...` → 某 class 的欄位/註解/預設值/基底在搬移時被改動，**回 Task 02 修到逐字相同**。
跑完**刪除暫存檔**：
```
rm _equiv_check.py
```
（此檔不 commit。）

- [ ] **Step 4: 全套件 + 覆蓋（零回歸、覆蓋不降）**

Run：
```
PYTHONUTF8=1 python -m pytest --cov=the_door.models --cov-report=term-missing tests/
```
Expected: 全 PASS；`the_door/models/` 各子模組覆蓋率合計**不低於**拆前單檔 `models.py`（純資料定義，import 即覆蓋；應接近 100%）。記下數字。

再跑一次完整套件確認全域零回歸：
```
PYTHONUTF8=1 python -m pytest
```
Expected: 全 PASS（與拆前一致，無新 fail/error）。

- [ ] **Step 5: 確認改動面（只動 models + 兩個新測試）**

Run：
```
git diff --stat HEAD~2..HEAD
```
（`HEAD~2` = Task 01 之前；範圍涵蓋 Task 01 測試 + Task 02 cutover。）
Expected：只見 `src/the_door/models.py` 刪除、`src/the_door/models/*.py` 新增、`tests/unit/core/test_models_import_equivalence.py` 新增。**不得有任何其他既有 `.py` 被修改**（門面保證消費端零改）。若有他檔變更 → 違反護欄，回報。

- [ ] **Step 6: Commit（DSM 測試）**

```
git add tests/unit/core/test_models_package_structure.py
git commit -m "test(models): DSM structural invariant (acyclic + edge set + SDP)"
```
