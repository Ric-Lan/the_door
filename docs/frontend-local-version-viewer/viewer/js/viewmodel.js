export function buildViewModelFromReport(report) {
  const l1Changes = report.l1_changes || [];
  const l2Details = report.l2_details || [];
  const diffAvailable = l1Changes.length > 0;

  const detailsMap = {};
  l2Details.forEach((d) => {
    detailsMap[d.feature_id] = {
      id: d.feature_id,
      change_type: d.change_type,
      before: {
        label: d.baseline_label || "未提供",
        description: d.baseline_description || "未提供",
      },
      after: {
        label: d.current_label || "未提供",
        description: d.current_description || "未提供",
      },
      scope_state: d.scope_state || null,
      related_vulnerabilities: d.related_vulnerabilities || [],
      affected_relations: d.affected_relations || [],
      source: "UpdateReport.l2_details",
    };
  });

  l1Changes.forEach((c) => {
    if (!detailsMap[c.feature_id]) {
      detailsMap[c.feature_id] = {
        id: c.feature_id,
        change_type: c.change_type,
        before: { label: "未提供", description: "未提供" },
        after: { label: c.current_label || "未提供", description: "未提供" },
        scope_state: null,
        related_vulnerabilities: [],
        affected_relations: [],
        source: "UpdateReport.l1_changes",
      };
    }
  });

  const changeCounts = { added: 0, removed: 0, attribute_changed: 0, dependency_changed: 0 };
  const riskCounts = { out_of_scope: 0, vulnerability: 0, semantic_drift: 0 };
  l1Changes.forEach((c) => {
    if (c.change_type in changeCounts) changeCounts[c.change_type]++;
    (c.risk_flags || []).forEach((f) => { if (f in riskCounts) riskCounts[f]++; });
  });

  const changes = l1Changes.map((c) => ({
    id: c.feature_id,
    label: c.current_label || c.baseline_label || c.feature_id,
    change_type: c.change_type,
    risk_flags: c.risk_flags || [],
    current_label: c.current_label || null,
    baseline_label: c.baseline_label || null,
    source: "UpdateReport.l1_changes",
  }));

  return {
    mode: "update-report",
    diff_available: diffAvailable,
    summary: report.l0_summary || "（無摘要）",
    change_counts: changeCounts,
    risk_counts: riskCounts,
    changes,
    details: detailsMap,
    interrupted: report.interrupted || false,
    source: "UpdateReport",
  };
}

export function buildL1ViewModelFromStatic(graphData) {
  const nodes = graphData.nodes || [];
  return {
    features: nodes.map((n) => ({
      id: n.id,
      label: n.label,
      confidence: n.confidence,
      description: n.description,
      trigger_description: n.trigger_description,
      source: "L1Output.features",
    })),
    stats: { feature_count: nodes.length },
  };
}

// provenance 後綴只標非 current（誠實 surface 跨契約/無戳；current 不加字＝避免每項都掛雜訊）
const PROVENANCE_SUFFIX = { legacy: "（舊契約）", unknown: "（無契約戳）" };

export function snapshotLabel(snapshot) {
  if (!snapshot) return "（未知）";
  const base =
    snapshot.git_tags?.length ? snapshot.git_tags[0]
    : snapshot.label ? snapshot.label
    : snapshot.timestamp?.slice(0, 16).replace("T", " ") ?? "（無時間）";
  return base + (PROVENANCE_SUFFIX[snapshot.provenance] ?? "");
}
