// Shared DOM render for phasebar + steplist + prog-live.
// Consumed by ui-wizard.js (精靈 PROGRESS) and ui-modal.js (Viewer 重新分析 modal).
// Spec §5.3 / §5.4 / §7.

import { PHASE_BUCKETS, phaseStatus, labelFor } from './phase-status.js';

const STEPS_CANONICAL = ['analyze_old', 'analyze_new', 'diff', 'scope_verify', 'timeline', 'report'];

/**
 * Returns innerHTML string for the phasebar + steplist + (optional) prog-live.
 * Pure function — no DOM mutation; caller decides where to mount.
 */
export function renderProgressInnerHTML({ steps, currentStep, progress }) {
  const stepsByName = new Map((steps || []).map(s => [s.step_name, s]));
  const fullSteps = STEPS_CANONICAL.map(name =>
    stepsByName.get(name) || { step_name: name, status: 'pending' });

  const phasebarHTML = PHASE_BUCKETS.map(bucket => {
    const st = phaseStatus(bucket, fullSteps, currentStep);
    const icon = st === 'done' ? '✓ ' : st === 'failed' ? '✗ ' : '';
    return `<div class="wizard-phase ${st}"><div class="track"><div class="fill"></div></div><div class="pl">${icon}${bucket.label}</div></div>`;
  }).join('');

  const rowsHTML = fullSteps.map(s => {
    const icon = s.status === 'completed' ? '✓'
      : s.status === 'failed'  ? '✗'
      : s.status === 'skipped' ? '⊘'
      : s.status === 'running' ? '<span class="wizard-spin"></span>'
      : '○';
    const dur = s.duration_ms != null ? `${(s.duration_ms / 1000).toFixed(1)}s` : '';
    const err = s.error_message ? `<span class="wizard-sl-err">${s.error_message}</span>` : '';
    return `<div class="wizard-sl-row ${s.status}" data-step-status="${s.status}">`
         + `<span class="si">${icon}</span><span class="sn">${labelFor(s.step_name)}</span>${err}<span class="dur">${dur}</span></div>`;
  }).join('');

  const progLiveHTML = progress ? `
    <div class="wizard-prog-live">
      <div class="wizard-pl-head">
        <span class="wizard-pl-dot"></span>
        正在分析 <span class="wizard-pl-count">${progress.files_done} / ${progress.files_total}</span> 個檔案
      </div>
      <div class="wizard-pl-feed"></div>
    </div>` : '';

  return `
    <div class="wizard-phasebar">${phasebarHTML}</div>
    <div class="wizard-steplist">${rowsHTML}</div>
    ${progLiveHTML}
  `;
}

/**
 * Append a file path line into the most recent .wizard-pl-feed within `scope`
 * (defaults to document). No-op if no feed exists. Trims to ≤20 lines.
 */
export function appendPlLine(filePath, scope = document) {
  const feed = scope.querySelector('.wizard-pl-feed');
  if (!feed) return;
  const line = document.createElement('div');
  line.className = 'wizard-pl-line';
  line.textContent = filePath;
  feed.appendChild(line);
  while (feed.children.length > 20) feed.removeChild(feed.firstChild);
}

/**
 * Update the .wizard-pl-count text within `scope`. No-op if absent.
 */
export function updateProgressCount(done, total, scope = document) {
  const cnt = scope.querySelector('.wizard-pl-count');
  if (cnt) cnt.textContent = `${done} / ${total}`;
}
