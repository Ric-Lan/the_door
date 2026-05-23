import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { appendUserNotesSection, relativeTime } from '../js/ui-notes.js';

const flushPromises = () => new Promise(resolve => setTimeout(resolve, 0));

function makeContainer() {
  return document.createElement('div');
}

function makeNote(overrides = {}) {
  return {
    display_name: 'Alice',
    comment: 'Great feature.',
    created_at: '2024-03-15T09:30:00',
    ...overrides,
  };
}

beforeEach(() => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ notes: [] }),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── structure ─────────────────────────────────────────────────────

describe('appendUserNotesSection — structure', () => {
  it('appends section with h3, name input, textarea, submit button', async () => {
    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const section = container.querySelector('.user-notes-section');
    expect(section).not.toBeNull();
    expect(section.querySelector('h3').textContent).toBe('使用者備註');
    expect(section.querySelector('.user-notes-name')).not.toBeNull();
    expect(section.querySelector('.user-notes-comment')).not.toBeNull();
    expect(section.querySelector('.user-notes-submit')).not.toBeNull();
    expect(section.querySelector('.user-notes-history')).not.toBeNull();
  });
});

// ── initial load ──────────────────────────────────────────────────

describe('appendUserNotesSection — initial load', () => {
  it('shows notes in history when notes are returned', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ notes: [makeNote(), makeNote({ display_name: 'Bob', created_at: null })] }),
    });
    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const history = container.querySelector('.user-notes-history');
    expect(history.querySelectorAll('.user-note').length).toBe(2);
    expect(history.querySelector('.user-notes-history-label')).not.toBeNull();
    // created_at null → empty string slice
    const notes = history.querySelectorAll('.user-note');
    const timeEl = notes[0].querySelector('.note-time');
    expect(timeEl).not.toBeNull();
  });

  it('leaves history empty when no notes returned', async () => {
    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const history = container.querySelector('.user-notes-history');
    expect(history.children.length).toBe(0);
    expect(history.querySelector('.user-notes-history-label')).toBeNull();
  });

  it('treats missing notes key as empty (body.notes || [] branch)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const history = container.querySelector('.user-notes-history');
    expect(history.children.length).toBe(0);
  });

  it('silently ignores load failure — section still exists', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network fail'));
    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    expect(container.querySelector('.user-notes-section')).not.toBeNull();
  });

  it('includes versionA and versionB in query when provided', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ notes: [] }),
    });
    const container = makeContainer();
    appendUserNotesSection(container, 'baseline', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const url = fetchSpy.mock.calls[0][0];
    expect(url).toContain('version_a=vA');
    expect(url).toContain('version_b=vB');
  });

  it('omits versionA when null', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ notes: [] }),
    });
    const container = makeContainer();
    appendUserNotesSection(container, 'baseline', null, 'vB', 'feat-1');
    await flushPromises();

    const url = fetchSpy.mock.calls[0][0];
    expect(url).not.toContain('version_a');
    expect(url).toContain('version_b=vB');
  });

  it('omits versionB when null', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ notes: [] }),
    });
    const container = makeContainer();
    appendUserNotesSection(container, 'baseline', 'vA', null, 'feat-1');
    await flushPromises();

    const url = fetchSpy.mock.calls[0][0];
    expect(url).toContain('version_a=vA');
    expect(url).not.toContain('version_b');
  });
});

// ── submit validation ─────────────────────────────────────────────

describe('appendUserNotesSection — submit validation', () => {
  it('shows error and does not fetch when name is empty', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ notes: [] }),
    });
    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const section = container.querySelector('.user-notes-section');
    section.querySelector('.user-notes-comment').value = 'some comment';
    section.querySelector('.user-notes-submit').click();
    await flushPromises();

    const errorEl = section.querySelector('.user-notes-error');
    expect(errorEl.hidden).toBe(false);
    expect(errorEl.textContent).toContain('名稱');
    // only the initial GET was called
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('shows error and does not fetch when comment is empty', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ notes: [] }),
    });
    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const section = container.querySelector('.user-notes-section');
    section.querySelector('.user-notes-name').value = 'Alice';
    section.querySelector('.user-notes-submit').click();
    await flushPromises();

    const errorEl = section.querySelector('.user-notes-error');
    expect(errorEl.hidden).toBe(false);
    expect(errorEl.textContent).toContain('意見');
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});

// ── submit success ────────────────────────────────────────────────

describe('appendUserNotesSection — submit success', () => {
  it('POSTs note, clears inputs, prepends note to history', async () => {
    const note = makeNote();
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ notes: [] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ note }) });

    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const section = container.querySelector('.user-notes-section');
    section.querySelector('.user-notes-name').value = 'Alice';
    section.querySelector('.user-notes-comment').value = 'Great!';
    section.querySelector('.user-notes-submit').click();
    await flushPromises();

    const nameInput = section.querySelector('.user-notes-name');
    const commentInput = section.querySelector('.user-notes-comment');
    expect(nameInput.value).toBe('');
    expect(commentInput.value).toBe('');

    const history = container.querySelector('.user-notes-history');
    const noteEl = history.querySelector('.user-note');
    expect(noteEl).not.toBeNull();
    expect(noteEl.querySelector('summary').textContent).toBe('Alice');
  });

  it('prepends note after existing heading when history already has notes', async () => {
    const note = makeNote();
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ notes: [makeNote({ display_name: 'Bob' })] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ note }) });

    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const section = container.querySelector('.user-notes-section');
    section.querySelector('.user-notes-name').value = 'Alice';
    section.querySelector('.user-notes-comment').value = 'A comment.';
    section.querySelector('.user-notes-submit').click();
    await flushPromises();

    const history = container.querySelector('.user-notes-history');
    const heading = history.querySelector('.user-notes-history-label');
    expect(heading).not.toBeNull();
    // Alice's note should be right after the heading
    expect(heading.nextElementSibling.querySelector('summary').textContent).toBe('Alice');
  });
});

// ── submit failure ────────────────────────────────────────────────

describe('appendUserNotesSection — submit failure', () => {
  it('shows error message from api response', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ notes: [] }) })
      .mockResolvedValueOnce({ ok: false, json: async () => ({ error: { message: 'duplicate entry' } }) });

    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const section = container.querySelector('.user-notes-section');
    section.querySelector('.user-notes-name').value = 'Alice';
    section.querySelector('.user-notes-comment').value = 'comment';
    section.querySelector('.user-notes-submit').click();
    await flushPromises();

    const errorEl = section.querySelector('.user-notes-error');
    expect(errorEl.hidden).toBe(false);
    expect(errorEl.textContent).toContain('duplicate entry');
  });

  it('uses fallback "新增備註失敗。" when no error message', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ notes: [] }) })
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) });

    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const section = container.querySelector('.user-notes-section');
    section.querySelector('.user-notes-name').value = 'Alice';
    section.querySelector('.user-notes-comment').value = 'comment';
    section.querySelector('.user-notes-submit').click();
    await flushPromises();

    const errorEl = section.querySelector('.user-notes-error');
    expect(errorEl.textContent).toBe('新增備註失敗。');
  });

  it('shows network error message on fetch throw', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ notes: [] }) })
      .mockRejectedValueOnce(new Error('connection lost'));

    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const section = container.querySelector('.user-notes-section');
    section.querySelector('.user-notes-name').value = 'Alice';
    section.querySelector('.user-notes-comment').value = 'comment';
    section.querySelector('.user-notes-submit').click();
    await flushPromises();

    const errorEl = section.querySelector('.user-notes-error');
    expect(errorEl.hidden).toBe(false);
    expect(errorEl.textContent).toContain('connection lost');
  });

  it('uses "network error" fallback when thrown error has no message', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ notes: [] }) })
      .mockRejectedValueOnce({});

    const container = makeContainer();
    appendUserNotesSection(container, 'diff', 'vA', 'vB', 'feat-1');
    await flushPromises();

    const section = container.querySelector('.user-notes-section');
    section.querySelector('.user-notes-name').value = 'Alice';
    section.querySelector('.user-notes-comment').value = 'comment';
    section.querySelector('.user-notes-submit').click();
    await flushPromises();

    const errorEl = section.querySelector('.user-notes-error');
    expect(errorEl.textContent).toContain('network error');
  });
});

// ── relativeTime ──────────────────────────────────────────────────

describe('relativeTime', () => {
  const now = new Date('2026-05-23T12:00:00Z').getTime();
  it('seconds → 剛剛', () => {
    expect(relativeTime(now - 30 * 1000, now)).toBe('剛剛');
  });
  it('minutes', () => {
    expect(relativeTime(now - 5 * 60 * 1000, now)).toBe('5 分鐘前');
  });
  it('hours', () => {
    expect(relativeTime(now - 3 * 3600 * 1000, now)).toBe('3 小時前');
  });
  it('days', () => {
    expect(relativeTime(now - 2 * 86400 * 1000, now)).toBe('2 天前');
  });
  it('older than 7d falls back to UTC MM-DD HH:MM', () => {
    const past = new Date('2026-04-01T08:30:00Z').getTime();
    expect(relativeTime(past, now)).toBe('04-01 08:30');
  });
});
