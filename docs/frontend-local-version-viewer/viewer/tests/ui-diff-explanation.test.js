import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { appendDiffExplanationSection } from '../js/ui-diff-explanation.js';
import { state } from '../js/state.js';

const flushPromises = () => new Promise(resolve => setTimeout(resolve, 0));

function makeContainer() {
  return document.createElement('div');
}

function makeExplanation(overrides = {}) {
  return {
    confidence: 'high',
    impact_summary: 'Major performance improvement.',
    possible_purpose: 'Reduce latency.',
    caution: 'Monitor memory usage.',
    linked_resources: [],
    ...overrides,
  };
}

function resetState() {
  state.versionA = 'v1';
  state.versionB = 'v2';
}

beforeEach(() => {
  resetState();
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ explanation: null }),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  state.versionA = null;
  state.versionB = null;
});

// ── structure ─────────────────────────────────────────────────────

describe('appendDiffExplanationSection — structure', () => {
  it('appends section with h3 and content container', async () => {
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const section = container.querySelector('.diff-explanation-section');
    expect(section).not.toBeNull();
    expect(section.querySelector('h3').textContent).toBe('差異推論');
    expect(section.querySelector('.diff-explanation-body')).not.toBeNull();
  });
});

// ── initial load ──────────────────────────────────────────────────

// T5-V (丙案 D1): diff-explanation generation retired — display-only, no generate/regen button.
describe('appendDiffExplanationSection — initial load (display-only)', () => {
  it('shows cached explanation content and NO generate/regen button', async () => {
    const explanation = makeExplanation();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ explanation }),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    expect(body.querySelector('.confidence-badge')).not.toBeNull();
    expect(body.querySelector('.diff-explanation-generate-btn')).toBeNull();
  });

  it('shows empty-state text and NO button when no cached explanation (null body)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    expect(body.querySelector('.diff-explanation-generate-btn')).toBeNull();
    expect(body.querySelector('.missing').textContent).toContain('尚無差異推論');
  });

  it('shows empty-state and NO button when fetch throws (no-cache case)', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('404'));
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    expect(body.querySelector('.diff-explanation-generate-btn')).toBeNull();
    expect(body.querySelector('.missing')).not.toBeNull();
  });

  it('shows empty-state and NO button when versionA is null', async () => {
    state.versionA = null;
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    expect(body.querySelector('.diff-explanation-generate-btn')).toBeNull();
    expect(body.querySelector('.missing')).not.toBeNull();
  });

  it('shows empty-state and NO button when versionB is null', async () => {
    state.versionB = null;
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    expect(body.querySelector('.diff-explanation-generate-btn')).toBeNull();
    expect(body.querySelector('.missing')).not.toBeNull();
  });
});

// ── explanation content rendering ─────────────────────────────────

describe('renderExplanationContent — field coverage', () => {
  it('renders confidence badge with known confidence', async () => {
    const explanation = makeExplanation({ confidence: 'medium' });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ explanation }),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const badge = container.querySelector('.confidence-badge');
    expect(badge.textContent).toContain('中');
    expect(badge.className).toContain('confidence-badge-medium');
  });

  it('uses confidence value as fallback for unknown confidence', async () => {
    const explanation = makeExplanation({ confidence: 'very-high' });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ explanation }),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const badge = container.querySelector('.confidence-badge');
    expect(badge.textContent).toContain('very-high');
  });

  it('null confidence renders as 未評估 (unknown), NOT 低 (no 謊報)', async () => {
    const explanation = makeExplanation({ confidence: null });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ explanation }),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const badge = container.querySelector('.confidence-badge');
    // 缺值＝來源未評估信心 → 誠實退 unknown，不謊報成低信心（H1 誠實化原則）
    expect(badge.className).toContain('confidence-badge-unknown');
    expect(badge.className).not.toContain('confidence-badge-low');
    expect(badge.textContent).toContain('未評估');
  });

  it('renders linked_resources section when resources exist', async () => {
    const explanation = makeExplanation({ linked_resources: ['fileA.js', 'fileB.ts'] });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ explanation }),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const ul = container.querySelector('.source-list');
    expect(ul).not.toBeNull();
    expect(ul.querySelectorAll('li').length).toBe(2);
  });

  it('omits resources section when linked_resources is empty', async () => {
    const explanation = makeExplanation({ linked_resources: [] });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ explanation }),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    expect(container.querySelector('.source-list')).toBeNull();
  });

  it('omits resources section when linked_resources is null — || branch', async () => {
    const explanation = makeExplanation({ linked_resources: null });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ explanation }),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    expect(container.querySelector('.source-list')).toBeNull();
  });

  it('skips field sections when field text is null', async () => {
    const explanation = makeExplanation({
      impact_summary: null,
      possible_purpose: null,
      caution: null,
    });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ explanation }),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    // Only confidence badge + regen button, no field sections
    const sections = body.querySelectorAll('.detail-section');
    expect(sections.length).toBe(0);
  });
});

// ── H1 confidence honesty (未評估 ≠ 低信心) ─────────────────────────

describe('H1 confidence honesty in diff explanation', () => {
  it('missing confidence (undefined) renders 未評估, not 低', async () => {
    const explanation = makeExplanation({ confidence: undefined });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ explanation }),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const badge = container.querySelector('.confidence-badge');
    expect(badge.textContent).toContain('未評估');
    expect(badge.className).not.toContain('confidence-badge-low');
  });
});

// generate button click tests removed in T5-V (丙案 D1): diff-explanation generation
// retired; display is read-only with no generate/regen button.
