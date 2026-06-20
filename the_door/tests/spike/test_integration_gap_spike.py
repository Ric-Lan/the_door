"""整合落差驗證 spike。

對照 spec §6 閘門：
- test_three_way_verdict_matches_reality → G2 真陽性 + G3 假陽性
- test_relationcheck_alone_cannot_three_way → 設計輸入（RelationCheck 無法三態）

非循環性（G4）：本測試的宣稱清單對應 tests/spike/claims.md，該檔在抽取前已 commit。
"""
from pathlib import Path

from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.validation.relation_check import RelationCheck

FIXTURE = Path(__file__).parent / "fixtures" / "broken_integration"


def _extract():
    result = ASTExtractor().extract(str(FIXTURE))
    nodes = [n.node_id for n in result.nodes]
    edges = [{"from": e.from_node, "to": e.to_node} for e in result.edges]
    return nodes, edges


def _adjacency(edges):
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], set()).add(e["to"])
    return adj


def _in_file(nodes, filename):
    """node_id 真實格式為 '{file.path}::{name}'，以檔名（:: 左側 path 段）比對。"""
    return {n for n in nodes if n.split("::", 1)[0].endswith(filename)}


REDIS_EXTERNAL = {"redis_cache.py::RedisCache.get", "redis_cache.py::RedisCache.set"}


def _classify(from_nodes, claimed_to_nodes, graph_nodes, adjacency):
    present = set(claimed_to_nodes) & set(graph_nodes)
    if not present:
        return "undetermined"  # 被依賴方不是程式碼節點
    if RelationCheck()._has_path(set(from_nodes), present, adjacency):
        return "backed"
    return "gap"


def test_three_way_verdict_matches_reality():
    nodes, edges = _extract()
    adj = _adjacency(edges)

    db = _in_file(nodes, "db.py")
    user = _in_file(nodes, "user_service.py")
    order = _in_file(nodes, "order_service.py")
    report = _in_file(nodes, "report_service.py")
    auth = _in_file(nodes, "auth_service.py")

    assert db and user and order and report and auth, f"extractor 漏抽節點: {sorted(nodes)}"

    assert _classify(user, db, nodes, adj) == "gap"
    assert _classify(order, db, nodes, adj) == "backed"
    assert _classify(report, db, nodes, adj) == "backed"
    assert _classify(auth, db, nodes, adj) == "backed"
    assert _classify(user, REDIS_EXTERNAL, nodes, adj) == "undetermined"


def test_relationcheck_alone_cannot_three_way():
    nodes, edges = _extract()
    structure_json = {"edges": edges}
    llm_output = {
        "l1": {
            "features": [
                {"feature_id": "feat-user", "source_nodes": list(_in_file(nodes, "user_service.py"))},
                {"feature_id": "feat-db", "source_nodes": list(_in_file(nodes, "db.py"))},
                {"feature_id": "feat-redis", "source_nodes": ["redis_cache.py::RedisCache.get"]},
            ],
            "feature_relations": [
                {"from": "feat-user", "to": "feat-db", "relation_type": "static"},
                {"from": "feat-user", "to": "feat-redis", "relation_type": "static"},
            ],
        }
    }
    result = RelationCheck().check(llm_output, structure_json)
    assert not result.passed
    assert len(result.errors) == 2
