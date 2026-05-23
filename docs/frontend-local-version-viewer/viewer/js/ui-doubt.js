// Doubts view — status badges + doubt detail rendering

const MAP = {
  open:      { className: 'confidence-badge confidence-badge-low',    label: '未解決' },
  assigned:  { className: 'confidence-badge confidence-badge-medium', label: '處理中' },
  resolved:  { className: 'confidence-badge confidence-badge-high',   label: '已解決' },
  escalated: { className: 'confidence-badge confidence-badge-escalated', label: '已升級' },
};

export function statusBadge(status) {
  return MAP[status] ?? MAP.open;
}

/**
 * Render a doubt detail panel into the given container element.
 * @param {HTMLElement} container
 * @param {object} doubt
 */
export function renderDoubtDetail(container, doubt) {
  if (!doubt) { container.innerHTML = '<p class="no-selection">請選擇一個疑義項目。</p>'; return; }
  const badge = statusBadge(doubt.status);
  container.innerHTML = `
    <div class="doubt-detail">
      <h3 class="doubt-title">${escapeHtml(doubt.title ?? '（無標題）')}</h3>
      <div class="doubt-fields">
        <div class="doubt-field"><span class="field-label">異常類型</span><span>${escapeHtml(doubt.anomaly_type ?? '—')}</span></div>
        <div class="doubt-field"><span class="field-label">說明</span><span>${escapeHtml(doubt.description ?? '—')}</span></div>
        <div class="doubt-field"><span class="field-label">狀態</span><span class="${badge.className}">${badge.label}</span></div>
        <div class="doubt-field"><span class="field-label">指派對象</span><span>${escapeHtml(doubt.assignee ?? '—')}</span></div>
        <div class="doubt-field"><span class="field-label">來源功能</span><span>${escapeHtml(doubt.source_feature ?? '—')}</span></div>
      </div>
    </div>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
