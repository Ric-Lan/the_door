// Mindmap badge utilities — single source of truth for diff badge config

export const DIFF_BADGE = {
  added:              { fill: '#d4edda', stroke: '#28a745', color: '#1d6e34', text: '+ 新增' },
  removed:            { fill: '#f8d7da', stroke: '#dc3545', color: '#9a1a1a', text: '− 移除' },
  attribute_changed:  { fill: '#ffe0cc', stroke: '#fd7e14', color: '#7a4e00', text: '~ 修改' },
  dependency_changed: { fill: '#ffe0cc', stroke: '#fd7e14', color: '#7a4e00', text: '≠ 依賴' },
};

/**
 * Returns the badge config for the given node in diffNodes, or null if not found/unknown type.
 */
export function selectDiffBadge(nodeId, diffNodes) {
  const entry = (diffNodes ?? []).find(d => d.id === nodeId);
  if (!entry) return null;
  return DIFF_BADGE[entry.change_type] ?? null;
}
