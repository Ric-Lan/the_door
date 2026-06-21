# Phase 2 — MCP 工具 + CLI

> 父計畫：[../2026-06-22-locate-query-plan.md](../2026-06-22-locate-query-plan.md)
> 前置：Phase 1 完成（`locator.search` / `locator.node` / `locator.LocateError` 已存在）。

兩個薄轉接，都只呼叫 Phase 1 的 `locator`，不含查詢邏輯。

---

### Task 6: MCP `locate` 工具 + server 註冊

**Files:**
- Create: `the_door/src/the_door/mcp/tools/locate_tool.py`
- Modify: `the_door/src/the_door/mcp/server.py`
- Test: `the_door/tests/unit/mcp/tools/test_locate_tool.py`

- [ ] **Step 1: 寫工具模組**

建 `the_door/src/the_door/mcp/tools/locate_tool.py`（樣式對齊 `edge_residue_tool.py`：
`TOOL_SCHEMA` + `async def execute`，成功回 `wrap(...)`、失敗回 `{"error": ...}`）：

```python
"""MCP tool: locate — symbol 定位點查 over 既有 structure-view（secondary，非主打）。"""
from __future__ import annotations

from pathlib import Path

from the_door.core.structure_view import locator
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "action"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root."},
        "action": {
            "type": "string",
            "enum": ["search", "node"],
            "description": "search=find symbols by name/path substring; node=detail of one node_id.",
        },
        "query": {"type": "string", "description": "search: substring matched against name and node_id."},
        "node_id": {"type": "string", "description": "node: the node_id to inspect (format file::symbol)."},
        "limit": {"type": "integer", "description": "search: max results (default 20)."},
    },
}


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    if not codebase_path:
        return {"error": "codebase_path is required"}
    action = arguments.get("action")
    try:
        if action == "search":
            payload = locator.search(
                codebase_path,
                arguments.get("query", ""),
                arguments.get("limit") or locator.SEARCH_DEFAULT_LIMIT,
            )
        elif action == "node":
            node_id = arguments.get("node_id")
            if not node_id:
                return {"error": "node_id is required for action=node"}
            payload = locator.node(codebase_path, node_id)
        else:
            return {"error": f"unknown action: {action!r} (expected 'search' or 'node')"}
    except locator.LocateError as exc:
        return {"error": str(exc)}
    return wrap(payload, Path(codebase_path))
```

- [ ] **Step 2: 註冊到 server**

修改 `the_door/src/the_door/mcp/server.py`：

(a) 於既有 tool import 區（約 line 30，`edge_residue_tool` import 附近）加：

```python
from the_door.mcp.tools import locate_tool
```

(b) 於 `_build_tools()` 回傳的 `Tool(...)` 清單末端（`integration_check` 之後、`]` 之前）加：

```python
        Tool(
            name="locate",
            description="(Secondary) Symbol locate point-queries over existing structure-view: action=search finds symbols by name/path; action=node returns one node's location + callers/callees. Data is not live (re-run extract_structure after edits); freshness signal included.",
            inputSchema=locate_tool.TOOL_SCHEMA,
        ),
```

(c) 於 `call_tool` 的 dispatch 鏈（`elif name == "integration_check":` 之後、`else:` 之前）加：

```python
            elif name == "locate":
                return await self._dispatch_tool(locate_tool, arguments)
```

- [ ] **Step 3: 寫測試**

建 `the_door/tests/unit/mcp/tools/test_locate_tool.py`：

```python
import asyncio

import pytest

from the_door.mcp import server
from the_door.mcp.tools import locate_tool


@pytest.fixture()
def simple(fixtures_dir):
    return fixtures_dir / "sample_codebases" / "python_simple"


def test_locate_registered_in_server():
    assert "locate" in server.REGISTERED_TOOL_NAMES


def test_execute_search(simple):
    out = asyncio.run(locate_tool.execute(
        {"codebase_path": str(simple), "action": "search", "query": "login"}))
    assert "error" not in out
    assert any(r["node_id"] == "app.py::login" for r in out["results"])
    assert "next_actions" in out          # wrap 注入

def test_execute_node(simple):
    out = asyncio.run(locate_tool.execute(
        {"codebase_path": str(simple), "action": "node",
         "node_id": "auth.py::authenticate_user"}))
    assert "error" not in out
    assert any(c["node_id"] == "app.py::login" for c in out["callers"])


def test_execute_missing_codebase_path():
    out = asyncio.run(locate_tool.execute({"action": "search", "query": "x"}))
    assert out["error"] == "codebase_path is required"


def test_execute_unknown_action(simple):
    out = asyncio.run(locate_tool.execute(
        {"codebase_path": str(simple), "action": "bogus"}))
    assert "unknown action" in out["error"]


def test_execute_node_without_node_id(simple):
    out = asyncio.run(locate_tool.execute(
        {"codebase_path": str(simple), "action": "node"}))
    assert "node_id is required" in out["error"]
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/unit/mcp/tools/test_locate_tool.py -v`
Expected: PASS（6 個測試全綠）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/mcp/tools/locate_tool.py the_door/src/the_door/mcp/server.py the_door/tests/unit/mcp/tools/test_locate_tool.py
git commit -m "feat(mcp): register locate tool (search/node) over structure-view

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: CLI `the-door locate` 群組 + main 註冊

**Files:**
- Create: `the_door/src/the_door/cli/locate_cmd.py`
- Modify: `the_door/src/the_door/cli/main.py`
- Test: `the_door/tests/unit/cli/test_locate_cmd.py`

- [ ] **Step 1: 寫 CLI 群組（人讀輸出 + freshness 尾註）**

建 `the_door/src/the_door/cli/locate_cmd.py`：

```python
"""CLI: the-door locate — 人讀的 symbol 定位點查（secondary；資料非即時）。"""
from __future__ import annotations

import click

from the_door.core.structure_view import locator


def _echo_freshness(freshness: dict) -> None:
    status = freshness.get("status")
    if status == "stale":
        n = freshness.get("changed_count", 0)
        click.echo(f"⚠ structure-view 可能過時（{n} 個檔已變動）；重跑 extract_structure 以更新")
    elif status == "unknown":
        click.echo("⚠ 無法判斷 structure-view 新鮮度（未跑過 edge_residue）")


@click.group("locate")
def locate_group():
    """對既有 structure-view 做 symbol 定位點查（輔助功能；資料非即時、名稱比對非語意搜尋）。"""


@locate_group.command("search")
@click.argument("query")
@click.option("--codebase-path", default=".", help="Codebase root (default: cwd).")
@click.option("--limit", default=locator.SEARCH_DEFAULT_LIMIT, show_default=True,
              help="Max results.")
def search_cmd(query, codebase_path, limit):
    """用名稱/路徑子字串找 symbol。"""
    try:
        result = locator.search(codebase_path, query, limit)
    except locator.LocateError as exc:
        raise click.ClickException(str(exc))
    for r in result["results"]:
        click.echo(f"{r['match_kind']:4}  {r['file']}:{r['start_line']}  "
                   f"{r['node_id']}  (in:{r['in_degree']})")
    click.echo(f"matched {result['total_matched']}, shown {result['returned']}")
    _echo_freshness(result["freshness"])


@locate_group.command("node")
@click.argument("node_id")
@click.option("--codebase-path", default=".", help="Codebase root (default: cwd).")
def node_cmd(node_id, codebase_path):
    """看單一 node 的位置 + callers/callees。"""
    try:
        result = locator.node(codebase_path, node_id)
    except locator.LocateError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"{result['node_id']}  {result['file']}:"
               f"{result['start_line']}-{result['end_line']}")
    for label, key in (("callers", "callers"), ("callees", "callees")):
        click.echo(f"{label}:")
        for c in result[key]:
            loc = f"  {c.get('file')}:{c.get('start_line')}" if c.get("file") else ""
            click.echo(f"  {c['node_id']}{loc}")
    _echo_freshness(result["freshness"])
```

> `click.ClickException` 由 click 印 `Error: <msg>` 至 stderr、exit code 1，
> 符合 spec §4.3「錯誤→stderr、非零 exit」。

- [ ] **Step 2: 註冊到 main**

修改 `the_door/src/the_door/cli/main.py`：

(a) 於 import 區（約 line 25，`verify_datamodel_cmd` import 之後）加：

```python
from the_door.cli.locate_cmd import locate_group
```

(b) 於 `main.add_command(...)` 區末端（`main.add_command(verify_datamodel_cmd)` 之後）加：

```python
main.add_command(locate_group)
```

- [ ] **Step 3: 寫測試（click CliRunner）**

建 `the_door/tests/unit/cli/test_locate_cmd.py`：

```python
import pytest
from click.testing import CliRunner

from the_door.cli.main import main


@pytest.fixture()
def simple(fixtures_dir):
    return str(fixtures_dir / "sample_codebases" / "python_simple")


def test_cli_search(simple):
    r = CliRunner().invoke(main, ["locate", "search", "login", "--codebase-path", simple])
    assert r.exit_code == 0
    assert "app.py::login" in r.output


def test_cli_node(simple):
    r = CliRunner().invoke(
        main, ["locate", "node", "auth.py::authenticate_user", "--codebase-path", simple])
    assert r.exit_code == 0
    assert "callers:" in r.output
    assert "app.py::login" in r.output


def test_cli_search_missing_artifacts(tmp_path):
    r = CliRunner().invoke(main, ["locate", "search", "x", "--codebase-path", str(tmp_path)])
    assert r.exit_code != 0
    assert "extract_structure" in r.output


def test_cli_help_registered():
    r = CliRunner().invoke(main, ["locate", "--help"])
    assert r.exit_code == 0
    assert "search" in r.output and "node" in r.output
```

- [ ] **Step 4: 跑測試確認通過**

Run: `python -m pytest tests/unit/cli/test_locate_cmd.py -v`
Expected: PASS（4 個測試全綠）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/cli/locate_cmd.py the_door/src/the_door/cli/main.py the_door/tests/unit/cli/test_locate_cmd.py
git commit -m "feat(cli): add the-door locate group (search/node) for humans

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 2 自審

- **spec §2 轉接**：Task 6（MCP 單一 `locate` 工具、action 分派、wrap 包裹）、Task 7（CLI 群組 search/node 子指令）。✓
- **spec §4.3 CLI 輸出**：Task 7 人讀逐行 + `matched/shown` + freshness 尾註、錯誤走 ClickException、無 `--json`。✓
- **型別一致**：`locator.search(codebase_path, query, limit)` / `locator.node(codebase_path, node_id)` / `locator.LocateError` / `locator.SEARCH_DEFAULT_LIMIT` 均與 Phase 1 定義一致。✓
- **註冊接線**：server `_build_tools` Tool + dispatch elif + import 三處；main import + add_command 兩處。`REGISTERED_TOOL_NAMES` 由 `_build_tools` 自動衍生，無需另改。✓
- **無 placeholder**：所有 code step 完整。✓
