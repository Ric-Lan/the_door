"""Chunk Merge: 收齊各 chunk 的 features，從結構邊決定性推導 static relations，
組裝成可寫入 snapshot_write 的 payload。唯讀（讀 structure-view）、不寫 snapshot。

subagent 只產 features；relations 全由本模組從結構邊推導（CLAUDE.md 閘門：
結構性分析走純程式）。spec: docs/superpowers/specs/2026-06-23-chunk-dispatch-merge-design.md
"""
from __future__ import annotations

from the_door.core.structure_view.locator import load_views  # noqa: F401 (used in merge)


class ChunkMergeError(Exception):
    """合併的可預期錯誤（重複 feature_id、缺欄位、空 chunks）。"""


def _collect_features(chunks: list) -> list:
    """Union 所有 chunk 的 features；feature_id 跨塊重複 → ChunkMergeError。"""
    features: list = []
    seen: dict = {}
    for ch in chunks:
        cid = ch.get("chunk_id")
        for f in ch.get("features", []) or []:
            fid = f.get("feature_id")
            if not fid:
                raise ChunkMergeError(
                    f"feature missing feature_id (chunk {cid!r})")
            if fid in seen:
                raise ChunkMergeError(
                    f"duplicate feature_id {fid!r} (chunks {seen[fid]!r} and {cid!r}); "
                    f"feature_id must be chunk-namespaced and globally unique")
            seen[fid] = cid
            features.append(f)
    return features


def _node_to_feature(features: list) -> tuple[dict, list]:
    """{node_id: feature_id}。一節點被多 feature 認領 → 取 feature_id 字典序首者
    （決定性）並記 warning。回 (mapping, sorted_warnings)。"""
    mapping: dict = {}
    warnings: set = set()
    # 按 feature_id 升冪迭代 → 先到先得＝字典序首者得標
    for f in sorted(features, key=lambda x: x["feature_id"]):
        fid = f["feature_id"]
        for nid in f.get("source_nodes", []) or []:
            if nid in mapping:
                if mapping[nid] != fid:
                    warnings.add(nid)
                continue
            mapping[nid] = fid
    return mapping, sorted(warnings)


def _derive_relations(views: dict, node_to_feature: dict) -> tuple[list, int]:
    """從結構邊推導 feature 層 static relations。
    對每條 out_edge u→v：兩端皆有 feature 且不同 → relation(邊型別, static)。
    按 (from,to,relation) 聚合去重。端點缺 feature 的邊 → skip + 計數。
    回 (sorted_relations, skipped_count)。"""
    seen: set = set()
    relations: list = []
    skipped = 0
    for nid, view in views.items():
        ffrom = node_to_feature.get(nid)
        for e in view.get("out_edges", []) or []:
            fto = node_to_feature.get(e.get("to_node_id"))
            if ffrom is None or fto is None:
                skipped += 1
                continue
            if ffrom == fto:
                continue  # intra-feature，非 feature relation
            rel = e.get("type", "calls")
            key = (ffrom, fto, rel)
            if key in seen:
                continue
            seen.add(key)
            relations.append({"from_feature": ffrom, "to_feature": fto,
                              "relation": rel, "relation_type": "static"})
    relations.sort(key=lambda r: (r["from_feature"], r["to_feature"], r["relation"]))
    return relations, skipped
