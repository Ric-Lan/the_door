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

describe('appendDiffExplanationSection — initial load', () => {
  it('shows cached explanation content and a regen button', async () => {
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
    // generate button should NOT be the primary "生成" button — regen is shown instead
    const btns = body.querySelectorAll('.diff-explanation-generate-btn');
    expect(btns.length).toBeGreaterThan(0);
    expect(btns[btns.length - 1].textContent).toContain('重新生成');
  });

  it('shows generate button when no cached explanation (null body)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    const btn = body.querySelector('.diff-explanation-generate-btn');
    expect(btn).not.toBeNull();
    expect(btn.textContent).toBe('生成差異推論');
  });

  it('shows generate button when fetch throws (no-cache case)', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('404'));
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    const btn = body.querySelector('.diff-explanation-generate-btn');
    expect(btn).not.toBeNull();
  });

  it('shows generate button when versionA is null', async () => {
    state.versionA = null;
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    const btn = body.querySelector('.diff-explanation-generate-btn');
    expect(btn).not.toBeNull();
  });

  it('shows generate button when versionB is null', async () => {
    state.versionB = null;
    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    const btn = body.querySelector('.diff-explanation-generate-btn');
    expect(btn).not.toBeNull();
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

// ── generate button click ─────────────────────────────────────────

describe('appendDiffExplanationSection — generate button', () => {
  it('disables button and changes text on click', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ explanation: makeExplanation() }) });

    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const btn = container.querySelector('.diff-explanation-generate-btn');
    btn.click();

    expect(btn.disabled).toBe(true);
    expect(btn.textContent).toBe('生成中…');
    await flushPromises();
  });

  it('shows result and regen button on generate success', async () => {
    const explanation = makeExplanation();
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ explanation }) });

    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    container.querySelector('.diff-explanation-generate-btn').click();
    await flushPromises();

    const body = container.querySelector('.diff-explanation-body');
    expect(body.querySelector('.confidence-badge')).not.toBeNull();
    const lastBtn = body.querySelector('.diff-explanation-generate-btn');
    expect(lastBtn.textContent).toContain('重新生成');
  });

  it('re-enables button and shows error on generate failure (api error)', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
      .mockResolvedValueOnce({ ok: false, json: async () => ({ error: { message: 'LLM error' } }) });

    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const btn = container.querySelector('.diff-explanation-generate-btn');
    btn.click();
    await flushPromises();

    expect(btn.disabled).toBe(false);
    const body = container.querySelector('.diff-explanation-body');
    expect(body.textContent).toContain('LLM error');
  });

  it('re-enables button and shows error on generate failure (no message)', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) });

    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const btn = container.querySelector('.diff-explanation-generate-btn');
    btn.click();
    await flushPromises();

    expect(btn.disabled).toBe(false);
    const body = container.querySelector('.diff-explanation-body');
    expect(body.textContent).toContain('未知錯誤');
  });

  it('re-enables button and shows error on network error', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
      .mockRejectedValueOnce(new Error('network down'));

    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    const btn = container.querySelector('.diff-explanation-generate-btn');
    btn.click();
    await flushPromises();

    expect(btn.disabled).toBe(false);
    expect(container.querySelector('.diff-explanation-body').textContent).toContain('network down');
  });

  it('uses "network error" fallback when thrown error has no message — || branch', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) })
      .mockRejectedValueOnce({});

    const container = makeContainer();
    appendDiffExplanationSection(container, 'feat-1');
    await flushPromises();

    container.querySelector('.diff-explanation-generate-btn').click();
    await flushPromises();

    expect(container.querySelector('.diff-explanation-body').textContent).toContain('network error');
  });
});
