# Task 06 — MCP 工具（localize_data_model + verify_data_model_contract）

**內容分類：** agent-as-LLM 入口（無需 API key）。`localize_data_model`=Tier 0 序列化；`verify_data_model_contract`=Tier 1 收 agent 兩份欄位集、算 diff、寫報告。

**設計來源：** spec §7.2、§8、§9（邊界驗證）。依賴 Task 02、03、04。

**Files:**
- Create: `the_door/src/the_door/mcp/tools/localize_datamodel_tool.py`
- Create: `the_door/src/the_door/mcp/tools/verify_contract_tool.py`
- Modify: `the_door/src/the_door/mcp/server.py`（import + `list_tools` 兩個 `Tool(...)` + `call_tool` 兩個 `elif`）
- Create: `the_door/tests/unit/mcp/test_localize_datamodel_tool.py`
- Create: `the_door/tests/unit/mcp/test_verify_contract_tool.py`

---

- [ ] **Step 1: 寫 localize 工具失敗測試**

`the_door/tests/unit/mcp/test_localize_datamodel_tool.py`：

```python
import asyncio

from the_door.mcp.tools import localize_datamodel_tool


def _make_project(tmp_path):
    md = tmp_path / "models"
    md.mkdir()
    (md / "user.py").write_text("def save_user(name):\n    return name\n", encoding="utf-8")
    (tmp_path / "init.sql").write_text("CREATE TABLE u(id int);\n", encoding="utf-8")
    return tmp_path


def test_localize_happy(tmp_path):
    _make_project(tmp_path)
    result = asyncio.run(localize_datamodel_tool.execute({"codebase_path": str(tmp_path)}))
    code_files = {c["file"] for c in result["code_candidates"]}
    schema_files = {c["file"] for c in result["schema_candidates"]}
    assert any("user.py" in f for f in code_files)
    assert "init.sql" in schema_files
    assert "next_actions" in result          # envelope injected


def test_localize_missing_path():
    result = asyncio.run(localize_datamodel_tool.execute({}))
    assert "error" in result
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && python -m pytest tests/unit/mcp/test_localize_datamodel_tool.py -q`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 3: 實作 localize_datamodel_tool.py**

`the_door/src/the_door/mcp/tools/localize_datamodel_tool.py`：

```python
"""MCP tool: localize_data_model — Tier 0 local localization (zero token)."""
from __future__ import annotations

from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.datamodel.datamodel_localizer import DataModelLocalizer
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path"],
    "properties": {
        "codebase_path": {
            "type": "string",
            "description": "Path to the codebase root.",
        },
    },
}


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    if not codebase_path:
        return {"error": "codebase_path is required"}
    result = ASTExtractor().extract(codebase_path)
    loc = DataModelLocalizer().localize(result, codebase_path)
    payload = {
        "code_candidates": [
            {"node_id": c.node_id, "file": c.file, "flagged_reason": c.flagged_reason}
            for c in loc.code_candidates
        ],
        "schema_candidates": [
            {"file": c.file, "flagged_reason": c.flagged_reason}
            for c in loc.schema_candidates
        ],
    }
    return wrap(payload, Path(codebase_path))
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd the_door && python -m pytest tests/unit/mcp/test_localize_datamodel_tool.py -q`
Expected: PASS。

- [ ] **Step 5: 寫 verify 工具失敗測試**

`the_door/tests/unit/mcp/test_verify_contract_tool.py`：

```python
import asyncio
import json

from the_door.mcp.tools import verify_contract_tool


def _args(tmp_path):
    return {
        "codebase_path": str(tmp_path),
        "declared_model": {"User": [{"field": "id", "type": "int"}, {"field": "name"}]},
        "code_touched_model": [{"op": "write", "entity": "User", "fields": ["name", "email"]}],
    }


def test_verify_happy_writes_report(tmp_path):
    result = asyncio.run(verify_contract_tool.execute(_args(tmp_path)))
    assert result["summary"] == {"write_gap": 1, "coverage_gap": 1, "match": 1}
    report = tmp_path / ".the-door" / "datamodel" / "contract.json"
    assert report.exists()
    parsed = json.loads(report.read_text(encoding="utf-8"))
    statuses = {(e["field"], e["status"]) for e in parsed["entries"]}
    assert ("email", "write_gap") in statuses
    assert ("id", "coverage_gap") in statuses
    assert ("name", "match") in statuses
    assert "next_actions" in result


def test_verify_missing_path():
    result = asyncio.run(verify_contract_tool.execute(
        {"declared_model": {}, "code_touched_model": []}))
    assert "error" in result


def test_verify_declared_not_dict(tmp_path):
    result = asyncio.run(verify_contract_tool.execute(
        {"codebase_path": str(tmp_path), "declared_model": [], "code_touched_model": []}))
    assert "error" in result


def test_verify_touched_not_list(tmp_path):
    result = asyncio.run(verify_contract_tool.execute(
        {"codebase_path": str(tmp_path), "declared_model": {}, "code_touched_model": {}}))
    assert "error" in result


def test_verify_malformed_field_set(tmp_path):
    # declared field dict missing required "field" key → caught, returns error
    result = asyncio.run(verify_contract_tool.execute({
        "codebase_path": str(tmp_path),
        "declared_model": {"User": [{"type": "int"}]},
        "code_touched_model": [],
    }))
    assert "error" in result
```

- [ ] **Step 6: 跑測試確認失敗**

Run: `cd the_door && python -m pytest tests/unit/mcp/test_verify_contract_tool.py -q`
Expected: FAIL（`ModuleNotFoundError`）。

- [ ] **Step 7: 實作 verify_contract_tool.py**

`the_door/src/the_door/mcp/tools/verify_contract_tool.py`：

```python
"""MCP tool: verify_data_model_contract — Tier 1 contract diff over agent-normalized field-sets."""
from __future__ import annotations

from pathlib import Path

from the_door.core.datamodel.models import DeclaredField, CodeTouch
from the_door.core.datamodel.contract_verifier import ContractVerifier
from the_door.core.datamodel.datamodel_renderer import contract_diff_to_json
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "declared_model", "code_touched_model"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root."},
        "declared_model": {
            "type": "object",
            "description": "entity -> list of {field, type?} (agent-normalized declared schema).",
        },
        "code_touched_model": {
            "type": "array",
            "description": "list of {op: 'write'|'read', entity, fields: [..]} (agent-normalized).",
        },
    },
}


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    declared_raw = arguments.get("declared_model")
    touched_raw = arguments.get("code_touched_model")
    if not codebase_path:
        return {"error": "codebase_path is required"}
    if not isinstance(declared_raw, dict):
        return {"error": "declared_model must be an object of entity -> fields"}
    if not isinstance(touched_raw, list):
        return {"error": "code_touched_model must be a list of touches"}

    try:
        declared = {
            entity: [DeclaredField(field=f["field"], type=f.get("type")) for f in fields]
            for entity, fields in declared_raw.items()
        }
        touched = [
            CodeTouch(op=t["op"], entity=t["entity"], fields=tuple(t["fields"]))
            for t in touched_raw
        ]
    except (KeyError, TypeError) as exc:
        return {"error": f"malformed field-set: {exc}"}

    diff = ContractVerifier().verify(declared, touched)

    root = Path(codebase_path)
    report_dir = root / ".the-door" / "datamodel"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "contract.json"
    report_path.write_text(contract_diff_to_json(diff), encoding="utf-8")

    payload = {
        "report_path": str(report_path),
        "summary": {
            "write_gap": sum(1 for e in diff.entries if e.status == "write_gap"),
            "coverage_gap": sum(1 for e in diff.entries if e.status == "coverage_gap"),
            "match": sum(1 for e in diff.entries if e.status == "match"),
        },
    }
    return wrap(payload, root)
```

- [ ] **Step 8: 跑測試確認通過**

Run: `cd the_door && python -m pytest tests/unit/mcp/test_verify_contract_tool.py -q`
Expected: PASS（happy + 4 error branches）。

- [ ] **Step 9: 註冊到 server.py**

在 `the_door/src/the_door/mcp/server.py`：

(a) import 區塊（與其他 `from the_door.mcp.tools import ...` 同段）加：

```python
from the_door.mcp.tools import localize_datamodel_tool, verify_contract_tool
```

(b) `_setup_tools` 內 `list_tools()` 回傳的 Tool 清單裡（與其他 `Tool(name=..., inputSchema=...)` 同段）加兩個：

```python
                Tool(
                    name="localize_data_model",
                    description="Tier 0 local localization of data-model touch points (zero token).",
                    inputSchema=localize_datamodel_tool.TOOL_SCHEMA,
                ),
                Tool(
                    name="verify_data_model_contract",
                    description="Tier 1 bidirectional contract diff over agent-normalized field-sets.",
                    inputSchema=verify_contract_tool.TOOL_SCHEMA,
                ),
```

(c) `call_tool(name, arguments)` 的 dispatch 鏈（與其他 `elif name == ...` 同段）加：

```python
            elif name == "localize_data_model":
                return await self._dispatch_tool(localize_datamodel_tool, arguments)
            elif name == "verify_data_model_contract":
                return await self._dispatch_tool(verify_contract_tool, arguments)
```

> 註：`description` 是否為 `Tool(...)` 必填依現有其他條目而定——若既有條目都帶 `description` 就照上；
> 若既有條目省略 `description`，比照省略即可。請以同檔現有寫法為準。

- [ ] **Step 10: 驗證註冊不破壞 server**

Run: `cd the_door && python -c "from the_door.mcp.server import *"`（無 import 錯誤即可）
其次跑既有 MCP server 測試確認不退步：
Run: `cd the_door && python -m pytest tests/unit/mcp -q`
Expected: 全綠、無退步。

- [ ] **Step 11: 跑覆蓋率**

Run: `cd the_door && python -m pytest tests/unit/mcp/test_localize_datamodel_tool.py tests/unit/mcp/test_verify_contract_tool.py --cov=the_door/src/the_door/mcp/tools/localize_datamodel_tool.py --cov=the_door/src/the_door/mcp/tools/verify_contract_tool.py --cov-report=term-missing -q`
Expected: PASS；兩工具檔 **100%**。

- [ ] **Step 12: Commit**

```bash
cd the_door
git add src/the_door/mcp/tools/localize_datamodel_tool.py src/the_door/mcp/tools/verify_contract_tool.py src/the_door/mcp/server.py tests/unit/mcp/test_localize_datamodel_tool.py tests/unit/mcp/test_verify_contract_tool.py
git commit -m "feat(mcp): localize_data_model + verify_data_model_contract tools"
```

## Done when
- [ ] `localize_data_model` 回候選檔 + 節點名、含 envelope；缺 codebase_path 回 error
- [ ] `verify_data_model_contract` 算 diff、寫 `.the-door/datamodel/contract.json`、回摘要；3 種邊界 + malformed 各回明確 error
- [ ] 兩工具在 server `list_tools` / `call_tool` 註冊、既有 MCP 測試不退步
- [ ] 兩工具檔覆蓋率 100%
