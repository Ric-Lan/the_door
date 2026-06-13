"""structure_view 對 the_door 自身的 characterization（spec §5.1-4/5）。

對象＝src/the_door（production 子樹；node_id 相對其根，如
"mcp/tools/_response_envelope.py::wrap"）。單次抽取共用 module fixture。
"""
import gzip
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
    # start_line / end_line 磁碟層驗證（gzip region 檔含新欄位）
    assert "start_line" in wrap_view, "start_line missing from gzip region artifact"
    assert wrap_view["start_line"] is not None, "start_line should be populated from tree-sitter"


def test_index_stays_index_sized(self_index):
    """spec §5.1-5：對自身，index.json < 32KB（釘『回應＝索引尺寸』承諾）。"""
    index, out = self_index
    size = (out / ".the-door" / "structure-view" / "index.json").stat().st_size
    assert size < 32 * 1024, f"index.json {size} bytes — 索引膨脹，違反 L0 承諾"
