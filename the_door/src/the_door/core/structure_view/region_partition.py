"""區域分割：按 node_id 路徑頂層段聚類，計算跨區流向矩陣。

純結構計算、決定性、零路徑名寫死。退化案例（單一頂層段）＝1 區、
零撥離訊號＝誠實輸出（spec §4.1 明令不得自行加第二層聚類）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from the_door.models import ASTNode, Edge

_ROOT_BUCKET = "_root_"  # 無 "/" 的 node_id（root 層檔案）之 fs-safe 桶名


@dataclass(frozen=True)
class Region:
    """一個路徑頂層段區域與其邊界流量。"""

    region_id: str
    node_ids: tuple[str, ...]          # 已排序
    internal_edges: int
    inbound_edges: int                 # 他區 -> 本區 總計
    outbound_edges: int                # 本區 -> 他區 總計
    flow_to: dict[str, int] = field(default_factory=dict)    # 鄰區 -> 邊數（本區為 from）
    flow_from: dict[str, int] = field(default_factory=dict)  # 鄰區 -> 邊數（本區為 to）


def region_of(node_id: str) -> str:
    """node_id 的路徑頂層段；無 '/' → _ROOT_BUCKET。"""
    return node_id.split("/", 1)[0] if "/" in node_id else _ROOT_BUCKET


def partition(nodes: list[ASTNode], edges: list[Edge]) -> list[Region]:
    """分割節點為區域並計數三向邊流。輸出按 region_id 排序（決定性）。"""
    members: dict[str, list[str]] = {}
    for n in nodes:
        members.setdefault(region_of(n.node_id), []).append(n.node_id)

    internal: dict[str, int] = {}
    flow: dict[tuple[str, str], int] = {}  # (from_region, to_region) -> count，僅跨區
    for e in edges:
        fr, to = region_of(e.from_node), region_of(e.to_node)
        if fr == to:
            internal[fr] = internal.get(fr, 0) + 1
        else:
            flow[(fr, to)] = flow.get((fr, to), 0) + 1

    regions: list[Region] = []
    for rid in sorted(members):
        flow_to = {to: c for (fr, to), c in sorted(flow.items()) if fr == rid}
        flow_from = {fr: c for (fr, to), c in sorted(flow.items()) if to == rid}
        regions.append(Region(
            region_id=rid,
            node_ids=tuple(sorted(members[rid])),
            internal_edges=internal.get(rid, 0),
            inbound_edges=sum(flow_from.values()),
            outbound_edges=sum(flow_to.values()),
            flow_to=flow_to,
            flow_from=flow_from,
        ))
    return regions
