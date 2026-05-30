// Pure helpers for PROGRESS phasebar (spec §5.3).
// No DOM access — safe for unit tests under jsdom or node.

export const PHASE_BUCKETS = [
  { id: 'explore', label: '探索結構', steps: ['analyze_old', 'analyze_new'] },
  { id: 'analyze', label: '比對與驗核', steps: ['diff', 'scope_verify'] },
  { id: 'report',  label: '產出快照',   steps: ['timeline', 'report'] },
];

export const STEP_LABELS = {
  analyze_old:  '分析舊版',
  analyze_new:  '分析新版',
  diff:         '比對差異',
  scope_verify: '範圍驗核',
  timeline:     '時間軸',
  report:       '產生報告',
};

export function labelFor(step_name) {
  return STEP_LABELS[step_name] ?? step_name;
}

/**
 * Returns 'done' | 'active' | 'pending' | 'failed' for a bucket.
 * 'failed' has highest priority (spec §0.4 第 1 條：不可造假進度).
 */
export function phaseStatus(bucket, steps, currentStep) {
  const owned = steps.filter(s => bucket.steps.includes(s.step_name));
  if (owned.length === 0) return 'pending';
  if (owned.some(s => s.status === 'failed')) return 'failed';
  const hasRunning = owned.some(s => s.status === 'running');
  const currentInBucket = currentStep && bucket.steps.includes(currentStep);
  if (hasRunning || currentInBucket) return 'active';
  const allEnded = bucket.steps.every(name => {
    const s = owned.find(x => x.step_name === name);
    return s && (s.status === 'completed' || s.status === 'skipped');
  });
  return allEnded ? 'done' : 'pending';
}
