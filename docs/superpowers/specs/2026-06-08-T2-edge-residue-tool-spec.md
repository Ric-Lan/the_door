# T2 spec：`edge_residue` 工具（雜訊膜表徵可觀察 ＋ L1 鏈免-key 輸入）

> **日期**：2026-06-08　**狀態**：spec（待雙審 → plan → 雙審 → inline TDD → ff-merge）
> **承接**：丙案種子 `2026-06-08-execution-model-control-via-structure-seed.md` §10.7.2 階段 1、§6 試點、§10.5。
> **這是階段 1 的第一份 spec。** 同階段 T1（隔離 provider）、C3+C4（gate）為後續獨立 spec。
> **性質**：純加法。新增一個零-token、零-key、確定性 MCP 工具，**不改任何既有路徑的行為**。

---

## 1. 命題與目標

**今天「雜訊」完全不可觀察**（種子 §4f/§10.5）：邊的格外殘餘（`skipped_dynamic`）與格內低信心（`name_match_ambiguous`）只在**有 key 的 analyze 路徑**（`BatchReader`）即時算成 prompt 輸入、**不持久化、無工具吐**；agent-as-LLM 路徑（`extract_structure`→`snapshot_write`）整段繞過它。

**T2 做一件事**：把這層殘餘的計算，做成一個獨立 MCP 工具 `edge_residue`，**輸出持久化成可檢視 artifact**。

達成兩個目的（種子 §6「一刀補兩洞」的工具半）：
1. **雜訊膜表徵可觀察**：使用者/agent 終於能看見「哪些邊被當雜訊、座標分明」（gap_kind / cardinality / proportion）。
2. **L1 鏈免-key 補件**：agent-as-LLM 的 L1 雜訊輸入**從此可取用**（artifact 落盤，**agent 自讀**取用——本刀只接「產出」，不接「消費」；把 artifact 讀進 L1 是 agent 的事，C3 也只 gate 存在、不 gate 消費）。這是「移除 provider 後 L1 不缺料」的前提（種子 §9.4 順序鎖：**先有此工具、後拔 provider**）。

> ⚠ **粒度界定（避免與 analyze 路徑混淆）**：本工具算**全 codebase** 殘餘;analyze 路徑（`batch_reader.py:290-298`）算的是**過濾到 batch_node_set 的 per-batch** 殘餘。因 `project_edges_for_prompt` 的 proportion 以 `total = len(edges)` 為分母（`edge_projection.py:43`），**全域殘餘的 proportion 數值不會等於 analyze 的 per-batch 數字**。全域 by design——對「可觀察性」與「整體 agent-as-LLM L1」才是正確的；**不是** analyze per-batch 的重現。

**非目標**：本 spec **不**含 blocking hook gate（那是 C3+C4，需要本工具的 artifact 先存在才有東西可驗）。本 spec 只交付「會產 artifact 的工具」。

---

## 2. 背景與驗證事實（spike 已對真實碼驗畢，免事後驗證）

| # | 事實 | 依據（file:line） |
|---|---|---|
| 2.1 | MCP `extract_structure` 的 edges 輸出為 `{from,to,type}`、**不含 `resolution`**，且**不寫 `.the-door/structure.json`**（只回傳給 agent） | `mcp/server.py:264-301`（`_extract_structure`，edges 見 :285-288） |
| 2.2 | ⟹ `edge_residue` **必須自行 re-extract**（`ASTExtractor`，可取 `e.resolution`），**不可**依賴持久化 structure.json（純 agent-as-LLM 流下它不存在）。範本＝`localize_data_model`（同樣 re-extract） | `mcp/tools/localize_datamodel_tool.py:22-38` |
| 2.3 | 殘餘計算＝純函式 `project_edges_for_prompt(edges: list[dict]) -> (kept, residue)`；零 key、零 LLM、零 I/O | `core/llm/edge_projection.py:25-71`（模組 docstring :10「pure: no I/O, no logging, no global state, no flags」） |
| 2.4 | 它消費的 edge_dict 形狀＝`{"from","to","type","resolution"}`；`residue` 形狀＝`{"indeterminate":[NoisePosition.to_json()...], "low_confidence_ambiguous":[{caller,methods,cardinality,confidence}...]}` | `core/reading/batch_reader.py:290-308`（呼叫端）；`edge_projection.py:56-70`（residue 構造） |
| 2.5 | **不可 relocate** `project_edges_for_prompt`：`batch_reader.py:9,301` 仍 import 它跑 analyze 路徑。relocate 會破壞 analyze。⟹ 工具**import 並共用**該純函式（§9.4「搬進工具」＝「經工具可達」，非「物理搬移」） | `core/reading/batch_reader.py:9`（import）、`:301`（呼叫） |
| 2.6 | artifact 路徑慣例＝`.the-door/` 下；`structure.json`（canonical）、`structures/<vid>.json.gz`（versioned） | `core/extraction/structure_serializer.py:121,134` |
| 2.7 | MCP 工具註冊＝4 點：新檔（`TOOL_SCHEMA`＋`async def execute`）→ server.py import → `list_tools` 加 `Tool(...)` → `call_tool` 加 `elif`→`_dispatch_tool`；回傳統一過 `wrap(payload, project_path)` | `mcp/server.py:13-24,70-199,201-262`；`mcp/tools/_response_envelope.py:14-38` |
| 2.8 | 測試慣例位置＝`tests/unit/mcp/tools/`；純函式已有 `tests/unit/core/llm/test_edge_projection.py`＋`tests/property/test_edge_projection_properties.py`（本 spec 不動它們） | repo 既有結構 |

**結論**：設計無未知。下節設計直接落在已驗證的接縫上。

---

## 3. 設計

### 3.1 新檔 `the_door/src/the_door/mcp/tools/edge_residue_tool.py`

```python
"""MCP tool: edge_residue — persist the membrane noise residue (zero token, zero key)."""
from __future__ import annotations

import json
from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.llm.edge_projection import project_edges_for_prompt
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

EDGE_RESIDUE_FILENAME = "edge-residue.json"


def _artifact_path(codebase_path: str | Path) -> Path:
    return Path(codebase_path) / ".the-door" / EDGE_RESIDUE_FILENAME


async def execute(arguments: dict) -> dict:
    codebase_path = arguments.get("codebase_path")
    if not codebase_path:
        return {"error": "codebase_path is required"}

    extraction = ASTExtractor().extract(codebase_path)
    edge_dicts = [
        {"from": e.from_node, "to": e.to_node, "type": e.type, "resolution": e.resolution}
        for e in extraction.edges
    ]
    kept, residue = project_edges_for_prompt(edge_dicts)

    artifact = {
        "indeterminate": residue["indeterminate"],
        "low_confidence_ambiguous": residue["low_confidence_ambiguous"],
        "total_edges": len(edge_dicts),
        "kept_edges": len(kept),
    }
    out_path = _artifact_path(codebase_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "artifact_path": str(out_path),
        "indeterminate_count": len(residue["indeterminate"]),
        "low_confidence_count": len(residue["low_confidence_ambiguous"]),
        "total_edges": len(edge_dicts),
        "kept_edges": len(kept),
    }
    return wrap(payload, Path(codebase_path))
```

**設計要點**：
- **re-extract**（2.2）：`ASTExtractor().extract` 給帶 `resolution` 的 `Edge`。
- **共用純函式**（2.5）：import `project_edges_for_prompt`，不複製、不搬移。
- **持久化**（2.6）：`.the-door/edge-residue.json`，UTF-8（Windows cp950 安全）。
- **artifact 內容＝完整 residue**（給人/agent 唸成自然語言）；**回傳 payload＝摘要＋路徑**（避免巨量回灌，對齊 `project_list` 巨量輸出的教訓）。
- 過 `wrap()`（2.7）保持 next_actions 一致。

### 3.2 註冊（`mcp/server.py`，4 處小改）
1. `from the_door.mcp.tools import edge_residue_tool`（併入 :24 一帶 import）。
2. `list_tools` 加：
   ```python
   Tool(
       name="edge_residue",
       description="Persist the membrane noise residue (off-grid + low-confidence edges) as a viewable artifact. Zero token, zero key. Run after extract_structure, before snapshot_write.",
       inputSchema=edge_residue_tool.TOOL_SCHEMA,
   ),
   ```
3. `call_tool` 加：`elif name == "edge_residue": return await self._dispatch_tool(edge_residue_tool, arguments)`。

### 3.3 不動的東西（保證零回歸）
- `core/llm/edge_projection.py`：**不改一行**。
- `core/reading/batch_reader.py`：**不改一行**（analyze 路徑照舊用同一純函式）。
- provider / analyze / 任何既有工具：**不碰**。

---

## 4. 範圍邊界

**In scope**：
- 新增 `edge_residue` MCP 工具（re-extract → `project_edges_for_prompt` → 持久化 `.the-door/edge-residue.json` → 回摘要）。
- server.py 註冊。
- 單元測試。

**Out of scope（明確排除，留給後續刀）**：
- ❌ blocking hook gate（C3）／bash code-exec gate（C4）——本工具只「產 artifact」，gate 是下一份 spec。
- ❌ 移除/隔離 provider（T1/T5）。
- ❌ 改 `extract_structure` 讓它持久化 structure.json 或補 resolution（非本刀；re-extract 已解）。
- ❌ versioned artifact（`<vid>` 維度）——pilot 用 canonical 單檔；版本化待 C2 checklist schema 一起想。
- ❌ viewer 顯示 residue（人類面，另案）。

---

## 5. 驗收 / TDD（red→green 順序）

測試檔：`the_door/tests/unit/mcp/tools/test_edge_residue_tool.py`

| # | 測試 | 斷言 |
|---|---|---|
| T-1 | 對含 `skipped_dynamic` 邊的 fixture codebase 呼叫 `execute` | 回傳 `indeterminate_count > 0`；artifact 檔案存在於 `.the-door/edge-residue.json` |
| T-2 | artifact 內容 | 讀回 JSON，含 `indeterminate`/`low_confidence_ambiguous`/`total_edges`/`kept_edges`；`indeterminate` 元素結構＝`NoisePosition.to_json()`（gap_kind/cardinality/proportion 等鍵） |
| T-3 | 確定性 | 同一 codebase 連呼兩次，artifact 位元組相同（純函式＋確定性 extract） |
| T-4 | 缺 `codebase_path` | 回 `{"error": ...}`，不寫檔 |
| T-5 | 無雜訊的 codebase | `indeterminate_count == 0`、`low_confidence_count == 0`，仍正常寫出空殘餘 artifact（不報錯、不謊報） |
| T-6（回歸護欄） | import `core.reading.batch_reader` 與 `core.llm.edge_projection` | 兩模組未被本刀更動：`project_edges_for_prompt` 仍可被 batch_reader 呼叫（既有 `test_edge_projection*`、`test_batch_reader*` 全綠） |

**E2E fixture 守則**（`feedback_e2e_fixture_input_only`）：fixture 只放輸入 codebase；residue 由工具產、測試斷言；不放 hand-built 結果。

---

## 6. 不做 / 防呆紀錄

- **不 relocate 純函式**（2.5）：會弄死 analyze。共用即可。
- **不依賴 structure.json**（2.2）：MCP extract 不寫它；re-extract 才 robust。
- **不把完整 residue 塞回傳**：巨量會爆 context（`project_list` 教訓）；完整入 artifact、回傳只摘要。
- **不自鑄精確**：residue 缺值/空集照實寫（fact-finder；空≠錯）。

---

## 7. Forward-coherence（本刀對下一刀 C3 提供什麼——含與種子 §3 的偏差，誠實標明）

本刀為 C3（gate `snapshot_write`）備齊的前提：
- ✅ 有一個**確定路徑**的 artifact（`.the-door/edge-residue.json`）讓 PreToolUse hook 用 `test -f` 驗存在。
- ✅ `snapshot_write` 的 TOOL_SCHEMA **required `codebase_path`**（已驗證 `snapshot_write_tool.py:20-24`，snapshot 存於 `<codebase_path>/.the-door/snapshots/`）→ C3 hook 可從 `snapshot_write` 的 `tool_input.codebase_path` 推得同一 `.the-door/` 路徑。（`jq` 能否讀 MCP `tool_input` 仍是 C3 的 spike，不是本刀。）
- ✅ 工具**先於** `snapshot_write` 跑（語意：產雜訊料 → 才落 L1）——正是 C3 要強制的序。

🔴 **與種子 §3 成敗關鍵的偏差（不可隱瞞）**：種子 §3 要求 gate 驗「artifact 已存在**且涵蓋本批節點**」，§9.6 另警告「存在≠currency」。但本刀的 artifact 是 **版本-less、無 node-coverage manifest 的單檔**（§4 已將 versioned/coverage out-of-scope）。⟹ **C3 首閘只能做「存在性檢查」，做不到種子 §3 等級的「涵蓋本批節點」檢查；且 codebase 變動後 stale artifact 仍會過閘。**

**這是 pilot 的有意簡化，非「§3 已滿足」**：
- pilot 目的＝先證「gate 機制能擋」（承 §6「先垂直切片證機制」），存在性閘已足以證機制。
- **涵蓋檢查 ＋ currency（stale 偵測）deferred**：待後續為 artifact 補 `version_id` ＋ node-coverage 清單（與 C2 checklist schema 一起設計），C3 再升級到種子 §3 等級。**此偏差登記在此，C3 spec 須承接、不得默默當成已達標。**

⟹ 本刀交付後，C3 有「可被 existence-gate 的真實 artifact」可綁；種子 §10.7.2 順序鎖（先 T2、後 C3）滿足。種子 §3 的完整涵蓋閘為**已知待補**，非本刀範圍。

---

## 8. 雙審待查點（給 reviewer）

- §3.1 `residue["indeterminate"]` 元素是否已是 JSON-safe（`NoisePosition.to_json()`）——`edge_projection.py:58` 已 `.to_json()`，工具直接轉存即可，勿二次序列化。
- artifact 寫入失敗（唯讀目錄）是否該 fail-closed？pilot 傾向讓例外冒泡（`_dispatch_tool` 已包 try/except 轉 `{"error":...}`）。
- `ASTExtractor().extract` 的 `extra_ignore` 預設行為與 `extract_structure` 是否一致（本刀未傳 extra_ignore；確認預設不漏邊）。
