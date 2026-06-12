# 立體化結構實作計畫 Part 2／2：MCP 接縫＋文件＋驗收（Task 5–9）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Part 1 的 structure_view 管線接上 MCP（extract_structure 回索引、validate_output artifact 接縫）、同步文件、跑自驗收。

**前置：** Part 1（`2026-06-12-stereoscopic-structure-part1.md`）Task 1–4 已完成且全綠。

**Spec:** `docs/superpowers/specs/2026-06-12-stereoscopic-structure-design.md`

**環境鐵則同 Part 1**（cwd＝`the_door/`、`PYTHONUTF8=1 python -m pytest`、commit 用 `-F`/單行 `-m`）。

---

### Task 5: `_extract_structure` 改回 L0 索引（回應瘦身＋wrap）

**Files:**
- Modify: `the_door/src/the_door/mcp/server.py:251-288`（`_extract_structure` 方法）＋頂部 import 區
- Modify: `the_door/src/the_door/mcp/server.py` `_build_tools()` 內 extract_structure 的 description
- Test: `the_door/tests/unit/mcp/test_tools.py`（更新既有形狀斷言）

- [ ] **Step 1: 更新測試（既有斷言改為索引形狀＋artifact 存在）**

打開 `the_door/tests/unit/mcp/test_tools.py`，找 `TestExtractStructureTool`（約 :119）。保留 `test_extract_with_invalid_path` 不動。把 `test_extract_with_valid_path` 整個替換為：

```python
    @pytest.mark.asyncio
    async def test_extract_with_valid_path_returns_index(self, server, sample_codebase):
        """extract_structure 回 L0 索引（非全量），bulk 落 structure-view artifact。"""
        result = await server._extract_structure({"codebase_path": sample_codebase})
        assert len(result) == 1
        data = json.loads(result[0].text)
        # 索引形狀
        assert "totals" in data and "regions" in data and "consumption_guide" in data
        assert data["totals"]["nodes"] > 0
        # 全量欄位不再內嵌
        assert "nodes" not in data and "edges" not in data and "topology" not in data
        # wrap envelope 照常
        assert "next_actions" in data and "verification_guidance" in data
        # artifact 落檔
        from pathlib import Path
        view_dir = Path(sample_codebase) / ".the-door" / "structure-view"
        assert (view_dir / "index.json").is_file()
        assert (view_dir / "structure.full.json.gz").is_file()
        for r in data["regions"]:
            assert Path(r["artifact_path"]).is_file()
```

同檔其他若有斷言 extract 回應含 `nodes`/`edges` 的測試（先 `grep -n '"nodes"\|"edges"' the_door/tests/unit/mcp/test_tools.py` 檢查），一律改成從 `structure.full.json.gz` 讀後斷言（形狀同舊）。

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_tools.py -v`
Expected: `test_extract_with_valid_path_returns_index` FAIL（回應仍是全量形狀）

- [ ] **Step 3: 改 server.py**

import 區加（與既有 import 風格一致、字母序插入）：

```python
from the_door.core.llm.edge_projection import project_edges_for_prompt
from the_door.core.structure_view.structure_index import write_artifacts
from the_door.mcp.tools._response_envelope import wrap
from the_door.models import StructureJSON
```

（先 grep server.py 既有 import：`StructureJSON` 與 `wrap` 可能已在，已在則不重複。）

`_extract_structure` 整個方法替換為：

```python
    async def _extract_structure(self, arguments: dict):
        codebase_path = arguments.get("codebase_path", "")
        try:
            extractor = ASTExtractor()
            result = extractor.extract(codebase_path)

            analyzer = TopologyAnalyzer()
            topology = analyzer.analyze(result.nodes, result.edges)

            structure = StructureJSON(
                files=result.files, nodes=result.nodes,
                edges=result.edges, topology=topology.entries,
            )
            # 殘餘基數（L2 視圖的 residue_as_caller 用）；與 edge_residue 工具同一純函式
            edge_dicts = [
                {"from": e.from_node, "to": e.to_node, "type": e.type, "resolution": e.resolution}
                for e in result.edges
            ]
            _, residue = project_edges_for_prompt(edge_dicts)

            index = write_artifacts(codebase_path, structure, residue)
            payload = wrap(index, Path(codebase_path))
            return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]
        except (FileNotFoundError, ValueError) as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
```

（`Path` 若 server.py 未 import 則補 `from pathlib import Path`。）

`_build_tools()` 裡 extract_structure 的 `description` 改為：

```
"Extract AST structure: returns an L0 index (regions + peel labels + sizes + drill addresses); full nodes/edges/topology land in .the-door/structure-view/ artifacts."
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_tools.py -v`
Expected: 全 passed

- [ ] **Step 5: 跑整個 mcp 測試群抓連鎖破壞**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/ -v`
Expected: 全 passed。若 `test_response_envelope_coverage.py::test_every_tool_returns_next_actions` 之類掃工具回應的測試失敗，按其斷言把 extract 回應對齊（wrap 已附 next_actions，理論上直接過）。

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/mcp/server.py the_door/tests/unit/mcp/test_tools.py
git commit -m "feat(mcp): extract_structure 回 L0 撥離索引，全量落 structure-view artifact"
```

---

### Task 6: `validate_output` artifact 接縫（codebase_path 可選參數）

**Files:**
- Modify: `the_door/src/the_door/mcp/server.py:290-306`（`_validate_output`）＋`_build_tools()` 內 validate_output schema（:49 附近）
- Test: `the_door/tests/unit/mcp/test_tools.py`（新增 class）

- [ ] **Step 1: 寫失敗測試**

加進 `the_door/tests/unit/mcp/test_tools.py`：

```python
class TestValidateOutputSeam:
    """validate_output 的 structure-view artifact 接縫（spec §4.2）。"""

    @pytest.mark.asyncio
    async def test_fallback_reads_structure_view_artifact(self, server, sample_codebase):
        await server._extract_structure({"codebase_path": sample_codebase})  # 先落 artifact
        result = await server._validate_output({
            "llm_output": {"l1_features": [], "relations": []},
            "codebase_path": sample_codebase,
        })
        data = json.loads(result[0].text)
        assert "error" not in data and "passed" in data  # 取得結構、走完驗證

    @pytest.mark.asyncio
    async def test_explicit_structure_json_takes_precedence(self, server, sample_codebase):
        result = await server._validate_output({
            "llm_output": {"l1_features": [], "relations": []},
            "structure_json": {"files": [], "nodes": [], "edges": [], "topology": []},
            "codebase_path": "/nonexistent",  # 若 fallback 被誤走會炸
        })
        data = json.loads(result[0].text)
        assert "passed" in data

    @pytest.mark.asyncio
    async def test_neither_source_returns_error(self, server, tmp_path):
        result = await server._validate_output({
            "llm_output": {"l1_features": []},
            "codebase_path": str(tmp_path),  # 無 artifact
        })
        data = json.loads(result[0].text)
        assert "error" in data
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_tools.py -k Seam -v`
Expected: 3 FAIL

- [ ] **Step 3: 改 `_validate_output`**

```python
    async def _validate_output(self, arguments: dict):
        llm_output = arguments.get("llm_output", {})
        structure_json = arguments.get("structure_json")
        codebase_path = arguments.get("codebase_path")
        try:
            if structure_json is None and codebase_path:
                gz = (Path(codebase_path) / ".the-door" / "structure-view"
                      / "structure.full.json.gz")
                if gz.is_file():
                    with gzip.open(gz, "rt", encoding="utf-8") as f:
                        structure_json = json.load(f)
            if structure_json is None:
                return [TextContent(type="text", text=json.dumps({
                    "error": "no structure_json given and no structure-view artifact found; "
                             "run extract_structure first or pass structure_json"}))]
            validator = OutputValidator()
            result = validator.validate(llm_output, structure_json)
            output = {
                "passed": result.passed,
                "schema": {"passed": result.schema_result.passed, "errors": result.schema_result.errors},
                "coverage": {"passed": result.coverage_result.passed, "errors": result.coverage_result.errors},
                "language": {"passed": result.language_result.passed, "errors": result.language_result.errors},
                "anchor": {"passed": result.anchor_result.passed, "errors": result.anchor_result.errors},
                "relation": {"passed": result.relation_result.passed, "errors": result.relation_result.errors},
            }
            return [TextContent(type="text", text=json.dumps(output))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
```

server.py 頂部補 `import gzip`（若無）。

`_build_tools()` 的 validate_output schema（server.py:49 附近）：`required` 從 `["llm_output", "structure_json"]` 改 `["llm_output"]`；properties 加：

```python
"codebase_path": {
    "type": "string",
    "description": "省略 structure_json 時，從 <codebase_path>/.the-door/structure-view/structure.full.json.gz 讀結構（extract_structure 已落檔）。",
},
```

並在 structure_json 的 description 補一句「優先於 codebase_path」。

- [ ] **Step 4: 跑測試確認通過**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/unit/mcp/test_tools.py -v`
Expected: 全 passed

- [ ] **Step 5: Commit**

```bash
git add the_door/src/the_door/mcp/server.py the_door/tests/unit/mcp/test_tools.py
git commit -m "feat(mcp): validate_output 可從 structure-view artifact 取結構（codebase_path 可選參數）"
```

---

### Task 7: 文件同步（CLAUDE.md＋.kiro design）

**Files:**
- Modify: `CLAUDE.md`（外層 root）「Agent-as-LLM chain (single version)」步驟 1
- Modify: `.kiro/specs/incremental-analysis/design.md`（extract_structure schema 段）

- [ ] **Step 1: CLAUDE.md 步驟 1 替換**

原文（「### Agent-as-LLM chain (single version)」下第 1 點）：

```
1. `extract_structure(codebase_path="./my-project")`
   → Returns `files`, `nodes`, `edges`, `topology`, `analyzed_files`.
```

替換為：

```
1. `extract_structure(codebase_path="./my-project")`
   → Returns an **L0 index** (not the full structure): `totals`, `regions[]`
   (each with node_count / share % / edge flow / batches / `peel` label with
   evidence / `artifact_path`), and a `consumption_guide`. Full
   nodes/edges/topology land in `.the-door/structure-view/` artifacts:
   - Read the index first. Regions labeled `peel: one_way_consumer` (e.g.
     test code) are structurally peripheral — judge from the attached evidence
     (flow counts) whether to skip them for L1 derivation; the data stays on
     disk, nothing is filtered.
   - Drill down per region: `regions/<region_id>.json.gz` holds per-node L2
     views (attrs + in/out edges keyed `from_node_id`/`to_node_id` + topology
     + residue counts) — use these views instead of joining raw lists yourself.
   - Consume in `batch_assignment` order (batch 1 = entry points, 2..5 by
     descending in_degree) to plan reading.
   - `validate_output` no longer needs the structure inline: pass
     `codebase_path` and it reads `structure.full.json.gz` itself.
```

同檔「Commands & MCP tool reference」表裡 `extract_structure` 那列的 Use when 文字改為：

```
Agent-as-LLM: get the L0 region index + drill-down artifacts, then YOU produce L1.
```

- [ ] **Step 2: .kiro design 同步**

`.kiro/specs/incremental-analysis/design.md` 內 extract_structure 的 output schema 段（grep `extract_structure` 定位），把輸出描述改為 L0 索引形狀（鍵：`totals`/`regions`/`artifact_dir`/`full_structure_path`/`consumption_guide`），並註明全量結構移至 `.the-door/structure-view/structure.full.json.gz`、validate_output 新增可選 `codebase_path`。保持該文件既有格式。

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md .kiro/specs/incremental-analysis/design.md
git commit -m "docs: agent-as-LLM 鏈步驟 1 改 L0 索引消費法+validate_output 接縫"
```

---

### Task 8: 自己驗自己整合測試（F-b characterization＋索引尺寸）

**Files:**
- Test: `the_door/tests/integration/test_structure_view_self.py`

- [ ] **Step 1: 寫測試（直接寫，本 task 為 characterization，紅燈即 bug）**

```python
"""structure_view 對 the_door 自身的 characterization（spec §5.1-4/5）。

對象＝src/the_door（production 子樹；node_id 相對其根，如
"mcp/tools/_response_envelope.py::wrap"）。單次抽取共用 module fixture。
"""
import json
from pathlib import Path

import pytest

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.llm.edge_projection import project_edges_for_prompt
from the_door.core.structure_view.structure_index import write_artifacts
from the_door.core.topology.topology_analyzer import TopologyAnalyzer
from the_door.models import StructureJSON

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "the_door"
_WRAP = "mcp/tools/_response_envelope.py::wrap"


@pytest.fixture(scope="module")
def self_index(tmp_path_factory):
    result = ASTExtractor().extract(str(_SRC_ROOT))
    topology = TopologyAnalyzer().analyze(result.nodes, result.edges)
    structure = StructureJSON(files=result.files, nodes=result.nodes,
                              edges=result.edges, topology=topology.entries)
    edge_dicts = [{"from": e.from_node, "to": e.to_node, "type": e.type,
                   "resolution": e.resolution} for e in result.edges]
    _, residue = project_edges_for_prompt(edge_dicts)
    out = tmp_path_factory.mktemp("selfview")
    return write_artifacts(str(out), structure, residue), out


def test_wrap_out_edges_preassembled_no_manual_join(self_index):
    """F-b characterization：查 wrap 的出邊必須零 join 直接可得（含鏈式建構子+別名匯入）。"""
    import gzip
    index, out = self_index
    mcp_entry = next(r for r in index["regions"] if r["region_id"] == "mcp")
    with gzip.open(mcp_entry["artifact_path"], "rt", encoding="utf-8") as f:
        region = json.load(f)
    wrap_view = next(n for n in region["nodes"] if n["node_id"] == _WRAP)
    targets = {e["to_node_id"] for e in wrap_view["out_edges"]}
    assert "core/guidance/verification_guidance.py::verification_guidance" in targets  # 直呼
    assert "core/guidance/state.py::inspect" in targets          # 鏈式建構子呼叫
    assert "core/guidance/actions.py::to_json_dict" in targets   # 別名匯入
    assert wrap_view["topology"]["out_degree"] == len(wrap_view["out_edges"])  # 跨軸一致


def test_index_stays_index_sized(self_index):
    """spec §5.1-5：對自身，index.json < 32KB（釘『回應＝索引尺寸』承諾）。"""
    index, out = self_index
    size = (out / ".the-door" / "structure-view" / "index.json").stat().st_size
    assert size < 32 * 1024, f"index.json {size} bytes — 索引膨脹，違反 L0 承諾"
```

- [ ] **Step 2: 跑測試**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest tests/integration/test_structure_view_self.py -v`
Expected: 2 passed（自身抽取一次約 10–30s，module fixture 共用）。
若 `out_degree == len(out_edges)` 不等：先查是否 edges 含重複型別（calls+imports 同對端）而 topology 只計 calls——以實際計數規則為準改斷言並在測試註解記錄規則，**不得**改生產碼遷就測試。

- [ ] **Step 3: 全套基線**

Run: `cd the_door && PYTHONUTF8=1 python -m pytest`
Expected: ≥1460 passed / 0 failed（基線 1460+本計畫新增；43 skipped / 1 xfailed 照舊；`test_round_trip_preserves_all_records` 偶發 Hypothesis deadline flake 重跑即過）

- [ ] **Step 4: Commit**

```bash
git add the_door/tests/integration/test_structure_view_self.py
git commit -m "test(structure-view): 自己驗自己 characterization（F-b 零 join+索引尺寸）"
```

---

### Task 9: 消費層驗收（§5.2，非 pytest——由主 agent 執行）

**這個 task 不是給 subagent 的**；實作全部完成、ff-merge 回 main（聽使用者指示）並 `pip install -e ./the_door`＋重啟 MCP host app 之後，由主 agent 親自跑：

- [ ] **Step 1: 重裝＋重啟確認**：`pip install -e ./the_door` 後重啟 host app；呼叫任一 MCP 工具確認回應帶 `verification_guidance`（佐證 live server 已是新碼——2026-06-12 spike 發現舊裝沒有）。
- [ ] **Step 2: 重跑同一翻譯任務**：對 `the_door/` 走 `extract_structure` → 只憑索引＋下鑽產 verification-guidance 功能的 L1 描述。
- [ ] **Step 3: 對照基線逐項回報**（基線＝spec §1 F-a..F-d）：
  - F-a：首口（索引）實際字元數；是否仍需「吃到撐再切片」。
  - F-b：查 `wrap` 出邊是否從 L2 視圖直接取得、零手工 join。
  - F-c：是否僅讀撥離標示＋證據即裁決跳過 tests 區（不取其內容）。
  - F-d：batch_assignment 是否經 `consumption_guide`＋`batches` 可見可用。
- [ ] **Step 4: 效力總評**：對「翻譯更正確/更省」給分級信心＋攤開理由；單樣本誠實界線照 spec §5.2（不升格通用、不以單樣本否定）。結果寫成 `docs/superpowers/specs/2026-06-12-stereoscopic-structure-acceptance.md`。

---

## Self-review 記錄（寫完計畫後自查）

- Spec 覆蓋：§4.1 四模組→Task 1–4；§4.2 兩接縫→Task 5–6；§4.4 文件→Task 7；§5.1 七項結構驗證→Task 1–6 各測試＋Task 8（第 5/4 項）＋Task 8 Step 3（第 8 項全綠）；§5.2 消費層→Task 9。§4.3「不做」清單無對應 task＝正確（不做）。
- 佔位符掃描：無 TBD/TODO；Task 2 Step 3 與 Task 8 Step 2 的「以實際為準改測試」附了精確判斷規則與禁止事項，非開放式佔位。
- 型別一致：`write_artifacts(codebase_path, structure, residue)` 三處呼叫簽名一致；`Region` 欄位名 Task 1/2/4 一致；L2 view 鍵 Task 3/8/CLAUDE.md 一致（`to_node_id`/`from_node_id`/`residue_as_caller`）。
