# Phase 3 — MCP 工具 + CLAUDE.md 協定

> 父計畫：[../2026-06-23-chunk-dispatch-merge-plan.md](../2026-06-23-chunk-dispatch-merge-plan.md)。前置：Phase 1、2 完成。
> 同前環境規則。

把 `chunk_merge.merge` 包成 MCP 工具並註冊（唯讀、不入 gate），再於 CLAUDE.md 寫分塊翻譯協定。

---

### Task 6: `chunk_merge` MCP 工具 + server 註冊

**Files:**
- Create: `the_door/src/the_door/mcp/tools/chunk_merge_tool.py`
- Modify: `the_door/src/the_door/mcp/server.py`
- Test: `the_door/tests/unit/mcp/tools/test_chunk_merge_tool.py`

- [ ] **Step 1: 寫工具模組**

建 `the_door/src/the_door/mcp/tools/chunk_merge_tool.py`：

```python
"""MCP tool: chunk_merge — 收齊各 chunk 的 features，從結構邊決定性推導 static
relations，回傳可寫入 snapshot_write 的 payload。唯讀、不寫 snapshot、不入 C3 gate。"""
from __future__ import annotations

from pathlib import Path

from the_door.core.structure_view import chunk_merge
from the_door.core.structure_view.locator import LocateError
from the_door.mcp.tools._response_envelope import wrap

TOOL_SCHEMA = {
    "type": "object",
    "required": ["codebase_path", "chunks"],
    "properties": {
        "codebase_path": {"type": "string", "description": "Path to the codebase root."},
        "chunks": {
            "type": "array",
            "description": (
                "Per-chunk subagent outputs. Each: {chunk_id, features:[{feature_id "
                "(chunk-namespaced, globally unique), label, description, confidence, "
                "source_nodes:[node_id]}]}. Subagents produce features only — relations "
                "are derived here deterministically from structural edges."
            ),
            "items": {
                "type": "object",
                "required": ["chunk_id", "features"],
                "properties": {
                    "chunk_id": {"type": "string"},
                    "features": {"type": "array", "items": {"type": "object"}},
                },
            },
        },
    },
}


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    if not codebase_path:
        return {"error": "codebase_path is required"}
    chunks = arguments.get("chunks")
    if not chunks:
        return {"error": "chunks is required and must be non-empty"}
    try:
        payload = chunk_merge.merge(codebase_path, chunks)
    except (chunk_merge.ChunkMergeError, LocateError) as exc:
        return {"error": str(exc)}
    return wrap(payload, Path(codebase_path))
```

- [ ] **Step 2: 註冊到 server**

修改 `the_door/src/the_door/mcp/server.py`：

(a) import 區（`integration_check_tool` import 附近）加：
```python
from the_door.mcp.tools import chunk_merge_tool
```

(b) `_build_tools()` 的 `Tool(...)` 清單末端（`integration_check` 之後、`]` 之前）加：
```python
        Tool(
            name="chunk_merge",
            description="(大專案分塊翻譯) Merge per-chunk subagent feature outputs into one snapshot_write payload; derives feature-level static relations deterministically from structural edges. Read-only (does not write a snapshot).",
            inputSchema=chunk_merge_tool.TOOL_SCHEMA,
        ),
```

(c) `call_tool` dispatch 鏈（`elif name == "integration_check":` 之後、`else:` 之前）加：
```python
            elif name == "chunk_merge":
                return await self._dispatch_tool(chunk_merge_tool, arguments)
```

> **不需動 C3 gate**：`.claude/hooks/c3_gate_snapshot_write.py` 只 gate `snapshot_write`/`snapshot_patch`；`chunk_merge` 唯讀、不寫 source_nodes，本就不在 gate 範圍。

- [ ] **Step 3: 寫測試**

建 `the_door/tests/unit/mcp/tools/test_chunk_merge_tool.py`：

```python
import asyncio
import pytest

from the_door.mcp import server
from the_door.mcp.tools import chunk_merge_tool


@pytest.fixture()
def simple(fixtures_dir):
    return str(fixtures_dir / "sample_codebases" / "python_simple")


def _feat(fid, nodes):
    return {"feature_id": fid, "label": fid, "description": "d",
            "confidence": "high", "source_nodes": list(nodes)}


def test_chunk_merge_registered():
    assert "chunk_merge" in server.REGISTERED_TOOL_NAMES


def test_execute_normal(simple):
    chunks = [
        {"chunk_id": "c001", "features": [_feat("feat-c001-login", ["app.py::login"])]},
        {"chunk_id": "c002", "features": [_feat("feat-c002-auth", ["auth.py::authenticate_user"])]},
    ]
    out = asyncio.run(chunk_merge_tool.execute({"codebase_path": simple, "chunks": chunks}))
    assert "error" not in out
    assert out["rollup"]["feature_count"] == 2
    assert "next_actions" in out          # wrap 注入
    assert any(r["relation_type"] == "static" for r in out["relations"])


def test_execute_missing_codebase_path():
    out = asyncio.run(chunk_merge_tool.execute({"chunks": [{"chunk_id": "c", "features": []}]}))
    assert out["error"] == "codebase_path is required"


def test_execute_empty_chunks(simple):
    out = asyncio.run(chunk_merge_tool.execute({"codebase_path": simple, "chunks": []}))
    assert "chunks is required" in out["error"]


def test_execute_duplicate_feature_id(simple):
    chunks = [
        {"chunk_id": "c001", "features": [_feat("feat-dup", ["app.py::login"])]},
        {"chunk_id": "c002", "features": [_feat("feat-dup", ["auth.py::generate_token"])]},
    ]
    out = asyncio.run(chunk_merge_tool.execute({"codebase_path": simple, "chunks": chunks}))
    assert "duplicate feature_id" in out["error"]
```

- [ ] **Step 4: 跑測試確認通過 + registry 不回歸**

Run: `python -m pytest the_door/tests/unit/mcp/tools/test_chunk_merge_tool.py the_door/tests/unit/mcp/test_server_tool_registry.py -v`
Expected: 全 PASS（5 新 + registry 內部一致仍綠，`chunk_merge` 自動入 REGISTERED_TOOL_NAMES）

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/mcp/tools/chunk_merge_tool.py the_door/src/the_door/mcp/server.py the_door/tests/unit/mcp/tools/test_chunk_merge_tool.py
git commit -F - <<'EOF'
feat(mcp): register chunk_merge tool (read-only, derives static relations)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### Task 7: CLAUDE.md 分塊翻譯協定 + 工具表

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 工具表加一列**

在 `CLAUDE.md`「Commands & MCP tool reference」表，於 `integration_check` 那列之後加：

```markdown
| `chunk_merge` MCP | （大專案分塊翻譯）收齊各 chunk subagent 的 features，從結構邊決定性推導 feature 層 static relations，回傳可寫入 `snapshot_write` 的 payload。唯讀、不寫 snapshot。詳分塊翻譯協定。 |
```

- [ ] **Step 2: 加「大專案分塊翻譯協定」段**

在 `CLAUDE.md` 的 agent-as-LLM chain 區（`### Agent-as-LLM chain (single version)` 等附近）新增一節，內容如下：

````markdown
### Agent-as-LLM chain (大專案分塊翻譯：dispatch + merge)

當專案大到單一 agent 讀不完整份 structure-view 時，改走分塊：每塊派一個 fresh
Task subagent 翻譯、再決定性合併。**The Door 不 spawn subagent——派發是你（執行
agent）的事**；工具只提供切分計畫與決定性合併。

**第 0 步（必做）**：`chunk_planner.plan(codebase_path)` 讀 `feasible` / `needs_split`：
- `feasible == false`（`regime: "too_large"`）→ **不派發**，回饋使用者：
  「⚠ 專案過大（估計 ~{total_est_tokens} tokens，超過上限 {max_total_tokens}），
  無法使用 LLM 翻譯功能。可縮小分析範圍、或明確調高 max_total_tokens 重試（風險自負）。」
- `needs_split == false` → 走單版 chain（前述既有路徑）。
- `feasible == true` 且 `needs_split == true` → 分塊翻譯：
  - **派發成本軟提醒**：若 `rollup.chunk_count` 偏高（>30），先告知不擋：「將派發 N 個
    subagent（耗時/成本較高），可調高 target_tokens 減少塊數」。

**分塊翻譯流程**：
1. 對 `plan()` 回的每個 chunk，派一個 Task subagent，給它**該塊 node_ids 的 views**
   （從 `.the-door/structure-view/regions/*.json.gz` 取；因塊為預算大小，必塞得下）
   ＋ `chunk_id`。subagent 任務：就這些節點產 L1 features，每筆
   `{feature_id, label, description, confidence, source_nodes}`，**`feature_id` 以
   `chunk_id` 前綴命名空間**（如 `feat-c003-auth`）、**不產 relations、不產 project_summary**。
   回傳**只含 features**。
2. `chunk_merge(codebase_path, chunks=[{chunk_id, features:[…]}, …])`
   → 回 `{l1_features, relations(static、由結構邊推導), rollup}`。
3. `edge_residue(codebase_path)`（C3 前置，蓋 checklist）。
4. 你**自己**從 `l1_features` 綜合 `project_summary`（白話、不引入 features 外的能力）。
5. `snapshot_write(codebase_path, l1_features=…, relations=…, project_summary=…, label=…)`
   → 一次 gated 寫入（source_nodes 為全節點子集、⊆ edge_residue covered → 過 C3）。

**前置鏈順序**：`extract_structure`（仍必跑——產 structure-view，供 plan / 各 subagent /
chunk_merge 讀）→ `plan` → 分塊 dispatch → `chunk_merge` → `edge_residue` → `snapshot_write`。
（分塊模式跳過的是單-agent「全量讀 L0 index 再逐區 drill」那段，直接以 `plan` 切塊派發；
但 `extract_structure` 本身不可省。）`edge_residue` 須在最終 `snapshot_write` 前完成、且其後
source 未變動（否則 C3 staleness 擋）。

**誠實限制**（寫給使用者看的話也照此）：分塊模式產出的 feature 較細、可能碎裂（稠密
專案無法乾淨切分）；只產 `static` 結構 relation（無概念/inferred）；天花板被推高但仍有限
（`too_large` 時明確回饋）。
````

- [ ] **Step 3: 驗證文件正確**

Run: `python -m pytest the_door/tests/ -k "claude_md or docs" -v`
Expected: 若無對應 lint 測試則「no tests ran」——改人工目視 CLAUDE.md：表格無斷裂、新段落 fenced code 正確閉合。

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -F - <<'EOF'
docs(claude): add large-project chunked translation protocol (dispatch + merge)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
```

---

### 收尾：全套件回歸 + 禁區守恆

- [ ] **Step 1: 全套件**

Run: `python -m pytest the_door/tests/ -q`
Expected: 全 PASS（含新 chunk_merge / 工具 / planner guard 測試）。`test_server_tool_registry.py` 只驗內部一致，加 `chunk_merge` 自動通過；`test_tools.py` 無工具總數硬斷言。

- [ ] **Step 2: 禁區守恆**

Run: `git diff --stat main`
Expected: 只含 `chunk_planner.py`（加守衛）、`chunk_merge.py`、`chunk_merge_tool.py`、`server.py`（註冊）、`CLAUDE.md`、3 個測試檔。**不應**出現：`models/`、`extract_structure`、契約版號、**gate hook（`.claude/hooks/`）**、前端 viewer、`region_partition.py`、`locator.py`（import 複用、不改）。

---

## Phase 3 自審
- spec §4 工具化（schema、execute、wrap、唯讀不入 gate）→ Task6；server 三點註冊。✓
- spec §2 協定 + §5 回饋敘述 + §3 subagent 任務規範 + 前置鏈（含 edge_residue）→ Task7。✓
- 型別一致：`chunk_merge.merge` / `ChunkMergeError` / `LocateError` 與 Phase 2 定義相符；schema required 欄位與 execute 取值相符。✓
- registry 不回歸（自動衍生）；禁區守恆檢查列為收尾。✓
- 無 placeholder。✓
