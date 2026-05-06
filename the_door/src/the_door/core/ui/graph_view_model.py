"""GraphViewModel_Converter — Pure functions for converting core outputs to graph ViewModels.

Phase UI-3 Interactive Graph.

All functions are pure (no side effects, no state) and return dict (not dataclass)
for direct JSON serialization.

ViewModel formats:

L1_Graph_ViewModel:
{
  "nodes": [{"id": str, "label": str, "confidence": str,
             "description": str, "trigger_description": str | None}],
  "edges": [{"source": str, "target": str, "relation": str}],
  "warnings": [str]
}

L2_Graph_ViewModel:
{
  "nodes": [{"id": str, "label": str, "confidence": str, "source_nodes": list[str]}],
  "edges": [{"source": str, "target": str, "description": str, "relation_type": str}],
  "anomalies": [{"anomaly_type": str, "affected_node_ids": list[str],
                 "explanation": str, "confidence": str}],
  "warnings": [str]
}

L3_Graph_ViewModel:
{
  "nodes": [{"id": str, "label": str, "type": str, "file": str}],
  "edges": [{"source": str, "target": str, "type": str}],
  "warnings": [str]
}

Diff_Graph_ViewModel:
{
  "nodes": [{"id": str, "label": str, "change_type": str,
             "current_label": str | None, "baseline_label": str | None,
             "current_description": str | None, "baseline_description": str | None,
             "risk_flags": list[str]}],
  "edges": [{"source": str, "target": str, "diff_state": str}],
  "warnings": [str]
}
"""
from __future__ import annotations

import difflib

from the_door.models import L1Output, L2Output, StructureJSON


def build_l1_graph_view_model(l1_output: L1Output) -> dict:
    """Convert L1Output to L1_Graph_ViewModel.

    - Nodes: one per Feature in l1_output.features
    - Edges: one per FeatureRelation in l1_output.feature_relations
    - Dangling edges (referencing unknown feature_id) are omitted; warning recorded.
    - trigger_description comes from Feature.trigger_description.

    Returns dict with keys: nodes, edges, warnings.
    """
    # Build node set
    feature_ids = {f.feature_id for f in l1_output.features}
    nodes = [
        {
            "id": f.feature_id,
            "label": f.label,
            "confidence": f.confidence,
            "description": f.description,
            "trigger_description": f.trigger_description,
        }
        for f in l1_output.features
    ]

    # Build edges, omitting dangling references
    edges = []
    warnings = []
    for rel in l1_output.feature_relations:
        if rel.from_feature not in feature_ids or rel.to_feature not in feature_ids:
            warnings.append(
                f"Dangling edge omitted: from={rel.from_feature} to={rel.to_feature}"
            )
            continue
        edges.append(
            {
                "source": rel.from_feature,
                "target": rel.to_feature,
                "relation": rel.relation,
            }
        )

    return {"nodes": nodes, "edges": edges, "warnings": warnings}


def build_l1_graph_view_model_from_snapshot(
    l1_snapshot: dict,  # dict[str, FeatureSummary-like dict]
    feature_relations_snapshot: list,  # list[RelationSummary-like dict]
) -> dict:
    """Convert VersionSnapshot fields to L1_Graph_ViewModel.

    Used by GET /api/l1 which reads from VersionSnapshot (not L1Output).
    trigger_description is always null (not present in FeatureSummary).

    Returns dict with keys: nodes, edges, warnings.
    """
    # Build node set
    feature_ids = set(l1_snapshot.keys())
    nodes = [
        {
            "id": feature_id,
            "label": summary["label"],
            "confidence": summary["confidence"],
            "description": summary["description"],
            "trigger_description": None,  # FeatureSummary does not have this field
        }
        for feature_id, summary in l1_snapshot.items()
    ]

    # Build edges, omitting dangling references
    edges = []
    warnings = []
    for rel in feature_relations_snapshot:
        from_feature = rel["from_feature"]
        to_feature = rel["to_feature"]
        if from_feature not in feature_ids or to_feature not in feature_ids:
            warnings.append(
                f"Dangling edge omitted: from={from_feature} to={to_feature}"
            )
            continue
        edges.append(
            {
                "source": from_feature,
                "target": to_feature,
                "relation": rel["relation"],
            }
        )

    return {"nodes": nodes, "edges": edges, "warnings": warnings}


def build_l2_graph_view_model(l2_output: L2Output) -> dict:
    """Convert L2Output to L2_Graph_ViewModel.

    - Nodes: one per L2Module in l2_output.modules
    - Edges: one per ModuleInteraction in l2_output.module_interactions
    - Anomalies: all entries from l2_output.anomalies
    - Dangling interactions (referencing unknown module_id) are omitted; warning recorded.

    Returns dict with keys: nodes, edges, anomalies, warnings.
    """
    # Build node set
    module_ids = {m.module_id for m in l2_output.modules}
    nodes = [
        {
            "id": m.module_id,
            "label": m.label,
            "confidence": m.confidence,
            "source_nodes": m.source_nodes,
        }
        for m in l2_output.modules
    ]

    # Build edges, omitting dangling references
    edges = []
    warnings = []
    for interaction in l2_output.module_interactions:
        if (
            interaction.from_module not in module_ids
            or interaction.to_module not in module_ids
        ):
            warnings.append(
                f"Dangling interaction omitted: from={interaction.from_module} to={interaction.to_module}"
            )
            continue
        edges.append(
            {
                "source": interaction.from_module,
                "target": interaction.to_module,
                "description": interaction.description,
                "relation_type": interaction.relation_type,
            }
        )

    # Build anomalies
    anomalies = [
        {
            "anomaly_type": a.anomaly_type,
            "affected_node_ids": a.affected_node_ids,
            "explanation": a.explanation,
            "confidence": a.confidence,
        }
        for a in l2_output.anomalies
    ]

    return {"nodes": nodes, "edges": edges, "anomalies": anomalies, "warnings": warnings}


def build_l3_graph_view_model(
    structure_json: StructureJSON,
    source_node_ids: list[str],
) -> dict:
    """Convert StructureJSON to L3_Graph_ViewModel filtered to source_node_ids.

    - Nodes: ASTNode entries whose node_id is in source_node_ids
    - Edges: Edge entries where both from_node and to_node are in source_node_ids
    - AST nodes not in source_node_ids are excluded.
    - Edges referencing nodes outside source_node_ids are excluded.

    Returns dict with keys: nodes, edges, warnings.
    """
    source_node_set = set(source_node_ids)

    # Build nodes filtered to source_node_ids
    nodes = [
        {
            "id": node.node_id,
            "label": node.name,
            "type": node.type,
            "file": node.file,
        }
        for node in structure_json.nodes
        if node.node_id in source_node_set
    ]

    # Build edges filtered to source_node_ids
    edges = [
        {
            "source": edge.from_node,
            "target": edge.to_node,
            "type": edge.type,
        }
        for edge in structure_json.edges
        if edge.from_node in source_node_set and edge.to_node in source_node_set
    ]

    return {"nodes": nodes, "edges": edges, "warnings": []}


def build_diff_graph_view_model(
    update_report: dict,
    diff_result: dict | None,
) -> dict:
    """Convert UpdateReport dict + DiffResult dict to Diff_Graph_ViewModel.

    - Nodes: derived from update_report["l1_changes"], pre-sorted by risk-first order
             (calls sort_diff_nodes_by_risk internally; Req 10 AC1 default sort)
    - Edges: derived from diff_result["edge_diffs"] where both from_node and to_node
             are present in the changed node set; if diff_result is None, no edges.
    - change_type values: "added" | "removed" | "attribute_changed" | "dependency_changed"

    Returns dict with keys: nodes (risk-first sorted), edges, warnings.
    """
    # Build nodes from l1_changes
    l1_changes = update_report.get("l1_changes", [])
    nodes = [
        {
            "id": change["feature_id"],
            "label": change.get("current_label") or change.get("baseline_label") or "",
            "change_type": change["change_type"],
            "current_label": change.get("current_label"),
            "baseline_label": change.get("baseline_label"),
            "current_description": change.get("current_description"),
            "baseline_description": change.get("baseline_description"),
            "risk_flags": change.get("risk_flags", []),
        }
        for change in l1_changes
    ]

    # Sort nodes by risk-first order (default sort per Req 10 AC1)
    nodes = sort_diff_nodes_by_risk(nodes)

    # Build edges from diff_result (if present)
    edges = []
    if diff_result is not None:
        changed_node_ids = {node["id"] for node in nodes}
        edge_diffs = diff_result.get("edge_diffs", [])
        for edge_diff in edge_diffs:
            from_node = edge_diff["from_node"]
            to_node = edge_diff["to_node"]
            if from_node in changed_node_ids and to_node in changed_node_ids:
                edges.append(
                    {
                        "source": from_node,
                        "target": to_node,
                        "diff_state": edge_diff["diff_state"],
                    }
                )

    return {"nodes": nodes, "edges": edges, "warnings": []}


def sort_diff_nodes_by_risk(nodes: list[dict]) -> list[dict]:
    """Sort diff nodes by risk-first order (pure function, no mutation).

    Order: out_of_scope → vulnerability → semantic_drift → added →
           attribute_changed → dependency_changed → removed.
    Nodes without risk_flags are sorted by change_type only.

    Called by build_diff_graph_view_model to pre-sort nodes in the returned
    Diff_Graph_ViewModel (default sort order per Req 10 AC1).
    Frontend only needs to re-sort when user switches to semantic-diff-first.

    Returns a new sorted list (does not mutate input).
    """

    def _priority(node: dict) -> tuple[int, int]:
        """Return (risk_priority, change_type_priority) for sorting."""
        risk_flags = node.get("risk_flags", [])

        # Risk priority (lower is higher priority)
        if "out_of_scope" in risk_flags:
            risk_priority = 0
        elif "vulnerability" in risk_flags:
            risk_priority = 1
        elif "semantic_drift" in risk_flags:
            risk_priority = 2
        else:
            risk_priority = 3

        # Change type priority (lower is higher priority)
        change_type = node.get("change_type", "")
        change_type_priority = {
            "added": 3,
            "attribute_changed": 4,
            "dependency_changed": 5,
            "removed": 6,
        }.get(change_type, 7)

        return (risk_priority, change_type_priority)

    return sorted(nodes, key=_priority)


def sort_diff_nodes_by_semantic_diff(nodes: list[dict]) -> list[dict]:
    """Sort diff nodes by semantic change magnitude (pure function, no mutation).

    Magnitude = edit_distance(current_label, baseline_label)
              + edit_distance(current_description, baseline_description)
    Edit distance uses difflib.SequenceMatcher ratio converted to character count.
    Nodes with higher magnitude rank first.

    Returns a new sorted list (does not mutate input).
    """

    def _magnitude(node: dict) -> int:
        """Calculate semantic change magnitude for a node."""
        current_label = node.get("current_label")
        baseline_label = node.get("baseline_label")
        current_description = node.get("current_description")
        baseline_description = node.get("baseline_description")

        label_dist = _edit_distance(current_label, baseline_label)
        desc_dist = _edit_distance(current_description, baseline_description)

        return label_dist + desc_dist

    # Sort by magnitude descending (higher magnitude first)
    return sorted(nodes, key=_magnitude, reverse=True)


def _edit_distance(a: str | None, b: str | None) -> int:
    """Compute character-level edit distance between two strings.

    Uses difflib.SequenceMatcher: distance = (1 - ratio) * max(len(a), len(b)).
    None is treated as empty string.
    """
    # Treat None as empty string
    a = a or ""
    b = b or ""

    # Calculate similarity ratio
    ratio = difflib.SequenceMatcher(None, a, b).ratio()

    # Convert to edit distance
    max_len = max(len(a), len(b))
    distance = int(max_len * (1 - ratio))

    return distance
