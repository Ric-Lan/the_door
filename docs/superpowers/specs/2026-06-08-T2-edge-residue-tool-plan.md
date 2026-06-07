# T2 plan：`edge_residue` 工具（inline TDD 任務分解）

> **承接 spec**：`2026-06-08-T2-edge-residue-tool-spec.md`（已雙審通過）。
> **執行模式**：inline TDD，每 task red→green→（不 commit，全綠後一次 ff-merge）。
> **環境**：pytest cwd＝內層 `the_door/`；Windows 前置 `PYTHONUTF8=1`。換 worktree 先 `pip install -e ./the_door`。
> **總原則**：純加法、零回歸。不改 `edge_projection.py`／`batch_reader.py` 一行。

---

## 測試策略（雙審已定，記此免重議）

`edge_residue` 的**新責任＝把 extraction.edges 接成 edge_dicts → 餵 `project_edges_for_prompt` → 落盤 artifact**。
- extraction 本身、`project_edges_for_prompt` 本身**已被既有測試覆蓋**（`tests/unit/core/llm/test_edge_projection.py` 用 `_edge()` 直建 edge dict；property 測在 `tests/property/test_edge_projection_properties.py`）。
- ⟹ **單元測試（Task 1）注入已知 extraction**（monkeypatch `ASTExtractor.extract` 回傳帶 `resolution` 的假 extraction），精確測「接線＋落盤」邏輯,對殘餘數值做**確定性斷言**。
- ⟹ **一條 E2E smoke（Task 3）** 用 input-only 的 `tmp_path` 真實小 codebase 跑真 extraction，**只斷言 artifact 產出＋鍵結構良好＋counts 為 int≥0**（不 hand-build 殘餘數值——那依 extractor 啟發式，會脆）。符合 `feedback_e2e_fixture_input_only`（fixture 只放 input）＋單元隔離兩者。

---

## Task 1 — 工具核心邏輯（unit, 注入 extraction）

**檔案**
- 新增：`the_door/src/the_door/mcp/tools/edge_residue_tool.py`（內容＝spec §3.1）
- 新增：`the_door/tests/unit/mcp/tools/test_edge_residue_tool.py`

**Red（先寫測，monkeypatch `ASTExtractor.extract` 回傳假 extraction）**

假 extraction＝一個有 `.edges` 的物件，每邊帶 `from_node/to_node/type/resolution`。建議用簡單 namespace/物件清單：
```python
import types
def _fake_extraction(edges):
    Edge = types.SimpleNamespace
    return types.SimpleNamespace(
        edges=[Edge(from_node=f, to_node=t, type="call", resolution=r) for (f, t, r) in edges]
    )
```

| 測試名 | 對應 spec | 斷言 |
|---|---|---|
| `test_residue_computed_and_artifact_written` | T-1 | 注入含 `("a","Bus.send","skipped_dynamic")` → 回傳 `indeterminate_count > 0`；`<tmp>/.the-door/edge-residue.json` 存在 |
| `test_artifact_shape` | T-2 | 讀回 artifact JSON：含鍵 `indeterminate`/`low_confidence_ambiguous`/`total_edges`/`kept_edges`；`indeterminate[0]` 含 `NoisePosition.to_json()` 的鍵（gap_kind/cardinality/proportion 等——以 `edge_projection.indeterminate_residue_element(...).to_json()` 實際鍵為準，測時呼一次取鍵集對齊，不 hardcode 猜鍵） |
| `test_no_noise_empty_residue` | T-5 | 注入全 `scope_rule` 邊 → `indeterminate_count == 0` 且 `low_confidence_count == 0`；artifact 仍寫出（空殘餘）、不報錯 |
| `test_missing_codebase_path` | T-4 | `execute({})` → 回 `{"error": ...}`；**不寫檔**（斷言路徑不存在） |
| `test_determinism` | T-3 | 同輸入呼兩次 → artifact 位元組相同 |

> ⚠ `execute` 是 `async def` → 測試用 `pytest.mark.asyncio` 或 `asyncio.run(execute(...))`（對齊既有 mcp tool 測法，先 grep `tests/unit/mcp/tools/` 既有風格）。

**Green（impl）**：照 spec §3.1 寫 `edge_residue_tool.py`（`TOOL_SCHEMA`、`_artifact_path`、`execute`）。

**Verify**：`PYTHONUTF8=1 python -m pytest tests/unit/mcp/tools/test_edge_residue_tool.py -q`

---

## Task 2 — server.py 註冊（integration）

**檔案**
- 編輯：`the_door/src/the_door/mcp/server.py`（3 處，見 spec §3.2）
  1. import：`from the_door.mcp.tools import edge_residue_tool`（併入 :24 一帶）
  2. `list_tools` 加 `Tool(name="edge_residue", description=..., inputSchema=edge_residue_tool.TOOL_SCHEMA)`
  3. `call_tool` 加 `elif name == "edge_residue": return await self._dispatch_tool(edge_residue_tool, arguments)`
- 測試：**擴充既有** `the_door/tests/unit/mcp/test_tools.py`（**非新檔**）——它已有 `server` fixture、`_list_tools(server)` helper（`request_handlers[ListToolsRequest]`）、`sample_codebase` fixture，以及 `test_<tool>_registered` 範本（`test_snapshot_write_registered` :61-69）。

**Red（mirror 既有 pattern，勿自鑄存取法）**
| 測試名 | 斷言（對齊 `test_tools.py:28-69`） |
|---|---|
| `test_edge_residue_registered` | `tools = await _list_tools(server)`；`"edge_residue" in [t.name for t in tools]`；該 tool `inputSchema["required"]` 含 `codebase_path`（mirror `test_snapshot_write_registered`） |
| `test_edge_residue_dispatch` | 經 `server._server.request_handlers[CallToolRequest]`（確認 import 名 `mcp.types.CallToolRequest`）呼叫 `edge_residue`（args＝`{"codebase_path": sample_codebase}`）→ 回 `TextContent`，`json.loads(...text)` 含 `artifact_path` |

> 🔴 **存取法已查實**：list/dispatch handler 是註冊在 `server._server` 上的 closure，**非** `TheDoorMCPServer` 方法。**必用** `_list_tools` helper ＋ `request_handlers[...]`（`test_tools.py:28-32` 即此法）。

**Green**：做上述 3 處註冊。

**Verify**：`PYTHONUTF8=1 python -m pytest tests/unit/mcp/ -q`

---

## Task 3 — E2E smoke ＋ 回歸護欄

**檔案**
- 編輯：`the_door/tests/unit/mcp/tools/test_edge_residue_tool.py`（加一條 E2E）

**Red（input-only，真 extraction；用既有 fixture）**
| 測試名 | 斷言 |
|---|---|
| `test_e2e_real_extraction` | 用既有 input-only fixture `the_door/tests/fixtures/sample_codebases/python_simple`（即 `test_tools.py` 的 `sample_codebase`），**先 `shutil.copytree` 到 `tmp_path`** 再傳入（見下注）。`execute({"codebase_path": <tmp 副本>})` → artifact 存在；JSON 鍵齊全（`indeterminate`/`low_confidence_ambiguous`/`total_edges`/`kept_edges`）；counts 皆 `int ≥ 0`。**不斷言殘餘確切數值**（依 extractor 啟發式、避免脆測）。 |

> 用 repo 既有 input-only fixture（不手搭、不放 hand-built 結果）。
> ⚠ **寫入位置**：`execute` 把 artifact 寫到 `<codebase_path>/.the-door/edge-residue.json`。E2E **不可污染 checked-in fixture** ⟹ 先 copytree 到 `tmp_path` 對副本跑。

**回歸護欄（純驗證、無 code 改動）**
- `PYTHONUTF8=1 python -m pytest tests/unit/core/llm/test_edge_projection.py tests/unit/core/llm/test_edge_projection_membrane.py tests/property/test_edge_projection_properties.py tests/unit/core/reading/test_batch_reader.py tests/unit/core/reading/test_batch_reader_resolution.py -q`
  → 全綠＝確認 `edge_projection.py`／`batch_reader.py` 未被本刀波及（本刀本就沒碰它們，此為護欄）。

**最終 Verify（全綠才 ff-merge）**：`PYTHONUTF8=1 python -m pytest -q`（全套零回歸）

---

## 完成定義（done-state）
- [ ] `edge_residue_tool.py` 存在，`execute` 行為符合 spec §3.1。
- [ ] `server.py` 三處註冊，`edge_residue` 可被 list/dispatch。
- [ ] 新測 T-1..T-6（含 E2E）全綠。
- [ ] 既有 edge_projection／batch_reader 測全綠（零回歸）。
- [ ] 全套 `pytest -q` 綠。
- [ ] `edge_projection.py`／`batch_reader.py` git diff ＝ 空。

## 不做（再次釘樁，承 spec §4/§6）
- 不接 hook gate（C3/C4）、不碰 provider（T1/T5）、不改 `extract_structure`、不做 versioned/coverage artifact、不碰 viewer。
