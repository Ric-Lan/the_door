import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(__dirname, '../styles.css'), 'utf8');

describe('styles.css :root — Part 2 A-section tokens (11)', () => {
  const tokens = [
    '--term-bg', '--term-fg', '--term-toolbar',
    '--radius', '--radius-card',
    '--rail-bg', '--rail-bg-2', '--rail-line',
    '--rail-text', '--rail-muted', '--rail-dim',
  ];
  for (const t of tokens) {
    it(`defines ${t} in :root`, () => {
      // simplistic check: token appears in a :root { ... } block at file top
      const rootBlock = css.match(/:root\s*{([^}]+)}/);
      expect(rootBlock).toBeTruthy();
      expect(rootBlock[1]).toMatch(new RegExp(`${t}\\s*:`));
    });
  }
  it('does NOT add --font-sans / --font-mono to styles.css :root (those live in wizard.css scope per spec §1.3 B)', () => {
    const rootBlock = css.match(/:root\s*{([^}]+)}/);
    expect(rootBlock[1]).not.toMatch(/--font-sans\s*:/);
    expect(rootBlock[1]).not.toMatch(/--font-mono\s*:/);
  });
});

describe('styles.css shared progress region', () => {
  const required = [
    '.wizard-phasebar',
    '.wizard-phase',
    '@keyframes wizardIndet',
    '.wizard-steplist',
    '.wizard-sl-row',
    '.wizard-prog-live',
    '.wizard-pl-head',
    '.wizard-pl-feed',
    '.wizard-pl-line',
    '.wizard-pl-count',
    '.wizard-pl-dot',
    '@keyframes wizardPlPulse',
    '@keyframes wizardPlIn',
    '.wizard-spin',
    '@keyframes wizardSpin',
  ];
  for (const sel of required) {
    it(`defines selector or keyframe: ${sel}`, () => {
      // escape regex meta for "."
      const re = new RegExp(sel.replace(/[.@]/g, m => '\\' + m) + '\\b');
      expect(css).toMatch(re);
    });
  }

  it('wizardPlIn has no opacity:0 starter (spec §3.1 violation rewrite)', () => {
    const m = css.match(/@keyframes\s+wizardPlIn\s*{([^}]+)}/);
    expect(m).toBeTruthy();
    expect(m[1]).not.toMatch(/opacity\s*:\s*0\b/);
  });

  it('phasebar supports .failed state (per spec §5.3 phaseStatus failed branch)', () => {
    expect(css).toMatch(/\.wizard-phase\.failed\b/);
  });

  it('sl-row supports .failed and .skipped states', () => {
    expect(css).toMatch(/\.wizard-sl-row\.failed\b/);
    expect(css).toMatch(/\.wizard-sl-row\.skipped\b/);
  });
});

describe('styles.css @keyframes hygiene (spec §3.1)', () => {
  it('no @keyframes block contains opacity:0 starter (from / 0% / any %)', () => {
    const blocks = [...css.matchAll(/@keyframes\s+\w+\s*{([^@}]*(?:}[^@}]*)*?)}/g)];
    for (const b of blocks) {
      // check each declaration block within
      expect(b[1]).not.toMatch(/opacity\s*:\s*0\b/);
    }
  });
});
