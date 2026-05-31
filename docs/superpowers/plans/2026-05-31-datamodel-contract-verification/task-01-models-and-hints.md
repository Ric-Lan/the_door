# Task 01 — 值物件 models + 啟發式 hints config

**內容分類：** 純資料形狀 + config 判定函式。地基，02/03/04 都用。零 UI、零 I/O。

**設計來源：** spec §6（dataclasses）、§4（Tier 0 啟發式）。

**Files:**
- Create: `the_door/src/the_door/core/datamodel/__init__.py`（空檔）
- Create: `the_door/src/the_door/core/datamodel/models.py`
- Create: `the_door/src/the_door/core/datamodel/datamodel_hints.py`
- Create: `the_door/tests/unit/datamodel/__init__.py`（空檔，鏡像既有 `tests/unit/mcp` 等子套件）
- Create: `the_door/tests/unit/datamodel/test_models.py`
- Create: `the_door/tests/unit/datamodel/test_hints.py`

---

- [ ] **Step 1: 建空 package marker**

建 `the_door/src/the_door/core/datamodel/__init__.py`（空檔）與 `the_door/tests/unit/datamodel/__init__.py`（空檔）。

- [ ] **Step 2: 寫 models 失敗測試**

`the_door/tests/unit/datamodel/test_models.py`：

```python
from the_door.core.datamodel.models import (
    DataModelCandidate, DataModelLocalization,
    DeclaredField, CodeTouch, ContractEntry, ContractDiff,
)


def test_candidate_and_localization():
    c = DataModelCandidate(node_id="m1", file="models/user.py",
                           kind="code_site", flagged_reason="name contains 'save'")
    loc = DataModelLocalization(code_candidates=(c,), schema_candidates=())
    assert loc.code_candidates[0].node_id == "m1"
    assert loc.schema_candidates == ()


def test_declared_field_optional_type():
    assert DeclaredField(field="name").type is None
    assert DeclaredField(field="age", type="int").type == "int"


def test_code_touch_and_contract():
    t = CodeTouch(op="write", entity="User", fields=("name", "age"))
    assert t.fields == ("name", "age")
    diff = ContractDiff(entries=(
        ContractEntry(entity="User", field="name", status="match", detail="ok"),
    ))
    assert diff.entries[0].status == "match"


def test_dataclasses_are_frozen():
    import dataclasses
    import pytest
    c = DataModelCandidate(node_id="x", file="f", kind="code_site", flagged_reason="r")
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.file = "y"  # type: ignore[misc]
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_models.py -q`
Expected: FAIL（`ModuleNotFoundError: the_door.core.datamodel.models`）。

- [ ] **Step 4: 實作 models.py**

`the_door/src/the_door/core/datamodel/models.py`：

```python
"""Value objects for data-model contract verification (side-channel, off translation path)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataModelCandidate:
    """A localized data-model touch point (Tier 0)."""
    node_id: str            # ASTNode.node_id；schema 檔候選此欄為 ""
    file: str               # 候選檔案路徑（交付粒度為「檔」，spec §3 無行範圍）
    kind: str               # "code_site" | "schema_file"
    flagged_reason: str     # 命中哪條啟發式（可讀字串）


@dataclass(frozen=True)
class DataModelLocalization:
    """Tier 0 output: code-site + schema-file candidates."""
    code_candidates: tuple[DataModelCandidate, ...] = ()
    schema_candidates: tuple[DataModelCandidate, ...] = ()


@dataclass(frozen=True)
class DeclaredField:
    """One declared field in a schema entity (agent-normalized)."""
    field: str
    type: str | None = None


@dataclass(frozen=True)
class CodeTouch:
    """One code-side data touch (agent-normalized)."""
    op: str                 # "write" | "read"
    entity: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class ContractEntry:
    """One bidirectional contract-diff result for an entity field."""
    entity: str
    field: str
    status: str             # "write_gap" | "coverage_gap" | "match"
    detail: str


@dataclass(frozen=True)
class ContractDiff:
    """Tier 1 output: the full contract diff."""
    entries: tuple[ContractEntry, ...] = ()
```

- [ ] **Step 5: 跑測試確認通過**

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_models.py -q`
Expected: PASS（4 個 case 全綠）。

- [ ] **Step 6: 寫 hints 失敗測試**

`the_door/tests/unit/datamodel/test_hints.py`：

```python
from the_door.core.datamodel.datamodel_hints import code_site_reason, schema_file_reason


def test_code_site_reason_name_hit():
    assert code_site_reason("save_user", "svc/user.py") == "name contains 'save'"
    assert code_site_reason("UserRepository", "a/b.py") == "name contains 'repository'"


def test_code_site_reason_dir_hit():
    assert code_site_reason("plain", "app/models/user.py") == "file under 'models/'"
    assert code_site_reason("plain", "schema/x.py") == "file under 'schema/'"


def test_code_site_reason_miss():
    assert code_site_reason("render", "ui/view.py") is None


def test_schema_file_reason_suffix():
    assert schema_file_reason("db/init.sql") == "schema file (.sql)"
    assert schema_file_reason("data/seed.csv") == "schema file (.csv)"


def test_schema_file_reason_json_hint():
    assert schema_file_reason("conf/schema.json") == "schema-like json (name contains 'schema')"
    assert schema_file_reason("model.json") == "schema-like json (name contains 'model')"


def test_schema_file_reason_json_miss_and_other_miss():
    assert schema_file_reason("package.json") is None
    assert schema_file_reason("src/app.py") is None


def test_path_separator_normalized():
    assert code_site_reason("plain", "app\\\\models\\\\user.py") == "file under 'models/'"
```

- [ ] **Step 7: 跑測試確認失敗**

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_hints.py -q`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 8: 實作 datamodel_hints.py**

`the_door/src/the_door/core/datamodel/datamodel_hints.py`：

```python
"""Cross-language heuristics for locating data-model touch points (Tier 0).

刻意不掛 language_configs.py（那是 per-language scope rules）；這裡是跨語言
name/dir 啟發式。集合小而明確，便於審視與擴充。
"""
from __future__ import annotations

PERSIST_NAME_HINTS = ("save", "create", "insert", "update", "persist", "repository", "dao")
PERSIST_DIR_HINTS = ("models", "schema", "migrations", "entities")
SCHEMA_FILE_SUFFIXES = (".sql", ".csv")
SCHEMA_JSON_NAME_HINTS = ("schema", "model")


def code_site_reason(name: str, file: str) -> str | None:
    """Return a human-readable reason if this node looks persistence-related, else None."""
    lname = name.lower()
    for hint in PERSIST_NAME_HINTS:
        if hint in lname:
            return f"name contains '{hint}'"
    lfile = file.replace("\\", "/").lower()
    for d in PERSIST_DIR_HINTS:
        if f"/{d}/" in lfile or lfile.startswith(f"{d}/"):
            return f"file under '{d}/'"
    return None


def schema_file_reason(path: str) -> str | None:
    """Return a reason if this file path looks like a declared schema artifact, else None."""
    lpath = path.replace("\\", "/").lower()
    for suf in SCHEMA_FILE_SUFFIXES:
        if lpath.endswith(suf):
            return f"schema file ({suf})"
    if lpath.endswith(".json"):
        name = lpath.rsplit("/", 1)[-1]
        for hint in SCHEMA_JSON_NAME_HINTS:
            if hint in name:
                return f"schema-like json (name contains '{hint}')"
    return None
```

- [ ] **Step 9: 跑測試確認通過 + 覆蓋率**

Run: `cd the_door && python -m pytest tests/unit/datamodel/test_hints.py tests/unit/datamodel/test_models.py --cov=the_door.core.datamodel.models --cov=the_door.core.datamodel.datamodel_hints --cov-report=term-missing -q`
Expected: PASS；models.py + datamodel_hints.py **100%**（無 Missing 行）。

- [ ] **Step 10: Commit**

```bash
cd the_door
git add src/the_door/core/datamodel/__init__.py src/the_door/core/datamodel/models.py src/the_door/core/datamodel/datamodel_hints.py tests/unit/datamodel/
git commit -m "feat(datamodel): value objects + cross-language localization hints"
```

## Done when
- [ ] 6 個值物件 dataclass 全 frozen、可建構
- [ ] `code_site_reason` / `schema_file_reason` 命中與不命中分支正確（含 `\` 路徑正規化、json 命中/不命中）
- [ ] models.py + datamodel_hints.py 覆蓋率 100%
