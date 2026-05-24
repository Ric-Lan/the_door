import { state } from './state.js';
import { els } from './dom.js';

function snapshotLabel(snapshot) {
  if (snapshot.git_tags?.length) return snapshot.git_tags[0];
  if (snapshot.label) return snapshot.label;
  return snapshot.timestamp?.slice(0, 16).replace('T', ' ') ?? '（無時間）';
}

export function renderTopBar() {
  const um = state.updateModel;
  const hasDiff = um?.diff_available === true;
  const hasVersionCompare = !!(state.versionA && state.versionB && state.versionA !== state.versionB);

  const modeSwitch = document.querySelector('.mode-switch');
  if (modeSwitch) {
    modeSwitch.hidden = !hasDiff && !hasVersionCompare;
  }

  if (hasDiff) {
    els.summaryText.textContent = um?.summary || '（無摘要）';
  } else if (state.l1Model) {
    const fc = state.l1Model.stats?.feature_count ?? state.l1Model.features?.length ?? 0;
    const vId = state.mode === 'baseline' ? state.versionA : state.versionB;
    const snap = state.snapshots.find(s => s.version_id === vId);
    const label = snap ? snapshotLabel(snap) : null;
    els.summaryText.textContent = label
      ? `${label} · 共 ${fc} 個功能`
      : `共 ${fc} 個功能`;
  } else {
    els.summaryText.textContent = '（載入中…）';
  }

  els.btnDiff.classList.toggle('active', state.mode === 'diff');
  els.btnBaseline.classList.toggle('active', state.mode === 'baseline');
  els.btnCurrent.classList.toggle('active', state.mode === 'current');

  const snapA = state.snapshots.find(s => s.version_id === state.versionA);
  const snapB = state.snapshots.find(s => s.version_id === state.versionB);
  els.btnBaseline.textContent = snapA ? snapshotLabel(snapA) : '版本 A';
  els.btnCurrent.textContent  = snapB ? snapshotLabel(snapB) : '版本 B';

  els.btnDiff.disabled = !hasDiff && !hasVersionCompare;

  if ((hasDiff || hasVersionCompare) && state.mode === 'diff') {
    const vd = state.versionDiff?.summary;
    const cc = (vd && (vd.total_changed ?? 0) > 0) ? vd : (um?.change_counts || {});
    const rc = um?.risk_counts || {};

    els.countAdded.removeAttribute('hidden');
    els.countRemoved.removeAttribute('hidden');
    els.countModified.removeAttribute('hidden');
    els.countAdded.textContent    = '新增 ' + (cc.added   ?? 0);
    els.countRemoved.textContent  = '移除 ' + (cc.removed  ?? 0);
    const modified = (cc.attribute_changed ?? 0) + (cc.dependency_changed ?? 0);
    els.countModified.textContent = '修改 ' + modified;

    const totalRisk = Object.values(rc).reduce((a, b) => a + b, 0);
    if (totalRisk > 0) {
      els.countRisk.textContent = '注意 ' + totalRisk;
      els.countRisk.removeAttribute('hidden');
    } else {
      els.countRisk.setAttribute('hidden', '');
    }
  } else {
    const fc = state.l1Model?.stats?.feature_count ?? state.l1Model?.features?.length ?? 0;
    els.countAdded.textContent = fc ? fc + ' 功能' : '';
    els.countRemoved.setAttribute('hidden', '');
    els.countModified.setAttribute('hidden', '');
    els.countRisk.setAttribute('hidden', '');
  }
}

export function renderSummaryText(mode, state) {
  if (mode === 'diff') {
    return { tag: null, text: state.updateModel?.summary ?? '尚未有分析報告。' };
  }
  const id = mode === 'baseline' ? state.versionA : state.versionB;
  const label = state.snapshots.find(s => s.version_id === id)?.label ?? '—';
  const count = state.l1Model?.features?.length ?? 0;
  return { tag: label, text: `${label} 共有 ${count} 個 L1 功能。` };
}

export function modeSwitchLabel(mode, versionA, versionB, snapshots) {
  if (mode === 'diff') return '差異';
  const id = mode === 'baseline' ? versionA : versionB;
  const tag = mode === 'baseline' ? 'A' : 'B';
  const label = snapshots.find(s => s.version_id === id)?.label ?? '—';
  return `版本 ${tag} · ${label}`;
}

export function resolveLogoState(mode, layerState) {
  if (layerState === 'L3') return 'l3';
  if (mode === 'diff')      return 'diff';
  if (mode === 'current')   return 'l2';
  if (mode === 'baseline')  return 'l1';
  return 'l1';
}

export function updateLogoMark() {
  const img = document.getElementById('logo-mark');
  if (!img) return;
  let next = 'l1';
  if (state.mode === 'diff' && (state.updateModel?.diff_available || state.versionDiff)) {
    next = 'diff';
  } else if (state.layerState === 'L3') {
    next = 'l3';
  } else if (state.layerState === 'L2') {
    next = 'l2';
  }
  if (img.dataset.state === next) return;
  img.dataset.state = next;
  img.setAttribute('src', `./assets/mark-${next}.svg`);
}
