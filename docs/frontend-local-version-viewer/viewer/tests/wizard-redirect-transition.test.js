import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { redirectWithTransition } from '../js/ui-wizard.js';

describe('redirectWithTransition (spec §6.2)', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div class="wizard-shell"></div>';
    vi.useFakeTimers();
  });
  afterEach(() => { vi.useRealTimers(); });

  it('adds .leaving class to .wizard-shell immediately', () => {
    const setLocation = vi.fn();
    redirectWithTransition('/index.html', setLocation);
    expect(document.querySelector('.wizard-shell').classList.contains('leaving')).toBe(true);
    expect(setLocation).not.toHaveBeenCalled();
  });

  it('delays setLocation by ~620ms (animation duration)', () => {
    const setLocation = vi.fn();
    redirectWithTransition('/index.html', setLocation);
    vi.advanceTimersByTime(619);
    expect(setLocation).not.toHaveBeenCalled();
    vi.advanceTimersByTime(2);
    expect(setLocation).toHaveBeenCalledWith('/index.html');
  });

  it('still redirects if no .wizard-shell present (fallback)', () => {
    document.body.innerHTML = '';
    const setLocation = vi.fn();
    redirectWithTransition('/index.html', setLocation);
    vi.advanceTimersByTime(700);
    expect(setLocation).toHaveBeenCalledWith('/index.html');
  });
});

describe('styles.css .onboarding-card viewerIn', () => {
  it('defines viewerIn keyframe without opacity:0 starter', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const url = await import('node:url');
    const dir = path.dirname(url.fileURLToPath(import.meta.url));
    const css = fs.readFileSync(path.resolve(dir, '../styles.css'), 'utf8');
    expect(css).toMatch(/@keyframes\s+viewerIn\s*{/);
    const m = css.match(/@keyframes\s+viewerIn\s*{([^}]+)}/);
    expect(m[1]).not.toMatch(/opacity\s*:\s*0\b/);
  });

  it('.onboarding-card has viewerIn animation', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const url = await import('node:url');
    const dir = path.dirname(url.fileURLToPath(import.meta.url));
    const css = fs.readFileSync(path.resolve(dir, '../styles.css'), 'utf8');
    // Match within .onboarding-card { ... animation: viewerIn ... }
    const block = css.match(/\.onboarding-card\s*{[^}]*animation\s*:\s*viewerIn/);
    expect(block).not.toBeNull();
  });
});
